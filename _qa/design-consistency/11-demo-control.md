# Audit desain — Demo Control

> **Snapshot 22 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tugas halaman:** Kontrol demo: sesi, skenario, parameter, data & rentang waktu.
**Peran yang diukur:** SPPG Operations Lead (`sppg.head@demo.local`) · viewport 1280×~620 · snapshot 22 Okt 2026 15.5x WIB
**Vonis:** konsisten setelah perbaikan; tidak ada token hantu, tidak ada teks di bawah 12 px, satu bahasa gerak.

## Metrik runtime (computed style, bukan sumber)

| metrik | sebelum | sesudah |
|---|---|---|
| ukuran teks unik | 5 | 4 |
| radius unik | 5 | 5 |
| keluarga huruf | 3 | 2 |
| nama animasi aktif | 0 | 1 |

## Temuan & perbaikan

`select.dc-select` tampil **Arial 13,3333 px + teks hitam murni** (satu-satunya hitam di aplikasi) → kini `Fira Sans` 14 px, `color: var(--ink)`.

## Yang diuji dan bersih

`--surface-2` (token tidak pernah dideklarasikan) → alias `--surface-sunken`, panel bersarang dapat lapisannya kembali.

## Cakupan yang belum diuji

- Peran lain (Nutritionist, BGN Monitor, Kepala/Gizi Bandung & Surabaya) dan tab role-gated `Pengaturan`.
- Keadaan `loading`, `empty`, dan `error API` pada halaman ini (yang terukur adalah keadaan berisi).
- Viewport 375 px / 768 px.
