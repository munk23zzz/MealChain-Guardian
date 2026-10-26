# Alur demo juri — MealChain Guardian

Dokumen kerja untuk sesi demo 11–14 menit. Angka di bawah diambil dari
**`docs/state-snapshot.md`** (dihasilkan `scripts/snapshot_state.py`, baca-saja) —
snapshot terakhir **26 Oktober 2026 19.29 WIB**, diambil sesudah rebuild kanonik
(48 keputusan / 125 batch / 1.598 blok). Jam tepatnya di kepala `docs/state-snapshot.md`. Kalau angka di sini berbeda
dengan snapshot, snapshot yang berlaku; jangan menyalin angka dari ingatan.

---

## 0. Keadaan awal (yang harus benar sebelum juri masuk)

| Aspek | Nilai |
|---|---|
| Batch | **125** (wortel 32, beras 32, telur 31, ayam 30) |
| Keputusan | **48** — 17 `pending_approval`, 9 `executed`, 10 `rejected`, 5 `verifier_flagged`, 3 `approved`, 2 `proposed`, 2 `review_only` (22 terbuka) |
| Notifikasi (Jakarta) | **14** kartu di jendela 24 jam (10 menunggu tindakan + 2 ditandai verifier + 2 sudah dieksekusi) |
| Pesanan SAP | **20** (15 confirmed, 3 submitted, 2 draft) |
| Blok ledger | **1.598** (1.526 arsip), `valid: true`, 0 yatim — tiap build/rebuild menambah **72 blok** arsip generasi, jadi angka ini mengikuti snapshot, bukan tetap |
| Trace agent | **118** |
| Pemasok / lokasi / komoditas | 61 / 10 / 4 |
| Penerimaan menunggu | **5** — termasuk ayam 90 kg dan ayam 80 kg (Jakarta) |
| Eksklusi pemasok | **2 aktif**, **2 usulan** (salah satunya CV Ayam Kampung Cugenang), 1 ditolak, 1 dicabut |
| Karantina | **2 batch ditahan**: beras Jakarta 540 kg (kemasan penyok) dan telur Makassar 180 kg (suhu); **3 batch gagal uji** total 740 kg (ayam Jakarta 120 kg, wortel Medan 260 kg, telur Surabaya 360 kg) |
| KPI 1 bulan | 7/7 tersedia: kontinuitas 70,52%, food loss 0,07%, imbalance 60,00%, SDC Rp18.472.767,67 (2 sampel), deviasi harga 3,42%, decision time 20 menit, kelengkapan bukti 50,00% |
| KPI hari ini | **6/7** tersedia: food loss 0,59% (3), imbalance 100,00% (2), SDC Rp18.472.767,67 (2), deviasi harga 2,66% (17), decision time 20 menit (2), kelengkapan bukti 66,67% (3); hanya kontinuitas `no_data` |
| Akun demo | 7 akun peran aktif (3 kepala SPPG, 3 ahli gizi, 1 BGN monitor); tabel `users` 8 baris — 1 akun uji dinonaktifkan |

**Prasyarat teknis**: `POST /demo/session/start` = **38–42 detik** terukur pada
mesin demo (menyemai 125 batch + 54 baris `road_routes`; 14 dari 15 kiriman
Jakarta mendapat geometri jalan). Jalankan 5 menit sebelum tampil, jangan saat
juri menunggu. Setelah aktif, sesi berlaku 120 menit dan tidak bisa diperpanjang
melewati plafon itu.

---

## 1. Peta enam babak (11 menit)

| # | Babak | Durasi | Tab | Pesan ke juri |
|---|---|---|---|---|
| 0 | Pembuka angka | 1,5' | Overview | "Ini kondisi pagi ini, bukan mockup." |
| 1 | Agent mengusulkan, manusia memutuskan | 3' | Recommendations → Decision & Evidence | Otonomi terbatas: approve 2 peran + eksekusi |
| 2 | Keamanan pangan | 2' | Keamanan Pangan | Batch gagal diblokir dari alokasi |
| 3 | Penerimaan barang | 1,5' | Keamanan Pangan (penerimaan) | Angka pasokan bergerak karena stok nyata |
| 4 | Pemasok berisiko | 1,5' | Pemasok | Eksklusi ber-scope, ada jalur pemulihan |
| 5 | Surplus lintas lokasi | 1,5' | Surplus & Limbah | 208 kg wortel Cianjur → Bogor, biaya 3,9% |
| 6 | Bukti & KPI | 1' | Agent Log, KPI, Ledger | 1.598 blok, 0 yatim |

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
   - **Notifikasi**: `14` (10 menunggu tindakan + 2 ditandai verifier + 2 sudah dieksekusi).
   - **Peta**: pilih komoditas yang punya kiriman **baru berangkat**. Status
     perjalanan dihitung dari jam berangkat + durasi rute, jadi rute pendek
     (Cipinang 12 menit, Bekasi 21 menit) cepat berubah "Sudah tiba". Pada
     snapshot terakhir 7 kiriman masih di jalan, 6 sudah tiba, 1 belum berangkat
     dan 1 tanpa geometri; untuk
     melihat truk bergerak, siapkan data tepat sebelum tampil. Pemasok aktif
     berdenyut violet `#8B5CF6`.
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
| Pesanan SAP | 20 | **21** |
| Blok ledger | 1.598 | **1.529** (approve kepala, approve gizi, eksekusi) |
| Trace agent | 118 | +1 per aksi |

