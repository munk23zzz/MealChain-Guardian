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
  = daftar kosong); strip "Langkah berikutnya" (`nextStep`, kini BIRU accent-soft karena
  instruksi ≠ bahaya); blok **"Kalau disetujui / Kalau ditolak"** (`consequences`,
  deterministik dari `can_execute`, `blocking_reasons`, `execution_target`, `iteration`).
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
| `.role-hero` (panduan peran, tampil di 3 tab) | 140 px | **72 px** — misi + langkah masuk `<details>` "Panduan peran" |
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
