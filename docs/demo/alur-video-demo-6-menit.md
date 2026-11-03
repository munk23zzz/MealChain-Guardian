# Alur membuat video demo 6 menit — MealChain Guardian

Dokumen kerja untuk **merekam video**, bukan presentasi langsung. Bedanya dengan
`alur-demo-juri.md` (11–14 menit, ada Q&A):

- tidak ada juri yang bisa bertanya, jadi setiap klaim harus terbaca **di layar**;
- waktu mati (tunggu sesi 38–42 detik, tunggu review ±90 detik) **dipotong saat editing**,
  tapi tetap harus direncanakan supaya rekaman tidak terlihat kosong;
- angka di dokumen ini adalah **snapshot**, bukan janji. Ambil ulang tepat sebelum rekam
  (§1.3) dan sesuaikan narasi, bukan datanya.

Nama tab di bawah diambil dari `frontend/app/page.tsx:1271-1310`, bukan dari ingatan:
**Hari Ini · Overview · Location Network** (di akun ahli gizi berubah jadi **Pasokan &
Kebutuhan**) **· Recommendations · Decision & Evidence · Keamanan Pangan · Pemasok ·
Agent Log · Performance & Audit · Pengaturan · Demo Control**.

Dua koreksi penting: **tidak ada tab "Supply & Demand"** (isinya ada di Location
Network) dan **tidak ada tab "Ledger"** (bukti ledger ada di dalam Decision & Evidence,
panel Integritas).

---

## 1. Pra-syarat teknis (jalankan 30 menit sebelum rekam)

### 1.1 Stack hidup

```bash
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'mealchain|mock-sap'
curl -s http://localhost:8000/health | head -c 400
curl -s -o /dev/null -w 'frontend=%{http_code}\n' http://localhost:3010/
```

Harus: backend 200 (`status: healthy`), frontend 200, postgres healthy, mock-sap jalan.

### 1.2 Review agent disetel ke jalur lokal — WAJIB

```bash
docker exec mealchain-backend sh -lc 'echo $AGENT_REVIEW_MODE'
```

Kalau hasilnya `advisory`, ganti dulu:

```bash
docker exec mealchain-backend sh -lc 'echo "AGENT_REVIEW_MODE=local" >> /app/.env'
docker restart mealchain-backend && sleep 20
```

Alasan (terukur 29 Okt 2026): mode `advisory` mengirim review ke runtime AgentCore,
lalu runtime memanggil balik API publik. Tunnel publik sedang mati, jadi review
gagal `HTTP 502 no tunnel` / `404 decision tidak ditemukan`. Mode `local` berjalan
in-process pada DB yang sama — 9 baris jejak, terbukti.

### 1.3 Angka hari ini — baca ulang, jangan menyalin dari dokumen

```bash
docker exec mealchain-postgres psql -U mealchain -d mealchain -t -c "
select 'keputusan='||count(*) from decisions
union all select 'batch='||count(*) from batches
union all select 'ledger='||count(*) from ledger_blocks
union all select 'pemasok='||count(*) from suppliers
union all select 'status:'||string_agg(s||'='||n,' ') from (select status s,count(*) n from decisions group by 1) t;"
```

Tulis hasilnya di kolom "Angka rekam" pada tabel babak (§2). Angka yang dipakai
narasi **hanya** yang keluar dari perintah ini.

### 1.4 Data demo siap (dan tidak disentuh lagi setelahnya)

- Tekan **"Siapkan data demo"** di panel Demo Control **sebelum** rekam. Terukur ±70 detik.
- Sesi aktif berlaku **120 menit** — tidak bisa diperpanjang. Mulai rekam ≤20 menit setelah sesi siap.
- **Jangan** menekan tombol itu di tengah rekaman: id keputusan berubah, kartu di layar jadi menunjuk baris yang sudah tidak ada.

### 1.5 Satu putaran review sudah selesai (supaya tidak menunggu 90 detik di kamera)

Jalankan satu kali sebelum rekam — lewat UI ("Jalankan agent") atau:

```bash
docker exec mealchain-postgres psql -U mealchain -d mealchain -t -c "
select decision_id, count(*) from agent_traces group by 1 order by 2 desc limit 3;"
```

Butuh satu `decision_id` dengan **9 baris** (7 worker + verifier + SUPERVISE).
Itu yang ditampilkan di babak 4 — rekaman tidak perlu menunggu model.

### 1.6 Yang TIDAK boleh masuk video

| Hal | Keadaan hari ini | Tindakan |
|---|---|---|
| Joule chat | tunnel mati → `502 no tunnel` | jangan direkam; sebut di slide batas |
| SAP "live" | masih mock (`sap_mock_purchase_orders`) | boleh tampil, tapi narasi menyebut "disimulasikan lewat mock" |
| Peramalan cadangan | hanya bila model mati | jangan dipaksa muncul; cukup jelaskan labelnya |

