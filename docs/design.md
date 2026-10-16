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
| — | *(acuan app)* **Surplus & Limbah** | Tab **Surplus & Limbah** (Langkah 5) — halaman `/surplus` di acuan: neraca surplus/kekurangan komoditas aktif, rencana alokasi surplus→kekurangan (greedy, jarak dari koordinat), keadaan pencatatan limbah ✓ (hanya peran SPPG, seperti acuan) | Tambahan demo |
| — | *(acuan app)* **Pemasok** | Tab **Pemasok** (Langkah 5) — halaman `/suppliers` di acuan: daftar pemasok + keandalan dari keputusan terakhir, register eksklusi, form usul eksklusi ✓ | Tambahan demo |
| 5 | Agent Activity Log (`/agent-log`) | Tab **Agent Log** — trace console + provider panel, pilih decision via dropdown ✓ | Wajib |
| 6 | Approval Modal/Flow | Di dalam Decision Detail ✓ | Wajib |
| 7 | KPI Dashboard (`/kpi`) + *(acuan app)* Kualitas Agen (`/quality`) | Tab **KPI & Kualitas Agen** — **digabung 2026-10-15 atas keputusan pemilik** (dua tab lama "KPI" + "Kualitas Agen" jadi satu, urutan KPI dulu lalu mutu agen). Bagian 1: 7 KPI live jujur dari `/kpi` (strip **Target KPI Demo Day** dihapus hari yang sama). Bagian 2: skor agregat mutu agen (langkah/run, kesesuaian verifikator, tingkat fallback, keputusan diubah manusia, rata-rata durasi) + rincian per run dari jejak agen nyata ✓. Komposisi ada di `components/KpiQualityBoard.tsx`; isi kedua bagian tidak diubah | Wajib |
| 8 | Demo Control Panel (`/demo-control`) | Tab **Demo Control** (approver-only) — skenario via API resmi: seed kasus + konsol analisis Event 1/2/3 ✓ | Wajib (demo) |
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
- **Penanda "sedang mengirim" (keputusan pemilik 2026-10-16):** pemasok yang punya batch kiriman
  **masih layak** (`usable_until >= sekarang`, dihitung backend dan dikirim sebagai kunci
  `shipping` pada `GET /suppliers`) mendapat **cincin** di sekeliling titiknya
  (`map-pin-supplier-shipping`, cincin `--status-safe`) — **bukan nada kelima**: warna pin tetap
  berarti keandalan/jangkauan, cincin berarti kiriman berjalan, jadi dua fakta berbeda bisa
  terbaca bersamaan dan tidak saling menutup. Label (`aria-label`) dan popup menambah
  "sedang mengirim N kiriman"; kiriman yang gagal uji disebut terpisah (`safety_fail_count`),
  tidak disembunyikan di balik kata "sedang mengirim".
- **Garis jalur kiriman (`ship-route`).** Garis putus-putus di peta menandai rute kiriman
  pemasok → tujuan **mengikuti jalan** (geometri OSRM, disimpan di tabel `road_routes`), bukan
  garis lurus. Warna garis memakai token yang sama dengan nada mutu kiriman
  (`--status-safe` / `--status-danger`) supaya satu fakta tidak punya dua bahasa; nilai paint
  WebGL tidak bisa membaca CSS var, jadi `ROUTE_LINE_COLORS` di
  `frontend/lib/supplier-routes.ts` dikunci tes yang **membaca `app/globals.css`** — token
  berubah tanpa menyentuh modul itu akan memerahkan tes.
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
- Timeline vertikal: DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE → ACT → LEARN
- Tiap step: tool yang dipanggil, input ringkas, output ringkas, timestamp, durasi
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
Lima kartu, semuanya dari API, tanpa angka karangan:
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
   SAMA dengan tab KPI; metrik `no_data` ditulis "—".
5. **Rantai audit** — `/ledger/verify`: status rantai, jumlah blok, 10 karakter pertama
   head hash.
Logika murni (tanpa DOM, diuji) ada di `frontend/lib/today.ts`; komponennya
`frontend/components/TodayDashboard.tsx`. Kelas `.today-*` di `globals.css`
memakai token yang sudah ada (tidak ada token baru).

