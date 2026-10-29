# Rencana redesign halaman Keamanan Pangan (Food Safety)

Status: **selesai 1–7 (30 Okt 2026).** Tahap 7 menutup pekerjaan: gaya dibersihkan
(30 kelas `.safety-*` mati, 3 salinan warna), cincin fokus kontrol drawer
diperbaiki, dan gerbang mutu `tests/safety-css-gate.test.ts` (7 uji) mengunci hasilnya. Halaman: tab **Keamanan Pangan**
(`frontend/components/FoodSafetyBoard.tsx`, 1.978 baris + `FoodSafetyBoard.module.css`
197 baris + 163 kelas `.safety-*` di `app/globals.css`).

## Dasar keputusan desain

Skill `ui-ux-pro-max` dijalankan untuk halaman ini. Hasil yang jujur:

| Query | Hasil | Dipakai? |
|---|---|---|
| `--design-system "food safety operations dashboard clean minimal"` | pola **Hero + Features + CTA**, palet merah `#DC2626` / latar `#FFF1F2` | **Tidak.** Itu pola landing page, dan latar merah untuk layar kerja harian salah |
| `--design-system "internal operations dashboard monitoring table"` | pola **Real-Time Landing** + **Glassmorphism** gelap | **Tidak.** Bertabrakan dengan sistem token proyek |

Jadi arah visual **tidak** diambil dari katalog (tidak ada kecocokan untuk dashboard
operasional di dalam sistem proyek ini). Yang dipakai dari skill adalah **aturan
yang cocok**, dan tokennya tetap dari `docs/design.md` (sumber token kanonik):

- `--space-1..6` (4/8/12/16/24/32), `--fs-1..8` (12–32), `--radius` 16 → 12 (mobile)
- kontras teks ≥ 4.5:1, focus ring eksplisit, `prefers-reduced-motion` dihormati
- rule katalog yang relevan (domain `ux`):
  - **Color Only (High)** — status tidak boleh dibedakan warna saja → teks + ikon
  - **Contextual Live Badge (High)** — angka async diumumkan sebagai frasa utuh (`role="status" aria-atomic`), bukan angka telanjang
  - **Table Handling (Medium)** — tabel lebar wajib `overflow-x` atau berubah jadi kartu
  - **Empty States (Medium)** — keadaan kosong harus memberi pesan + aksi
  - **Confirmation Dialogs (High)** + **Confirmation Messages (Medium)** — aksi tak dapat dibatalkan wajib konfirmasi, sukses tidak boleh senyap

## Kondisi hari ini (yang jadi alasan perubahan)

1. Lima seksi bertumpuk dalam satu gulungan panjang: Ringkasan → Penerimaan barang →
   Menunggu persetujuan → Status per batch → Keputusan keamanan.
2. Kepala "Status keamanan per batch" memuat 4 tombol (2 cakupan, Ekspor CSV, Ekspor JSON)
   → aksi sekunder bersaing dengan aksi utama.
3. Detail batch tampil semua sekaligus; tidak ada jalur "lihat satu batch" (tidak ada
   progressive disclosure).
4. Gaya terbelah dua tempat: 163 kelas `.safety-*` di `globals.css` + 197 baris module CSS.
5. Aksi tulis (penerimaan barang, keputusan) belum punya pola konfirmasi/sukses yang seragam.

Keputusan 29 Okt yang **dipertahankan** (jangan dibalik): tanpa bidang merah selebar kartu,
tanpa lencana "Ada batch gagal" (kalimat putusan sudah menyebutnya), cakupan angka
ditulis eksplisit di kepala kartu.

---

## Tahapan perubahan

### Tahap 1 — Kerangka halaman: 5 seksi → 3 zona

- **Ubah:** bungkus ulang tata letak jadi tiga zona bernama:
  **A. Putusan** (ringkasan) · **B. Tindakan** (penerimaan + menunggu persetujuan) ·
  **C. Daftar & bukti** (batch + keputusan).
- Tambah sub-navigasi jangkar (3 tautan) yang menempel saat digulir, supaya Kepala SPPG
  bisa langsung ke "Tindakan".
- **Alasan:** satu halaman, satu pertanyaan utama ("apakah ada yang harus saya tindak?"),
  sisanya bukti.
- **Selesai bila:** urutan region A→B→C terbaca oleh screen reader, jangkar bekerja dengan
  keyboard, tidak ada seksi yang kehilangan judul.
- **Berkas:** `FoodSafetyBoard.tsx`, `FoodSafetyBoard.module.css`.

### Tahap 2 — Zona A: ringkasan jadi satu strip putusan

