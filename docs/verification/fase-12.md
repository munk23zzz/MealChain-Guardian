# Fase 12 — Peta: kotak "Info map" + estimasi tiba perjalanan kiriman dari DB

Tanggal: 2026-10-16 · Assignee: Hermes · Repo: `E:\hackathon\HackathonAWS\mealchain-guardian`
Branch: `feature/sprint2-decision-intelligence` (belum ada commit/push untuk fase ini)

## Permintaan pemilik (kutip apa adanya)

> "untuk teks legenda map ganti menjadi info map dan isi nya gimana caranya informasi nya di susun
> rapih atau ada modifikasi isi nya, lalu ketika mengaktifkan jalur kiriman tampilkan juga waktu
> estimasi sampai dan perlu di ingat bahwa jalur kiriman itu adalah di mana menampilkan perjalan
> dari barang yang di antar dari suplier ke tujuan, so pastikan sinkron dengan database"

Setelah ditanya dua pertanyaan (cara ETA + susunan isi kotak), pemilik memilih:

> "anda buatkan juga databasenya sekalian dengan beberapa data lainnya anda harus menggunakan
> perhitungan waktu yang sesuai dengan realnya"

→ ETA **tidak** dibuat sebagai estimasi bersyarat ("jika berangkat sekarang"); jam keberangkatan
kiriman dibuat **nyata di DB**, lalu estimasi tiba dihitung server dari jam itu + waktu tempuh OSRM.
Isi kotak "Info map" mengikuti **Opsi A** (hanya kelompok yang lapisannya hidup, plus baris
perjalanan), dengan judul yang terlihat.

## 1. Temuan audit SEBELUM perubahan

| # | Temuan | Bukti |
|---|---|---|
| 1 | **`batch_id` dikirim `"None"` (string) untuk SEMUA rute.** Endpoint tidak memilih `Batch.id`; `build_route_payloads` melakukan `str(None)`. Akibatnya identitas kiriman hilang — di klien semua baris ber-`id` sama sehingga klik garis bisa membuka popup baris yang salah begitu ada 2+ kiriman ke tujuan yang sama. | `SELECT` di `backend/app/api/supplier_routes.py` (dulu `"batch_id": None`) |
| 2 | **`harvested_at` tidak pernah dikirim** walau ada di DB — padahal itu konteks umur barang terhadap waktu tempuh. | kolom ada di `batches`, tidak ada di payload |
| 3 | **DB tidak punya jam keberangkatan kiriman sama sekali** (tidak ada `dispatched_at`/`shipped_at`). Yang ada: `road_routes.duration_s` (waktu tempuh OSRM), `batches.usable_until`, `batches.harvested_at`. → "estimasi tiba" apa pun sebelum fase ini adalah **angka karangan**. | `\d batches`; `grep -rn "dispatched\\|shipped_at" backend/app` → kosong |
| 4 | Isi kotak legenda **tidak mengikuti lapisan yang hidup**: keterangan pemasok tetap tampil walau sakelar pemasok mati, dan entri "Jalur kiriman gagal uji" selalu ditulis walau tidak ada kiriman bergagal-uji di peta. | `components/SupplyMap.tsx` (`Boolean(suppliers) &&` — bukan `showSuppliers`) |

## 2. Perubahan

### (a) DB — migrasi `015_batch_dispatch`
- `batches.dispatched_at` TIMESTAMPTZ **NULLABLE**; `NULL` = **belum berangkat** (bukan jam nol).
- CHECK `batches_dispatch_after_harvest`: `dispatched_at IS NULL OR dispatched_at >= harvested_at`.
- Estimasi tiba **tidak disimpan** — dihitung saat baca (`app/core/journey.py`) supaya tidak ada dua
  sumber kebenaran yang bisa bertentangan.
- Seed kanonik: `dispatch_offset_hours` per batch (relatif `reference_time`, pola yang sama dengan
  `harvested_at_offset_hours`), divalidasi tidak mendahului panen **di seeder dan di DB**.

| Kiriman | Panen (jam dari REF) | Berangkat | Waktu tempuh OSRM | Keadaan pada REF |
|---|---|---|---|---|
| Jakarta (800 kg, Supplier A) | −36 | **−1** | 84,3 menit (110,4 km) | **di jalan**, tiba +24,3 menit |
| Surabaya (600 kg, Supplier B) | −24 | **−5** | 541,1 menit (730,8 km) | **di jalan**, tiba +4,0 jam |
| Cianjur (500 kg) | −18 | −15,5 | 3,5 menit (3,2 km) | sudah tiba |
| Bogor (500 kg) | −18 | −16,5 | 49,3 menit (62,8 km) | sudah tiba |
| Bandung (400 kg) | −210 | **NULL** | 52,2 menit (67,9 km) | **belum berangkat** |
| Semarang (200 kg, gagal uji) | −96 | −90 | — | sudah tiba (di luar peta: kedaluwarsa) |
| Palembang (250 kg, gagal uji) | −672 | −670 | — | sudah tiba (di luar peta: kedaluwarsa) |