### 3.8 Halaman sidebar acuan yang disesuaikan (Langkah 5 — permintaan Roy 2026-10-11)

Aplikasi acuan `E:\hackathon\HackathonBil\MealchainGuardian` punya 9 halaman sidebar
(`frontend/lib/nav.ts`); repo ini sudah setara untuk 5 (Hari Ini/Overview/Keputusan/
Decision & Evidence/Agent Log) dan **kurang 4**. Keempatnya dibangun ulang di sini
dengan **data API nyata** — bukan data contoh seperti di acuan:

| Tab baru | Di acuan | Sumber angka di repo ini | Yang TIDAK dipakai dari acuan |
|---|---|---|---|
| Keamanan Pangan | `/compliance` | `GET /batches`: `safety_status`, `freshness_score`, `usable_until`, `quantity_kg` | papan CCP per-alat, bank sampel, jejak lot EPCIS (tidak ada endpoint) |
| Surplus & Limbah | `/surplus` | `GET /balance/map?commodity=…`: `surplus_kg`, `shortage_kg`, `latitude`/`longitude`, `region` | pencatatan limbah/disposal (tidak ada tabel; ditulis "—" + alasan) |
| Pemasok | `/suppliers` | **`GET /suppliers`** (35 pemasok: 14 kanonik + 21 demo — daftar, keandalan, komoditas, kapasitas, jarak/koordinat, status eksklusi) + `GET /supplier-exclusions`; pin di peta (lihat §3.1). Halaman Pemasok: kolom **Jarak** (dari `distance_km` server) + penyaring "Hanya dalam jangkauan" untuk peran SPPG; jarak tanpa rujukan ditulis "—". Kolom **Status** menulis pil ringkas dari kunci `shipping` server bila pemasok itu punya kiriman masih layak (`.shipping-tag`, token ok), pil bahaya terpisah `.shipping-tag-fail` bila ada kiriman gagal uji, "Dikecualikan di …" bila ada eksklusi, selain itu "Aktif"; kartu Ringkasan memuat "Sedang mengirim barang: N dari M". **F12c (16 Okt): tabel dirapikan jadi 7 kolom** — "Hub" dan "Koordinat" tidak lagi kolom sendiri, keduanya jadi baris kedua sel **Pemasok** (`supplierMetaLine`: "Surabaya · -7,2395 / 112,7731") karena dua kolom itu memakan 178 px dari 913 px; ukur sesudahnya: tabel **913 = 913 px (tanpa geser)**, tinggi baris **54 px rata**. **Satu standar bentuk label** (dipakai `.reach-tag`, `.shipping-tag`, `.shipping-tag-fail`): 12 px, `padding: 2px 8px`, `inline-flex`, `white-space: nowrap` + `text-overflow: ellipsis`, jadi **tinggi 22 px** (setara `.commodity-pill`) — sebelum F12c pil kiriman memuat kalimat penuh dan membungkus 3 baris (186×63 px). Kalimat penuh tetap tersedia lewat `title`; pil jangkauan hanya menulis keadaan karena km-nya sudah ada di kolom **Jarak** tepat di sebelahnya. Pemasok tanpa sumber profil tetap "—" (tidak dikarang) | harga/PO per pemasok (belum ada endpoint; ditulis "—") |
| Kualitas Agen (bagian 2 tab **KPI & Kualitas Agen**) | `/quality` (`MOCK_AGENT_RUNS` di acuan) | `GET /decisions/{id}/traces` + `verdict` pada `approval-summary` (sampel 8) | LLM-as-judge, biaya token (belum ada di repo) |

Aturan yang dipegang (sama seperti halaman lain): angka yang tidak ada ditulis
"**—**", dan halaman yang memakai **sampel** menyatakan jumlahnya terang-terangan
("dinilai 8 dari 95 keputusan dalam cakupan"). Logika murni dipisah ke
`lib/food-safety.ts`, `lib/surplus.ts`, `lib/suppliers-board.ts`, `lib/agent-quality.ts`
(diuji) dan markup ke `components/*Board.tsx` (kontrak markup diuji). Halaman
**Surplus & Limbah** dibatasi peran SPPG (`sppg_head`, `sppg_nutritionist`) seperti
acuan; sisanya semua peran.

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