Kalimat: "Dua peran berbeda harus setuju. Agent tidak boleh mengeksekusi
sendiri — dan setiap persetujuan meninggalkan blok hash yang tidak bisa diubah."

Cadangan: bila tombol eksekusi menolak, keputusan itu butuh bukti tambahan;
pilih kartu `regional_balance` lain (Bandung/Surabaya juga `consistent`).

### Babak 2 — Keamanan pangan (2 menit)

Rute klik: **Keamanan Pangan**.

1. Tunjuk tile **batch gagal uji**: **3 batch, 740 kg** — ayam Jakarta 120 kg,
   wortel Medan 260 kg, telur Surabaya 360 kg. Ketiganya `fail` dan **tidak
   boleh dialokasikan**; itulah sebabnya rekomendasi tidak menyarankan batch itu.
2. Tunjuk **karantina**: **2 batch ditahan** — beras Jakarta **540 kg**
   (alasan "kemasan penyok pada 3 dus") dan telur Makassar **180 kg**
   (suhu keluar rentang aman). Aksi: **Lepas** (alasan wajib) →
   `quarantined` → `released`.
3. Angka yang bergerak: jumlah batch ditahan −1, kg "tidak boleh dialokasikan"
   turun sesuai batch yang dilepas, dan batch kembali jadi kandidat alokasi.

Kalimat: "Karantina bukan status kosmetik — batch keluar dari kandidat alokasi
sampai ada manusia yang memutuskan, dan alasannya masuk evidence ledger."

### Babak 3 — Penerimaan barang menggerakkan pasokan (1,5 menit)

Rute klik: **Keamanan Pangan** → panel **Penerimaan menunggu** (5 baris; dua di
antaranya ayam 90 kg dan ayam 80 kg di Jakarta — keduanya komoditas ayam, jadi
sisa stok ayam yang bergerak).

1. Setujui penerimaan **ayam 90 kg**.
2. Buka **Overview** → komoditas **ayam** → Jakarta.

Angka yang bergerak:

| Momen | Sebelum | Sesudah |
|---|---|---|
| Status penerimaan | `menunggu` | `disetujui` |
| `supply_records` | — | +1 baris (90 kg) |
| Pasokan ayam Jakarta | nilai sebelum (baca layar) | **naik 90 kg** |
| Selisih ayam Jakarta | sebelum (baca layar) | **naik 90 kg** |

Kalimat: "Persetujuan penerimaan menulis satu baris stok. Overview membaca stok
terbaru — jadi angka pasokan berubah karena datanya berubah, bukan animasi."

Catatan: penerimaan ayam 80 kg sengaja **dibiarkan** untuk babak tanya-jawab;
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
| Harga | Rp18.600/kg → nilai Rp3.868.800 |
| Biaya angkut | Rp152.746 (**3,9%** dari nilai) |

Kalimat: "Sistem memilih pasangan ini karena biaya angkutnya 3,9% — di bawah
ambang 10% — dan stoknya benar-benar ada, bukan proyeksi."

### Babak 6 — Bukti & KPI (1 menit)

1. **Agent Log**: 118 trace, filter per keputusan → rantai penalaran agent.
2. **KPI & Kualitas Agen**: 7 metrik 1 bulan, 6 metrik hari ini (angka §0).
3. **Ledger**: `valid: true`, `blocks: 1.598` sebelum babak 1 (naik 3 setelah
   approve + eksekusi), `linked_ratio: 1.0`, 0 blok yatim — sebutkan head hash
   berubah setiap aksi.

