# PLAN TEMPORARY — Ganti Telemetri Node / Status Lokasi / Informasi pengiriman dengan Monitoring Harga

Status: **DRAF SEMENTARA (belum disetujui, belum ada kode yang diubah)** · 28 Okt 2026
Sasaran: tab **Overview** (`frontend/app/page.tsx`)
Boleh dihapus kapan saja. Tidak di-commit.

---

## 1. Pendapat saya atas idenya (jujur, bukan menyenangkan)

| Bagian yang mau dihapus | Isi sebenarnya | Nilaiku |
|---|---|---|
| **Telemetri Node** | `components/NodeTelemetry.tsx` (101 baris). Hanya berisi kalau ada lokasi dipilih dari dropdown top bar; default-nya cuma tulisan "Belum ada lokasi yang disorot…" | **Setuju diganti.** Kartu yang keadaan bawaannya kosong adalah kandidat terbaik untuk dilepas. |
| **Status Lokasi** | `StatusLocationList` (di-ekspor dari `components/SupplyMap.tsx`, dipakai halaman di baris 1608). Daftar lokasi + status, fungsinya melayang-kan peta ke titik (`lib/map-sorot.ts`) | **Setuju diganti.** Isinya menduplikasi pin di peta; fungsi "terbang ke lokasi" tetap bisa dari pin yang diklik. |
| **Informasi pengiriman** | `components/ShipmentCard.tsx` (199 baris) + `lib/shipment-card.ts` (313 baris) — dibangun 16 Okt atas permintaan Anda (Arah A riset industri) | **Boleh diganti, tapi ini satu-satunya bukti "barang bergerak" di Overview.** Isinya masih terjangkau di tab Pemasok (`ShipmentBoard`) dan tab Decision & Evidence (jalur persetujuan). Saranku: lepas dari Overview, **komponennya jangan dihapus** supaya satu baris bisa memulihkannya kalau juri menanyakannya. |

Catatan penting: ketiganya bukan "kontrol" berstate, jadi pola kerjanya adalah **penghapusan tingkat-mount** (skill `ui-control-removal` langkah 8): lepas JSX + import + hook data + prop; berkas komponen tetap ada.

Yang **hilang dari tata letak**: satu baris 440 px (`#ov-telemetri` `.overview-pair`) + satu blok kartu kiriman. Itu ruang yang dipakai panel harga. Nav "Lompat ke bagian" Overview turun dari 5 → 4 tujuan (Ringkasan · Peta & antrean · Kecukupan · Harga) — masih memenuhi batas minimum 3 di `docs/design.md` §24.

---

## 2. Inventaris kode yang tersentuh (hasil pemetaan, bukan dugaan)

**Dilepas dari halaman**
- `app/page.tsx:1572-1583` → blok `#ov-kiriman` + `<ShipmentCard>`
- `app/page.tsx:1591-1621` → blok `.overview-pair #ov-telemetri` (`<NodeTelemetry>` + `<StatusLocationList>`)
- `app/page.tsx:132` import `ShipmentCard`, `:126` import `NodeTelemetry`, `:109` import `StatusLocationList`
- `app/page.tsx:520-521` `focusRow` / `focusTotal` + `:133` import `focusNote, focusPick, focusRows` — jadi tak terpakai setelah kartu kiriman hilang. `focusPick` tetap hidup di `SupplyMap.tsx:1012`; sorotan jalur di peta **tidak boleh ikut mati** (digerakkan `focusedRoute`, bukan kartu).

**Diubah, bukan dihapus**
- `lib/section-jump.ts:48-54, 80-103` — buang `kiriman` + `telemetri`, tambah `harga: "ov-harga"`; `overviewSections()` berhenti menerima `hasShipments`.
- `lib/route-focus.ts:92` `focusNote` — setelah kartu dilepas pemakaian di luar `tests/` tinggal nol → hapus fungsi + tesnya (skill `ui-control-removal` langkah 5).
- `app/globals.css` — `.overview-pair`, `.node-telemetry*`, `.status-location-list`, `.shipment-card*` (cek dulu pemakaian lain sebelum dihapus; blok yang ditinggal akan dijaga tesnya sendiri).

