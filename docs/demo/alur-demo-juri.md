# Alur demo juri — MealChain Guardian

Dokumen kerja untuk sesi demo 11–14 menit. Semua angka di bawah **dibaca dari
database yang sekarang berjalan** (PostgreSQL 16.15, `mealchain`), bukan
perkiraan. Kalau angka berubah, dokumen ini yang harus diperbarui — bukan
sebaliknya.

---

## 0. Keadaan awal (yang harus benar sebelum juri masuk)

| Aspek | Nilai |
|---|---|
| Batch | **120** (beras 31, wortel 30, telur 30, ayam 29) |
| Keputusan | **31** — 11 `pending_approval` (semua sudah `verified: consistent`), 5 `executed`, 9 `rejected`, 3 `verifier_flagged`, 3 lain (1 `approved`, 1 `proposed`, 1 `review_only`) |
| Notifikasi (Jakarta) | **5** (4 menunggu tindakan + 1 ditandai verifier) |
| Pesanan SAP | **16** (14 confirmed, 2 submitted) |
| Blok ledger | **72**, `valid: true`, `linked_ratio: 1.0`, 0 yatim |
| Trace agent | **82** |
| Pemasok / lokasi / komoditas | 60 / 10 / 4 |
| Penerimaan menunggu | **2** — ayam 90 kg, beras 300 kg (Jakarta) |
| Eksklusi pemasok | **1 aktif** (CV Ambarawa Telur Utama), **1 usulan** (CV Ayam Kampung Cugenang) |
| Karantina | **1 batch** beras Jakarta 540 kg; **1 batch gagal uji** beras 800 kg (9,5 °C, 8 titik log, ~80 menit) |
| KPI 30 hari | 7/7 tersedia: kontinuitas 100%, food loss 1,70%, imbalance 100%, SDC Rp18.062.477,91, deviasi harga 2,66%, decision time 20 menit, kelengkapan bukti 100% |
| Akun demo | 7 (3 kepala SPPG, 3 ahli gizi, 1 BGN monitor) |

**Prasyarat teknis**: `POST /demo/session/start` = **±70 detik** (menyemai 120
batch + mengambil 53 rute OSRM). Jalankan 5 menit sebelum tampil, jangan saat
juri menunggu. Setelah aktif, sesi berlaku 120 menit.

---

## 1. Peta enam babak (11 menit)

| # | Babak | Durasi | Tab | Pesan ke juri |
|---|---|---|---|---|
| 0 | Pembuka angka | 1,5' | Overview | "Ini kondisi pagi ini, bukan mockup." |
| 1 | Agent mengusulkan, manusia memutuskan | 3' | Recommendations → Decision & Evidence | Otonomi terbatas: approve 2 peran + eksekusi |
| 2 | Keamanan pangan | 2' | Keamanan Pangan | Batch gagal diblokir dari alokasi |
| 3 | Penerimaan barang | 1,5' | Keamanan Pangan (penerimaan) | Angka pasokan bergerak karena stok nyata |
| 4 | Pemasok berisiko | 1,5' | Pemasok | Eksklusi ber-scope, ada jalur pemulihan |
| 5 | Surplus lintas lokasi | 1,5' | Surplus & Limbah | 208 kg wortel Cianjur → Bogor, biaya 3,4% |
| 6 | Bukti & KPI | 1' | Agent Log, KPI, Ledger | 72 blok, 100% tertaut |

Cadangan bila waktu habis: babak 0 → 1 → 6 (angka + bukti), sisanya disebut
lisan.

---

## 2. Detail babak

### Babak 0 — Pembuka (Overview, 1,5 menit)

1. Login **SPPG Head** (`sppg.head@demo.local`, password di `Demo Control` →
   tombol akun demo; jangan ditulis di slide).
2. Overview memuat otomatis. Biarkan 5 detik agar `Live Sync (5s)` selesai.
3. Tunjuk, jangan klik:
   - **Kartu selisih pasokan**: `−780 kg` (kurang 72% dari kebutuhan), `0 lokasi
     surplus · 1 shortage` untuk komoditas terpilih.
   - **Pasokan terpantau**: `300 kg` dari `1.080 kg` kebutuhan jaringan (28%).
   - **Notifikasi**: `5`.
   - **Peta**: pilih komoditas **wortel** dulu — hanya wortel yang punya kiriman
     `di_jalan` hari ini, jadi hanya di situ garis + ikon truk muncul; pemasok
     aktif berdenyut violet `#8B5CF6`. Komoditas lain menampilkan pin tujuan dan
     kartu "tidak ada kiriman berjalan" (itu juga jujur, bukan bug).
