# UI/UX UPGRADE — 29 Okt 2026

**Sifat dokumen:** hasil Fase 1 (inspeksi + baseline) dan rencana kerja. Status pengerjaan
ditulis di `TODO.md`; dokumen ini tidak dinaikkan statusnya sendiri.

**Repo:** `E:\hackathon\HackathonAWS\mealchain-guardian` · branch `feature/db-modes-demo-coverage`
· working tree kotor (174 entri, milik beberapa sesi) — tidak ada commit yang dibuat sesi ini.

---

## 1. Baseline terukur (29 Okt 2026, 12:54–13:0x WIB)

| Gerbang | Perintah | Hasil |
|---|---|---|
| Typecheck | `npx tsc --noEmit` | **0 error** |
| Lint | `npx next lint` | **0 warning / 0 error** |
| Unit/komponen | `npx vitest run --pool=forks --poolOptions.forks.singleFork=true` | **244 berkas / 2.728 tes lulus**, 45,6 dtk |
| Build produksi | `NEXT_DIST_DIR=.next-p1next npm run build` | **sukses**; rute `/` 479 kB, First Load JS **574 kB** |

Stack yang dipakai untuk inspeksi visual: `mealchain-frontend` :3010, `mealchain-backend` :8000,
`mealchain-postgres` :15432. Peran: `sppg.head@demo.local` (SPPG Operations Lead).
Build memakai `NEXT_DIST_DIR` terpisah karena dev server memegang `.next/trace`; direktori
sementara sudah dihapus dan `tsconfig.json` dikembalikan ke keadaan sebelum build (hanya
`target: es2017` milik sesi lain yang tersisa).

Catatan bundle: 574 kB First Load untuk satu halaman konsol adalah temuan tersendiri
(recharts + maplibre ikut di chunk awal). Tidak diubah di fase ini.

---

## 2. Peta lima modul

| Modul prompt | Tab konsol | Komponen utama | Endpoint |
|---|---|---|---|
| A. Agent Log | `agent-log` | `app/page.tsx` §agent-log, `ModuleSearch`, `AgentActivityPanel` → `DecisionAuditTable` + `AgentPipelinePanel`, `AgentTraceViewer`, `AgentRunSummary`, `AgentRoster`, `SupervisorStatusLine`, `IntegrityPanel` | `GET /decisions`, `/decisions/{id}/traces`, `/decisions/{id}/ledger`, `/agent/quality-sample`, `/supervisor/health` |
| B. KPI Dashboard | `kpi-kualitas` | `KpiQualityBoard` → `KPIDashboard` (+ `KpiDetailPanel`, `KpiScopeToggle`), `AgentQualityBoard` | `GET /kpi`, `/agent/quality-sample` |
| C. Keamanan Pangan | `safety` | `FoodSafetyBoard` (2.002 baris) + `ReceiptDrawer`, `BatchPerhatianCard`, `ComplianceEvidencePanel` | `GET /batches`, `/batches/{id}`, `/supplier-routes`, `/balance/map`, `/decisions`, `POST /safety/evaluate`, `/receipts/*` |
| D. Pemasokan & Kebutuhan | `location-network` (label "Pasokan & Kebutuhan" untuk nutritionist) | `LocationNetworkBoard`, `SupplyDemandPanel`, `AllocationTable`, `FactList` | `GET /balance/map`, `/balance/{loc}/{com}`, `/supply/{loc}/{com}`, `/demand/{loc}/{com}`, `/demand/forecast/{loc}/{com}`, `/surplus/allocations`, `/waste/summary`, `/batches`, `/decisions` |
| E. Decision & Evidence | `evidence` | `DecisionEvidence` → `DecisionDetail`, `DecisionChain`, `DecisionAudit`, `ComplianceEvidencePanel`, `IntegrityPanel`, `DecisionDrawer` | `GET /decisions`, `/decisions/{id}` (+ `/traces`, `/chain`, `/approval-summary`, `/ledger`), `/ledger/verify`, `/purchase-orders` |

Kontrak yang **tidak boleh berubah**: definisi 8 KPI (`lib/kpi.ts` + `app/services/kpi_service.py`),
ambang keselamatan (`app/core/temperature.py`, `commodity_policies`), aturan gerbang
persetujuan/eksekusi, dan RBAC tiap peran.

---

## 3. Temuan per modul (terhadap kriteria prompt)

Legenda: **Ada** = memenuhi; **Sebagian** = ada tetapi belum sesuai kriteria; **Belum** = tidak ada.

### A. Agent Log

