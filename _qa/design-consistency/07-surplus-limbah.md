# Audit desain — Surplus & Limbah

**Tugas halaman:** Neraca surplus/kekurangan per komoditas.
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

Pil komoditas aktif memakai warna kategori (`--cat-amber-solid` #92400E untuk wortel) — **by design**, bukan fallback; dicatat agar tidak salah dibaca sebagai pelanggaran.

## Yang diuji dan bersih

Zebra baris `.location-table` dulu `#FAFBFC` (di luar palet) → `var(--surface-sunken)`.

## Cakupan yang belum diuji

- Peran lain (Nutritionist, BGN Monitor, Kepala/Gizi Bandung & Surabaya) dan tab role-gated `Pengaturan`.
- Keadaan `loading`, `empty`, dan `error API` pada halaman ini (yang terukur adalah keadaan berisi).
- Viewport 375 px / 768 px.
