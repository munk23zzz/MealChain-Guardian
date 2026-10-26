# Audit desain — KPI & Kualitas Agen

> **Snapshot 22 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tugas halaman:** KPI 24 jam, kualitas agen, verdict segmen.
**Peran yang diukur:** SPPG Operations Lead (`sppg.head@demo.local`) · viewport 1280×~620 · snapshot 22 Okt 2026 15.5x WIB
**Vonis:** konsisten setelah perbaikan; tidak ada token hantu, tidak ada teks di bawah 12 px, satu bahasa gerak.

## Metrik runtime (computed style, bukan sumber)

| metrik | sebelum | sesudah |
|---|---|---|
| ukuran teks unik | 8 | 7 |
| radius unik | 5 | 5 |
| keluarga huruf | 3 | 2 |
| nama animasi aktif | 0 | 1 |

## Temuan & perbaikan

Delapan ukuran teks → tujuh (13,3333 px bawaan hilang). Skala 12–32 px seluruhnya dari token.

## Yang diuji dan bersih

Tidak ada temuan khusus.

## Cakupan yang belum diuji

- Peran lain (Nutritionist, BGN Monitor, Kepala/Gizi Bandung & Surabaya) dan tab role-gated `Pengaturan`.
- Keadaan `loading`, `empty`, dan `error API` pada halaman ini (yang terukur adalah keadaan berisi).
- Viewport 375 px / 768 px.