**Tidak disentuh (sengaja)**
- `components/ShipmentCard.tsx`, `components/NodeTelemetry.tsx`, `lib/shipment-card.ts`, `lib/map-console.ts` (nodeGauges), `StatusLocationList` di `SupplyMap.tsx` — tetap ada + tetap diuji.
- `components/ShipmentBoard.tsx` di `SupplierBoard.tsx:249` — komponen berbeda, jangan dikira sama.

**Tes yang harus ikut berubah**
- `tests/overview-section-order.test.ts` — urutan nav vs render; tambah `ov-harga`, hapus asersi `ov-kiriman`.
- `tests/section-jump.test.tsx` — label "Telemetri"/"Kiriman" di fixture.
- `tests/shipment-card*.test.*` (2 berkas, 535 baris) — tetap hijau karena menguji komponen, bukan halaman; tambah satu asersi di tes halaman: `expect(src).not.toContain("<ShipmentCard")` dan `not.toContain("Informasi pengiriman")`.
- `tests/supply-map-layer.test.tsx` — StatusLocationList tetap diuji (komponennya tetap ada), tidak dihapus.

---

## 3. Data yang memberi makan grafik (ringkas — detail di laporan sebelumnya)

- Sumber: **PIHPS Bank Indonesia** `GET https://www.bi.go.id/hargapangan/WebSite/TabelHarga/GetGridDataKomoditas`, harian, per provinsi/kota, satuan kg. Terbukti hidup hari ini: Telur Ayam Ras Segar DKI 22–28 Okt = 25.700 (flat), nasional 29.600 → 29.500; 21 komoditas; satu request bisa mengembalikan 30 kolom tanggal.
- Hari kerja saja (Sabtu–Minggu kosong) → grafik **tidak boleh** menyambung garis melewati tanggal kosong; titip hilang, bukan 0.
- Komoditas proyek: telur, ayam, beras **ada**; **wortel tidak ada** di PIHPS → wajib label `estimasi_internal`, garis putus-putus, badge abu.
- Wilayah: 8 kota demo punya baris kota; **Cianjur tidak ada** → fallback Provinsi Jawa Barat + catatan sumber.
- Endpoint internal baru: `GET /price/monitor?commodity=&region=&days=` (tabel baru `price_observations`; **jangan menimpa `price_signals`** yang dipakai mesin keputusan).

---

## 4. Desain UI yang saya usulkan

```
┌ #ov-harga ───────────────────────────────────────────────────────────────┐
│ Monitor harga komoditas              [Telur][Ayam][Beras][Wortel] [7|30|90]│
│ Sumber: PIHPS BI · data 28 Okt 2026 · diperbarui 16.12 WIB               │
├───────────────────────────────────────────┬──────────────────────────────┤
│  27.000 ┤                          ╭──     │ Harga hari ini               │
│         │        ╭───╮      ╭────╯        │   Rp 25.700 /kg     ▲ +0,8%  │
│  26.000 ┤  ╭─────╯   ╰──────╯              │                              │
│         │──╯                               │ Δ 7 hari   ▲ +2,4%           │
│  25.000 ┤                                  │ Tertinggi 30 hari  Rp 26.300 │
│         └──────────────────────────────    │                              │
│          1   5   12   19   26   Okt        │ Pergerakan teratas (7 hari)  │
│                                            │  Medan       telur  ▲ +6,1%  │
│  ● telur  ● ayam  ● beras  ┄ wortel        │  Palembang   ayam   ▼ −3,4%  │
└───────────────────────────────────────────┴──────────────────────────────┘
```

