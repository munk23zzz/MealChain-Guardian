# Audit desain — Overview

> **Snapshot 22 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tugas halaman:** Peta 10 lokasi + antrean keputusan + kecukupan + telemetri.
**Peran yang diukur:** SPPG Operations Lead (`sppg.head@demo.local`) · viewport 1280×~620 · snapshot 22 Okt 2026 15.5x WIB
**Vonis:** konsisten setelah perbaikan; tidak ada token hantu, tidak ada teks di bawah 12 px, satu bahasa gerak.

## Metrik runtime (computed style, bukan sumber)

| metrik | sebelum | sesudah |
|---|---|---|
| ukuran teks unik | 10 | 9 |
| radius unik | 8 | 8 |
| keluarga huruf | 4 | 3 |
| nama animasi aktif | 2 | 3 |

## Temuan & perbaikan

Font pihak ketiga `Helvetica Neue` (kanvas MapLibre) tetap ada sebagai pengecualian sah. Popup peta: tinggi 402 px pada kanvas 400 px → dibatasi `max-height: 340px` + `overflow-y:auto` (terukur setelah: 350 px, celah atas 38 px / bawah 12 px, 0 teks terpotong horizontal).

## Yang diuji dan bersih

Legenda ↔ kanvas peta sudah disamakan pada audit peta 22 Okt (nada `tiba`, `sisa`).

## Cakupan yang belum diuji

- Peran lain (Nutritionist, BGN Monitor, Kepala/Gizi Bandung & Surabaya) dan tab role-gated `Pengaturan`.
- Keadaan `loading`, `empty`, dan `error API` pada halaman ini (yang terukur adalah keadaan berisi).
- Viewport 375 px / 768 px.