- **Ubah:** satu kalimat putusan (sudah ada) + 4 tile metrik: **Aman · Perlu verifikasi ·
  Karantina · Gagal uji**, tiap tile = angka + label + tautan saring ke zona C.
- Pindahkan tombol "Tinjau N batch…" dari kepala kartu ke strip ini sebagai aksi utama
  tunggal (bukan dua CTA).
- Angka memakai `role="status" aria-atomic="true"` dengan frasa utuh,
  mis. "3 batch perlu tindakan".
- **Alasan:** rule Color Only + Live Badge; satu aksi utama per zona.
- **Selesai bila:** setiap status punya teks + ikon (bukan warna saja), jumlah aksi di
  kepala kartu turun jadi 1, dan tile bisa diaktifkan dengan keyboard.

### Tahap 3 — Zona C: tabel batch yang benar-benar tabel

- **Ubah:** daftar kartu → tabel dengan kepala lengket: **Batch · Komoditas · Lokasi ·
  Status · Suhu/Uji · Umur · Aksi**. Baris bisa diklik → **drawer** detail (progressive
  disclosure) alih-alih semua detail terbuka.
- Filter pill → segmented control + kolom pencarian; saringan aktif ditampilkan sebagai
  chip yang bisa dilepas.
- Bungkus dengan `overflow-x: auto`; di ≤720 px berubah jadi kartu bertumpuk.
- Ekspor CSV/JSON pindah ke menu "…" di kepala tabel.
- **Alasan:** Table Handling (Medium) + mengurangi 4 tombol di kepala.
- **Selesai bila:** 375/768/1024/1440 px tidak ada gulir horizontal di tingkat halaman,
  kolom status terbaca tanpa warna, dan detail satu batch terbuka tanpa memuat ulang halaman.

### Tahap 4 — Zona B: penerimaan barang dua langkah — **selesai 30 Okt 2026**

- **Hasil:** tombol utama di langkah 1 berubah jadi **"Lanjut: konfirmasi"**; layar
  konfirmasi (`data-testid="receipt-konfirmasi"`) menampilkan komoditas, batch, berat
  diterima, butir terjawab, dan catatan, dengan dua tombol: "Catat & hitung nilai"
  (menyimpan) dan "Kembali perbaiki" (menutup tanpa menulis). Diuji: klik pertama
  **tidak** memanggil `onRecordReceipt`; klik kedua memanggilnya tepat sekali
  (`tests/receipt-drawer-open.test.tsx`, uji "gerbang konfirmasi").
- **Tidak berubah:** pesan hasil sudah `role="status"`/`role="alert"` sejak awal, galat
  berat & ceklis tampil di dekat field-nya.
- **Ubah:** alur "pilih batch → isi → **konfirmasi**"; ringkasan perubahan ditampilkan
  sebelum menekan tombol akhir (tidak dapat dibatalkan).
- Pesan sukses singkat muncul setelah aksi (bukan senyap), galat tampil di dekat field.
- **Alasan:** Confirmation Dialogs (High) + Confirmation Messages (Medium) + error dekat field.
- **Selesai bila:** aksi tulis tidak bisa terjadi tanpa layar konfirmasi; setiap hasil
  (sukses/gagal) punya pesan yang terbaca screen reader.

### Tahap 5 — Zona B: menunggu persetujuan diringkas

- **Ubah:** kartu approval jadi satu baris ringkas: **komoditas · jumlah · alasan ·
  2 tombol**, dengan tautan ke Decision & Evidence untuk detail.
- Keadaan kosong: "Tidak ada yang menunggu persetujuan" + tautan ke daftar batch aman.
- **Alasan:** Empty States + menghindari duplikasi detail yang sudah ada di tab lain.
- **Selesai bila:** tidak ada informasi yang hilang dari kartu lama (dicek per field) dan
  keadaan kosong punya aksi.

### Tahap 6 — Zona C: keputusan keamanan lokasi — **selesai 30 Okt 2026**

- **Hasil:** daftar `<ul class="board-list">` → tabel dengan pola kepala yang sama
  seperti tabel batch (`.board-table-wrap` + `table.location-table.safety-table`,
  `th scope="col"`, `data-label` per sel). Kolom: Dibuat · Komoditas · Jumlah · Status ·
  Masa berlaku · Aksi. Saringan komoditas pill → `<select>` berlabel (opsi tetap
  dibangun dari data, jadi tidak ada pilihan karangan).
