# Audit desain — Login

**Tugas halaman:** Masuk ke konsol: pilih akun demo / isi email+sandi.
**Peran yang diukur:** SPPG Operations Lead (`sppg.head@demo.local`) · viewport 1280×~620 · snapshot 22 Okt 2026 15.5x WIB
**Vonis:** konsisten setelah perbaikan; tidak ada token hantu, tidak ada teks di bawah 12 px, satu bahasa gerak.

## Metrik runtime (computed style, bukan sumber)

| metrik | sebelum | sesudah |
|---|---|---|
| ukuran teks unik | 6 | 6 (12/13/14/16/18/32) |
| radius unik | 3 | 3 |
| keluarga huruf | 2 (Fira Sans + Arial) | 1 (Fira Sans) |
| nama animasi aktif | 0 | 0 (login tidak beranimasi, disengaja) |

## Temuan & perbaikan

Kontrol form (input, tombol Masuk) tampil **Arial**: `font-family` tidak diwarisi. Diperbaiki lewat aturan global `button,input,select,textarea{font:inherit}` di `theme-ext.css`. Terukur sesudah: `input` = Fira Sans 14 px warna `--ink`, tombol = Fira Sans 16 px, satu keluarga huruf di seluruh halaman, 13,3333 px (bawaan peramban) hilang.

## Yang diuji dan bersih

Arial pada `input`/`button.login-submit` (terukur: 3 elemen Arial); radius 4/8/12 px semuanya token.

## Cakupan yang belum diuji

- Peran lain (Nutritionist, BGN Monitor, Kepala/Gizi Bandung & Surabaya) dan tab role-gated `Pengaturan`.
- Keadaan `loading`, `empty`, dan `error API` pada halaman ini (yang terukur adalah keadaan berisi).
- Viewport 375 px / 768 px.
