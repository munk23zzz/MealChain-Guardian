# design.md — MealChain Guardian

**Prasyarat baca:** `PRD.md`, `Architecture.md`

---

## 1. Prinsip desain

1. **Transparansi di atas segalanya** — user harus selalu bisa lihat KENAPA agent
   merekomendasikan sesuatu. Tidak ada "black box card" tanpa link ke evidence.
2. **Status keamanan tidak boleh ambigu** — PASS/FAIL/NEEDS_VERIFICATION harus punya warna
   dan label yang tidak bisa disalahartikan sekilas.
3. **Approval adalah friksi yang disengaja** — tombol approve aksi berisiko tinggi TIDAK
   boleh satu klik tanpa menampilkan ringkasan evidence dulu.
4. **Role-aware by default** — SPPG Head/Nutritionist tidak boleh melihat/merasa kewalahan dengan data
   lintas-lokasi yang bukan urusannya.

## 2. User roles & flow utama

> **PRD 2.4 alignment (arah Roy 2026-10-09):** persona memakai judul resmi
> PRD §2 — `sppg_head` = **SPPG Operations Lead**, `sppg_nutritionist` =
> **Food Safety Officer**, `bgn_monitor` = **National Inspector**.
> Navigasi konsol = **5 tab** sesuai 7 screen PRD: login terpisah,
> decision detail digabung ke Recommendations, tab = Overview / KPI /
> Recommendations / Agent Log / Demo Control (approver-only).

### Cakupan data per peran (ruling 2026-10-14 — `docs/ruling-2026-10-14-scope-lokasi.md`)

| Peran | Keputusan (`/decisions`) | Peta & angka (`/balance/map`, `/supply`, `/demand`) | Data sumber (`/suppliers`, register pemasok) | Demo Control (`/demo/*`) | Admin (`/admin/*`) |
|---|---|---|---|---|---|
| `sppg_head` | hanya yang **target lokasi = lokasi sendiri** | hanya lokasi sendiri (`/supply/Cianjur/...` → **403**) | boleh dibaca lintas daerah (opsi pemasok tidak dibatasi wilayah pengguna) | penuh (kecuali yang destruktif butuh 2 langkah) | 403 |
| `sppg_nutritionist` | idem | idem | idem | penuh | 403 |
| `bgn_monitor` | semua lokasi | semua lokasi | idem | **403** (read-only demo, tidak boleh mengubah/mengisi data) | boleh dibaca |

Artinya angka yang sama bisa sah berbeda antar peran di layar — bukan bug; yang salah
adalah menampilkan angka lintas daerah ke peran SPPG. Setiap penolakan cakupan dijawab
`403` oleh API (bukan daftar kosong), supaya UI bisa menampilkan alasan, bukan "tidak ada data".

### Flow: SPPG Staff
Login → Dashboard (lokasi sendiri) → lihat status supply/demand → notifikasi ada rekomendasi
baru → buka Decision Detail → review evidence → Approve/Reject → lihat status di feed berubah

### Flow: Dinas/BGN Admin
Login → Dashboard (semua lokasi, peta) → lihat KPI global → drill-down ke lokasi bermasalah →
lihat Agent Activity Log kalau ada anomali → approve aksi lintas-wilayah → export evidence
untuk audit

### Flow: Demo ke juri (guided)
Login sebagai Dinas Admin → Dashboard (peta 10 lokasi) → trigger Event 1/2/3 (tombol demo
khusus, hanya ada di environment demo) → Agent Activity Log ter-update real-time → Decision
Detail muncul dengan evidence → Approve → status di peta berubah

## 3. Screen inventory

| # | Screen (PRD 2.4) | Realita konsol | Prioritas |
|---|---|---|---|
| 1 | Login (`/login`) | Login + quick-access akun demo ✓ | Wajib |
| — | *(di luar PRD)* **Hari Ini** | Tab **Hari Ini** (permintaan Roy 2026-10-11) — rekap operasional hari berjalan dari API: keputusan menunggu tindakan + sisa waktu, batch kedaluwarsa/<48 jam, lokasi shortage, KPI 24 jam, status rantai audit ✓ | Tambahan demo |
| 2 | Overview Map (`/overview`) | Tab **Overview** — MapLibre + chart stok + tabel node ✓ | Wajib |
| 3 | Recommendation Feed (`/recommendations`) | Tab **Recommendations** + Decision Detail digabung ✓ | Wajib |
| 4 | Decision Detail & Evidence | Tab **Decision & Evidence** (Langkah 4, permintaan Roy 2026-10-11) — halaman tersendiri seperti sidebar acuan: ringkasan + identitas/tenggat, biaya, keamanan & pemasok, governance, riwayat iterasi, bukti tersimpan/ledger/ttd; klik kartu di feed membawa ke sini ✓ | Wajib |
| — | *(acuan app)* **Keamanan Pangan** | Tab **Keamanan Pangan** (Langkah 5, permintaan Roy 2026-10-11) — halaman `/compliance` di acuan: ringkasan pengawasan batch (aman/gagal uji/perlu verifikasi), blokir batch gagal, daftar batch perlu segera dipakai, tabel status per batch (status, kesegaran, sisa masa layak) ✓ | Tambahan demo |
| — | *(acuan app)* **Surplus & Limbah** | Tab **Surplus & Limbah** (Langkah 5) — halaman `/surplus` di acuan: neraca surplus/kekurangan komoditas aktif, rencana alokasi surplus→kekurangan (greedy, jarak dari koordinat; sejak 20 Okt 2026 dihitung server lintas lokasi lewat `GET /surplus/allocations` + kolom biaya tetap), keadaan pencatatan limbah ✓ (hanya peran SPPG, seperti acuan) | Tambahan demo |
| — | *(acuan app)* **Pemasok** | Tab **Pemasok** (Langkah 5) — halaman `/suppliers` di acuan: daftar pemasok + keandalan dari keputusan terakhir, register eksklusi, form usul eksklusi ✓ | Tambahan demo |
| 5 | Agent Activity Log (`/agent-log`) | Tab **Agent Log** — trace console + provider panel, pilih decision via dropdown ✓ | Wajib |
| 6 | Approval Modal/Flow | Di dalam Decision Detail ✓ | Wajib |
| 7 | KPI Dashboard (`/kpi`) + *(acuan app)* Kualitas Agen (`/quality`) | Tab **KPI & Kualitas Agen** — **digabung 2026-10-15 atas keputusan pemilik** (dua tab lama "KPI" + "Kualitas Agen" jadi satu, urutan KPI dulu lalu mutu agen). Bagian 1: 7 KPI live jujur dari `/kpi` (strip **Target KPI Demo Day** dihapus hari yang sama). Bagian 2: skor agregat mutu agen (langkah/run, kesesuaian verifikator, tingkat fallback, keputusan diubah manusia, rata-rata durasi) + rincian per run dari jejak agen nyata ✓. Komposisi ada di `components/KpiQualityBoard.tsx`; isi kedua bagian tidak diubah | Wajib |
| 8 | Demo Control Panel (`/demo-control`) | Tab **Demo Control** (approver-only) — **sejak 2026-10-19 tiga blok sederhana** (1) siapkan data demo, (2) jalankan agent: satu tombol, komoditas dari dropdown (nama yang ADA di DB) + SPPG akun sendiri sebagai tujuan; yang dinilai adalah PEMASOK yang sudah memasok SPPG itu (stok batch di SPPG, penawaran harga untuk SPPG, jarak pemasok → SPPG), bukan surplus SPPG lain, (3) bukti agent dibaca ulang dari DB: langkah yang tercatat beserta alatnya, provider yang menjawab, status keputusan, narasi supervisor terlipat. OpsConsole/ChaosPanel (Event 1/2/3) tidak lagi dipasang di tab ini; komponennya tetap ada di repo. ✓ | Wajib (demo) |
| 9 | Settings/Admin | Nice-to-have |

> Penyesuaian dari PRD 2.4 (keputusan Roy): **arsitektur & backend tetap
> mengikuti keputusan terakhir.** Komponen kripto PRD kini diimplementasi
> versi lokal (paket 1–6 disetujui Roy 2026-10-09/10): **P1** Merkle ledger
> append-only di PostgreSQL (tabel `ledger_blocks`, `GET /ledger/verify`)
> menggantikan on-chain; **P2** dossier konten-addressed (`mc1-` SHA-256)
> menggantikan IPFS; **P3** ECDSA secp256k1 signing per approval (kunci di
> `.env` → compose meneruskannya ke kontainer `backend` sebagai `SIGNING_KEY_HEX`;
> tanpa kunci = `unsigned` jujur; per 11 Okt kunci terpasang → ttd aktif
> `state: signed` + `verify: true` dari `GET /decisions/{id}/dossier`);
> **P4** chaos sliders memicu Event 3 via API resmi (safety tetap
> dihitung server); **P5** telemetry banner jujur di login (tanpa klaim
> sertifikasi); **P6** tabel facts menu_plans/delivery_events/
> disposal_events → KPI Meal Continuity & Avoidable Food Loss LIVE.
> Polygon Amoy anchoring asli = bonus opsional (butuh internet stabil).
> Angka KPI PRD tampil hanya sebagai target berlabel eksplisit, KPI live
> tetap jujur dari DB (ruling O-KPI).

### 3.1 Dashboard / Peta 10 Lokasi
- Peta **MapLibre GL** (tile raster OpenStreetMap apa adanya — TERANG, tanpa
  penggelapan; tanpa API key) dengan 10 node; warna pin sesuai status:
  hijau (surplus), merah (shortage), abu (seimbang) + label mono nama/selisih;
  klik pin → popup pasokan/permintaan/gap