4. Kalimat: "Angka ini berubah selama demo. Saya akan buktikan tiga kali."

### Babak 1 — Agent mengusulkan, manusia memutuskan (3 menit)

Rute klik: **Recommendations** → kartu `regional_balance` (alokasi antar lokasi)
→ **Decision & Evidence** → Verifikasi tampil `consistent` → **Setujui** →
login **Nutritionist** (`sppg.nutritionist@demo.local`) → **Setujui** →
kembali ke Head → **Eksekusi**.

Angka yang bergerak (terukur):

| Momen | Sebelum | Sesudah |
|---|---|---|
| Status keputusan | `pending_approval` | `executed` |
| Pesanan SAP | 16 | **17** |
| Blok ledger | 72 | **75** (approve kepala, approve gizi, eksekusi) |
| Trace agent | 82 | +1 per aksi |

Kalimat: "Dua peran berbeda harus setuju. Agent tidak boleh mengeksekusi
sendiri — dan setiap persetujuan meninggalkan blok hash yang tidak bisa diubah."

Cadangan: bila tombol eksekusi menolak, keputusan itu butuh bukti tambahan;
pilih kartu `regional_balance` lain (Bandung/Surabaya juga `consistent`).

### Babak 2 — Keamanan pangan (2 menit)

Rute klik: **Keamanan Pangan**.

1. Tunjuk tile **batch gagal uji**: beras Jakarta **800 kg**, suhu puncak
   **9,5 °C**, 8 titik log, durasi di atas ambang → `fail`, **tidak boleh
   dialokasikan**. Ini yang membuat rekomendasi tidak menyarankan batch itu.
2. Tunjuk **karantina**: beras Jakarta **540 kg**, alasan "kemasan penyok pada
   3 dus". Aksi: **Lepas** (alasan wajib) → status `quarantined` → `released`.
3. Angka yang bergerak: jumlah batch karantina −1, kg "tidak boleh
   dialokasikan" turun 540 kg, dan batch kembali jadi kandidat alokasi.

Kalimat: "Karantina bukan status kosmetik — batch keluar dari kandidat alokasi
sampai ada manusia yang memutuskan, dan alasannya masuk evidence ledger."

### Babak 3 — Penerimaan barang menggerakkan pasokan (1,5 menit)

Rute klik: **Keamanan Pangan** → panel **Penerimaan menunggu** (2 baris:
ayam 90 kg, beras 300 kg, Jakarta).

1. Setujui penerimaan **ayam 90 kg**.
2. Buka **Overview** → komoditas **ayam** → Jakarta.

Angka yang bergerak:

| Momen | Sebelum | Sesudah |
|---|---|---|
| Status penerimaan | `menunggu` | `disetujui` |
| `supply_records` | — | +1 baris (90 kg) |
| Pasokan ayam Jakarta | 200 kg | **290 kg** |
| Selisih ayam Jakarta | −15 kg (shortage) | **+75 kg (surplus)** |

Kalimat: "Persetujuan penerimaan menulis satu baris stok. Overview membaca stok
terbaru — jadi angka pasokan berubah karena datanya berubah, bukan animasi."

Catatan: penerimaan beras 300 kg sengaja **dibiarkan** untuk babak tanya-jawab;
jangan disetujui lebih dulu kalau ingin mendemokan sekali lagi.

### Babak 4 — Pemasok berisiko (1,5 menit)

Rute klik: **Pemasok**.

1. Tunjuk **1 aktif**: CV Ambarawa Telur Utama — "dua kiriman telur di atas
   ambang suhu; HACCP belum diperbarui".
2. Tunjuk **1 usulan**: CV Ayam Kampung Cugenang — "kemasan retak; menunggu
   klarifikasi". Status `proposed` → setelah disetujui dua peran + eksekusi
   menjadi `active`, dan pemasok itu berhenti muncul di kandidat pengadaan
   lokasi tersebut.
3. Sebutkan jalur pemulihan: **Pulihkan** (`/supplier-exclusions/{id}/restore`)
   mengembalikan pemasok ke kandidat — eksklusi bukan hukuman permanen.

