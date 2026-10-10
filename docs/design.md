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
| 2 | Overview Map (`/overview`) | Tab **Overview** — MapLibre + chart stok + tabel node ✓ | Wajib |
| 3 | Recommendation Feed (`/recommendations`) | Tab **Recommendations** + Decision Detail digabung ✓ | Wajib |
| 4 | Decision Detail & Evidence | Di dalam tab Recommendations (klik kartu) ✓ | Wajib |
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
> `.env`); **P4** chaos sliders memicu Event 3 via API resmi (safety tetap
> dihitung server); **P5** telemetry banner jujur di login (tanpa klaim
> sertifikasi); **P6** tabel facts menu_plans/delivery_events/
> disposal_events → KPI Meal Continuity & Avoidable Food Loss LIVE.
> Polygon Amoy anchoring asli = bonus opsional (butuh internet stabil).
> Angka KPI PRD tampil hanya sebagai target berlabel eksplisit, KPI live
> tetap jujur dari DB (ruling O-KPI).

### 3.1 Dashboard / Peta 10 Lokasi
- Peta **MapLibre GL** (tile raster OpenStreetMap, tanpa API key) dengan 10
  marker, warna sesuai status: merah (shortage), hijau (surplus),
  abu (seimbang); klik marker → popup pasokan/permintaan/gap
- Angka detail per lokasi (pasokan / permintaan / gap) tetap tampil sebagai
  daftar di samping peta — peta bukan satu-satunya sumber angka
- Sidebar: filter komoditas (telur/ayam/beras/wortel), filter status feed
- Untuk SPPG Head/Nutritionist: peta fit ke bounds lokasi-lokasi dari data

### 3.2 Recommendation Feed
- List card, sorted by urgency (safety issue > regional imbalance > price anomaly)
- Tiap card: judul singkat ("Alokasi Cianjur→Jakarta direkomendasikan"), badge status
  (Pending Approval/Approved/Rejected/Executed), waktu, tombol "Lihat Detail"
- Empty state: "Belum ada rekomendasi aktif" (bukan kosong tanpa penjelasan)

### 3.3 Decision Detail & Evidence
- Header: jenis keputusan, Safe Delivered Cost breakdown (tabel: purchase+transport+handling+
  expected loss+freshness risk+safety penalty = total)
- Evidence timeline: tiap bukti (SAP data, sensor, inspeksi) dengan sumber & timestamp,
  ditandai konsisten/tidak konsisten
- Hard constraint checklist: safety eligibility ✅/❌, freshness threshold ✅/❌, capacity ✅/❌,
  delivery window ✅/❌ — kalau ada yang ❌, kandidat itu otomatis tidak muncul sebagai opsi
- Verifier Agent note: catatan audit dari Verifier (kalau ada flag)
- Tombol Approve/Reject (hanya kalau status Pending Approval & user punya hak akses lokasi itu)

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
> Catatan sinkronisasi: `globals.css` `:root` = sumber kebenaran teknis; bagian ini
> merangkum maksudnya. Panel gelap/teal ala mockup "Cold-Chain Integrity Console"
> sudah tidak dipakai — acuan tidak punya panel gelap, jadi sidebar, panel peta,
> dan konsol agent semuanya permukaan terang. Badge memakai label + tint warna
> (tanpa titik), mengikuti komponen badge acuan.

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
  sejak 2026-10-09) — tile raster OSM gratis tanpa API key, marker berwarna per
  status, popup detail per lokasi, fitBounds otomatis dari koordinat database.
  Versi sementara SVG skematik sudah diganti.
- **Chart**: Recharts (konsisten dengan chart proposal)
- **Component library**: shadcn/ui di atas Tailwind — cepat untuk build, mudah di-custom
  warnanya sesuai design token di atas
- **Real-time update**: polling sederhana (bukan WebSocket) untuk MVP — cukup untuk demo,
  lebih simpel diimplementasi dalam waktu terbatas
