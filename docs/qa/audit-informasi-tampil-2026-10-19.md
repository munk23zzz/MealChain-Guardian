# Audit informasi yang tampil — 19 Okt 2026

Permintaan pemilik: *"cek untuk semua informasi yang tampil apakah sudah benar karena di saya
beberapa error, pastikan semuanya aman"*.

## 1. Akar "beberapa error": mesin Docker mati, bukan aplikasi

`docker version` mengembalikan **HTTP 500** dari `dockerDesktopLinuxEngine`, `docker ps` kosong,
`curl :3010` menggantung. Artinya semua tab gagal memuat data sekaligus — bukan bug per halaman.
Pemulihan: `docker desktop restart` → 45 detik kemudian keempat kontainer `Up (healthy)`,
`:3010` → 200, `:8000/health` → 200. Tidak ada perubahan kode untuk ini.

## 2. Temuan yang benar-benar salah (dan sudah diperbaiki)

| # | Gejala di layar | Akar | Perbaikan | Bukti |
|---|---|---|---|---|
| A1 | Kartu "Rekomendasi menunggu" **16**, lonceng top bar **24**, badge nav **(24)** | `notifList(decisions, 4)` dipanggil **tanpa peran**; `proposed` hanya dihitung untuk `sppg_head` | `notifList(decisions, 4, role)` + tes pengunci di `tests/topbar-lib.test.ts` | live: kartu 24 · lonceng 24 · nav 24; SQL Jakarta: 8 proposed + 15/10 pending + 5/4 approved + 4/2 flagged |
| A2 | Saat halaman baru dibuka, kartu menulis **"0"** dan "semua sudah ditindaklanjuti" | nilai awal `decisions = []` sebelum query selesai | `decisionsQuery.isLoading` → tampil `"—"` + "memuat daftar keputusan" | live: tidak ada lagi 0 palsu saat muat |
| A3 | Pemasok "Ayam Segar Karawang" mengirim **telur**; "CV Sayur Berastagi" mengirim **beras** | seeder memilih pemasok dengan `indeks % len(pemasok)`; nama komoditas berhuruf besar membuat kamus kata kunci tidak cocok | `_pemasok_untuk()`: cocokkan kata komoditas → pemasok netral → daftar penuh; `str(komoditas).lower()` | SQL: 0 baris batch yang pemasoknya lintas komoditas |
| A4 | PO menampilkan kode bahan **`MAT-BERA`, `MAT-WORT`, `MAT-TELU`** | baris lama dibuat sebelum pemetaan memakai nama penuh | normalisasi di seeder dari `decisions.commodity_id` | SQL: hanya `MAT-AYAM(3)`, `MAT-BERAS(3)`, `MAT-TELUR(3)`, `MAT-WORTEL(2)` |
| A5 | 10 kiriman "rute jalan belum disinkronkan", kolom **Estimasi tiba `—`** | sinkronisasi rute pertama hanya menyentuh kiriman "aktif" | `sync_road_routes(..., semua_batch=True)` → 118 diperiksa, 107 ada, 11 diambil, 0 gagal | live Pemasok: "Jalur kiriman (jalan) **37 dari 37**", 0 baris `—`, 0 "belum disinkronkan" |

## 3. Angka yang diperiksa ulang terhadap database (semua cocok)

| Yang tampil | Nilai layar | Nilai DB/API | Status |
|---|---|---|---|
| Selisih pasokan Jakarta | −779,86 kg (kurang 73%) | `/balance/map?commodity=telur`: supply 291,09 − demand 1.070,95 | cocok |
| Pasokan terpantau | 291,09 kg / 1.070,95 kg (27%) | sama | cocok (aritmetika 27% benar) |
| Batch keamanan pangan | 43 diperiksa · 29 aman · 6 gagal (1.011 kg) · 5 perlu verifikasi · 9 kedaluwarsa | DB: pass 26 + 3 kanonik, fail 6 = 1.011,00 kg, verifikasi 5, pending 3 | cocok |
| Limbah tercatat | 381,2 kg · 49 peristiwa · 39,3 tanpa mitra | `/waste/summary` jendela 30 hari: 381,22 · 49 · 39,32 | cocok (50 baris total di DB, 1 di luar jendela) |
| Purchase order | terkirim 7 · terkonfirmasi 2 · **Rp 80.425.600,00** | `sum(ordered_quantity*price)` Jakarta: 47.545.600 + 32.880.000 | cocok sampai rupiah |
| Lonceng notifikasi | 24 menunggu · 41 lewat tenggat | SQL Jakarta: aktif 24, lewat tenggat 41 | cocok |
| Integritas bukti | 160 dari 160 blok tertaut | `/ledger/verify` linked_ratio 1,0 | cocok |
| KPI 24 jam | 7/7 metrik tersedia | `/kpi` semua `available` | cocok |
| Pemasok | 60 terdaftar · 82% rata-rata · 4 keandalan <60% · 37 kiriman | `/suppliers` + `/deliveries` | cocok |