- Kotak penjelas peta bernama **"Info map"** (Fase 12, arah pemilik 2026-10-16: *"untuk teks
  legenda map ganti menjadi info map"*) dan **BISA DILIPAT** — yang terlihat di kanvas
  kiri-bawah hanya chip **"Info map"** (terukur 103×24 px). Sebelumnya kotak legenda selalu
  terbuka **300×137 px** dan menutupi Jawa Barat tempat pin SPPG + jalur kiriman berada. Isi
  kotak (status lokasi · jalur kiriman · perjalanan kiriman · pemasok) TIDAK dihapus dari DOM:
  saat tertutup hanya `display: none`, sehingga ia keluar dari pohon aksesibilitas dan tetap
  satu klik lagi untuk dibuka; tombolnya memakai gaya chip yang sama dengan "Rincian lapisan
  peta" (`aria-expanded` + `aria-controls="map-legend-panel"`, chevron CSS diputar 90°).
  **Susunan isinya mengikuti lapisan yang sedang HIDUP** (keputusan yang sama): status lokasi
  selalu, jalur kiriman hanya saat sakelarnya hidup, pemasok hanya saat sakelarnya hidup —
  keterangan warna yang tidak ada di peta adalah informasi palsu. Entri **"Jalur kiriman gagal
  uji"** juga hanya muncul kalau memang ada kiriman bergaris bergagal-uji
  (`routeLegendEntries(rows)`). Makna pin tetap terbaca tanpa membuka kotak karena subjudul
  halaman sudah menulis "hijau surplus, merah shortage, abu seimbang". Kontrol bawaan MapLibre
  tetap: zoom + kompas kanan-atas, atribusi © OpenStreetMap contributors kanan-bawah
- Angka detail per lokasi (pasokan / permintaan / gap) tetap tampil sebagai
  daftar di samping peta + kartu **Telemetri Node** untuk lokasi yang disorot —
  peta bukan satu-satunya sumber angka
- Sidebar: filter komoditas (telur/ayam/beras/wortel), filter status feed
- Untuk SPPG Head/Nutritionist: peta fit ke bounds lokasi-lokasi dari data
  (dropdown cakupan terkunci ke SPPG-nya; koridor tetap terlihat untuk konteks)
- **Zoom milik pengguna tidak disentuh sinkronisasi** (arah Roy 2026-10-11):
  peta dibangun SEKALI, polling `/balance/map` tiap 5 detik hanya memperbarui
  isi penanda (angka/label/posisi/popup). `fitBounds` hanya saat pertama tampil
  atau saat pilihan lokasi di dropdown cakupan BERGANTI (`nextMapFocus`,
  `pinSignatures`/`pinDiff` di `lib/map-console.ts`)
- **Layer pemasok (Fase 2–3 rencana 2026-10-14; jangkauan ditambahkan Fase 7b 2026-10-15):** tombol
  "Tampilkan pemasok (N)" memunculkan pin pemasok dari `GET /suppliers` — warna pin dari
  `reliability_score` (`map-pin-supplier-ok` ≥ ambang, `map-pin-supplier-low` di bawahnya,
  `map-pin-supplier-excluded` untuk pemasok di register eksklusi, `map-pin-supplier-far` untuk
  pemasok **di luar jangkauan** — titik kosong bergaris putus-putus, warna tetap token), label
  (`aria-label`) berbunyi `"<nama> — pemasok <komoditas>, keandalan NN%, hub <kota>, dalam/di luar
  jangkauan (N km)", legenda "Pemasok · Keandalan rendah · Dikecualikan · Di luar jangkauan ·
  Sedang mengirim".
  Pemasok **tanpa koordinat tidak dipin** (tidak ada titik karangan) dan jumlahnya dinyatakan di
  samping tombol.
- **Penanda "sedang mengirim" (revisi 2026-10-20):** pemasok yang punya kiriman **`di_jalan`
  sekarang** (`journey.state === "di_jalan"` dari `GET /supplier-routes`, dihitung di peta)
  digambar sebagai **lingkaran PENUH violet `--status-live`** dengan **satu halo yang melebar
  2,2 dtk** (`@keyframes pin-kirim-halo`) — bukan cincin `--status-safe`. Dua alasan revisi:
  (a) cincin tipis di sekitar garis tepi pin hanya terbaca sebagai border tebal, bukan status;
  (b) kunci `shipping` dari `GET /suppliers` menghitung **semua** kiriman termasuk yang sudah
  tiba, sehingga 6 pemasok menyala saat hanya 2 yang benar-benar di jalan. `--status-live`
  khusus penanda "hidup/bergerak" (juga dipakai puck mobil), bukan nada status — warna pin
  biasa tetap berarti keandalan/jangkauan. `prefers-reduced-motion` mematikan denyut dan
  menyisakan halo diam, jadi statusnya tetap terbaca. Label (`aria-label`) dan popup tetap
  menyebut "sedang mengirim N kiriman"; kiriman yang gagal uji disebut terpisah
  (`safety_fail_count`), tidak disembunyikan di balik kata "sedang mengirim".
- **Garis jalur kiriman (`ship-route`).** Garis putus-putus di peta menandai rute kiriman
  pemasok → tujuan **mengikuti jalan** (geometri OSRM, disimpan di tabel `road_routes`), bukan
  garis lurus. Warna garis memakai token yang sama dengan nada mutu kiriman
  (`--status-safe` / `--status-danger`) supaya satu fakta tidak punya dua bahasa; nilai paint
  WebGL tidak bisa membaca CSS var, jadi `ROUTE_LINE_COLORS` di
  `frontend/lib/supplier-routes.ts` dikunci tes yang **membaca `app/globals.css`** — token
  berubah tanpa menyentuh modul itu akan memerahkan tes.
- **Tiga keadaan garis, satu palet (audit 21 Okt 2026).** Peta menggambar tiga keadaan dengan
  warna yang semuanya berasal dari token status, bukan warna baru:
  *berjalan* = satu keluarga violet dengan ikon truk: bagian yang sudah ditempuh
  `--route-live-strong` `#7C3AED` (kontras 4,97:1 di tile OSM terang), sisa perjalanan
  `--route-live-soft` `#8B5CF6` (3,69:1, lolos ambang grafik 3:1) dibedakan oleh pola putus,
  tebal 5 / 4,5 px dengan alas putih 7,2 px;
  *sudah tiba* = abu netral `--route-arrived` `#475569`, tebal 3,6 px, opasitas 0,75, putus 7/5,
  alas putih 6,5 px; *gagal uji* = `--status-danger` putus.
  Riwayat singkat: versi pertama memakai hijau `--status-safe` + biru `--accent-strong`, lalu
  versi kedua abu 2,5 px opasitas 0,32 — keduanya dinilai pemilik "tidak terlihat" di basemap
  terang. Karena itu warna sekarang dipilih dengan kontras terukur, bukan selera, dan alas putih
  tetap wajib: tanpa ia garis tipis bertabrakan dengan jalan peta. Ikon mobil tetap HANYA untuk
  keadaan berjalan, supaya "ada yang bergerak" tidak pernah salah dibaca.

- **Kontrol layer sejajar, tidak menumpuk.** Sakelar pemasok dan sakelar jalur duduk dalam satu
  wadah `.map-overlay-toggles` (pil putih, `gap: 2px`) — dua kotak yang saling menimpa di pojok kiri
  atas pernah jadi masalah nyata. Sejak revisi 16 Okt (permintaan pemilik: "2 tombol di atas dibuat
  kecil saja") tombolnya 26 px (dari 34), padding 2×8, pil terukur 203×32 px di :3010; **teks yang
  terlihat hanya jumlahnya** ("Pemasok (7)", "Jalur kiriman (1)") — keadaan hidup/mati dibawa
  `aria-pressed` + warna (pola pil komoditas) dan kalimat "Tampilkan/Sembunyikan …" menjadi `title`
  (tooltip), jadi tidak ada informasi yang hilang. Ukuran huruf tetap 12 px (lantai teks data) dan
  target sentuh 44 px tetap berlaku di `(pointer: coarse)`/≤720 px.
- **Rincian lapisan bisa dilipat (revisi 16 Okt).** Di bawah kanvas: `.map-layer-info` = tombol kecil
  "Rincian lapisan peta" (`aria-expanded`/`aria-controls`, chevron CSS diputar 90° saat terbuka) +
  tag angka yang **selalu terlihat** (`supplierReachTag` → "7/9 pemasok dalam 150 km", `routeLayerTag`
  → "1 jalur kiriman · jalur jalan OSRM"), lalu panel lipat berisi kalimat jujurnya
  (`supplierReachNote`, ringkasan OSRM). Panel TIDAK menghapus isi dari DOM — hanya dilipat
  (tinggi `0fr` + `visibility: hidden` sehingga hilang dari pohon aksesibilitas), jadi angka
  "N di luar jangkauan tidak dipasang di peta" tetap bisa diperiksa: penyaringan tidak pernah jadi
  penyembunyian. Peringatan "perbesar peta" (`.map-layer-hint`) sengaja DI LUAR panel supaya muncul
  seketika saat lapisan dinyalakan pada zoom jauh.
- **Legenda jalur memakai contoh garis, bukan kotak warna**, karena yang digambar peta memang
  garis: "Jalur kiriman (jalan)" / "Jalur kiriman gagal uji" (yang kedua hanya muncul bila ada
  kiriman bergaris bergagal-uji). Catatan "jalur jalan dari OSRM
  (diambil saat sinkronisasi, bukan saat peta dibuka)" ditulis di tag/panel rincian lapisan
  (`.map-layer-info`, sejak revisi 16 Okt — dulu di legenda) supaya angka jarak
  tidak pernah dibaca sebagai hitungan aplikasi sendiri.
- **Perjalanan kiriman + waktu estimasi sampai (Fase 12, arah pemilik 2026-10-16: "ketika
  mengaktifkan jalur kiriman tampilkan juga waktu estimasi sampai … pastikan sinkron dengan
  database").** Saat sakelar jalur kiriman hidup: (a) tag bilah rincian menyebut
  `2 jalur kiriman · 1 di jalan · tiba terdekat ± 22.54`; (b) kotak "Info map" memuat blok
  **Perjalanan kiriman** (maks 3 baris + "+N kiriman lain") seperti
  `Jakarta · di jalan · tiba ± 22.54 (24 menit lagi)`; (c) popup garis menambah baris jam
  berangkat, estimasi tiba, dan perbandingan dengan batas layak. **Tidak ada jam tiba yang
  dihitung di peramban**: angkanya datang utuh dari `journey` di `GET /supplier-routes`, yang
  dihitung server dari `batches.dispatched_at` (DB) + `road_routes.duration_s` (OSRM). Keadaan
  yang mungkin disebut apa adanya: `di_jalan`, `sudah_tiba`, `belum_berangkat` (jam berangkat
  NULL — estimasi TIDAK dibuat), dan `tidak_diketahui` (sudah berangkat tapi jalur jalannya
  belum tersinkron → tidak diklaim tiba maupun di jalan).
- **Popup klik pada garis** menampilkan pemasok → tujuan, komoditas & berat, jalur jalan (jarak
  + durasi dari sumbernya), perjalanan (jam berangkat, estimasi tiba, sisa waktu), masa layak,
  dan status keamanan kiriman — semua dari data API, bukan dihitung ulang di peramban.
  **Tiga hal DIBUANG atas permintaan pemilik 2026-10-16** (*"Jarak lurus: 78,4 km, Tiba sebelum
  batas layak (25 Okt 2026) dan ini Jalur jalan 1,41× jarak lurus (jalan berkelok, bukan garis
  lurus) hapus saja"*): baris "Jarak lurus: …", baris rasio `1,41×`, dan kalimat penghibur
  "Tiba sebelum batas layak (…)". `straightKm`/`ratioVsStraight` tetap dikirim server (dipakai
  kolom tabel lain + jejak audit) dan tanggal layak pakai tetap tertulis sekali di baris
  "Layak dipakai s/d …" — jadi menghapusnya tidak mengurangi fakta, hanya menghilangkan derajat
  presisi yang tidak dipakai saat membaca peta. Peringatan sebaliknya
  ("Estimasi tiba melewati batas layak pakai") TETAP ada: itu menandai masalah nyata.
- **Kolom "Jalur kirim" di tabel Pemasok** menjawab "pemasok ini mengirim lewat jalur mana?"
  tanpa membuka peta: `→ Cianjur · 3,2 km jalan · +3 tujuan`, dengan daftar lengkap tujuan di
  atribut `title`. Tiga aturan yang dikunci tes: baris utama = jalur **terpendek** yang
  geometrinya sudah ada; **tanpa lencana warna** (lencana sudah milik kolom Status — dua makna
  tidak boleh tampil dengan bahasa visual yang sama); dan **jarak lurus tidak diulang** di sini
  (kolom Jarak sudah memuatnya). Empat keadaan dibedakan tegas: `—` (tidak punya kiriman
  aktif), `…` (data jalur belum dimuat), `belum disinkronkan`, dan `jalur tidak tersedia`.
- **Ambang jangkauan (relevansi, bukan scope).** Peta Overview meminta
  `GET /suppliers?commodity=…&max_distance_km=150` bila perannya SPPG
  (`supplierReachKmForRole`; `bgn_monitor` tanpa ambang = nasional). Rujukan jarak datang dari
  server (`distance_reference`); UI tidak menghitung jarak sendiri. Di samping tombol layer ada
  kalimat status dari `supplierReachNote`, mis. "4 dari 6 pemasok dalam jangkauan 150 km dari
  Jakarta · 2 di luar jangkauan tidak dipasang di peta" — angka "2" berasal dari
  `reach.excluded_out_of_reach` server, dan untuk peran SPPG **jarak yang tidak diketahui tidak
  pernah dihitung sebagai dekat**. Ruling cakupan 2026-10-14 §4 tetap: semua peran boleh membaca
  pemasok lintas lokasi; yang dibatasi hanya apa yang ditonjolkan.
- Catatan data apa adanya: filter komoditas peta memuat 4 pilihan (telur/ayam/beras/wortel)
  sedangkan DB demo hanya punya `ayam`, `telur`, `wortel`. Pilihan `beras` dijawab API
  dengan `404` dan UI menampilkan galat + tombol "Coba lagi" — disengaja (bukan angka
  kosong yang menyamar sebagai data), dan akan rapi setelah komoditas diselaraskan.

### 3.2 Recommendation Feed
- List card, sorted by urgency (safety issue > regional imbalance > price anomaly)
- Tiap card: judul singkat ("Alokasi Cianjur→Jakarta direkomendasikan"), badge status
  (Pending Approval/Approved/Rejected/Executed), waktu, tombol "Lihat Detail"
- Empty state: "Belum ada rekomendasi aktif" (bukan kosong tanpa penjelasan)

### 3.3 Decision Detail & Evidence (tab tersendiri)
- Tab **Decision & Evidence** = halaman bukti satu keputusan (sidebar acuan halaman 3).
  Feed Recommendations hanya memuat daftar; klik kartu → pilih keputusan + buka
  halaman ini (urutan sidebar acuan: Overview → Recommendation Feed → Decision &
  Evidence → Agent Activity → KPI → Demo Control).
- Isi halaman (semua dari API, nilai tak diketahui = "—"):
  1. **Ringkasan keputusan** — kartu keputusan + identitas/tenggat
     (`Rute`, `Komoditas`, `Jumlah`, `Iterasi`, `Menggantikan`, `Diusulkan oleh`,
     `Tenggat` dalam sisa waktu manusiawi) dari `/decisions/{id}` + `/approval-summary`
  2. **Biaya** — harga beli, logistik, biaya aman terkirim, catatan (`cost_breakdown`).
     Sejak Fase 7d (2026-10-15) biaya angkut dipecah dua baris **hanya bila
     backend mengirim pecahannya**: `Angkut pemasok → SPPG` (kaki pertama, hint
     "N km dari pemasok" atau alasannya bila jarak tidak diketahui) dan
     `Angkut antar SPPG` (linehaul); baris `Logistik` tetap total angkut.
  3. **Keamanan & pemasok** — status keamanan terburuk, batch diperiksa, diblokir,
     verifikator, nomor material, target eksekusi, pemasok + skor keandalan
  4. **Governance & persetujuan** — jumlah/syarat persetujuan, boleh disetujui/dieksekusi,
     alasan tertahan, peran penyetuju + `DecisionActions` (alur approve/verify/execute nyata)
  5. **Riwayat iterasi** — `DecisionChain` (rejection loop v1→v2→v3 dengan alasannya)
  6. **Bukti tersimpan & integritas** — `IntegrityPanel`: daftar `evidence[]` dari
     `/decisions/{id}/compliance`, rantai Merkle (`/ledger/verify`), alamat konten
     dossier + status tanda tangan ECDSA, ekspor JSON/CSV
  7. **Form supplier-exclusion** muncul bila keputusan administratif supplier
- Tanpa keputusan dipilih: keadaan kosong yang menjelaskan, plus saran dari
  keputusan yang benar-benar menunggu tindakan (bisa juga memilih lewat dropdown).
- Panel integritas **pindah** dari tab Agent Log ke halaman ini (jejak reasoning
  agen vs bukti keputusan = dua halaman berbeda, mengikuti sidebar acuan).
- Logika murninya di `frontend/lib/evidence.ts` (`decisionFacts`, `costFacts`,
  `safetyFacts`, `supplierFact`, `approvalFacts`, `dossierMeta`, `evidenceTally`).

### 3.4 Agent Activity Log
- Timeline vertikal: DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE → ACT → LEARN.
  Urutan itu *kemungkinan*, bukan janji: `ACT` hanya tercatat saat aksi benar-benar
  dieksekusi (`executed`), dan `LEARN` hanya tercatat oleh loop penolakan
  (`POST /actions/repropose`) setelah keputusan ditolak lalu diajukan ulang.
  Pipeline yang baru dijalankan berhenti di `DECIDE`/`SUPERVISE` (status `proposed`).
- Tiap step: tool yang dipanggil (ditulis dengan sebutan manusia), output ringkas
  (`output_summary`) apa adanya, fakta turunan (nomor PO, model penyedia), timestamp, durasi.
- Data ditarik dari AgentCore Observability trace (bukan log buatan sendiri)
- Bisa filter per decision_id
- Ini screen yang PALING PENTING untuk demo juri — harus terlihat jelas dan real-time

### 3.5 Approval Modal
- Muncul saat klik Approve — WAJIB tampilkan ringkasan: apa yang akan dieksekusi, ke SAP mana,
  evidence utama, hasil audit Verifier
- Tidak ada "approve all" massal untuk MVP — satu per satu, disengaja

### 3.6 KPI Dashboard
- 7 KPI card (lihat `Skill.md` untuk definisi): Meal Continuity Rate, Avoidable Food Loss,
  Regional Imbalance Resolution Rate, Safe Delivered Cost (rata-rata), Procurement Price
  Deviation, Decision Time, Evidence Completeness
- Tiap card: angka besar + trend kecil (naik/turun vs periode sebelumnya, kalau ada histori)

### 3.7 Hari Ini (di luar PRD — permintaan Roy 2026-10-11)
Tab pertama di rail, dibuka manual (halaman setelah login tetap **Overview**).
Urutannya sengaja dari atas ke bawah — **status → pengecualian → agenda → rincian**:

**Strip ringkasan** (desain ulang 2026-10-17) — lima tile tombol di bawah kepala
halaman: *Menunggu tindakan*, *Batch <48 jam*, *Lokasi shortage*, *KPI terisi*,
*Rantai audit*. Angkanya berasal dari fungsi yang SAMA dengan kartunya (tidak ada
perhitungan kedua), dan mengklik tile menggulir + memfokuskan kartu tujuan
(`#today-action`, `#today-agenda`, `#today-batches`, `#today-shortage`, `#today-kpi`,
`#today-ledger`). Sumber yang gagal ditulis keadaan gagalnya ("tidak terbaca"),
bukan 0. Empat kartu rincian, semuanya dari API, tanpa angka karangan:
1. **Menunggu tindakan** — keputusan berstatus `PENDING_APPROVAL`/`NEEDS_VERIFICATION`/
   `VERIFIER_FLAGGED` dari `/decisions`, urut: yang sudah lewat tenggat dulu (paling baru
   lewat), lalu yang paling dekat jatuh tempo. Sisa waktu dihitung dari jam KLIEN
   (`now` dari pemanggil) supaya tidak ada selisih hidrasi server/klien; sebelum jam
   siap, label ditulis "—". Daftar dipotong 6 baris dan sisanya DINYATAKAN
   ("+N keputusan lain…" + tombol "Lihat semua").
2. **Batch mendekati kedaluwarsa** — `/batches`, dipisah kedaluwarsa vs <48 jam
   (`DUE_SOON_HOURS`), total kg dijumlahkan hanya dari kuantitas yang sah. Batch dengan
   tanggal tak terbaca tidak diklaim kedaluwarsa maupun aman.
3. **Lokasi shortage** — `/balance/map` untuk komoditas aktif, urut kekurangan terbesar.
4. **KPI 24 jam** — `/kpi` (periode 24 jam berakhir sekarang), memakai formatter yang
   SAMA dengan tab KPI; metrik `no_data` ditulis "—". Periode ditulis dari data
   (`kpiPeriodLabel`), bukan ditebak "24 jam terakhir".
5. **Rantai audit** — `/ledger/verify`: status rantai, jumlah blok, 10 karakter pertama
   head hash.
Empat kartu rincian duduk dalam grid **dua kolom** (`.today-detail-grid`; satu kolom
≤1180 px) — tidak lagi bobot 7/5 yang merentangkan satu kartu setinggi tetangganya.

**Agenda harian** (2026-10-17, menggantikan grid bulan besar di kartu) — kepala kartu
memuat **hari terpilih sebagai judul** ("Sabtu, 17 Oktober 2026"), tombol `‹`/`›` yang
bergeser **satu hari** (bukan satu bulan; mati di tepi `RANGE_MIN`/`RANGE_MAX` supaya
tidak menampilkan hari kosong seolah "tidak ada operasi"), pil "Hari ini", dan **ikon
kalender kecil** sebagai pemicu popup pemilih tanggal/bulan/tahun. Grid bulan tidak
lagi dirender di kartu (terukur: 0 elemen `.agenda-cell` di kartu; gridnya hidup hanya
di dalam popup). Info hari terpilih tetap lengkap, dikelompokkan tiga tema —
**Rencana & pasokan**, **Limbah & kedaluwarsa**, **Keputusan agen** — dan hari tanpa
catatan menulis "tidak ada catatan" per baris, bukan menghilang.

Logika murni (tanpa DOM, diuji) ada di `frontend/lib/today.ts` (`summaryTiles`,
`updatedLabel`, `kpiPeriodLabel`, `ledgerSummary`) dan `frontend/lib/agenda.ts`
(`agendaGroups`, `clampDayStep`, `dayOf`); komponennya
`frontend/components/TodayDashboard.tsx`, `TodaySummary.tsx`, `TodayAgendaCalendar.tsx`.
Kelas `.today-*`/`.agenda-*` di `globals.css` memakai token yang sudah ada (tidak ada
token baru).

### 3.8 Halaman sidebar acuan yang disesuaikan (Langkah 5 — permintaan Roy 2026-10-11)

Aplikasi acuan `E:\hackathon\HackathonBil\MealchainGuardian` punya 9 halaman sidebar
(`frontend/lib/nav.ts`); repo ini sudah setara untuk 5 (Hari Ini/Overview/Keputusan/
Decision & Evidence/Agent Log) dan **kurang 4**. Keempatnya dibangun ulang di sini
dengan **data API nyata** — bukan data contoh seperti di acuan:

| Tab baru | Di acuan | Sumber angka di repo ini | Yang TIDAK dipakai dari acuan |
|---|---|---|---|
| Keamanan Pangan | `/compliance` | `GET /batches`: `safety_status`, `freshness_score`, `usable_until`, `quantity_kg` | papan CCP per-alat, bank sampel, jejak lot EPCIS (tidak ada endpoint) |
| Surplus & Limbah | `/surplus` | `GET /balance/map?commodity=…`: `surplus_kg`, `shortage_kg`, `latitude`/`longitude`, `region` | limbah: `GET /waste/summary` → `recorded` / `diverted` / `unassigned` + `partners` (kolom `disposal_events.partner_name`, migrasi 022; "—" hanya bila memang tak ada baris) |
| Pemasok | `/suppliers` | **`GET /suppliers`** (35 pemasok: 14 kanonik + 21 demo — daftar, keandalan, komoditas, kapasitas, jarak/koordinat, status eksklusi) + `GET /supplier-exclusions`; pin di peta (lihat §3.1). Halaman Pemasok: kolom **Jarak** (dari `distance_km` server) + penyaring "Hanya dalam jangkauan" untuk peran SPPG; jarak tanpa rujukan ditulis "—". Kolom **Status** menulis pil ringkas dari kunci `shipping` server bila pemasok itu punya kiriman masih layak (`.shipping-tag`, token ok), pil bahaya terpisah `.shipping-tag-fail` bila ada kiriman gagal uji, "Dikecualikan di …" bila ada eksklusi, selain itu "Aktif"; kartu Ringkasan memuat "Sedang mengirim barang: N dari M". **F12c (16 Okt): tabel dirapikan jadi 7 kolom** — "Hub" dan "Koordinat" tidak lagi kolom sendiri, keduanya jadi baris kedua sel **Pemasok** (`supplierMetaLine`: "Surabaya · -7,2395 / 112,7731") karena dua kolom itu memakan 178 px dari 913 px; ukur sesudahnya: tabel **913 = 913 px (tanpa geser)**, tinggi baris **54 px rata**. **Satu standar bentuk label** (dipakai `.reach-tag`, `.shipping-tag`, `.shipping-tag-fail`): 12 px, `padding: 2px 8px`, `inline-flex`, `white-space: nowrap` + `text-overflow: ellipsis`, jadi **tinggi 22 px** (setara `.commodity-pill`) — sebelum F12c pil kiriman memuat kalimat penuh dan membungkus 3 baris (186×63 px). Kalimat penuh tetap tersedia lewat `title`; pil jangkauan hanya menulis keadaan karena km-nya sudah ada di kolom **Jarak** tepat di sebelahnya. Pemasok tanpa sumber profil tetap "—" (tidak dikarang) | harga/PO per pemasok (belum ada endpoint; ditulis "—") |
| Kualitas Agen (bagian 2 tab **KPI & Kualitas Agen**) | `/quality` (`MOCK_AGENT_RUNS` di acuan) | `GET /decisions/{id}/traces` + `verdict` pada `approval-summary` (sampel 8) | LLM-as-judge, biaya token (belum ada di repo) |

Aturan yang dipegang (sama seperti halaman lain): angka yang tidak ada ditulis
"**—**", dan halaman yang memakai **sampel** menyatakan jumlahnya terang-terangan
("dinilai 8 dari 95 keputusan dalam cakupan"). Logika murni dipisah ke
`lib/food-safety.ts`, `lib/surplus.ts`, `lib/suppliers-board.ts`, `lib/agent-quality.ts`
(diuji) dan markup ke `components/*Board.tsx` (kontrak markup diuji). Halaman
**Surplus & Limbah** dibatasi peran SPPG (`sppg_head`, `sppg_nutritionist`) seperti
acuan; sisanya semua peran. Konsekuensinya (ditemukan 20 Okt 2026): panel
"Rencana alokasi surplus" tidak boleh lagi merakit pasangannya dari
`/balance/map` — endpoint itu dibatasi cakupan peran (Ruling 2026-10-14), jadi
peran SPPG hanya menerima lokasinya sendiri dan panel selalu kosong. Rencana
sekarang dihitung server lintas lokasi (`GET /surplus/allocations`, pasangan
`from/to/kg/distance_km` + `cost_share_pct`), dan panel menulis sebabnya bila
kosong (`available: false` + `reason`).

**Ambang 150 kg (permintaan pemilik 20 Okt 2026).** "Jangan rencanakan surplus
jika di bawah 150 kg." Dua ambang ditegakkan di server (`MIN_SURPLUS_KG`):
lokasi hanya menjadi sumber bila surplusnya ≥150 kg, dan tiap baris pengiriman
hanya tampil bila kg-nya ≥150 kg. Alasan ambang kedua: penanganan tetap
Rp150.000 selalu kena berapa pun kg-nya, jadi alokasi 5 kg lintas kota bukan
rencana yang masuk akal. Respons membawa `min_surplus_kg`, `surplus_locations`
(kini hanya sumber yang lolos), `totals.surplus_below_min_kg` (bagian yang
sengaja tidak direncanakan), dan `reason`
`surplus_di_bawah_ambang`/`alokasi_di_bawah_ambang`; panel menulis ambang itu
di bawah judul. Terukur: telur menyisakan satu baris `Cianjur → Jakarta
622,17 kg`; ayam tidak punya rencana karena semua pasangannya <150 kg; beras
tetap tiga baris (1.344,06 / 269,47 / 183,64 kg).

Konvensi tabel baru: tabel lebar WAJIB dibungkus `<div className="board-table-wrap">`
(geser di dalam kartu) + petunjuk `.board-scroll-hint` yang hanya tampil ≤640px —
tanpa itu tabel melebarkan seluruh halaman di 375px.

### 3.9 Panel "Data & rentang waktu" di Demo Control (Fase 5 rencana 2026-10-14)

Tab **Demo Control** (khusus approver) memuat dua hal, dalam urutan kerja yang disengaja:
**siapkan data dulu → picu skenario → analisis**. Panel baru berada DI ATAS konsol pemicu
skenario, karena mengubah rentang data tanpa sadar setelah menjalankan skenario adalah
sumber angka yang tidak bisa dipertanggungjawabkan.

Aturan yang dipegang panel ini:

- **Pratinjau dipicu tombol, bukan per ketikan tanggal** — satu permintaan
  `GET /demo/preview?start&end`, hasilnya dibuang begitu rentang berubah, supaya angka lama
  tidak pernah tampil berpasangan dengan rentang baru.
- **Semua kalimat dan angka berasal dari payload backend** (`totals`, `generated_at`,
  `writes:false`) — tidak ada hitungan di frontend. Kalimat status dibangun di
  `lib/demo-data.ts` dan diuji (`tests/demo-data.test.ts`).
- **Peringatan destruktif tampil SEBELUM tombol ditekan**, dan "Bersihkan data demo"
  (hapus `origin='demo'`) berjalan dua langkah dengan konfirmasi eksplisit; "Buat/perbarui"
  menyatakan lebih dulu berapa baris yang akan dihapus/ditambah.
- **"Segarkan ke hari ini" memindahkan jangkar snapshot kanonik** (seeder menggeser tanggal
  relatif ke sekarang). Karena itu peringatannya tegas dan ada tes backend yang memaku
  tanggal kanonik (`test_refresh_hari_ini_bergeser_dan_bisa_dikembalikan`) — kalau tombol
  ini ditekan, angka demo berubah sampai data kanonik dimuat ulang.
- Respons backend ditampilkan apa adanya (termasuk `0` dan galat), bukan diringkas menjadi
  kalimat yang lebih enak dibaca.



## 4. Design system

### Warna (design token — sinkron dengan `frontend/app/globals.css`, Bento Modern 2026-10-16)
Fase 0 (Bento Modern, Arah 4): netral jadi slate, brand jadi biru `#2563EB`, kartu
putih ber-border rambut, radius 16px, bayangan ultra-halus. Warna STATUS sengaja
TETAP gelap (AA) — kemodernan status datang dari sistem tint (`--ok/--warn/--danger`),
bukan dari mencerahkan tinta yang akan merusak kontras teks.
```
--navy-900 (ink): #0F172A   /* teks utama & heading (slate-900) */
--navy-700:       #334155   /* aksen sekunder (slate-700) */
--line:           #E2E8F0   /* border rambut (slate-200) */
--ink-muted:      #475569   /* teks sekunder (slate-600) */
--accent-strong:  #2563EB   /* brand: tombol, link, fokus (blue-600) */
--accent:         #1D4ED8   /* hover aksi (blue-700) */
--bg-page:        #F8FAFC   /* latar halaman (slate-50) */
--status-safe:    #2E7D32   /* PASS / surplus (tetap — AA) */
--status-live:    #8B5CF6   /* penanda AKTIF (pin pemasok mengirim + puck mobil) — bukan status */
--status-warning: #F9A825   /* tight — hanya tint; teks badge pakai --warn-ink */
--status-danger:  #C62828   /* FAIL / shortage (tetap — AA) */
```

Token tambahan hasil audit UI/UX 2026-10-11 (semua sudah diuji kontras WCAG AA
secara terhitung, bukan dikira-kira):

```
--ink-subtle:     #64748B   /* teks tersier & pemisah (slate-500): ~4,8:1 di putih */
--line-input:     #7C8B9B   /* batas KONTROL interaktif (input/select/chip/tombol): >= 3:1 (WCAG 1.4.11) */
--ok-bg/--ok-border/--ok-ink             /* #ECFDF5 / #A7F3D0 / #065F46 — lencana aman (7,3:1) */
--warn-bg/--warn-border/--warn-ink       /* #FFFBEB / #FDE68A / #8A5A00 — lencana & TEKS peringatan (5,9:1) */
--danger-bg/--danger-border/--danger-ink /* #FEF2F2 / #FECACA / #991B1B — lencana bahaya (7,6:1) */
--neutral-bg/--neutral-border/--neutral-ink /* #F1F5F9 / #CBD5E1 / #475569 — lencana netral (6,9:1) */
--ink-inverse:    #FFFFFF   /* teks di atas latar berwarna (tombol primer, avatar, lencana) */
--accent-soft:    #EFF6FF   /* tint aksen: item rail aktif, chip peran (blue-50) */
--skeleton-base:  #E8EDF2   /* kerangka memuat */
--dur-1/--dur-2/--dur-3     /* 90ms tekan, 160ms hover/fokus, 240ms panel */
--ease-standard:  cubic-bezier(0.2, 0.8, 0.2, 1)
--space-1..--space-6        /* 4/8/12/16/24/32px */
--text-meta: 12.5px ; --text-micro: 12px   /* lantai ukuran teks */
```

Aturan yang mengikat setelah audit (jangan dilanggar saat menambah UI):

- Token **garis** jangan dipakai sebagai **warna teks** — inilah penyebab temuan
  kontras terbesar (`.rec-sep` & `.kpi-breadcrumb-sep` memakai `--line-strong`
  = 1,49:1; sekarang `--ink-subtle` = 5,27:1).
- Warna status **#F9A825 dilarang sebagai warna teks** di latar terang (1,97:1);
  teks peringatan memakai `--warn-ink`. `--status-warning` tetap untuk lencana/tint.
- Batas kontrol interaktif memakai `--line-input` (≥3:1); `--line`/`--line-strong`
  hanya untuk garis dekoratif.
- **Fase 1 (2026-10-16): rail & top bar TIDAK lagi biru.** Keduanya permukaan kaca
  putih; teks memakai `--ink-muted` (7,5:1 di putih) dan item aktif `--accent-strong`
  di atas tint `--accent-soft` (~5:1). Aturan lama "teks di atas rail/top bar biru
  minimal `rgba(255,255,255,0.92)` (4,64:1 di #0969DA)" kini berlaku HANYA untuk
  permukaan gelap yang tersisa: panel brand login, tombol primer, avatar, lencana.
- Ukuran teks data ≥ 12px (`--text-micro`/`--text-meta`).
- **Fase 2 (2026-10-16): angka hero Overview 44px** — satu-satunya teks besar selain
  `.page-header h1`; nada warnanya memakai token status versi gelap (merah 6,5:1 /
  hijau 6,3:1 di atas putih) sehingga ukuran kecil pun tetap lolos AA. Nilai yang
  tidak tersedia ditulis "—", bukan "0 kg", supaya pembaca layar tidak diberi angka palsu.
- Target sentuh ≥ 44px pada `(pointer: coarse)` **atau** `(max-width: 720px)`
  untuk nav rail, chip, pil komoditas, pilih cakupan, dan tombol ikon.
- Setiap kontrol punya umpan balik `:active` (transform 1px + peredupan, 90ms)
  dan cincin fokus `:focus-visible`; gerak dimatikan saat
  `prefers-reduced-motion: reduce` (umpan balik peredupan tetap ada).
- **Gerak peta (revisi 16 Okt).** Perubahan keadaan di sekitar peta diberi gerak
  pendek dari token (`--dur-1/2/3` + `--ease-standard`): panel rincian lapisan
  membuka/menutup lewat tinggi `grid-template-rows` `0fr → 1fr` (bisa dibuka DAN
  ditutup; `max-height` tidak bisa menutup mulus), chevron diputar 90°, legenda
  masuk `map-legend-in`, isi popup masuk `map-popup-in` — dipasang pada `.map-popup`
  (ISI), bukan `.maplibregl-popup`, karena MapLibre memakai `transform` elemen itu
  untuk memposisikan popup. Pin titik bertransisi (cincin lokasi aktif, hover
  membesar 1,28×; rotasi 45° pin pemasok dipertahankan). Semuanya mati di
  `prefers-reduced-motion: reduce` — umpan balik warna/cincin tetap ada.
- Keadaan memuat memakai satu pola: komponen `LoadingState` (skeleton +
  `role="status"` + `aria-busy`) — bukan teks "Memuat…" polos.

Panel peta memakai palet aplikasi yang sama (arah Roy 2026-10-11): peta TERANG
apa adanya, legenda putih, pin hijau/merah/abu dari `--status-*` — tidak ada
palet gelap kedua dan tidak ada token tambahan untuk peta.
> Catatan sinkronisasi: `globals.css` `:root` = sumber kebenaran teknis; bagian ini
> merangkum maksudnya. Sidebar, panel peta, dan konsol agent semuanya permukaan
> terang; badge memakai label + tint warna (tanpa titik), mengikuti komponen
> badge acuan.

**Kerangka/shell (Fase 1 redesign, 2026-10-16 — membalik "rail biru" 9 Okt).**
Rail sidebar dan top bar adalah **permukaan kaca putih** (`rgba(255,255,255,.86)`
rail / `rgba(255,255,255,.72)` top bar, `backdrop-filter: blur`), dipisah garis
rambut `--line`. Tinta memakai `--ink` / `--ink-muted`, **bukan** teks putih lagi.
Item rail aktif = tint `--accent-soft` + tinta & bar kiri `--accent-strong`.
Chip peran di top bar = pill bertint biru; jam top bar memakai Fira Code
(`--font-data`) supaya angkanya tidak bergetar. Pilih cakupan yang terkunci
memakai `--surface-sunken` + `--ink-muted` (≈7:1). Di lebar ≤720px rail menjadi
satu baris mendatar yang bisa digeser (perilaku lama, hanya warnanya ikut terang).
Tombol keluar rail memakai nada merah-terang (`--danger-bg`/`--danger-border`),
bukan putih-di-atas-biru.

**Overview bento (Fase 2 redesign, 2026-10-16).** Strip KPI Overview bukan lagi satu
kartu berisi tiga kolom sama lebar: **tiga kartu terpisah** di grid 12 kolom dengan
bobot **5/3/4**. Tile hero memuat SATU angka terpenting halaman — selisih pasokan
lokasi aktif (atau Σsurplus − Σshortage jaringan saat cakupan "semua lokasi") dalam
Fira Code 44px, diwarnai nada selisih (`is-shortage` → `--status-danger`,
`is-surplus` → `--status-safe`, netral → `--navy-900`), dengan kaki "kurang/lebih
N% dari kebutuhan" dan baris mini jumlah lokasi. Nilai yang tidak tersedia ditulis
"—" (`lib/overview-bento.ts`) dan **tidak pernah 0** — sama seperti aturan jujur
angka di halaman lain. Kartu "Perlu keputusan" di samping peta memakai `notifList`
yang sama dengan lonceng top bar supaya kedua tempat tak pernah berbeda angka.
Basemap peta diredupkan lewat filter pada kanvas (`.map-gl canvas`, saturate .62):
pin adalah penanda DOM, jadi pin hijau/merah tetap menyala penuh — tidak ada tile
atau gaya peta baru. Grafik "Pasokan per Lokasi" selebar halaman dengan tinggi
**mengikuti jumlah lokasi** (`--chart-h` = 96 px sumbu+legenda + 34 px per batang,
dijepit 180–380 px; `maxBarSize` 26 px). Tinggi tetap 380 px dulu membuat kartunya
448 px padahal data seed hanya punya SATU lokasi — satu batang raksasa selebar
~980 px di dalam kartu setinggi itu (arah pemilik 2026-10-16). Diukur sesudahnya:
kartu 448 → **248 px**, holder 380 → **180 px**. Jangan kembalikan ke tinggi
persentase (`ResponsiveContainer` menghitung 0 di rantai flex yang tingginya dari
`min-height`/`auto`) dan jangan hapus `--chart-h` dari komponen: CSS `.stock-chart-
holder` yang dulu memaku 380 px akan mengalahkan tinggi child-nya.

**Aturan ukuran BENTUK, bukan teks (revisi 16 Okt lanjutan — keluhan pemilik:
"banyak bagian shape yang berisi teks yang ukurannya terlalu besar").** Skala
tipografi sudah dipangkas di Fase 8–9 dan terukur bersih (maks 36 px = angka hero),
jadi yang tersisa adalah ukuran *pembungkusnya*. Tiga aturan yang berlaku app-wide:
- **Lencana status WAJIB satu baris** — `.badge` dapat `white-space: nowrap`,
  `flex: none`, `line-height: 1.35`. Dulu "PENDING APPROVAL" membungkus jadi dua
  baris di kolom sempit sehingga jadi pil **120×42 px** (dan "VERIFIER FLAGGED"
  136×42 px) untuk teks 12 px; sekarang **142×22 px**. `flex: none` tidak boleh
  dilepas: tanpa itu badge ikut menyusut di dalam baris flex dan labelnya
  membungkus lagi. `.node-badge` ikut 12 px (`--fs-1`, dulu 13 px) supaya satu
  bahasa dengan `.badge`.
- **Kartu ringkas tidak berdiri selebar halaman sendirian** — Telemetri Node
  (237 px) + daftar Status Lokasi (203 px) kini sepasang di `.overview-pair`
  (grid 2 kolom ≥1100 px; bertumpuk di bawahnya): 440 px → **223 px**.
- Angka di dalam kartu ringkas dirapatkan: `.node-telemetry-body` padding 14 px,
  `.node-gauge-list` gap 8 px, `.node-telemetry-meta` margin 4/10 px.

Hasil terukur (1440 px, SPPG Head/Overview): tinggi dokumen **2256 → 1826 px**
(−19%), kartu grafik 448 → 248 px, chip legenda menggantikan kotak 300×137 px,
dan **0 luapan** horizontal di 375/768/1280/1440 px.

**Feed & decision evidence (Fase 3 redesign, 2026-10-16).**
- Feed Recommendations: entri yang **lewat tenggat** diredam lewat *permukaan*
  (`--surface-sunken` + tepi netral), **bukan `opacity`** — meredupkan seluruh
  kartu menjatuhkan teks sekunder `#64748B` ke ~3:1 dan itu gagal AA. Lencana masa
  berlaku berbunyi **"Lewat tenggat"** (satu kosakata dengan lonceng top bar).
  Enam kartu pertama masuk berurutan (`@keyframes feed-row-in`, 35ms bertingkat,
  hanya `transform`/`opacity`, mati pada `prefers-reduced-motion: reduce`).
- Decision & Evidence: ringkasan = hero 2 kolom (kartu keputusan | fakta identitas
  & tenggat, ≥1100px); tiga kartu fakta grid 12 kolom **span 4** (≤1180px → 6,
  ≤760px → 12); baris bawah **5fr/7fr** = Riwayat iterasi | Bukti & integritas.
  `SupplierExclusionView` selalu baris penuh (form) tepat setelah Governance.
- **Di kartu sempit (span 4), label fakta DITARUH DI ATAS nilai** — dengan label di
  samping, kolom nilai hanya ~105px dan "Rp14.022.000" terpecah di tengah angka.
- **Kartu kepercayaan gelap** (`.integrity-trust`): satu-satunya permukaan gelap di
  tema terang, hanya untuk bukti kriptografis (Merkle + alamat konten + tanda tangan
  ECDSA) — token `--trust-bg/-surface/-line/-ink/-ink-muted/-accent`. Daftar
  pengukuran (ComplianceEvidencePanel) dan tombol ekspor tetap terang: itu dokumen
  kerja, bukan bukti kripto.
- Approval: modal radius `--radius` dengan garis aksen 4px di kiri; item menu
  tindakan radius 10 dengan hover tint; ring fokus eksplisit pada tombol
  modal/menu/ekspor. **Gating approval (1b/2b/3b) tidak diubah.**

**Decision & Evidence — kerapian baca (2026-10-17, keluhan "tampilannya sangat kurang").**
- **Pemilih keputusan punya label terlihat** (`.evidence-picker-label` =
  "Keputusan yang diperiksa") + `.evidence-picker-hint` yang menyebut
  **"N menunggu tindakan · M keputusan tersedia"**. Angkanya dari `countActionable`
  (`lib/topbar.ts`) — **satu sumber dengan lonceng top bar**, bukan hitungan kedua.
  Sebelum ini pemilihnya hanya `<select>` berisi "— pilih keputusan —" tanpa label.
- **Baris fakta "—" tidak lagi menumpuk terbuka**: `FactList` menerima prop
  `collapseEmpty`; baris dengan nilai `DASH` dipindah ke `<details class="fact-more">`
  berlabel "N rincian belum ada datanya" (satu angka, jamak/tunggal benar, **tidak
  pernah "0 rincian"**). Tampil dulu yang punya isi. **Aturan kosong tetap satu:
  HANYA `"—"` (DASH) yang dianggap kosong** — "0", "Rp0", dan "Tidak" adalah jawaban
  nyata (`hasValue`/`splitFacts` di `lib/evidence.ts`). Kartu **Governance sengaja
  TIDAK di-collapse**: di sana "—" justru kabar baik ("tidak ada penghalang").
- **Strip "Langkah berikutnya"** (`.evidence-next` + nada `-warn/-ok/-danger/-muted`)
  membuka kartu Ringkasan keputusan: satu kalimat dari `nextStep()` (`lib/evidence.ts`)
  yang menjawab "apa yang harus saya lakukan". Hanya memakai field yang ada
  (`status`, `approvals`, `approval_requirement.min_approvals`, `blocking_reasons`,
  `expiry.valid`, `can_execute`); peran non-penyetuju dapat kalimat "bersifat
  pengawasan". Daftar penghalang **dipangkas 2 + "(+N lain)"** supaya tidak jadi
  dinding teks. Cerminan `APPROVER_ROLES` ← `visibleActions()` (paritas dijaga tes).
- Tinggi halaman halaman contoh: 2004px → 1772px (baris "—" masuk rincian).

**Decision & Evidence — DESAIN BARU "catatan keputusan" (2026-10-17, riset pola).**
Permintaan user: "perbaiki ui ux halaman Decision & Evidence, tapi riset dulu dan cari
referensi, lalu pakai skill desain". Riset lengkap + rujukan ada di
`_qa/rencana-decision-evidence-v2.md`; ringkasnya: pola **approval workflow**
(UX Patterns Guide — "routed request record": ringkasan, penyetuju, status rute, tenggat,
kontrol keputusan, riwayat), **aturan 3 detik** + "kuning bukan merah" + hierarki
aksi→skala→konteks→akibat (AgentInterface), **"review screen is the entire product"** +
ember umur + konfirmasi yang menyebut objek (Skopx), dan **triage lewat flag** +
"tunjukkan konsekuensi, bukan niat" (Code and Proof). DB `ui-ux-pro-max` untuk
"decision evidence approval audit console" mengembalikan **Minimalism & Swiss** dengan
palet navy/`#2563EB`/`#F8FAFC` — nyaris sama dengan token Arah 4, jadi bahasa visual tidak
diganti; **strukturnya** yang diperbaiki.
- Urutan region BARU (dari urutan tabel → urutan keputusan manusia):
  `evidence-hero` (kepala keputusan) → `evidence-route` (jalur persetujuan) →
  `evidence-decide` (`#zona-keputusan`) → `evidence-grid` (bukti) → `evidence-bottom` (jejak).
- **Kepala keputusan** = lencana status berupa KATA ("menunggu persetujuan", bukan
  "PENDING_APPROVAL") + jendela berlaku (`dueLabel`) + id/iterasi + jalan pintas
  "Ke zona keputusan"; judul **aksinya** dari `decisionHeadline()`
  ("Alihkan 492 kg telur: Bogor → Jakarta"); strip metrik (`decisionMetrics`) —
  kuantitas, biaya aman terkirim, selisih dari harga beli, tujuan; blok
  **"Perlu diperhatikan (N)"** (`attentionFlags` — triase, bukan alarm: keputusan sehat
  = daftar kosong; **tile strip** di grid `auto-fit minmax(260px, 1fr)` — satu temuan
  memakai lebar penuh, tiga temuan tiga kolom, jadi tidak ada bar selebar halaman yang
  separuh kanannya kosong; blok baru dirender setelah ringkasan persetujuan tiba,
  supaya tidak muncul "(1) Belum diverifikasi" palsu saat data masih dimuat); strip "Langkah berikutnya" (`nextStep`, kini BIRU accent-soft karena
  instruksi ≠ bahaya); blok **"Kalau disetujui / Kalau ditolak"** (`consequences`,
  deterministik dari `can_execute`, `blocking_reasons`, `execution_target`, `iteration`).
- **Tata letak kepala = grid ber-area (19 Okt 2026):** label + judul di kolom kiri,
  "Langkah berikutnya" di kolom kanannya, metrik & blok temuan selebar kartu, akibat
  dan tautan jejak selebar kartu di bawahnya. Dulu setiap baris memakai lebar 909 px
  padahal isinya 140-167 px (separuh kanan kosong) dan kartunya ~527 px; sekarang
  ~370-410 px. Di ≤900 px kembali satu kolom (urutan baca tetap: status → ringkasan →
  angka → temuan → langkah → akibat → jejak).
- **Bukti = dua kolom koran**, bukan baris grid 3 × 4/12: tinggi kartu sangat
  bergantung keputusan yang dibuka (Biaya bisa 615 px sementara Keamanan 355 px dan
  Identitas 335 px), sehingga baris setinggi kartu terpanjang menyisakan 260-400 px
  kosong. `columns: 2` + `break-inside: avoid` menyeimbangkan kolom sendiri
  (966 px → 665 px pada data itu; 236 px pada data 110/110/222), satu kolom di ≤900 px.
- **Jejak & bukti tersimpan ditumpuk** (satu kolom selebar kartu): 5/7 membuat kartu
  riwayat 217 px di samping panel 546 px → 329 px kosong. Penumpukan: riwayat 947×166 +
  panel 947×265, dan dua bukti (Merkle Ledger & Dossier) berdampingan
  (`repeat(auto-fit, minmax(260px, 1fr))` di `.integrity-trust`).
- **Fakta di kartu bukti sebaris label→nilai (≥721 px), nilai rata kanan.** Ada override
  lama `.evidence-grid .fact-row { grid-template-columns: minmax(0, 1fr) }` yang
  menumpuk label di atas nilai: tiap fakta 56 px dua baris dan separuh kanan kartu
  kosong. Bentuk baru 38% / 62% + `text-align: right` pada `dd` (kolom angka sejajar
  seperti lembar spesifikasi) → baris 32-34 px. Di ≤720 px tetap menumpuk (angka
  panjang tidak terpecah di tengah).
- **Lencana status + meter persetujuan satu baris** (`.gov-status` grid
  `max-content minmax(0,1fr)`; `.gov-progress` `max-width: none`): dulu lencana 162 px
  dan meter 420 px bertumpuk di baris 909 px, meter kini mengisi 731 px; baris peran,
  penunggu, dan penghambat melebar penuh (`grid-column: 1 / -1`).
- **Jalur persetujuan** (`approvalRoute`): empat langkah tetap Diajukan → Verifikasi agent
  → Persetujuan → Eksekusi, tiap langkah membawa "siapa/waktu/apa berikutnya"
  (mis. "1 dari 2 · berikutnya: Ahli Gizi SPPG"); keadaan langkah **selalu ada teksnya**
  (`.sr-only` "Keadaan langkah: …") — warna/bentuk bukan satu-satunya pembawa arti.
- **Zona keputusan naik** ke posisi 3 (urutan Tab kanonik: ringkasan → rute → kontrol
  keputusan → bukti → riwayat); isinya tetap `approvalFacts` + `DecisionActions` yang sama
  — **gating 1b/2b/3b tidak diubah**.
- Kartu keempat `evidence-grid` menjadi "Identitas & tenggat" (fakta `decisionFacts`
  dipindah dari ringkasan lama). `RecommendationCard` dilepas dari halaman ini karena
  kepala keputusan sudah menjadi kartu keputusan (kartu itu tetap dipakai di feed).
- Semua logika baru **murni + ber-tes** di `lib/evidence.ts` (13 tes baru);
  markupnya dijaga 6 tes baru di `tests/decision-evidence.test.tsx` (termasuk tes
  URUTAN region). Ukuran judul 24px (`--fs-7`), metrik mono tabular.
- **Langkah 2 (17 Okt 2026) — "jejak bercerita, umur jujur, satu tombol ekspor":**
  - Kartu "Riwayat iterasi" (chip v1/v2/v3 yang terpisah dari fakta governance) DIGANTI
    **"Jejak & riwayat"** = SATU lini masa (`auditTimeline()` → `components/DecisionAudit.tsx`):
    iterasi keluarga dari `/decisions/{id}/chain` → pengajuan iterasi kini (+`proposed_by`)
    → verifikasi (`verdict` + catatan) → tiap baris `/approval-summary`
    ("Disetujui/Ditolak · label peran manusia · waktu · komentar"). Urutan BERCERITA
    (bukan diurut ulang menurut jam: verifikasi tidak punya kolom waktu, jadi diurut
    kronologis ia akan salah tempat). Waktu yang tidak ada ditulis "waktu tidak tercatat".
  - Baris approval tanpa nilai `approved: true|false` **tidak lagi** dirender "Ditolak"
    (klaim palsu yang sempat bocor); `rejection_reason` muncul sebagai kejadian "Ditolak"
    hanya bila tidak ada baris penolakan. Catatan verifier yang cuma salinan huruf kecil
    dari putusan mentah ("consistent" vs "konsisten") tidak diulang (`catatanUnik`).
  - **Umur jendela** `windowUsage()` → chip "Jendela terpakai N%" / "Jendela lewat" di
    kepala keputusan. SENGAJA tanpa ember fresh/aging/breached ala Skopx: target
    waktu-ke-keputusan per jenis permintaan tidak ada di data repo — mengarang ambang =
    mengarang kebijakan. Hanya dua fakta: persen terpakai & lewat/tidak.
  - **Ekspor bukti satu tombol** di kepala keputusan: `downloadDossier()` +
    `dossierFileName()` (lib/export.ts, nama berkas satu tempat) memanggil
    `/decisions/{id}/dossier` yang sama dengan panel Bukti tersimpan, dengan umpan balik
    jujur ("Bukti terunduh sebagai …" / kalimat gagal yang menunjuk panel bawah).
    `IntegrityPanel` tetap apa adanya.
  - **Badge kasus demo kembali** ke kepala keputusan lewat `caseLabelOf()` yang kini
    DIEKSPOR dari `RecommendationCard` (kelas `.rec-case` dipakai ulang, bukan palet
    kedua) — penanda itu dulu datang dari kartu feed yang kini digantikan hero.
  - Tes: `evidence-summary.test.ts` + tes murni (auditTimeline, windowUsage, catatanUnik);
    markup `decision-evidence.test.tsx` +5 (umur, ekspor, lini masa, badge kasus).
  - Kontrak komposisi di `tests/sidebar-wiring.test.tsx` disesuaikan ke desain baru
    (`<DecisionAudit` + `caseLabelOf` menggantikan `<RecommendationCard`).

**Decision & Evidence — LANGKAH 3 "bahasa, tautan, sentuh" (2026-10-17).**
- **Lapisan bahasa** `frontend/lib/bahasa.ts` (murni, 13 tes di `tests/bahasa.test.ts`):
  `humanizeBlocker` menerjemahkan kalimat yang BENAR-BENAR dikirim server
  (`decision expired`, `decision belum terverifikasi`, `decision ditolak`,
  `decision sudah dieksekusi`, `approval belum memenuhi requirement (missing/rejected)`,
  `status X tidak dapat dieksekusi`, `batch sumber FAIL`, `safety revalidation gagal`)
  dan menerjemahkan juga saat kalimat itu dibungkus pesan galat
  ("Gagal menyetujui: …"); string yang tidak dikenal dikembalikan APA ADANYA (tanpa tebakan).
  `safetyLabel` (PASS→Lolos, FAIL→Gagal, NEEDS_VERIFICATION→Perlu verifikasi),
  `agentLabel` (supervisor_agent→Agen supervisor, verifier_agent→Agen verifikator; agen lain
  dibiarkan), `executionTargetLabel` (MOCK→Simulasi (mock)), `roleList` (sppg_head→Kepala SPPG),
  `blockingReasons`.
  Dipakai di: `nextStep`, `consequences`, `approvalFacts` ("Alasan tertahan", "Peran penyetuju"),
  `safetyFacts` (status keamanan, "Verifikator", "Target eksekusi"), `decisionFacts`
  ("Diusulkan oleh"), `approvalRoute` + `auditTimeline` (pelaku), dan pesan dialog
  `DecisionActions` (sebelumnya menampilkan pesan server mentah).
  Label hint "putusan aturan:" → "aturan persetujuan:".
- **Deep link** `?keputusan=<id>` (`frontend/lib/decision-link.ts`, 9 tes):
  dibuka sekali saat mount → tab Decision & Evidence + keputusan itu; pilihan berikutnya
  menulis URL lewat `history.replaceState`; pindah tab melepas param supaya tautan tidak
  menunjuk keputusan yang tidak sedang dilihat. Nilai bukan-id (spasi/terlalu panjang) → null.
  Tautan yang menunjuk keputusan di luar cakupan peran diberi keadaan sendiri:
  "Keputusan itu tidak ada di cakupan akun ini" (bukan "belum ada keputusan dipilih"),
  dan selama daftar masih diambil muncul "Memuat keputusan…" — jangan menuduh sebelum data tiba.
- **Sentuh & pembaca layar (375px terukur)**: tautan "Ke zona keputusan" dinaikkan ke
  `min-height:24px` (WCAG 2.2 AA 2.5.8; 44px di `@media (pointer: coarse)`), lini masa diberi
  `aria-label="Jejak keputusan"`. Hasil ukur di iframe 375px (viewport 356): luapan horizontal
  **0px**, tombol Unduh 138×44px, tautan 121×24px, kepala keputusan membungkus rapi 134px,
  4 tile metrik selebar kolom (272px), `.audit-item` 63px, tidak ada elemen melewati tepi.
- **Sisa kebocoran yang ikut dibersihkan saat verifikasi layar**:
  `approvalRoute` ("target MOCK") dan `consequences` → `executionTargetLabel`;
  `ComplianceEvidencePanel` ("PASS n · FAIL n · NEEDS_VERIFICATION n") → `safetyLabel`;
  `SupplierExclusionPanel` : "LOCAL · SPPG" → "Lingkup lokal · SPPG", UUID mentah
  "Scope SPPG penerima: 23e6e766-…" → "SPPG penerima: #23e6e766", dan kalimat
  "Batch FAIL tetap tidak eligible" → "Batch yang gagal pemeriksaan tetap tidak bisa dipakai".
  `ApprovalModal` ("Batch FAIL tetap diblokir", "EXCLUDED (FAIL)", `worst_status` mentah, dan
  `target LOCAL`) → "gagal pemeriksaan"/"dikecualikan", `safetyLabel`, dan
  `executionTargetLabel` (LOCAL = "Lokal (tanpa PO)").
  Pemindaian teks layar sesudahnya: `missing/rejected`, `requirement`, `sppg_head`,
  `supervisor_agent`, `verifier_agent`, `unavailable`, `consistent`, `PASS`, `MOCK`,
  `NEEDS_VERIFICATION` = **0 kemunculan** di halaman bukti.
- Catatan jujur: `aria-sort` TIDAK dipasang karena halaman ini tidak punya tabel bukti, dan
  pintasan papan tulis (j/k/a/r) bukan milik halaman ini — keduanya tetap di daftar halaman lain.

**KPI & Agent Log (Fase 4 redesign, 2026-10-16).**
- Kartu KPI: angka **mono tabular 32px** + **bullet bar** hanya untuk metrik
  berskala sendiri (persen 0–100, `SCALE_MAX` di `lib/kpi.ts`). **Tidak ada
  ambang target yang dikarang**: `GET /kpi` tidak mengirim target/threshold, jadi
  yang ditampilkan hanya skala nyata + arah perbaikan (`KPI_DIRECTION`:
  "makin tinggi/rendah makin baik"). Bar tanpa skala (IDR, menit) tidak digambar.
  Nilai > skala → bar penuh + `data-over`, angka di kartu tetap asli. Nilai
  null/teks/negatif → tanpa bar, **bukan 0%**.
- Agent Log: chip umur langkah terakhir di kepala konsol dari `step_at`
  (`lib/agent-trace.ts`), titik berdenyut (`trace-pulse`) untuk langkah baru,
  **shimmer** (`trace-shimmer`) hanya bila `output_summary.status` ∈
  running/in_progress/started/pending — `agent_traces` tidak punya kolom status,
  jadi "sedang berjalan" tidak boleh dikira-kira. Durasi per langkah
  (`duration_ms`) kini dirender. Panel provider = chip (titik + kata status).
- Konsol Agent Log **tetap terang**: permukaan gelap hanya dipakai sekali di app
  ini (`.integrity-trust`), kalau dipakai dua kali efeknya hilang.

**Keamanan Pangan / Surplus & Limbah / Pemasok (Fase 5 redesign, 2026-10-16).**
- Keamanan Pangan: tile angka besar 30px mono dengan tint status; **tint = keadaan ada**,
  jadi hitungan nol tampil netral (warna harus berarti sesuatu). Kotak blokir batch gagal
  = pagar bahaya tepi kiri 4px. Daftar batch mendesak memakai titik amber via `::before`
  (tanpa menambah teks). Angka tabel mono + `tabular-nums`.
- Surplus & Limbah: `.balance-flow` — dua angka besar (surplus `--ok-ink`, kekurangan
  `--danger-ink`) mengapit panah SVG aksen; `data-kosong="true"` membuat panah netral
  saat salah satu sisi tidak punya angka (panah tidak boleh menggambar aliran yang tak
  terbukti). Jarak/Jumlah mono. Bagian limbah kini berisi angka server (lihat §13); "—" hanya
bila endpoint menjawab `available: false`.
- Pemasok: kolom Keandalan = bar mini 6px + angka; lebar dari `reliabilityMeter()`
  (0–100, ambang `LOW_RELIABILITY` = 0,6), `aria-label` membawa angkanya, skor kosong →
  tanpa bar. Panel governance (`SupplierExclusionPanel.module.css`) memakai token tema.

**Hari Ini / Demo Control / Pengaturan (Fase 6 redesign, 2026-10-16).**
- Hari Ini jadi bento 12 kolom: "Menunggu tindakan" span 7 × 2 baris, batch & shortage
  span 5 di kanan, KPI + rantai audit baris penuh (< 1180px semua menumpuk satu kolom).
  Chip sisa waktu = pil + dot: lewat merah, ≤ `DUE_SOON_HOURS` (48) amber, netral abu;
  jam klien belum siap → tanpa klaim. `PageHeader` dapat slot `eyebrow` (kini dipakai
  sapaan "Selamat pagi/siang/sore/malam, <peran>"; server tidak menyapa).
- Demo Control: empat blok = empat kartu dengan chip urutan (Langkah 1–4), `OpsConsole`
  ikut jadi kartu putih radius 16. Pratinjau `writes:false` diberi lencana "pratinjau —
  tidak menulis apa pun" (amber). Baris hasil/pratinjau backend = mono; prosa tetap
  font badan. Peringatan dua langkah tidak diubah.
- Pengaturan: kontrol radius 10px (tinggi 44 px tetap), chip "belum disimpan" hanya pada
  baris yang draft-nya berbeda dari nilai tersimpan.

**Responsive & aksesibilitas (Fase 7 redesign, 2026-10-16).** Diukur 29 kombinasi peran×tab di
375/768/1024/1440 px + reflow 320 px (axe-core 4.10.2 + tier manual), hasil: 0 luapan halaman,
0 fokus tanpa cincin, temuan ● 123 → 0.
- **Kontras teks di atas tint** memakai token `--safe-ink-tint` (`#2A722E`, 5,19:1) — bukan
  `--status-safe` (`#2E7D32` yang di atas `rgba(46,125,50,.1)` hanya 4,49:1, gagal AA dengan
  selisih 0,01). Aturan: **warna status tetap untuk dot/teks di atas putih; teks di dalam lencana
  ber-tint memakai varian `*-ink-tint`.** Jangan pakai `opacity` untuk meredupkan teks
  (`.legend-count` pernah 4,00:1) — pakai token warna eksplisit.
- **Judul:** satu `h1` per halaman (dari `PageHeader`), tanpa lompatan tingkat. `PageHeader` punya
  prop `level` (1 = judul halaman, 2 = bagian di dalamnya) — dipakai tab "KPI & Kualitas Agen".
  Judul kartu memakai h3 di bawah h2 halaman.
- **Anti-luapan (WCAG 1.4.10, sampai 320 px):** kontainer scroll tabel diberi `contain: paint`
  (Chrome memperhitungkan isi kontainer scroll pada `scrollWidth` dokumen — tanpa ini halaman bisa
  digeser 10 px); tabel yang bisa digeser diberi `.board-scroll-hint` (muncul ≤640 px).
  **Jangan** memakai persentase di dalam `min()` pada `max-width` elemen di dalam flex: elemen itu
  melaporkan kontribusi intrinsik ke induk sehingga induknya meluap; batasi induknya
  (`max-width: 100%` + `min-width: 0`) lalu beri elemen `width: 100%` + batas px.
- **Target sentuh:** 44 px untuk kontrol; `<label>` yang membungkus checkbox dinaikkan tinggi
  (bukan kotaknya). Pengecualian yang disengaja: kontrol bawaan MapLibre 29×29 (WCAG 2.2 = 24 px)
  dan `.map-layer-toggle` 34 px.
- **Teks untuk pembaca layar:** jangan pasang `aria-label` pada elemen tanpa role (mis. `<span>`);
  pakai teks `.sr-only` di dalam elemen + tandai teks yang terlihat `aria-hidden` bila keduanya
  akan terbaca ganda.

### Palet warna (2026-10-17)

Permintaan pemilik: *"banyak hal yang harus berwarna supaya menyampaikan hal namun malah
tidak berwarna; tampilan terasa membosankan"*. Prinsipnya: **warna = makna**, bukan hiasan.
Status tetap memakai token lama (ok/warn/danger); ditambah **palet identitas** untuk entitas
yang berulang (komoditas, agen, kategori integrasi). Semua pasangan tinta/latar di bawah
lolos WCAG AA (rasio diukur, bukan dikira):

| Keluarga | Latar | Garis | Tinta | Solid (putih di atasnya) | Rasio tinta/latar |
|---|---|---|---|---|---|
| Biru — informasi, beras, supervisor | `#EFF6FF` | `#BFDBFE` | `#1D4ED8` | `#1D4ED8` | 6,16:1 |
| Amber — peringatan, telur | `#FFFBEB` | `#FCD34D` | `#92400E` | `#92400E` | 6,84:1 |
| Rose — risiko, ayam | `#FFF1F2` | `#FECDD3` | `#9F1239` | `#9F1239` | 7,30:1 |
| Teal — terverifikasi, agen verifier, jangkauan | `#F0FDFA` | `#99F6E4` | `#115E59` | `#115E59` | 7,27:1 |
| Violet — manusia/wortel | `#F5F3FF` | `#DDD6FE` | `#5B21B6` | `#5B21B6` | 8,19:1 |

#### Skala keparahan 4 tingkat (aman · medium · hard · critical)

Dua tingkat lama (warn & danger) tidak cukup membedakan "berat" dari "kritis".
Ditambahkan satu tingkat oranye di antaranya; semua tetap didampingi label:

| Tingkat | Latar | Garis | Tinta | Titik/solid | Rasio | Dipakai untuk |
|---|---|---|---|---|---|---|
| aman | `#ECFDF5` | `#A7F3D0` | `#065F46` | `#2E7D32` | 7,29:1 | approved / tersedia / lolos |
| medium | `#FFFBEB` | `#FDE68A` | `#8A5A00` | `#B45309` | 5,72:1 | pending / perlu verifikasi |
| hard | `#FFF7ED` | `#FED7AA` | `#9A3412` | `#EA580C` | 6,88:1 | verifier flagged / berat |
| critical | `#FEF2F2` | `#FECACA` | `#991B1B` | `#C62828` | 7,60:1 | rejected / failed / kedaluwarsa |

Utilitas: `.sev-pill` + `.sev-safe|medium|hard|critical` (titik 6 px + label).
Lencana tabel: `.board-badge-hard`. `statusTone()` di `AgentQualityBoard`
memisahkan `flagged → hard` dari `reject/fail → danger`. Slider Demo Control
memakai band 0–24 / 25–49 / 50–74 / 75–100 **sebagai penanda tampilan saja**
(slider tidak pernah dikirim ke server — bukan ambang kebijakan).
Penerapan (semua bentuk kecil):

| Permukaan | Sebelum | Sesudah |
|---|---|---|
| Pil komoditas peta (telur/ayam/beras/wortel) | abu-abu seragam | tint + titik 7 px per komoditas; aktif = solid gelap + teks putih |
| Tile "Hari Ini" (ok/warn/danger) | putih + garis kiri | wash gradien 72% + label berwarna |
| Kartu KPI Overview | putih semua | wash merah (shortage) / biru (pasokan) / amber (menunggu) + pita 3 px |
| Kartu KPI & Kualitas | tanpa penanda status | pita atas 3 px hijau/amber/merah |
| Tag rute & jangkauan di tabel Pemasok | teks abu | chip biru / teal |
| Chip jumlah ("3 kiriman") | abu | tint biru + angka tabular |
| Titik identitas judul kartu | tidak ada | kotak 6 px biru di kiri judul |
| Lencana integrasi "warn" | tanpa warna teks | tinta amber |

Aturan yang dijaga: warna tidak pernah satu-satunya pembawa makna (selalu ada teks/label),
angka hero tetap tinta netral (hanya wash yang berwarna), dan peta/legenda tidak diubah.
### Tipografi
- Font: **Fira Sans di-self-host** — berkas `frontend/public/fonts/*.woff2`
  (400/500/600/700) + `@font-face` di `globals.css`. Sejak 17 Okt 2026
  `next/font/google` DIBUANG: build tanpa jaringan hanya menghasilkan
  `__Fira_*_Fallback_*` (Arial) — terbukti di `.next/static/css`, sehingga
  seluruh app tampil dengan font sistem, bukan Fira. Pasangan Fira Sans +
  Fira Code juga rekomendasi `ui-ux-pro-max` ("Dashboard Data", mono + sans).
- Angka & telemetri memakai Fira Code (monospace, tabular) lewat `--font-data`
  (400/500/600, self-host, `font-variant-numeric: tabular-nums`).
- **Skala 8 langkah (2026-10-16) — satu-satunya sumber ukuran teks.** Semua
  `font-size` memakai token ini; angka mentah dilarang muncul kembali (dulu ada
  24 ukuran berbeda, termasuk 11/11,5px dan pecahan 12,5/13,5/14,5/15,5px):

  | Token | px | Peran |
  |---|---|---|
  | `--fs-1` | 12 | micro — label kecil, meta, lencana, keterangan tabel |
  | `--fs-2` | 13 | dense — sel tabel, baris sekunder, label nav rail |
  | `--fs-3` | 14 | base — badan tulisan, tombol (nilai `body`) |
  | `--fs-4` | 16 | title — judul kartu (h3), nilai yang ditonjolkan |
  | `--fs-5` | 18 | head — judul seksi (h2), angka di dalam kartu |
  | `--fs-6` | 20 | page — judul halaman (h1; `PageHeader level={2}` memakai `--fs-5`) |
  | `--fs-7` | 24 | metric — angka metrik besar (KPI/tile/neraca) |
  | `--fs-8` | 32 | hero — angka hero, satu per halaman (36 → 32, 17 Okt) |

  **Lantai 12 px dijaga:** `<small>` bawaan browser (0,833em → 11,67 px) dipatok ke
  `--fs-1` (`.agenda-hint`); audit 10 tab = 0 elemen di bawah 12 px.

  **Mobile (≤720 px):** `--fs-2` 14 · `--fs-3` 15 · `--fs-4` 17, dan
  `input/select/textarea` 16 px supaya iOS tidak memperbesar halaman saat fokus.
  Terukur di iframe 375 px: badan 15 px, luapan horizontal 0.
  Ujung atas (20/24/36) diturunkan 2026-10-16 dari 22/28/44 atas permintaan
  pemilik ("tidak terlalu besar"); rentang hero 36–42 mengikuti contoh skala
  skill `ui-ux-pro-max`. Karena semua `font-size` memakai token, satu perubahan
  token merambat ke seluruh app — dan judul halaman otomatis ikut seragam
  (`.page-header h1`, `.overview-header-title h1`, `.settings-title` = `--fs-6`).

- Tinggi baris: `--lh-num` 1.15 (angka besar), `--lh-head` 1.3 (judul),
  `--lh-body` 1.5 (badan tulisan — batas bawah 1.5–1.75 menurut pedoman a11y).
  Jarak huruf: `--track-tight` −0.02em (judul/angka besar), `--track-caps` 0.04em
  (label KAPITAL kecil).
- Lantai teks 12px dipertahankan (nilai di bawahnya dinaikkan 2026-10-11).
- **Judul wajib punya aturan sendiri.** Heading tanpa `font-size` jatuh ke
  bawaan peramban (h2 21px, h3 16,38px) — pernah terjadi pada `.provider-panel h2`
  dan panel governance. Setiap selector judul baru harus menyebut token skala.

### Lapisan densitas (2026-10-17)

Permintaan pemilik: *"banyak hal yang terlalu besar ... tampilannya jangan kebesaran"*.
Yang dikecilkan **hanya bentuk** dan penekanan angka; lantai teks 12 px dan target sentuh 44 px
di `(pointer: coarse)`/≤720 px tidak disentuh.

| Yang berubah | Sebelum | Sesudah |
|---|---|---|
| `--radius` (kartu) | 16 px | **12 px** |
| `--fs-8` (angka hero) | 36 px | **32 px** |
| Padding `.card` | 16 px | **14 px** |
| Jarak blok halaman (`.today-page`, `.evidence-page`, `.board-page`, `.overview-page`, `.demo-control-section`) | 14–18 px | **12–13 px** |
| Margin bawah `.page-header` | 20 px | **12 px** |
| Padding kartu KPI (`.kpi-dashboard .kpi-card`) | 20 px | **14 px** |
| Angka metrik (`.kpi-value`, `.stat-tile-value`, `.balance-value`) | 24 px (`--fs-7`) | **20 px** (`--fs-6`) |
| Tinggi kanvas `.map-gl` (desktop) | 460 px | **400 px** (breakpoint 900/720 px tetap 380/320) |
| Jumlah kartu feed awal | 24 | **10** (tombol "Tampilkan 24 lagi" tetap) |

Terukur pada viewport 1262×568, 10 tab: total tinggi halaman **23.996 → 21.208 px (−11,6%)**;
Recommendations **4.105 → 1.868 px (−54,5%)**; Overview **2.630 → 2.524 px**; KPI **2.386 → 2.270 px**.
Bukti angka: `_qa/ui-kompaksi/sebelum.json` & `sesudah.json`. Luapan horizontal 1440/375 px = 0.

#### Step 2 — blok penjelas dilipat (angka & tag tetap terlihat)

| Yang berubah | Sebelum | Sesudah |
|---|---|---|
| Baris daftar `.today-row` | 83–84 px (tombol "Buka" jatuh ke baris kedua karena `grid-column: 2` bertabrakan dengan pil tenggat) | **55–56 px** — grid `1fr auto auto`, tombol di kolom 3; ≤720 px kembali 2 kolom |
| `.role-hero` (panduan peran, tampil di 3 tab) | 140 px | **72 px** — misi + langkah masuk `<details>` "Panduan peran". **27 Okt 2026: blok itu DIHAPUS seluruhnya atas permintaan pemilik** (`.role-hero-more`, `.role-steps` ikut dihapus); yang tersisa hanya judul role + catatan batas domain peran, jadi tingginya turun lagi |
| Baris `.integration-row` (Agent Log) | ±70 px, kartu 777 px | **46 px**, kartu **497 px** — bukti & catatan per komponen di `<details>` |
| Kartu feed awal | 24 kartu | **10 kartu** ("Tampilkan 24 lagi" tetap) |

Total 10 tab: **23.996 → 20.714 px (−13,7%)**. Isi `<details>` tetap di DOM, jadi pembaca layar
dan tes tetap menemukannya; yang hilang hanya tinggi saat tertutup. Batas jujur: sisa blok tinggi
di KPI (11 tile × 212 px, isi 148 px + padding) dan tabel Pemasok (35 baris × ±56 px) adalah **isi**, bukan chrome.
### Rail (sidebar)
- Baris brand **setinggi top bar: 64px** (`min-height`), padding 10/16px; logo,
  avatar, dan tombol ikon semuanya **32×32**.
- Item nav (padat): `min-height: 38px`, padding `0 10px`, `gap: 3px` antar item
  (pitch 41px), ikon dalam **kotak tetap 16×16**, label `--fs-2` (13px) agar
  semua label mulai di kolom yang sama; warna ikon memakai token (`--ink-subtle`),
  bukan `opacity`. Batas sentuh 44px tetap ada lewat `@media (pointer: coarse)`
  dan baris mobile (≤720px), jadi yang kecil hanya rail desktop.
- **Arah panah tombol lipat ditentukan komponen, bukan CSS**: `ChevronIcon`
  merender `<` saat terbuka dan `>` saat tertutup. Jangan menambahkan
  `rotate(180deg)` — putaran itu membalik artinya (pernah terjadi, dan sidebar
  tertutup jadi menampilkan `<`).
- Rail terlipat (68px): padding samping dan `gap` **dinolkan** (label berlebar 0
  tetap menyumbang satu `gap` sehingga ikon bergeser 5px; tombol yang menyusut
  berlebar 0 tetap menyisakan padding+border 14px). Semua isi harus berada di
  pusat kolom: ikon = avatar = tombol lipat = pusat rail.

### Komponen inti
| Komponen | Fungsi |
|---|---|
| `LocationCard` | Ringkasan status satu lokasi |
| `StatusBadge` | Label warna (PASS/FAIL/NEEDS_VERIFICATION, surplus/shortage/tight) |
| `RecommendationCard` | Item di feed |
| `EvidenceTimeline` | Daftar bukti dengan indikator konsistensi |
| `AgentTraceViewer` | Timeline step agent, sumber dari AgentCore Observability |
| `KPICard` | Angka + trend |
| `ApprovalModal` | Konfirmasi sebelum eksekusi |
| `SafeDeliveredCostBreakdown` | Tabel komponen biaya |

### State yang wajib didesain untuk tiap komponen data
- Loading (skeleton, bukan spinner polos)
- Empty (dengan penjelasan, bukan kosong)
- Error (dengan retry action)
- Data stale/mock (badge kecil "Data Simulasi" untuk semua yang bersumber dari mock SAP)

## 5. Keputusan desain teknis

- **State management**: React Query untuk server state (polling Agent Activity Log tiap
  beberapa detik saat demo), tidak perlu Redux untuk skala MVP ini
- **Map**: MapLibre GL JS **TERPAKAI di frontend** (`frontend/components/SupplyMap.tsx`,
  sejak 2026-10-09) — tile raster OSM gratis tanpa API key, peta TERANG apa
  adanya, pin berwarna per status (token `--status-*`) + label mono
  nama/selisih, popup detail per lokasi (dibangun sebagai node DOM, bukan
  innerHTML — nama lokasi datang dari database), fitBounds otomatis dari
  koordinat database. Versi sementara SVG skematik sudah diganti.
  Chrome peta (arah Roy 2026-10-11): legenda putih mengapung kiri-bawah +
  kontrol bawaan MapLibre (`NavigationControl` kanan-atas, `AttributionControl`
  kanan-bawah) — tidak ada kepala/kaki panel tambahan. Logika murninya di
  `lib/map-console.ts` (`pinTone`, `pinLabel`, `nodeGauges`).
- **Chart**: Recharts (konsisten dengan chart proposal)
- **Component library**: shadcn/ui di atas Tailwind — cepat untuk build, mudah di-custom
  warnanya sesuai design token di atas
- **Real-time update**: polling sederhana (bukan WebSocket) untuk MVP — cukup untuk demo,
  lebih simpel diimplementasi dalam waktu terbatas

## Kontrak halaman "Keamanan Pangan" (kepala SPPG — ditetapkan 2026-10-16)

Halaman ini dipakai **kepala SPPG** (satu lokasi, satu dapur), bukan hanya
pengawas nasional. Aturan yang dipegang:

- **Cakupan dinyatakan, tidak dicampur.** Data yang ditampilkan ber-default
  LOKASI SENDIRI; tampilan jaringan hanya lewat pemilih cakupan yang eksplisit
  ("Lokasi saya — <nama>" / "Semua lokasi (pengawasan)") di kepala kartu tabel.
  Warna/istilah status tetap sama di kedua cakupan.
- **Setiap angka bisa ditelusuri ke satu endpoint.** Tiles + tabel dari
  `GET /batches`; kartu "Pasokan masuk" dari `GET /supplier-routes`; kalimat
  kebutuhan-vs-kiriman dari `GET /balance/map`; kartu "Keputusan keamanan" dari
  `GET /decisions` (ber-scope server-side). Tidak ada angka yang dikarang di
  komponen — nilai tak diketahui ditulis "—".
- **Masa layak = keadaan, bukan hanya persen.** Chip `Kedaluwarsa` (bahaya) /
  `≤48 jam` (peringatan) / `≤7 hari` (peringatan) muncul hanya untuk baris yang
  perlu ditindak; baris sehat tidak ditumbuhi lencana "Aman" (bising). Warna
  memakai token status yang sama dengan lencana/tile (kontras sudah teruji).
- **Tindakan harus benar-benar menulis.** "Periksa kiriman" / "Uji ulang" →
  `POST /freshness/evaluate` + `POST /safety/evaluate` (server menghitung ulang
  dari log suhu & umur panen yang tersimpan, lalu menyimpan) dan data diambil
  ulang sesudahnya; "Ajukan ulang" → `POST /actions/repropose`. Sesudah menulis,
  layar menampilkan hasil dari SERVER, bukan tebakan.
- **Tombol hanya untuk jalur yang sah.** `/actions/repropose` hanya menerima
  status `rejected` (dengan alasan) — keputusan yang cuma kedaluwarsa TIDAK
  mendapat tombol; kartunya menjelaskan aturan itu apa adanya.
- **Kartu "Penerimaan barang"** menjalankan langkah terima barang: lima titik
  periksa petugas (kemasan/suhu/bau-warna/timbang ulang/lot), pemilih batch
  (default = kiriman yang sedang datang bila bisa dipasangkan dengan batch
  nyata), **isian "Lainnya"**, dan tombol "Catat hasil terima & hitung ulang".
- **Opsi "Lainnya" (permintaan pemilik 2026-10-16, migrasi `016_batch_receipts`).**
  Petugas sering menghadapi keadaan yang tidak ada di daftar periksa, jadi ia
  bisa menuliskannya sendiri. Aturan yang dipegang:
  - Opsi ini **bukan titik periksa ke-6** — di luar `RECEIVING_CHECKS`, sehingga
    kalimat "N dari 5 titik periksa" tidak berubah artinya.
  - Catatannya **tersimpan di database** (`batch_receipts.other_note`, maks 500
    karakter); `POST /receipts` juga menyimpan snapshot titik periksa yang
    benar-benar dicentang (`checked`, JSONB), pencatat (`recorded_by`), dan
    waktu server (`recorded_at`) — catatan penerimaan tanpa pencatat bukan bukti.
  - Catatan yang hanya berisi spasi disimpan `NULL`: layar bisa membedakan
    "tidak ada catatan" dari "ada catatan".
  - Satu batch boleh punya banyak catatan (kiriman ulang/koreksi) — riwayat
    terakhir dibaca dari `GET /receipts?batch_id=…&limit=5` dan ditampilkan di
    kartu, sehingga isian itu **muncul lagi setelah halaman dimuat ulang**.
  - Peran: mencatat = `MUTATING_ROLES` **dan** batch wajib milik lokasi pemakai
    (`assert_in_scope`, ruling 2026-10-14 — barang diterima di dapur sendiri);
    membaca = semua peran terautentikasi (pengawas nasional harus bisa membaca).
- **Daftar periksa itu sendiri tetap tidak dipersistensikan sebagai "kebenaran
  resmi"** — yang tersimpan adalah apa yang benar-benar dicentang petugas pada
  saat itu (snapshot) plus hasil hitung ulang (`/freshness/evaluate` +
  `/safety/evaluate`). Snapshot sengaja disimpan apa adanya: kalau daftar
  periksa berubah nanti, baris lama tetap menggambarkan keadaan saat dicatat.
- **"Ajukan keputusan" per baris** hanya untuk baris **GAGAL UJI**, dan
  memanggil `POST /events/safety-disruption` (Event 3): server menilai ulang
  dari log suhu — batch gagal → 201 keputusan `safety_disruption` + bukti +
  jejak; batch aman → 200 `no_disruption` (layar bilang "tidak ada keputusan
  baru", tidak mengarang keputusan). Dua aturan yang dipegang komponen:
  `operation_key` adalah kunci idempotensi per batch (dibuat sekali, dikirim
  ulang saat mengulang → dilayani dari catatan, bukan keputusan kembar), dan
  `target_location_id` diambil dari `/auth/me` — WAJIB lokasi pemakai sendiri
  (ruling 2026-10-14), bukan dari baris yang diklik; batch pemicu boleh milik
  lokasi lain (sisi sumber).
- **Setiap path API baru wajib didaftarkan di DUA tempat**: `frontend/lib/api.ts`
  dan `API_ROOTS` di `frontend/next.config.js`. Tanpa itu, permintaan dari UI
  mendarat di Next sendiri dan membalas 404 HTML (terukur:
  "Tidak bisa memeriksa: HTTP 404: /freshness/evaluate"). Tes kontrak
  `tests/proxy-roots.test.ts` menjaga keduanya sinkron. (`/events` sudah terdaftar
  sejak awal, jadi Event 3 tidak menambah akar baru.)

**Kelas CSS baru (aman diuji):** `.board-card-head` (kepala kartu dengan aksi di
kanan), `.safety-scope` (baris pemilih cakupan), `.safety-state` +
`.safety-state-{expired,urgent,watch,unknown}` (chip keadaan masa layak),
`.safety-pick` (pemilih batch penerimaan), `.safety-checks` (daftar periksa —
matikan `::before` titik amber bawaan `.board-list` karena titik itu berarti
"mendesak", bukan "sudah diperiksa"), `.safety-other` (label + `<textarea>`
isian "Lainnya"), `.safety-notes` (riwayat catatan dari database; `::before`
dimatikan juga), `.board-subhead` (sub-judul di dalam kartu),
`.safety-row-actions` (tombol tindakan per baris tabel). Kelas tes-sensitif
(`.map-*`, `.side-tab*`, `.board-table-wrap`, `.commodity-pill`) tidak diubah.

---

## Kontrak kartu "Informasi pengiriman" (Arah A — riset 2026-10-16)

Keputusan pemilik: setelah riset pembanding industri
(`docs/research/informasi-pengiriman-industri.md`, 11 sumber), arah yang dibangun
adalah **"Kartu Kiriman"** — bukan papan tabel (Arah B) dan bukan panel samping
peta (Arah C). Alasan: menutup paling banyak kesenjangan tanpa satu pun field
backend baru, karena seluruh angkanya sudah dikirim `GET /supplier-routes`.

**Di mana:** tab Overview (di bawah baris peta, memakai jalur yang sekomoditas
dengan tampilan) dan halaman Pemasok (seluruh jalur aktif). Tab Keamanan Pangan
BELUM memakai kartu ini — di sana sudah ada kartu "Pasokan masuk" dengan aksi
"Periksa kiriman"; menyatukannya menyentuh berkas yang sedang disunting sesi
lain, jadi dicatat sebagai langkah berikutnya.

**Empat lapis informasi** (satu kiriman = satu blok, dari paling cepat dibaca):
1. judul `Pemasok → Tujuan` + pil status (keadaan + sisa waktu, mis.
   `Di jalan · 20 menit lagi`);
2. stepper empat tahap `Dipanen → Berangkat → Di jalan → Tiba` (tahap aktif
   disorot, tahap yang tak bisa dipastikan = lingkaran putus-putus);
3. satu baris angka kunci `110,4 km jalan · ± 1 jam 24 menit · 800 kg telur`;
4. kalimat keputusan (`Tiba ± 14.20 WIB, masih sebelum batas layak 16 Okt 2026.`),
   lalu rincian lengkap di balik `<details>` — isinya tetap ada di DOM saat
   tertutup, dan panelnya bekerja tanpa JavaScript.

**Aturan yang mengikat** (dikunci `tests/shipment-card.test.ts` +
`tests/shipment-card-component.test.tsx`, 37 tes):
- **Tidak ada angka karangan.** Geometri jalur hilang → yang ditulis adalah jarak
  LURUS berlabel "lurus (jarak udara)" + sebab dari server (`road_missing_reason`);
  "0,0 km" tidak pernah muncul, dan waktu tempuh tidak diklaim.
- **"Belum ada data" ≠ "terlambat".** Tahap tak pasti memakai nada netral/putus-
  putus; simpangan "terlambat N menit" sengaja TIDAK ditampilkan karena model kita
  belum punya waktu tiba yang dijanjikan — angka simpangan apa pun akan karangan.
- **Jam tiba tidak pernah dihitung di peramban**: seluruh angka waktu datang dari
  `journey` server.
- Pil memakai aturan `.badge`: satu baris, `flex: none`, `--fs-1` (12px) — terukur
  111×22 px untuk `Sudah tiba 19.24`.
- Warna memakai token status yang ada (`--accent*`, `--ok-*`, `--danger-*`,
  `--neutral-*`); **tidak ada warna baru** dan tidak ada ukuran font baru.

**Terukur (1440 px, data seed 1 kiriman):** kartu 1140×223 px saat rincian
tertutup, 1140×401 px saat dibuka (rincian menambah 178 px); satu blok kiriman
128 px; luapan horizontal 0 px di 375 / 768 / 1280 / 1440 px; di 375 px kartu
menyusut ke 331 px tanpa teks terpotong.

---

## Tahap 2 (16 Okt 2026) — pil, lencana, dan kartu yang direntangkan

Lanjutan sapuan yang sama (keluhan pemilik: bentuk lebih besar dari teksnya).
Tiga aturan yang sekarang berlaku, semuanya terukur sebelum → sesudah:

**1. `.commodity-pill` — bentuk mengikuti teks, bukan sebaliknya.**
`padding: 2px 10px; font-size: var(--fs-1)` (dulu `5px 14px` + 13px). Pil kepala
halaman: 32 → **22 px**. Pil penyaring komoditas (`.filter-card .commodity-pill`,
13px): 30 → **24 px**. Pil kepala halaman adalah TEKS STATIS (span) sehingga
`.page-header-pills > .commodity-pill` dikecualikan dari aturan target sentuh
(`min-height: 0` + `cursor: default`) — tetap 22 px bahkan di 375 px. Sebaliknya
kontrol yang benar-benar ditekan (penyaring komoditas, cakupan keamanan) TETAP
44 px di `@media (pointer: coarse)` / ≤720 px — terverifikasi di 375 px.

**2. `.today-badge` disamakan dengan `.badge`:** `--fs-1` + `line-height: 1.35` +
`flex: none` + `white-space: nowrap` → 26 → **22 px** (dulu satu-satunya lencana
13px di app ini).

**3. `.board-grid { align-items: start }` — kartu tidak lagi direntangkan setinggi
tetangganya.** Terukur: "Batch perlu segera dipakai" di Keamanan Pangan
562×423 px dengan isi hanya 72 px (**17%**) semata karena kartu sebelahnya lebih
tinggi → sekarang 562×**117 px** (61% berisi). Efek samping yang diinginkan:
tabel "Rincian per run" di KPI menyusut 532 → 401 px karena lencana di dalam
barisnya ikut ramping.

**Gerbang:** tsc 0 · suite frontend **774 lulus / 69 berkas** · luapan horizontal
0 px di 375/768/1440 px untuk 9 tab (Hari Ini, Overview, Recommendations,
Decision & Evidence, Keamanan Pangan, Surplus & Limbah, Pemasok, Agent Log, KPI).

**Keputusan pemilik (16 Okt, setelah melihat angka di atas):** tabel "Rincian
Pasokan per Lokasi" **DIHAPUS**, kartu "Status Lokasi" **dipertahankan**. Jadi
Overview tidak lagi punya dua penyaji angka yang sama: daftar ringkas + legenda
warna di kartu, dan grafik batang "Pasokan per lokasi" untuk gambaran cepat.
Berkas yang dihapus (masih ada di git bila perlu dikembalikan):
`components/OverviewLocationBreakdown.tsx`, `.../OverviewLocationBreakdown.module.css`,
`tests/overview-location-breakdown.test.tsx`. Teks aksesibilitas grafik ikut
diperbaiki: dulu ia menunjuk "…di tabel Rincian Pasokan per Lokasi" (sekarang
menunjuk "…di kartu Status Lokasi") — teks bantuan yang menunjuk elemen yang
sudah tidak ada lebih buruk daripada tidak ada teks.

**4. Orphan kata di baris terakhir daftar (Hari Ini).** `.today-row-meta` dan
`.today-row-title` diberi `text-wrap: pretty`. Terukur sebelum: "250 kg ·
kesegaran 0% · lolos uji" membungkus dengan baris terakhir **18 px** (hanya kata
"uji") karena pil "Lewat N hari" di kolom kanan menyempitkan kolom teks →
sesudah: baris terakhir **58 px** ("lolos uji" utuh). Peramban lama yang belum
mengenal `pretty` hanya kehilangan kerapian ini, bukan keterbacaan.

**5. Kartu kiriman menggantikan daftar ringkas "Pasokan masuk" (tab Keamanan
Pangan), 16 Okt 2026.** Daftar lama menyajikan angka jalur yang sama dengan
kartu (jarak jalan, waktu tempuh, rasio, mutu, masa layak) dan halaman itu belum
punya TAHAP perjalanan — jadi yang dipertahankan bukan dua penyaji angka, tetapi
satu penyaji angka + stepper. Tombol **"Periksa kiriman"** tetap ada, kini
menempel pada kirimannya lewat prop baru `action`.

Kontrak `ShipmentCard` bertambah tiga prop (semuanya opsional, perilaku lama
tidak berubah):

| Prop | Guna |
|---|---|
| `hanya` | Menyaring baris SEBELUM dipilih (mis. hanya kiriman menuju lokasi SPPG ini). Baris di luar cakupan TIDAK dihitung sebagai `hidden` — angka "+N lain" hanya bicara soal baris yang termasuk cakupan. |
| `empty` | Pesan pengganti saat tidak ada kiriman. Tanpa prop ini kartu tetap tidak dirender sama sekali (aturan lama: kartu kosong lebih buruk daripada tidak ada kartu). |
| `action` | Tindakan per kiriman, dirender di dalam blok kiriman (`.shipment-action`, rata kanan). |

Penyaringnya hidup di logika murni `pickShipments(rows, maks, hanya)` — bukan di
JSX — supaya hitungan sisa ikut tersaring dan bisa diuji tanpa DOM.

**Terukur (SPPG Head, lokasi Jakarta, 1440 px):** satu kartu
`Pasokan masuk menuju Jakarta` 1140×264 px, 1 kiriman, 4 tahap stepper, tombol
"Periksa kiriman" ada, panel rincian ada; teks lama "… jalan · … mutu …" **0
kemunculan**; hanya SATU judul "Pasokan masuk…" di halaman; luapan horizontal
0 px (di 375 px kartunya 331×384 px, tombol dan stepper tetap utuh).

---

## Papan kiriman (Arah B riset 16 Okt 2026) — satu baris per KIRIMAN

Halaman **Pemasok**. Sepuluh kolom: Pemasok · Tujuan · Muatan · Jalur · Berangkat
· Estimasi tiba · Sisa · Masa layak · Mutu · Keadaan, dengan kontrol urutan
"Paling mendesak" (bawaan) / "Estimasi tiba" / "Batas layak" — bentuk pil yang
sama dengan `.kpi-period` (pill + `aria-pressed`, 44 px di perangkat sentuh).

**Peran yang digantikan:** papan ini mengambil alih peran kartu ringkas Arah A
DAN kolom teks "Jalur kirim" **di halaman ini saja** (tabel pemasok tetap punya
kolomnya sebagai ringkasan per pemasok, grain-nya berbeda). Alasannya sama dengan
keputusan Overview: satu halaman = satu penyaji angka yang sama. Kartu Arah A
tetap di Overview dan Keamanan Pangan, di mana justru stepper + kalimat
keputusan yang dicari.

**Aturan jujur yang dipegang (diuji di `tests/shipment-board.test.ts`):**

- Tanpa geometri jalan → sel menulis jarak lurus berlabel + sebabnya
  (`road_missing_reason`); tanpa keduanya → "—" (dengan sebab dalam tanda kurung
  kalau server memberikannya). Tidak pernah "0 km".
- **Sisa waktu hanya untuk perjalanan yang SEDANG berjalan.** Kiriman yang sudah
  tiba atau belum berangkat → "—"; kolom Keadaan di sebelahnya yang menjelaskan.
  (Terbukti perlu: data seed sempat membawa `remaining_min = 197 jam` pada
  kiriman berkeadaan "sudah tiba" — angka itu akan menyesatkan.)
- **Sel waktu ringkas "8 Okt 18.00"** (tanpa tahun) dengan **tooltip waktu
  lengkap** ("8 Okt 2026 18.00 WIB"). Tahun tidak hilang: ada di kolom Masa layak
  dan di tooltip. Tanpa ringkasan ini sepuluh kolom tidak muat di 1440 px dan
  kolom Mutu/Keadaan terpotong.
- Urutan selalu menaruh baris tanpa data di **belakang** (bukan dianggap 0), dan
  nama pemasok jadi pemutus terakhir supaya urutannya bisa diprediksi.

**Terukur:** di 1440 px lebar ISI tabel = lebar pembungkus = **1106 px** → tidak
ada gulir mendatar, kesepuluh kolom terlihat penuh; di 375 px isi 1065 px
digulir DI DALAM pembungkusnya (`.board-table-wrap`) dan luapan halaman tetap
**0 px**. Ukuran huruf tabel 12 px (lantai tipografi repo) — hanya tabel papan,
bagian halaman lain tidak berubah. Tangkapan: `ui-audit/t4-papan-1440.png`.

---

## Riwayat kejadian per kiriman (kesenjangan #12 riset, 16 Okt 2026)

Tempatnya **di dalam panel `Rincian kiriman`** yang sudah ada — bukan kartu atau
bagian baru di halaman. Alasannya dua: panel itu memang sudah dipakai untuk angka
rinci, dan menambah bentuk baru di halaman justru berlawanan dengan arah
perbaikan (mengurangi pembungkus, bukan menambah).

Isi: `Riwayat kiriman · N kejadian tercatat` lalu daftar **terbaru dulu**, tiap
baris = judul (kiri) + waktu lengkap WIB (kanan, huruf data) + keterangan di
bawahnya bila ada. Terakhir, satu catatan kaki audit yang dipisah garis.

**Empat aturan jujur yang dipegang (semua diuji di
`tests/shipment-timeline.test.ts`):**

1. **Hanya kejadian yang PUNYA WAKTU di server** yang masuk daftar. Model kita
   menyimpan `safety_status` tetapi TIDAK menyimpan waktu pemeriksaannya, jadi
   baris "uji mutu" tidak dibuat — tanggalnya tidak boleh dikarang. Mutu tetap
   tampil sebagai keadaan di kartu.
2. **"Perkiraan" dipisah dari "kejadian".** Estimasi tiba ditandai `kind:
   "rencana"` → judulnya berwarna redup + tag pil "perkiraan", supaya tidak
   terbaca seolah barangnya sudah tiba. Kiriman yang sudah tiba menampilkan
   kejadian "Tiba di tujuan" sebagai gantinya.
3. **Waktu hitung jalur BUKAN kejadian**, melainkan catatan kaki audit
   (`shipmentRouteAudit()`). Ini keputusan yang lahir dari pengukuran: waktu itu
   adalah kapan SERVER menghitung (pada demo selalu "hari ini"), sehingga saat
   dijadikan baris kejadian ia duduk di ATAS kejadian "Tiba" bertanggal lebih
   awal dan garis waktunya terbaca rusak. Nilainya tetap dibuka karena bagian
   dari jejak audit.
4. **Waktu yang tidak terbaca tidak masuk daftar** (bukan ditulis "—"), dan bila
   tidak ada satu pun waktu, bloknya tidak dirender sama sekali — tidak ada blok
   kosong berisi teka-teki.

**Terukur (SPPG Head, Overview, 1440 px):** tiga baris riwayat, tinggi tiap baris
46–47 px, kartu terbuka 1140×608 px (sebelum riwayat 401 px untuk 4 baris fakta,
jadi riwayat menambah ± 200 px HANYA saat panel dibuka). Tanpa luapan halaman
(0 px) di 1440 maupun 375. Selisih judul-ke-waktu 784–845 px → tidak ada
tumpang tindih.

Satu bug tata letak ditemukan lewat tangkapan layar dan sudah diperbaiki: kolom
waktu dengan lebar tetap (`minmax(0, 16ch)`) lebih sempit daripada
"16 Okt 2026 07.00 WIB", sehingga tanggal MENABRAK judulnya. Sekarang judul dan
waktu berada pada satu baris flex (judul kiri, waktu kanan) — tidak ada kolom
lebar tetap yang bisa kalah dari isinya.

---

## Sorotan kiriman di peta — Arah C (16 Okt 2026)

Riset §6: *"Pilih jalur di peta → panel berisi stepper + rincian + riwayat; garis
jalur disorot, segmen yang belum ditempuh digambar putus-putus."*

**Yang dibangun.** Di kartu peta Overview, di bawah kanvas, ada baris
`Pilih kiriman: [Semua (N)] [Pemasok → Tujuan · keadaan]` (`.route-focus`).
Memilih satu kiriman: (1) garisnya di peta ditarik **padat** untuk bagian yang
sudah ditempuh dan **putus-putus** untuk sisanya, (2) kartu `Informasi
pengiriman` di bawah baris peta **menyaring ke kiriman itu** dan menuliskan
`Menampilkan kiriman terpilih di peta: … (N kiriman lain disembunyikan)`.
Kembali ke semua: tekan `Semua (N)`.

**Kenapa ada TOMBOL pemilih, bukan hanya klik di peta.** Garis di kanvas
MapLibre tidak bisa difokus keyboard dan tidak ada di pohon aksesibilitas.
Klik garis di peta TETAP menyorot kiriman yang sama (dan popup jalur yang sudah
ada tetap muncul seperti sebelumnya — pemilik pernah memangkasnya sendiri di
Fase 12b, jadi tidak dihapus tanpa izin), tetapi tombol inilah jalur setaranya.

**Satu nilai untuk dua tampilan.** `focusedRoute` di `app/page.tsx` dikirim ke
PETA dan ke KARTU sekaligus; tidak ada salinan keadaan di dua tempat, sehingga
garis yang menyala dan angka di kartu tidak bisa berbeda cerita.

**Aturan jujur yang dipegang (diuji):**
- **Gagal-tertutup**: id tak dikenal/kosong/kosong-string = tampilan SEMUA
  (bukan tebakan "kiriman pertama") — pola yang sama dengan `activeLocation`.
- **Sudah tiba → seluruh garis padat**, walau `progress` tidak dikirim. Keadaan
  itu datang dari server dan artinya tidak ambigu; menebak 0% akan menggambar
  perjalanan yang sudah selesai sebagai "belum ditempuh".
- **Tanpa `progress` (dan belum tiba) → garis utuh putus-putus**, sama dengan
  garis dasar. Tidak ada klaim sudah berjalan, dan tidak ada garis lurus palsu
  ketika geometri jalan tidak ada (tidak ada yang digambar sama sekali).
- **Potongan mengikuti PANJANG tiap segmen**, bukan jumlah titik; titik sambung
  dihitung presisi penuh (haversine meter) — pembulatan `haversineKm` (km bulat)
  akan salah memotong segmen pendek.
- Saat sorotan dilepas, layer DAN source-nya dibuang — tidak boleh ada garis
  sorotan tertinggal untuk kiriman yang sudah dilepas (diuji di DOM tiruan peta).

**Terukur (SPPG Head, Overview):** pemilih 22 px satu baris di 1440, 94 px
terbungkus di 375 (target sentuh 44 px terjaga), luapan halaman 0 px di kedua
lebar. Bukti grafis sorotan diukur dengan **beda piksel**, bukan mata: baseline
peta stabil (beda antar dua tangkapan tanpa aksi = 45 px), saat disorot muncul
**28.584 px** berbeda, dan citra bedanya persis mengikuti jalur Cianjur →
Jakarta; setelah dilepas, beda di area jalur hilang (yang tersisa 27.797 px ada
di bilah tombol lapisan — teks angka yang berdenyut karena polling 5 detik,
bukan garis). Alat: `cek-pixel-arah-c2.py` (pillow) + `ui-audit/c3-beda-*.png`.

**Catatan kontras yang BELUM diubah (minta keputusan pemilik).** Garis dasar di
peta digambar **putus-putus untuk semua kiriman** (`line-dasharray: [2, 1.2]`),
padahal riset menetapkan putus-putus = "belum ditempuh". Sesudah Arah C,
perbedaannya mulai terlihat: garis yang disorot padat, sisanya putus-putus.
Mengubahnya bukan keputusan UI kecil (garis dasar muncul di setiap tangkapan
layar demo), jadi dibiarkan dan dilaporkan.

**Berkas:** `frontend/lib/route-focus.ts` (murni) + `frontend/lib/route-line-split.ts`
(murni) + `frontend/components/RouteFocusPicker.tsx` + perubahan di
`frontend/components/SupplyMap.tsx` dan `frontend/app/page.tsx`.
Tes: `tests/route-focus.test.ts` (8), `tests/route-line-split.test.ts` (10),
`tests/route-focus-line.test.ts` (6), `tests/route-focus-picker.test.tsx` (4),
`tests/supply-map-layer.test.tsx` (+6).

## Peta operasional — arah desain dari riset (Langkah 7a, BELUM dikerjakan)

Acuan yang dipilih (detail, kutipan verbatim, dan celah lengkap: `docs/research/peta-ui-industri.md`):

- Peta adalah konten utama, bukan pelengkap; hierarki visual harus disengaja ("squint test")
  — Axis Maps Cartography Guide [21], ArcGIS *application layouts* [15].
- Kontrol peta dibagi tiga kategori — Informational (kredit, **skala**), Viewport (**tombol reset tampilan**),
  Visualization (toggle lapisan) — Google Maps [4]. Dua yang bercetak tebal belum kita punya.
- Setiap toggle lapisan dipasangkan legenda; legenda harus terlihat **tanpa klik tambahan** dan
  menyebut sumber/umur data — Bathyl [8].
- Target sentuh kontrol ≥ 44 px, kontras teks di atas peta ≥ 4.5:1, dan setiap aksi peta harus
  punya padanan di panel (peta raster tak bisa difokus keyboard) — Admiralty [16], W3C/NSGIC [5][6].
- Garis putus-putus berarti "belum pasti / belum jadi / belum ditempuh" — ISOM 2000 [17], USGS [18].
  Ini konfirmasi konvensi untuk aturan Arah C (sisa perjalanan = putus-putus).
- Tooltip di peta untuk info singkat; cerita panjang di panel tetap — Axis Maps [22], NN/g [13].

Keadaan terukur SETELAH 7b-1/7b-2/7b-3 (19 Okt 2026): kartu peta 752×528 px @1440 /
331×502 px @375; kontrol MapLibre 29×29 px di desktop dan **44×44 px** di `(pointer: coarse)`;
sakelar lapisan **32×32 px** di desktop dan **44×44 px** di layar sentuh; tombol "Rincian lapisan
peta" 44 px di layar sentuh. Tombol "Tampilkan semua" (reset ke batas awal) ada sejak 7b-1. Bilah
skala sempat ada (7b-1) lalu **dihapus 19 Okt 2026** atas permintaan pemilik — kiri-bawah dipakai pil
sakelar lapisan (§14.4). Jadi butir 1 pada daftar riset di atas kini terpenuhi SEBAGIAN: reset ada,
skala tidak — keputusan pemilik, bukan kelalaian. Legenda terbaca tanpa klik (baris di bawah kanvas) dan "Info map"
sudah tidak ada sebagai panel terpisah (lihat §14).

Urutan kerja: **7b-1 SELESAI 17 Okt** → **7b-2 SELESAI 17 Okt** (legenda terlihat tanpa klik, satu zona
"Info peta", chip penanda filter aktif, cooperative gestures di perangkat sentuh) → **K5 dari 7b-3 SELESAI
17 Okt** (seed tiga keadaan perjalanan; lihat §7b-3 di bawah) → sisa 7b-3 menunggu giliran: K1 arti garis
padat/putus-putus, K3 daftar penanda bernama + padanan sr-only, K4 popup jalur satu baris. K2 (melebarkan
peta) diputuskan TIDAK dikerjakan.

### 7b-1 — kontrol peta (selesai 17 Okt 2026)

Berkas: `frontend/lib/map-view.ts` (baru, murni) + `frontend/components/SupplyMap.tsx` +
`frontend/app/globals.css` (gaya `.map-reset-view` & `.maplibregl-ctrl-scale`, dan blok kontrol peta di
`@media (pointer: coarse), (max-width: 720px)`). Tes: `tests/map-view.test.ts` (6 murni) +
`tests/supply-map-layer.test.tsx` (+5 kontrak).

Angka terukur (SPPG Head, Overview): bilah **skala "30 km"** (sebelumnya tidak ada; ditaruh kanan-bawah di
langkah ini, lalu **dipindah ke kiri-bawah di 7b-2** setelah legenda turun dari kanvas);
tombol **"Tampilkan semua"** (`.map-reset-view`, `<button>` asli, ikon empat sudut, `aria-label` tetap +
`title` "Kembalikan tampilan ke semua N lokasi[ dan jalur kiriman]") — 29 px desktop, **44 px** di 375 px;
grup MapLibre 29×29 → **44×44** di 375 px; chip toggle lapisan / "Info map" / "Rincian lapisan peta"
26/24 px → **44 px** di 375 px; luapan halaman 0 px; **tanpa tumpang tindih** kontrol (diperiksa berpasangan).
Audit kontras: terendah **4,55:1** (tag bilah lapisan) — lulus 4,5:1; atribusi peta tidak diubah karena
memang hanya berisi kredit.

Pelajaran yang ditulis ke kode: `.map-layer-toggle` dkk. sempat 26/24 px di ponsel karena `min-height`
kelas MENANG atas `button { min-height: 44px }` — jadi target sentuh 44 px harus ditulis eksplisit pada
media query, bukan diwariskan dari aturan `button` global.

**Jebakan MapLibre yang wajib diingat:** sudut kontrol MapLibre memakai `pointer-events: none` dan
mewariskannya ke anak. Kontrol bawaan diselamatkan kelas `.maplibregl-ctrl { pointer-events: auto }` yang
ditambahkan MapLibre sendiri — **kontrol buatan sendiri TIDAK dapat kelas itu**, jadi wajib menulis
`pointer-events: auto` pada gayanya. Tanpa itu kontrolnya terlihat tapi mati. Dijaga oleh
`tests/map-controls-css.test.ts` (bersama kontrak 44 px). Tombol reset juga dibuktikan bekerja dengan
klik sungguhan di browser: pin `[614,741]` → digeser `[201,485]` → setelah tombol diklik `[633,731]`.

### 7b-2 — satu zona kendali & legenda tanpa klik (selesai 17 Okt 2026)

Berkas: `frontend/lib/map-legend-compact.ts` (baru, murni) + `frontend/lib/route-focus.ts` (chip saringan) +
`frontend/lib/map-view.ts` (gestur kooperatif + pesan Indonesia) + `frontend/components/SupplyMap.tsx` +
`frontend/app/globals.css`. Tes: 35 baru (8 murni legenda, 3 murni saringan, 6 murni gestur, 16 kontrak peta,
2 kontrak CSS).

Empat perubahan yang terlihat:

1. **Baris legenda ringkas di bawah kanvas** (`.map-legend-compact`) — makna titik/garis terbaca TANPA satu
   klik: 752×18 px @1440, 331×40 px @375 (2 baris), 4 tanda. Status lokasi selalu ada (pin SPPG tidak punya
   sakelar); butir jalur/pemasok hanya muncul saat lapisannya hidup — keterangan warna tanpa lapisan =
   informasi palsu. Tandanya memakai kelas `.map-legend-box-*` yang sama dengan kotak Info map.
2. **Satu elemen mengapung di kanvas.** Chip "Info map" masuk ke pil kendali kiri-atas; isinya turun ke
   bawah kanvas (`.map-legend-detail`, ikut alur). Terukur: elemen kendali aplikasi yang mengapung SENDIRI di
   kanvas **2 → 1** (tombol "Tampilkan semua" & skala tidak dihitung — keduanya di sudut kontrol MapLibre
   bersama tombol zoom, tempat yang memang benar untuk kontrol peta); membuka Info map menambah tinggi kartu
   (554 → 649 px) tanpa menyentuh tinggi kanvas (460 px).
   Panggung absolut lama `.map-legend-stack` DIHAPUS — bukan dipakai ulang dengan penimpa posisi.
3. **Chip saringan aktif di atas kanvas** (`.map-filter`, ikut alur): "Menyaring: Supplier A Cianjur →
   Jakarta" + tombol "Lepas" yang mengirim `FOCUS_ALL`. Nama kirimannya dari `focusLabel` yang sama dengan
   pil pemilih & kartu. Alur diuji hidup: 554 → 590 px saat menyaring, kembali 554 px setelah "Lepas".
4. **Gestur kooperatif hanya untuk perangkat sentuh** (`pointer: coarse`): satu jari menggulir halaman
   (scrollY 0 → 2579), dua jari menggeser peta (pin 160,186 → 10,36 = 300 px; halaman diam). Desktop tetap
   roda tetikus = zoom. Pesan layar MapLibre (Inggris) diganti bahasa Indonesia dan latarnya dipergelap
   `rgba(15,23,42,.66)` (bawaan `rgba(0,0,0,.4)` hanya ±2,8:1 dengan teks putih).

Tiga keputusan yang diambil saat mengerjakan: isi "Info map" tetap LENGKAP (duplikasi 3–5 butir dengan baris
ringkas disengaja — ringkas untuk makna sekejap, kotak untuk rincian perjalanan/asal geometri); skala
dipindah ke kiri-bawah (posisi bawaan MapLibre, bukan zona atas seperti usul riset, karena acuan industri
menaruh skala di sudut bawah); gestur kooperatif TIDAK berlaku di desktop (mode MapLibre mengubah desktop
juga, dan keluhan yang diperbaiki hanya gulir halaman di ponsel).

### 7b-3 — K5: tiga keadaan perjalanan di seed (selesai 17 Okt 2026)

Berkas: `data/seed/sprint1_seed.json` + `backend/app/seed/seed_data.py` + `backend/app/api/demo.py` +
`frontend/app/page.tsx`. Tes baru: `backend/tests/test_seed_jakarta_journey_states.py` (4),
`backend/tests/test_demo_refresh_routes.py` (2), `backend/tests/test_seed_menu_plan_anak.py` (1).

Masalahnya: pemilih kiriman hanya berisi "Semua (1)" + satu kiriman "Sudah tiba", sehingga garis sisa
perjalanan, tag "perkiraan", dan alur peta→keputusan→bukti tidak bisa diperagakan. Sekarang seed Jakarta
memuat tiga kiriman **satu komoditas** (telur) dari tiga pemasok berbeda supaya ketiganya tampil di pemilih
yang disaring komoditas:

| Kiriman | Berangkat | Keadaan |
|---|---|---|
| Supplier A Cianjur | −21 menit (rute 84 menit) | Di jalan · ± 1 jam 2 menit lagi, 27% jalur |
| Supplier Bogor-1 | −2,5 jam | Sudah tiba 10.32 |
| Supplier D Cianjur | `null` | Belum berangkat |

Jam relatif terhadap "hari ini", jadi tetap benar setelah "Segarkan ke hari ini" — bukan tanggal mati.

Dua bug yang ketemu saat memverifikasi dan diperbaiki (keduanya memblokir tombol demo):

1. **`POST /demo/refresh` → 500** (bukan bug K5): upsert `menu_plans` mengganti **PK** baris `origin='demo'`
   di tanggal kanonik (id demo → id kanonik) sementara `delivery_events` masih merujuk id lama →
   `ForeignKeyViolationError`, dan satu tanggal bentrok menggagalkan SELURUH refresh. Perbaikan: baris demo di
   tanggal itu **diadopsi** (isi + `origin` jadi `seed`, **id dipertahankan**), anak-anaknya diarahkan lewat
   peta id aktual (`peta_plan`). Tidak ada PK yang diganti. Dijaga tes `test_seed_menu_plan_anak.py` (merah
   dulu, hijau setelah perbaikan).
2. **Peta tidak ikut segar setelah refresh**: `onDataChanged` hanya me-refetch keputusan, peta & pemilih
   kiriman tetap memakai cache → tombol "Segarkan ke hari ini" terasa tidak bekerja sampai halaman dimuat
   ulang. Perbaikan: `mapQuery.refetch()` + `mapSupplierRoutesQuery.refetch()`.

### 7b-3 — K1: satu arti untuk bentuk garis (selesai 17 Okt 2026)

Berkas: `frontend/lib/route-line-split.ts` (`journeyLineParts`) + `frontend/lib/supplier-routes.ts`
(`routeGeoJson` kini mengirim DUA fitur per kiriman, properti `kind`; `routeLegendEntries` membawa `gaya`) +
`frontend/components/SupplyMap.tsx` (satu source, dua layer: `supplier-route-line-done` padat,
`supplier-route-line-todo` putus-putus, klik popup terpasang di KEDUANYA) + `frontend/lib/map-legend-compact.ts`
(`gaya` ikut kelas tanda) + `frontend/app/globals.css` (`.map-legend-line-padat` / `-putus`). Tes: 6 murni
(`journeyLineParts`) + 3 kontrak GeoJSON + 1 legenda + asersi layer di `supply-map-layer.test.tsx`.

Masalahnya: legenda menulis "Sisa perjalanan" putus-putus, tetapi LAYER menggambar SEMUA kiriman
putus-putus — termasuk yang "Sudah tiba 19.24". Sekarang bentuk garis ditentukan keadaan perjalanan dari
server:

| Keadaan | Bentuk garis |
|---|---|
| `sudah_tiba` | seluruhnya padat (walau `progress` tidak dikirim — keadaan tidak ambigu) |
| `di_jalan` + `progress` | padat sampai titik tempuh, putus-putus sisanya |
| `belum_berangkat` | seluruhnya putus-putus |
| perjalanan tidak dilaporkan / `progress` null | putus-putus (garis itu perkiraan) |

Catatan teknis: `line-dasharray` MapLibre **tidak bisa data-driven** (hanya konstanta/zoom), jadi pemisahan
dilakukan lewat dua layer dengan filter `kind` pada satu source. Klik popup dipasang di kedua layer — kalau
hanya di layer putus-putus, kiriman yang sudah tiba kehilangan popup karena garisnya padat semua.

Terukur di aplikasi hidup (1440 px, setelah "Segarkan ke hari ini"): legenda ringkas menulis "Sudah ditempuh ·
Sisa perjalanan (perkiraan)" dengan `border-top-style` **solid** dan **dashed**; analisis komponen piksel
kanvas menemukan **komponen hijau terbesar 780 px menyambung** (tidak mungkin dari garis putus-putus) di
samping **40 komponen <20 px** — dua gaya garis memang tergambar bersamaan. Garis Supplier Bogor-1 (sudah
tiba) tampak menyambung penuh Jakarta→Bogor, sementara jalur Cianjur putus-putus.

## 8. Data hidup: satu tulis menyegarkan SEMUA panel (selesai 17 Okt 2026)

Permintaan pemilik: "saya akan mencoba semua fitur di setiap role, jadi semua bagian yang menampilkan
informasi itu juga datanya realtime dengan DB — ketika saya melakukan sesuatu, pastikan semuanya berjalan
sesuai."

**Temuan audit (bukan dugaan):** repo ini **tidak punya satu pun `useMutation` atau `invalidateQueries`**.
Setiap aksi hanya me-refresh query yang diingat komponennya. Akibatnya kelas bug yang sama muncul berkali-kali
(peta tidak menyegar setelah "Segarkan", Pemasok/KPI tetap memakai cache 5 menit). Tiga hook bahkan tidak
punya polling (`useSuppliers`, `useSupplierRoutes`, `useExclusions`) dengan `staleTime` 5–10 menit.

**Aturan yang sekarang berlaku** (`frontend/lib/refresh.ts`, dipanggil `lib/api.ts` + `lib/supplier-exclusions.ts`
dan didaftarkan di `app/providers.tsx`):

| Metode | Sesudah respons sukses |
|---|---|
| GET/HEAD | tidak menyegarkan apa pun |
| POST/PUT/PATCH/DELETE | `queryClient.invalidateQueries()` — SELURUH cache |

Konsekuensi yang diinginkan: panel yang sedang tampil langsung mengambil ulang; panel yang belum terbuka
ditandai basi sehingga mengambil ulang saat dibuka, **walau `staleTime` 5 menit**. Modul yang punya pembungkus
`fetch` sendiri (`supplier-exclusions.ts`, dibuat supaya pesan `detail` validasi tidak hilang) wajib memanggil
aturan yang sama — kalau tidak, ia menjadi satu-satunya jalur tulis yang meninggalkan panel lain basi.

Terukur di aplikasi hidup: satu `POST /demo/refresh` → **8 endpoint** diambil ulang dalam 26 permintaan, semua
**200**; tab Pemasok & KPI (keduanya tanpa polling) tetap memanggil `/suppliers` dan `/kpi` saat dibuka sesudah
aksi itu (`suppliers_dipanggil=true`, `kpi_dipanggil=true`).

## 9. Kegiatan demo: aplikasi tidak boleh tampak kosong (selesai 17 Okt 2026)

Permintaan pemilik: "buat data mock yang lumayan banyak supaya terlihat aktiv website ini."

`backend/app/seed/demo_activity.py` menambah dua kelompok baris **`origin='demo'`** yang idempoten
(UUID5 deterministik) dan ikut terhapus oleh "Bersihkan data demo":

1. **Kiriman** — 4 per lokasi × 10 lokasi = **40 batch** (4 komoditas bergilir, tiga keadaan perjalanan),
   supaya peta, papan kiriman, dan pemilih kiriman punya bahan nyata. Rute jalan disinkronkan OSRM:
   **47 pasangan diperiksa, 37 diambil, 0 gagal**.
2. **Keputusan selesai + limbah** — 3 keputusan (Jakarta/Bandung/Surabaya) dengan jejak `DETECT..ACT`,
   dua bukti konsisten SEBELUM approval, approval manusia, `safe_delivered_cost`, dan PO mock hari ini;
   plus 2 kejadian limbah hari ini. Ini bukan hiasan: empat kartu KPI membaca baris-baris inilah.

Hasil pada periode **24 jam** (SPPG Head, 17 Okt): **7/7 metrik `tersedia`** — Meal Continuity 100,00%,
Avoidable Food Loss 0,53% (2 sampel), Imbalance 4,41% (68), Safe Delivered Cost Rp15.079.436 (3),
Price Deviation 0,98% (4), Decision Time 6,74 menit (3), Evidence Completeness 75,00% (4). Tile "KPI terisi"
di Hari Ini berubah dari `6/7 · 1 metrik belum ada data` menjadi **`7/7 · semua metrik ada`**.

**Batas jujur yang TIDAK diisi dengan data karangan:** Agent Log tetap menulis "belum ada langkah agent yang
tercatat" untuk keputusan non-demo karena `AGENTCORE_RUNTIME_ARN` kosong (tidak ada eksekusi nyata), dan
Surplus & Limbah dulu menulis "belum ada data mitra pengolahan" karena kolomnya tidak ada di
skema; sejak migrasi 022 + `/waste/summary` baris itu berisi mitra dan kg-nya (§13).

## 10. K3 — padanan TEKS untuk isi peta (selesai 17 Okt 2026)

Masalah: penanda peta tidak masuk urutan Tab dan daftar teks lokasi dimatikan di Overview
(`showStatusList={false}`) — pembaca layar tidak punya satu pun jalan masuk ke isi peta.

Yang ditambahkan: `frontend/lib/map-a11y.ts` (`penandaPeta`, `ringkasPenanda`) + di `SupplyMap.tsx` satu baris
`Penanda: …` (selalu dirender, juga saat daftar status dimatikan) dan `<ul class="sr-only" aria-label="Daftar
penanda peta">` berisi satu butir per lokasi dengan **status disebut sebagai kata**, bukan warna.

Batas yang dijaga: bentuknya **satu baris**, bukan tabel. Tabel "Rincian Pasokan per Lokasi" sudah dihapus atas
permintaan pemilik; tes `supply-map-marker-line` menolak `<table>` dan kata "Kebutuhan" di blok ini.

Terukur di aplikasi hidup: cakupan Jakarta → `Penanda: Jakarta kurang 765,8 kg`, `title` memuat kalimat penuh,
1 butir sr-only, tinggi baris **18 px**, tanpa tabel. Cakupan nasional (BGN Monitor, 10 lokasi) →
`Penanda: Jakarta kurang 765,8 kg · Surabaya kurang 11,48 kg · Semarang kurang 10,68 kg · +7 lokasi lain`,
**10 butir sr-only**, tinggi tetap **18 px**, `scrollWidth` tidak melebihi `clientWidth` (dipotong elipsis,
peta tidak terdorong ke bawah).

## 11. K4 — popup jalur: dua baris jam digabung (selesai 17 Okt 2026)

Popup terukur 240×176 px berisi 5 baris; dua di antaranya hanya jam untuk satu fakta yang sama. Kini satu baris:

    Berangkat 17 Okt 2026 17.33 WIB → tiba ± 18.21 WIB · 30 menit lagi
    Belum berangkat (barang masih di pemasok) → tiba belum ada — barang belum berangkat

Tidak ada fakta yang dipangkas: baris jalur jalan, masa layak, peringatan "melewati batas layak", dan
"Waktu tempuh jalur" (hanya saat estimasi tiba belum ada) tetap seperti sebelumnya

## 12. Beras: komoditas keempat yang benar-benar berisi (selesai 18 Okt 2026)

Chip "beras" sudah ada di UI sejak awal (`app/page.tsx` COMMODITIES, `components/OpsConsole.tsx`),
tetapi tabel `commodities` hanya berisi `telur`, `ayam`, `wortel`. Akibatnya memilih beras memberi
peta kosong, papan kiriman kosong, tanpa harga, tanpa pemasok — fitur yang terlihat tetapi tidak
berfungsi. Permintaan pemilik 18 Okt 2026: "tolong buat data beras".

### Yang ditambahkan (semua lewat jalur seed yang sudah ada, bukan data karangan di klien)

| Bagian | Isi | Angka |
|---|---|---|
| Komoditas | `beras`, masa layak **180 hari** (barang kering) | 1 baris |
| Pemasok | Beras Makmur Jakarta, Beras Sari Bogor, Beras Pandan Wangi Cianjur — koordinat, kapasitas, sertifikasi | 3 baris |
| Pasokan | 10/10 lokasi | 600–2.400 kg |
| Permintaan | 8/8 lokasi SPPG, 7 observasi tiap lokasi | 850–3.010 kg |
| Kiriman | 2 sudah tiba, 1 di jalan, 1 belum berangkat | 800–2.400 kg |
| Harga | `pihps_reference` 10 kota + `supplier_quote` 3 pemasok | Rp11.800–14.500/kg |
| Stok SAP mock | material **1003** di CIANJ/BOGOR/JKRTA | 900–2.400 kg |

### Dua keputusan teknis yang tidak boleh disederhanakan

1. **Suhu aman per komoditas.** Evaluasi kesegaran memakai rentang dingin 0–8 °C. Beras disimpan
   pada suhu ruang (26 °C di Indonesia); memakai rentang itu akan menuduhnya "temperature excursion"
   padahal penyimpanannya benar. Karena itu `_SAFE_TEMP_BY_COMMODITY` di `app/api/freshness.py`
   memberi beras **15–30 °C**, dan komoditas tanpa masa layak kini menjawab 422, bukan KeyError.
2. **Pemasok beras butuh koordinat, bukan hanya nama.** Tanpa baris di `data/seed/suppliers_demo.json`,
   ketiga pemasok beras tidak punya pin di peta dan "jarak dari SPPG" kosong. Karena itu berkas itu
   memuat ketiganya (satu pengecualian yang ditulis di docstring modul: nama sama dengan baris kanonik).

### Terukur di aplikasi hidup

- Peta nasional (`bgn_monitor`): **10 lokasi** — Cianjur surplus 2.400 kg, Bandung surplus 1.200 kg,
  Jakarta kurang **2.110 kg** (900 vs 3.010), 6 SPPG lain kekurangan 95–195 kg.
- Pemasok beras (`sppg_head`, ≤150 km): **3** — 0,6 km / 44,8 km / 77,1 km, kapasitas 2.600/3.800/5.200 kg/minggu.
- Rute jalan OSRM: **4 pasangan baru diambil, 0 gagal** (108,9 km / 83 menit untuk Cianjur → Jakarta).
- Chip beras → `Penanda: Jakarta kurang 2.110 kg`, dua kartu kiriman ("Beras Makmur Jakarta → Jakarta
  Sudah tiba 13.53", "Beras Pandan Wangi Cianjur → Jakarta Sudah tiba 17.13"), nol respons ≥400.

### Batas jujur

- ~~Belum ada keputusan demo beras / deret waktunya~~ → **selesai 19 Okt 2026 (§13)**:
  keputusan Jakarta+beras dibuat lewat jalur seed yang sama (4 jejak, 3 bukti, 2 persetujuan),
  dan deret waktu demo beras terisi penuh (1.290 baris pasokan, 216 permintaan, 1.338 harga).
- **Dua kiriman beras lokal** (Jakarta → Jakarta) punya rasio jalan/lurus 3,85× karena OSRM memutar
  di jalan kota; itu angka nyata, bukan kesalahan hitung.

### Tes

- `backend/tests/test_seed_beras.py` — 7 tes: komoditas+masa layak, pasokan tersebar, permintaan 7
  observasi, kiriman dari pemasok beras, aturan sumber harga, stok SAP 1003, jangkar telur tidak bergeser.
- Penyesuaian sadar pada tes yang memaku 3 komoditas: `test_seed_data.py` (3→4, +180 hari),
  `test_balance_data_state.py` (KOMODITAS_DEMO + beras), `test_supplier_city_coverage.py`
  (acuan 30→40, quote Cianjur + beras), batas harga beras 11.000–16.000.
- Bug ikutan yang ditemukan & diperbaiki: **kunci daftar kiriman** memakai `id` pasangan
  pemasok-tujuan, sehingga dua batch ke tujuan yang sama memicu "same key" di React. Kini
  `shipmentKey(row)` = `id#batchId` (id pemilihan tetap per pasangan); tes: `tests/supplier-routes.test.ts`.

## 13. Sisa pekerjaan "kerjakan semuanya" — rollover harian, beras, limbah bermitra (19 Okt 2026)

Lima hal yang sebelumnya dilaporkan sebagai *belum bisa* kini selesai atau dibatasi
secara eksplisit. Tiap butir menyebut buktinya, dan yang masih kosong tetap ditulis kosong.

### 13.1 KPI "hari ini" ikut bergeser (dulu 6/7 tiap hari baru)

Gejala: pada 18 Okt panel KPI menulis **Procurement Price Deviation — no_data** ⇒ 6/7,
padahal sehari sebelumnya 7/7. Sebabnya bukan data hilang: keputusan/limbah demo
bertanggal **17 Okt**, dan `seed_demo_completed_decisions` **idempoten** — baris yang
sudah ada tidak disentuh, jadi tanggalnya membeku selamanya.

Perbaikan (bukan mengarang angka baru, hanya memindahkan tanggal baris demo yang sudah ada):

| Baris | Kolom yang dipindah tiap penyemaian |
|---|---|
| `decisions` | `created_at`, `updated_at` |
| `decision_evidence` | `recorded_at` (dan payload/binding diperbarui) |
| `decision_approvals` | `approved_at` |
| `agent_traces` | `step_at`, `duration_ms` |
| `purchase_orders` | `created_at` |
| `disposal_events` | `generated_at`, `disposed_at` |

Id deterministik TIDAK berubah, jadi penyemaian ulang memperbarui baris yang sama —
tidak menggandakan keputusan/limbah.

Tambahan `seed_demo_daily_prices()`: **3 kota × 4 komoditas × 2 jenis = 24 baris/hari**
(acuan PIHPS pada `now−4 jam`, kutipan pemasok pada `now−3 jam`). Urutan itu penting:
metrik deviasi memasangkan kutipan dengan acuan **terakhir SEBELUM** kutipan, jadi
acuan yang bertanggal sesudah kutipan tidak akan berpasangan. Id per
(tanggal, kota, komoditas, jenis) ⇒ menyegarkan dua kali pada hari yang sama tidak
menggandakan baris.

Bukti hidup (jendela 24 jam, 19 Okt 00:0x WIB): **7/7 metrik tersedia** —
Meal Continuity 100,00% · Avoidable Food Loss 0,61% · Regional Imbalance 5,13% ·
Safe Delivered Cost Rp15.454.957 · Procurement Price Deviation 0,98% (6 sampel) ·
Decision Time 20,00 mnt · Evidence Completeness 50,00%.

### 13.2 Keputusan BERAS (dulu: panel Decision & Evidence kosong untuk beras)

Rotasi keputusan demo memilih komoditas per kota, sehingga beras tidak pernah kebagian.
Sekarang beras disemai **eksplisit** untuk Jakarta lewat jalur yang sama:
`MC-661695B2C685` — 600 kg, Rp13.300/kg = **Rp7.980.000**, pemasok *Beras Makmur Jakarta*,
**4 jejak** (DETECT→…→ACT), **3 bukti**, **2 persetujuan**. Terukur di UI:
baris *"MC-661695B2C685 terkonfirmasi dari eksekusi · Jakarta · Beras Makmur Jakarta ·
600 kg · Rp 13.300,00/kg · Rp 7.980.000,00"*.

Harga PO per komoditas kini berbeda (`HARGA_PO`): beras 13.300 — sebelumnya semua
komoditas memakai harga telur 25.132,39, yang membuat beras tampak 2× lipat harga pasar.

### 13.3 Deret waktu beras (dulu: satu titik kanonik)

Deret waktu demo beras kini terisi penuh: **1.290 baris pasokan** (1 Sep–4 Nov),
**216 baris permintaan** (8 SPPG × 27 hari), **1.338 baris harga**. Grafik stok beras
menampilkan tren, bukan satu titik.

### 13.4 Agent Log (dulu dilaporkan kosong)

Dengan keputusan demo + jejaknya, tab Agent Log berisi **28 baris** saat diukur.
Catatan jujur yang tetap berlaku: jejak untuk keputusan **non-demo** hanya lahir kalau
`AGENTCORE_RUNTIME_ARN` diset — tanpa ARN, tidak ada yang bisa ditampilkan dan itu
tidak diisi karangan.

### 13.5 Mitra pengolahan limbah (dulu: kolomnya tidak ada)

Panel menulis *"Komposter / bank pangan: — · belum ada data mitra pengolahan"*, dan itu
memang benar: skema tidak menyimpan ke mana limbah dialihkan.

Sekarang ada:

- **Migrasi `022_disposal_partner`** — `disposal_events.partner_name text NULL`.
  `NULL` = limbah **dibuang tanpa mitra**; itu keadaan BERBEDA dari 0 kg, jadi API
  memisahkannya, tidak menyamakannya.
- **`GET /waste/summary?days=30`** (`backend/app/api/waste.py`) → `recorded`,
  `diverted`, `unassigned`, dan `partners[]` (nama + kg + jumlah peristiwa).
  Invariannya: `recorded = diverted + unassigned`. Bila tidak ada baris, jawabannya
  `available: false` + alasan — bukan 0 kg yang seolah terukur. Cakupan peran lewat
  `app/core/scope.py` (SPPG = lokasi sendiri, BGN = nasional).
- **Klien**: `wasteFacts(payload)` menggambar angka server; tanpa payload tetap "—".
  `useWasteSummary` hanya memuat di tab Surplus & Limbah; penyegaran global sesudah
  tulis tetap berlaku.
- **Kontrak proxy**: `next.config.js` `API_ROOTS` + `"waste"` — tes
  `tests/proxy-roots.test.ts` menangkap ini lebih dulu (tanpa akar itu panel menerima
  404 HTML dari router Next, bukan JSON).

Tes: `backend/tests/test_waste_summary.py` (2) mengunci invarian dan pemisahan
mitra/dibuang serta cakupan peran; `frontend/tests/surplus.test.ts` (+2) mengunci
tampilan kg/mitra dan keadaan "data tidak tersedia".

### 13.6 Catatan operasional (penting untuk demo)

DB demo dipakai **bersama** sesi lain. Selama pengerjaan, baris demo sempat terhapus
oleh pembersihan tes sesi paralel (terukur: keputusan/limbah demo hilang di antara dua
pemeriksaan beberapa detik). Karena itu: setelah menjalankan pytest, tekan
**"Segarkan ke hari ini"** sebelum menilai UI, dan jangan menyimpulkan "fitur rusak"
dari angka yang berubah-ubah tanpa memeriksa ulang barisnya di DB.

## 14. Pil peta jadi ikon & "Info map" dilebur (19 Okt 2026)

Permintaan pemilik: *"untuk pemasok dan jalur, tombolnya dibuat ikon saja; informasi map
yang saya lihat sama saja dengan legenda."* Dua-duanya dikerjakan bersamaan karena
sumbernya satu: pil kendali yang mengapung di kanvas.

### 14.1 Sakelar lapisan: ikon saja

| Sebelum | Sesudah |
|---|---|
| `Pemasok (7)` + `Jalur kiriman (3)` + `⌄ Info map` — tiga chip berteks | Dua tombol ikon: pin (pemasok) dan polyline (jalur) |
| Tinggi 26 px, lebar mengikuti teks (~120 px) | **32×32 px** di desktop, **44×44 px** di `(pointer: coarse)` |
| Nama = teks tombol | Nama aksesibel `aria-label="Pemasok (7)"`, aksi di `title` |

Kenapa aman menghapus teksnya (dan bukan sekadar merapikan): jumlah dan makna tetap ada di
dua tempat yang sudah terbaca — baris **Legenda** di bawah kanvas (tanpa klik) dan tag
**"Rincian lapisan peta"**. Yang hilang hanya label 120 px yang menutupi Jawa Barat.

Aturan yang dipegang (ui-ux-pro-max prioritas 1 & 2):
- **Nama aksesibel wajib** kalau ikon tanpa teks; `aria-label` membawa jumlah, `title` membawa aksi.
- **Keadaan tidak boleh warna saja**: tombol mati diberi **garis miring** (`.map-layer-toggle-icon::after`),
  tombol hidup terisi aksen — jadi pengguna buta warna tetap melihat bedanya, dan `aria-pressed`
  membawa keadaan yang sama untuk pembaca layar.
- **Ikon dekoratif** `aria-hidden="true"` + `focusable="false"`; dua ikonnya beda bentuk (pin vs polyline)
  supaya tidak tertukar walau tanpa label.
- Target sentuh 44×44 px eksplisit di blok media (WCAG 2.5.8 minta minimum 24 px; panduan sentuh 44 px).

### 14.2 "Info map" dihapus, isinya dipindah

Temuan pemilik benar dan terverifikasi di kode: isi kotak "Info map" adalah **butir legenda yang
sama** dengan baris legenda ringkas (`compactLegendItems` memakai `STATUS_LEGEND`, nada jalur, dan
`SUPPLIER_PIN_LEGEND` yang sama) — satu fakta dibaca dua tempat, yang kedua lewat klik tambahan.
Satu-satunya isi yang tidak duplikat: daftar **Perjalanan kiriman**.

Jadi: kotak status/jalur/pemasok dihapus, `Perjalanan kiriman` dipindah ke panel
**"Rincian lapisan peta"** (satu panel lipat di bawah peta, konten tetap di DOM walau tertutup).
Hasilnya tiga permukaan informasi, masing-masing dengan satu tugas:

1. **baris Legenda** — makna warna/bentuk, selalu terlihat, tanpa klik;
2. **tag jumlah** — "7/9 pemasok dalam jangkauan", "3 jalur kiriman · semua lewat jalur jalan";
3. **panel Rincian lapisan** — perjalanan per kiriman + kalimat panjang (termasuk asal geometri OSRM).

### Terukur di aplikasi hidup (19 Okt 2026, SPPG Head, Overview)

- Pil: **2 tombol, 32×32 px**, `innerText` pil kosong, label `Pemasok (7)` / `Jalur kiriman (3)`,
  `aria-pressed` `false` / `true`. Tidak ada teks "Info map" di halaman mana pun.
- Ponsel 375 px: kedua tombol **44×44 px**.
- Menyalakan pemasok menambah butir legenda (`Pemasok · Keandalan rendah · Dikecualikan ·
  Di luar jangkauan · Sedang mengirim`) — keterangan warna hanya muncul saat lapisannya hidup.
- Panel rincian: `Perjalanan kiriman: Jakarta · di jalan · tiba ± 02.18 (1 jam 3 menit lagi) …
  7 dari 9 pemasok dalam jangkauan 150 km dari Jakarta · 2 di luar jangkauan tidak dipasang di peta`.
- Artefak: `ui-audit/p15-pil-ikon.png`, `p16-pil-mati-nyala.png`, `p15-peta-375.png`.

### Tes yang mengunci bentuk baru

- `tests/map-toggle-icons.test.tsx` (6) — tanpa teks terlihat, `aria-label`+jumlah, `title`+aksi,
  `aria-pressed`, ikon `aria-hidden`, dua ikon beda, tidak ada "Info map".
- `tests/map-controls-css.test.ts` — 32 px persegi di desktop, 44 px di sentuh, dan
  **garis miring untuk keadaan mati** (bukan hanya warna); kelas `map-legend-toggle`/
  `map-legend-detail` harus tetap hilang.
- `tests/supply-map-layer.test.tsx` — perjalanan kiriman ada di panel rincian, hilang saat lapisan
  jalur dimatikan, dan legenda tetap terbaca tanpa klik.
- `tests/supply-map-suppliers.test.tsx`, `tests/supply-map.test.tsx` — jumlah pindah ke `aria-label`;
  legenda status kini "Legenda: … Shortage" (judul "Status lokasi:" ikut hilang bersama kotaknya).

### 14.4 Revisi pemilik, 19 Okt 2026 (lanjutan): skala dihapus, pil turun ke kiri-bawah, transparan

Permintaan: *"info km di bawah kiri hapus saja dan untuk pil sakelar taruh di bawah kiri dan
hapus background putih di belakang jadikan transparant."*

| Sebelum | Sesudah |
|---|---|
| Bilah skala `50 km` di kiri-bawah (`ScaleControl`, 7b-1) | **Dihapus** — kontrol tidak lagi dipasang |
| Pil sakelar di kiri-atas, piring putih (latar `--surface`, border, bayangan) | **Kiri-bawah**, latar **transparan**, tanpa border, tanpa bayangan |
| Tombol berlatar putih 96% | Tombol transparan; plat putih **hanya saat hover/fokus** (area klik) |
| Nyala = kotak aksen terisi | Nyala = **ikon hijau tua + garis miring hilang**, tetap tanpa latar |

Konsekuensi yang disengaja (ditulis supaya tidak jadi temuan):

- **Jarak tidak lagi bisa diukur langsung dari peta.** Angka km tetap ada di popup jalur, kartu
  kiriman, dan panel rincian — sumbernya sama (OSRM). Ini keputusan pemilik, bukan kehilangan data.
- **Keadaan nyala/mati kini dibawa BENTUK + warna, bukan latar.** Mati: ikon tinta gelap
  (`--ink`) + garis miring; nyala: ikon hijau tua `#15803d` (4,6:1 di atas peta terang) + tanpa
  garis miring. Hijau `--map-accent` (#22c55e, ±2,2:1) sengaja **tidak** dipakai untuk ikon tanpa
  latar karena terlalu pucat.
- **Tema konsol peta gelap (`app/map-console.css`) mengecat tombol dengan kaca gelap.** Aturan
  transparan di `globals.css` karena itu dinaikkan spesifisitasnya
  (`.map-card .map-overlay-toggles .map-layer-toggle`) supaya menang tanpa `!important`; warna ikon
  tetap tinta gelap karena **ubin peta tetap terang** walau kerangka konsol gelap.
- Halo putih 1,5 px (`drop-shadow`) menjaga kontras saat ikon jatuh di atas jalan, hutan, atau pin
  berwarna.

Terukur di aplikasi hidup: pil di `left 8 px / bottom 8 px`, lebar 70 px untuk dua tombol 32×32,
`background rgba(0,0,0,0)`, tanpa border & bayangan, `ScaleControl` **tidak ada** di daftar kontrol;
tombol mati `rgb(15,23,42)` + garis miring, tombol nyala `rgb(21,128,61)`.
Artefak: `ui-audit/p19-pil-transparan.png`, `p19-pil-dua-nyala.png`.

Tes yang ikut berubah: `tests/supply-map-layer.test.tsx` (skala **tidak** dipasang; kiri-bawah kosong
dari kontrol) dan `tests/map-controls-css.test.ts` (pil kiri-bawah + latar transparan + tanpa
bayangan; tombol transparan + plat putih hanya saat hover; aturan skala harus tetap hilang).

### 14.5 Audit UI/UX ketat (19 Okt 2026): tiga temuan, semuanya diperbaiki

Dijalankan dengan aturan prioritas `ui-ux-pro-max` (aksesibilitas 1, sentuh 2) +
`references/map-ui-patterns.md` + checklist `pro-rules.md`. Yang diukur adalah
**warna yang benar-benar dirender** (latar efektif dirunut lewat leluhur, piksel
peta diambil dari tangkapan layar), bukan token di CSS.

| # | Temuan | Terukur | Status |
|---|---|---|---|
| 1 | Cincin fokus pil memakai `--map-focus` (#7dd3fc) dari tema konsol | **1,43:1** di atas ubin peta terang → gagal WCAG 1.4.11 & 2.4.7 | Diperbaiki: cincin putih 2 px (18:1 ke piringan fokus) + halo tinta gelap 5 px (≈8:1 ke peta). Dua lapis karena satu warna selalu hilang di salah satu sisi |
| 2 | Pil "Pilih kiriman" & chip "Semua (N)" | tinggi **22 px** (WCAG 2.5.8 minta 24) | Naik ke **28 px** di desktop; 44 px di `(pointer: coarse)` tetap |
| 3 | Ikon "nyala" hijau `#15803D` | **2,84:1** di atas ubin hijau → gagal 3:1 untuk grafis | Diganti `--map-accent-ink` (#1E40AF) yang diukur 4,94–8,72:1 di empat ekstrem basemap |

Yang **lolos** dan tidak diubah: kontras teks panel/legenda 5,53–14,77:1 (18 simpul
teks diukur, 0 gagal); target sentuh 375 px semuanya ≥44 px; tidak ada gulir
mendatar; pil tidak menabrak atribusi MapLibre; ikon 16 px dengan stroke 1,6 px
seragam; label aksesibel menyebut jumlah; keadaan nyala/mati dibawa bentuk + warna.

Catatan konsistensi: aturan hover pil sempat putih 92% di `globals.css` sementara
tema memakai kaca gelap pada spesifisitas sama — hasilnya bergantung urutan berkas.
Nilainya kini **disamakan** dengan tema (`var(--map-glass-deep, …)`), jadi tidak
lagi rapuh. Tes mengunci: latar hover bukan putih, cincin fokus bukan `--ink`
tunggal, dan pil pemilih ≥28 px.

Artefak: `ui-audit/p21-fokus-pil.png` (cincin fokus), `p19-pil-transparan.png`,
`p20-peta-375.png` (ponsel).

### 14.6 Warna bingkai pil, 19 Okt 2026 (revisi pemilik: "warna bingkainya perbaiki lagi")

Keadaan sebelum: piringan hover/fokus membawa `border-color: var(--map-hair-strong)` —
abu `rgba(203,213,225,.5)`. Di atas piringan gelap garis setengah transparan itu terbaca
**kotor/berbayang**, dan bersama cincin fokus lama (putih 2 px + halo gelap 5 px) menghasilkan
tiga lapis bingkai: abu → putih → gelap.

| Keadaan | Sebelum | Sesudah |
|---|---|---|
| Diam | tanpa bingkai (transparan) | tetap — ikon langsung di peta |
| Hover | piringan gelap + **bingkai abu 50%** | piringan gelap, **border transparan** |
| Fokus | abu + cincin putih + halo gelap 5 px | **celah putih 2 px + cincin tinta 2 px** di luarnya |

Cincin fokus dipilih dari LUAR ke dalam karena peta di belakang pil terang: cincin putih
sendirian hanya ~1:1 terhadap peta, sedangkan tinta gelap 13:1; celah putih yang memisahkan
cincin dari piringan gelap (18:1). Total tebal 4 px — cukup terlihat, tidak menggunakan
`!important` (spesifisitas dinaikkan lewat `button` di selektor).

Catatan: bingkai elemen peta lain sudah konsisten dan tidak diubah — `.map-gl`, `.map-pin-label`,
`.map-reset-view`, dan grup kontrol MapLibre semuanya `1px rgba(148,163,184,.32)`; pemisah
legenda/panel `rgba(255,255,255,.08)`.

Artefak: `ui-audit/p22-bingkai-diam.png`, `p22-bingkai-hover.png`, `p22-bingkai-fokus.png`
(DPI 1x dan 3x).

## 15. Chrome peta: tema gelap → tema terang (19 Okt 2026)

Permintaan pemilik: *"terkait warna tema gelap buat ke tema terang"*. Lingkup: chrome di dalam
kartu peta saja (label pin, legenda, panel, pil, popup, kontrol MapLibre, atribusi). Basemap OSM
memang sudah terang; yang gelap hanya chromenya.

Cara: `frontend/app/map-console.css` diubah menjadi tema terang dengan **nama token yang sama**
(`--map-glass`, `--map-glass-deep`, `--map-text`, `--map-hair-strong`, `--map-accent-ink`,
`--map-focus`, …), sehingga aturan di `globals.css` dan tes lama tetap berlaku tanpa disentuh.

| Token | Gelap (sebelum) | Terang (sesudah) | Alasan |
|---|---|---|---|
| `--map-glass` | `rgba(15,23,42,.88)` | `rgba(255,255,255,.92)` | piringan kartu |
| `--map-glass-deep` | `rgba(10,15,28,.94)` | `rgba(255,255,255,.97)` | chip, popup, kontrol |
| `--map-hair` | `rgba(148,163,184,.32)` | `rgba(15,23,42,.12)` | pemisah dekoratif |
| `--map-hair-strong` | `rgba(203,213,225,.5)` | `rgba(15,23,42,.45)` | batas kontrol = **3,2:1** (WCAG 1.4.11) |
| `--map-text` | `#E2E8F0` | `#0F172A` | 17,85:1 di putih |
| `--map-text-muted` | `#AEBCCD` | `#475569` | 7,58:1 di putih |
| `--map-accent` | `#7DD3FC` | `#2563EB` | aksen brand; 5,17:1 di piringan |
| `--map-accent-ink` | `#1E40AF` | `#1E40AF` | ikon pil mengapung di peta — 8,72/7,93/4,94/5,69 di empat ekstrem basemap |
| `--map-focus` | `#7DD3FC` | `#1E40AF` | 8,7:1 di piringan putih, 4,9:1 di ubin taman |
| surplus / shortage / seimbang | `#4ADE80` / `#F87171` / `#FBBF24` | `#15803D` / `#B91C1C` / `#B45309` | nada terang gagal di putih; versi 700/800 lulus 5,02 / 6,47 / 5,02:1 |

Perubahan yang **bukan** sekadar tukar token:

- **Ikon kontrol MapLibre**: `filter: invert(0.92)` dihapus — di piringan putih filter itu membuat
  ikon zoom/kompas putih dan hilang.
- **Popup**: panah (`-tip`) keempat arah mengikuti `--map-glass-solid` putih; teks muted, judul ink.
- **Pil sakelar**: tetap tanpa piringan saat diam; plat hover/fokus kini **putih** `.97` dengan batas
  `--map-hair-strong`. Di `globals.css` aturan hover/fokus yang dulu `border-color: transparent`
  (untuk piringan gelap) diubah memakai token batas.
- **Cincin fokus pil**: dari dua lapis (putih + halo gelap) menjadi satu cincin `--map-focus`
  `#1E40AF`; di piringan putih lapisan kedua tidak lagi menambah apa pun.
- `prefers-reduced-transparency` → putih pekat; `prefers-reduced-motion` dan `forced-colors` tetap.

Terukur di aplikasi (bukan dari token): 18 simpul teks di kartu peta, **0 gagal** 4,5:1 (rentang
7,56–17,85:1); chip pin `rgba(255,255,255,.97)` + teks `rgb(15,23,42)`; grup zoom & atribusi
`rgb(255,255,255)`; cincin fokus `2px solid rgb(30,64,175)`; target sentuh 375 px semuanya ≥44 px;
tanpa gulir mendatar; pil tidak menabrak atribusi.

Temuan sampingan yang ikut diperbaiki: `min-height: 28px` pada `.map-card .route-focus-pill` (kelas
0,3,0) **mengalahkan** `button { min-height: 44px }` (0,0,1) di blok sentuh, sehingga pil pemilih
kembali 28–38 px di ponsel. Ditambahkan media block eksplisit 44 px + tes yang mengunci.

Artefak: `ui-audit/p23-kartu-peta.png` (chrome terang), `p24-panel-terang.png` (legenda + panel),
`p25-popup-terang.png`.

## 16. Panel "Integritas Bukti": permukaan gelap terakhir → tema terang (19 Okt 2026)

Permintaan pemilik (verbatim): *"pada halaman evidence … saya kurang suka terkait desain bagian
integrasi bukti, tolong gunakan skill untuk memperbaikinya terutama pada warna gunakan palet warna
yang cocok dengan tema light mealchainguardian"*. Lanjutan langsung dari §15 (chrome peta) — setelah
peta, `.integrity-trust` adalah **satu-satunya permukaan gelap** yang tersisa di konsol terang, jadi
sekarang ikut terang.

Cara: nama token `--trust-*` **tidak diubah** (seperti §15), hanya nilainya; aturan lama, tes lama,
dan `docs/design.md` §4 tetap berlaku tanpa penulisan ulang.

| Token | Gelap (sebelum) | Terang (sesudah) | Kontras |
|---|---|---|---|
| `--trust-bg` | `#0F172A` | `#FFFFFF` | dasar kartu |
| `--trust-surface` | `rgba(255,255,255,.06)` | `#F1F5F9` | chip hash/alamat |
| `--trust-line` | `rgba(148,163,184,.32)` | `#E2E8F0` | garis rambut |
| `--trust-ink` | `#E2E8F0` | `#0F172A` | 17,85:1 |
| `--trust-ink-muted` | `#94A3B8` | `#475569` | 7,58:1 |
| `--trust-accent` | `#7DD3FC` | `#1D4ED8` | 6,12:1 di atas `--trust-surface` |

Perubahan yang **bukan** sekadar tukar token:

- **Dua kotak bukti** (`.integrity-proof`: Merkle Ledger, Dossier Keputusan) dengan **nada keadaan**
  dari `data-tone` → tiga variabel (`--tone-bg/-line/-ink`) memakai token status sistemik:
  `ok` = teal `#ECFDF5/#A7F3D0/#065F46` (7,29:1) untuk rantai valid & segel terverifikasi;
  `warn` = amber `#FFFBEB/#FDE68A/#8A5A00` (5,72:1) untuk unsigned; `danger` = rose
  `#FEF2F2/#FECACA/#991B1B` (7,60:1) untuk rantai putus / segel tidak cocok; `plain` = netral
  `#F1F5F9/#CBD5E1/#475569` untuk "belum ada data". Garis kiri **3 px** = nada keadaan.
- **Lencana keadaan** (`.integrity-chip`): titik 6 px + kata, jadi keadaan tidak pernah bergantung
  pada warna saja (WCAG 1.4.1). Emoji ✅/❌/⚠️ dihapus — diganti bentuk (titik) + tint + teks.
- **Label→nilai rapi**: `Blok` (mono tabular) dan `Head`/`Alamat konten` sebagai chip mono;
  sebelumnya semuanya satu paragraf yang dipisah "·" sehingga angka bercampur kalimat.
  `reason` rantai putus punya baris sendiri (`.integrity-reason`), tidak lagi dikurung dalam paragraf
  status bersama `broken_at`.
- **Daftar pengukuran & tombol ekspor tetap netral** (tidak ikut tint): itu dokumen kerja, bukan
  bukti kripto — alasan yang sama seperti sebelumnya, hanya arah warnanya yang berbalik.
- **Papan "Bukti integrasi per komponen"** (Agent Log, `.integration-*`): lencana tidak lagi memakai
  `rgba` ad hoc (ok `#2A722E`, warn tanpa warna teks, danger `--status-danger`) melainkan pasangan
  token `--ok/--warn/--danger/--neutral-{bg,border,ink}` + titik; baris dapat garis kiri 3 px sesuai
  nada (`integration-tone-*`). Nol nilai warna baru — semua dari `:root`.

Batas yang **tidak** berubah: endpoint (`GET /ledger/verify`, `GET /decisions/{id}/dossier`), angka
yang ditampilkan, aturan kejujuran "hijau hanya bila backend menyatakan valid", lipatan rincian,
`data-testid` (`ledger-status`, `dossier-status`, `dossier-address`, `dossier-signature`,
`btn-verify-ledger`, `ledger-coverage`), dan teks "Dossier Keputusan".

Gerbang: vitest **1359 lulus / 119 berkas**, `tsc --noEmit` 0, `npm run build` 0. **Terukur di aplikasi
hidup** (:3010, akun demo SPPG Head, 19 Okt 12.22 WIB): `.integrity-trust` = `rgb(255,255,255)`, kotak
ledger `data-tone="ok"` dengan lencana "Rantai valid" dan dossier "tersegel & terverifikasi" — data
nyata, bukan contoh. Papan Agent Log (7 komponen): 4 netral `rgb(241,245,249)`/`rgb(71,85,105)`,
1 amber `rgb(255,251,235)`/`rgb(138,90,0)`, 1 rose `rgb(254,242,242)`/`rgb(153,27,27)`, tiap lencana
bertitik via `::before`, garis kiri baris ikut nada (`rgb(203,213,225)` / `rgb(249,168,37)` /
`rgb(198,40,40)`); tidak ada baris hijau karena panel itu memang tidak menjalankan probe.
Pratinjau statis (375/768/1440 px) yang dirender dari `globals.css` yang sama: nol luapan mendatar;
di ≤460 px kepala kotak dan baris label→nilai menumpuk (label di atas nilai).

### 16.1 Jarak ke panel PO (revisi pemilik, 19 Okt 2026: "jarak ke po kok spacenya banyak bener")

Slack 72 px untuk bar pintasan yang menempel di bawah layar dipasang pada `.evidence-page`, padahal
panel **Purchase order (mock lokal)** dirender SESUDAH `.evidence-page` sebagai saudara di `.app-body`.
Akibatnya slack itu jatuh di TENGAH halaman: **88 px** ruang kosong (72 slack + 16 margin) tepat di
antara kartu terakhir dan panel PO, sementara halaman tidak punya slack di ujung bawahnya sendiri.

Perbaikan: slack dipindah ke anak terakhir halaman — `.app-body:has(.evidence-actionbar) > :last-child
{ margin-bottom: 72px }` (jadi tetap tidak ada tambahan tinggi saat bar pintasan tidak dirender) — dan
`.po-panel { margin-top: 16px → 13px }` mengikuti gap halaman. Terukur di aplikasi hidup: jarak kartu
terakhir → PO **88 px → 13 px**; `.evidence-page` `padding-bottom` 72 px → 0; margin bawah panel PO
72 px (slack bar pintasan kini di ujung halaman, bukan di tengah).


## 17. Popup "Governance & persetujuan": kartu fakta + latar blur 20% (19 Okt 2026)

Permintaan pemilik (verbatim): *"pada halaman pop up "Governance & persetujuan" ubah tampilan ui dan
bacgraud di buat blur 20% saja"*, lalu *"untuk blur nya mungkin bisa 15% saja"*, lalu *"blur nya itu
masih samar samar untuk tampilan di belakangnya, berarti di turunin lagi"*. Ini **membalik**
keputusan latar pagi hari yang sama (scrim kabut 66% + blur + `saturate(140%)`): pemilik ingin blur
saja, bukan panel yang nyaris pekat, dan kadarnya diturunkan bertahap 20 → 15 → **8 px**.

**Latar (`.popup-backdrop`).** `background: rgba(248,250,252,.2)` + `backdrop-filter: blur(8px)`
tanpa `saturate()`. Di 8 px bentuk panel di belakang masih terbaca **samar** (blob, bukan huruf) —
itu yang diminta; di bawah ~6 px huruf di belakang mulai terbaca, jadi 6 px adalah lantainya. Teks di belakang tetap tidak terbaca karena blur-nya, bukan karena ditutup cat
(glassmorphism: blur 10-20 px, translucent white 15-30%). Dua jaring pengaman tidak berubah: browser
tanpa `backdrop-filter` jatuh ke scrim gelap `rgba(15,23,42,.55)`, dan `prefers-reduced-transparency`
memakai latar `rgba(248,250,252,.97)` tanpa blur. `tests/popup-backdrop.test.ts` diperbarui ke
kontrak baru (blur **6-10 px** tanpa saturasi, alpha tint 0,15-0,30) — tes lama memang memaku angka
0,66, dan blur dipaku sebagai rentang karena pemilik menala kadarnya tiga kali.

**Isi popup (`className="popup-governance"`).** `Popup` dapat prop opsional `className`; hanya dialog
ini yang memakai tata letak baru, sedangkan dua dialog lain yang berbagi cangkang (pemilih tanggal,
karantina) tidak berubah kecuali latar blur tadi.

- Panel `min(720px, 100%)`, `max-height: min(92vh, 900px)` (86vh memotong kartu di tengah fakta).
- Chip status tidak lagi menyelip antara deskripsi dan ringkasan: jadi **strip** sendiri di atas isi
  (chip kiri, meter progres 240 px kanan). Track progres memakai `--line-strong`, bukan
  `--surface-sunken` — di atas strip yang juga sunken, track sunken tidak terlihat (temuan saat
  verifikasi layar). Track lebar penuh terbaca seperti garis pemisah, jadi meter dibatasi 240 px.
- Ringkasan bukti: `<ul>` bullet padat → `<dl>` kartu fakta (`dt` label 12 px `--ink-subtle` di kolom
  152 px, `dd` nilai 13 px); pemisah `--line` antar baris; id panjang dipatahkan (`overflow-wrap:
  anywhere`). Label biru 4 px di tepi kartu dibuang — di dalam panel bershadow ia terbaca sebagai
  kartu di dalam kartu.
- Emoji ⛔ di `blocking_reasons` diganti ikon SVG `aria-hidden` (aturan skill: ikon SVG, bukan emoji)
  dan blok itu diberi judul "Tertahan".
- Tiap pilihan tindakan jadi kartu ber-stripe **3 px** sesuai dampaknya: tolak `--status-danger`,
  ajukan/re-propose `--accent-strong`, verifikasi `--navy-700`, eksekusi `--status-safe`. Stripe
  pertama kali dipasang dengan `--danger-border` (#FECACA) dan **tidak terlihat** di atas putih —
  diukur dari piksel layar, lalu diganti `--status-danger`. Warna hanya penguat: nama tindakan dan
  akibatnya tetap tertulis (tidak pernah warna saja, WCAG 1.4.1).
- Kaki sticky: hint "Tekan Esc untuk menutup jendela ini." + tombol Tutup.
- ≤720 px: fakta satu kolom (label di atas nilai) supaya kolom 152 px tidak memakan separuh layar.

Batas yang tidak berubah: teks tiap fakta, gating `can_approve`/`can_reject`/`can_execute` dari
server, tidak ada approve massal, `data-action` tiap tombol, `aria-modal`/`aria-labelledby`, dan
`prefers-reduced-motion`.

Gerbang: vitest **1359 lulus / 119 berkas**, `tsc --noEmit` 0, `npm run build` 0. Terukur di aplikasi
hidup (:3010, akun demo SPPG Head, 19 Okt 12.2x WIB): `.popup-backdrop` = `rgba(248,250,252,0.2)` +
`blur(8px)`, panel `class="popup popup-governance"` lebar 720 px, 10 baris `.approval-fact`, strip
progres 240 px, stripe kiri baris tolak `rgb(198,40,40)` dan verifikasi `rgb(51,65,85)` (sampel piksel
screenshot, bukan perkiraan).

Terukur untuk kadar blur (sampel wilayah sidebar di belakang backdrop, screenshot :3010 pada 1262 px):
`blur(15px)` → simpangan baku luminans **6,32**; `blur(8px)` → **9,07** (≈+44% detail yang masih
terbaca) dengan teks di belakang tetap tidak terbaca. Angka inilah dasar "samar-samar", bukan selera.


## 18. Dock "Ke zona keputusan": pil toast → pintasan keputusan (19 Okt 2026)

Permintaan pemilik (verbatim): *"untuk popup ke zona keputusan anda redesign lagi deh soalnya rada
kurang menurut gua pakai ui ux pro max susun rencana lalu jalnkan"*. Yang dimaksud "popup" adalah
`.evidence-actionbar` — bar melayang di bawah layar selama zona keputusan belum terlihat.

Keadaan sebelumnya (terukur di :3010): pil 720 x 57 px, `border-radius: 999px`, satu baris teks abu-abu
`"menunggu persetujuan · 0 dari 2 persetujuan"`, CTA biru bertanda garis bawah bawaan `<a>`. Tiga
masalah: (a) bentuk pil + teks tunggal membuatnya terbaca seperti toast, bukan pintasan kerja;
(b) keadaan dan hitungan approval — dua informasi berbeda bobot — disamakan dalam satu baris abu-abu,
padahal keadaan yang menentukan apakah ada yang bisa dikerjakan; (c) CTA tidak punya tanda arah,
sementara tautan kembarnya di kepala keputusan memakai "↓".

Sesudah:

- **Dock 560 px, radius 14 px**, border `--line`, `--shadow-2` + satu lapis bayangan 40 px. Bukan lagi
  999 px karena radius penuh milik pil status, bukan panel kerja.
- **Titik nada keadaan** (8 px + cincin tint) dari `data-tone` yang dipetakan ke `STATUS_TONES` yang
  sudah ada: `warning`/`safe`/`danger`/`neutral`. Warna hanya penguat — kata keadaannya tetap tertulis
  di baris pertama (WCAG 1.4.1).
- **Hierarki dua baris**: "menunggu persetujuan" 13 px/600 `--ink`, di bawahnya "0 dari 2 persetujuan"
  12 px `--ink-muted`; keduanya di-ellipsis, bukan membungkus bar.
- **CTA** "Ke zona keputusan ↓" — `min-height: 40px`, radius 8 px, `text-decoration: none` (label putih
  di atas biru dengan garis bawah terbaca seperti tautan teks, bukan tombol).
- **Posisi: tetap di TENGAH layar.** Sempat dicoba "rata kanan kiri mengikuti sidebar buka/tutup"
  (`left: calc(var(--side-w, 256px) + 22px); right: 22px`), lalu pemilik mengoreksi: *"eh salah tetap
  kaya di buat rata tengah maksudnya"*. Jadi lebar tetap `min(560px, 100vw - 24px)` dan `left: 50%` +
  `translateX(-50%)`; buka/tutup sidebar tidak menggeser dock. Terukur: delta pusat dock vs pusat
  layout viewport = **0 px** (560 px pada 1247 px).
- **Perilaku**: animasi masuk `actionbar-in` 240 ms (`--dur-3`, `--ease-standard`), dimatikan
  `prefers-reduced-motion`; `bottom: calc(16px + env(safe-area-inset-bottom))` di iOS; disembunyikan
  saat cetak; ≤560 px hitungan approval dilepas dan CTA mengisi sisa lebar (informasi tidak dibuang,
  hanya dipadatkan — sebelumnya seluruh teks di-`display:none`).

Batas yang tidak berubah: teks status/hitungan, `href="#zona-keputusan"` + `id="zona-keputusan"`,
`role="region"` + `aria-label="Pintasan ke zona keputusan"`, logika tampil (`selected && bolehBertindak
&& !zonaTerlihat`), dan slack 72 px pada anak terakhir `.app-body`.

Gerbang: vitest 120 berkas / 1368 tes lulus, `tsc --noEmit` 0, `npm run build` 0. Terukur di :3010:
dock 560 x 58 px, `border-radius: 14px`, `animation-name: actionbar-in`, titik `rgb(249,168,37)` untuk
tone `warning`, dua baris teks hasil pemisahan `<strong>` + `<span>`.
Koreksi posisi (dicatat supaya tidak diulang): percobaan full-width sempat terpasang dan terukur
`x=278, w=947` (tepi isi halaman, mengikuti rail 256 px) — pemilik menolaknya, jadi kembali ke dock
tengah. Jangan mengubah ke full-width tanpa permintaan eksplisit.

---

## 19. Pemilih keputusan: `<select>` → pemilih yang bisa dicari (19 Okt 2026)

**Permintaan pemilik:** *"tolong ubah redesign dropdown dari 'pilih keputusan' di halaman Agent
Activity Log dan halaman Decision & Evidence — Keputusan yang diperiksa"* — dikerjakan dengan
skill `frontend-design`, `design-system`, dan `ui-ux-pro-max`.

### 19.1 Masalah pada `<select>` lama

- **Tidak bisa dicari.** Satu akun bisa melihat 48–126 keputusan; mencari satu nomor berarti
  menggulir daftar sepanjang layar di dalam popup OS yang tidak bisa digayakan.
- **Satu baris per keputusan.** Label `"<jenis> · <status> · <id 8>"` harus muat dalam satu baris
  sempit, jadi yang terpotong justru bagian pembeda (sisa waktu vs status).
- **Tidak ada konteks jumlah.** Pengguna tidak tahu ada berapa yang menunggu tindakan dan berapa
  yang disembunyikan karena lewat tenggat.
- **Tidak konsisten dengan sisa konsol.** Semua kontrol lain di repo memakai token, cincin fokus,
  dan target sentuh 44 px; `<select>` bawaan tidak bisa mengikuti itu.

### 19.2 Bentuk baru (`components/DecisionPicker.tsx`)

- **Pemicu** (`button`, `aria-haspopup="listbox"`, `aria-expanded`, `aria-controls`): dua baris —
  judul keputusan (`--fs-2`, tebal) dan baris meta (`--fs-1`: sisa waktu/status · nomor).
  Nomor 8 heksa memakai `--font-data` lewat `.dpick-nomor`, kata tetap sans — supaya nomor
  mudah dibedakan tanpa membuat seluruh baris terasa seperti log.
- **Panel** (`hidden` saat tertutup, jadi `aria-controls` selalu menunjuk elemen yang ada):
  kotak cari ("Cari jenis, status, atau nomor…") + `ul[role="listbox"]` datar berisi header grup
  `li[role="presentation"]` dan opsi `li[role="option"]`. Satu listbox datar dipilih supaya
  `aria-activedescendant` tetap sederhana; tidak ada listbox bersarang.
- **Grup** tetap dari `lib/decision-picker.ts` (`Menunggu tindakan` / `Diusulkan, belum masuk
  persetujuan` / `Tidak menunggu tindakan`) — hanya jumlahnya **dihitung ulang dari hasil saring**.
  Angka yang salah lebih buruk daripada tanpa angka: pada kueri "alokasi", `(4)` menjadi `(1)`.
- **Keyboard**: fokus otomatis ke kotak cari saat panel dibuka (lewat `requestAnimationFrame`,
  karena klik tombol menaruh fokus kembali ke pemicu setelah efek React), `↑`/`↓` memindah
  sorotan (`aria-activedescendant`), `Home`/`End`, `Enter` memilih, `Esc` menutup dan
  mengembalikan fokus ke pemicu, klik di luar menutup.
- **Keadaan**: sorotan keyboard = latar `--accent-soft` + garis aksen; pilihan aktif = garis kiri
  3 px `--accent-strong` + centang. Bedakan sorotan dari pilihan supaya "sedang di sini" dan
  "yang sedang dilihat" tidak tertukar.
- **Token**: hanya `--surface`, `--surface-sunken`, `--line`, `--line-input`, `--ink`,
  `--ink-muted`, `--ink-subtle`, `--accent`, `--accent-strong`, `--accent-soft`, `--font-data`,
  `--fs-1`, `--fs-2`. Tidak ada hex baru.
- **≤640 px**: `min-width` dilepas, `max-width: none`, panel selebar pemicu.
- `prefers-reduced-motion` tidak perlu aturan baru: tidak ada animasi masuk, hanya perubahan
  `hidden`/latar (tidak ada gerak yang harus dimatikan).

### 19.3 Kesalahan yang ditemukan saat verifikasi live (dan perbaikannya)

| Gejala terukur | Sebab | Perbaikan |
|---|---|---|
| Panel muncul **43 px** di bawah pemicu | `top: calc(100% + 6px)` dihitung dari `.dpick` yang ikut memuat label + baris hint | pembungkus `.dpick-anchor` (hanya pemicu) jadi acuan `position: relative`; jarak **6 px** |
| Dua pemilih memakai `id="pilih-keputusan"` | id bawaan dipakai di dua halaman | Agent Log memakai `id="pilih-keputusan-log"` |
| Pemicu di Agent Log hanya **130 px** → judul dua baris | `.page-header-meta` menyusut mengikuti isi | `.dpick { min-width: 300px }` (dilepas ≤640 px); terukur **300 px**, judul satu baris |
| Angka grup tidak berubah saat mencari | jumlah dibekukan di `lib/decision-picker.ts` | dihitung ulang dari `group.options.length` setelah saring |
| Angka "0 keputusan" sempat tampil lama | daftar keputusan tiba setelah tab dibuka | efek jaring kedua di `app/page.tsx`: begitu `decisions` tersedia, `defaultEvidenceId`/`defaultAgentLogId` dipilih |

### 19.4 Bukti terukur di :3010 (akun SPPG Head, 1× zoom)

- Decision & Evidence: pemicu **340 × 45 px**, panel **340 × 341 px**, jarak **6 px**, daftar
  bergulir 255 px dari 2.642 px isi, **0** overflow horizontal.
- Agent Log: pemicu **300 × 44 px** rata kanan ke tepi isi (**1.225 px**), panel **300 px**,
  opsi dua baris **53 px**, pencarian "alokasi" → 27 opsi (1 + 22 + 4).
- Keyboard (event keyboard nyata lewat CDP): `↓` memindah sorotan, `Enter` memilih
  (`#e1871b42`… → `#3036af23`), panel tertutup, fokus kembali ke pemicu, URL berubah ke
  `?tab=evidence&keputusan=…`, isi keputusan berganti.
- `Esc` menutup, kotak cari bersih, fokus kembali ke pemicu.

Batas yang tidak berubah: logika pengelompokan & kata status tetap di `lib/decision-picker.ts`,
sakelar "Tampilkan yang lewat tenggat" tetap di kepala halaman bukti, gating approval tidak
disentuh, dan `?keputusan=<id>` tetap bisa dibagikan.

Gerbang: vitest **1.388 lulus / 123 berkas**, `tsc --noEmit` 0, `npm run build` 0.

---

## 20. Dokumen PO sebagai PDF — hanya untuk yang sudah disetujui (20 Okt 2026)

Permintaan pemilik (verbatim): *"untuk bagian yang sudah disetujui untuk po anda bisa buat pdf po nya
yang bisa di download"* — di tab **Decision & Evidence**, PO yang approval-nya sudah tercatat harus
menghasilkan berkas PDF yang bisa diunduh, dicetak, dan diserahkan ke bagian keuangan.

### Keputusan

1. **PDF dibuat di backend, bukan di browser.** `GET /sap/purchase-orders/{po_number}/pdf`
   (`app/api/sap_orders.py` → `app/services/po_document.py`). Alasannya: angka dan jejak persetujuan
   harus dibaca dari DB pada detik unduh. Dokumen yang dirakit di klien bisa lebih baru atau lebih
   lama daripada datanya, dan tidak ada tempat untuk memagari "PO ini sudah disetujui atau belum".
2. **Pagar persetujuan.** PDF hanya terbit untuk PO yang lahir dari keputusan `approved`/`executed`
   (`po_document.STATUS_BOLEH_PDF`). PO impor tanpa keputusan (`4500000001`) → **409** "tidak lahir
   dari keputusan"; keputusan yang masih menunggu → **409** "keputusan menunggu persetujuan — PDF PO
   diterbitkan setelah keputusan disetujui". Tidak ada dokumen kosong, tidak ada PDF untuk pembelian
   yang belum disetujui.
3. **Cakupan = cakupan daftar.** Peran SPPG meminta PO lokasi lain → **404**, sama seperti daftar yang
   memang tidak memuatnya; pesan galat tidak membocorkan keberadaan PO lokasi lain.
4. **Isi dokumen (satu halaman A4, satu halaman kecuali isi memanjang):** kop (nomor PO, status,
   tanggal terbit WIB), pihak & bahan (lokasi tujuan, pemasok, nama bahan, nomor bahan), rincian
   pesanan + total, dasar persetujuan (ID, jenis, status, versi, jendela berlaku), jejak persetujuan
   (peran, nama, setuju/menolak, waktu WIB, catatan) + kalimat "N persetujuan tercatat dari M yang
   disyaratkan matriks persetujuan — syarat terpenuhi/belum", lalu catatan kaki. Setiap halaman
   menyebut **"SAP simulasi"** (Rules.md §4) dan menuliskan bahwa sumbernya tabel mock di DB aplikasi,
   bukan SAP S/4HANA produksi.
5. **Satu aturan angka.** `total = harga × kuantitas` (rumus yang sama dengan endpoint daftar),
   kuantitas/harga dibaca apa adanya, nilai tak diketahui ditulis "—". Status PO dijelaskan artinya
   (`catatan_status`): "Terkonfirmasi" = baris impor SAP, bukan konfirmasi yang dikirim aplikasi.
6. **UI: aksi sekunder per baris.** Tombol "Unduh PDF" (ikon garis 12 px + label, 30 px tinggi;
   44 px di `(pointer: coarse)`) hanya pada baris yang memenuhi pagar; baris lain mendapat **kalimat
   sebabnya** — tombol yang hilang tanpa penjelasan terbaca sebagai fitur rusak, tombol yang selalu
   ada padahal backend menolak 409 terbaca sebagai janji palsu. Keadaan: `Menyiapkan PDF…`
   (`aria-busy`) → `Dokumen terunduh sebagai PO-<nomor>.pdf` (`role="status"`) atau
   `Dokumen tidak bisa diunduh: <alasan server>` (`role="alert"`, memakai `ApiError.detail`).
   Nama berkas satu aturan dengan backend (`poFileName` di `lib/export.ts` ↔ `po_document.nama_berkas`),
   disalin karena `Content-Disposition` tidak terbaca lintas-origin tanpa ekspos CORS.

### Jebakan yang terukur

- **Tes lama memanggil komponen sebagai fungsi.** `renderToStaticMarkup(PurchaseOrderList({...}))`
  (dan `root.render(PurchaseOrderList({...}))` di tes tautan) meledak begitu komponen memegang hook:
  `Cannot read properties of null (reading 'useState')`. Kedua helper tes diubah merender **elemen**;
  perilaku aplikasi tidak pernah terpengaruh (aplikasi selalu merender elemen).
- **Kolom "Keputusan" terpotong** jadi "Keputus an" saat lebarnya 11% → 14% (kolom Peran/Nama/Waktu
  digeser sedikit). Ditemukan dari render PNG halaman 1 + `vision_analyze`, bukan dari tes.
- **`align-items: baseline` menurunkan tombol 30 px ~4 px** dari tautan di sebelahnya →
  `.po-row-foot .po-pdf-button { align-self: center; }`. Perataan teks lain tidak diubah.
- **`reportlab` + `pypdf` masuk `backend/requirements.txt`** dan image backend di-`build` ulang.
  Tanpa itu PDF hanya hidup sampai kontainer dibuat ulang (pip di dalam kontainer bersifat sementara);
  `pypdf` khusus dipakai tes untuk mengekstrak ulang teks PDF.

### Gerbang

- `pytest tests/test_po_document_pdf.py` → **11 lulus** (pagar status, 404 cakupan, 409 tanpa
  keputusan & belum disetujui, isi PDF diekstrak ulang dan dibandingkan dengan ground truth DB,
  label "SAP simulasi").
- Suite backend penuh: **1.167 lulus / 15 gagal / 5 dilewati** — 15 kegagalan itu di lima berkas yang
  **nol** menyebut identifier perubahan ini; 9 di antaranya hijau saat dijalankan sendiri
  (interferensi antar-berkas), 6 merah karena kondisi data demo hasil penyemaian sesi sebelumnya
  (`test_demo_completed_decisions_konsisten` 5, `test_suppliers_api` 1). Bukan regresi fitur ini.
- `ruff check` empat berkas tersentuh → bersih (repo-wide masih 17 pelanggaran di berkas lain).
- Frontend: **vitest 1.410 lulus / 126 berkas**, `tsc --noEmit` 0. `next build` tidak dijalankan
  karena dev server :3010 memegang `.next` (dokumentasi jebakan build repo ini).
- Hidup di :3010 (SPPG Head): 9 PO → 9 tombol; klik baris pertama → server 200
  `application/pdf`, 3.768 byte, awalan `%PDF-`, dan UI menulis
  "Dokumen terunduh sebagai PO-MC-661695B2C685.pdf"; sesudah image backend di-build ulang
  (`reportlab 5.0.1 | pypdf 6.21.1` di dalam kontainer) unduhan tetap 200.

## 20. Judul keputusan di Decision & Evidence: 24px → 18px (19 Okt 2026)

Permintaan pemilik: *"kurang kecil untuk ini 'Alihkan 712 kg telur: Cianjur → Jakarta'"*.

Judul itu memakai `.evidence-hero-title` dengan `--fs-7` (24px) — tangga token untuk **angka
metrik**, bukan kalimat. Kalimat 60 karakter pada 24px menimpa kartu di sekitarnya dan membuat
satu baris judul lebih berat daripada angka keputusan di bawahnya.

Sekarang `--fs-5` (18px, tangga judul seksi) di desktop dan `--fs-4` (16px) di ≤760px. 18px tetap
mengalahkan `.card h2` (14px) dan `.evidence-page .card > h2` (16px), jadi hierarki "judul
keputusan = aksi" tetap utuh.

Bukti hidup (:3010, SPPG Head): `getComputedStyle` → `font-size: 18px`, `line-height: 23,4px`,
tinggi judul 23px di dalam kartu 432px; tidak ada teks terpotong; satu-satunya elemen di 10 tab
yang memuat frasa ini adalah kartu hero (18px).

## 21. Kartu 7 agen: latar hijau saat benar-benar jalan + slug alat disembunyikan (19 Okt 2026)

Dua permintaan pemilik sekaligus: *"bagian 7 agent jika jalan kasih indikator background hijau"*
dan *"untuk bagian seperti ini `evaluate_safety` hapus atau tidak usah ditampilkan"*.

1. **Latar hijau memakai token yang ada**, bukan warna baru: `.swarm-card[data-state="ok"]` →
   `background: var(--ok-bg)` (#ECFDF5), `border-color: var(--ok-border)` (#A7F3D0), chip status
   `var(--ok-ink)`. Keadaan tetap terbaca tanpa warna: titik terisi, kata "Selesai", dan angka
   durasi. Kartu `degraded`/`error`/`skipped` tidak berubah.
2. **`AgentTraceViewer` tidak lagi mencetak `tool_called` mentah.** Baris alat memakai
   `toolLabel()`; bila slug tidak punya padanan manusia, barisnya tidak dirender sama sekali —
   jadi `evaluate_safety` hilang, bukan berubah menjadi teks lain yang tetap teknis.

Bukti hidup (:3010, keputusan `4191797f`, run `ccf2b4bd`): 7 kartu `.swarm-card[data-state="ok"]`
dengan `background-color: rgb(236, 253, 245)` dan `border-color: rgb(167, 243, 208)`, chip
"Selesai"; `.trace-tool` hanya berisi "Layanan verifikator", "Penyedia perkiraan", "Buat
keputusan"; pencarian `evaluate_safety` di seluruh teks Agent Log → 0.

## 22. Panel 7 agen: roster + tiga keadaan — HANYA di Demo Control

Klarifikasi pemilik (2026-10-19): *"ku malah ubah yang di agent log, balikin desainnya;
yang saya maksud adalah yang di Demo Control yang di-redesign."*

**Agent Log dikembalikan ke desain semula.** Tidak ada legenda, tidak ada latar hijau,
ringkasan tetap `N/7 tercatat`, kartu tanpa baris tetap "Belum tercatat", dan tab Agent
Log kembali memilih keputusan terbaru yang punya review (perilaku P4). Kelas `.swarm-card`
tidak lagi punya varian `ok`/`running`/`not_recorded`.

**Redesign dipindah ke Demo Control → blok "Bukti agent".** Tujuh kartu selalu tampil
begitu ada putaran; sumbernya `/demo/agent/last-run` yang kini mengirim `agents` (tujuh
kunci tetap) dan `agents_run_id`.

| Keadaan | Kapan | Tampilan |
|---|---|---|
| **Selesai** | baris review tersimpan, status `ok` | latar `--ok-bg`, tepi `--ok-border`, titik hijau, chip "Selesai" |
| **Berjalan** | putaran baru sedang berjalan (`busy === "agent"`) | latar `--accent-soft`, tepi `--accent-strong`, titik biru berdenyut (dimatikan pada `prefers-reduced-motion`), chip "Berjalan", durasi/peringatan "—" |
| **Tidak dijalankan** | belum ada baris untuk agen itu | latar `--neutral-bg`, tepi putus-putus, chip "Tidak dijalankan" |
| **Terbatas / Gagal** | status `degraded` / `error` | `--warn-*` / `--danger-*` |

Aturan data yang dipaku:
- Status hanya dari baris review tersimpan; agen tanpa baris tidak diberi angka (durasi
  dan peringatan "—", bukan 0).
- Selama putaran berjalan ketujuh kartu "Berjalan" — bukan hasil putaran sebelumnya.
- Bukti pipeline (DETECT/OPTIMIZE) diambil dari baris **tanpa** `agent_name`, karena baris
  review worker memakai nama langkah yang sama (`agent.supply` di DETECT, dst.).
- `last-run` memilih keputusan terbaru yang punya langkah SUPERVISE (bukan sekadar DETECT,
  yang juga ditulis data seed).

Bukti hidup (:3010, SPPG Head, putaran 30f6a79f):
- saat berjalan: 7 kartu `data-state="running"`, chip "Berjalan", `rgb(239,246,255)`, tepi `rgb(37,99,235)`, animasi `dc-agent-pulse`;
- sesudah selesai: 7 kartu `data-state="ok"`, `rgb(236,253,245)`, tepi `rgb(167,243,208)`, durasi 256 md … 2,8 dtk, peringatan 0/1;
- Agent Log: `7/7 tercatat`, latar `rgb(255,255,255)`, tanpa legenda.
**Daftar langkah pipeline dilipat.** 15 chip langkah (`DETECT agent.supply` … `SUPERVISE agent.review_summary`)
memakan ±195 px tinggi blok, jadi dibungkus `<details class="dc-steps-fold">` dengan segitiga bawaan peramban
(`display: list-item`, bukan `flex` — `flex` menghapus `::marker`). Ringkasan `Langkah pipeline · 15` tetap
membawa jumlahnya di luar lipatan; isi langkah tetap ada di DOM (15 `<li>`), hanya tidak digambar.
Terukur di :3010: tertutup 28 px (dokumen 1.235 px), terbuka 195 px (dokumen 1.402 px); `innerText` daftar
saat tertutup = kosong.

## 23. Kartu "Penerimaan barang": opsi batch, gerbang, dan kalimat (20 Okt 2026)

Audit pemilik: *"untuk bagian 'Penerimaan barang' pada halaman 'Keamanan Pangan' tolong anda periksa
apakah semuanya sudah sesuai atau belum, terutama bagian kalimatnya dan opsi pilihan"*. Hasil periksa
diukur di aplikasi hidup (:3010, SPPG Head, dapur Jakarta), bukan dari kesan tangkapan layar.

**Opsi batch tidak boleh ikut cakupan tabel.** Daftar "Batch yang diterima" dulu memakai baris yang
sudah disaring cakupan (`urut`), sehingga saat cakupan diubah ke "Semua lokasi (pengawasan)" dropdown
menawarkan 50+ batch kota lain. Memilih salah satunya dijawab `403 "lokasi batch di cakupan lokasi di
luar SPPG Anda"` (`assert_in_scope` di `POST /receipts`, ruling 2026-10-14: barang diterima di dapur
sendiri). Sekarang penyaringnya `receivingBatchOptions(rows, ownLocation)` di `lib/food-safety.ts`:
lokasi sendiri, hanya baris ber-`id`, **batch yang masih layak didahulukan** (urutan tenggat menaruh
nilai negatif paling atas, sehingga pilihan default bisa jatuh ke batch kedaluwarsa — bukan sasaran yang
masuk akal untuk barang datang hari ini; batch kedaluwarsa tetap bisa dipilih karena kiriman bisa
terlambat). Terukur sesudah: cakupan jaringan tetap 5 opsi, semuanya JKT.

**Tahun selalu ikut di tanggal layak pakai.** Batch beras demo layak sampai Maret tahun berikutnya; tanpa tahun, labelnya "19 Mar" — terbaca seolah bulan depan, dan di kartu penerimaan label itu dipakai memilih batch. `usableLabel` sekarang menulis "19 Mar 2027, 01.00" (juga membuatnya deterministik: tidak bergantung tahun berjalan). Di 375 px tanggal dibungkus `span.safety-nobr` supaya tidak pecah antara bulan dan tahun. Terukur: tabel batch 1440 & kartu 375 tanpa luapan, kolom "Layak sampai" membungkus dua baris dengan rapi.

**Keadaan batch terbaca tanpa membuka daftar.** Opsi di dalam `<select>` hanya identitas
(`komoditas · kg · kode wilayah`) karena teks panjang terpotong di 375 px (301 px). Keamanan + masa layak
ditaruh di baris `Keadaan batch: <status> · layak s/d <tanggal>` **di luar `<label>`** — kalau di dalam,
teks itu ikut menjadi nama field bagi pembaca layar.

**Gerbang yang tidak ada jangan dijanjikan.** Kalimat lama "0 dari 5 titik periksa sudah ditandai —
tandai sisanya sebelum barang dipakai" memerintah sesuatu yang tidak ditegakkan: tombol aktif di 0/5
(`disabled: false`, terukur) dan `POST /receipts` menerima snapshot kosong. Yang dipilih: mencatat
sebagian tetap boleh (memaksa 5/5 membuat orang mencentang tanpa memeriksa — bukti jadi palsu), tetapi
kalimatnya jujur: "… — N belum diperiksa. Boleh disimpan sebagian." Pesan sesudah simpan dipisah
(`receiptSavedSentence`) dan memakai bentuk lampau, karena versi lama menyuruh menandai ulang tepat
setelah catatannya tersimpan.

**Kalimat lain yang dirapikan.** Pembuka kartu kehilangan pengulangan "hitung ulang … yang dihitung
server" dan menyebut urutan tulisnya (catatan periksa → hitung ulang server). Contoh "Lainnya" tidak lagi
muncul tiga kali (label, placeholder, catatan bawah) melainkan sekali; catatan bawah kini bicara status
simpan. Label suhu menyebut batas yang benar-benar dipakai mesin — 0–8 °C untuk telur/ayam/wortel dan
15–30 °C untuk beras (`_SAFE_TEMP_BY_COMMODITY`, `backend/app/api/freshness.py`), bukan "sesuai" yang
harus ditebak petugas.

**Kendaraan berpendingin sengaja BUKAN titik periksa ke-6.** Rantai dingin sudah dihitung deterministik
oleh `/safety/evaluate` + `/freshness/evaluate` dari log suhu tersimpan (`excursion_minutes`), dan satu
titik periksa generik akan salah untuk beras yang justru butuh 15–30 °C. Keadaan khusus tetap bisa
ditulis di "Lainnya" — contohnya memang menyebut "kendaraan tanpa pendingin".

**Snapshot titik periksa memang tersimpan** sejak migrasi `016_batch_receipts` (`checked` JSONB,
`other_note`, `recorded_by`, `recorded_at`). Komentar lama di `lib/food-safety.ts` yang menyebut "sengaja
tidak dipersistensikan: backend tidak punya kolom" dikoreksi karena bertentangan dengan kartunya sendiri.
Id titik `warna` diganti `bau_warna` supaya sepadan dengan labelnya; baris lama tetap menyimpan kunci
lamanya (snapshot disimpan apa adanya).

**Aksesibilitas.** Lima kotak centang kini satu kelompok bernama (`<fieldset><legend>Titik periksa</legend>`,
bingkai bawaan dimatikan di CSS) dan penghitung "N dari 5" memakai `aria-live="polite"` supaya perubahan
terdengar tanpa memindahkan fokus.

Bukti: `_qa/penerimaan-barang/` (`probe-kartu.py`, `probe-opsi.py`, `probe-403.py`, `probe-sesudah.py`,
`probe-375.py`, `kartu-1440.png`, `kartu-sesudah-375.png`). Simpan nyata di :3010 → 201, `checked` berisi
`bau_warna`, `checked_count` 5, riwayat "5 titik · SPPG Head Demo" muncul tanpa memuat ulang halaman.

## Sesi demo (migrasi 024 & 025, 20 Okt 2026)

Permintaan pemilik: tampilan default **kosong**; tombol **"Siapkan data demo"** memanggil data dan mengaktifkannya
selama satu jendela waktu (bawaan 2 jam, maksimum 4 jam); ada **hitungan mundur**; perpanjangan menambah waktu
tanpa mengubah data berjalan; data **hanya bisa diubah selama sesi**; sesudah sesi habis data kembali kosong dan
perubahan hilang (mulai lagi dari template); waktu & tanggal disinkronkan saat tombol ditekan.

### Bentuk data

`demo_sessions` (satu baris per jendela): `status` (`active`/`expired`/`ended`), `started_at`, `expires_at`,
`anchor_now`, `ended_at`, `template_version`, `created_by`. `anchor_now` mencatat waktu server saat tombol
ditekan — jam **tidak** dibekukan, karena membekukan waktu membuat log suhu dan umur panen berhenti masuk akal.

`demo_session_id` (nullable, FK `demo_sessions.id`, `ON DELETE SET NULL`) ada di 13 tabel operasional: `batches`,
`decisions`, `batch_receipts`, `demand_records`, `supply_records`, `price_signals`, `menu_plans`, `delivery_events`,
`disposal_events`, `road_routes`, `supplier_exclusions`, `sap_mock_material_stock`, `sap_mock_purchase_orders`.
Tabel referensi (`users`, `locations`, `commodities`, `suppliers`) **tidak** diberi stempel: login dan peta harus
tetap jalan tanpa sesi.

### Kosong-secara-default dijaga oleh siklus data, bukan filter kueri

Percobaan pertama memakai `with_loader_criteria` untuk menyaring SELECT. Itu **dibuang** setelah terukur gagal:
banyak endpoint memilih kolom (`select(Batch.id, ...)`) atau memakai Core/bulk, sehingga kriteria ORM hanya
sebagian berlaku — `/batches` menjawab 0 padahal 118 baris ada, sementara `count` menjawab 118. Sekarang:

- **Mulai sesi** → kosongkan semua baris operasional (semua sesi, termasuk sisa sesi lain) → semai ulang → stempel
  massal (`tandai_sesi`) untuk baris yang lahir lewat bulk insert yang tidak melewati event flush.
- **Sesi berakhir / kedaluwarsa** → semua baris operasional dihapus; tabel referensi utuh.
- **Tanpa sesi sama sekali** → `sapu_tanpa_sesi()` menghapus baris `origin='demo'` yang **belum ber-stempel**, dijeda
  10 detik agar tidak menjadi DELETE di setiap request dan dipanggil dari jalur baca (`aktif()`). Ini menutup celah
  yang terukur 21 Okt 2026: 25 keputusan demo lahir lewat jalur lama (`/demo/seed`, `/demo/refresh`) tanpa stempel;
  karena tidak ada sesi untuk ditutup, `kosongkan_bertanda()` tidak pernah berjalan dan data itu hidup selamanya.
  Batas amannya `origin='demo'` — baris kanonik (`origin='seed'`) tidak pernah disentuh, jadi peta, KPI, dan suite
  backend tetap punya data.
- **Boot** → bila mode sesi menyala dan tidak ada sesi aktif, hanya baris **ber-stempel** (milik sesi) yang
  dibersihkan. Sebelum 21 Okt 2026 boot memanggil `bersihkan_warisan()` = hapus SELURUH baris operasional, dan
  efeknya terukur: setiap `uvicorn --reload` saat menyunting kode memusnahkan template demo (121 batch → 0) tanpa
  sesi. Tampilan tetap kosong tanpa sesi karena UI menyembunyikan data, jadi pembersihan menyeluruh tidak pernah
  dibutuhkan untuk perilaku itu. Restart di tengah sesi juga tidak menyentuh data.
- **Membangun template** (`app.seed.demo_template`, dipakai tombol *Bangun ulang data*) selalu memastikan ada sesi
  aktif lebih dulu (`pastikan_sesi`). Alasannya bukan kosmetik: baris hasil semai ber-`origin='demo'` dan belum
  ber-stempel sampai pembekuan selesai, sehingga penyapu di proses aplikasi bisa menghapusnya di tengah build
  (terukur: build "sukses" tetapi berakhir 0 batch saat UI sedang polling).

Konsekuensi yang dinyatakan terbuka: bukti sesi yang sudah berakhir tidak disimpan sebagai arsip di DB. Itu
konsekuensi langsung dari "kembali kosong" yang diminta; kalau kelak perlu audit pasca-demo, langkahnya adalah
menulis dump sebelum pembersihan, bukan mempertahankan baris di tabel utama.

### Penjagaan mutasi

`butuh_sesi_aktif` (dependency FastAPI) membalas **409** untuk `POST /demo/seed`, `/demo/timeseries`,
`/demo/timeseries/purge`, `/demo/refresh`, `/demo/event1`, dan `POST /receipts` saat mode sesi menyala tanpa sesi
aktif. Dengan `DEMO_SESSION_ENFORCE=false` (bawaan repo/CI) dependency itu tidak melakukan apa pun, sehingga
1.200+ tes lama tetap sah.

### UI

- `DemoControlPanel` menampilkan kartu sesi: status (`Belum ada sesi` / `Sesi demo berjalan`), **hitungan mundur**
  dari `remaining_seconds` server (tick lokal 1 detik, diselaraskan ulang tiap 20 detik), tombol
  **Perpanjang 30 menit** dan **Akhiri sesi**. Tombol "Siapkan data demo" memulai sesi (menyemai + menyalakan jam),
  lalu memuat ulang halaman supaya semua tab membaca data sesi.
- `DemoSessionBanner` muncul di semua tab saat `enforced && !active`: menjelaskan bahwa data memang kosong dan
  menyediakan tombol "Buka Demo Control" (atau petunjuk menghubungi Kepala SPPG untuk peran non-penyetuju).
- Hitungan mundur tidak memakai jam browser untuk memutuskan apa pun; sesi yang lewat waktu tetap ditutup server.

### Verifikasi

E2E di :3010 (Kepala SPPG): kosong → banner + kartu "Belum ada sesi" → klik **Siapkan data demo** → sesi berjalan
`1 j 59 m`, banner hilang, 13 tabel terisi dan **0 baris tanpa stempel** → **Perpanjang 30 menit** menjadi
`2 j 29 m`, id sesi sama, data utuh → **Akhiri sesi** → 13 tabel kembali 0 dan banner kosong muncul lagi.
`POST /receipts` saat sesi = 201 (batch sendiri) / 403 (batch luar cakupan, aturan lama); tanpa sesi = 409.
Backend: gerbang penuh **1.213 lulus / 15 dilewati / 0 gagal** (20 Okt, DB kanonik 8 Okt + deret waktu); frontend: **142 berkas / 1.589 tes**, `tsc` 0, `next lint` 0.
Bukti: `_qa/sesi-demo/` (`diagnosa-sesi.py`, `e2e-sesi-penuh.py`, `e2e-ui.py`, `ui-1-kosong.png` … `ui-4-kosong-lagi.png`).


### Kalimat kartu sesi (revisi 20 Okt, sore)

Tiga kalimat lama dibuang karena menyesatkan atau mengulang: (a) pengingat "Data demo hanya bisa diubah selama sesi — tekan Siapkan data demo" yang tampil tepat di bawah `pesanSesi` yang sudah mengatakan hal yang sama untuk keadaan kosong/habis; (b) status yang menyuruh menekan "Buat/perbarui data" — tombol itu milik panel DATA, bukan kartu sesi; (c) judul tombol "Seeder relatif hari ini + muat ulang 4 kasus skrip" (istilah internal). Gantinya: subjudul "Mengisi data demo untuk satu jendela waktu … menekan lagi saat sesi berjalan tidak memuat ulang data", dan baris status "Data demo siap dipakai selama sesi ini." / "Data demo belum dimuat — mulai dengan Siapkan data demo." Tes sumber `frontend/tests/demo-session.test.ts` mengunci ketiganya (`not.toContain` untuk kalimat lama) supaya tidak kembali.

### Prasyarat gerbang backend di checkout ini

Suite memakai database demo bersama: `docker compose exec -T -e DEMO_SESSION_ENFORCE=false backend pytest -q`. Flag harus dimatikan lewat env, bukan `.env`, karena `.env` lokal menyalakannya untuk demo. Data kanonik yang diharapkan tes (menu 2 Okt, rencana 20 Okt–5 Nov) berasal dari `python -m app.seed.seed_data --reference-time 2026-10-08T12:00:00+00:00 --with-demo-users --with-demo-suppliers` lalu `generate_timeseries()`; menjalankan `seed_data` dengan referensi "hari ini" menggeser jangkar dan membuat `test_agenda_api` merah. Setelah gerbang, semai ulang sebelum demo bila sesi demo sedang mati.


### Riwayat 30 hari di sesi demo + label periode bulan (20 Okt 2026, malam)

**Masalah yang dilaporkan:** pemilih periode KPI (24 jam / 7 hari / 1 bulan) menampilkan angka yang sama. Terukur: `period.start` berbeda (19 Okt / 13 Okt / 20 Sep) tetapi hampir semua nilai identik, karena penyemai sesi menaruh fakta di satu hari — jendela 7 hari dan 30 hari memuat himpunan baris yang sama.

**Perbaikan backend.** `/demo/session/start` kini menyemai riwayat `DEMO_SESSION_HISTORY_DAYS` (bawaan **30**) lewat `generate_timeseries(now-30h, now, interval_hours=24)` — pasokan, harga, permintaan 30 hari; rencana menu/kiriman/limbah tetap mulai `EVENT_DEMO_START` (8 Okt) supaya Meal Continuity tidak jatuh hanya karena hari lama belum punya kiriman. Biaya: start **36,8 s** (sebelumnya ±35 s), 2.916 baris distempel, 0 baris tanpa stempel. `generate_timeseries`/`preview_timeseries`/`plan_all` mendapat parameter opsional `menu_start` (default `None` = perilaku lama).

Hasil KPI (DB sesi, 20 Okt):

| Metrik | 24 jam | 7 hari | 1 bulan (Oktober) |
|---|---|---|---|
| Meal Continuity | 100,00% | 100,00% | 98,41% |
| Avoidable Food Loss | **1,64%** | **0,42%** | **0,17%** |
| Procurement Price Deviation | **2,66%** | **2,92%** | **3,41%** |
| Safe Delivered Cost | Rp18.062.478 | sama | sama |
| Decision Time / Evidence | 20 mnt / 100% | sama | sama |

Tiga metrik terakhir tetap sama secara jujur: SDC/waktu keputusan/kelengkapan bukti dihitung dari keputusan + PO yang semuanya bertanggal hari ini (`kpi_service.py`), bukan dari jendela fakta.

**Jendela "1 bulan".** Tombol ketiga bukan lagi "30 hari" bergulir: `kpiWindowRange("30d")` mengembalikan awal **bulan berjalan menurut WIB** (1 Okt 00.00 WIB = 30 Sep 17.00 UTC) sampai sekarang, sehingga label periode menulis satu bulan ("Oktober 2026"). Riwayat semai 30 hari tetap cukup untuk menutup bulan berjalan (maksimal 31 hari).

**Perbaikan UI.** `periodeBulan(start, end)` di `lib/kpi.ts` menggantikan tanggal persis: "Periode Oktober 2026" (satu bulan) dan "Periode September – Oktober 2026" (lintas bulan, tahun ditulis sekali; lintas tahun ditulis dua kali). Format memakai zona Asia/Jakarta — 31 Okt 20.00 UTC = 1 Nov WIB.


### Semantik penutupan sesi (koreksi 20 Okt 2026, menjelang gate)

`akhiri()` semula menghapus **semua** baris operasional (`kosongkan_kecuali(db, None)`). Itu benar untuk demo (semua baris berstempel) tetapi mematikan isolasi suite: 58 tes backend lain kehilangan data ketika satu tes sesi berjalan lebih dulu. Kini `akhiri()` memakai `kosongkan_bertanda()` — menghapus baris yang **punya stempel sesi mana pun**, menyisakan data kerja tanpa stempel (kanonik). Start sesi dan boot tanpa sesi tetap mengosongkan total, jadi janji "default kosong" tidak berubah; yang berubah hanya efek samping "Akhiri" terhadap data non-sesi. Tes `test_demo_session.py` diberi `pytestmark` skip saat `DEMO_SESSION_ENFORCE=false` karena berkas itu memang mengubah seluruh tabel; jalankan terpisah dengan flag menyala.
### Skala kanonik: radius, bayangan, label ringkas, font (20 Okt 2026)

Hasil audit konsistensi seluruh halaman (10 tab + login, computed style di aplikasi hidup).
Sebelumnya berkas CSS memuat 12 nilai radius mentah, 17 literal bayangan dengan 11 alpha,
dan lencana status dengan tiga tinggi berbeda. Sekarang hanya token di bawah yang sah;
penjaganya tes kontrak (`tests/radius-scale-css`, `tests/token-bayangan`,
`tests/label-ringkas-geometri`, `tests/token-alias-css`, `tests/token-warna-komponen`,
`tests/sisa-audit-desain`).

| Peran | Token | Nilai |
|---|---|---|
| Kartu | `--radius` | 12 px |
| Dock/panel melayang | `--radius-dock` | 14 px |
| Kontrol besar (input, select, modal) | `--radius-control` | 10 px |
| Kontrol kecil, item rail | `--radius-control-sm` | 8 px |
| **Tombol (semua varian)** | literal | **999 px** — sejak 27 Okt 2026 permintaan pemilik: tombol kotak → oval. `.button` di `globals.css` + daftar kelas di `tombol-pil.css`; kartu/baris yang seluruhnya bisa diklik (`.link-button`, `.map-row-btn`, `.sa-row-btn`, `.queue-item-action`, `.today-tile`) SENGAJA tidak dipil |
| Chip, lencana, penanda peta | `--radius-chip` | 4 px |
| Pil / bulat | literal | 999px / 50% |

Bayangan: `--shadow-1..3` (elevasi umum) + peran `--shadow-pin`, `--shadow-pin-hover`,
`--shadow-pin-soft`, `--shadow-pin-core`, `--shadow-pin-active`, `--shadow-cluster`,
`--shadow-pop`, `--shadow-float`, `--shadow-control`, `--shadow-dock`, `--ring-hairline`.
Tidak ada lagi `rgba(15, 23, 42, …)` yang ditulis langsung di `box-shadow`.

Label ringkas (lencana status): satu geometri `padding: 2px 8px; line-height: 16px;
min-height: 22px; font-size: var(--fs-1); white-space: nowrap` untuk `.board-badge`,
`.kpi-state`, `.safety-state`, `.shipping-tag`, `.shipping-tag-fail`, `.integration-badge`,
`.shipment-pill`, `.shipment-chip`, `.route-tag`, `.reach-tag` — diukur tinggi 22 px seragam,
teks tidak terpotong. Kendali pil (`.commodity-pill`, `.board-sort-pill`,
`.route-focus-pill`) dikecualikan: tombol dengan target sentuh sendiri. `.shipment-event-tag`
juga dikecualikan karena tag inline di dalam baris teks.

Font: `--font-ui` (Fira Sans) dan `--font-data` (Fira Code). `code`/`kbd`/`samp`/`pre`
wajib memakai `--font-data`; sebelumnya `code` jatuh ke `monospace` bawaan peramban.

Alias warisan `--primary` / `--danger` kini dideklarasikan (`var(--accent-strong)` /
`var(--status-danger)`), karena tanpa deklarasi itu blok agenda, pil periode KPI, dan pil
urutan papan jatuh ke teal `#005C55` — di luar tema.


### Persetujuan penerimaan → stok → Overview (migrasi 026, 20 Okt 2026)

**Yang dilaporkan pemilik:** demo "barang sampai → ada approve barang diterima → data yang diperlukan (mis. Overview) berubah". Sebelumnya kartu Penerimaan barang hanya mencatat daftar periksa lalu menghitung ulang keamanan/kesegaran; tidak ada keputusan dan tidak ada tulisan stok, sehingga Overview (dibaca dari `supply_records`) tidak bergerak.

**Bentuk yang dibangun.** Dua lapis, dipisah tegas:

1. `POST /receipts` — petugas mencatat. Status lahir `menunggu`, **belum** menambah stok.
2. `POST /receipts/{id}/approve` — hanya `sppg_head`, scope lokasi sendiri. Menulis SATU baris `supply_records` (source `manual`) sebesar `stok terakhir + batch.quantity_kg`, lalu menandai catatan `disetujui`.
   `POST /receipts/{id}/reject` — alasan wajib (≥3 karakter), tidak menulis stok.

Aturan yang ditegakkan server (bukan UI):
- batch `safety_status='fail'` → 409 "barang berstatus TIDAK AMAN";
- batch lewat `usable_until` → 409 "barang sudah kedaluwarsa";
- satu batch paling banyak satu penerimaan disetujui — unique index parsial `uq_batch_receipts_satu_disetujui` (klik ganda tidak menggandakan stok);
- approve idempoten: balasan kedua `sudah: true` dengan `supply_record_id` yang sama;
- approve oleh peran lain → 403; batch lokasi lain → 403.

**Kenapa stok = terakhir + kg, bukan kg saja.** Overview membaca baris supply TERBARU per lokasi. Menulis hanya `batch.quantity_kg` membuat pasokan turun bila stok sebelumnya lebih besar. Terukur: ayam Jakarta 200 kg → approve 145 kg = **345 kg**; approve 213 kg berikutnya = **558 kg**.

**Bukti angka (sesi demo 20 Okt).** Ayam Jakarta: `supply 200 → 345 → 558`, `demand 215`, status peta `shortage → surplus`; kartu Overview: "Selisih pasokan Jakarta +343 kg · lebih 160% dari kebutuhan · Pasokan terpantau 558 kg (260%)". Tangkapan: `_qa/sesi-demo/penerimaan/overview-setelah-approve.png`.

**UI.** Badge status di riwayat (`Menunggu persetujuan` / `Disetujui` / `Ditolak`), baris keputusan terpisah ("Disetujui SPPG Head Demo · waktu · +196 kg stok"), panel `.safety-approve` dengan tombol "Setujui & masukkan stok" dan "Tolak penerimaan" (textarea alasan). Batch kedaluwarsa menampilkan peringatan dan tombol setujui disembunyikan. Setelah approve, `page.tsx` mengambil ulang `todayQuery`, `mapQuery`, `decisionsQuery` — angka baru datang dari server.

**Tes.** `backend/tests/test_receipts_approval.py` (7 tes): catat tidak menulis stok; approve menambah tepat sebesar kg dan idempoten; reject wajib alasan dan tidak menulis stok; peran lain 403; lokasi lain 403; barang gagal aman 409; barang kedaluwarsa 409. Frontend: `receiptStatusLabel`, `receiptRows` status/kg/alasan, badge & baris riwayat.

### Redesign tata letak "Keamanan Pangan" (20 Okt 2026)

**Masalah terukur.** Halaman setinggi 5.400 px di 1440x900; tabel "Status keamanan per batch"
memuat 40+ baris sekaligus tanpa saringan, sehingga batch gagal tenggelam di antara batch aman
dan pengguna harus menggulir jauh. Di 768 px delapan kolom memaksa tanggal "Layak sampai"
pecah tiga baris; di 375 px tabel hanya bisa digeser mendatar.

**Perubahan.**
1. **Toolbar saringan** di atas daftar: chip `Perlu tindakan`, `Gagal uji`, `Perlu verifikasi`,
   `Aman`, `Semua` — masing-masing membawa jumlah, sehingga isi saringan diketahui sebelum
   diklik. `Perlu tindakan` = gagal + perlu verifikasi + ditahan. Kotak cari menyaring
   lokasi/komoditas tanpa peduli huruf besar/kecil; saringan dan pencarian digabung.
2. **Paginasi 8 baris** memakai `Pager` yang sama dengan Pemasok/Kiriman; rentang "1–8 dari N"
   selalu tertulis dan `aria-live`.
3. **Tombol prioritas** di kartu Ringkasan: "Tinjau N batch gagal" memindahkan saringan ke
   `gagal` lalu menggulir ke daftar.
4. **Kartu berlabel di ≤860 px**: `thead` disembunyikan, setiap `td` memakai `data-label`
   sehingga baris menjadi kartu "Asal / Komoditas / Jumlah / Status keamanan / Kesegaran /
   Layak sampai / Sisa masa", tombol tindakan turun ke bawah kartu. Ambang 860 px dipilih
   karena pada 768 px tabel masih pecah tiga baris.
5. **Daftar periksa dua kolom** di ≥900 px — lima titik periksa terlihat tanpa menggulir.
6. **Perbaikan token**: `.commodity-pill-active` kini punya aturan dasar (sebelumnya hanya
   berlaku di dalam `.filter-card`, sehingga pil aktif di luar filter tampil putih-di-putih).
   Radius baru memakai `var(--radius)` / `var(--radius-control)`, bukan px lepas.

**Hasil terukur (sesi demo 20 Okt, 1440x900).** Tinggi halaman 5.400 → 2.775 px; default
"Semua" menampilkan 8 baris pertama dari N; klik `Gagal uji` → "1–1 dari 1"; cari "beras" →
"1–2 dari 2"; 375 px dan 768 px `docOverflow = 0`; 768 px `thead` `display:none` dan kartu
berlabel tampil. Gerbang frontend **146 berkas / 1612 tes lulus**, `tsc` 0, `next lint` 0.

**Yang TIDAK berubah (kontrak halaman).** Sumber angka tetap `GET /batches` (satu sumber),
cakupan tetap "lokasi saya" default, aksi Uji ulang / Ajukan keputusan / Tahan tetap di baris,
dan penerimaan barang tetap dua langkah (catat → setujui). Redesign hanya menyusun ulang
penyajian; tidak ada endpoint atau angka baru.

### Penerimaan dua langkah + titik periksa per komoditas (20 Okt 2026)

**Permintaan pemilik.** "Pilihan di bagian Penerimaan barang mungkin bisa dibuat pilihan
komoditasnya baru memilih batchnya" dan "titik periksa mungkin bisa disesuaikan ceklisnya
dengan komoditasnya".

**Pemilih dua langkah — revisi setelah riset (20 Okt 2026).** Versi pertama memakai dua
`<select>` bertingkat (komoditas → batch). Itu dibuang karena riset menunjukkan pola tersebut
justru sumber kebingungan:

- NN/g, *Dropdowns: Design Guidelines*: "avoid interacting menus, wherein the options in one
  menu change when users select something in another menu — users get very confused when
  options come and go".
- NN/g, *Does Your Form Really Need a Dropdown List?*: dropdown menyembunyikan pilihan,
  menambah dua klik, dan bermasalah untuk pengguna keyboard/motorik; GOV.UK menyarankan select
  hanya sebagai pilihan terakhir.
- DWP Design System, *Filters*: "use radios, not dropdowns" untuk memilih satu dari daftar
  pendek; GOV.UK *Radios*: radio di kiri label, semua opsi terlihat, jangan bergantung warna.

Karena itu sekarang: **Langkah 1 — Komoditas** berupa pil yang terlihat semua (dengan jumlah
batch), dan **Langkah 2 — Barang yang belum diuji** berupa daftar kartu radio (1–3 kartu),
bukan dropdown. Tiap kartu menampilkan berat · kode lokasi, "belum diperiksa · layak s/d …",
dan lencana **Belum diuji**.

**Hanya barang yang BELUM dinilai (revisi 20 Okt 2026).** Pemilik memilih tegas: "hanya untuk
barang yang belum dinilai; yang sudah dinilai jangan dimasukkan situ." Artinya filter bukan
`receipt_status`, melainkan `safety_status === "pending"` (ditambah `receipt_status === null`).
Batch **Aman**, **Gagal uji**, dan **Perlu verifikasi** sudah punya hasil penilaian, jadi tidak
pernah muncul di form penerimaan. Konsekuensinya, setelah "Catat hasil terima & hitung ulang"
status berubah dari `pending` menjadi `pass`/`needs_verification`/`fail` dan batch **langsung
hilang** dari pilihan — bukan kembali dengan label "menunggu persetujuan".

**Antrean "Menunggu persetujuan" terpisah.** Karena barang yang sudah dicatat keluar dari form,
persetujuan tidak lagi menumpang di riwayat batch terpilih. `GET /receipts/menunggu` (baru)
mengembalikan catatan `menunggu` terbaru per batch, ter-scope lokasi pengguna; kartu
**Menunggu persetujuan** menampilkan komoditas · kg · lokasi, jumlah titik periksa, pencatat,
waktu, serta tombol "Setujui & masukkan stok" / "Tolak". Setelah diputuskan, item hilang dari
antrean dan stok/Overview diambil ulang dari server. Tanpa antrean ini, approval akan
kehilangan pintu masuknya begitu filter "belum dinilai" diberlakukan.

**Data demo.** Seed `jakarta_lengkap.seed_batches` menambah tiga barang baru datang berstatus
`pending` (ayam 90 kg, beras 300 kg, wortel 120 kg; log suhu ayam/wortel 4 °C, beras 27 °C).
Status `pending` tidak lagi dibuat oleh rotasi batch kanonik, supaya kartu Penerimaan hanya
berisi kedatangan yang memang belum dinilai. `GET /batches` juga diminta dengan `limit=500`
(plafon server) — tanpa itu, 50 baris terbaru membuat barang baru datang tidak terkirim.

Mengganti komoditas atau batch mengosongkan centang karena kalimat titik periksa bergantung
komoditas dan batch berbeda = barang berbeda. Mengganti komoditas memilih batch pertama
kelompoknya (paling mendesak); urutan kelompok mengikuti kemunculan pertama pada daftar yang
diurutkan tenggat.

**Batas suhu safety = freshness (perbaikan 20 Okt 2026).** `/safety/evaluate` sebelumnya memakai
`settings` 0–8 °C untuk semua komoditas, sedangkan `/freshness/evaluate` sudah memakai
15–30 °C untuk beras. Akibatnya mencatat penerimaan beras pada 27 °C langsung `fail` dan
approval ditolak 409. Peta kini dipusatkan di `app/core/commodity_limits.py` dan dipakai kedua
endpoint.

**Bukti UI (sesi demo, 1440).** Pil hanya `ayam 1`, `beras 1`, `wortel 1`; kartu menampilkan
`90 kg · JKT` dengan lencana **Belum diuji**, tanpa satu pun batch Aman/Gagal uji. Mencatat
beras 300 kg → pil beras hilang, kartu **Menunggu persetujuan** muncul; Setujui → pesan
"300 kg masuk stok", `/balance/Jakarta/beras` `881,97 → 1.181,97 kg` (kekurangan
`2.070,14 → 1.770,14 kg`). Di 375 px `docOverflow = 0`. Tangkapan:
`_qa/keamanan-pangan/penerimaan-hanya-pending-1440.png`, `penerimaan-hanya-pending-375.png`,
`penerimaan-antrean-beras-1440.png`.

**Titik periksa per komoditas.** `receivingChecks(komoditas)` mempertahankan **lima id yang
sama** (`kemasan`, `suhu`, `bau_warna`, `timbang`, `lot`) supaya catatan lama tetap terbaca
dan penghitung "N dari 5" tidak berubah; yang berbeda hanya kalimatnya:

| Komoditas | Kemasan | Suhu | Ciri khas |
|---|---|---|---|
| ayam | kemasan/segel utuh | 0–8 °C | tidak berbau asam/amis, warna tidak pucat |
| telur | rak/tray utuh | 0–8 °C | tidak retak atau pecah, permukaan bersih |
| beras | karung utuh | 15–30 °C | tidak berjamur/apek, butir tidak berkutu |
| wortel | krat utuh | 0–8 °C | tidak layu/berlendir, warna cerah |
| lain | kemasan utuh | 0–8 °C | bau & warna normal |

Rentang suhu menyalin `_SAFE_TEMP_BY_COMMODITY` di `backend/app/api/freshness.py` — satu
sumber, bukan angka baru di layar. Isian "Lainnya" dan dua field tetap (timbangan, nomor lot)
tidak berubah, dan server tetap menerima snapshot `checked` seperti sebelumnya (tanpa migrasi).

**Bukti UI (sesi demo, 1440).** Opsi komoditas: `ayam · 2 batch · 200 kg`,
`wortel · 1 batch · 170 kg`, `beras · 2 batch · 900 kg`. Memilih beras → batch
`540 kg · JKT · Aman` / `360 kg · JKT · Aman`, dan lima titik periksa berubah menjadi
karung, 15–30 °C, apek, timbangan, nomor lot. Tangkapan:
`_qa/keamanan-pangan/penerimaan-beras-1440.png`.

## 24. Navigasi "lompat ke bagian" jadi komponen bersama (20 Okt 2026)

Nav menempel yang dipakai halaman **Decision & Evidence** dipindahkan keluar dari komponen
itu supaya halaman lain memakai komponen yang **sama**, bukan salinan. Permintaan pemilik:
"jangan di semua halaman — ke halaman yang benar-benar butuh saja".

**Yang dipakai bersama.**

| Berkas | Isi |
|---|---|
| `components/SectionJump.tsx` | `<nav class="section-jump" aria-label>` + daftar tautan `<a href="#id">`; tautan, **bukan** tombol, supaya bisa dibuka di tab baru dan terbaca pembaca layar sebagai daftar tujuan |
| `lib/hooks/useActiveSection.ts` | pengukur "bagian yang sedang dibaca": listener gulir di-throttle `requestAnimationFrame`, bagian **terakhir** yang tepinya melewati ambang 140 px |
| `lib/section-jump.ts` | daftar tujuan per halaman (`evidenceSections`, `overviewSections`, `safetySections`) — dibangun dari kondisi render yang sama dengan bagiannya |
| `app/globals.css` | `.section-jump`, `.section-jump-link`, `.section-jump-link[aria-current="true"]`, `.jump-target` |

**Aturan pemakaian (kenapa tidak semua halaman).** Nav hanya dipasang bila halaman
**≥ ±2,5 layar** dan punya **≥ 3 bagian tetap**; maksimum **lima** tujuan; hanya muncul bila
datanya sudah ada. Halaman yang panjangnya sudah dipecahkan cara lain tidak diberi nav:

| Halaman | Keputusan | Alasan |
|---|---|---|
| Decision & Evidence | nav (5 tujuan) | sudah; kini memakai komponen bersama |
| Keamanan Pangan | nav (3–5 tujuan) | lima bagian panjang, aksi tulis tersebar di beberapa bagian |
| Overview | nav (4–5 tujuan) | delapan blok satu gulungan; sudah ada `scrollIntoView` ke `#overview-map` |
| Hari Ini | **tidak** | sudah punya jalur pintas yang lebih baik: lima tile tombol yang menggulir **dan** memindahkan fokus (`TodaySummary.jumpToSection`) |
| Recommendations | **tidak** | pencarian + filter status + urutan + "tampilkan 24 lagi" sudah memendekkan halaman |
| Pemasok, KPI & Kualitas, Agent Log, Demo Control | **tidak** | tiga bagian atau kurang, dan/atau halamannya pendek |

**Tautan mati dilarang.** Halaman yang bagiannya bergantung pada data membangun daftar nav
dari kondisi render yang sama: "Penerimaan barang" (Keamanan Pangan) hanya bila peran punya
SPPG sendiri **dan** batch selesai dimuat; "Keputusan keamanan lokasi ini" hanya bila daftar
keputusan tersedia; "Kiriman" (Overview) hanya bila kartu kiriman benar-benar dirender
(kartu itu tidak merender apa pun saat daftar kiriman kosong).

**Gaya (semua dari token, tanpa palet baru).** Satu baris `nowrap` yang bisa digulir mendatar;
menempel `top: 72px` (top bar 64 + 8) dengan latar `rgba(255,255,255,.94)` + `backdrop-filter:
blur(8px)`; teks 12 px (`--fs-1`, lantai teks); pil `border-radius: 999px`, batas transparan,
`--line-strong` saat hover; keadaan aktif = `--accent-soft` + `--accent-strong` + tinta
`--accent`; target sentuh 44 px di `(pointer: coarse)`/≤720 px; cincin fokus 2 px `--accent`;
gerak 120 ms dimatikan saat `prefers-reduced-motion`; latar padat saat
`prefers-reduced-transparency`; `Highlight` saat `forced-colors`; **disembunyikan saat
`@media print`** (kertas tidak punya gulir).

**Jangkar tidak boleh tertutup.** `.jump-target` (`scroll-margin-top: 132px`) dipasang sebagai
kelas pada elemen tujuan, bukan daftar id — sebelumnya daftar lima id ditulis manual di
`evidence-dossier.css`, sehingga halaman baru harus menambah selektor (WCAG 2.2 SC 2.4.11).

**Tes yang mengunci bentuk ini.**

- `tests/section-jump.test.tsx` — markup, tepat satu `aria-current="true"`, posisi mengikuti
  gulir (rect di-stub), tujuan yang tidak ada di DOM dilewati, isi daftar tiap halaman.
- `tests/food-safety-board.test.tsx` — nav hanya memuat tujuan yang bagiannya dirender;
  setiap tujuan punya tepat satu sasaran ber-id.
- `tests/overview-section-jump.test.tsx` — halaman memakai komponen + daftar bersama, tiap
  tujuan punya sasaran `jump-target`.
- `tests/evidence-dossier.test.tsx` — nav memakai `.section-jump` di `globals.css`
  (`position: sticky`, `top: 72px`, `--accent-soft`) dan `.jump-target` 132 px.

### Ringkasan pengawasan & bukti suhu — tenggat, kebaruan, syarat (29 Okt 2026, lanjutan)

Permintaan pemilik: *"upgrade design upgrade ringkasan pengawasan, suhu semaksimal mungkin namun
tetap sama atau cocok dengan design lainnya"*. Arah yang diambil: menambah **informasi yang belum
ada**, bukan mengulang angka yang sudah ada — keputusan 29 Okt sebelumnya (satu angka satu arti,
tanpa bar/legenda di Ringkasan) tetap dipegang.

**Ringkasan pengawasan.**
- Baris **"Paling mendesak"**: satu batch yang masih BOLEH dipakai dengan `usable_until` terdekat,
  mis. `PALING MENDESAK · wortel · Bandung · 2 hari 20 jam lagi`. Batch gagal dan batch ditahan
  tidak ikut (keduanya tidak boleh dialokasikan, jadi "segera pakai" menyesatkan); kalau tanggalnya
  sudah lewat labelnya berganti menjadi **"Sudah lewat"** dengan tinta bahaya — datanya tidak
  disembunyikan, kalimatnya tidak menyarankan memakainya. Sumber: `hoursLeft`/`hoursLabel` server.
- **Berat di bawah angka**: `failedKg` kini dicetak di bawah "Gagal uji" (sebelumnya hanya
  "Ditahan"), sehingga angka gagal terbaca bersama akibatnya. Berat yang tidak dikirim server tetap
  ditulis "berat tidak tercatat" untuk kelompok Ditahan.
- **Label tombol** menyebut jumlah: "Tinjau N batch perlu tindakan" memakai
  `needsVerification + quarantined + unchecked`, bukan kalimat tanpa angka.

**Bukti suhu.**
- **Kebaruan bukti**: setiap baris mencetak `dibaca <waktu>` dari `observed_at` (mis.
  "dibaca 28 Okt 2026 06.20"). Tanpa `observed_at`, tidak ada kalimat waktu — bukan "—".
- **Penanda "wajib dingin"** untuk baris dengan `cold_chain_required = true`: syarat, bukan
  keadaan, jadi bentuknya netral (garis + teks redup) dan **setinggi lencana keadaan** di
  sebelahnya (terukur 87x22 vs 86x22, selisih 0 px).
- **Ukuran bukti**: kaki kartu menyebut `N sampel tercatat` (jumlah `sample_count` yang dikirim);
  tidak ada satu pun jumlah → kalimat tidak dicetak (0 sampel adalah klaim yang tidak dibuat server).
- **Catatan "menuntut bukti"** tidak lagi kotak amber penuh dengan pagar kiri 4 px — pola yang sama
  dengan putusan di Ringkasan: satu titik + satu kalimat (terukur: latar transparan, titik 8 px
  `--warn-ink`).

Kelas CSS baru: `.safety-deadline`, `.safety-deadline-label`, `.safety-deadline-body`,
`.safety-deadline-time`, `.safety-count.is-danger .safety-count-note` (di `app/theme-ext.css`) dan
`.rowBadges`, `.coldChain` (di `TemperatureEvidenceCard.module.css`). Tidak ada kelas tes-sensitif
yang diubah.

**Bukti terukur** (localhost:3010, peran Kepala SPPG Bandung, 1247 px): Ringkasan 947x233 dengan
baris tenggat 911x20 (13 px, label 12 px kapital), Bukti suhu 947x447 dengan enam baris 454x76,
tanpa gulir mendatar; 390 px `docScrollWidth` = `docClientWidth` = 390 (tinggi halaman 8.655 px
karena tabel menjadi kartu berlabel). Gerbang: `tsc` 0, `next lint` 0, **223 berkas / 2.560 tes
lulus**, build `BUILD_ID=xb_mNGteO2N0HbVkfLPZU`.

**Urutan bagian Keamanan Pangan (27 Okt 2026).** Permintaan pemilik: "atur urutan dari tiap
bagian". Halaman ini kini mengalir **keadaan → bukti → tenggat → tindakan → rujukan → konteks →
jejak audit**:

| # | Bagian | Peran dalam alur |
|---|---|---|
| 1 | Ringkasan pengawasan | keadaan + penghalang |
| 2 | Bukti suhu | dasar bukti untuk status di atasnya |
| 3 | Batch perlu segera dipakai | tenggat ≤ 48 jam |
| 4 | Penerimaan barang | tindakan tulis: uji barang datang |
| 5 | Menunggu persetujuan | tindakan tulis: setujui/tolak |
| 6 | Status keamanan per batch | rujukan panjang (± 1.200 px) + filter |
| 7 | Pasokan masuk | konteks kiriman menuju lokasi |
| 8 | Keputusan keamanan lokasi ini | jejak audit |

Perubahan yang diambil: kartu **"Pasokan masuk"** (± 680 px, tanpa aksi) dulu duduk di antara
kartu tenggat dan dua kartu bertindak, sehingga memutus urutan tindakan; sekarang ia sesudah
tabel, dan kedua kartu bertindak (Penerimaan, Menunggu persetujuan) jadi berdampingan. Nav
memegang **lima** tujuan sesuai batas §24 dan tetap urut dengan halaman: Ringkasan, Bukti suhu,
Penerimaan, Status per batch, Keputusan — "Segera dipakai" tidak lagi memakan jatah karena hanya
satu kartu di bawah panel bukti, sedangkan "Menunggu persetujuan" dan "Pasokan masuk" tetap punya
jangkar (`safety-persetujuan`, `safety-pasokan`) supaya bisa ditautkan langsung. Dikunci oleh
`tests/safety-section-order.test.ts` (urutan jangkar di komponen vs urutan nav) dan
`tests/section-jump.test.tsx`.

## 25. Panel "Bukti integrasi per komponen" dicabut dari Agent Log (21 Okt 2026)

**Keputusan.** Tab **Agent Log** berhenti di jejak langkah agen (`.agent-console`).
Papan "Bukti integrasi per komponen" (`IntegrationStatusPanel`, W-3 2026-10-17) tidak
lagi dipasang di sana — permintaan pemilik 21 Okt: bagian itu yang dihapus, bukan
output jejak per langkah.

**Yang TIDAK berubah.** `components/IntegrationStatusPanel.tsx`, hook
`useIntegrationStatus`, endpoint `/integrations/status`, dan tes kontraknya
(`tests/integration-status.test.tsx`) tetap utuh: panelnya hanya tidak dimount.
Kalau nanti dibutuhkan lagi (mis. di Pengaturan), pasang kembali di sana dan ubah
tes `tests/prd-nav.test.tsx` yang memaku "tidak dipasang di page.tsx".

**Jejak per langkah tetap apa adanya.** `<pre class="trace-output">` berisi
`output_summary` TIDAK dihapus; §3.4 tetap berlaku ("output ringkas"). Keputusan
sementara 20 Okt untuk menyembunyikannya dibatalkan pemilik 21 Okt.

**Salinan label Demo Control.** Lipatan narasi supervisor berjudul **"Hasil
supervisor"** — keterangan "(apa adanya dari model)" dibuang karena itu catatan
internal, bukan bahasa layar (`components/DemoControlPanel.tsx`, dipaku di
`tests/demo-control-panel.test.tsx`).

**Daftar "Langkah pipeline" hanya nama langkah.** `stepChips` → **`stepNames`**
(`lib/demo-agent.ts`): tiap baris menampilkan `step_name` saja (DETECT, VERIFY,
…, LEARN). Slug `tool_called` seperti `evaluate_safety`, `supplier.evaluate`,
atau `supervisor.narration` tidak dicetak lagi — itu istilah internal, dan
pemilik menolaknya 21 Okt ("saya mau menghapus seperti ini `evaluate_safety`").
CSS `.dc-step-tool` ikut dihapus. Konsekuensi: langkah yang sama (mis. dua DETECT)
tampil dua baris tanpa pembeda alat; urutannya tetap urutan server, dan jumlahnya
tetap dinyatakan di lencana lipatan.



## 26. Kartu popup peta: SPPG, pemasok, truk (21 Okt 2026)

**Permintaan pemilik (verbatim).** *"pada maps itu kalo di klik icon nya seperti mobil,
suplier dan sppg kan bakal muncul informasi tuh, tolong di design ui ux yang sebagun
mungkin gunakan skil buat eye catching"*.

**Masalah yang diukur.** Popup lama adalah gelembung putih berisi 2–5 baris teks tanpa
hierarki; warna hanya dipakai untuk pin. Ikon mobil bahkan tidak bisa diklik karena
`.map-truck { pointer-events: none; }` — jadi "klik mobil" tidak pernah membuka apa pun.
Setiap marker juga memasang popup sendiri, sehingga mengklik pemasok kedua meninggalkan
popup pertama terbuka (terukur: dua sampai tiga gelembung sekaligus).

**Satu bahasa desain, empat jenis penanda.** `lib/map-popup.ts` membangun model tampilan
MURNI (tanpa DOM); `SupplyMap.tsx` merendernya menjadi node (bukan `innerHTML`, karena nama
lokasi/pemasok datang dari DB). Semua kartu memakai urutan yang sama:

1. **Kepala** — ikon SVG dalam tile 38 px, kicker kecil (jenis penanda), judul tebal, chip
   status berteks.
2. **Angka utama** — satu hal yang paling ingin diketahui: selisih pasokan (SPPG),
   keandalan (pemasok), progres perjalanan (truk/jalur).
3. **Metrik** — 2–3 angka pendek (pasokan/permintaan, komoditas/sertifikasi/jarak,
   muatan/jarak/ETA).
4. **Meter** — bar pasokan atau progres/keandalan.
5. **Fakta & callout** — jalur, masa layak, kiriman aktif, exclusion, atau peringatan
   mutu. Callout memakai kata, bukan warna saja.

**Warna = jenis + nada, arti tetap ditulis.** `.map-popup[data-kind]` memberi aksen biru
(SPPG/truk/jalur) atau teal (pemasok); `.map-popup[data-tone="danger|safe|warning|neutral"]`
menimpanya untuk shortage/surplus/seimbang dan gagal uji. Chip selalu berisi kata
("Shortage", "Dikecualikan", "Sedang mengirim") sehingga WCAG 1.4.1 tidak bergantung pada
warna. Semua radius memakai token (`--radius-dock`, `--radius`, `--radius-control`,
`--radius-control-sm`, `999px`) dan bayangan memakai `--shadow-3`; tes `radius-scale-css`
dan `token-bayangan` mengunci ini.

**Perilaku peta.**

- **Satu popup pada satu waktu.** `jagaPopup()` menutup popup sebelumnya saat popup baru
  dibuka.
- **Tidak terpotong.** Setelah autoPan MapLibre selesai, popup digeser pada sumbu Y dan X
  (penting di 375 px: penanda di tepi membuat kartu terpotong kiri/kanan). Geseran dibatasi
  tinggi/lebar peta, dan popup yang seluruhnya di luar viewport tidak memicu pan (dulu bisa
  melempar peta ribuan piksel sampai terlihat seperti laut).
- **Bar tab ponsel.** Di ≤480 px diberi inset atas 82 px agar kepala kartu tidak tertutup
  bar tab lengket.
- **Truk bisa diklik.** `pointer-events: auto` + `cursor: pointer` + cincin hover/focus.
  Ada jaring pengaman `requestAnimationFrame` bila klik jatuh pada `<path>` SVG; klik truk
  juga tidak tembus ke layer garis di bawahnya (`trukKlikTerakhir`), supaya yang muncul
  tetap "Kiriman", bukan "Jalur kiriman".
- **Keyboard.** Enter/Space pada marker membuka popup; tombol tutup tetap bisa difokus
  dan berlabel Indonesia "Tutup informasi" (MapLibre menulis "Close popup" dalam bahasa
  Inggris).

**Kepadatan 375 px.** Kartu truk dipadatkan: fakta "Sisa …" yang mengulang meter
disembunyikan, teks meter supplier/truk disembunyikan karena angka besar sudah menyatakannya,
dan padding dirapatkan. Fakta **"Layak dipakai s/d …"** tetap tampil — itu satu-satunya
batas keamanan di popup. Tinggi kartu turun dari 304 px (terpotong 212 px) menjadi 217 px.

**Bukti terukur (aplikasi hidup :3010, sesi demo aktif, akun SPPG Head).**

| Viewport | Kartu | Tinggi | Jarak ke tepi peta (atas/bawah) | Overflow dokumen |
|---|---|---|---|---|
| 1440×1000 | SPPG Jakarta | 224 px | 164 / 12 px | 0 |
| 1440×1000 | Pemasok CV Barokah Telur Cianjur | 267 px | 35 / 98 px | 0 |
| 1440×1000 | Truk CV Hortikultura Subang Lestari → Jakarta | 272 px | 116 / 12 px | 0 |
| 768×900 | Truk | 272 px | 95 / 13 px | 0 |
| 375×812 | SPPG | 193 px | 115 / 12 px | 0 |
| 375×812 | Pemasok | 217 px | 82 / 21 px | 0 |
| 375×812 | Truk | 217 px | 91 / 12 px | 0 |

Klik SPPG lalu pemasok: tepat **1** popup, judul berganti ke pemasok. Tombol tutup
menghapus popup; Enter pada marker truk membuka popup kembali.

**Berkas.**

- `frontend/lib/map-popup.ts` — model tampilan murni (SPPG/pemasok/truk/jalur).
- `frontend/components/SupplyMap.tsx` — `renderPopup`, `jagaPopup`, popup truk, guard klik.
- `frontend/app/map-console.css` — kartu, aksen/tone, meter, callout, responsif 375 px.
- `frontend/app/globals.css` — `.map-truck` dapat diklik + cincin fokus.
- `frontend/tests/map-popup.test.ts` (7), `map-popup-css.test.ts` (3),
  `supply-map-layer.test.tsx` (assertion popup pemasok & truk).

**Gerbang.** `tsc -p tsconfig.json --noEmit` 0 error; vitest **160 berkas / 1.746 tes
lulus**; `next lint` **0 peringatan/error** (dua peringatan lama `react-hooks/exhaustive-deps`
di `SupplyMap.tsx` ikut dibereskan: `geserTruk` masuk dependency dan ref truk disalin untuk
cleanup). Artefak: `_qa/map-popup/final-sppg-1440.png`,
`final-supplier-1440.png`, `final-truck-1440.png`, `final-sppg-375.png`,
`final-supplier-375.png`, `final-truck-375.png`, `final-truck-768-page.png`.

**Sekalian diperbaiki.** `ROUTE_LINE_COLORS.ok` sempat bernilai `#8B5CF6` (violet terang),
padahal token `--route-live-strong` = `#7C3AED`; tes `supplier-routes` dan
`supply-map-layer` menuntut pasangan yang sama. Nilai dikembalikan ke `#7C3AED`; sisa
perjalanan tetap `#8B5CF6` (`ROUTE_TODO_COLORS`).

## 27. Verifier menjadi agent ke-8 (23 Okt 2026)

**Permintaan pemilik.** *"tolong Verifier anda jadikan agent jadi anda sesuaikan semuanya
supaya Verifier bisa jadi agent"*. Sebelumnya verifier hanya dua lapis di luar daftar agent:
`agent/verify.py` (deterministik, menempel di payload run) dan `verifier_client.py` (REST
model, dipanggil sebelum approval).

**Keputusan.** Verifier dijadikan agent terdaftar bernama `verifier`, tetapi dengan tiga pagar
supaya independensinya tidak hilang:

1. **Urutan.** Ia berjalan SESUDAH supervisor menarasikan (`run_review` → tujuh worker →
   supervisor → `verify_run` → `VerifierWorker.audit`). Narasi tidak bisa meringkas auditornya.
2. **Wadah terpisah.** Temuannya disimpan di `AgentRun.verifier_finding`, bukan di `findings`.
   Status run, narasi, dan veto tetap dihitung dari tujuh worker analitik — auditor tidak boleh
   mengubah hasil yang diauditnya.
3. **Tidak boleh melonggarkan.** Masukannya hasil gerbang deterministik. Verdict `flag` tidak
   bisa berubah menjadi `pass` walau model yang disuntikkan mengaku CONSISTENT; model hanya
   boleh menambah alasan. Model mati/rusak diabaikan (audit tetap terbit dari jalur
   deterministik). `blocking` selalu `false` — memblokir tetap milik guardian.

**Bentuk teknis.** `AgentName.VERIFIER` + `ANALYST_AGENTS` (tujuh analitik) di
`agent/contracts.py`; entri `verifier` di `agent/hierarchy.json` (stage VERIFY,
`blocking_allowed=false`); `agent/workers/verifier.py`; baris trace `agent.verifier` sebelum
`SUPERVISE` (`agent/telemetry.py`); review kini **9 baris** (7 worker + verifier + SUPERVISE).

**Sesuai di lapisan lain.** `persist_agent_review` menerima 9 baris (8 diterima sebagai
runtime lama yang belum diperbarui); kartu Agent Log menjadi 8 (`SWARM_AGENTS`), hitungan
`n/8 tercatat` dinamis; teks "Review 7 agen" → "Review 8 agen"; prompt supervisor menyebut
verifier berjalan sesudah narasi dan tidak dijalankan oleh supervisor.

**Gerbang.** Tes agent 91 + 6 tes auditor baru lulus; `test_demo_event1_api`,
`test_trace_persistence` lulus; panel agent vitest 14 tes lulus; `tsc --noEmit` 0 error.

## 28. Watchdog tunnel: satu pemilik, tiga sinkronisasi (23 Okt 2026)

**Masalah.** Quick Tunnel Cloudflare memberi URL acak setiap cloudflared restart. URL yang
sama dipakai tiga tempat: environment runtime AgentCore (worker agent), `.env`, dan aplikasi
Joule di Cloud Foundry. Bila hanya satu yang diperbarui, sistem tampak hidup tetapi buta —
chat menjawab sementara tujuh worker gagal, atau sebaliknya.

**Perbaikan.** `agent/tunnel_watchdog.py` sekarang:
1. memiliki cloudflared sebagai anak proses dan membaca URL dari keluarannya;
2. menyinkronkan runtime AgentCore lewat `agent/set_runtime_env.py` (menunggu READY);
3. menyinkronkan aplikasi CF (`cf set-env <app> MEALCHAIN_API_URL <url>` + `cf restage`);
   bentuk `KEY=VALUE` ditolak cf — argumen harus tiga posisi terpisah;
4. memanaskan runtime dengan satu review nyata, bukan `/health`;
5. menolak instance kedua (`agent/.tunnel_watchdog.pid` + cek PID hidup), karena dua
   instance berarti dua tunnel yang saling menimpa.

**Autostart.** `schtasks /Create` ditolak tanpa hak admin, jadi dipakai jalur pengguna:
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\mealchain-watchdog.cmd` →
`scripts/nyalakan-watchdog.cmd` (memakai `C:\Python314\python.exe`, log ke
`.tunnel-watchdog.log`).

**Jalankan manual.** `scripts\nyalakan-watchdog.cmd` (idempoten: instance ganda menolak
sendiri). Cek status: `type agent\.tunnel_state.json` dan `tasklist /FI "IMAGENAME eq cloudflared.exe"`.

## 29. Audit animasi pengiriman di peta (24 Okt 2026)

**Pertanyaan pemilik.** Kalau ada pengiriman menuju SPPG, apakah animasi di peta muncul?

**Temuan audit.**
1. Ikon mobil memang hanya dibuat untuk baris `journey.state === "di_jalan"` yang
   punya geometri jalan; kiriman yang sudah tiba atau belum berangkat tidak
   digambar. Ini benar dan sudah diuji.
2. Data tidak pernah disegarkan: `useSupplierRoutes` memakai
   `refetchInterval: false` + `staleTime` 5 menit. Akibatnya posisi mobil beku di
   angka saat halaman dibuka, dan kiriman yang tiba tetap tampak "di jalan"
   sampai tab ditinggalkan.
3. Perpindahan antar-denyut tidak ada. Satu-satunya gerak adalah ease 700 ms saat
   angka berubah — dan angka itu hanya berubah tiap 60 detik (denyut global).
4. Pada zoom nasional, jalur 300 km digambar selebar ~300 px, jadi kecepatan
   sesungguhnya hanya ~1 px per menit. Walau data hidup, puck terbaca diam.

**Perbaikan.**
- `lib/query.ts`: `MAP_TRUCK_POLL_MS = 15_000`, dipakai HANYA oleh query peta
  (`app/page.tsx`); halaman Pemasok dan Keamanan Pangan tetap tanpa polling.
- `lib/hooks/useSupplierRoutes.ts`: parameter `pollMs`; saat hidup, `staleTime` 0
  dan `refetchInterval` mengikuti `pollMs`, `refetchIntervalInBackground: false`.
- `lib/truck-progress.ts`: `fraksiBerjalan(journey, jangkar, now)` — `progress`
  server menjadi jangkar, lalu dimajukan waktu berjalan dibagi `travelMin`.
  Jangkar diganti hanya saat angka server berubah, jadi gerak lokal tidak mundur.
- `SupplyMap.tsx`: detak 1 detik memanggil `syncTruk` selama ada kiriman
  `di_jalan`; `data-frac` pada elemen truk untuk bukti audit; jangkar dibuang saat
  kiriman tiba.
- `app/globals.css`: halo puck berdenyut (`truk-denyut`, 2,4 s) supaya "ada
  kiriman bergerak" terbaca di zoom nasional tanpa memalsukan posisi; dimatikan
  pada `prefers-reduced-motion`.

**Bukti.** Di layar (BGN Monitor, komoditas telur): 2 mobil; `data-frac`
0,19117 → 0,19222 dan 0,45240 → 0,45453 dalam 16 detik; satu kiriman yang tiba
hilang dari peta tanpa menyisakan ikon. Tes: `tests/truck-progress.test.ts` (7),
`tests/map-truck-poll.test.ts` (4), `tests/supply-map-layer.test.tsx` (64);
frontend penuh 1775 tes / 163 berkas lulus, `tsc --noEmit` bersih.

**Catatan jujur.** Di zoom nasional gerak puck tetap ~1 px/menit — itu kecepatan
sebenarnya, bukan bug; yang membuatnya terbaca hidup adalah denyut halo dan jejak
ekor. Di zoom kota (mis. Bandung) perpindahannya terlihat jelas.

**Sisa.** Label `aria-label` persentase masih diperbarui saat data datang (≤15
detik), bukan tiap detik; angka itu tidak dipakai untuk posisi.

## 30. Periode feed rekomendasi: hari ini / 7 hari / 1 bulan (24 Okt 2026)

**Permintaan pemilik.** Di tab Recommendations harus ada menu untuk memilih
rekomendasi hari ini, 7 hari, atau 1 bulan — dan tampilannya harus menarik
tetapi tetap satu bahasa desain dengan halaman lain.

**Kontrak data (bukan hitungan peramban).**
- `GET /decisions?window=24h|7d|30d` menyaring menurut `created_at`.
  `24h`/`7d` = jendela bergulir; `30d` = **bulan berjalan menurut WIB**
  (aturan yang sama dengan pemilih periode KPI). Tanpa parameter = seluruh
  riwayat (perilaku lama). Kunci asing → 422.
- `total` dan `count` ikut jendela, jadi "10 dari 27" tidak pernah bertentangan
  dengan banyaknya baris yang bisa dicapai.
- Aturan jendela hidup di `backend/app/core/window.py`; diuji tanpa database
  (`tests/test_decisions_window.py`, 8 tes).

**Pemisahan query.** Feed memakai query sendiri (`useDecisions(..., feedWindow)`)
dan hanya aktif saat tab Recommendations dibuka. Lonceng notifikasi, badge
sidebar, dan kartu KPI tetap memakai seluruh riwayat — mempersempit feed tidak
boleh mengubah arti "21 menunggu tindakan".

**Kontrol UI.** Memakai komponen yang SUDAH ADA: `.kpi-period` +
`.commodity-pill` + `aria-pressed`, dengan tombol asli (bukan `div`), urutan
`Hari ini → 7 hari → 1 bulan`, baris bantuan ("24 jam terakhir", "bulan berjalan
(WIB)"), dan chip yang membungkus (`flex-wrap: wrap`). Mengganti periode
mengembalikan halaman ke 1.

**Penyesuaian visual (agar mencolok tanpa bahasa baru).**
- Keadaan aktif sekarang **terisi** `--primary` dengan teks `--surface`
  (kontras 5,2:1), bukan sekadar garis + tebal — garis tipis tenggelam di antara
  chip status. Berlaku untuk KPI dan feed karena satu selektor.
- Tinggi pil 22 px → 28 px (padding `5px 12px`); 44 px tetap berlaku di
  perangkat sentuh lewat aturan `(pointer: coarse)` yang sudah ada.
- Tanpa hex mentah: warna memakai token (`--primary`, `--ink`, `--surface`),
  dijaga `design-tokens-kontrak.test.ts` dan `token-alias-css.test.ts`.

**Keadaan kosong.** Jika jendela terpilih kosong, layar menyebut periodenya dan
menawarkan tombol "Lihat 1 bulan terakhir" — bukan pesan "tidak ada data" yang
ambigu dengan "tidak cocok dengan filter".

**Bukti.** Di layar (BGN Monitor): "Hari ini" → 27 rekomendasi, 5 perlu tindakan,
"Menampilkan 10 dari 27"; klik "7 hari" → 90 rekomendasi, 21 perlu tindakan,
"10 dari 90", `aria-pressed` berpindah, permintaan jaringan `?window=24h` lalu
`?window=7d`, halaman kembali ke 1. Tes: frontend 1785 lulus / 165 berkas
(`tests/decisions-window.test.ts`, `tests/feed-window-wiring.test.ts`,
`tests/query.test.ts` diperbarui), `tsc --noEmit` bersih; backend
`test_decisions_window.py` 8 lulus.

## 31. "Siapa yang mengirim?" — baris pengirim + label yang jujur (24 Okt 2026)

**Keluhan pemilik.** Di tab Recommendations hanya tampak nama WILAYAH, jadi tidak
jelas apakah barang datang dari pemasok atau dari SPPG lain; judul "Alokasi
regional" dan kata "Alihkan" menambah kebingungan.

**Akar masalah.** `GET /decisions` tidak pernah mengirim identitas pengirim:
yang ada hanya `supplier_id` (kadang kosong) dan `target_location_id` (UUID).
Kartu lalu hanya bisa menyebut wilayah dari data lain.

**Perubahan data (tanpa tebakan).** `/decisions` kini mengirim:
- `supplier_name` — dari `decisions.supplier_id`; bila kosong dipakai
  `supplier_id` di payload `decision_evidence` (satu-satunya jejak tersimpan).
- `pengirim` — `"pemasok"` bila pemasok teridentifikasi, `"antar_sppg"` untuk
  `regional_balance`/`surplus_redistribution` tanpa pemasok, selain itu `null`.
- `target_location_name` — nama lokasi tujuan, bukan UUID.

**Kartu.** `routeLineOf()` merender satu baris berikon truk:
- "Dikirim pemasok UD Cibinong Telur Berkah ke Bandung"
- "Bukan dari pemasok — stok dipindahkan antar-SPPG ke Jakarta"
Bila tidak ada fakta yang cukup, baris TIDAK dirender (tidak ada kalimat karangan).

**Kosakata yang diperbaiki.**
- `regional_balance`: "Alokasi regional direkomendasikan" → **"Penyeimbangan
  pasokan regional"**; kata kerja kepala halaman "Alihkan" → **"Seimbangkan"**.
  Jenis ini menutup kekurangan satu SPPG — bisa dengan pasokan pemasok, bisa
  dengan surplus SPPG lain; karena itu labelnya tidak mengklaim sumber.
- `safety_disruption`: "Pengalihan pasokan (gangguan keamanan)" → **"Ganti sumber
  pasokan (gangguan keamanan)"** — yang terjadi memang mengganti sumber.

**Bukti.** Di layar (BGN Monitor, 27 rekomendasi hari ini): 8 dari 10 kartu
halaman pertama menampilkan baris pengirim dengan nama pemasok nyata
(UD Cibinong Telur Berkah, Koperasi Telur Cipanas Bersama); dua kartu
`price_anomaly` tidak menampilkan baris karena sumbernya memang tidak tercatat.
Tes: frontend 1789 lulus / 166 berkas (`tests/recommendation-route.test.ts`),
backend `tests/test_decisions_pengirim.py` 4 lulus; `tsc --noEmit` bersih.

## 32. Satu hari operasional Jakarta: menunggu, berjalan, selesai (24 Okt 2026)

**Yang diminta pemilik.** Dalam jendela 1 hari harus terlihat tiga fase sekaligus
— ada yang menunggu persetujuan, ada yang sedang dikirim, ada yang sudah selesai
— dan kartu paling atas adalah **persetujuan pengiriman dari pemasok** supaya
bisa didemokan langsung. Angka KPI harus lahir dari kejadian itu, bukan ditempel.

**Keadaan sebelum perubahan.** Jakarta 24 jam hanya punya 1 rekomendasi; KPI 3/7
(4 metrik `no_data`); dan tidak ada satu pun penulis `batches.dispatched_at`,
jadi menekan Setujui → Eksekusi berakhir di status tanpa truk apa pun di peta.

**Seed baru: `backend/app/seed/hari_ini.py`.** Idempoten (id deterministik,
`_bersihkan()` menghapus miliknya sendiri), Jakarta-sentris, memakai penulis
produksi: `settlement.catat_penerimaan / catat_po_terbit / catat_pembuangan`,
`Approval`, `DecisionEvidence`, `SapMockPurchaseOrder`, `AgentTrace`.

```
Keputusan (9)                        Status
Pengadaan dari pemasok 780 kg        pending_approval   ← kartu teratas, expires 18 mnt
Penyeimbangan pasokan regional       pending_approval
Pengadaan dari pemasok (beras)       pending_approval   ← expires_at sudah lewat
Penyesuaian harga                    rejected           + rejection_reason
Ganti sumber pasokan                 verifier_flagged
Penyeimbangan pasokan regional       approved           (belum berangkat)
Pengadaan telur 780 kg               executed           truk berjalan
Redistribusi wortel 400 kg           executed           truk berjalan
Pengadaan beras 480 kg               executed           selesai + penerimaan disetujui
```

**Waktu berangkat diturunkan dari DURASI RUTE.** Versi pertama memakai offset
tetap (4 jam / 2 jam). Rute Bekasi→Jakarta hanya ±40 menit, jadi truk langsung
terbaca `sudah_tiba` dan tak pernah muncul sebagai perjalanan aktif. Setelah
`sync_road_routes` mengisi geometri, `dispatched_at = now − 45% durasi` dan
`usable_until = now + 55% durasi` — truk selalu lahir di tengah jalan.

**Eksekusi = barang berangkat.** `_dispatch_bound_batches()` di
`app/api/actions.py` mengisi `dispatched_at` untuk batch di
`decision_evidence.payload.batch_ids` (jalur yang sama dengan revalidasi safety),
hanya untuk batch yang belum berangkat, dan tidak menyentuh jenis administratif
(`supplier_exclusion*`, `price_anomaly`). Respons `/actions/execute` memuat
`dikirim: [{batch_id, dispatched_at}]`.

**Syarat yang ditemukan saat menguji alur setujui → eksekusi** (semua harus
dipenuhi seed, kalau tidak tombolnya 409):
1. `verified_by` + `verifier_note="consistent"` — tanpa verdict, "belum terverifikasi".
2. Binding butuh batch dengan **supplier, lokasi, dan komoditas yang sama**
   dengan keputusan; memakai batch komoditas lain → "binding batch/supplier berubah".
3. Pemasok tidak boleh berstatus eksklusi aktif di SPPG penerima → seed memilih
   pemasok dengan `SupplierExclusion.status == 'active'` disaring keluar.
4. Satu batch hanya boleh punya **satu** penerimaan disetujui
   (`uq_batch_receipts_satu_disetujui`) → kiriman selesai memakai batch sendiri.

**Endpoint.** `POST /demo/hari-ini` (peran `sppg_head`/`sppg_nutritionist`,
butuh sesi aktif) — memuat ulang satu hari untuk kota pemanggil.

**Metrik yang bergerak** (Jakarta, 24 jam, sesudah seed):

```
Meal Continuity 100,00%   Avoidable Food Loss 0,53%   Regional Imbalance 42,86%
Safe Delivered Cost 11.073.548   Price Deviation 4,23%   Decision Time 22 mnt
Evidence Completeness 100,00%    → 7/7 tersedia (sebelumnya 3/7)
```

**Bukti.** `/supplier-routes` (SPPG Head): `di_jalan 3`, `with_road 19/19`;
dua batch seed berjalan dengan progress 0,457 dan 0,458. Di layar, tab wortel
menampilkan "CV Cipinang Boga Utama → JKT · Di jalan · 6 menit lagi · 400 kg";
posisi bergerak terukur (`data-frac 0,50500 → 0,52420` dalam 16 detik). Tes:
`backend/tests/test_hari_ini.py` 8 lulus; 42 tes backend terkait (actions,
approval, decisions) lulus; frontend 1790 tes / 166 berkas lulus.

### 32b. “Siapkan data demo” = satu hari utuh, bukan sisa potongan (24 Okt 2026)

Terukur sebelum diperbaiki: setujui kartu teratas (2 akun) → tekan
“Siapkan data demo” → `status=None`, `approvals=0`, feed 24 jam **1** kartu,
KPI kosong. Penyebabnya `_seed_demo_cases(force=True)` menghapus kasus skrip
(lalu membuatnya ulang) dan `geser_aksi_ke_riwayat` menggeser baris aksi keluar
jendela 24 jam.

Perbaikan: `POST /demo/refresh` kini memanggil `susun()` (seed hari-ini) di
akhir rangkaian. Hasil ukur sesudahnya, satu klik dari keadaan apa pun:

```
refresh 200 · hari_ini.keputusan = 9
feed 24 jam = 10 kartu  {pending_approval 4, executed 3, approved 1,
                         verifier_flagged 1, rejected 1}
KPI 24 jam = 7/7 tersedia
```

Konsekuensi yang tetap berlaku dan disengaja: persetujuan yang sudah diberikan
hilang saat tombol ditekan — reset demo memang harus deterministik. Urutan demo:
“Siapkan data demo” → setujui → eksekusi → peta.

## 33. Judul pengadaan dua baris (24 Okt 2026)

Permintaan pemilik: ringkasan keputusan jangan satu baris panjang. Bentuk final:

```
Pengadaan 780 kg telur
UD Sumber Rejeki Telur → Jakarta
```

Aturannya di `frontend/lib/evidence.ts::decisionHeadline`: khusus
`supplier_procurement`, baris pertama memuat **apa** (kata kerja + kuantitas +
komoditas), baris kedua memuat **dari siapa ke mana** (pemasok → SPPG). Titik
dua dibuang, kata "pemasok" tidak diulang karena baris kedua sudah nama pemasok.
`.evidence-hero-title` diberi `white-space: pre-line` supaya `\n` benar-benar
jadi baris baru. Jenis keputusan lain tetap satu baris (`Seimbangkan 250 kg
wortel: SPPG … → Jakarta`).

Bukti DOM: `textContent` = `"Pengadaan 780 kg telur\nUD Sumber Rejeki Telur →
Jakarta"`, `white-space: pre-line`, tinggi kotak judul 58 px (dua baris).

## 34. Data demo harus masuk akal, bukan sekadar terisi (24 Okt 2026)

Tiga baris nyata yang muncul di layar dan salah secara operasional:

```
Ganti pasokan 300 kg ayam: Surabaya → Jakarta      (663 km, lintas pulau, ayam segar)
Pengadaan beras dari CV Barokah Telur Cianjur      (pemasok telur memasok beras)
Penyeimbangan pasokan regional … pemasok UD …      (tipe antar-SPPG tapi pengirim pemasok)
```

Perbaikan di sumber datanya, bukan di tampilan:

1. **Sumber = pemasok/kota yang benar.** Keputusan yang barangnya dibeli dari
   pemasok memakai kota PEMASOK (`source_location_id` = kota pemasok, bukan
   Surabaya/Bandung yang tidak berhubungan). Pemindahan antar-SPPG memakai
   tetangga terdekat (Jakarta ← Bandung 116 km).
2. **Jarak dijaga.** `_sumber()` di `api/demo.py` kini memilih kota lain
   TERDEKAT di pulau yang sama, maksimum 400 km; kalau kota itu tidak punya
   tetangga dalam batas (Medan, Palembang, Makassar), kasus memakai stok lokal
   kota itu sendiri. `"Surabaya"` tidak lagi jadi kandidat cadangan.
3. **Pemasok harus menjual komoditasnya.** `seed_demo_activity` memilih pemasok
   per komoditas (bukan rotasi buta), `hari_ini._pemasok()` menyaring kandidat
   kanonik ke pemasok berkomoditas sama, dan modul baru
   `app/seed/rapikan.py::rapikan_pemasok_batch()` merapikan batch warisan yang
   terlanjur salah — dipanggil dari `susun()` dan `load_seed()`.
4. **Tipe keputusan jujur.** `rejection-loop-kuota` kini `supplier_procurement`
   (siklus penolakan pada pengadaan), bukan `regional_balance` yang membuat
   kartu berlabel "Penyeimbangan pasokan regional" padahal pengirimnya pemasok.
5. **Judul dua baris hanya untuk barang dari pemasok**; `price_anomaly`,
   `supplier_exclusion`, `supplier_reinstatement` tidak menampilkan rute sama
   sekali karena tidak ada barang yang bergerak.

Kunci regresi: `backend/tests/test_hari_ini.py::test_data_masuk_akal_jarak_dan_jenis_pemasok`
(gagal bila ada rute >400 km atau batch yang pemasoknya beda komoditas).

Keadaan sesudah perbaikan (24 jam, Jakarta):

```
10 kartu · pengadaan→UD Sumber Rejeki Telur / CV Cipinang Boga Utama
         · ganti pasokan→PT Nusantara Prima Ayam / UD Cibinong Telur Berkah
         · penyeimbangan→antar-SPPG Bandung/Cianjur (≤116 km)
         · penyesuaian harga→tanpa rute
jarak maksimum seluruh keputusan: 260 km (Semarang → Surabaya)
```

### 34b. “Segarkan ke hari ini” tidak lagi menggandakan snapshot kanonik

Empat tes invarian (`price_regional_seed`, `sprint1_contract_reconciliation`,
`road_route_sync`, `freshness band`) selalu merah **setelah** tombol demo
ditekan. Penyebabnya tombolnya, bukan tesnya:

```
load_seed(now)  → id baris kanonik diturunkan dari TANGGAL ACUAN
                → tanggal baru = id baru, baris acuan lama TETAP ADA
                → 100 price_signals yatim + 40 pihps_reference ganda
```

Dua jalan keluar dicoba. Menghapus baris kanonik lama setelah memuat snapshot
baru **ditolak**: batch yang masih dipakai tes lain (`test_suppliers_api`,
`test_seed_load_db`) ikut terhapus, dan memuat ulang snapshot lama gagal karena
baris demo sudah menempati kunci unik `(lokasi, komoditas, recorded_at)`.

Kontrak final: `POST /demo/refresh` memuat snapshot kanonik **hanya bila belum
ada** (`count(batches WHERE origin <> 'demo') == 0`). Kanonik tetap pada tanggal
acuannya; yang bergerak ke hari ini hanya baris demo — kiriman, empat kasus
skrip, keputusan selesai, harga harian, dan seed hari-ini.

Tambahan yang menjaga kebersihan setelah refresh:

* `rapikan_batch_ganda()` menghapus kiriman kembar (pemasok + lokasi +
  komoditas + waktu panen sama, id berbeda) — 4 baris pada keadaan sekarang;
* `rapikan_pemasok_batch()` memindahkan batch yang pemasoknya salah komoditas;
* respons menyebut angkanya (`rows.dilewati`, `batch_kembar_dihapus`,
  `hari_ini.keputusan`) supaya operator tahu apa yang terjadi.

Kontrak tesnya ikut diperbarui: `test_refresh_hari_ini_tidak_menggandakan_snapshot_kanonik`
membandingkan **id baris kanonik** sebelum/sesudah (harus sama) dan memastikan
baris demo bertambah tanpa batch kembar. Bukti: 72 tes terkait hijau —
`test_demo_timeseries_api`, `price_regional_seed`, `road_route_sync`,
`seed_load_db`, `suppliers_api`, `seed_menu_plan_anak`, `sprint1_acceptance`.


## 35. Audit menyeluruh 24 Okt 2026 — jejak dan persetujuan yang jujur

Audit memakai `fullstack-verification` (gate berlapis) + `dogfood` (penjelajahan
layar). Laporan penuh: `docs/verification/audit-2026-10-24.md`.

Hasil: process 12/12, be 10/10, db 8/8, compare 4/4, tab × peran 3/3
(10 tab Jakarta, 9 tab monitor, 10 tab Bandung), invariants 47/47.

Dua cacat data yang ditemukan dan DIPERBAIKI:

1. **Jejak ACT pada keputusan yang tidak dieksekusi (8 baris).** `hari_ini`
   menulis ACT untuk semua keputusan tanpa `demo_case`; `jakarta_lengkap`
   menulisnya untuk `executed` DAN `approved`. Keduanya kini hanya menulis ACT
   saat `status == "executed"`.
2. **Eksklusi pemasok `executed` tanpa baris approval (3 baris).**
   `seed_exclusions()` menulis status `executed` dan `SupplierExclusion.approved_at`
   tetapi tidak pernah menulis `approvals`/`agent_traces`. Kini menulis satu
   approval (Kepala SPPG Jakarta, +2 jam) dan tiga jejak DETECT/VERIFY/ACT.

Kunci regresinya: `backend/tests/test_invarian_riwayat_demo.py` (dua tes) —
aturan yang sama dengan `verify/invariants.spec.json`, tanpa perlu menjalankan
gate.

Spek `stack`/`invariants` sebelumnya memaku revisi Alembic `026` sehingga gate
tidak akan pernah hijau; kini `030_approval_four_eyes_unique`. Utang kecil yang
dicatat: nilai itu akan usang lagi tiap ada migrasi (rencana batch D).

### 35b. Batch A+B: bukti kasus skrip & draf usulan (24 Okt 2026)

**Batch A — bukti untuk kartu yang ditolak/di-flag.** `demo.py` mendapat
`_bukti()` (id deterministik, idempoten). Skrip 4 kasus kini membuktikan juga
versi yang berakhir `rejected`/`verifier_flagged`: v1 kuota (human_inspection,
`quota_full`), v2 kuota (market_price, rasio 1,12 + alasan penolakan),
gangguan-logistik v1 (gps, `disruption: banjir`), supplier-janggal
(market_price, rasio 0,60, `is_consistent=False`). `hari_ini.susun()` menulis
bukti untuk KESEMBILAN kartunya (sebelumnya lima), termasuk yang lewat tenggat,
ditolak, dan di-flag. Terukur: kasus skrip tanpa bukti **22 → 0**, keputusan
24 jam tanpa bukti **28 → 1**.

**Batch B — draf usulan & angka tenggat.** `_buang_draf_usang()` di
`POST /demo/refresh` membuang `proposed` tanpa `demo_case`, tanpa approval, tanpa
PO, dan tanpa bukti, lebih tua dari satu jam (respons: `draf.draf_usang_dihapus`).
Terukur: **17 + 15** draf terhapus, total `proposed` **58 → 29**.
Sisi tampilan: `countActionableBreakdown()` dan `notifList()` memisahkan `draft`
dari `expired`, jadi lonceng berbunyi **"19 menunggu tindakan · 4 lewat tenggat"**
(bukan lagi "· 31"), dan tooltip tab menambah klausa
**"27 draf usulan kedaluwarsa"**.

Tes penjaga: `backend/tests/test_bukti_dan_draf_demo.py` (2),
`frontend/tests/topbar-lib.test.ts` (+2). Frontend: 1792 tes / 166 berkas;
tsc bersih.

Sisa temuan yang BELUM dikerjakan (rencana terperinci ada di laporan):
bukti untuk varian kasus skrip yang ditolak/di-flag (28 baris 24 jam),
tumpukan 58 keputusan `proposed` yang membuat lonceng berbunyi
"47 lewat tenggat", dua rute cache lintas pulau (Medan→Jakarta/Surabaya) yang
tidak terpakai, dan `GET /kpi` yang membalas 422 tanpa parameter.

## 36. Veto guardian menjadi STATUS, bukan hanya flag (27 Okt 2026)

**Gejala.** Kartu bukti Demo Control menampilkan `Verifikasi: Terbatas`,
`Durasi: 0 md`, `Peringatan: 1`. Jejak `agent_traces` terakhir untuk
`agent_name='verifier'`:

```json
{"facts":{"reasons":["safety_veto_aktif: ada temuan blocking, tetapi status run dilaporkan completed"],
          "verdict":"flag","status_run":"completed","safety_veto":true},"status":"degraded"}
```

**Akar masalah (dua defek, bukan satu).**

1. **P1 — supervisor menghitung status tanpa veto.** `run.status`
   (`agent/validation.py:run_status`) hanya melihat kelengkapan worker, error,
   degraded/skipped, dan kontradiksi. `safety_veto` dihitung terpisah di
   `agent/orchestrator.py`. Akibatnya putaran dengan guardian `blocking=True`
   — status worker `ok`, jadi tidak ada degraded — ditulis `completed`.
   Verifier benar menandaknya (`agent/verify.py` cek "veto tapi completed"),
   dan tanda itu yang membuat kartu jatuh ke "Terbatas". Temuan ini sudah
   tercatat sebagai **C-09** di `INDEPENDENT_PROJECT_REVIEW.md`; perbaikannya
   di PENGHITUNG status, bukan dengan melemahkan verifier.
2. **P3 — durasi 0 ms.** `StubWorker._latency_ms` memakai `int()`, sehingga
   jalur cepat (model verifier tidak dikonfigurasi, fakta gagal terbaca) yang
   selesai di bawah satu milidetik terpotong menjadi **0**. UI menulis
   "0 md", yang terbaca sebagai "tidak ada pekerjaan berjalan".

**Keputusan.**

- `RunStatus.VETOED = "vetoed"` di `agent/contracts.py`; `run_status()`
  mengembalikan `VETOED` bila `safety_veto(findings)` benar — sebelum cabang
  `partial`/`completed`, sesudah `failed`. Veto adalah fakta yang paling
  menentukan boleh-tidaknya eksekusi, jadi error worker lain tidak
  menghapusnya.
- `verify.py` tidak dilonggarkan: ceknya berubah menjadi "veto aktif tetapi
  status BUKAN `vetoed`", sehingga penulis status lain (runtime lama/agen
  lain) tetap ditandai.
- `_latency_ms` = `max(1, round(...))`: hasil pengukuran tidak pernah 0;
  "tidak diukur" tetap `None`. Semua worker memakai jalur yang sama.
- Rantai konsumen ikut diperbarui supaya `vetoed` tidak jatuh ke `failed`:
  `agent_review_client.ALLOWED_STATUS` + `.completed` (9 baris trace tetap
  disimpan — itu bukti veto, bukan kegagalan runtime), label UI
  `agent-swarm.STATUS_LABELS` (`vetoed: "Diblokir"`), `demo-agent.agentReviewLine`
  ("selesai dengan veto guardian"), dan `OpsConsole.labelReview7Agen`.
- Heuristik `narasi_tidak_menyebut_penurunan` mengenal kata
  `memblokir/diblokir/veto`. Narasi veto justru paling keras — menuduhnya
  menghaluskan penurunan adalah salah tuduh yang muncul di setiap putaran
  ber-veto dengan worker degraded (terukur pada putaran nyata 27 Okt).

**Terukur (satu putaran agent nyata, `run_review` lewat `agent/api_client`
terhadap stack demo, decision `d517f61a…`).**

| Nilai | Sebelum | Sesudah |
|---|---|---|
| `run.status` / baris SUPERVISE | `completed` | `vetoed` |
| `duration_ms` baris VERIFY | `0` (jejak 03:54) | `29` ms |
| alasan verifier "status run dilaporkan completed" | ada | tidak ada |
| `run.verification` | `flag` (1 alasan) | `pass` (0 alasan) |
| baris tersimpan `persist_agent_review` | 9 | 9 (status `vetoed` diterima) |

**Tes.** `backend/tests/test_agent_run_status_veto.py` (8 tes: status veto,
trace SUPERVISE, verifier tanpa tuduhan palsu, guard tetap ada, latency ≥ 1 ms,
baris VERIFY > 0, narasi veto tidak ditandai, klien review menerima `vetoed`)
+ 2 tes frontend (label `Diblokir`, kalimat review). Gerbang: backend suite
**1666 lulus / 0 gagal / 28 dilewati**; `ruff check .` (backend) bersih;
`tsc --noEmit` 0; vitest **1823 lulus**; `invariants.spec.json`
**PASS 60 / FAIL 0 / SKIP 1**.

**Sisa risiko.** Runtime AgentCore yang sedang melayani demo memakai image
lama — sampai dideploy ulang, jejak yang ditulis runtime itu masih
`completed` + `duration_ms 0` (perbaikan ini ada di repo, bukan di deployment).
Kartu verifier juga masih bisa menampilkan "Terbatas" dengan alasan jujur bila
model verifier tidak dikonfigurasi di runtime (`audit_verdict: unavailable`).