| Kriteria | Status | Bukti / sebab |
|---|---|---|
| Ringkasan eksekusi (total/sukses/gagal/berjalan/durasi) | **Belum** | Halaman hanya menulis "17 dari 17 keputusan dalam cakupan" + chip verifikasi. Tidak ada agregat durasi/langkah. |
| Timeline / daftar kronologis | **Sebagian** | Ada tabel keputusan + strip 9 tahap + panel langkah; tidak ada urutan kronologis lintas keputusan. |
| Detail per eksekusi | **Sebagian** | Detail ada, tetapi berupa blok di bawah tabel (bukan drawer/detail page) dan mengikuti `decision_id`, bukan execution/correlation ID. |
| Pencarian & filter | **Ada** | `ModuleSearch`: teks, komoditas, status verifikasi, periode, chip status, reset. Belum ada filter *agen* dan filter *error/warning*. |
| Status eksekusi | **Sebagian** | Yang tercatat: keadaan verifikasi + status keputusan. Database tidak menyimpan status `running`/`failed` per eksekusi — tidak boleh dikarang. |
| Redaksi data sensitif | **Ada** | Trace hanya memuat `step_name/tool_called/duration_ms/agent_name`. |

### B. KPI Dashboard

| Kriteria | Status | Bukti / sebab |
|---|---|---|
| Hierarki/grup KPI (safety, pasokan, susut, agen, finansial) | **Belum** | Satu grid datar "Hasil operasional" berisi 8 kartu; tidak ada pengelompokan domain. |
| Kartu: nama, nilai, unit, periode, status, tren | **Sebagian** | Nama/unit/status/tren ada; periode ada di header (bukan per kartu); tidak ada sparkline historis (data historis per metrik tidak dikirim `/kpi`). |
| Detail definisi & sumber | **Ada** | `KpiDetailPanel` + provenance per kartu (`kpi-provenance`). |
| Live vs simulasi vs historis | **Ada** | `data_mode`, `data-testid="kpi-demo-note"`, `kpi-basis`. |
| `null` ≠ 0, pembagian nol aman | **Ada** | `fmtValue`/`STATE_LABEL`, alasan `no_data` dari server (S4-53). |
| Cap waktu kesegaran data | **Belum** | Tidak ada "diperbarui <jam>" per kartu/panel; hanya pil periode. |
| Jumlah metrik | **8** | Kontrak 7 vs kode 8 sedang disengketakan di AUD-013. Sesi ini **tidak** mengubah jumlah. |

### C. Keamanan Pangan

| Kriteria | Status | Bukti / sebab |
|---|---|---|
| Ringkasan (total/aman/berisiko/tidak aman/kedaluwarsa/pending) | **Ada** | "Ringkasan pengawasan" + `safety-ringkasan-mendesak`, tile kedaluwarsa, bukti suhu. |
| Tabel batch: ID, komoditas, pemasok, status, suhu, masa layak, tindakan | **Sebagian** | Kolom yang ada: batch, lokasi/komoditas, status, kesegaran, layak sampai, sisa masa, tindakan. **Suhu terkini dan rentang aman tidak ada di tabel**; pemasok tidak ada. |
| Sortir/filter/cari/paginasi/pilih baris | **Sebagian** | Cari + 5 saringan + paginasi + ekspor; **sortir kolom belum ada**; tidak ada keadaan baris terpilih. |
| Hierarki status (aman/peringatan/tidak aman/kedaluwarsa/pending) | **Ada** | `safety-state-*`, badge teks, bukan warna saja. |
| Grafik suhu time-series | **Belum** | Hanya ringkasan bukti suhu (jumlah sampel, menit penyimpangan). `GET /batches` & `/batches/{id}` **tidak mengirim sampel** `temperature_log`. |
| Detail batch (provenance, riwayat suhu, kebijakan, keputusan terkait) | **Sebagian** | Ada kartu bukti suhu, asal log ("log simulasi"), bagian keputusan keamanan; tidak ada drawer per batch yang menyatukan provenance + policy + riwayat. |
| Penjelasan "mengapa ditandai" | **Ada** | `urgencyReason`/`reasons` dari evaluator + langkah berikutnya per baris. |

### D. Pemasokan & Kebutuhan

| Kriteria | Status | Bukti / sebab |
|---|---|---|
| Ringkasan pasokan/kebutuhan/selisih | **Ada** | `SupplyDemandPanel`: pasokan terakhir, kebutuhan, selisih, perkiraan 7 hari (dengan metode + keyakinan). |
| Inbound terkonfirmasi, PO tertunda, pengiriman berisiko | **Belum di halaman ini** | Data PO ada di tab Pemasok & Decision; halaman ini tidak merangkumnya. |
| Perbandingan demand vs supply (grafik) | **Belum** | Hanya tabel selisih per lokasi. Grafik kecukupan ada di Overview. |
| Peringatan kekurangan/kelebihan berurut keparahan | **Ada** | `networkHeadline` + `sortBySeverity` + nada warna. |
| Pemisahan forecast vs stok aktual | **Ada** | Kartu perkiraan terpisah, label metode + "dasar tipis". |
| Satuan konsisten | **Ada** | Semua kg; `formatKg`. |

### E. Decision & Evidence