### 1.7 Perangkat rekam

- OBS Studio (atau Xbox Game Bar `Win+G`): 1920×1080, 30 fps, sumber = jendela browser.
- Browser: zoom **110–125%**, bookmarks bar disembunyikan, satu profil bersih, **notifikasi dimatikan** (Focus Assist).
- Dua tab browser sudah login sebelum rekam: SPPG Head dan ahli gizi (jangan login di tengah take).
- Mikrofon diuji 10 detik; rekam ruangan senyap. Bicara ±130 kata/menit → 6 menit ≈ 780 kata.
- Kursor disorot (OBS: highlight cursor) supaya klik terbaca di video.

---

## 2. Tulang waktu 6 menit (6 babak, 7 klik + 1 opsional)

Enam menit memberi ruang satu klik lebih banyak daripada panduan lima menit. Semua nama tab di bawah sudah diverifikasi ke kode.

Format tiap baris: **waktu · klik · yang harus muncul · narasi · angka wajib terbaca**

### Babak 0 — 0:00–0:40 · Overview (0 klik)

- **Muncul:** kartu angka di Overview.
- **Narasi:** "Ini bukan mockup. Keadaan pagi ini di database demo: 62 keputusan,
  31 di antaranya menunggu tindakan, 141 batch. Setiap angka di layar ini punya baris
  di database dan punya jejak audit."
- **Angka wajib:** jumlah keputusan + yang menunggu tindakan + batch (dari §1.3;
  angka 62/31/141 adalah contoh hasil ukur 29 Okt 2026 — ganti dengan hasil perintah hari rekam).

### Babak 1 — 0:40–2:10 · Recommendations → dua peran memutuskan (4 klik)

- **Klik 1:** tab **Recommendations** → buka satu keputusan `pending_approval`.
- **Klik 2:** **Approve** sebagai SPPG Head.
- **Klik 3:** pindah ke tab ahli gizi → **Approve** (persetujuan kedua).
- **Klik 4:** **Execute**.
- **Muncul:** status `pending_approval` → `approved` → `executed`; entri baru di riwayat persetujuan.
- **Narasi:** "Satu peran tidak cukup. Kepala SPPG mengusulkan, ahli gizi menyetujui, baru bisa dieksekusi — dan yang mengeksekusi bukan model, melainkan endpoint deterministik yang memeriksa ulang kelayakan."
- **Angka wajib:** dua nama peran + status akhir `executed`.

### Babak 2 — 2:10–3:10 · Decision & Evidence → bukti ledger (1 klik)

- **Klik 5:** tab **Decision & Evidence** → panel **Integritas** untuk keputusan yang sama.
- **Muncul:** dossier keputusan + hasil verifikasi ledger (`valid: true`, 0 yatim) + jumlah blok.
- **Narasi:** "Ini bukti yang tidak bisa diubah belakangan: setiap langkah tercatat di
  ledger berantai, dan verifikasinya dijalankan saat halaman dibuka — bukan label statis."
- **Angka wajib:** jumlah blok + `valid` + jumlah yatim (0).

### Babak 3 — 3:10–4:10 · Location Network → angka ramalan (1 klik)

- **Klik 6:** tab **Location Network** (di akun ahli gizi: **Pasokan & Kebutuhan**)
  → pilih komoditas yang punya riwayat.
- **Muncul:** angka kebutuhan + label sumber **SAP-RPT-1.6** + keyakinan (mis. "keyakinan 94%").
- **Narasi:** "Kebutuhannya bukan tebakan: model tabular SAP-RPT-1.6 membaca 28 hari
  riwayat. Kalau modelnya mati, sistem jatuh ke aturan statistik — dan labelnya berubah,
  jadi Anda selalu tahu angka mana yang sedang dilihat. Ada cache 15 menit dan rem
  biaya 20 panggilan per menit."
- **Angka wajib:** jumlah kg + `SAP-RPT-1.6` + persen keyakinan.

### Babak 4 — 4:10–5:10 · Agent Log → sembilan langkah (1 klik)

- **Klik 7:** tab **Agent Log** → buka jejak `decision_id` dari §1.5.
- **Muncul:** 9 baris — DETECT, PREDICT, VERIFY (freshness, safety, verifier),
  OPTIMIZE (price, logistics), TRACE, SUPERVISE — lengkap dengan durasi dan status.
- **Narasi:** "Sembilan langkah, dan garisnya jelas: angka dihitung Python —
  deterministik dan bisa diuji. Model bahasa hanya menarasikan dan mengaudit, mode
  advisory, tidak bisa mengubah status keputusan. Supervisor boleh menulis 'vetoed',
  tetapi keputusan tetap milik manusia."
- **Angka wajib:** 9 baris + status supervisor.

### Babak 5 — 5:10–6:00 · Keamanan Pangan + penutup (1 klik, boleh dipotong)