- **Uji:** `tests/safety-keputusan-tabel.test.tsx` (5 uji) mengunci opsi select,
  daftar kepala kolom, 12 sel ber-`data-label`, komoditas/kg di kolomnya sendiri, dan
  masa berlaku ("2 jam lagi" / "lewat"). Uji lama yang menuntut teks baris daftar
  ("Gangguan keamanan") diganti ke kontrak tabel.
- **Ubah:** daftar keputusan → tabel ringkas (waktu · komoditas · status · tautan bukti),
  filter komoditas pill → `select`.
- **Alasan:** konsistensi dengan tabel batch; pill filter dengan >5 pilihan menyulitkan
  pemindaian.
- **Selesai bila:** kedua tabel di zona C memakai pola kepala/kolom yang sama.

### Tahap 7 — Konsolidasi gaya + gerbang mutu — **selesai 30 Okt 2026**

- **Hasil:** 30 kelas `.safety-*` yang tidak pernah dipakai kode dihapus (15 di
  antaranya bersembunyi di dalam `@media` dan luput dari sapuan pertama). Kelas
  unik turun: `globals.css` 23 → 15, `theme-ext.css` 26 → 21. Warna
  `.safety-state-expired/-urgent/-watch` yang ditulis dua kali (globals **dan**
  theme-ext; theme-ext menang diam-diam karena diimpor belakangan) kini hanya di
  theme-ext. Kelas `safety-counts-total` di JSX ternyata tidak punya aturan CSS
  sama sekali → atribut kelasnya dilepas.
- **Aksesibilitas:** cincin fokus eksplisit untuk kontrol drawer penerimaan
  (kotak berat, tombol opsi, tombol aksi). Tombol opsi adalah `<label>` yang
  membungkus radio, jadi `.option:focus-visible` tidak pernah cocok — dipakai
  `.option:has(input:focus-visible)`, pola yang sama dengan `.batchItem`.
- **Gerbang:** `tests/safety-css-gate.test.ts` (7 uji) menolak kelas `.safety-*`
  yatim, kelas JSX tanpa definisi, `safety-state-*` ganda, kontrol tanpa cincin
  fokus, `transition`/`animation` tanpa `prefers-reduced-motion`, kontras di bawah
  4,5:1, dan `font-size` di bawah 12 px.
- **Kontras terukur:** `--ink-subtle` 5,43:1 · `--ink-muted` 7,58:1 · `--ink`
  17,85:1 · `--accent-strong` 5,17:1 · lencana sedang/berat/kritis 5,72 / 6,88 /
  7,60:1 — semua di atas 4,5:1. `--fs-1` = 12 px; tidak ada teks lebih kecil.
- **Bukti runtime:** `.safety-figure-value`, `.safety-marker-dot`,
  `.safety-pick-row` = 0 kemunculan di `layout.css` yang dilayani; `.safety-band`
  85, `.safety-verdict` 6. Halaman `/` 200, `✓ Compiled`.

#### Rencana awal tahap ini (dipertahankan sebagai catatan)

- Pindahkan 163 kelas `.safety-*` dari `app/globals.css` ke `FoodSafetyBoard.module.css`
  (bertahap per seksi, bukan sekaligus), sisakan hanya token di globals.
- Audit: kontras 4.5:1 (terutama teks status di atas tint), focus-visible pada pill/baris
  tabel/drawer, `prefers-reduced-motion`, tanpa hex mentah (sekarang 0 di modul — jaga).
- Gerbang: `npm run test`, `npm run typecheck`, `npm run lint`, plus render test baru untuk
  tiap zona (A/B/C) dan tes aksesibilitas status-bukan-warna.
- **Selesai bila:** ketiga gerbang hijau, jumlah kelas `.safety-*` di `globals.css` = 0,
  dan tidak ada penurunan jumlah tes.

---

## Urutan kerja yang disarankan

| Urutan | Tahap | Alasan urutan |
|---|---|---|
| 1 | Tahap 1 | kerangka dulu; semua tahap lain menempel ke zona |
| 2 | Tahap 2 | nilai tertinggi per usaha: pertanyaan "ada yang harus ditindak?" |
| 3 | Tahap 3 | bagian terbesar dan paling sering dipakai |
| 4 | Tahap 7 (sebagian) | rapikan gaya seksi yang sudah disentuh, sebelum lanjut |
| 5 | Tahap 5 | kecil, cepat, mengurangi duplikasi |
| 6 | Tahap 4 | menyentuh jalur tulis → butuh tes sendiri |
| 7 | Tahap 6 | paling belakang karena paling jarang dibuka |
| 8 | Tahap 7 (sisa) | konsolidasi akhir + gerbang penuh |

Setiap tahap berhenti untuk diperiksa: laporan singkat + gerbang hijau, baru lanjut.
