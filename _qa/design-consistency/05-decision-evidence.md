# Audit desain — Decision & Evidence

> **Snapshot 22 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tugas halaman:** Rantai keputusan, bukti, dossier, action bar.
**Peran yang diukur:** SPPG Operations Lead (`sppg.head@demo.local`) · viewport 1280×~620 · snapshot 22 Okt 2026 15.5x WIB
**Vonis:** konsisten setelah perbaikan; tidak ada token hantu, tidak ada teks di bawah 12 px, satu bahasa gerak.

## Metrik runtime (computed style, bukan sumber)

| metrik | sebelum | sesudah |
|---|---|---|
| ukuran teks unik | 6 | 5 |
| radius unik | 7 | 7 |
| keluarga huruf | 3 | 2 |
| nama animasi aktif | 1 | 2 |

## Temuan & perbaikan

`.integrity-warning` dulu memakai cokelat `#92400e` + garis `#fcd34d` dari **fallback token hantu**; kini `--warn-ink` #8A5A00 / `--warn-bg` #FFFBEB / `--warn-border` #FDE68A — sama dengan peringatan di halaman lain (terukur di DOM).

## Yang diuji dan bersih

Keluarga lencana (badge/tag/chip) sudah seragam 22 px & 12 px, tanpa label terpotong.

## Cakupan yang belum diuji

- Peran lain (Nutritionist, BGN Monitor, Kepala/Gizi Bandung & Surabaya) dan tab role-gated `Pengaturan`.
- Keadaan `loading`, `empty`, dan `error API` pada halaman ini (yang terukur adalah keadaan berisi).
- Viewport 375 px / 768 px.