### Warna (design token — sinkron dengan `frontend/app/globals.css`, overhaul 2026-10-11)
Sejak 2026-10-11 konsol memakai palet aplikasi acuan `MealchainGuardian` (versi
biru): navy untuk teks/heading, biru brand untuk aksi & navigasi, kartu putih
ber-border tanpa bayangan.
```
--navy-900 (ink): #1F3B4D   /* teks utama & heading */
--navy-700:       #2E5266   /* aksen sekunder, item nav aktif */
--line:           #DCE6E9   /* border & permukaan netral */
--ink-muted:      #555555   /* teks sekunder, caption */
--accent-strong:  #0969DA   /* brand: tombol, link, fokus */
--accent:         #0550AE   /* hover aksi */
--bg-page:        #F5F6FA   /* latar halaman */
--status-safe:    #2E7D32   /* PASS / surplus */
--status-warning: #F9A825   /* tight / needs verification — teks badge pakai navy */
--status-danger:  #C62828   /* FAIL / shortage */
```

Token tambahan hasil audit UI/UX 2026-10-11 (semua sudah diuji kontras WCAG AA
secara terhitung, bukan dikira-kira):

```
--ink-subtle:     #5F6E77   /* teks tersier & pemisah: 5,27:1 di putih, 4,88:1 di latar */
--line-input:     #7C8B9B   /* batas KONTROL interaktif (input/select/chip/tombol): >= 3:1 (WCAG 1.4.11) */
--ok-bg/--ok-border/--ok-ink             /* #ECFDF5 / #A7F3D0 / #065F46 — lencana aman (7,3:1) */
--warn-bg/--warn-border/--warn-ink       /* #FFFBEB / #FDE68A / #8A5A00 — lencana & TEKS peringatan (5,9:1) */
--danger-bg/--danger-border/--danger-ink /* #FEF2F2 / #FECACA / #991B1B — lencana bahaya (7,6:1) */
--neutral-bg/--neutral-border/--neutral-ink /* #F1F5F9 / #CBD5E1 / #475569 — lencana netral (6,9:1) */
--ink-inverse:    #FFFFFF   /* teks di atas latar berwarna (rail, top bar, tombol primer) */
--on-dark-danger: #FF8A80   /* aksi merusak di atas rail biru */
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
- Teks di atas rail/top bar biru minimal `rgba(255,255,255,0.92)` (4,64:1 di
  #0969DA). Nilai 0,45–0,6 sebelumnya gagal AA (label nav 2,84:1).
- Ukuran teks data ≥ 12px (`--text-micro`/`--text-meta`).
- Target sentuh ≥ 44px pada `(pointer: coarse)` **atau** `(max-width: 720px)`
  untuk nav rail, chip, pil komoditas, pilih cakupan, dan tombol ikon.
- Setiap kontrol punya umpan balik `:active` (transform 1px + peredupan, 90ms)
  dan cincin fokus `:focus-visible`; gerak dimatikan saat
  `prefers-reduced-motion: reduce` (umpan balik peredupan tetap ada).
- Keadaan memuat memakai satu pola: komponen `LoadingState` (skeleton +
  `role="status"` + `aria-busy`) — bukan teks "Memuat…" polos.

Panel peta memakai palet aplikasi yang sama (arah Roy 2026-10-11): peta TERANG
apa adanya, legenda putih, pin hijau/merah/abu dari `--status-*` — tidak ada
palet gelap kedua dan tidak ada token tambahan untuk peta.
> Catatan sinkronisasi: `globals.css` `:root` = sumber kebenaran teknis; bagian ini
> merangkum maksudnya. Sidebar, panel peta, dan konsol agent semuanya permukaan
> terang; badge memakai label + tint warna (tanpa titik), mengikuti komponen
> badge acuan.

### Tipografi
- Font: Inter (fallback: system-ui) — jelas terbaca di data-dense dashboard.
  Angka & telemetri memakai monospace sistem (`ui-monospace, SFMono-Regular,
  Menlo, Consolas`) mengikuti `tailwind.config` acuan.
- Heading: 600 weight, Body: 400 weight, ukuran dasar 14px (text-sm) — dashboard padat
- Teks mikro minimal 12px (text-xs); nilai di bawah itu dinaikkan 2026-10-11

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