Kalimat penutup: "Yang kami jual bukan dashboard: keputusan yang bisa
dipertanggungjawabkan. Angka, bukti, dan rantai hash-nya konsisten."

---

## 3. Reset setelah demo

Data demo **tidak** dihapus oleh "Akhiri sesi" (baris template sengaja tidak
distempel). Sesi berikutnya membangun ulang dari nol. Dua cara:

| Cara | Klik / perintah | Waktu | Kapan dipakai |
|---|---|---|---|
| A. Sesi masih berjalan | Demo Control → **Bangun ulang data** → **Ya, bangun ulang** | 39–42 dtk | Geladi berulang tanpa menutup sesi |
| B. Sesi sudah ditutup | Demo Control → **Siapkan data demo** | 38–42 dtk | Mulai sesi baru dari nol |
| C. Tanpa UI | `docker exec mealchain-backend python -m app.seed.demo_template` | 39–42 dtk | Mesin demo tanpa operator; **tidak** membuka sesi |

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
# harapan: 125 | 48 | 1.598 | 20
```

Rollback penuh (bila eksperimen merusak data referensi):

```bash
docker exec -i mealchain-postgres pg_restore -U mealchain -d mealchain \
  --clean --if-exists < data/backups/mealchain-pra-demo-2026-10-21.dump
```

### 3a. Yang selamat dari restart (diukur 21 Okt 2026)

| Kejadian | Sebelum perbaikan | Sesudah perbaikan |
|---|---|---|
| `docker restart mealchain-backend` tanpa sesi | 125 batch → **0** | 125 batch → **125** |
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
data, bukan regresi kode. Jalankan suite setelah template dibangun (125 batch).


---

## 4. Di mana setiap kasus tinggal

| Tab | Isi yang dijamin ada |
|---|---|
| Overview | 10 lokasi, 4 komoditas, gap per lokasi, notifikasi, peta + truk |
| Recommendations | 22 keputusan terbuka (17 `pending_approval`, 5 `verifier_flagged`); 14 kartu di jendela 24 jam |
| Decision & Evidence | 57 bukti keputusan (SAP PO + inspeksi manusia), 28 baris approval |
| Keamanan Pangan | Jaringan: 3 gagal uji (740 kg), 2 batch ditahan (540 + 180 kg), 5 penerimaan menunggu, 15 `needs_verification` dari 125 batch |
| Surplus & Limbah | 2 surplus / 8 shortage wortel; 1 pasangan 208 kg; 83 disposal event |
| Pemasok | 61 pemasok; 2 eksklusi aktif, 2 usulan, 1 ditolak, 1 dicabut; 36 hygiene, 17 HACCP, 8 tanpa sertifikat |
| Agent Log | 118 jejak |
| KPI & Kualitas Agen | 7 metrik tersedia untuk 1 bulan; 6 metrik tersedia untuk hari ini |
| Demo Control | Siapkan data, Akhiri sesi, Segarkan ke hari ini, purge |

---

## 5. Risiko yang sudah diketahui (sebutkan, jangan sembunyikan)

1. **Verifier bisa lambat, bukan mati.** Diukur 21 Okt 2026: chain AgentCore
   menjawab ~6 detik pada percobaan probe. Tetapi rantai fallback bisa memakan
   puluhan detik, dan satu percobaan bisa gagal karena backend sedang reload.
   Mitigasi: pakai keputusan yang sudah `consistent`; kalau harus memverifikasi
   usulan baru, lakukan sebelum tampil, bukan di panggung.
2. **`Siapkan data demo` 41 detik** — lakukan sebelum juri masuk. Kalau
   terpaksa di panggung, isi dengan narasi arsitektur.
3. **Rute OSRM butuh internet**; tanpa internet, garis/truk tidak muncul
   (batch & angka tetap benar).
4. **Tunnel Cloudflare ephemeral** untuk AgentCore — mati saat mesin tidur.
   Demo juri: pakai named tunnel atau `MULTI_AGENT_REVIEW=false`.
5. **Ledger lama** pernah punya blok yatim; template sekarang membangun ulang
   rantai dari keputusan yang ada (1.598 blok total, 1.526 arsip, 0 yatim).
   Jangan `DELETE` manual tanpa membangun ulang.

## Jakarta saja: dua contoh per kasus, tiga kiriman per komoditas

Demo dijalankan sebagai SPPG **Jakarta**; Bandung/Surabaya sengaja tidak digandakan.

- Tiap kasus punya **2 contoh hidup** (pasangan kartu): gangguan-logistik 2,
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
