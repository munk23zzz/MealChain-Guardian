---
name: db-mode
description: Use when choosing, preparing, or resetting the MealChain Guardian database mode — DEFAULT (reference data only, clean dev/production) or DEMO (full demo dataset). Covers exact commands, how to verify the active mode, switching, and rollback.
---

# db-mode — memilih dan menyiapkan mode database

Dua mode, satu schema:

| | **DEFAULT** | **DEMO** |
|---|---|---|
| Isi | schema lengkap + data referensi/master: komoditas, lokasi/SPPG, akun RBAC | DEFAULT + seluruh dataset demo (kanonik, deret waktu 1 Sep–5 Nov, aktivitas, 4 kasus/kota, pelengkap cakupan) |
| Tabel bisnis | **kosong** — empty state frontend harus benar | terisi, semua bertanda `origin='demo'` |
| Dipakai untuk | development bersih, CI, produksi | presentasi juri, demo Joule, uji end-to-end |
| `DB_MODE` | `default` | `demo` |

Mode **tidak** disimpan sebagai tebakan di kepala operator: `status` membacanya
dari isi database (`mode_isi`) dan membandingkannya dengan `DB_MODE`
(`mode_env`). Bila `cocok: false`, ikuti nilai `mode_isi` — itulah kenyataan.

## Kapan memakai yang mana

- **DEFAULT** — memulai fitur baru, menguji empty state/loading/error, menjalankan
  suite tes yang menyemai datanya sendiri, atau menyiapkan database produksi.
- **DEMO** — sebelum demo/juri, sebelum menguji jawaban Joule, saat memeriksa
  pagination/filter/grafik dengan volume data nyata, atau saat memotret layar.

## Perintah persis

Semua dari akar repo (`mealchain-guardian/`), stack Docker hidup
(`docker compose up -d postgres backend`).

```bash
# 1. Lihat mode aktif + jumlah baris per tabel + revisi alembic
bash scripts/db-mode.sh status

# 2. Siapkan mode DEFAULT (schema + referensi saja)
DB_MODE=default bash scripts/db-mode.sh init-default

# 3. Siapkan mode DEMO (referensi + dataset demo penuh; ~2-4 menit)
DB_MODE=demo bash scripts/db-mode.sh init-demo

# 4. Bangun ulang deret demo relatif HARI INI (dipakai bila demo lama)
DB_MODE=demo bash scripts/db-mode.sh init-demo --refresh

# 5. Kembali ke DEFAULT (hapus baris bisnis; referensi tetap)
DB_MODE=default bash scripts/db-mode.sh reset-demo --yes
```

Database selain `mealchain` (mis. DB gate terpisah): tambahkan `DB_NAME=...`.

```bash
DB_NAME=mealchain_gate DB_MODE=default bash scripts/db-mode.sh init-default
```

Untuk database yang benar-benar baru, buat dulu:

```bash
docker exec mealchain-postgres sh -lc \
  "dropdb -U mealchain --if-exists <nama> && createdb -U mealchain <nama>"
```

`init-*` menjalankan `alembic upgrade head` sendiri, jadi database kosong
langsung menjadi schema terkini.

## Cara memastikan mode benar (jangan percaya ingatan)

```bash
bash scripts/db-mode.sh status | head -8
```

Yang harus dibaca:

- `mode_isi` — mode menurut isi database (ini yang dipakai).
- `mode_env` — nilai `DB_MODE` yang diharapkan aplikasi. **`null` berarti
  operator tidak menyetelnya** (skrip tidak mengarang nilai bawaan), jadi tidak
  ada yang perlu diperbandingkan.
- `cocok` — `true`/`false` hanya muncul bila `mode_env` diisi. `false` berarti
  environment dan isi database berbeda; perbaiki dengan perintah
  `init-*`/`reset-demo`, atau ubah `DB_MODE` di `.env`.
- `jumlah` — bila mode DEFAULT, semua tabel bisnis harus `0`.
- `bertanda_demo` — jumlah baris `origin='demo'` per tabel (mode DEMO).

## Pindah mode

- **DEFAULT → DEMO**: `DB_MODE=demo bash scripts/db-mode.sh init-demo`.
- **DEMO → DEFAULT**: `DB_MODE=default bash scripts/db-mode.sh reset-demo --yes`
  (menghapus baris bisnis, komoditas/lokasi/akun tetap).
- **DEMO → DEMO (segar)**: `init-demo --refresh` — idempoten, tidak menggandakan
  baris; waktu deret bergeser ke hari ini.

## Pengaman yang sudah terpasang

- `reset-demo` **menolak** jalan bila host database bukan lokal
  (`postgres`, `localhost`, `127.0.0.1`, `db`) atau bila `DB_MODE_ENV=production`.
- `reset-demo` tanpa `--yes` hanya menjelaskan rencananya, tidak menghapus.
- Semua `init-*` idempoten: id memakai `stable_uuid(...)`, jadi dijalankan dua
  kali tetap menghasilkan jumlah baris yang sama.
- `reset-demo` tidak menyentuh `commodities`, `locations`, `users`.

## Rollback bila salah mode

1. Jangan panik: data demo selalu bisa dibangun ulang
   (`init-demo`) dan selalu bisa dibersihkan (`reset-demo --yes`).
2. Bila `init-demo` dijalankan di database yang salah, hentikan dan periksa
   `status` (host + jumlah). Baris demo bertanda `origin='demo'`, jadi
   `reset-demo --yes` aman di database demo mana pun.
3. Bila schema perlu mundur satu revisi (hanya di DB lokal):
   `docker compose exec backend alembic downgrade -1`, lalu
   `docker compose exec backend alembic upgrade head`.
4. Sebelum tindakan destruktif apa pun, ambil dump:
   `docker exec mealchain-postgres pg_dump -U mealchain -Fc -d <db> > data/backups/<db>-$(date +%F-%H%M).dump`

## Sesi demo vs mode demo

`DB_MODE=demo` mengisi database; ia **tidak** menyalakan pengunci sesi.
Pengunci sesi (`DEMO_SESSION_ENFORCE=true`) membuat data hanya terlihat selama
sesi berjalan dan dibersihkan saat sesi berakhir — berguna untuk juri yang
ingin melihat "database kosong lalu diisi". Untuk mode demo yang harus selalu
tampil penuh (mis. pengujian Joule), biarkan `DEMO_SESSION_ENFORCE=false`
seperti pada `.env.example`.