- **Klik 8:** tab **Keamanan Pangan** → satu batch gagal/karantina.
- **Muncul:** batch bertanda gagal, dan alokasi tidak menawarkannya.
- **Narasi:** "Batch yang gagal uji tidak pernah masuk kandidat alokasi. Ini dijaga kode
  Python, dan ada tes yang gagal kalau modul keselamatan sampai memanggil model.
  Batas yang saya sebut sendiri: SAP masih disimulasikan lewat mock, Joule chat belum
  tersambung ke backend publik, dan narasi agen tidak deterministik — angkanya yang
  deterministik."
- **Angka wajib:** jumlah batch ditahan/gagal + komoditas + lokasi.

**Kalau waktunya mepet:** potong babak 5 lebih dulu, jangan babak 1 dan 2.
Prioritas: Babak 1 (keputusan) > Babak 2 (ledger) > Babak 4 (jejak) >
Babak 3 (ramalan) > Babak 5 (safety).

---

## 3. Amunisi cadangan (kalau ada babak yang gagal / waktu sisa)

| Kalau ini gagal | Ganti dengan | Biaya waktu |
|---|---|---|
| Approve kedua ditolak (peran salah) | tunjukkan riwayat persetujuan keputusan lain yang sudah `executed` | 20 detik |
| Label `SAP-RPT-1.6` tidak muncul | tunjukkan `/health` blok `forecast` (`sap_rpt_configured: true`) + jelaskan labelnya | 25 detik |
| Batch gagal tidak ada di daftar | tunjukkan KPI food loss di **Performance & Audit** | 20 detik |
| Agent Log kosong | sebut "review dijalankan setelah keputusan dibuat" + tunjukkan screenshot hasil §1.5 (boleh di-insert saat editing) | 15 detik |
| Ledger lambat memuat | potong saat editing, narasi diulang di atas gambar | — |

---

## 4. Langkah merekam (urut)

1. **Rekam 2 take penuh**, jangan potong-potong per babak. Take kedua hampir selalu lebih baik.
2. Sebelum take: segarkan browser, pastikan sesi masih aktif, tutup tab lain.
3. Saat menunggu (sesi 38–42 detik, review ±90 detik): **diam dan jangan bicara** — bagian ini dipotong saat editing, bukan dinarasikan.
4. Setelah take: catat jam mulai tiap babak (atau tekan penanda) supaya editing cepat.
5. Editing: buang waktu tunggu, sisipkan potongan percepatan (2×) hanya untuk progres bar, jangan untuk keputusan.
6. Panjang final **≤ 6:00**. Kalau lebih, potong babak 5 dulu, lalu babak 3 — jangan potong babak 1 dan 2.
7. Caption Indonesia (auto) + koreksi nama teknis: SAP-RPT-1.6, AgentCore, ledger, RPT.
8. Ekspor 1080p; simpan versi tanpa narasi untuk Q&A.

---

## 5. Jangan lakukan

- Jangan menekan "Siapkan data demo" atau "Bangun ulang" saat merekam.
- Jangan meninggalkan suite tes penuh berjalan: ia memakai DB yang sama, menulis ulang baris, dan merebut CPU.
- Jangan merekam saat `AGENT_REVIEW_MODE=advisory` (review akan gagal di layar).
- Jangan mengklaim SAP live, Joule tersambung, atau "semua agen berjalan dengan LLM" — ketiganya tidak benar hari ini.
- Jangan menarasikan angka yang tidak terbaca di layar. Kalau ragu, ganti dengan angka yang tampil.

---

## 6. Setelah rekaman

```bash
# 1) catat angka yang BENAR-BENAR muncul di video
docker exec mealchain-postgres psql -U mealchain -d mealchain -t -c "
select count(*) from decisions; select count(*) from ledger_blocks;"

# 2) kembalikan mode review bila perlu
docker exec mealchain-backend sh -lc 'grep AGENT_REVIEW_MODE /app/.env'

# 3) tutup sesi demo (opsional, bila sesi dibuat khusus untuk rekaman)
#    POST /demo/session/end — atau lewat panel "Akhiri sesi"
```

Tulis di catatan rilis: tanggal rekam, angka saat rekam, babak tercepat/terlambat,
dan hal yang gagal di take pertama. Itu bahan revisi untuk take berikutnya.

---

## 7. Ringkasan satu layar

```
0:00  Overview              angka hari ini              "bukan mockup"
0:40  Recommendations       approve 2 peran → execute   (4 klik)
2:10  Decision & Evidence   ledger valid, 0 yatim       (1 klik)
3:10  Location Network      label SAP-RPT-1.6 + keyakinan (1 klik)
4:10  Agent Log             9 baris; Python vs narasi LLM (1 klik)
5:10  Keamanan Pangan       batch gagal tidak dialokasikan (1 klik, opsional)
6:00  tutup + batas
```
