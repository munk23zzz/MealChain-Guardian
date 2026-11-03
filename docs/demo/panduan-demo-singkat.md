# Panduan demo MealChain Guardian (ringkas)

Sumber angka: **`docs/state-snapshot.md`** (dihasilkan `scripts/snapshot_state.py`, baca-saja).
Snapshot terakhir: lihat kepala `docs/state-snapshot.md`. Kalau angka di sini berbeda dengan snapshot,
snapshot yang berlaku. Angka yang belum terukur ditulis "—", tidak pernah diganti nol.

**Durasi**: persiapan 15 menit, tampil 12 menit, tanya-jawab 5 menit.

## Keadaan awal yang harus terlihat

| Ukuran | Nilai (26 Okt 2026) |
|---|---|
| Batch | **125** — 2 ditahan karantina, 8 kedaluwarsa < 48 jam |
| Keputusan | **48** — 22 terbuka (17 menunggu, 5 ditandai verifier), 14 kartu di jendela 24 jam |
| Pemasok | 61 (36 hygiene, 17 HACCP, 8 tanpa sertifikat) |
| Pesanan SAP | **20** |
| Penerimaan menunggu | **5** |
| Rute kiriman (cakupan Jakarta) | **15** — 14 berjalur OSRM |
| Jejak agen | **118** langkah |
| Rantai audit | **1.598** blok (1.526 arsip), valid, 0 yatim |
| KPI tersedia hari ini | **6 dari 7** — susut 0,59% (3), imbalance 100% (2), SDC Rp18.472.767,67 (2), harga 2,66% (17), decision time 20 mnt (2), bukti 66,67% (3); kontinuitas `—` |

## Persiapan (urutannya penting)

1. `docker compose up -d` — tunggu backend `healthy`.
2. Tekan **Siapkan data demo** di tab Demo Control (terukur 38–42 detik pada mesin demo). Tombol ini
   membangun template lebih dulu, baru membuka sesi 120 menit. Alternatif CLI:
   `DB_MODE=demo bash scripts/db-mode.sh init-demo` (± 90 detik) — versi CLI tidak membuka sesi,
   jadi semua tulisan tetap ditolak 409 sampai sesi dimulai.
3. `curl -s http://localhost:8000/health` → `healthy`
4. `bash scripts/joule-perbaiki.sh` → berakhir dengan `"backend":{"reachable":true,...}`
5. Buka tiga akun: `sppg.head@demo.local`, `sppg.nutritionist@demo.local`, `bgn.monitor@demo.local` (kata sandi di `.env`)

Layanan: frontend `:3010`, backend `:8000`, jembatan Joule `:8099`, PostgreSQL `15432→5432`, mock SAP `:8001`.

**Jangan** menjalankan `docker compose exec backend pytest` di database kerja: perintah itu mem-purge
baris demo (terukur 26 Okt: keputusan 48 → 9, pasokan 5.240 → 40). Jalankan tes di DB klon dengan `docker run`.

## Enam babak

| Waktu | Tab | Aksi | Angka yang bergerak |
|---|---|---|---|
| 0:00–1:30 | Overview | peta + strip, chip komoditas | 125 batch, 48 keputusan, 15 rute |
| 1:30–4:30 | Recommendations → Decision & Evidence | Kelola persetujuan → Setuju (dua akun) → Eksekusi | persetujuan 0/2 → 1/2 → PO baru terbit, status `executed` |
| 4:30–6:30 | Keamanan Pangan | 3 batch gagal uji (740 kg), 2 ditahan (540 + 180 kg), antrean penerimaan | penerimaan menunggu 5 |
| 6:30–8:00 | Pemasok | cari pemasok, tanda eksklusi, papan kiriman | 15 kiriman — 7 di jalan, 6 tiba, 1 belum berangkat, 1 tanpa jalur |
| 8:00–9:30 | Demo Control | Jalankan agent → status selesai | jejak agen bertambah dari 118 |
| 9:30–12:00 | Joule | kondisi pasokan → antrean penerimaan → direktori pemasok | angka sama dengan layar |

Dua hal yang harus disebut jujur di panggung:

- Pada snapshot terakhir **7 kiriman berstatus "di jalan"** — truk langsung terlihat bergerak. Kalau ingin ada
  truk bergerak, siapkan data tepat sebelum tampil; posisi dihitung dari jam berangkat + durasi rute,
  bukan GPS.
- Tab Keamanan Pangan memakai **partisi**: tile status uji (aman/gagal/perlu verifikasi/belum diuji)
  menjumlah ke 14 batch Jakarta, sedangkan karantina dan kedaluwarsa adalah penanda tambahan.

Detail langkah klik ada di PDF halaman 4.

## Joule

URL: `https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap/webclient/standalone/mealchain_assistant_4sehat3trio`

Diuji 14 pertanyaan, 14 lulus (mode DEMO). Tiga yang aman untuk panggung: `kondisi pasokan`,
`antrean penerimaan`, `direktori pemasok`. Jumlah baris tiap jawaban ikut perubahan data — sebutkan
"sama dengan layar", jangan menyebut angka hafalan.

## Kalau gagal di panggung

| Gejala | Tindakan |
|---|---|
| Joule "backend tidak bisa dihubungi" | `bash scripts/joule-perbaiki.sh` |
| Peta kosong / tanpa truk | `DB_MODE=demo bash scripts/db-mode.sh init-demo` |
| Layar kosong di Overview (peran BGN) | muat ulang; kalau berulang laporkan (diperbaiki 22 Okt) |
| Ingin keadaan bersih | `DB_MODE=default bash scripts/db-mode.sh init-default` |

## Jangan diklaim

Beban pengguna serentak, SAP S/4HANA & tenant Joule produksi (masih endpoint tiruan berkontrak sama),
kuota Bedrock produksi (TPM 0), peta satu komoditas per tampilan, dan **data real-time** — data berasal
dari template demo; angka dihitung ulang tiap permintaan, tetapi tidak ada aliran masuk dari SAP,
PIHPS, atau sensor. Jangan juga mengklaim "seluruh suite hijau": 13 tes backend bergantung urutan.
