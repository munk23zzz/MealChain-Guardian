# Perluasan kiriman & limbah sampai 5 Nov (2026-10-17)

> **Snapshot 25 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Lanjutan dari `perluasan-deret-aktual-5nov.md`. Deret pasokan/harga sudah
mencapai 4 Nov, tetapi jendela KPI pendek masih membaca nol karena **tabel
peristiwa tidak ikut diperpanjang**:

| tabel | sebelum | sifat angka |
|---|---|---|
| `delivery_events` | 70 baris, 1–7 Okt | "Meal Continuity Rate" = 0.00% di jendela 24 jam (ada rencana, tidak ada kiriman) |
| `disposal_events` | 20 baris, 4–7 Okt | "Avoidable Food Loss" = `no_data` (tidak ada limbah di jendela) |

Nolnya bukan angka palsu, tetapi ia terbaca "tidak ada makanan terkirim" dan
"tidak ada limbah" — padahal sebabnya tabelnya berhenti 7 Okt. Karena itu
keduanya diperluas, bukan dibiarkan.

## Yang berubah

**Migrasi `017_event_origin`** — `delivery_events` dan `disposal_events` kini
punya `origin` (`seed`/`demo`) + `generated_at`, pola yang sama dengan tabel
deret waktu lain (migrasi 013). Baris lama otomatis `origin='seed'`.

**Generator `app/seed/timeseries.py`**

- `EVENT_DEMO_START = 2026-10-08` — hari rencana pertama tanpa kiriman kanonik.
  Jangkar kanonik (2 Okt, 1.200 porsi di Jakarta) karena itu tidak pernah
  tersentuh.
- `plan_delivery_rows()` — satu kiriman per rencana sejak 8 Okt, porsi terkirim
  80–100% dari rencana (85% penuh, 10% ×0,92, 5% ×0,80). Kalau semuanya 100%,
  "Meal Continuity Rate" hanya bisa 100% dan panelnya tidak informatif.
- `plan_disposal_rows()` — dua catatan limbah per hari rencana, 3–13 kg, lokasi
  bergilir (`n` dan `n+3` dari daftar terurut), alasan hanya dua yang dipakai
  data kanonik: `spoilage_cold_chain`, `expired_transport`. Komoditas diambil
  dari pasokan lokasi itu, jadi tidak ada limbah tanpa material.
- Idempotensi lewat **id deterministik** (`uuid5` atas `kind:lokasi:tanggal`) +
  `ON CONFLICT (id) DO NOTHING`; kiriman hanya dibuat untuk rencana yang belum
  punya kiriman apa pun. Dua kali jalan = 0 baris tambahan.
- `PURGE_MODELS` kini memuat kedua tabel (anak dulu, induk belakang), sehingga
  `purge` tidak meninggalkan peristiwa yatim.
- `event_plan` ikut dilaporkan di pratinjau (`counts.deliveries.planned`,
  `counts.disposals.planned`) dan ikut dijaga `pastikan_deret_demo()`.

## Angka yang diharapkan

| tabel | baris demo | total dengan kanonik | rentang |
|---|---|---|---|
| `delivery_events` | 290 (29 hari × 10 lokasi) | 360 | 8 Okt – 5 Nov |
| `disposal_events` | 58 (29 hari × 2) | 78 | 8 Okt – 5 Nov |

## Bukti

`backend/tests/test_perluasan_kirim_limbah.py` (7 tes):

1. kiriman demo menutup semua hari rencana 8 Okt–5 Nov;
2. porsi 0 < terkirim ≤ rencana, dengan minimal dua rasio berbeda;
3. kanonik utuh: 70 kiriman, 20 limbah, 2 Okt Jakarta tetap 1.200 porsi;
4. limbah demo terisi, alasannya hanya yang dikenal, kg > 0;
5. `purge` hanya membuang baris demo;
6. KPI jendela 7 hari kini `available` untuk Meal Continuity dan Avoidable
   Food Loss;
7. agenda 12 Okt punya kiriman dan limbah.

Hasil terukur (2026-10-17, DB dev):

- `python -m app.seed.timeseries` **jalan kedua** → `added: 0` untuk supply,
  harga, menu, **kiriman**, dan **limbah** (idempoten, bukan tebak-tebakan).
- `pastikan_deret_demo()` → `kurang: {}` dengan kiriman 290 dan limbah 58
  ikut dihitung (jaring pengaman kini mencakup peristiwa).
- KPI nasional: **24 jam 6/7 available** (dulu 5/7), **7 hari 7/7** (dulu 6/7),
  **30 hari 7/7**. Meal Continuity **98,20 %** (dulu 0,00 %),
  Avoidable Food Loss **0,07 %** dengan 14 sampel (dulu `no_data`).
  Satu-satunya kartu kosong di 24 jam tinggal Procurement Price Deviation —
  memang butuh pasangan harga, dan kutipan pemasok mingguan.
- Kanonik tidak bergerak: kiriman seed 70 (1–7 Okt), limbah seed 20 (4–7 Okt),
  supply 30 dan harga 44 pada stamp 8 Okt 12:00.

## Catatan jujur

- Kiriman demo **selalu ada** tiap hari (tidak ada hari "tidak kirim"), jadi
  Meal Continuity bergerak di 80–100%, bukan 0%. Hari tanpa kiriman adalah
  skenario yang lebih tajam, tetapi menambahkannya berarti mengubah arti panel
  "Meal Continuity" untuk demo — belum dilakukan tanpa persetujuan.
- Angka ini hidup di DB dev lokal. Demo statis (klon GitHub Pages) tidak
  membaca tabel ini, jadi tidak otomatis ikut.