**Peringatan jujur**: usulan **baru** yang dibuat saat demo akan bertanda
verifier `unavailable` bila runtime agent tidak terjangkau, dan persetujuan
ditolak (409). Untuk demo, pakai usulan yang **sudah ada** (sudah
`consistent`). Jangan membuat usulan baru di panggung.

### Babak 5 — Surplus lintas lokasi (1,5 menit)

Rute klik: **Surplus & Limbah** → komoditas **wortel**.

Angka:

| Metrik | Nilai |
|---|---|
| Lokasi surplus | 2 (`667 kg`) |
| Lokasi kekurangan | 8 (`286 kg`) |
| Dapat dialokasikan | `208 kg` |
| Pasangan teratas | Cianjur → Bogor, **208 kg**, 44 km |
| Harga | Rp2.150/kg → nilai Rp4.472.000 |
| Biaya angkut | Rp152.746 (**3,4%** dari nilai) |

Kalimat: "Sistem memilih pasangan ini karena biaya angkutnya 3,4% — di bawah
ambang 10% — dan stoknya benar-benar ada, bukan proyeksi."

### Babak 6 — Bukti & KPI (1 menit)

1. **Agent Log**: 82 trace, filter per keputusan → rantai penalaran agent.
2. **KPI & Kualitas Agen**: 7 metrik tersedia (angka §0).
3. **Ledger**: `valid: true`, `blocks: 62` (setelah babak 1), `linked_ratio:
   1.0`, 0 blok yatim — sebutkan head hash berubah setiap aksi.

Kalimat penutup: "Yang kami jual bukan dashboard: keputusan yang bisa
dipertanggungjawabkan. Angka, bukti, dan rantai hash-nya konsisten."

---

## 3. Reset setelah demo

Data demo **tidak** dihapus oleh "Akhiri sesi" (baris template sengaja tidak
distempel). Sesi berikutnya membangun ulang dari nol. Dua cara:

| Cara | Klik / perintah | Waktu | Kapan dipakai |
|---|---|---|---|
| A. Sesi masih berjalan | Demo Control → **Bangun ulang data** → **Ya, bangun ulang** | ±70 dtk | Geladi berulang tanpa menutup sesi |
| B. Sesi sudah ditutup | Demo Control → **Siapkan data demo** | ±68 dtk | Mulai sesi baru dari nol |
| C. Tanpa UI | `docker exec mealchain-backend python -m app.seed.demo_template` | ±70 dtk | Mesin demo tanpa operator |

Isi tombol A sama dengan perintah C: baris operasional di-purge lalu template
disemai ulang; jendela sesi **tidak** disentuh. Tombol ini hanya muncul saat sesi
aktif, hanya untuk kepala SPPG, dan permintaan kedua saat proses berjalan
dijawab 409 (tidak diantrikan).

Verifikasi cepat setelah reset:

```bash
docker exec mealchain-postgres psql -U mealchain -d mealchain -c "
select (select count(*) from batches) batch,
       (select count(*) from decisions) keputusan,
       (select count(*) from ledger_blocks) ledger,
       (select count(*) from sap_mock_purchase_orders) po;"
# harapan: 120 | 35 | 72 | 16
```

Rollback penuh (bila eksperimen merusak data referensi):

```bash
docker exec -i mealchain-postgres pg_restore -U mealchain -d mealchain \
  --clean --if-exists < data/backups/mealchain-pra-demo-2026-10-21.dump
```

### 3a. Yang selamat dari restart (diukur 21 Okt 2026)

| Kejadian | Sebelum perbaikan | Sesudah perbaikan |
|---|---|---|
| `docker restart mealchain-backend` tanpa sesi | 120 batch → **0** | 120 batch → **120** |
| `docker restart` saat sesi berjalan | data utuh | data utuh |
| "Akhiri sesi" lalu restart | data terhapus | data utuh (UI tetap kosong) |

Sebabnya: boot backend memanggil pembersihan menyeluruh setiap kali tidak ada
sesi aktif, sehingga setiap `uvicorn --reload` saat menyunting kode memusnahkan
template. Sekarang boot hanya menghapus baris **ber-stempel** milik sesi; baris
template (tidak berstempel) dibiarkan, dan tampilan tetap kosong tanpa sesi
karena UI menyembunyikan data.

Konsekuensi yang perlu diingat saat menguji: suite backend menguji **keadaan data
demo hari ini**. Kalau DB baru di-seed kanonik (`--reference-time 2026-10-08`),
12 tes berbasis tanggal gagal karena memang menanyakan "hari ini" — itu keadaan
data, bukan regresi kode. Jalankan suite setelah template dibangun (120 batch).


