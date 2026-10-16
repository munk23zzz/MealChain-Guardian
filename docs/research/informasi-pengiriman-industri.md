# Riset tampilan "Informasi Pengiriman" — pembanding industri

Status: **Riwayat kejadian per kiriman (kesenjangan #12) SUDAH dibangun** — di dalam panel
"Rincian kiriman", terbaru dulu, waktu uji mutu sengaja TIDAK dikarang (model belum
menyimpannya) dan waktu hitung jalur ditaruh sebagai catatan kaki audit. **Arah A ("Kartu
Kiriman") SUDAH dibangun** — Overview + tab Keamanan Pangan
(di Keamanan Pangan ia menggantikan daftar ringkas "Pasokan masuk" supaya tidak ada dua
penyaji angka yang sama). **Arah B ("Papan Kiriman") SUDAH dibangun** di halaman Pemasok:
tabel 10 kolom, satu baris per kiriman, dengan urutan "paling mendesak". Arah C (panel
samping peta) masih usul. Lihat `docs/design.md` bagian "Kontrak kartu Informasi
pengiriman" dan "Papan kiriman (Arah B)".
Disusun 16 Okt 2026 atas permintaan pemilik proyek ("informasi pengirimannya harus
diriset: info apa saja yang diberikan dan UI-nya bagaimana supaya enak dibaca").

Dipakai bersamaan dengan `docs/design.md` (token warna & komponen) — dokumen ini hanya
menambahkan **apa yang perlu ditampilkan** dan **bagaimana bentuknya**, bukan token baru.

---

## 1. Apa yang diriset

Empat keluarga produk, karena MealChain Guardian bukan satu jenis produk saja:

| Keluarga | Contoh yang saya buka | Yang saya ambil |
| --- | --- | --- |
| Visibilitas angkutan perusahaan (control tower) | Oracle OTM *Shipment Visibility* [1], FourKites [5], project44 [6], Shippeo [11] | daftar field wajib, bagan rute, pengecualian |
| Pelacakan pesanan konsumen | Baymard (6 detail wajib) [2], NN/g (16 panduan status tracker) [3] | urutan prioritas informasi, bahasa manusia |
| Aplikasi kurir / last-mile | Gojek Engineering — "Why We Killed the Live Map" [4] | stepper menggantikan peta, warna sebagai makna |
| Rantai dingin & keamanan pangan | project44 cold chain [6], Appogio ColdChain [7], Sensorytics [8], Evigence [10] | suhu, ekskursi, umur simpan tersisa, bukti audit |
| SAP (konteks juri) | SAP Fiori *Track Freight Orders*, *Monitor Shipment Milestones*, POD [9] | istilah & objek: freight order, milestone, POD |

---

## 2. Temuan A — informasi apa saja yang diberikan produk yang sudah matang

Kolom terakhir = keadaan MealChain Guardian sekarang (dibaca dari `GET /supplier-routes`,
`backend/app/core/journey.py`, `backend/app/core/road_route.py`, UI Pemasok & peta).

| # | Informasi | Sumber industri | MealChain sekarang |
| --- | --- | --- | --- |
| 1 | Identitas kiriman (nomor kiriman / batch / freight order) | Oracle shipment ID [1], SAP freight order [9] | ADA (`batch_id`) tetapi tidak ditonjolkan di mana pun |
| 2 | Asal → tujuan dengan nama tempat | Oracle stop location [1] | ADA |
| 3 | Isi muatan: komoditas, berat, jumlah satuan/paket | Baymard #6 "package contents summary" [2], Oracle ship unit & package count [1] | ADA komoditas + kg; jumlah satuan/paket tidak ada di model |
| 4 | Pengangkut + kontak (nama, telepon, SCAC) | Oracle "Service Provider" [1], Baymard #3 "carrier name" [2] | BELUM (tidak ada entitas pengangkut/kendaraan di model) |
| 5 | Jam berangkat aktual | Oracle start time / actual departure [1] | ADA (`batches.dispatched_at`) |
| 6 | Estimasi tiba (ETA) | semua produk [1][4][5] | ADA angkanya (`journey.eta_at`), belum pernah ditulis sebagai kalimat |
| 7 | Status perjalanan yang mudah dibaca | Oracle Status (delayed / on time / early) [1], Gojek 5 realitas [4] | ADA (`state` + `state_label`: belum berangkat / di jalan / sudah tiba / tidak diketahui) — belum jadi stepper |
| 8 | Simpangan terhadap rencana ("terlambat 22 menit") | Oracle Status + warna simpul [1] | BELUM — dan **sengaja**: model kita belum punya waktu tiba yang dijanjikan, jadi angka simpangan apa pun akan karangan |
| 9 | Kemajuan (stop selesai x/y, % rute) | Oracle "Stops Completed" [1], Gojek stepper [4] | ADA hitungannya (`journey.progress` 0..1, `elapsed_min`, `remaining_min`), belum jadi indikator visual |
| 10 | Jarak & waktu tempuh jalur + sumbernya | Oracle "garis antar-stop = jarak + waktu tempuh" [1], SAP stage [9] | ADA dan **lebih kuat dari pembanding**: jarak jalan OSRM, durasi, rasio vs garis lurus, `source`, `fetched_at` |
| 11 | Kualitas data: bedakan "data belum ada" dari "terlambat" | Shippeo Smart Tracking Analyzer [11] | ADA alasannya (`road_missing_reason`) tetapi di UI masih menyatu dengan pesan lain |
| 12 | Riwayat kejadian: terbaru dulu, bertanggal, dengan sebab | Oracle Events (Event Description, Status Code, Location, Date, Reason, Reporting User, Contact) [1], NN/g #11 "tampilkan pembaruan sebelumnya" [3] | BELUM untuk pengiriman (peristiwa keamanan ada, tapi tidak tersambung ke kiriman) |
| 13 | Kondisi muatan: suhu dalam/luar rentang, log ekskursi | project44 cold chain [6], Appogio [7], Sensorytics [8] | SEBAGIAN (status mutu + peristiwa ekskursi termal di tab Keamanan Pangan), belum per-kiriman/per-suhu |
| 14 | Masa layak / umur simpan tersisa, dan "tiba sebelum batas layak?" | Evigence freshness [10], HACCP/FSMA [8] | ADA (`usable_until`, `journey.arrives_before_usable_until`) — belum pernah diterjemahkan jadi kalimat keputusan |
| 15 | Bukti serah terima (POD / tanda tangan / foto) | SAP Proof of Delivery [9] | BELUM |
| 16 | Kapasitas terpakai (%) | Oracle "Weight Utilization" [1] | BELUM (kita punya kg vs kebutuhan, bisa jadi % pemenuhan) |
| 17 | Slot waktu muat/bongkar | SAP Appointment Scheduling [9] | BELUM |
| 18 | Pemberitahuan dorong (push) + tautan langsung ke rinciannya | NN/g #13/#14 [3], Sensorytics [8] | SEBAGIAN (lonceng notifikasi top bar ada) |
| 19 | Ekspor riwayat untuk audit | Appogio (CSV/Excel/PDF) [7], Sensorytics (laporan kepatuhan otomatis) [8] | BELUM |

**Kesimpulan Temuan A.** Bahan mentahnya sudah ada dan sudah bagus (§4) — yang kurang adalah
**penyajian**: sekarang informasi kiriman hidup di tiga tempat yang saling tidak menyapa, yaitu
popup peta (harus diklik), satu kolom teks di tabel Pemasok, dan satu tag kecil di bilah rincian
lapisan. Tujuh dari sembilan angka perjalanan (`progress`, `elapsed_min`, `remaining_min`,
`arrives_before_usable_until`, …) sudah dikirim server tetapi **belum pernah dipakai UI**.

---

## 3. Temuan B — bagaimana UI-nya dibuat enak dibaca

Delapan pola yang berulang di sumber-sumber di atas, beserta alasannya:

1. **Stepper status, bukan sekadar label.** Gojek membuang peta live dan menggantinya dengan
   stepper yang "menjawab tepat di mana pesanan berada", dengan lima keadaan nyata (Packing /
   On the way / Early / On-time / Delayed) [4]. Pola umumnya 4 tahap: Diterima → Di jalan →
   Segera tiba → Tiba. Tahap yang sudah lewat ditandai jelas, tahap aktif disorot [4][3].
2. **Informasi terbaru paling menonjol, sisanya bertanggal.** "Prioritaskan informasi yang
   berkaitan dengan pembaruan terakhir… jangan penuhi tracker dengan informasi tak perlu" dan
   "tampilkan pembaruan sebelumnya lengkap dengan tanggal" [3]. Oracle menaruh kejadian
   terbaru di **baris paling atas** daftar [1].
3. **Progres vertikal untuk riwayat yang panjang.** Untuk banyak pembaruan, bar progres
   vertikal lebih hemat ruang dan lebih baik di layar sempit [3] — cocok untuk panel samping.
4. **ETA dalam bahasa manusia, bukan jargon.** Baymard: sediakan **tanggal tiba** (bukan
   "kecepatan kirim"), boleh berupa rentang, dan perbarui bila muncul sebab keterlambatan [2].
   Gojek menekankan penulisan ulang teks agar berbunyi seperti orang nyata [4].
5. **Warna = makna, dan dituliskan.** Hijau tepat waktu / kuning perhatian / merah terlambat /
   abu belum ada data. Oracle memakai ambang eksplisit: hijau ≤ 30 menit dari rencana, kuning
   30–60, merah > 60, **abu = belum ada kejadian** [1]. Gojek memakai hijau (tepat waktu),
   biru (hujan), oranye (permintaan maaf halus saat terlambat) [4]. Warna tidak boleh jadi
   satu-satunya pembeda — tetap ada label teks.
6. **Bagan rute yang melampaui peta.** Oracle menggambarnya sebagai deretan lingkaran stop:
   label di atasnya berisi nomor stop, lokasi, kota, waktu tiba (aktual → estimasi → rencana
   sebagai cadangan), warna lingkaran mengikuti simpangan, garis antar-stop memuat **jarak dan
   waktu tempuh**, garis putus-putus = belum ditempuh, dan kejadian ditandai lingkaran kecil
   berisi jumlah kejadian dengan panah hijau untuk kejadian terakhir [1]. Ini pola "peta
   skematik" yang terbaca di kartu yang sempit — tidak mungkin dilakukan peta geografis.
7. **Peta = konteks, bukan satu-satunya sumber.** Pelajaran Gojek: peta live yang dianggap
   wajib justru diganti karena lebih lambat dibaca [4]. Untuk MealChain artinya: peta tetap ada,
   tapi semua angka penting harus hidup **tanpa** perlu mengklik peta.
8. **Sertakan jalur tindakan di dekat yang bermasalah.** Oracle menyediakan Refresh + panel
   kontrol [1]; SAP menyediakan kolaborasi pengangkut & penjadwalan dok [9]; NN/g menuntut
   pembaruan yang bisa dikendalikan pengguna (frekuensi, kanal, berhenti) [3]. Angka merah
   tanpa satu tindakan apa pun hanya membuat panik.

Hal yang **tidak** perlu ditiru: jumlah field Oracle yang mencapai puluhan (declared value,
user defined image 1–5, dsb.) — itu untuk operator logistik yang bekerja 8 jam di layar itu.
MealChain menampilkan 5–8 angka kunci, sisanya di balik "Rincian".

---

## 4. Bahan yang SUDAH kita punya (jangan dikarang lagi)

`GET /supplier-routes` per baris (backend `road_route.py` + `journey.py`):

```
batch_id, supplier_id, supplier_name
origin {latitude, longitude, name}, destination_id, destination_name, destination {…}
commodity, quantity_kg
harvested_at, usable_until          safety_status ("fail" = gagal uji)
straight_km, route_key
road {distance_km, duration_min, ratio_vs_straight, geometry, source, fetched_at}  |  null
road_missing_reason                 (alasan jujur bila geometri belum ada)
journey {
  dispatched_at, eta_at, state, state_label,
  travel_min, travel_source, elapsed_min, remaining_min, progress,
  usable_until, arrives_before_usable_until
}
```

Empat keadaan `state` sudah bertingkat bahasa Indonesia: `belum_berangkat` / `di_jalan` /
`sudah_tiba` / `tidak_diketahui` — persis pola stepper Gojek, hanya belum digambar.

---

## 5. Kesenjangan yang layak ditutup (urutan usul)

1. **Kartu kiriman** yang memuat semua angka perjalanan sekaligus (lihat Arah A) — menutup #6, #7, #9, #10, #14.
2. **Stepper 4 tahap** di kartu itu, tahap aktif disorot, warna dari token `docs/design.md`.
3. **Pembeda jujur "data jalur belum disinkronkan" ≠ "terlambat"** (#11) — cukup chip netral + satu kalimat sebab.
4. **Riwayat kejadian per kiriman** (#12): panen → berangkat → uji mutu → tiba, terbaru dulu, bertanggal. Menyambungkan peristiwa keamanan yang sudah ada ke kirimannya.
5. **Papan kiriman** (Arah B) sebagai pengganti kolom teks "Jalur kirim" di tabel Pemasok.
6. Kapasitas/kontak/POD/slot dok (#4, #15, #16, #17) — **butuh field baru di backend**; jangan dipalsukan. Usul: catat sebagai backlog, bukan dikerjakan sekarang.

---

## 6. Tiga arah tampilan (pilih satu, lalu saya bangun mockupnya)

**Arah A — "Kartu Kiriman" (usulan utama).**
Kartu selebar kolom, isi dari atas ke bawah: baris judul `Pemasok → SPPG` + pil status ramping
(`Di jalan · ± 38 mnt lagi`); stepper 4 tahap; satu baris angka kunci `14,2 km jalan · 22 mnt ·
800 kg telur`; dua baris kalimat keputusan ("Tiba ± 14:20, sebelum batas layak 18:00" atau
"Jalur jalan belum disinkronkan — jarak belum bisa dipastikan"); rincian di balik toggle
(jarak lurus & rasio, sumber OSRM, batch, masa layak). Menutup #6,#7,#9,#10,#11,#14 tanpa field baru.
*Paling sesuai arahan pemilik di Tahap 1 (kartu rapi, tidak kosong) dan langsung terpakai di Overview, Keamanan Pangan, dan tab Pemasok.*

**Arah B — "Papan Kiriman".**
Tabel semua kiriman: Pemasok · Tujuan · Muatan (kg + komoditas) · Jalur (km jalan vs lurus) ·
Berangkat · ETA · Sisa · Masa layak · Mutu · Keadaan. Menggantikan kolom "Jalur kirim" yang
sekarang hanya satu kalimat panjang; ada pengurutan "paling mendesak" (sisa waktu vs batas
layak). Cocok untuk peran Pemasok/Auditor; butuh kolom lebih banyak → lebar meja jadi soal di 375px.

**Arah C — "Panel samping peta".**
Pilih jalur di peta → panel kanan berisi stepper + rincian + riwayat; garis jalur disorot,
segmen yang belum ditempuh digambar putus-putus (pola Oracle [1]). Paling mirip aplikasi
pembanding (Uber/Terminal49), tapi paling mahal: peta kita MapLibre dengan legenda lipat, dan
panel samping menyita lebar kanvas yang sudah sempit.

**Rekomendasi saya: Arah A dulu** (paling banyak menutup kesenjangan dengan nol field baru),
**lalu Arah B** sebagai daftar di bawah peta / isi tab Pemasok. Arah C disimpan sebagai perilaku
"klik jalur di peta → kartu A terbuka di panel".

---

## 7. Aturan yang dipegang (dari repo, bukan dari riset)

- **Tidak ada angka karangan.** Kalau `eta_at` atau geometri belum ada, UI menulis sebabnya
  (`road_missing_reason`), bukan "0 km" atau "terlambat".
- **"Belum ada data" ≠ "terlambat"** — Shippeo pun memisahkan keduanya [11]; di kita warna
  netral, bukan merah.
- **Lantai tipografi 12px** dan token warna tetap dari `docs/design.md`.
- **Bentuk mengikuti isi** — komentar yang sudah dipakai di `globals.css`: badge mengikuti
  panjang label; tinggi grafik mengikuti jumlah lokasi (`--chart-h`). Kartu kiriman harus ikut
  aturan yang sama: tinggi mengikuti berapa banyak keadaan nyata yang dimiliki kiriman itu.

---

## 8. Sumber

1. Oracle OTM — *Shipment Visibility* (field + bagan Route and Status) — https://docs.oracle.com/en/cloud/saas/transportation/26b/otmol/planning/shipment_manager/shipment_visibility.htm
2. Baymard — *Always Provide 6 Key Order-Tracking Details* — https://baymard.com/research-articles/integrate-tracking-info
3. NN/g — *Status Trackers and Progress Updates: 16 Design Guidelines* — https://www.nngroup.com/articles/status-tracker-progress-update/
4. Gojek Engineering — *Why We Killed the Live Map* — https://medium.com/gojekengineering/why-we-killed-the-live-map-using-motion-to-cure-post-booking-anxiety-ea479b00884e
5. FourKites — *Network Visibility* (deck) — https://transportation.northwestern.edu/docs/2022/20221116_fourkites-visibilityworkshop.pdf
6. project44 — cold chain: ambang suhu per kiriman + peringatan — https://www.project44.com/press-releases/project44-expands-supply-chain-visibility-leadership-in-europe-with-new-technologies/
7. Appogio ColdChain — ambang per alat, log ekskursi, ekspor audit — https://appogio.com/en/apps/coldchain
8. Sensorytics — pemantauan suhu, peringatan multi-kanal, laporan kepatuhan — https://sensorytics.com/solutions/cold-chain-monitoring
9. SAP Community — Fiori *Track Freight Orders*, *Monitor Shipment Milestones*, POD, Appointment Scheduling — https://community.sap.com/t5/supply-chain-management-blog-posts-by-members/reimagining-logistics-for-the-cloud-era-inside-sap-logistics-management/ba-p/14253026
10. Evigence — umur simpan tersisa (freshness) — https://cdn.prod.website-files.com/65141441447f03621fd1d28d/663127ae9089a717bb5ba844_Cold_Chain_8.5x11inc_New%20(1).pdf
11. Perbandingan project44 / FourKites / Shippeo (ETA perhentian, klasifikasi akar penyebab, kualitas data) — https://aipicksy.com/compare/ai-shipment-delay-prediction
