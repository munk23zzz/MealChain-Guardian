# Rencana redesign halaman **Suppliers** — MealChain Guardian

Tanggal: 29 Okt 2026 · Dasar: skill `ui-ux-pro-max` (kueri di bawah) + keadaan kode saat ini.
Status: **rencana saja — belum ada berkas yang diubah**.

## 1. Keadaan halaman sekarang (hasil pembacaan kode)

`app/page.tsx:2318` merender `SupplierBoard`. Isi halaman, atas → bawah:

| # | Bagian | Komponen | Baris | Catatan keadaan |
|---|--------|-----------|-------|-----------------|
| A | Kepala halaman: judul `Suppliers`, deskripsi 2 baris ("Daftar pemasok di jaringan, kepercayaan, jangkauan jarak ke SPPG Anda, register eksklusi, dan usul eksklusi baru."), 2 pil (`N pemasok`, `N eksklusi`), 3 jump-link | `BoardPage` di `SupplierBoard.tsx:159–172` | 554 (total) | Deskripsi mendaftar ulang isi halaman yang sudah dinyatakan jump-link |
| B | **Ringkasan** — strip KPI read-only (tanpa tombol) | `SupplierSummary.tsx` | 42 | Satu baris angka; label pendek; belum ada angka yang dipromosikan |
| C | **Papan kiriman** — satu baris per kiriman, kolom `Pemasok · Tujuan · Muatan · Jalur · Berangkat · ETA · Sisa · Masa layak · Mutu · Keadaan` | `ShipmentBoard` (dipanggil `SupplierBoard.tsx:206`) | — | Catatan kaki satu kalimat teknis; belum ada kartu-mobile |
| D | **Daftar pemasok** — tiga lapis kontrol terpisah: (1) baris penyaring jangkauan, (2) baris ringkasan + kolom cari, (3) pil jumlah di kepala kartu. Tabel 7 kolom: `Pemasok · Komoditas · Keandalan · Sertifikasi · Jarak · Status · Jalur kirim` + pager + scroll hint | `SupplierBoard.tsx:211–469`, data `lib/suppliers-board.ts` (346), `lib/supplier-search.ts` (50) | 259 | Kontrol tersebar di 3 baris; "Jalur kirim" meringkas hal yang sudah ada di Papan kiriman |
| E | **Riwayat penerimaan** | `SupplierReceipts.tsx` | 185 | Berdiri sendiri tanpa pil jumlah |
| F | **Register eksklusi** + **Usul eksklusi** (form) | `SupplierExclusionPanel.tsx` | 152 | Dua register dibaca berurutan; form jadi ekor panjang di bawah |

Tes yang menyentuh halaman ini: 17 berkas (`supplier-board`, `supplier-summary-ui`, `suppliers-board`, `supplier-receipts-ui`, `supplier-exclusion-panel`, `supplier-governance-ui`, `supplier-search-ui`, `supply-map-suppliers`, …).

## 2. Dasar desain dari skill (bukti kueri, bukan selera)