**Keputusan tampilan (dan alasannya)**
1. **Satu grafik garis multi-komoditas**, bukan empat grafik kecil. Tujuannya "scan": mata membandingkan bentuk tren, bukan membaca angka.
2. **Sumbu X tanggal bisnis apa adanya.** Titik Sabtu/Minggu tidak diinterpolasi; tooltip menulis "data tidak dipublikasikan" bila tanggal itu kosong. Ini yang membuat panel jujur, bukan terlihat rapi.
3. **Rentang 7/30/90 hari** sebagai pil, bawaan **30 hari** (satu request = satu kolom per tanggal, jadi murah).
4. **Warna dari token, bukan hex**: garis utama `var(--accent-strong)`, estimasi `var(--ink-muted)` putus-putus, naik `var(--status-danger)` / turun `var(--status-safe)` (konvensi harga pangan: naik = buruk). Δ selalu diberi tanda +/−, tidak mengandalkan warna saja.
5. **Kartu kanan** memakai lingkup lokasi yang sedang aktif di dropdown top bar → panel ini ikut "bercerita" dengan peta, tidak jadi pulau data.
6. **Badge sumber wajib** di kepala panel. Kalau baris itu bukan PIHPS (wortel, Cianjur) → badge abu + garis putus-putus + tooltip "estimasi internal, bukan PIHPS".
7. **Tinggi grafik px tetap (260–280)**, bukan persen — `ResponsiveContainer` di rantai flex pernah menghitung `height: 100%` jadi 0 (bug nyata yang sudah tercatat di `StockChart.tsx`).
8. **Pola implementasi meniru `StockChart.tsx`**: recharts sudah jadi dependensi, ada guard `mounted` (SSR) dan placeholder skeleton dengan tinggi sama supaya tidak ada lompatan layout.
9. **Aksesibilitas**: `<p class="sr-only">` merangkum tren ("telur naik 2,4% dalam 7 hari, tertinggi 26.300 pada 24 Okt"), target pil ≥ 32px, fokus terlihat, `aria-label` per titik tidak praktis → sediakan tabel ringkas 5 baris terakhir yang bisa dibuka.
10. **States**: loading (skeleton tinggi sama) · kosong ("belum ada snapshot harga untuk komoditas ini") · error + tombol "Coba lagi" · data parsial (sebagian kota kosong, ditandai "—", bukan 0).

---

## 5. Langkah kerja (satu langkah = satu laporan, berhenti setelah tiap langkah)

1. **Fetcher baca-saja** `backend/scripts/tarik_harga_pihps.py` → tarik 4 komoditas × 10 kota × 30 hari → simpan snapshot JSON + ringkasan cetak. Belum menyentuh DB.
   *Gate*: jalankan, tunjukkan 3 baris nyata + jumlah titik kosong (weekend) + komoditas yang harus fallback.
2. **Logika murni + TDD** `frontend/lib/price-monitor.ts`: bentuk seri, jarak hari bisnis, Δ harian/7 hari, label sumber, penanda estimasi. Tes ditulis lebih dulu (merah → hijau).
   *Gate*: `vitest run tests/price-monitor.test.ts` hijau.
3. **Backend**: model + migrasi `price_observations`, `GET /price/monitor`, tes API + tes "jangan sentuh `price_signals`".
   *Gate*: `pytest` berkas terkait hijau, `alembic check` bersih.
4. **Komponen UI** `components/PriceMonitor.tsx` + CSS + tes SSR (kepala panel, badge sumber, keadaan kosong/estimasi).
   *Gate*: `vitest run` berkas baru hijau + `tsc --noEmit` + `npm run lint`.
5. **Lepas tiga bagian lama** (langkah 8 skill `ui-control-removal`): JSX + import + hook + prop, `lib/section-jump.ts`, `focusNote`, CSS mati + tes kontrak CSS, balik tes menjadi asersi ketiadaan + kontrol positif ("Cekukupan" masih ada), pasang `#ov-harga` di posisi yang sama.
   *Gate*: suite penuh `vitest run` + `tsc` + `lint` hijau; DOM hidup: `[class*="node-telemetry"]` = 0, `#ov-telemetri` = 0, `<h3>Telemetri Node</h3>` = 0, `<h3>Status Lokasi</h3>` = 0, `<h3>Informasi pengiriman</h3>` = 0, sedangkan `#ov-harga` dan `#ov-kecukupan` ada.
6. **Demo-hardening**: snapshot dibekukan per tanggal demo + fallback "data terakhir 27 Okt" kalau jaringan venue mati; perbarui `TODO.md`, `memory/global/decisions.md`, `docs/design.md` §komponen.
   *Gate*: build produksi (`next build` dengan patch exFAT, jangan cwd di folder output) + cek halaman di browser.

---

## 6. Risiko