| Kriteria | Status | Bukti / sebab |
|---|---|---|
| Ringkasan keputusan (ID, tipe, status, waktu, aktor, entitas) | **Ada** | Dossier `DecisionDetail`. |
| Approval / execution / verification terpisah | **Sebagian** | Badge status keputusan + `approval-summary` + `IntegrityPanel`; perlu diverifikasi apakah tiga keadaan itu punya label masing-masing di semua keadaan. |
| Lini masa siklus keputusan | **Ada** | `DecisionChain` (dari `GET /decisions/{id}/chain`), aktor + waktu. |
| Evidence explorer berkategori | **Sebagian** | `ComplianceEvidencePanel` + `DecisionAudit`; kategori mengikuti sumber yang ada. |
| Integritas ledger + peringatan | **Ada** | `IntegrityPanel` (blok, chain valid, cakupan, "perlu tinjau"). |
| Aksi persetujuan dengan konfirmasi | **Ada** | `ApprovalModal`/`ApprovalMenu`, `DecisionActions`, konfirmasi + disabled saat pending. |

---

## 4. Rencana kerja (fase berikutnya)

Setiap paket = satu langkah yang bisa diverifikasi sendiri (tes → `tsc` → `lint` → ukur DOM).
Tidak ada perubahan formula KPI, ambang keselamatan, atau aturan RBAC.

| Paket | Isi | Berkas utama | Risiko |
|---|---|---|---|
| **UI-1 Agent Log** | Strip "Ringkasan eksekusi" dari data nyata (`runs`, langkah, durasi rata-rata, fallback, keputusan tanpa ACT, agen terlibat); filter **agen**; cari berdasarkan ID keputusan; nyatakan bahwa status `running/failed` tidak dicatat; drawer detail eksekusi (ID + trace + ringkasan) memakai komponen yang sudah ada. | `agent-activity.css`, `AgentActivityPanel`, `ModuleSearch`, `lib/agent-activity.ts`, `app/page.tsx` | File juga disentuh sesi lain (AUD-028/029) |
| **UI-2 KPI** | **DIBATALKAN atas permintaan pemilik (29 Okt 2026):** pengelompokan domain (judul grup + jumlah metrik + kalimat penjelas) sempat dipasang lalu dihapus — bagian "Hasil operasional" kini hanya kartu KPI dalam satu grid datar. `groupKpiMetrics` + tesnya ikut dihapus. Yang dipertahankan: pil "Dihitung <jam> WIB" dari `computed_at` server. Sparkline tetap **tidak** dibuat karena `/kpi` tidak mengirim riwayat. | `KPIDashboard.tsx`, `theme-ext.css` | AUD-013 (7 vs 8) |
| **UI-3 Keamanan Pangan** | Kolom suhu terkini + rentang aman (dari `evidence.commodity_profile` + sampel terakhir **jika** tersedia); sortir kolom; drawer detail batch (provenance, policy, bukti suhu, keputusan terkait); grafik suhu hanya bila endpoint baca sampel ditambahkan. | `FoodSafetyBoard.tsx`, `lib/food-safety.ts`, `theme-ext.css`; usulan backend: field `temperature_samples` di `GET /batches/{id}` | Perubahan backend aditif + tes |
| **UI-4 Pemasokan & Kebutuhan** | Strip ringkasan (pasokan, kebutuhan, selisih, perkiraan, PO tertunda dari `/purchase-orders` bila peran berhak); grafik batang demand vs supply per lokasi dari `/balance/map` yang **sudah** diambil; urutkan kekurangan kritis lebih dulu. | `LocationNetworkBoard.tsx`, `SupplyDemandPanel.tsx`, `supply-adequacy.css` | Duplikasi visual dengan Overview |
| **UI-5 Decision & Evidence** | Pisahkan tiga lencana (persetujuan / eksekusi / verifikasi) dengan label teks; kelompokkan bukti per kategori; pastikan peringatan integritas selalu terlihat (tidak di lipatan). | `DecisionEvidence.tsx`, `DecisionDetail.tsx`, `evidence-dossier.css` | Kontrak tes markup |
| **UI-6 Verifikasi** | Sweep 390/768/1280 px per tab (metode `00b-mobile-dan-peran`), axe pada 5 tab, tangkapan layar sebelum/sesudah, suite penuh + build. | `_qa/ui-ux-2026-10-29/` | — |

---

## 5. Batasan yang dinyatakan di muka

1. **Status `running`/`failed` per eksekusi tidak ada di skema.** Agent Log akan melaporkan apa
   yang tercatat (langkah, durasi, fallback, keputusan tanpa ACT) dan menyebut batas ini — bukan
   mengarang status.
2. **Sampel suhu mentah tidak diekspos** oleh endpoint baca mana pun (`GET /batches/{id}` hanya
   mengirim ringkasan `evidence`). Grafik suhu butuh field aditif di endpoint itu.
3. **Riwayat KPI per metrik tidak dikirim** `/kpi`, jadi sparkline tren tidak akan dibuat.
4. **Working tree dipakai bersama beberapa sesi** (174 entri kotor, termasuk `globals.css`,
   `page.tsx`, `FoodSafetyBoard.tsx`). Patch dibuat sekecil mungkin dan setiap langkah diakhiri
   `tsc` + `vitest` agar regresi sesi lain langsung terlihat. Tidak ada `git commit`, `checkout`,
   atau `stash`.
5. Angka keadaan (jumlah batch/keputusan) tidak ditulis di dokumen ini; sumbernya
   `docs/state-snapshot.md`.