---

## 4. Di mana setiap kasus tinggal

| Tab | Isi yang dijamin ada |
|---|---|
| Overview | 10 lokasi, 4 komoditas, gap per lokasi, notifikasi, peta + truk |
| Recommendations | 10 keputusan siap approve (3 kota × regional_balance + 2 safety_disruption, Jakarta + supplier_exclusion) |
| Decision & Evidence | bukti per keputusan: 29 baris bukti (SAP PO + inspeksi manusia), 8 approval |
| Keamanan Pangan | 1 gagal uji, 1 karantina, 2 penerimaan menunggu, 14 `needs_verification` |
| Surplus & Limbah | 2 surplus / 8 shortage wortel; 1 pasangan 208 kg; 22 disposal event |
| Pemasok | 60 pemasok; 1 eksklusi aktif, 1 usulan; 35 hygiene, 17 HACCP, 8 tanpa sertifikat |
| Agent Log | 82 trace |
| KPI & Kualitas Agen | 7 metrik tersedia 30 hari terakhir |
| Demo Control | Siapkan data, Akhiri sesi, Segarkan ke hari ini, purge |

---

## 5. Risiko yang sudah diketahui (sebutkan, jangan sembunyikan)

1. **Verifier bisa lambat, bukan mati.** Diukur 21 Okt 2026: chain AgentCore
   menjawab ~6 detik pada percobaan probe. Tetapi rantai fallback bisa memakan
   puluhan detik, dan satu percobaan bisa gagal karena backend sedang reload.
   Mitigasi: pakai 10 keputusan yang sudah `consistent`; kalau harus memverifikasi
   usulan baru, lakukan sebelum tampil, bukan di panggung.
2. **`Siapkan data demo` 68 detik** — lakukan sebelum juri masuk. Kalau
   terpaksa di panggung, isi dengan narasi arsitektur.
3. **Rute OSRM butuh internet**; tanpa internet, garis/truk tidak muncul
   (batch & angka tetap benar).
4. **Tunnel Cloudflare ephemeral** untuk AgentCore — mati saat mesin tidur.
   Demo juri: pakai named tunnel atau `MULTI_AGENT_REVIEW=false`.
5. **Ledger lama** pernah 570 blok yatim; template sekarang membangun ulang
   rantai dari keputusan yang ada (72 blok, 0 yatim). Jangan `DELETE` manual
   tanpa membangun ulang.

## Jakarta saja: dua contoh per kasus, tiga kiriman per komoditas

Demo dijalankan sebagai SPPG **Jakarta**; Bandung/Surabaya sengaja tidak digandakan.

- Tiap kasus punya **2 contoh hidup** (8 kartu): gangguan-logistik 2 (600 kg, 400 kg),
  rejection-loop-kuota 2, shortage-darurat 2, supplier-janggal 2 (ditandai verifikator).
  Jejak historis tetap ada: 3 keputusan lama berstatus ditolak.
- Tiap komoditas punya **3 kiriman hidup** (batas min 1 maks 3): beras, wortel, telur, ayam.
  Batch gagal uji tidak dihitung kiriman (masa layaknya dimundurkan) supaya peta tidak
  menampilkan barang yang sudah dibuang.
- Pemasok dipastikan sejenis komoditasnya: sebelumnya batch beras Jakarta terikat ke
  pemasok telur, sehingga peta menampilkan "CV Barokah Telur" mengirim beras.

### Kenapa truk harus "baru berangkat" saat demo

Status perjalanan dihitung dari jam berangkat batch + durasi rute (bukan disimpan sebagai label).
Karena itu, beberapa saat setelah data dibangun, kiriman dari pemasok dekat berubah menjadi "Sudah tiba":
beras dari Cipinang hanya 12 menit, telur dari Bekasi 21 menit, sedangkan wortel dari Subang 94 menit —
itulah sebabnya pada 21 Oktober pukul 10.28 hanya wortel yang tampak di jalan.

Perbaikannya ada di builder: satu kiriman per komoditas dianchor pada 35% perjalanan, sehingga saat data
selesai dibangun tiap komoditas punya truk yang sedang bergerak. Batasnya: beras dan telur tetap tiba
sekitar 10-15 menit kemudian karena rutenya memang pendek. Karena itu tekan **Siapkan data demo** tepat
sebelum juri masuk, bukan sejam sebelumnya.