| Risiko | Mitigasi |
|---|---|
| Endpoint PIHPS berubah (bukan API resmi) | Snapshot disimpan ke disk; UI selalu bisa menampilkan snapshot terakhir + tanggalnya. Fetcher gagal = panel tetap jujur, bukan kosong. |
| Angka demo berubah tiap hari → cerita juri tidak konsisten | Bekukan snapshot per tanggal demo; tampilkan "data 28 Okt 2026". |
| Menghapus "Informasi pengiriman" melemahkan narasi rantai pasok | Komponen tidak dihapus; isi masih ada di tab Pemasok + Decision & Evidence. Bisa dipasang ulang satu baris. |
| Grafik harga bertabrakan makna dengan "Procurement Price Deviation" di KPI | Panel harga = acuan pasar; deviasi = quote pemasok vs acuan. Tulis bedanya di subjudul panel. |
| Ruang hilang 440 px tapi grafik butuh 300 px | Sisa ruang dipakai kartu ringkas kanan (bukan dibiarkan kosong). |

## 7. Pertanyaan terbuka (butuh keputusan Anda)

1. **Informasi pengiriman**: ikut dilepas (rekomendasi saya: ya, komponen disimpan) atau tetap di Overview?
2. **Cakupan panel**: 4 komoditas proyek saja, atau 21 komoditas PIHPS (jadi "monitoring harga pangan" yang lebih lebar)?
3. **Grafik**: satu komoditas per tampilan (bersih) atau multi-garis sekaligus (padat, cocok untuk scan)? Rekomendasi saya: multi-garis.
4. Panel ini menggantikan **posisi** ketiganya (#ov-harga di bawah Kecukupan) atau ditaruh **paling atas** Overview sesudah peta?

---

## 8. HASIL PENERAPAN (28 Okt 2026) — plan ini sudah dieksekusi

Pemilik meminta "gunakan skill ui ux dan terapkan semuanya", jadi empat pertanyaan terbuka
di §7 dijawab dengan rekomendasi di dokumen ini dan langsung dikerjakan:

1. **Informasi pengiriman ikut dilepas** dari Overview; komponen + tesnya tetap ada sehingga
   bisa dipasang ulang satu baris. Isinya masih terbaca di tab Pemasok (`ShipmentBoard`) dan
   di Decision & Evidence.
2. **Cakupan data = 21 komoditas PIHPS** (semua yang diterbitkan), tetapi chip panel menampilkan
   tiga komoditas proyek (beras/telur/ayam). Wortel disebut sebagai komoditas tanpa acuan PIHPS.
3. **Multi-garis**, dengan **mode bawaan Indeks (basis 100)** dan mode Rupiah sebagai pilihan —
   sebab level harga beras ~Rp17 ribu vs ayam ~Rp39 ribu membuat grafik rupiah terbaca datar.
4. **Panel menempati posisi ketiganya** (`#ov-harga`, tepat setelah Kecukupan).

### Bedanya dengan rencana awal (§5 langkah 3)

Tabel `price_observations` **tidak dibuat**. Data harga adalah salinan pakan eksternal, bukan
keadaan operasional; menyimpannya sebagai snapshot JSON (`data/harga_pihps/pihps_latest.json`)
membuat panel tetap terbaca tanpa jaringan venue, menyimpan jejak sumber (`source_url` +
`fetched_at`) apa adanya, dan tidak menambah migrasi pada skema demo di tengah pekerjaan lain
yang belum di-commit. Logikanya diuji tanpa DB (`backend/tests/test_harga_monitor.py`, 17 tes).

### Bukti gerbang

| Gerbang | Hasil |
|---|---|
| `pytest tests/test_harga_monitor.py` | 17 lulus |
| `pytest tests/test_openapi_artifact_drift.py` | lulus (artefak diregenerasi) |
| `ruff check app/ scripts/ tests/test_harga_monitor.py` | bersih |
| `vitest run` (seluruh frontend) | 189 berkas / 2.087 tes lulus |
| `tsc --noEmit` | 0 galat |
| `next lint` | 0 peringatan |
| `next build` | sukses |
| Verifikasi DOM hidup (:3010) | panel tampil dengan data nyata; `#ov-kiriman` = 0, `#ov-telemetri` = 0, `<h3>Telemetri Node</h3>` = 0, `<h3>Status Lokasi</h3>` = 0; tanpa galat konsol |

### Sisa risiko yang perlu keputusan pemilik

- Snapshot dibekukan per tanggal demo belum diotomasi: jalankan ulang penarik sehari sebelum
  demo lalu jangan tarik lagi (`pihps_latest.json` di-commit, arsip harian di-gitignore).
- Endpoint PIHPS bukan API ber-SLA; kalau berubah, panel menampilkan snapshot terakhir + tanggalnya
  (bukan angka karangan), dan penarik perlu disesuaikan.