### (b) API — `GET /supplier-routes`
- `batch_id` = **UUID asli** dari DB (`Batch.id`), plus `route_key` (kunci geometri) sebagai
  identitas cadangan; `harvested_at` ikut dikirim.
- Blok baru `journey` per rute: `dispatched_at`, `eta_at`, `state`, `state_label`, `travel_s`,
  `travel_min`, `travel_source`, `elapsed_min`, `remaining_min`, `progress`, `usable_until`,
  `arrives_before_usable_until`.
- `summary.journey_states` (jumlah per keadaan, urutan tetap dari `URUTAN_KEADAAN`).
- Modul murni `backend/app/core/journey.py` — empat aturan yang dipegang:
  1. tanpa jam berangkat → **tidak ada** `eta_at` (keadaan `belum_berangkat`), walau waktu tempuh
     tetap dilaporkan karena itu sifat JALUR, bukan sifat barang;
  2. sudah berangkat tapi waktu tempuh belum ada → keadaan `tidak_diketahui` (tidak diklaim tiba
     maupun di jalan);
  3. tepat pada estimasi tiba = `sudah_tiba`; tepat pada jam berangkat = `di_jalan`;
  4. `arrives_before_usable_until` hanya **perbandingan dua angka**, bukan klaim keamanan pangan.

### (c) Frontend
- Chip kanvas + `aria-label` kotak: **"Info map"** (dulu "Legenda peta").
- Isi kotak mengikuti lapisan hidup: status lokasi selalu · jalur kiriman saat sakelarnya hidup ·
  pemasok saat sakelarnya hidup · entri "Jalur kiriman gagal uji" hanya bila ada kiriman bergaris
  bergagal-uji (`routeLegendEntries(rows)`).
- Blok **Perjalanan kiriman** (maks 3 baris + "+N kiriman lain") menulis keadaan + jam tiba dari
  server, mis. `Jakarta · di jalan · tiba ± 22.54 (24 menit lagi)`; baris berwarna nada keadaan
  (`map-journey-moving|done|pending|unknown`).
- Tag bilah rincian: `2 jalur kiriman · 1 di jalan · tiba terdekat ± 22.54` → estimasi tiba terlihat
  **tanpa membuka apa pun**; jatuh kembali ke keterangan asal geometri bila tidak ada kiriman berjalan.
- Popup garis: `Berangkat: 16 Okt 2026 21.30 WIB`, `Estimasi tiba: ± 22.54 WIB · 24 menit lagi`,
  dan perbandingan dengan batas layak. **Nol aritmetika waktu di peramban** (hanya `formatClockWib`).
- Helper murni baru: `parseJourney`, `journeyTone`, `durationLabel`, `routeJourneyLine`,
  `routeJourneyRowClass`, `routeJourneyRows`, `nearestEta`, `routeEtaLines`, `formatClockWib`.

## 3. Bukti (dijalankan, bukan diklaim)

| Bukti | Hasil |
|---|---|
| `alembic upgrade head` di kontainer backend | `Running upgrade 014_road_routes -> 015_batch_dispatch` |
| `psql`: `select dispatched_at ... from batches` | 6 batch terisi, **Bandung NULL**; CHECK `batches_dispatch_after_harvest` terpasang |
| `python -m app.seed.seed_data --reference-time 2026-10-08T12:00:00+00:00 --with-demo-users --with-demo-suppliers` | idempoten; rute OSRM `0 diambil, 5 sudah ada, 0 gagal` |
| TDD RED → GREEN: `pytest tests/test_journey.py` | 6 lulus (murni: aritmetika, batas, keadaan, payload) |
| `pytest tests/test_supplier_routes_api.py tests/test_road_route.py` | 46 lulus (termasuk `batch_id` = himpunan id batch aktif di DB, `eta = berangkat + duration_s`, Bandung tanpa ETA, cache kosong → bukan "sudah tiba") |
| Suite backend penuh `pytest -q` | **900 passed, 3 skipped, 2 failed** — dua kegagalan `test_kpi_act_trace` & `test_kpi_safe_delivered_cost` karena **residu data**: `select status, count(*) from decisions` → 1 baris `executed` (16 Okt 15:42 UTC) dari sesi demo sebelumnya, sehingga metrik KPI memang `available` dan bukan `no_data`. Tidak menyentuh rute/batch. |
| Suite frontend penuh `npm run test` | **736 passed / 67 berkas** (naik dari 711: +25 tes baru) |
| `npx tsc --noEmit` · `npm run lint` | `TSC_EXIT=0` · `No ESLint warnings or errors` |

