# Panduan demo MealChain Guardian (ringkas)

Sumber fakta sama dengan PDF: `docs/demo/panduan-demo-mealchain.pdf` (dibangun oleh
`docs/demo/buat_panduan_demo.py`). Angka diukur 22 Oktober 2026 dari DB `mealchain` dan
`GET /supplier-routes`.

**Durasi**: persiapan 15 menit, tampil 12 menit, tanya-jawab 5 menit.

## Keadaan awal yang harus terlihat

| Ukuran | Nilai |
|---|---|
| Batch aktif | 125 |
| Keputusan | 47 (16 menunggu) |
| Pemasok | 61 |
| Pesanan SAP | 20 |
| Penerimaan menunggu | 5 |
| Rute kiriman | 105 (80 berjalur) |

## Persiapan (urutannya penting)

1. `docker compose up -d`
2. `DB_MODE=demo bash scripts/db-mode.sh init-demo` — ± 90 detik; menyegarkan rute OSRM dan memberangkatkan 8 kiriman
3. `curl -s http://localhost:8000/health` → `healthy`
4. `bash scripts/joule-perbaiki.sh` → berakhir dengan `"backend":{"reachable":true,...}`
5. Buka tiga akun: `sppg.head@demo.local`, `sppg.nutritionist@demo.local`, `bgn.monitor@demo.local` (kata sandi di `.env`)

Layanan: frontend `:3010`, backend `:8000`, jembatan Joule `:8099`, PostgreSQL `15432→5432`, mock SAP `:8001`.

## Enam babak

| Waktu | Tab | Aksi | Angka yang bergerak |
|---|---|---|---|
| 0:00–1:30 | Overview | peta + KPI, chip komoditas | 125 batch, 47 keputusan |
| 1:30–4:30 | Recommendations → Decision & Evidence | Kelola persetujuan → Setuju | persetujuan 0/2 → 1/2 |
| 4:30–6:30 | Keamanan Pangan | batch gagal uji & karantina, antrean penerimaan | menunggu 5 |
| 6:30–8:00 | Pemasok | cari pemasok, tanda eksklusi, papan kiriman | 105 kiriman, 8 di jalan |
| 8:00–9:30 | Demo Control | Jalankan agent → status selesai | jejak agent bertambah |
| 9:30–12:00 | Joule | kondisi pasokan → antrean penerimaan → direktori pemasok | angka sama dengan layar |

Detail langkah klik ada di PDF halaman 4.

## Joule

URL: `https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap/webclient/standalone/mealchain_assistant_4sehat3trio`

Diuji 14 pertanyaan, 14 lulus (mode DEMO). Tiga yang aman untuk panggung: `kondisi pasokan`
(tabel 40 baris), `antrean penerimaan` (12 baris + id), `direktori pemasok`.

## Kalau gagal di panggung

| Gejala | Tindakan |
|---|---|
| Joule "backend tidak bisa dihubungi" | `bash scripts/joule-perbaiki.sh` |
| Peta kosong / tanpa truk | `DB_MODE=demo bash scripts/db-mode.sh init-demo` |
| Layar kosong di Overview (peran BGN) | muat ulang; kalau berulang laporkan (diperbaiki 22 Okt) |
| Ingin keadaan bersih | `DB_MODE=default bash scripts/db-mode.sh init-default` |

## Jangan diklaim

Beban pengguna serentak, SAP S/4HANA & tenant Joule produksi (masih endpoint tiruan berkontrak sama),
kuota Bedrock produksi (TPM 0), dan peta satu komoditas per tampilan.
