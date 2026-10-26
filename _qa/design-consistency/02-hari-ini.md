# Audit desain — Hari Ini

> **Snapshot 22 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tugas halaman:** Ringkasan status harian: 5 tile status, agenda, batch kedaluwarsa, KPI 24 jam, rantai audit.
**Peran yang diukur:** SPPG Operations Lead (`sppg.head@demo.local`) · viewport 1280×~620 · snapshot 22 Okt 2026 15.5x WIB
**Vonis:** konsisten setelah perbaikan; tidak ada token hantu, tidak ada teks di bawah 12 px, satu bahasa gerak.

## Metrik runtime (computed style, bukan sumber)

| metrik | sebelum | sesudah |
|---|---|---|
| ukuran teks unik | 6 | 5 |
| radius unik | 5 | 5 |
| keluarga huruf | 3 | 2 |
| nama animasi aktif | 1 | 2 |

## Temuan & perbaikan

Arial 13,3333 px pada kontrol hilang (96→0 elemen). Gerak masuk: `today-tile-in` + reveal panel.

## Yang diuji dan bersih

Angka tile sengaja 16 px (keputusan pemilik 17 Okt: 18 px terbaca seperti judul) — TIDAK diubah; dicatat sebagai keputusan, bukan cacat.

## Cakupan yang belum diuji

- Peran lain (Nutritionist, BGN Monitor, Kepala/Gizi Bandung & Surabaya) dan tab role-gated `Pengaturan`.
- Keadaan `loading`, `empty`, dan `error API` pada halaman ini (yang terukur adalah keadaan berisi).
- Viewport 375 px / 768 px.