## 4. Susulan hari yang sama — tiga baris popup dibuang (arah pemilik)

Kutipan pemilik: *"Jarak lurus: 78,4 km, Tiba sebelum batas layak (25 Okt 2026) dan ini Jalur
jalan 1,41× jarak lurus (jalan berkelok, bukan garis lurus) hapus saja."*

Dibuang dari popup klik garis (`routePopupLines` + `routeEtaLines`):

- `Jarak lurus: 78,4 km`
- `Jalur jalan 1,41× jarak lurus (jalan berkelok, bukan garis lurus)`
- `Tiba sebelum batas layak (25 Okt 2026)`

Yang TETAP di popup: `Jalur jalan (OSRM): 110,4 km · ± 84 menit` · `Berangkat: 16 Okt 2026 21.30 WIB`
· `Estimasi tiba: ± 22.54 WIB · 24 menit lagi` · `Layak dipakai s/d 7 Nov 2026` ·
`Mutu kiriman: GAGAL UJI keamanan (dilaporkan apa adanya)`.

Tiga hal yang diputuskan sadar di sini:

1. **Tanggal layak pakai tidak hilang** — ia sudah ditulis sekali di baris `Layak dipakai s/d …`,
   jadi menghapus kalimat "Tiba sebelum batas layak (…)" menghilangkan pengulangan, bukan fakta.
2. **Peringatan sebaliknya TETAP ada** — `Estimasi tiba melewati batas layak pakai (dilaporkan apa
   adanya)` menandai masalah nyata; yang dibuang adalah kalimat yang menenangkan. Kalau pemilik
   ingin itu dibuang juga, kerjanya satu baris.
3. `straightKm` / `road.ratioVsStraight` tetap dikirim server (dipakai halaman Keamanan Pangan dan
   kartu Kiriman) — hanya berhenti dipampang di popup peta.

Bukti: `tests/supplier-routes.test.ts` (2 tes diubah jadi menuntut KETIADAAN ketiga baris — RED dulu,
2 gagal) dan tes baru **tingkat DOM** `tests/supply-map-layer.test.tsx` *"popup garis tidak lagi
memuat jarak lurus, rasio, dan kalimat batas layak"*: klik garis palsu → periksa `.map-popup-line`
(tiruan `FakePopup` diperluas dengan `setLngLat`/`addTo` + `popupLog`). Gerbang: frontend **773 lulus
/ 69 berkas**, `tsc --noEmit` 0, `next lint` 0.

## 5. Yang harus diketahui operator

- Dengan **REF kanonik 8 Okt 12:00 UTC**, semua perjalanan hari ini terbaca **"sudah tiba"** — itu
  jujur (barang memang tiba 8 hari lalu) dan bukan bug. Supaya juri melihat keadaan hidup
  ("di jalan" + estimasi tiba dalam menit), tekan **"Segarkan ke hari ini"** di panel Demo Control:
  seeder menaruh ulang seluruh offset relatif `now`, sehingga Jakarta/Surabaya kembali berjalan.
- Dua tes KPI yang merah hanya hijau kembali kalau residu keputusan demo dibersihkan (tombol
  "Bersihkan data demo" di panel yang sama) — keputusan pemilik, bukan pekerjaan otomatis.

## 6. F12c — kerapian halaman Pemasok (hari yang sama)

Permintaan pemilik: *"pada halaman pemasok anda gunakan skill ui ux dan anda susun supaya tampilan
nya rapih dan enak di lihat user dan pastikan shape teks harus enak di lihat juga tidak kebesaran
maupun ke kecilan"*.

Semua angka di bawah **diukur di peramban** (akun SPPG Head, lebar viewport **1262 px** — saat itu
`(max-width: 1280px)` aktif) — sebelum dan sesudah — bukan taksiran. Aturan CSS yang ditambahkan
bersifat **top-level** (diperiksa lewat penelusuran kurawal, bukan mata), jadi berlaku di lebar
berapa pun; `.location-table` & `.board-table-wrap` juga top-level. Halaman ini tidak memuat peta;
pekerjaan F12c murni frontend.

### 6.1 Keadaan SEBELUM (cacat yang terukur)