## 4. Nol dan "—" yang memang benar (bukan data hilang)

- `TOTAL SURPLUS —` dan `Lokasi surplus 0` di tab Surplus: cakupan Kepala SPPG satu lokasi, dan
  Jakarta sedang **kekurangan** telur. Nol adalah jawaban, bukan kegagalan memuat.
- `0 DITAHAN (KARANTINA)`: belum ada batch yang dikarantina.
- `0 dari 5 titik periksa sudah ditandai`: daftar tugas pemeriksaan, bukan metrik; menandainya
  otomatis akan memalsukan catatan inspeksi.
- Komposisi putusan verifikator "tidak tersedia" untuk 4 dari 8 run: belum ada putusan, dan
  mengarang putusan lebih buruk daripada jujur.

## 5. Konsol & galat runtime

Sapuan 10 tab: **0 js error, 0 permintaan 4xx/5xx**, tidak ada `NaN`/`undefined`/`Invalid Date`.
Satu-satunya pesan di konsol adalah peringatan dev React tentang `defaultProps` pada
`XAxis`/`YAxis` recharts — peringatan pustaka, hilang di build produksi, bukan kegagalan.

## 6. Gerbang

- `npx tsc --noEmit` → 0
- `npx vitest run` → **1392 lulus / 124 berkas**
- `ruff check app/seed/jakarta_lengkap.py` → bersih
- Suite backend penuh sengaja tidak dijalankan setelah seeding: fixture-nya menghapus baris
  `origin='demo'`. Jalankan suite lebih dulu, lalu `python -m app.seed.jakarta_lengkap`.

## 7. "Review 7 agen kosong setiap kali Jalankan agent" — akar dan perbaikan

Gejala: setiap run baru, panel **Review 7 agen** kosong (`agent_review: unavailable`) walau
langkah pipeline tercatat; keputusan lama tetap 7/7 karena baris review-nya berasal dari dataset demo.

Akar: worker review berjalan di AgentCore (AWS) dan memanggil balik API lewat
`MEALCHAIN_API_URL`. Nilainya `https://solid-faster-reef-finally.trycloudflare.com` — Quick Tunnel
yang sudah mati (`nslookup`: could not resolve host; `curl /health` → 000). Worker gagal dengan
`AgentApiError: tidak dapat menghubungi API ... (Name or service not known)`, dan kode sengaja
TIDAK menulis 7 baris palsu saat runtime gagal.

Perbaikan: `python agent/tunnel_watchdog.py` (venv dengan boto3) — menjalankan cloudflared,
membaca URL baru `https://jewish-spoken-stage-puts.trycloudflare.com`, memanggil
`agent/set_runtime_env.py` (runtime READY · versi 19), memperbarui `.env`, lalu memverifikasi
`/health` 200 dari luar.

Bukti sesudahnya: `POST /demo/agent/run` (beras) 23,9 dtk → `agent_review: completed`,
run `ccf2b4bd`; DB 15 baris trace (7 pipeline + 8 review: supply, demand, freshness, safety,
price, logistics, evidence, supervisor); layar Agent Log: **"REVIEW 7 AGEN · ADVISORY · run
ccf2b4bd · 7/7 tercatat"** dengan 7 kartu worker.

Catatan operasional: watchdog harus tetap hidup selama demo. Kalau mesin/terminal ditutup, URL
tunnel mati lagi dan gejalanya kembali persis sama.
