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
| — | *(acuan app)* **Kualitas Agen** | Tab **Kualitas Agen** (Langkah 5) — halaman `/quality` di acuan: skor agregat (langkah/run, kesesuaian verifikator, tingkat fallback, keputusan diubah manusia, rata-rata durasi) + rincian per run dari jejak agen nyata ✓ | Tambahan demo |
| 5 | Agent Activity Log (`/agent-log`) | Tab **Agent Log** — trace console + provider panel, pilih decision via dropdown ✓ | Wajib |
| 6 | Approval Modal/Flow | Di dalam Decision Detail ✓ | Wajib |
| 7 | KPI Dashboard (`/kpi`) | Tab **KPI** — 7 KPI live jujur + strip **Target KPI Demo Day** (PRD §5, berlabel "TARGET DEMO · bukan angka live") ✓ | Wajib |
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
- Legenda putih mengapung kiri-bawah ("Status lokasi: Surplus · Seimbang ·
  Shortage") dengan titik berwarna SAMA seperti pin, dan kontrol bawaan
  MapLibre: zoom + kompas kanan-atas, atribusi © OpenStreetMap contributors
  kanan-bawah
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
  2. **Biaya** — harga beli, logistik, biaya aman terkirim, catatan (`cost_breakdown`)
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
| Pemasok | `/suppliers` | pemasok pada `GET /decisions/{id}/approval-summary` (sampel 8 keputusan terakhir) + `GET /supplier-exclusions` | daftar pemasok mandiri, harga/PO (tidak ada endpoint daftar pemasok) |
| Kualitas Agen | `/quality` (`MOCK_AGENT_RUNS` di acuan) | `GET /decisions/{id}/traces` + `verdict` pada `approval-summary` (sampel 8) | LLM-as-judge, biaya token (belum ada di repo) |

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