| Objek | Ukuran sebelum | Cacatnya |
|---|---|---|
| Tabel "Daftar pemasok" | **1025 px di dalam wadah 913 px** | wajib digeser ke samping padahal desktop |
| Kolom "Hub" + "Koordinat" | 178 px dari 913 px | dua kolom untuk info yang bisa muat satu baris |
| Pil `.shipping-tag` | **186×63 px (3 baris)** | memuat kalimat penuh → bentuk terbesar di barisnya |
| Pil `.reach-tag` | 13 px / 24 px | standar berbeda dari pil kiriman (tidak ada satu bentuk) |
| Tinggi baris tabel | 74 / 79 px tak rata | tabel terbaca "bergelombang" |
| Kartu "Ringkasan" | **466 px dari 947 px** (392 px tinggi) | grid 2 kolom tanpa tetangga → 7 baris fakta memanjang |

### 6.2 Keadaan SESUDAH (bukti ukur)

| Objek | Ukuran sesudah | Perubahan |
|---|---|---|
| Tabel | **913 px = 913 px** | **0 geser horizontal** |
| Kolom | **7** (dari 9) | "Hub" + "Koordinat" → baris kedua sel Pemasok |
| Pil status/jangkauan | **22 px, selalu satu baris** (112 / 122 / 74 px lebar) | satu standar bentuk, tidak pernah membungkus |
| Tinggi baris | **54 px** untuk 34 dari 35 baris (1 baris 65 px: memang punya 2 pil) | tabel rata |
| Kartu "Ringkasan" | **947×226 px**, fakta jadi kotak **296×38 px** | 7 fakta sebaris, selebar halaman |
| Tinggi tabel | 2386 → **1925 px** | lebih ringkas |
| Tinggi halaman | 3669 → **3046 px** | −623 px |
| Skala teks halaman | **12 / 13 / 14 / 20 px** saja, **tidak ada < 12 px** | h1 20 · judul kartu 14 · sel 13 · meta & pil 12 |

### 6.3 Aturan yang dikunci (jangan diulang salah)

1. **Satu standar bentuk label** dipakai bersama `.reach-tag`, `.shipping-tag`, `.shipping-tag-fail`:
   12 px, `padding: 2px 8px`, `inline-flex`, `white-space: nowrap`, `text-overflow: ellipsis` →
   tinggi **22 px**, setara pil kepala halaman (`.commodity-pill`). Kalimat panjang **tidak** ditulis
   di dalam pil: ia pindah ke atribut `title`.
2. **Angka tidak ditulis dua kali dalam satu baris.** Pil jangkauan cukup menyebut keadaannya
   ("di luar jangkauan") karena km-nya sudah ada di kolom **Jarak** persis di sebelahnya — fungsi
   murni `directoryReachTagLabel` (kalimat penuh ber-km `directoryReachLabel` tetap dipakai sebagai
   `title`).
3. **Info yang bisa sebaris dibiarkan sebaris**: hub + koordinat jadi baris kedua sel Pemasok
   (`supplierMetaLine`) alih-alih dua kolom yang memakan 178 px.
4. **Kartu fakta yang sendirian jangan dipasang di grid 2 kolom** — `.supplier-summary` selebar
   halaman dengan `grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))`.
5. **Kata yang sudah ada di kepala kolom tidak diulang di sel**: `" jalan"` dibuang dari
   `routeCellLabel` (nama kolomnya "Jalur kirim"; asal-usul OSRM tetap di `title`) — pelepasan itu
   memberi kolom **Status** 35 px tambahan sehingga pil status berhenti turun ke baris kedua.
6. `text-wrap: pretty` pada kalimat penjelas halaman (dulu menyisakan satu kata menggantung:
   "…usul eksklusi / **baru**").

### 6.4 Gerbang verifikasi

| Bukti | Hasil |
|---|---|
| TDD RED → GREEN: `tests/supplier-pins.test.ts`, `tests/suppliers-board.test.ts` | `shippingTagLabel`, `supplierMetaLine`, `directoryReachTagLabel` diuji **gagal lebih dulu**, lalu implementasi |
| Markup dikunci: `tests/supplier-board.test.tsx` + `tests/supplier-routes.test.ts` | kolom Hub/Koordinat tidak ada lagi, pil kiriman satu baris (kalimat penuh di `title`), pil gagal uji berkelas sendiri, Ringkasan berkelas `.supplier-summary`; `routeCellLabel` tanpa " jalan" |
| `npx vitest run` | **792 lulus / 69 berkas** (naik dari 774: +18 tes F12c) |
| `npx tsc --noEmit` · `npx next lint` | `TSC_EXIT=0` · `No ESLint warnings or errors` |
| Live `http://localhost:3010/` tab Pemasok | lebar tabel 913 = wadah 913 (**0 geser**), distribusi tinggi baris `{54: 34, 65: 1}`, jarak baris penyaring → kepala tabel 12 px, **0 error JS baru** selama 9 detik pengamatan (40 entri lama = `AbortError` permintaan ubin peta saat peta Overview dilepas) |

Belum ada commit/push untuk F12c.