```
search.py "enterprise procurement vendor management analytics dashboard" \
  --design-system --density 8 --variance 3 --motion 3
```
- **Style: Minimalism & Swiss** — cocok: "Enterprise apps, dashboards, professional tools"; risiko aksesibilitas `low`, wajib kontras 4.5:1, keyboard, focus terlihat, reduced-motion.
- **Density 8/10 (dense dashboard)**, **Variance 3 (centered/minimal)**, **Motion 3 (subtle)** → jarak 8–32 px, transisi 200–250 ms, tanpa koreografi.
- Palet yang dikembalikan generator (#1E40AF / #D97706 / Playfair Display SC) **tidak dipakai**: repo punya token sendiri di `docs/design.md` (hijau operasional / merah insiden / amber pemeliharaan, Fira Sans + Fira Code). Token repo menang.
- **Pola halaman: tidak ada padanan.** Percobaan pertama mengembalikan `Funnel (3-Step Conversion)`, percobaan kedua `Enterprise Gateway` — keduanya pola *landing page*, bukan halaman operasi. Sesuai aturan skill: tidak ada match katalog, jadi susunan halaman memakai aturan prioritas umum (1 aksesibilitas, 2 sentuh, 5 layout, 6 tipografi, 10 chart/data), bukan pola karangan.

Kueri UX yang dipakai:
| Kueri | Hasil | Dipakai untuk |
|-------|-------|---------------|
| `dense data table scanning rows` | *Table Handling* — "Tables can overflow on mobile → horizontal scroll atau card layout" (Medium) | S3, S4 (kartu-mobile) |
| `empty state no results guidance` | *Empty States* — "Show helpful message and action", bukan layar kosong (Medium) | S4, S5 |
| `status badge not color alone` | *Color Only* — "Use icons/text in addition to color" (**High**) | S2, S4 (pil status selalu berteks) |
| `sortable column affordance` | 1 hasil lemah (*Input Affordance*) | **Tidak dipakai** — tidak ada match; urutan tabel tetap urutan tetap seperti sekarang |

## 3. Tahapan perubahan (urut, tiap tahap berdiri sendiri & bisa diverifikasi)

### S0 — Kunci kontrak teks halaman Suppliers (fondasi, tanpa perubahan visual) — **SELESAI 29 Okt 2026**
- Tambah tes `tests/suppliers-teks-kontrak.test.tsx` (6 tes): markup halaman Suppliers tidak boleh memuat `backend`, `server`, `database`, `payload`, `schema`, `endpoint`, `historical_seed` — diperiksa pada lima keadaan (normal, belum dimuat, kosong, galat muat, register terisi) plus form usul eksklusi.
- Tujuan: janji "tidak ada kode backend di layar" ikut dijaga di halaman ini, bukan hanya Food Safety.
- Dua pelanggaran nyata ditemukan tes & diperbaiki: kartu galat ("dari server aplikasi … periksa koneksi ke backend") dan keterangan ID di form pemulihan eksklusi ("server memvalidasi relasinya").
- Temuan untuk S5 (bukan jargon mesin, jadi tidak diubah di S0): panel usul eksklusi masih mencampur bahasa — "Supplier governance", "Alasan exclusion", "Ajukan exclusion", "Tidak ada auto execute".
- Bukti: tes merah dulu (2 gagal), lalu hijau; `tsc` bersih.

### S1 — Kepala halaman & navigasi bagian — **SELESAI 29 Okt 2026**
- Deskripsi 2 baris → **satu kalimat konteks** yang menyebut cakupan SPPG + jangkauan km: "Pemasok jaringan SPPG Anda — ringkasan, kiriman aktif, daftar dalam jangkauan 120 km, dan register eksklusi." (tanpa `reachKm`: versi pendek tanpa angka).
- 2 pil → **3 pil**: `N pemasok` · `N kiriman` · `N eksklusi`. Pil kiriman dihitung dari payload jalur yang sama dengan papan kiriman, dan **tidak dirender** saat jalur belum dimuat (bukan "0 kiriman").
- Jump-link 3 → **5**: Ringkasan · Kiriman · Daftar pemasok · Register eksklusi · Usul eksklusi (`SUPPLIER_SECTION_IDS` + `supplierSections()`), masing-masing jangkar benar-benar dipasang (`id="supplier-ringkasan"`, `id="supplier-kiriman"`).
- Kartu galat sudah bersih dari "backend/server" (dikerjakan di S0).
- Berkas: `components/SupplierBoard.tsx`, `lib/section-jump.ts`, tes baru `tests/suppliers-kepala-halaman.test.tsx` (7 tes), `tests/navigation-shell.test.ts` disesuaikan ke lima jangkar.
- Bukti: 46 tes terkait lulus; suite penuh 258 berkas / 2.778 lulus / 2 dilewati; `tsc` bersih.
- Temuan samping yang ikut diperbaiki: `FoodSafetyBoard.module.css` memakai `border-radius: 8px` mentah (dari alur kerja lain, melanggar kontrak skala radius) → `var(--radius-control-sm)`.

### S2 — Ringkasan jadi strip 4 angka yang terbaca sekali lihat — **SELESAI 29 Okt 2026**
- Strip kini **selalu empat angka**, satu di antaranya dipromosikan (`data-lead="true"`): (1) pemasok **dalam jangkauan** — atau pemasok terdaftar bila peran tanpa ambang jangkauan — lalu (2) rata-rata keandalan, (3) keandalan di bawah 60%, (4) tanpa stok layak hari ini.
- Dua kolom lama dilepas karena angkanya sudah ada di tempat lain dan membuat satu angka tampil dua kali: jumlah pemasok (kini pil kepala halaman, S1) dan "di luar jangkauan" (kini kalimat di baris penyaring jangkauan, tepat di atas tabel). Tidak ada informasi yang hilang — hanya tidak diulang.
- Angka yang dipromosikan memakai token hero `--fs-8` + kolom lebih lebar; di ≤720 px ia mengambil satu baris penuh dan tiga angka lain berbagi baris di bawahnya. Tetap **read-only** (tanpa tombol/tautan).
- Berkas: `lib/supplier-summary.ts`, `components/SupplierSummary.tsx`, `app/supplier-summary.css`, tes `supplier-summary.test.ts` (unit), `supplier-summary-ui.test.tsx`, `supplier-summary-css.test.ts` (2 kontrak baru: token hero & baris penuh di mobile), `supplier-board.test.tsx` disesuaikan.
- Bukti: 129 tes di lingkup Suppliers + navigasi + skala radius lulus; `tsc` untuk berkas yang saya sentuh bersih.

### S3 — Papan kiriman: tabel yang dipindai, bukan dinding angka — **SELESAI 29 Okt 2026 (satu butir dilepas, alasannya di bawah)**
- Kepala kartu: judul + jumlah (`boardCounts`, teks yang sama dengan papan) + **tautan "Ke daftar pemasok"** (prop `tautan`, hanya dirender bila diminta; `SupplierBoard` mengirim `#supplier-daftar`).
- Tanpa kiriman, kartu kini **tetap dirender** dengan pesan "Belum ada kiriman aktif di jaringan." — sebelumnya `ShipmentBoard` mengembalikan `null`, sehingga jangkar `#supplier-kiriman` menunjuk ruang kosong.
- Tooltip jalur tidak lagi menjelaskan mekanisme ("dihitung OSRM saat sinkronisasi rute, bukan saat papan ini dibuka") → "dihitung dari jalur jalan yang tersimpan untuk kiriman ini". Label sumber `OSRM` tetap (provenance, sama seperti legenda peta).
- **< 760 px: tiap kiriman menjadi kartu berlabel** (`data-label` per sel, judul kartu = nama pemasok), pola yang sama dengan `.safety-table`; `thead` disembunyikan. Ini yang menghapus keharusan menggeser tabel ke samping untuk melihat kolom "Keadaan".
- Dua butir rencana awal dilepas setelah diperiksa, bukan karena lupa:
  - `table-layout: fixed` — sel bertipe `nowrap`; layout tetap akan memotong isi sel, bukan merapatkannya.
  - header lengket — `.board-table-wrap` adalah wadah gulir mendatar, jadi `th` sticky akan menempel pada kotak itu (yang tidak pernah menggulir tegak) dan tidak akan menempel di layar.
- Berkas: `components/ShipmentBoard.tsx`, `components/SupplierBoard.tsx`, `app/globals.css` (`.shipment-head*` + blok `@media (max-width: 760px)`), tes `shipment-board-component.test.tsx` (+3 kontrak), tes baru `shipment-board-mobile-css.test.ts` (4 kontrak).
- Bukti: 82 tes di lingkup Suppliers + papan kiriman + skala radius + token desain lulus.

### S4 — Daftar pemasok: satu bilah kontrol, satu tabel — **SELESAI 29 Okt 2026 (satu butir dilepas)**
- ~~Tiga lapis kontrol~~ → **satu bilah** `.directory-toolbar`: `[cari] [N pemasok / x dari N cocok] [Hanya dalam jangkauan (N)]`, ditutup satu kalimat keadaan `.directory-toolbar-note`. Pil jumlah **dipindah** ke bilah; salinan lamanya di kepala kartu dihapus (menghasilkan `id` kembar dan angka yang sama dua kali).
- Tabel: `Pemasok · Komoditas · Keandalan · Jarak · Sertifikasi · Status` — kolom **Jalur kirim dilepas**. Fakta jalur tetap terbaca per kiriman di papan S3 (`>Jalur</th>`, `110,4 km jalan`): pindah, bukan hilang. Impor `routeCellLabel/routeCellTitle/supplierRouteSummaries` dan variabel `jalurDimuat/jalurPerPemasok` ikut dilepas.
- Status tetap **teks + bentuk**: `Aktif`, `Dikecualikan di …`, pil `shipping-tag` / `N gagal uji` — tidak pernah warna saja.
- Empty state dua cabang (hasil pencarian kosong / jangkauan kosong) sudah punya aksi; dipertahankan apa adanya.
- `< 760 px`: kartu per pemasok (`.directory-table` + `data-label`, sel pertama jadi judul kartu) — satu-satunya penghapus geseran mendatar.
- **Dilepas: `table-layout: fixed` dan header lengket.** Sel bertipe `nowrap`, jadi layout tetap memotong isi sel, bukan merapatkannya; dan `.board-table-wrap` adalah wadah gulir mendatar sehingga `th` sticky menempel pada kotak itu yang tidak pernah menggulir tegak. Alasan yang sama dengan S3.
- Berkas: `SupplierBoard.tsx`, `app/globals.css` (`.directory-toolbar`, `.directory-reach-toggle`, `.directory-toolbar-note`, blok `@media 760/720`), `tests/supplier-board.test.tsx` (3 tes kolom jalur ditulis ulang + 5 tes bilah), `tests/supplier-directory-mobile-css.test.ts` (8 tes baru). `.board-summary-row` dihapus dari CSS (tidak dipakai lagi).

### S5 — Registri: penerimaan & eksklusi jadi satu keluarga — **SELESAI 29 Okt 2026**
- `Register eksklusi` kini berkepala sama dengan `Riwayat penerimaan`: judul + pil `N catatan` + satu kalimat keadaan (`.register-note`). Pil tidak dirender saat register kosong — angka 0 bukan informasi.
- `Register eksklusi` (baca) dan `Usul eksklusi` (tulis) dibungkus `.register-grid`: satu kolom di bawah 1200 px, dua kolom `minmax(0, 1.45fr) / minmax(0, 1fr)` mulai 1200 px — form usul tidak lagi jadi ekor halaman.
- Empty state register: kalimat + aksi `<a href="#supplier-usul">Ajukan eksklusi</a>`.
- Campuran bahasa di panel usul dibereskan: `Supplier governance` → `Tata kelola pemasok`; `Supplier exclusion` → `Usulan eksklusi pemasok`; `Alasan exclusion` → `Alasan eksklusi`; `Ajukan exclusion` → `Ajukan eksklusi`; `Bukti exclusion` → `Bukti eksklusi`; `Scope:` → `Lingkup:`; `Supplier:` → `Kode pemasok:`; `Tidak ada auto execute` → `Usulan hanya masuk antrean persetujuan — tidak ada yang dijalankan otomatis`; status mentah `Exclusion active` → `Eksklusi aktif` lewat `exclusionStatusLabel()` bersama.
- Berkas: `SupplierBoard.tsx`, `SupplierExclusionPanel.tsx`, `app/globals.css` (`.register-grid`, `.register-note`), tes baru `tests/suppliers-registri-sejajar.test.tsx` (8 tes), tes lama `supplier-exclusion-panel.test.tsx` / `supplier-board.test.tsx` / `suppliers-teks-kontrak.test.tsx` disesuaikan kosakatanya.

### S6 — Responsif, aksesibilitas, gerak — **SELESAI 29 Okt 2026**
- Target sentuh: `.button`, `.directory-reach-toggle`, `.board-search-clear` (26×26 → 44×44, padding kanan masukan 32 → 46 px supaya teks tidak tertutup), `.pager-btn` (sudah ada), `.receipt-chip` (sudah ada).
- Cincin fokus dikunci untuk `.directory-reach-toggle`, `.board-search-clear`, `.pager-btn`, `.button`, `.receipt-chip`.
- `prefers-reduced-motion`: `.button`, `.directory-reach-toggle`, `.board-search-clear`, `.count-pill`, `.summary-kpi`, `.pager-btn`, `.receipt-chip` berhenti bertransisi.
- Tabel `Riwayat penerimaan` **tidak lagi** dipaksa `min-width: 600px`; di ≤760 px ia jadi kartu berlabel seperti daftar pemasok & papan kiriman (5 `data-label` baru). Ini yang menghapus geseran mendatar di 360 px.
- `tests/design-tokens-kontrak.test.ts` diperluas: `supplier-summary.css` + `supplier-receipts.css` masuk daftar berkas yang diaudit (token hantu, palet hex, font-family literal, lantai 12 px), plus tes baru "font-size di `.summary-*`/`.directory-*`/`.register-*`/`.receipt-*` hanya dari `var(--fs-*)`".
- Tes baru `tests/suppliers-akses-responsif.test.ts` (12 tes): 44 px, padding masukan, cincin fokus, reduced-motion, kartu ≤760 px untuk tiga tabel, larangan `min-width` 600/700 px, grid 1200 px, bilah 720 px, strip ringkasan 360 px.
- Berkas: `app/globals.css`, `app/supplier-receipts.css`, `components/SupplierReceipts.tsx`, dua berkas tes di atas, `tests/supplier-receipts-css.test.ts` (tes `min-width: 600px` diganti kontrak kartu).

### S7 — Verifikasi penutup — **SELESAI 29 Okt 2026** (laporan: `_qa/verifikasi-suppliers-2026-10-29.md`)
- `npx tsc --noEmit` bersih; `vitest` penuh hijau; pratinjau statis per bagian (`_qa/pratinjau-suppliers-*.html`) untuk diperiksa mata sebelum demo.

## 4. Yang **tidak** diubah
- Kontrak data & endpoint (`/suppliers`, `/supplier-exclusions`, `/receipts`, `/routes`) — nol perubahan backend.
- Token warna/typografi `docs/design.md`; bahasa isi tetap Indonesia (hanya sidebar yang Inggris).
- Urutan tabel tetap (tidak ada sortir) sampai ada bukti kebutuhan; skill tidak punya padanan "sortable column".

## 5. Urutan kerja yang diusulkan
`S0+S1` → `S2` → `S4` → `S3` → `S5` → `S6` → `S7`.
Alasan urutan: S1 menstabilkan kepala halaman & jangkar (semua tahap lain menambah jangkar), S2 kecil dan mandiri, S4 adalah inti "dashboard enak dilihat", S3 menyusul karena `ShipmentBoard` dipakai juga di halaman lain (perubahan menyentuh dua tab).
