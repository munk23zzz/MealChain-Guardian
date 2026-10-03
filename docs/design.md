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

| # | Screen | Prioritas |
|---|---|---|
| 1 | Login | Wajib |
| 2 | Dashboard / Peta 10 Lokasi | Wajib |
| 3 | Recommendation Feed | Wajib |
| 4 | Decision Detail & Evidence | Wajib |
| 5 | Agent Activity Log (trace timeline) | Wajib — ini yang dipertunjukkan ke juri |
| 6 | Approval Modal/Flow | Wajib |
| 7 | KPI Dashboard | Wajib |
| 8 | Settings/Admin (manage users, lokasi) | Nice-to-have |

### 3.1 Dashboard / Peta 10 Lokasi
- Peta (MapLibre) dengan 10 marker, warna sesuai status: hijau (normal), kuning (tight),
  merah (shortage/surplus signifikan)
- Klik marker → popup ringkas (nama lokasi, komoditas, status, link ke detail)
- Sidebar: filter komoditas (telur/ayam/wortel), filter status
- Untuk SPPG Head/Nutritionist: peta di-zoom ke lokasi sendiri, badge lokasi lain di-mute

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

### Warna (konsisten dengan proposal — jangan ganti tanpa alasan kuat)
```
--navy-900: #1F3B4D      /* header, teks penting */
--navy-700: #2E5266      /* aksen utama, tombol primer */
--navy-100: #DCE6E9      /* background card netral */
--grey-500: #555555      /* teks sekunder, caption */
--status-safe: #2E7D32    /* PASS / normal */
--status-warning: #F9A825 /* tight / needs verification */
--status-danger: #C62828  /* FAIL / shortage kritis */
```

### Tipografi
- Font: Inter (fallback: system-ui) — jelas terbaca di data-dense dashboard
- Heading: 600 weight, Body: 400 weight, ukuran dasar 14-16px untuk dashboard density

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
- **Map**: MapLibre GL JS + tile OSM gratis (konsisten dengan OSRM yang dipakai di proposal)
- **Chart**: Recharts (konsisten dengan chart proposal)
- **Component library**: shadcn/ui di atas Tailwind — cepat untuk build, mudah di-custom
  warnanya sesuai design token di atas
- **Real-time update**: polling sederhana (bukan WebSocket) untuk MVP — cukup untuk demo,
  lebih simpel diimplementasi dalam waktu terbatas
