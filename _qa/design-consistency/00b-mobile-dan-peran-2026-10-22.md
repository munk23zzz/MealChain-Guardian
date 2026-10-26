# Audit 375 px + peran BGN Monitor & Nutritionist — 22 Okt 2026

> **Snapshot 22 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Lanjutan `00-ringkasan-2026-10-22.md` (yang mencakup peran SPPG Head di 1280 px).
Metode sama: sweep computed style di DOM hidup. Untuk 375 px aplikasi dimuat di iframe
same-origin 375×812 (media query ikut lebar iframe); tiap tab diukur setelah data siap,
dengan reload di antara kelompok agar hot-reload dev tidak mencemari snapshot.

## 1. Peran BGN Monitor (9 tab, 1262 px)

Tab: Hari Ini · Overview · Recommendations (5) · Decision & Evidence · Keamanan Pangan ·
Pemasok · Agent Log · KPI & Kualitas Agen · **Pengaturan** (baru, role-gated).
Tidak ada Surplus & Limbah / Demo Control — benar, keduanya bukan wewenang BGN.

| Metrik | Hasil |
|---|---|
| keluarga huruf | 2 per tab (Overview 3 — `Helvetica Neue` dari kanvas MapLibre) |
| skala teks | ⊆ {12, 13, 14, 16, 18, 20, 24, 32} px, 0 elemen < 12 px |
| radius | 3–8 nilai unik, semuanya token |
| animasi | `page-reveal` di 9 tab; Overview menambah `overview-pulse`, `map-layer-hint-in`, `sa-grow` |
| luapan horizontal | tidak ada (`scrollWidth − innerWidth` < 0) |

## 2. Peran Nutritionist (10 tab, 1262 px)

Tab: Hari Ini · Overview · Recommendations (11) · Decision & Evidence · Keamanan Pangan ·
**Surplus & Limbah** · Pemasok · Agent Log · KPI & Kualitas Agen · **Demo Control**.
Tidak ada Pengaturan. Hasil identik: 2 keluarga huruf per tab, skala teks 12–32 px tanpa
pelanggaran, 0 teks < 12 px, tanpa luapan.

Catatan cakupan: `Recommendations` memuat angka berbeda per peran (5 untuk BGN, 11 untuk
Nutritionist, 24 saat dibuka lewat iframe dengan peran BGN) — ini data, bukan cacat desain.

## 3. Temuan 375 px: pager meluap 9 px (Pemasok)

**Gejala terukur.** Pada lebar viewport 360 px, `Pemasok`: `documentElement.scrollWidth`
369 vs 360 → **luapan 9 px**; `.board-page` 347 di dalam kotak 316; `.pager-controls` 301
di dalam `.pager` 286.

**Sebab.** Nomor halaman dirender sebagai satu baris flex yang tidak boleh menyusut. Pada
`@media (pointer: coarse), (max-width: 720px)` tombol pager naik ke 44 px (batas sentuh),
sehingga enam nomor + rentang + dua tombol langkah = 301 px di ruang 286 px.

**Perbaikan.** `@media (max-width: 720px) { .pager-list { display: none } }` — nomor halaman
disembunyikan di layar sempit; posisi tetap terbaca dari rentang "1–10 dari 105" dan tombol
Sebelumnya/Berikutnya. Ditambah `min-width: 0` pada `.pager-controls` agar flex boleh menyusut.

**Bukti sesudah (diukur ulang):**

| | sebelum | sesudah |
|---|---|---|
| luapan halaman (Pemasok, 360 px) | +9 px | **0 px** |
| `.board-page` scrollWidth vs clientWidth | 347 / 316 | **316 / 316** |
| tinggi pager | — (meluap) | **44 px**, satu baris |
| pager scrollWidth vs clientWidth | 301 / 286 | **286 / 286** |
| tombol angka tampil | 6 | 0 (`display: none`) |
| tombol langkah | 44 px | 44 px |

Desktop tidak berubah (1262 px): pager 32 px, nomor 1·2·3·4·5·11 tetap tampil,
`luapan −15` (lebar scrollbar).

Percobaan pertama (membiarkan nomor membungkus) ditolak: pager jadi **214 px** tinggi —
enam baris tombol. Karena itu nomor disembunyikan, bukan dibungkus.

## 4. Hasil sapuan 9 tab BGN Monitor pada 375 px (sesudah perbaikan)

| Tab | luapan | skala teks | < 12 px | sentuh < 44 px | pager |
|---|---|---|---|---|---|
| Hari Ini | 0 | 12·14·15·17·20 | 0 | 0 | — |
| Overview | 0 | 12·14·15·17·18·20·24·32 | 0 | 0 | — |
| Recommendations | 0 | 12·14·15·17·20 | 0 | 0 | 44 px |
| Decision & Evidence | 0 | 12·14·15·20 | 0 | 0 | — |
| Keamanan Pangan | 0 | 12·14·15·20 | 0 | 0 | 44 px |
| Pemasok | 0 | 12·14·15·17·20 | 0 | 0 | 44 px |
| Agent Log | 0 | 12·14·15·17·20 | 0 | 0 | — |
| KPI & Kualitas Agen | 0 | 12·14·15·17·18·20·24 | 0 | 0 | — |
| Pengaturan | 0 | 12·14·15·17·20 | 0 | 0 | — |

Skala mobile memakai 14/15/17 px (bukan 12/13/14/16 desktop) sesuai `docs/design.md`
§Tipografi; lantai 12 px tidak dilanggar.

Elemen yang melewati tepi kanan tapi **bukan cacat**: `.section-jump-list` (rail chip
"Ringkasan · Jalur persetujuan · Keputusan · Bukti · Jejak & integritas") — induknya
`overflow-x: auto`, jadi digulir mendatar, dan luapan halaman tetap 0. Sama untuk
`.board-table-wrap` (tabel lebar) dan `.side-nav` (drawer off-canvas).

## 5. Yang belum diuji

- Peran **Kepala Bandung / Gizi Bandung / Kepala Surabaya / Gizi Surabaya** (4 akun) —
  tab-nya kemungkinan sama dengan Nutritionist/SPPG Head namun belum diukur.
- Keadaan `loading`, `empty`, `error API` per halaman.
- `(pointer: coarse)` sungguhan (perangkat sentuh): iframe mewarisi pointer halus, jadi
  aturan 44 px diverifikasi lewat `(max-width: 720px)` — jalur yang sama, tetapi bukan
  pembuktian perangkat.
