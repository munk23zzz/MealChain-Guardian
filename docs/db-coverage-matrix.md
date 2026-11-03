# Matriks Cakupan Database — MealChain Guardian

Dibuat otomatis oleh `scripts/audit/db_coverage.py` pada 2026-10-22 15:01 WIB. Seluruh angka di bawah diambil dari kondisi live saat skrip berjalan; berkas ini ditulis ulang setiap kali skrip dijalankan.

**Sumber bukti:** route dari `app.main` (kontainer backend), skema dari `Base.metadata` + `information_schema`, kosakata dari `pg_constraint` + `Literal[...]` kode, respons dari panggilan HTTP nyata dengan akun demo, dan satu query SQL per baris matriks. Tidak ada angka yang ditulis tangan.

## Ringkasan angka

| Ukuran | Nilai |
|---|---|
| Layar/tab di sidebar | 11 (terbaca dari `navItems` di `app/page.tsx`) |
| Baris matriks (layar/bagian) | 36 |
| Baris TERBUKTI (data ada + endpoint 2xx) | 33 |
| Baris GAP (belum ada data demo / klaim gagal) | 0 |
| Baris DIPENSIUNKAN (panel sengaja tidak dipasang, ada bukti tes) | 3 |
| Baris tanpa baris data sama sekali | 0 |
| Baris tanpa tabel data (status dari env/artefak) | 1 |
| Baris yang panelnya tidak terpasang di layar | 3 (dari itu 3 dipensiunkan sengaja) |
| Baris dengan klaim tak terverifikasi | 0 |
| Tabel di `Base.metadata` | 21 |
| Tabel di DB (`information_schema`) | 23 |
| Route FastAPI hidup (path+method) | 79 |
| Route GET yang diprobe | 28 |
| Fungsi request frontend terbaca (`lib/*.ts`) | 66 |
| Enum diperiksa | 11 |
| Enum dengan ketidaksinkronan (kode vs skema vs data) | 3 |
| Sel state tampilan diperiksa | 612 |
| Sel state TERBUKTI | 289 |
| Sel state GAP | 292 |
| Sel state tidak berlaku (N/A) | 31 |
| Komponen di `frontend/components` | 56 |
| Komponen tidak terpasang di layar mana pun | 5 |

Legenda status baris: **TERBUKTI** = semua klaim lolos pemeriksaan (label UI ada, fungsi api menunjuk route live, kolom ada di skema, endpoint membalas 2xx untuk peran utama layar itu, query bukti > 0 baris). **GAP** = ada klaim yang gagal atau datanya kosong; alasannya ada di kolom bukti dan di §5. Kolom *Terpasang* menandai panel yang benar-benar dirender; 403 pada peran lain adalah cakupan peran (desain), bukan kegagalan.

## 0. Kondisi DB saat audit

Jumlah baris dihitung dengan `count(*)` (bukan `n_live_tup`) pada awal dan akhir run. Kolom *bergerak* menandai tabel yang isinya berubah **selama** audit — kalau ada, angka di laporan ini adalah potret satu titik waktu, bukan nilai stabil.

| Tabel | Baris (awal) | Baris (akhir) | origin: seed / demo | Baris ber-sesi demo | Bergerak |
|---|---|---|---|---|---|
| `agent_traces` | 106 | 106 | — | — | tidak |
| `alembic_version` | 1 | 1 | — | — | tidak |
| `approvals` | 19 | 19 | — | — | tidak |
| `batch_receipts` | 7 | 7 | — | 0 | tidak |
| `batches` | 125 | 125 | 78 / 47 | 0 | tidak |
| `commodities` | 4 | 4 | — | — | tidak |
| `decision_evidence` | 46 | 46 | — | — | tidak |
| `decisions` | 47 | 47 | 31 / 16 | 0 | tidak |
| `delivery_events` | 290 | 290 | 70 / 220 | 0 | tidak |
| `demand_records` | 1360 | 1360 | 280 / 1080 | 0 | tidak |
| `demo_sessions` | 4 | 4 | — | — | tidak |
| `disposal_events` | 83 | 83 | 22 / 61 | 0 | tidak |
| `ledger_blocks` | 72 | 72 | — | — | tidak |
| `locations` | 10 | 10 | — | — | tidak |
| `menu_plans` | 660 | 660 | 70 / 590 | 0 | tidak |
| `price_signals` | 6015 | 6015 | 124 / 5891 | 0 | tidak |
| `road_routes` | 51 | 51 | — | 0 | tidak |
| `sap_mock_material_stock` | 40 | 40 | — | 0 | tidak |
| `sap_mock_purchase_orders` | 20 | 20 | 16 / 4 | 0 | tidak |
| `supplier_exclusions` | 6 | 6 | — | 0 | tidak |
| `suppliers` | 61 | 61 | — | — | tidak |
| `supply_records` | 5240 | 5240 | 40 / 5200 | 0 | tidak |
| `users` | 7 | 7 | — | — | tidak |

## 1. Matriks layar → data

Kolom *fungsi api* dan *endpoint* dihasilkan dari rantai nyata: nama fungsi diparse dari `frontend/lib/api.ts` (+ `lib/supplier-exclusions.ts`), path-nya dicocokkan ke route FastAPI yang hidup. Kolom *bukti demo* memuat hasil query per baris plus status HTTP endpoint utamanya untuk dua peran demo.

| # | Layar | Bagian/panel | Terpasang | Field/kartu (terverifikasi di komponen) | Fungsi api | Endpoint backend | Tabel.kolom sumber | Bukti demo (query + HTTP) | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Hari Ini | Tile status hari ini | ya | Hari Ini · Menunggu persetujuan · Ditandai verifikator · Rekomendasi | fetchDecisions, fetchBatches, fetchKpis | GET /batches<br>GET /decisions<br>GET /kpi | decisions.status, decisions.expires_at, decisions.decision_type, batches.usable_until, batches.safety_status, delivery_events.delivered_at | SQL 21 baris, contoh `0652c9bb-f35f-49d6-bda0-d3b87d350893` ; sppg_head 200/17 baris · bgn_monitor 200/47 baris | TERBUKTI |
| 2 | Hari Ini | Agenda harian | ya | Agenda harian · Tidak ada agenda yang belum lewat tenggat | fetchAgenda | GET /agenda | menu_plans.plan_date, menu_plans.planned_portions, delivery_events.delivered_at | SQL 660 baris, contoh `2026-09-01` ; sppg_head 200/29 baris · bgn_monitor 200/29 baris | TERBUKTI |
| 3 | Hari Ini | Rantai audit (Merkle ledger) | ya | Rantai audit · Blok terverifikasi · Kode verifikasi | verifyLedger | GET /ledger/verify | ledger_blocks.payload_hash, ledger_blocks.prev_hash, ledger_blocks.height | SQL 72 baris, contoh `1` ; sppg_head 200/1 baris · bgn_monitor 200/1 baris | TERBUKTI |
| 4 | Overview | Ringkasan peta pasokan (bento KPI) | ya | Overview Pasokan &amp; Distribusi · Selisih pasokan jaringan · Data simulasi · Sinkron otomatis | fetchBalanceMap | GET /balance/map | supply_records.quantity_kg, demand_records.quantity_kg, locations.name, locations.role_hint | SQL 10 baris, contoh `Bandung` ; sppg_head 200/1 baris · bgn_monitor 200/10 baris | TERBUKTI |
| 5 | Overview | Peta kondisi komoditas | ya | Peta kondisi komoditas · Legenda status · Status Lokasi · Pemasok | fetchBalanceMap, fetchBalance | GET /balance/map<br>GET /balance/{location}/{commodity} | supply_records.quantity_kg, locations.latitude, locations.longitude, suppliers.latitude, suppliers.longitude | SQL 10 baris, contoh `0d54faa0-89a5-5861-bbb8-95ec97ca2381` ; sppg_head 200/1 baris · bgn_monitor 200/10 baris | TERBUKTI |
| 6 | Overview | Grafik kecukupan pasokan | ya | Kecukupan pasokan · Kesegaran · Legenda kualitas stok | fetchBalanceMap | GET /balance/map | batches.freshness_score, supply_records.quantity_kg, demand_records.quantity_kg | SQL 124 baris, contoh `0334b041-a05a-5848-b25d-bbbedf6cdceb` ; sppg_head 200/1 baris · bgn_monitor 200/10 baris | TERBUKTI |
| 7 | Overview | Grafik keseimbangan pasokan | ya | Pasokan per lokasi · Legenda keseimbangan pasokan | fetchBalanceMap | GET /balance/map | supply_records.quantity_kg, demand_records.quantity_kg, locations.name | SQL 1360 baris, contoh `001a358d-56a9-4e1a-8c9d-4a65c0f7398a` ; sppg_head 200/1 baris · bgn_monitor 200/10 baris | TERBUKTI |
| 8 | Overview | Kartu informasi pengiriman | ya | Informasi pengiriman · Periksa kiriman | fetchSupplierRoutes | GET /supplier-routes | road_routes.distance_m, road_routes.duration_s, batches.dispatched_at, suppliers.latitude | SQL 51 baris, contoh `driving:-2.9641,104.7634>-2.9761,104.7754` ; sppg_head 200/15 baris · bgn_monitor 200/50 baris | TERBUKTI |
| 9 | Overview | Telemetri node | ya | Telemetri node · Memuat kondisi lokasi… | fetchBalanceMap | GET /balance/map | supply_records.quantity_kg, locations.latitude, locations.longitude | SQL 10 baris, contoh `Bandung` ; sppg_head 200/1 baris · bgn_monitor 200/10 baris | TERBUKTI |
| 10 | Recommendations | Feed rekomendasi + filter/sort + pager | ya | Rekomendasi baru · Penyeimbangan pasokan regional · Lewat tenggat | fetchDecisions | GET /decisions | decisions.decision_type, decisions.status, decisions.quantity_kg, decisions.safe_delivered_cost, decisions.expires_at | SQL 47 baris, contoh `01cc3ea0-d5ae-4146-9e23-49fdcabaa4ce` ; sppg_head 200/17 baris · bgn_monitor 200/47 baris | TERBUKTI |
| 11 | Recommendations | Konsol operasi — snapshot kondisi | **tidak** | Muat kondisi · Pasokan · Permintaan · Surplus · Shortage | fetchBalance | GET /balance/{location}/{commodity} | supply_records.quantity_kg, demand_records.quantity_kg, locations.name | SQL 524 baris, contoh `003e5ac7-407c-4e71-b48d-985ab86c0c98` ; sppg_head 200/1 baris · bgn_monitor 200/1 baris | DIPENSIUNKAN |
| 12 | Recommendations | Konsol operasi — analisis agent & usulan | **tidak** | Jalankan Analisis Agent · SDC · Ajukan · Hasil Event 1 penuh | runAnalysis, createDecision, proposeAction, runEvent1 | POST /actions/propose<br>POST /balance/analyze<br>POST /decisions<br>POST /demo/event1 | decisions.safe_delivered_cost, decisions.quantity_kg, price_signals.price_per_kg, agent_traces.step_name | SQL 6015 baris, contoh `000a09f2-d0f3-41e5-9e93-03768dbe9fb6` ; sppg_head 200/24 baris · bgn_monitor 403/1 baris | DIPENSIUNKAN |
| 13 | Recommendations | Panel anomali harga (Event 2) | ya | Event 2 — Deteksi Anomali Harga · Deviasi · Klasifikasi · Masuk review queue | fetchPriceQuotes | GET /price/quotes/{location}/{commodity} | price_signals.price_per_kg, price_signals.source, price_signals.supplier_id | SQL 706 baris, contoh `pihps_reference` ; sppg_head 200/20 baris · bgn_monitor 200/20 baris | TERBUKTI |
| 14 | Decision & Evidence | Ringkasan keputusan & bukti | ya | Ringkasan keputusan · Keputusan yang diperiksa · Terbaca · Unduh bukti (JSON) | fetchDecision, fetchDecisionTraces | GET /decisions/{decision_id}<br>GET /decisions/{decision_id}/traces | decisions.status, decisions.safe_delivered_cost, decision_evidence.evidence_type, decision_evidence.payload, agent_traces.step_name | SQL 46 baris, contoh `gps` ; sppg_head 200/1 baris · bgn_monitor 200/1 baris | TERBUKTI |
| 15 | Decision & Evidence | Jejak & riwayat persetujuan | ya | Jejak & riwayat · Kelola persetujuan… · Peran penyetuju | fetchDecisionChain, fetchApprovalSummary | GET /decisions/{decision_id}/approval-summary<br>GET /decisions/{decision_id}/chain | approvals.approved, approvals.comment, approvals.approved_at, decisions.iteration, decisions.supersedes_id | SQL 19 baris, contoh `220b90b5-728d-59b8-84e8-9425a768a240` ; sppg_head 200/1 baris · bgn_monitor 200/1 baris | TERBUKTI |
| 16 | Decision & Evidence | Integritas bukti & dossier | ya | Integritas Bukti · Merkle Ledger · Dossier Keputusan · Tanda tangan · Blok | fetchDossier, verifyLedger | GET /decisions/{decision_id}/dossier<br>GET /ledger/verify | ledger_blocks.payload_hash, ledger_blocks.entity_id, decision_evidence.payload | SQL 72 baris, contoh `01cc3ea0-d5ae-4146-9e23-49fdcabaa4ce` ; sppg_head 200/1 baris · bgn_monitor 200/1 baris | TERBUKTI |
| 17 | Decision & Evidence | Daftar purchase order (SAP simulasi) | ya | Data berasal dari SAP simulasi · SAP simulasi · Unduh PDF · Belum ada purchase order tercatat. | fetchPurchaseOrders, fetchPurchaseOrderSummary, fetchPurchaseOrderPdf | GET /sap/purchase-orders<br>GET /sap/purchase-orders/summary<br>GET /sap/purchase-orders/{po_number}/pdf | sap_mock_purchase_orders.po_number, sap_mock_purchase_orders.status, sap_mock_purchase_orders.price, sap_mock_purchase_orders.ordered_quantity, sap_mock_purchase_orders.decision_id | SQL 20 baris, contoh `4500000001` ; sppg_head 200/2 baris · bgn_monitor 200/20 baris | TERBUKTI |
| 18 | Keamanan Pangan | Papan batch & uji keamanan | ya | Periksa kiriman · Batch diperiksa · Kesegaran · Layak sampai · Berat batch gagal | fetchBatches, evaluateSafety, evaluateFreshness | GET /batches<br>POST /freshness/evaluate<br>POST /safety/evaluate | batches.safety_status, batches.freshness_score, batches.usable_until, batches.temperature_log, batches.certification_status | SQL 125 baris, contoh `0334b041-a05a-5848-b25d-bbbedf6cdceb` ; sppg_head 200/125 baris · bgn_monitor 200/125 baris | TERBUKTI |
| 19 | Keamanan Pangan | Penerimaan barang | ya | Penerimaan barang · Catat hasil terima & hitung ulang · Kirim penolakan · Menunggu persetujuan | fetchReceipts, fetchPendingReceipts, recordReceipt, approveReceipt, rejectReceipt | GET /receipts<br>GET /receipts/menunggu<br>POST /receipts<br>POST /receipts/{receipt_id}/approve<br>POST /receipts/{receipt_id}/reject | batch_receipts.status, batch_receipts.checked, batch_receipts.review_note, batch_receipts.recorded_at | SQL 7 baris, contoh `126d2330-f98a-5df2-88e9-cb108919c0ac` ; sppg_head 200/3 baris · bgn_monitor 200/5 baris | TERBUKTI |
| 20 | Keamanan Pangan | Karantina batch | ya | Lepas dari karantina · Nyatakan gagal · Ditahan (karantina) · Alasan (tercatat di ledger) | ubahKarantina | POST /batches/{batch_id}/quarantine | batches.quarantine_status, batches.quarantine_reason, batches.quarantined_at, batches.quarantine_actor_id | SQL 4 baris, contoh `467caaad-9d7b-559d-8f81-3e5efd48d53f` ; sppg_head 200/125 baris · bgn_monitor 200/125 baris | TERBUKTI |
| 21 | Surplus & Limbah | Rencana alokasi surplus | ya | Rencana alokasi surplus · Total surplus · Total kekurangan · Tujuan · Dari | fetchSurplusAllocations | GET /surplus/allocations | supply_records.quantity_kg, demand_records.quantity_kg, locations.name, locations.latitude | SQL 40 baris, contoh `0d82762a-f042-4283-89b5-6e11be4965dc` ; sppg_head 200/1 baris · bgn_monitor 200/1 baris | TERBUKTI |
| 22 | Surplus & Limbah | Pencatatan limbah | ya | Pencatatan limbah · Neraca hari ini | fetchWasteSummary | GET /waste/summary | disposal_events.quantity_kg, disposal_events.reason, disposal_events.partner_name | SQL 83 baris, contoh `0277eae3-926a-5cfd-b018-2be538ae4680` ; sppg_head 200/1 baris · bgn_monitor 200/10 baris | TERBUKTI |
| 23 | Pemasok | Daftar pemasok + pencarian | ya | Daftar pemasok · Pemasok terdaftar · Rata-rata keandalan · Dalam jangkauan · Hapus pencarian | fetchSuppliers | GET /suppliers | suppliers.name, suppliers.reliability_score, suppliers.certification_status, suppliers.capacity_kg_per_week, suppliers.latitude, suppliers.address | SQL 61 baris, contoh `CV Ambarawa Telur Utama` ; sppg_head 200/61 baris · bgn_monitor 200/61 baris | TERBUKTI |
| 24 | Pemasok | Jalur kiriman (jalan) | ya | Jalur kirim · Jalur kiriman (jalan) · Sedang mengirim barang | fetchSupplierRoutes | GET /supplier-routes | road_routes.distance_m, road_routes.duration_s, road_routes.geometry, batches.dispatched_at | SQL 51 baris, contoh `driving:-2.9641,104.7634>-2.9761,104.7754` ; sppg_head 200/15 baris · bgn_monitor 200/124 baris | TERBUKTI |
| 25 | Pemasok | Supplier governance (eksklusi/pemulihan) | ya | Supplier governance · Ajukan exclusion · Ajukan pemulihan · Alasan exclusion · ID bukti tersimpan (opsional bila memilih di atas) | fetchExclusions, fetchSupplierContext, proposeSupplierExclusion, proposeSupplierRestoration | GET /supplier-exclusions<br>GET /supplier-exclusions/context/{decision_id}<br>POST /supplier-exclusions/proposals<br>POST /supplier-exclusions/{exclusion_id}/restore | supplier_exclusions.status, supplier_exclusions.reason, supplier_exclusions.evidence_refs, supplier_exclusions.scope_location_id | SQL 6 baris, contoh `05dbb8ed-3f19-58ee-8b51-1448ae13f491` ; sppg_head 200/3 baris · bgn_monitor 200/6 baris | TERBUKTI |
| 26 | Agent Log | Status provider model | ya | Status provider model · Verifier · Forecast · Supervisor | fetchDecisionTraces | GET /decisions/{decision_id}/traces | agent_traces.step_name, agent_traces.output_summary, agent_traces.agent_name | SQL 26 baris, contoh `PREDICT` ; sppg_head 200/4 baris · bgn_monitor 200/4 baris | TERBUKTI |
| 27 | Agent Log | Jejak langkah agen (trace viewer) | ya | SUPERVISE | fetchDecisionTraces | GET /decisions/{decision_id}/traces | agent_traces.tool_called, agent_traces.duration_ms, agent_traces.input_summary, agent_traces.citations, agent_traces.run_id | SQL 106 baris, contoh `ACT` ; sppg_head 200/4 baris · bgn_monitor 200/4 baris | TERBUKTI |
| 28 | KPI & Kualitas Agen | KPI (jendela periode) | ya | Jendela periode KPI · Avoidable Food Loss · Procurement Price Deviation | fetchKpis | GET /kpi | delivery_events.delivered_portions, menu_plans.planned_portions, disposal_events.quantity_kg, decisions.safe_delivered_cost | SQL 290 baris, contoh `00ef6ba7-2a59-58fe-9281-cf47be633720` ; sppg_head 200/7 baris · bgn_monitor 200/7 baris | TERBUKTI |
| 29 | KPI & Kualitas Agen | Kualitas agen (sampel run) | ya | Kualitas Agen · Run dinilai · Rata-rata durasi · Tingkat fallback · Kesesuaian verifier | fetchDecisionTraces, fetchApprovalSummary | GET /decisions/{decision_id}/approval-summary<br>GET /decisions/{decision_id}/traces | agent_traces.step_name, agent_traces.duration_ms, agent_traces.output_summary, approvals.approved | SQL 106 baris, contoh `00fcf4f9-38bb-5057-a6e5-33d737e1391d` ; sppg_head 200/4 baris · bgn_monitor 200/4 baris | TERBUKTI |
| 30 | Pengaturan | Pengguna (admin) | ya | Memuat pengguna & lokasi… · Peran · Nama · Simpan | fetchAdminUsers, updateAdminUser | GET /admin/users<br>PATCH /admin/users/{user_id} | users.role, users.email, users.location_id, users.name | SQL 7 baris, contoh `bgn.monitor@demo.local` ; sppg_head 403/1 baris · bgn_monitor 200/7 baris | TERBUKTI |
| 31 | Pengaturan | Lokasi (admin) | ya | Wilayah · Koordinat · Lokasi | fetchAdminLocations, updateAdminLocation | GET /admin/locations<br>PATCH /admin/locations/{location_id} | locations.name, locations.region, locations.role_hint, locations.latitude, locations.longitude | SQL 10 baris, contoh `Bandung` ; sppg_head 403/1 baris · bgn_monitor 200/10 baris | TERBUKTI |
| 32 | Demo Control | Status data demo & sesi | ya | Demo Control · Siapkan data demo · Akhiri sesi · Perpanjang 30 menit | fetchDemoDataStatus, fetchDemoSession, fetchDemoPreview, startDemoSession, extendDemoSession, endDemoSession, refreshDemoToToday | GET /demo/data-status<br>GET /demo/preview<br>GET /demo/session<br>POST /demo/refresh<br>POST /demo/session/end<br>POST /demo/session/extend<br>POST /demo/session/start | demo_sessions.status, demo_sessions.expires_at, demo_sessions.anchor_now, batches.demo_session_id, decisions.demo_session_id | SQL 4 baris, contoh `active` ; sppg_head 200/1 baris · bgn_monitor 403/1 baris | TERBUKTI |
| 33 | Demo Control | Jalankan agent + log proses | ya | Jalankan agent · Log proses pengambilan data (terminal: langkah + sumber data) | fetchDemoAgentCommodities, fetchDemoAgentLastRun, runDemoAgent | GET /demo/agent/commodities<br>GET /demo/agent/last-run<br>POST /demo/agent/run | agent_traces.agent_name, agent_traces.step_name, decisions.demo_case, decisions.origin | SQL 19 baris, contoh `agent:allocation-optimizer` ; sppg_head 200/1 baris · bgn_monitor 403/1 baris | TERBUKTI |
| 34 | Global (di luar tab) | Login & identitas sesi | ya | Masuk ke konsol · Email · Password | login, fetchMe | GET /auth/me<br>POST /auth/login | users.email, users.password_hash, users.role, users.location_id | SQL 7 baris, contoh `bgn.monitor@demo.local` ; sppg_head 200/1 baris · bgn_monitor 200/1 baris | TERBUKTI |
| 35 | Global (di luar tab) | Top bar: notifikasi & cakupan lokasi | ya | Rekomendasi baru · Tidak ada keputusan menunggu tindakan · Pilih lokasi yang disorot di peta · Buka informasi notifikasi | fetchMe, fetchDecisions | GET /auth/me<br>GET /decisions | decisions.status, decisions.expires_at, users.location_id, locations.name | SQL 16 baris, contoh `0652c9bb-f35f-49d6-bda0-d3b87d350893` ; sppg_head 200/17 baris · bgn_monitor 200/47 baris | TERBUKTI |
| 36 | Global (di luar tab) | Status integrasi (panel tidak terpasang) | **tidak** | Bukti integrasi per komponen · Memuat status integrasi… | fetchIntegrationStatus | GET /integrations/status | — | tanpa tabel data (status dibaca dari env/artefak) ; sppg_head 200/7 baris · bgn_monitor 200/7 baris | DIPENSIUNKAN |

## 2. Peta layar → komponen → fungsi api

Bagian ini membuktikan tidak ada layar yang tertinggal: komponen tiap tab dibaca dari blok `{tab === "..." && (...)}` di `app/page.tsx`, lalu fungsi api-nya dilacak lewat komponen dan hook (`lib/hooks/*`).

| Layar | Komponen yang dirender | Fungsi api dipanggil langsung | Hook yang variabelnya dipakai | Fungsi api lewat hook |
|---|---|---|---|---|
| Hari Ini | TodayDashboard | — | useAgenda, useBalanceMap, useKpi, useToday | fetchAgenda, fetchBalanceMap, fetchBatches, fetchKpis, verifyLedger |
| Overview | NodeTelemetry, RoleHero, SectionJump, ShipmentCard, StatusBadge, StatusLocationList, SupplyAdequacyChart, SupplyBalanceChart, SupplyMap | — | useBalanceMap, useCommodityBalance, useDecisionDetail, useKpi, useMe, useSupplierRoutes, useSuppliers, useToday | fetchApprovalSummary, fetchBalanceMap, fetchBatches, fetchDecisionChain, fetchDecisionTraces, fetchKpis, fetchMe, fetchSupplierContext, fetchSupplierRoutes, fetchSuppliers, verifyLedger |
| Recommendations | PageHeader, Pager, RecommendationCard | — | useDecisions | fetchDecisions |
| Decision & Evidence | DecisionEvidence, PurchaseOrderList | — | useDecisionDetail, useDecisions, usePurchaseOrders | fetchApprovalSummary, fetchDecisionChain, fetchDecisionTraces, fetchDecisions, fetchPurchaseOrderSummary, fetchPurchaseOrders, fetchSupplierContext |
| Keamanan Pangan | FoodSafetyBoard | fetchPendingReceipts, fetchReceipts, recordReceipt | useBalanceMap, useMe, useSupplierRoutes, useToday | fetchBalanceMap, fetchBatches, fetchMe, fetchSupplierRoutes, verifyLedger |
| Surplus & Limbah | SurplusBoard | — | useBalanceMap, useSurplusPlan, useWasteSummary | fetchBalanceMap, fetchSurplusAllocations, fetchWasteSummary |
| Pemasok | SupplierBoard | — | useDecisionDetail, useDecisions, useExclusions, useSupplierRoutes, useSuppliers | fetchApprovalSummary, fetchDecisionChain, fetchDecisionTraces, fetchDecisions, fetchExclusions, fetchSupplierContext, fetchSupplierRoutes, fetchSuppliers |
| Agent Log | AgentSwarmPanel, AgentTraceViewer, DecisionPicker, PageHeader, ProviderPanel | — | useDecisionDetail | fetchApprovalSummary, fetchDecisionChain, fetchDecisionTraces, fetchSupplierContext |
| KPI & Kualitas Agen | KpiQualityBoard | — | useKpi, useQualitySample | fetchApprovalSummary, fetchDecisionTraces, fetchKpis |
| Pengaturan | SettingsPanel | fetchAdminLocations, fetchAdminUsers, updateAdminLocation, updateAdminUser | — | — |
| Demo Control | DemoControlPanel, PageHeader | endDemoSession, extendDemoSession, fetchDemoAgentCommodities, fetchDemoAgentLastRun, fetchDemoDataStatus, fetchDemoSession, rebuildDemoTemplate, refreshDemoToToday, runDemoAgent, startDemoSession | useMe | fetchMe |

Komponen yang **tidak terpasang** di layar mana pun (endpoint-nya tetap hidup): `ChaosPanel`, `DemoDataPanel`, `IntegrationStatusPanel`, `OpsConsole`, `StockChart`.

## 3. Inventaris enum & nilai status

Tiga sumber dibandingkan: kosakata **kode** (`Literal[...]`, tuple konstanta, union TypeScript), kosakata **skema** (`CHECK` constraint dari `pg_constraint`), dan nilai yang **benar-benar ada di data** (`select distinct`).

| Enum | Kolom | Nilai di kode | CHECK di DB | Nilai di data (n) | Warna StatusBadge | Sinkron? | Catatan |
|---|---|---|---|---|---|---|---|
| role user | `users.role` | `auth.py:MUTATING_ROLES`: sppg_head, sppg_nutritionist; `page.tsx:ROLE_LABEL`: bgn_monitor, sppg_head, sppg_nutritionist | sppg_head, sppg_nutritionist, bgn_monitor | bgn_monitor (1), sppg_head (3), sppg_nutritionist (3) | — | ya | — |
| decision_type | `decisions.decision_type` | `decisions.py:decision_type`: price_anomaly, regional_balance, safety_disruption, supplier_exclusion, supplier_exclusion_restoration, supplier_procurement; `RecommendationCard.tsx:DECISION_TYPE_LABELS`: price_anomaly, regional_balance, safety_disruption, supplier_exclusion, supplier_exclusion_restoration, supplier_procurement, surplus_redistribution | regional_balance, price_anomaly, safety_disruption, supplier_exclusion, supplier_exclusion_restoration, supplier_procurement | price_anomaly (7), regional_balance (19), safety_disruption (13), supplier_exclusion (3), supplier_exclusion_restoration (2), supplier_procurement (3) | — | **tidak** | — |
| status keputusan | `decisions.status` | — | proposed, verifier_flagged, pending_approval, approved, rejected, executed, review_only | approved (3), executed (9), pending_approval (16), proposed (2), rejected (10), review_only (2), verifier_flagged (5) | APPROVED, EXECUTED, FAIL, NEEDS_VERIFICATION, PASS, PENDING_APPROVAL, PROPOSED, REJECTED, SHORTAGE, SURPLUS, TIGHT, VERIFIER_FLAGGED | **tidak** | kode tidak punya enum; nilai ditulis tersebar sebagai string |
| safety_status batch | `batches.safety_status` | `quarantine.py:SAFETY_VALID`: fail, needs_verification, pass, pending; `safety.py:safety_status`: fail, needs_verification, pass | pending, pass, fail, needs_verification | fail (3), needs_verification (15), pass (102), pending (5) | APPROVED, EXECUTED, FAIL, NEEDS_VERIFICATION, PASS, PENDING_APPROVAL, PROPOSED, REJECTED, SHORTAGE, SURPLUS, TIGHT, VERIFIER_FLAGGED | ya | FoodSafetyBoard merender status ini sebagai teks, bukan StatusBadge |
| kesegaran (turunan freshness_score) | `batches.freshness_score` | `freshness.py:classify_freshness`: fail, needs_verification, pass | fail, needs_verification, pass | (NULL) (1), fail (4), needs_verification (42), pass (78) | — | ya | status turunan: pass / needs_verification / fail dari freshness_score |
| status penerimaan (receipt) | `batch_receipts.status` | — | menunggu, disetujui, ditolak | disetujui (1), ditolak (1), menunggu (5) | — | ya | default "menunggu" di api/receipts.py; status lain ditulis endpoint approve/reject |
| status eksklusi pemasok | `supplier_exclusions.status` | `supplier_exclusions.py:status`: active, proposed, rejected, revoked; `supplier-exclusions.ts:SupplierExclusion`: active, proposed, rejected, revoked | proposed, active, rejected, revoked | active (2), proposed (2), rejected (1), revoked (1) | — | ya | — |
| origin data | `batches.origin` | `timeseries.py:origin`: demo, seed | seed, demo | demo (47), seed (78) | — | ya | — |
| status PO (SAP mock) | `sap_mock_purchase_orders.status` | `sap_orders.py:status`: confirmed, draft, submitted | draft, submitted, confirmed | confirmed (15), draft (2), submitted (3) | — | ya | — |
| status pengiriman (delivery) | `delivery_events.status` | `kpi_facts.py:status`: delivered | **tidak ada CHECK** | delivered (290) | — | **tidak** | status hanya punya server_default; tidak ada CHECK maupun enum di kode |
| status karantina batch | `batches.quarantine_status` | — | none, quarantined, released, failed | failed (1), none (121), quarantined (2), released (1) | APPROVED, EXECUTED, FAIL, NEEDS_VERIFICATION, PASS, PENDING_APPROVAL, PROPOSED, REJECTED, SHORTAGE, SURPLUS, TIGHT, VERIFIER_FLAGGED | ya | input API memakai aksi tahan/lepas/gagal (Literal) yang dipetakan ke status ini |

### 3.1 Ketidaksinkronan kode vs skema vs data

| Enum | Jenis | Keterangan |
|---|---|---|
| decision_type | `kode_di_luar_skema` | kode memakai nilai di luar CHECK: surplus_redistribution — sumber: RecommendationCard.tsx:DECISION_TYPE_LABELS (surplus_redistribution) |
| status keputusan | `tanpa_warna` | StatusBadge tidak punya kelas warna (jatuh ke netral): review_only |
| status pengiriman (delivery) | `tanpa_check` | tidak ada CHECK constraint di DB |
| status pengiriman (delivery) | `kosakata_data` | kosakata hanya dari data: delivered |

Arti jenis: `kode_di_luar_skema` = kontrak kode menerima nilai yang ditolak DB (bug tulis); `skema_lebih_luas` = CHECK mengizinkan nilai yang tidak bisa dihasilkan kode (kontrak API lebih sempit dari skema); `belum_terbukti` = nilai sah yang belum punya satu baris pun di data demo; `data_di_luar_skema` = baris yang melanggar CHECK (tidak mungkin terjadi kecuali constraint dimatikan); `tanpa_check` = kolom status tanpa constraint sama sekali; `tanpa_warna` = `StatusBadge` tidak punya kelas warna sehingga nilai itu jatuh ke abu-abu netral.

## 4. Inventaris state tampilan per layar

State diuji dengan data nyata, bukan dengan membaca kode saja. `✓` = TERBUKTI (ada query/record yang membuktikannya), `GAP` = belum ada data demo yang bisa memicu state itu, `–` = tidak berlaku untuk baris tersebut (tidak punya tabel data / kolom terkait). Rincian bukti per sel ada di §4.2 untuk semua GAP, dan template query-nya di §6.

| Layar / bagian | kosong | satu_item | banyak_halaman | filter_tanpa_hasil | sort | error | loading | null_opsional | teks_panjang | angka_nol | angka_negatif | angka_besar | tanggal_lampau | tanggal_hari_ini | tanggal_masa_depan | unicode | format_lokal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Hari Ini — Tile status hari ini | GAP | ✓ | ✓ | GAP | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | ✓ | GAP |
| Hari Ini — Agenda harian | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | GAP | GAP |
| Hari Ini — Rantai audit (Merkle ledger) | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | ✓ | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Overview — Ringkasan peta pasokan (bento KPI) | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Overview — Peta kondisi komoditas | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Overview — Grafik kecukupan pasokan | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | GAP | GAP | ✓ |
| Overview — Grafik keseimbangan pasokan | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Overview — Kartu informasi pengiriman | GAP | GAP | ✓ | GAP | ✓ | ✓ | GAP | GAP | GAP | ✓ | – | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Overview — Telemetri node | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Recommendations — Feed rekomendasi + filter/sort + pager | GAP | ✓ | ✓ | GAP | ✓ | ✓ | GAP | ✓ | GAP | GAP | GAP | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Recommendations — Konsol operasi — snapshot kondisi | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Recommendations — Konsol operasi — analisis agent & usulan | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | – | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Recommendations — Panel anomali harga (Event 2) | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | – | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Decision & Evidence — Ringkasan keputusan & bukti | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | ✓ |
| Decision & Evidence — Jejak & riwayat persetujuan | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Decision & Evidence — Integritas bukti & dossier | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | ✓ | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Decision & Evidence — Daftar purchase order (SAP simulasi) | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | ✓ | GAP | – | – | GAP | ✓ | ✓ | GAP | GAP | ✓ |
| Keamanan Pangan — Papan batch & uji keamanan | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | ✓ | GAP | GAP |
| Keamanan Pangan — Penerimaan barang | ✓ | ✓ | GAP | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | ✓ | ✓ | GAP | ✓ | GAP |
| Keamanan Pangan — Karantina batch | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Surplus & Limbah — Rencana alokasi surplus | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Surplus & Limbah — Pencatatan limbah | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| Pemasok — Daftar pemasok + pencarian | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | – | GAP | ✓ | ✓ | GAP | GAP | ✓ |
| Pemasok — Jalur kiriman (jalan) | GAP | GAP | ✓ | GAP | ✓ | ✓ | ✓ | GAP | GAP | ✓ | – | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Pemasok — Supplier governance (eksklusi/pemulihan) | ✓ | ✓ | GAP | ✓ | ✓ | ✓ | GAP | ✓ | ✓ | GAP | GAP | GAP | ✓ | ✓ | GAP | ✓ | GAP |
| Agent Log — Status provider model | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Agent Log — Jejak langkah agen (trace viewer) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| KPI & Kualitas Agen — KPI (jendela periode) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | GAP | ✓ |
| KPI & Kualitas Agen — Kualitas agen (sampel run) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Pengaturan — Pengguna (admin) | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Pengaturan — Lokasi (admin) | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Demo Control — Status data demo & sesi | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | GAP | GAP |
| Demo Control — Jalankan agent + bukti pipeline | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Global (di luar tab) — Login & identitas sesi | GAP | GAP | GAP | GAP | ✓ | ✓ | ✓ | ✓ | GAP | GAP | GAP | GAP | ✓ | ✓ | GAP | GAP | GAP |
| Global (di luar tab) — Top bar: notifikasi & cakupan lokasi | GAP | ✓ | ✓ | GAP | ✓ | ✓ | GAP | ✓ | GAP | GAP | GAP | ✓ | ✓ | ✓ | ✓ | ✓ | GAP |
| Global (di luar tab) — Status integrasi (panel tidak terpasang) | – | – | – | – | – | ✓ | ✓ | – | – | – | – | – | – | – | – | – | GAP |

### 4.1 Arti tiap state

| State | Definisi operasional |
|---|---|
| `kosong` | Tidak ada baris sama sekali untuk satu kunci dimensi |
| `satu_item` | Tepat satu baris untuk satu kunci dimensi |
| `banyak_halaman` | Baris > ukuran halaman (pager benar-benar terpakai) |
| `filter_tanpa_hasil` | Filter pada dimensi yang tidak punya baris |
| `sort` | Kolom urut punya lebih dari satu nilai |
| `error` | Endpoint membalas 4xx untuk masukan tak sah |
| `loading` | Cabang memuat ada di komponen |
| `null_opsional` | Kolom opsional berisi NULL |
| `teks_panjang` | Ada nilai teks >= 80 karakter |
| `angka_nol` | Ada nilai numerik 0 |
| `angka_negatif` | Ada nilai numerik negatif |
| `angka_besar` | Ada nilai numerik >= 1.000.000 |
| `tanggal_lampau` | Ada tanggal sebelum sekarang |
| `tanggal_hari_ini` | Ada tanggal hari ini (WIB) |
| `tanggal_masa_depan` | Ada tanggal setelah sekarang |
| `unicode` | Ada teks non-ASCII (bahasa Indonesia/Unicode) |
| `format_lokal` | Formatter rupiah & tanggal lokal tersedia + ada nilai uang |

### 4.2 Bukti / alasan per state

| Layar / bagian | State | Status | Bukti / alasan |
|---|---|---|---|
| Tile status hari ini | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Tile status hari ini | `satu_item` | TERBUKTI | 6 kunci dimensi berisi tepat 1 baris |
| Tile status hari ini | `banyak_halaman` | TERBUKTI | 47 baris > 10/halaman |
| Tile status hari ini | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Tile status hari ini | `sort` | TERBUKTI | 7 nilai berbeda |
| Tile status hari ini | `error` | TERBUKTI | HTTP 401 pada /decisions?limit=abc |
| Tile status hari ini | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Tile status hari ini | `null_opsional` | TERBUKTI | 37 baris NULL |
| Tile status hari ini | `teks_panjang` | GAP | panjang maks 63 karakter |
| Tile status hari ini | `angka_nol` | GAP | tidak ada nilai 0 |
| Tile status hari ini | `angka_negatif` | GAP | tidak ada nilai negatif |
| Tile status hari ini | `angka_besar` | GAP | maks 0 |
| Tile status hari ini | `tanggal_lampau` | TERBUKTI | 9 baris |
| Tile status hari ini | `tanggal_hari_ini` | TERBUKTI | 28 baris |
| Tile status hari ini | `tanggal_masa_depan` | TERBUKTI | 38 baris |
| Tile status hari ini | `unicode` | TERBUKTI | 9 baris non-ASCII |
| Tile status hari ini | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Agenda harian | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Agenda harian | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Agenda harian | `banyak_halaman` | TERBUKTI | 660 baris > 10/halaman |
| Agenda harian | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Agenda harian | `sort` | TERBUKTI | 66 nilai berbeda |
| Agenda harian | `error` | TERBUKTI | HTTP 401 pada /agenda (tanpa parameter query) |
| Agenda harian | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Agenda harian | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Agenda harian | `teks_panjang` | GAP | panjang maks 0 karakter |
| Agenda harian | `angka_nol` | GAP | tidak ada nilai 0 |
| Agenda harian | `angka_negatif` | GAP | tidak ada nilai negatif |
| Agenda harian | `angka_besar` | GAP | maks 1224 |
| Agenda harian | `tanggal_lampau` | TERBUKTI | 520 baris |
| Agenda harian | `tanggal_hari_ini` | TERBUKTI | 10 baris |
| Agenda harian | `tanggal_masa_depan` | TERBUKTI | 140 baris |
| Agenda harian | `unicode` | GAP | teks hanya ASCII |
| Agenda harian | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Rantai audit (Merkle ledger) | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Rantai audit (Merkle ledger) | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Rantai audit (Merkle ledger) | `banyak_halaman` | TERBUKTI | 72 baris > 20/halaman |
| Rantai audit (Merkle ledger) | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Rantai audit (Merkle ledger) | `sort` | TERBUKTI | 72 nilai berbeda |
| Rantai audit (Merkle ledger) | `error` | TERBUKTI | HTTP 401 pada /ledger/verify?limit=abc |
| Rantai audit (Merkle ledger) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Rantai audit (Merkle ledger) | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Rantai audit (Merkle ledger) | `teks_panjang` | TERBUKTI | panjang maks 135 karakter |
| Rantai audit (Merkle ledger) | `angka_nol` | GAP | tidak ada nilai 0 |
| Rantai audit (Merkle ledger) | `angka_negatif` | GAP | tidak ada nilai negatif |
| Rantai audit (Merkle ledger) | `angka_besar` | GAP | maks 0 |
| Rantai audit (Merkle ledger) | `tanggal_lampau` | TERBUKTI | 72 baris |
| Rantai audit (Merkle ledger) | `tanggal_hari_ini` | TERBUKTI | 72 baris |
| Rantai audit (Merkle ledger) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Rantai audit (Merkle ledger) | `unicode` | GAP | teks hanya ASCII |
| Rantai audit (Merkle ledger) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Ringkasan peta pasokan (bento KPI) | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Ringkasan peta pasokan (bento KPI) | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Ringkasan peta pasokan (bento KPI) | `banyak_halaman` | TERBUKTI | 5240 baris > 10/halaman |
| Ringkasan peta pasokan (bento KPI) | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Ringkasan peta pasokan (bento KPI) | `sort` | TERBUKTI | 5012 nilai berbeda |
| Ringkasan peta pasokan (bento KPI) | `error` | TERBUKTI | HTTP 401 pada /balance/map (tanpa parameter query) |
| Ringkasan peta pasokan (bento KPI) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Ringkasan peta pasokan (bento KPI) | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Ringkasan peta pasokan (bento KPI) | `teks_panjang` | GAP | panjang maks 8 karakter |
| Ringkasan peta pasokan (bento KPI) | `angka_nol` | GAP | tidak ada nilai 0 |
| Ringkasan peta pasokan (bento KPI) | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Ringkasan peta pasokan (bento KPI) | `angka_besar` | GAP | maks 2543.77 |
| Ringkasan peta pasokan (bento KPI) | `tanggal_lampau` | TERBUKTI | 4160 baris |
| Ringkasan peta pasokan (bento KPI) | `tanggal_hari_ini` | TERBUKTI | 120 baris |
| Ringkasan peta pasokan (bento KPI) | `tanggal_masa_depan` | TERBUKTI | 1080 baris |
| Ringkasan peta pasokan (bento KPI) | `unicode` | GAP | teks hanya ASCII |
| Ringkasan peta pasokan (bento KPI) | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Peta kondisi komoditas | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Peta kondisi komoditas | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Peta kondisi komoditas | `banyak_halaman` | TERBUKTI | 5240 baris > 10/halaman |
| Peta kondisi komoditas | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Peta kondisi komoditas | `sort` | TERBUKTI | 5012 nilai berbeda |
| Peta kondisi komoditas | `error` | TERBUKTI | HTTP 401 pada /balance/map (tanpa parameter query) |
| Peta kondisi komoditas | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Peta kondisi komoditas | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Peta kondisi komoditas | `teks_panjang` | GAP | panjang maks 8 karakter |
| Peta kondisi komoditas | `angka_nol` | GAP | tidak ada nilai 0 |
| Peta kondisi komoditas | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Peta kondisi komoditas | `angka_besar` | GAP | maks 2543.77 |
| Peta kondisi komoditas | `tanggal_lampau` | TERBUKTI | 4160 baris |
| Peta kondisi komoditas | `tanggal_hari_ini` | TERBUKTI | 120 baris |
| Peta kondisi komoditas | `tanggal_masa_depan` | TERBUKTI | 1080 baris |
| Peta kondisi komoditas | `unicode` | GAP | teks hanya ASCII |
| Peta kondisi komoditas | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Grafik kecukupan pasokan | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Grafik kecukupan pasokan | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Grafik kecukupan pasokan | `banyak_halaman` | TERBUKTI | 125 baris > 10/halaman |
| Grafik kecukupan pasokan | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Grafik kecukupan pasokan | `sort` | TERBUKTI | 12 nilai berbeda |
| Grafik kecukupan pasokan | `error` | TERBUKTI | HTTP 401 pada /balance/map (tanpa parameter query) |
| Grafik kecukupan pasokan | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Grafik kecukupan pasokan | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Grafik kecukupan pasokan | `teks_panjang` | GAP | panjang maks 7 karakter |
| Grafik kecukupan pasokan | `angka_nol` | GAP | tidak ada nilai 0 |
| Grafik kecukupan pasokan | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Grafik kecukupan pasokan | `angka_besar` | GAP | maks 0.98 |
| Grafik kecukupan pasokan | `tanggal_lampau` | TERBUKTI | 125 baris |
| Grafik kecukupan pasokan | `tanggal_hari_ini` | TERBUKTI | 13 baris |
| Grafik kecukupan pasokan | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Grafik kecukupan pasokan | `unicode` | GAP | teks hanya ASCII |
| Grafik kecukupan pasokan | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Grafik keseimbangan pasokan | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Grafik keseimbangan pasokan | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Grafik keseimbangan pasokan | `banyak_halaman` | TERBUKTI | 1360 baris > 10/halaman |
| Grafik keseimbangan pasokan | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Grafik keseimbangan pasokan | `sort` | TERBUKTI | 1236 nilai berbeda |
| Grafik keseimbangan pasokan | `error` | TERBUKTI | HTTP 401 pada /balance/map (tanpa parameter query) |
| Grafik keseimbangan pasokan | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Grafik keseimbangan pasokan | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Grafik keseimbangan pasokan | `teks_panjang` | GAP | panjang maks 0 karakter |
| Grafik keseimbangan pasokan | `angka_nol` | GAP | tidak ada nilai 0 |
| Grafik keseimbangan pasokan | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Grafik keseimbangan pasokan | `angka_besar` | GAP | maks 3061.42 |
| Grafik keseimbangan pasokan | `tanggal_lampau` | TERBUKTI | 440 baris |
| Grafik keseimbangan pasokan | `tanggal_hari_ini` | TERBUKTI | 40 baris |
| Grafik keseimbangan pasokan | `tanggal_masa_depan` | TERBUKTI | 920 baris |
| Grafik keseimbangan pasokan | `unicode` | GAP | teks hanya ASCII |
| Grafik keseimbangan pasokan | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Kartu informasi pengiriman | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Kartu informasi pengiriman | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Kartu informasi pengiriman | `banyak_halaman` | TERBUKTI | 51 baris > 20/halaman |
| Kartu informasi pengiriman | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Kartu informasi pengiriman | `sort` | TERBUKTI | 42 nilai berbeda |
| Kartu informasi pengiriman | `error` | TERBUKTI | HTTP 401 pada /supplier-routes (tanpa parameter query) |
| Kartu informasi pengiriman | `loading` | GAP | komponen tanpa cabang memuat |
| Kartu informasi pengiriman | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Kartu informasi pengiriman | `teks_panjang` | GAP | panjang maks 41 karakter |
| Kartu informasi pengiriman | `angka_nol` | TERBUKTI | 10 baris bernilai 0 |
| Kartu informasi pengiriman | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Kartu informasi pengiriman | `angka_besar` | GAP | maks 6653 |
| Kartu informasi pengiriman | `tanggal_lampau` | TERBUKTI | 51 baris |
| Kartu informasi pengiriman | `tanggal_hari_ini` | TERBUKTI | 51 baris |
| Kartu informasi pengiriman | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Kartu informasi pengiriman | `unicode` | GAP | teks hanya ASCII |
| Kartu informasi pengiriman | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Telemetri node | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Telemetri node | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Telemetri node | `banyak_halaman` | TERBUKTI | 5240 baris > 10/halaman |
| Telemetri node | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Telemetri node | `sort` | TERBUKTI | 5012 nilai berbeda |
| Telemetri node | `error` | TERBUKTI | HTTP 401 pada /balance/map (tanpa parameter query) |
| Telemetri node | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Telemetri node | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Telemetri node | `teks_panjang` | GAP | panjang maks 8 karakter |
| Telemetri node | `angka_nol` | GAP | tidak ada nilai 0 |
| Telemetri node | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Telemetri node | `angka_besar` | GAP | maks 2543.77 |
| Telemetri node | `tanggal_lampau` | TERBUKTI | 4160 baris |
| Telemetri node | `tanggal_hari_ini` | TERBUKTI | 120 baris |
| Telemetri node | `tanggal_masa_depan` | TERBUKTI | 1080 baris |
| Telemetri node | `unicode` | GAP | teks hanya ASCII |
| Telemetri node | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Feed rekomendasi + filter/sort + pager | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Feed rekomendasi + filter/sort + pager | `satu_item` | TERBUKTI | 6 kunci dimensi berisi tepat 1 baris |
| Feed rekomendasi + filter/sort + pager | `banyak_halaman` | TERBUKTI | 47 baris > 10/halaman |
| Feed rekomendasi + filter/sort + pager | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Feed rekomendasi + filter/sort + pager | `sort` | TERBUKTI | 22 nilai berbeda |
| Feed rekomendasi + filter/sort + pager | `error` | TERBUKTI | HTTP 401 pada /decisions (tanpa parameter query) |
| Feed rekomendasi + filter/sort + pager | `loading` | GAP | komponen tanpa cabang memuat |
| Feed rekomendasi + filter/sort + pager | `null_opsional` | TERBUKTI | 37 baris NULL |
| Feed rekomendasi + filter/sort + pager | `teks_panjang` | GAP | panjang maks 63 karakter |
| Feed rekomendasi + filter/sort + pager | `angka_nol` | GAP | tidak ada nilai 0 |
| Feed rekomendasi + filter/sort + pager | `angka_negatif` | GAP | tidak ada nilai negatif |
| Feed rekomendasi + filter/sort + pager | `angka_besar` | TERBUKTI | maks 28775093.86 |
| Feed rekomendasi + filter/sort + pager | `tanggal_lampau` | TERBUKTI | 9 baris |
| Feed rekomendasi + filter/sort + pager | `tanggal_hari_ini` | TERBUKTI | 28 baris |
| Feed rekomendasi + filter/sort + pager | `tanggal_masa_depan` | TERBUKTI | 38 baris |
| Feed rekomendasi + filter/sort + pager | `unicode` | TERBUKTI | 9 baris non-ASCII |
| Feed rekomendasi + filter/sort + pager | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Konsol operasi — snapshot kondisi | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Konsol operasi — snapshot kondisi | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Konsol operasi — snapshot kondisi | `banyak_halaman` | TERBUKTI | 5240 baris > 10/halaman |
| Konsol operasi — snapshot kondisi | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Konsol operasi — snapshot kondisi | `sort` | TERBUKTI | 5012 nilai berbeda |
| Konsol operasi — snapshot kondisi | `error` | TERBUKTI | HTTP 401 pada /balance/00000000-0000-0000-0000-000000000000/telur |
| Konsol operasi — snapshot kondisi | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Konsol operasi — snapshot kondisi | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Konsol operasi — snapshot kondisi | `teks_panjang` | GAP | panjang maks 8 karakter |
| Konsol operasi — snapshot kondisi | `angka_nol` | GAP | tidak ada nilai 0 |
| Konsol operasi — snapshot kondisi | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Konsol operasi — snapshot kondisi | `angka_besar` | GAP | maks 2543.77 |
| Konsol operasi — snapshot kondisi | `tanggal_lampau` | TERBUKTI | 4160 baris |
| Konsol operasi — snapshot kondisi | `tanggal_hari_ini` | TERBUKTI | 120 baris |
| Konsol operasi — snapshot kondisi | `tanggal_masa_depan` | TERBUKTI | 1080 baris |
| Konsol operasi — snapshot kondisi | `unicode` | GAP | teks hanya ASCII |
| Konsol operasi — snapshot kondisi | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Konsol operasi — analisis agent & usulan | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Konsol operasi — analisis agent & usulan | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Konsol operasi — analisis agent & usulan | `banyak_halaman` | TERBUKTI | 6015 baris > 10/halaman |
| Konsol operasi — analisis agent & usulan | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Konsol operasi — analisis agent & usulan | `sort` | TERBUKTI | 5963 nilai berbeda |
| Konsol operasi — analisis agent & usulan | `error` | TERBUKTI | HTTP 401 pada /balance/analyze?limit=abc |
| Konsol operasi — analisis agent & usulan | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Konsol operasi — analisis agent & usulan | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Konsol operasi — analisis agent & usulan | `teks_panjang` | GAP | panjang maks 15 karakter |
| Konsol operasi — analisis agent & usulan | `angka_nol` | N/A | skema mewajibkan > 0 (CHECK) |
| Konsol operasi — analisis agent & usulan | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Konsol operasi — analisis agent & usulan | `angka_besar` | GAP | maks 87500.00 |
| Konsol operasi — analisis agent & usulan | `tanggal_lampau` | TERBUKTI | 4797 baris |
| Konsol operasi — analisis agent & usulan | `tanggal_hari_ini` | TERBUKTI | 205 baris |
| Konsol operasi — analisis agent & usulan | `tanggal_masa_depan` | TERBUKTI | 1218 baris |
| Konsol operasi — analisis agent & usulan | `unicode` | GAP | teks hanya ASCII |
| Konsol operasi — analisis agent & usulan | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Panel anomali harga (Event 2) | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Panel anomali harga (Event 2) | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Panel anomali harga (Event 2) | `banyak_halaman` | TERBUKTI | 6015 baris > 10/halaman |
| Panel anomali harga (Event 2) | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Panel anomali harga (Event 2) | `sort` | TERBUKTI | 5963 nilai berbeda |
| Panel anomali harga (Event 2) | `error` | TERBUKTI | HTTP 401 pada /price/quotes/00000000-0000-0000-0000-000000000000/telur |
| Panel anomali harga (Event 2) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Panel anomali harga (Event 2) | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Panel anomali harga (Event 2) | `teks_panjang` | GAP | panjang maks 15 karakter |
| Panel anomali harga (Event 2) | `angka_nol` | N/A | skema mewajibkan > 0 (CHECK) |
| Panel anomali harga (Event 2) | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Panel anomali harga (Event 2) | `angka_besar` | GAP | maks 87500.00 |
| Panel anomali harga (Event 2) | `tanggal_lampau` | TERBUKTI | 4797 baris |
| Panel anomali harga (Event 2) | `tanggal_hari_ini` | TERBUKTI | 205 baris |
| Panel anomali harga (Event 2) | `tanggal_masa_depan` | TERBUKTI | 1218 baris |
| Panel anomali harga (Event 2) | `unicode` | GAP | teks hanya ASCII |
| Panel anomali harga (Event 2) | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Ringkasan keputusan & bukti | `kosong` | TERBUKTI | 17 kunci dimensi tanpa baris |
| Ringkasan keputusan & bukti | `satu_item` | TERBUKTI | 26 kunci dimensi berisi tepat 1 baris |
| Ringkasan keputusan & bukti | `banyak_halaman` | TERBUKTI | 46 baris > 10/halaman |
| Ringkasan keputusan & bukti | `filter_tanpa_hasil` | TERBUKTI | 17 kunci dimensi tanpa baris |
| Ringkasan keputusan & bukti | `sort` | TERBUKTI | 6 nilai berbeda |
| Ringkasan keputusan & bukti | `error` | TERBUKTI | HTTP 401 pada /decisions/00000000-0000-0000-0000-000000000000 |
| Ringkasan keputusan & bukti | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Ringkasan keputusan & bukti | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Ringkasan keputusan & bukti | `teks_panjang` | GAP | panjang maks 18 karakter |
| Ringkasan keputusan & bukti | `angka_nol` | GAP | tidak ada nilai 0 |
| Ringkasan keputusan & bukti | `angka_negatif` | GAP | tidak ada nilai negatif |
| Ringkasan keputusan & bukti | `angka_besar` | GAP | maks 0 |
| Ringkasan keputusan & bukti | `tanggal_lampau` | TERBUKTI | 46 baris |
| Ringkasan keputusan & bukti | `tanggal_hari_ini` | TERBUKTI | 45 baris |
| Ringkasan keputusan & bukti | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Ringkasan keputusan & bukti | `unicode` | GAP | teks hanya ASCII |
| Ringkasan keputusan & bukti | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Jejak & riwayat persetujuan | `kosong` | TERBUKTI | 34 kunci dimensi tanpa baris |
| Jejak & riwayat persetujuan | `satu_item` | TERBUKTI | 7 kunci dimensi berisi tepat 1 baris |
| Jejak & riwayat persetujuan | `banyak_halaman` | TERBUKTI | 19 baris > 10/halaman |
| Jejak & riwayat persetujuan | `filter_tanpa_hasil` | TERBUKTI | 34 kunci dimensi tanpa baris |
| Jejak & riwayat persetujuan | `sort` | TERBUKTI | 9 nilai berbeda |
| Jejak & riwayat persetujuan | `error` | TERBUKTI | HTTP 401 pada /decisions/00000000-0000-0000-0000-000000000000/chain |
| Jejak & riwayat persetujuan | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Jejak & riwayat persetujuan | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Jejak & riwayat persetujuan | `teks_panjang` | GAP | panjang maks 68 karakter |
| Jejak & riwayat persetujuan | `angka_nol` | GAP | tidak ada nilai 0 |
| Jejak & riwayat persetujuan | `angka_negatif` | GAP | tidak ada nilai negatif |
| Jejak & riwayat persetujuan | `angka_besar` | GAP | maks 0 |
| Jejak & riwayat persetujuan | `tanggal_lampau` | TERBUKTI | 19 baris |
| Jejak & riwayat persetujuan | `tanggal_hari_ini` | TERBUKTI | 15 baris |
| Jejak & riwayat persetujuan | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Jejak & riwayat persetujuan | `unicode` | GAP | teks hanya ASCII |
| Jejak & riwayat persetujuan | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Integritas bukti & dossier | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Integritas bukti & dossier | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Integritas bukti & dossier | `banyak_halaman` | TERBUKTI | 72 baris > 20/halaman |
| Integritas bukti & dossier | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Integritas bukti & dossier | `sort` | TERBUKTI | 72 nilai berbeda |
| Integritas bukti & dossier | `error` | TERBUKTI | HTTP 401 pada /decisions/00000000-0000-0000-0000-000000000000/dossier |
| Integritas bukti & dossier | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Integritas bukti & dossier | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Integritas bukti & dossier | `teks_panjang` | TERBUKTI | panjang maks 135 karakter |
| Integritas bukti & dossier | `angka_nol` | GAP | tidak ada nilai 0 |
| Integritas bukti & dossier | `angka_negatif` | GAP | tidak ada nilai negatif |
| Integritas bukti & dossier | `angka_besar` | GAP | maks 0 |
| Integritas bukti & dossier | `tanggal_lampau` | TERBUKTI | 72 baris |
| Integritas bukti & dossier | `tanggal_hari_ini` | TERBUKTI | 72 baris |
| Integritas bukti & dossier | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Integritas bukti & dossier | `unicode` | GAP | teks hanya ASCII |
| Integritas bukti & dossier | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Daftar purchase order (SAP simulasi) | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Daftar purchase order (SAP simulasi) | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Daftar purchase order (SAP simulasi) | `banyak_halaman` | TERBUKTI | 20 baris > 10/halaman |
| Daftar purchase order (SAP simulasi) | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Daftar purchase order (SAP simulasi) | `sort` | TERBUKTI | 20 nilai berbeda |
| Daftar purchase order (SAP simulasi) | `error` | TERBUKTI | HTTP 401 pada /sap/purchase-orders?limit=abc |
| Daftar purchase order (SAP simulasi) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Daftar purchase order (SAP simulasi) | `null_opsional` | TERBUKTI | 13 baris NULL |
| Daftar purchase order (SAP simulasi) | `teks_panjang` | GAP | panjang maks 15 karakter |
| Daftar purchase order (SAP simulasi) | `angka_nol` | N/A | skema mewajibkan > 0 (CHECK) |
| Daftar purchase order (SAP simulasi) | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Daftar purchase order (SAP simulasi) | `angka_besar` | GAP | maks 999999.99 |
| Daftar purchase order (SAP simulasi) | `tanggal_lampau` | TERBUKTI | 20 baris |
| Daftar purchase order (SAP simulasi) | `tanggal_hari_ini` | TERBUKTI | 20 baris |
| Daftar purchase order (SAP simulasi) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Daftar purchase order (SAP simulasi) | `unicode` | GAP | teks hanya ASCII |
| Daftar purchase order (SAP simulasi) | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Papan batch & uji keamanan | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Papan batch & uji keamanan | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Papan batch & uji keamanan | `banyak_halaman` | TERBUKTI | 125 baris > 10/halaman |
| Papan batch & uji keamanan | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Papan batch & uji keamanan | `sort` | TERBUKTI | 12 nilai berbeda |
| Papan batch & uji keamanan | `error` | TERBUKTI | HTTP 401 pada /batches (tanpa parameter query) |
| Papan batch & uji keamanan | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Papan batch & uji keamanan | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Papan batch & uji keamanan | `teks_panjang` | GAP | panjang maks 55 karakter |
| Papan batch & uji keamanan | `angka_nol` | GAP | tidak ada nilai 0 |
| Papan batch & uji keamanan | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Papan batch & uji keamanan | `angka_besar` | GAP | maks 0.98 |
| Papan batch & uji keamanan | `tanggal_lampau` | TERBUKTI | 1 baris |
| Papan batch & uji keamanan | `tanggal_hari_ini` | TERBUKTI | 1 baris |
| Papan batch & uji keamanan | `tanggal_masa_depan` | TERBUKTI | 124 baris |
| Papan batch & uji keamanan | `unicode` | GAP | teks hanya ASCII |
| Papan batch & uji keamanan | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Penerimaan barang | `kosong` | TERBUKTI | 119 kunci dimensi tanpa baris |
| Penerimaan barang | `satu_item` | TERBUKTI | 5 kunci dimensi berisi tepat 1 baris |
| Penerimaan barang | `banyak_halaman` | GAP | 7 baris <= 10/halaman |
| Penerimaan barang | `filter_tanpa_hasil` | TERBUKTI | 119 kunci dimensi tanpa baris |
| Penerimaan barang | `sort` | TERBUKTI | 3 nilai berbeda |
| Penerimaan barang | `error` | TERBUKTI | HTTP 401 pada /receipts/menunggu?limit=abc |
| Penerimaan barang | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Penerimaan barang | `null_opsional` | TERBUKTI | 5 baris NULL |
| Penerimaan barang | `teks_panjang` | TERBUKTI | panjang maks 301 karakter |
| Penerimaan barang | `angka_nol` | GAP | tidak ada nilai 0 |
| Penerimaan barang | `angka_negatif` | GAP | tidak ada nilai negatif |
| Penerimaan barang | `angka_besar` | GAP | maks 0 |
| Penerimaan barang | `tanggal_lampau` | TERBUKTI | 7 baris |
| Penerimaan barang | `tanggal_hari_ini` | TERBUKTI | 7 baris |
| Penerimaan barang | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Penerimaan barang | `unicode` | TERBUKTI | 1 baris non-ASCII |
| Penerimaan barang | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Karantina batch | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Karantina batch | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Karantina batch | `banyak_halaman` | TERBUKTI | 125 baris > 10/halaman |
| Karantina batch | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Karantina batch | `sort` | TERBUKTI | 4 nilai berbeda |
| Karantina batch | `error` | TERBUKTI | HTTP 401 pada /batches (tanpa parameter query) |
| Karantina batch | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Karantina batch | `null_opsional` | TERBUKTI | 121 baris NULL |
| Karantina batch | `teks_panjang` | GAP | panjang maks 55 karakter |
| Karantina batch | `angka_nol` | GAP | tidak ada nilai 0 |
| Karantina batch | `angka_negatif` | GAP | tidak ada nilai negatif |
| Karantina batch | `angka_besar` | GAP | maks 0 |
| Karantina batch | `tanggal_lampau` | TERBUKTI | 4 baris |
| Karantina batch | `tanggal_hari_ini` | TERBUKTI | 4 baris |
| Karantina batch | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Karantina batch | `unicode` | GAP | teks hanya ASCII |
| Karantina batch | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Rencana alokasi surplus | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Rencana alokasi surplus | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Rencana alokasi surplus | `banyak_halaman` | TERBUKTI | 5240 baris > 10/halaman |
| Rencana alokasi surplus | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Rencana alokasi surplus | `sort` | TERBUKTI | 5012 nilai berbeda |
| Rencana alokasi surplus | `error` | TERBUKTI | HTTP 401 pada /surplus/allocations (tanpa parameter query) |
| Rencana alokasi surplus | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Rencana alokasi surplus | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Rencana alokasi surplus | `teks_panjang` | GAP | panjang maks 8 karakter |
| Rencana alokasi surplus | `angka_nol` | GAP | tidak ada nilai 0 |
| Rencana alokasi surplus | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Rencana alokasi surplus | `angka_besar` | GAP | maks 2543.77 |
| Rencana alokasi surplus | `tanggal_lampau` | TERBUKTI | 4160 baris |
| Rencana alokasi surplus | `tanggal_hari_ini` | TERBUKTI | 120 baris |
| Rencana alokasi surplus | `tanggal_masa_depan` | TERBUKTI | 1080 baris |
| Rencana alokasi surplus | `unicode` | GAP | teks hanya ASCII |
| Rencana alokasi surplus | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Pencatatan limbah | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Pencatatan limbah | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Pencatatan limbah | `banyak_halaman` | TERBUKTI | 83 baris > 10/halaman |
| Pencatatan limbah | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Pencatatan limbah | `sort` | TERBUKTI | 63 nilai berbeda |
| Pencatatan limbah | `error` | TERBUKTI | HTTP 401 pada /waste/summary (tanpa parameter query) |
| Pencatatan limbah | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Pencatatan limbah | `null_opsional` | TERBUKTI | 80 baris NULL |
| Pencatatan limbah | `teks_panjang` | GAP | panjang maks 24 karakter |
| Pencatatan limbah | `angka_nol` | GAP | tidak ada nilai 0 |
| Pencatatan limbah | `angka_negatif` | GAP | tidak ada nilai negatif |
| Pencatatan limbah | `angka_besar` | GAP | maks 26.50 |
| Pencatatan limbah | `tanggal_lampau` | TERBUKTI | 53 baris |
| Pencatatan limbah | `tanggal_hari_ini` | TERBUKTI | 7 baris |
| Pencatatan limbah | `tanggal_masa_depan` | TERBUKTI | 30 baris |
| Pencatatan limbah | `unicode` | GAP | teks hanya ASCII |
| Pencatatan limbah | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Daftar pemasok + pencarian | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Daftar pemasok + pencarian | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Daftar pemasok + pencarian | `banyak_halaman` | TERBUKTI | 61 baris > 10/halaman |
| Daftar pemasok + pencarian | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Daftar pemasok + pencarian | `sort` | TERBUKTI | 25 nilai berbeda |
| Daftar pemasok + pencarian | `error` | TERBUKTI | HTTP 401 pada /suppliers (tanpa parameter query) |
| Daftar pemasok + pencarian | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Daftar pemasok + pencarian | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Daftar pemasok + pencarian | `teks_panjang` | GAP | panjang maks 47 karakter |
| Daftar pemasok + pencarian | `angka_nol` | GAP | tidak ada nilai 0 |
| Daftar pemasok + pencarian | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Daftar pemasok + pencarian | `angka_besar` | GAP | maks 0.95 |
| Daftar pemasok + pencarian | `tanggal_lampau` | TERBUKTI | 61 baris |
| Daftar pemasok + pencarian | `tanggal_hari_ini` | TERBUKTI | 61 baris |
| Daftar pemasok + pencarian | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Daftar pemasok + pencarian | `unicode` | GAP | teks hanya ASCII |
| Daftar pemasok + pencarian | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Jalur kiriman (jalan) | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Jalur kiriman (jalan) | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Jalur kiriman (jalan) | `banyak_halaman` | TERBUKTI | 51 baris > 20/halaman |
| Jalur kiriman (jalan) | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Jalur kiriman (jalan) | `sort` | TERBUKTI | 42 nilai berbeda |
| Jalur kiriman (jalan) | `error` | TERBUKTI | HTTP 401 pada /supplier-routes (tanpa parameter query) |
| Jalur kiriman (jalan) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Jalur kiriman (jalan) | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Jalur kiriman (jalan) | `teks_panjang` | GAP | panjang maks 41 karakter |
| Jalur kiriman (jalan) | `angka_nol` | TERBUKTI | 10 baris bernilai 0 |
| Jalur kiriman (jalan) | `angka_negatif` | N/A | skema melarang nilai negatif (CHECK >= 0) |
| Jalur kiriman (jalan) | `angka_besar` | GAP | maks 6653 |
| Jalur kiriman (jalan) | `tanggal_lampau` | TERBUKTI | 51 baris |
| Jalur kiriman (jalan) | `tanggal_hari_ini` | TERBUKTI | 51 baris |
| Jalur kiriman (jalan) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Jalur kiriman (jalan) | `unicode` | GAP | teks hanya ASCII |
| Jalur kiriman (jalan) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Supplier governance (eksklusi/pemulihan) | `kosong` | TERBUKTI | 6 kunci dimensi tanpa baris |
| Supplier governance (eksklusi/pemulihan) | `satu_item` | TERBUKTI | 3 kunci dimensi berisi tepat 1 baris |
| Supplier governance (eksklusi/pemulihan) | `banyak_halaman` | GAP | 6 baris <= 10/halaman |
| Supplier governance (eksklusi/pemulihan) | `filter_tanpa_hasil` | TERBUKTI | 6 kunci dimensi tanpa baris |
| Supplier governance (eksklusi/pemulihan) | `sort` | TERBUKTI | 4 nilai berbeda |
| Supplier governance (eksklusi/pemulihan) | `error` | TERBUKTI | HTTP 401 pada /supplier-exclusions?limit=abc |
| Supplier governance (eksklusi/pemulihan) | `loading` | GAP | komponen tanpa cabang memuat |
| Supplier governance (eksklusi/pemulihan) | `null_opsional` | TERBUKTI | 5 baris NULL |
| Supplier governance (eksklusi/pemulihan) | `teks_panjang` | TERBUKTI | panjang maks 301 karakter |
| Supplier governance (eksklusi/pemulihan) | `angka_nol` | GAP | tidak ada nilai 0 |
| Supplier governance (eksklusi/pemulihan) | `angka_negatif` | GAP | tidak ada nilai negatif |
| Supplier governance (eksklusi/pemulihan) | `angka_besar` | GAP | maks 0 |
| Supplier governance (eksklusi/pemulihan) | `tanggal_lampau` | TERBUKTI | 6 baris |
| Supplier governance (eksklusi/pemulihan) | `tanggal_hari_ini` | TERBUKTI | 1 baris |
| Supplier governance (eksklusi/pemulihan) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Supplier governance (eksklusi/pemulihan) | `unicode` | TERBUKTI | 1 baris non-ASCII |
| Supplier governance (eksklusi/pemulihan) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Status provider model | `kosong` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Status provider model | `satu_item` | TERBUKTI | 3 kunci dimensi berisi tepat 1 baris |
| Status provider model | `banyak_halaman` | TERBUKTI | 106 baris > 10/halaman |
| Status provider model | `filter_tanpa_hasil` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Status provider model | `sort` | TERBUKTI | 8 nilai berbeda |
| Status provider model | `error` | TERBUKTI | HTTP 401 pada /decisions/00000000-0000-0000-0000-000000000000/traces |
| Status provider model | `loading` | GAP | komponen tanpa cabang memuat |
| Status provider model | `null_opsional` | TERBUKTI | 82 baris NULL |
| Status provider model | `teks_panjang` | GAP | panjang maks 24 karakter |
| Status provider model | `angka_nol` | GAP | tidak ada nilai 0 |
| Status provider model | `angka_negatif` | GAP | tidak ada nilai negatif |
| Status provider model | `angka_besar` | GAP | maks 1600 |
| Status provider model | `tanggal_lampau` | TERBUKTI | 106 baris |
| Status provider model | `tanggal_hari_ini` | TERBUKTI | 103 baris |
| Status provider model | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Status provider model | `unicode` | GAP | teks hanya ASCII |
| Status provider model | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Jejak langkah agen (trace viewer) | `kosong` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Jejak langkah agen (trace viewer) | `satu_item` | TERBUKTI | 3 kunci dimensi berisi tepat 1 baris |
| Jejak langkah agen (trace viewer) | `banyak_halaman` | TERBUKTI | 106 baris > 10/halaman |
| Jejak langkah agen (trace viewer) | `filter_tanpa_hasil` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Jejak langkah agen (trace viewer) | `sort` | TERBUKTI | 8 nilai berbeda |
| Jejak langkah agen (trace viewer) | `error` | TERBUKTI | HTTP 401 pada /decisions/00000000-0000-0000-0000-000000000000/traces |
| Jejak langkah agen (trace viewer) | `loading` | GAP | komponen tanpa cabang memuat |
| Jejak langkah agen (trace viewer) | `null_opsional` | TERBUKTI | 82 baris NULL |
| Jejak langkah agen (trace viewer) | `teks_panjang` | GAP | panjang maks 24 karakter |
| Jejak langkah agen (trace viewer) | `angka_nol` | GAP | tidak ada nilai 0 |
| Jejak langkah agen (trace viewer) | `angka_negatif` | GAP | tidak ada nilai negatif |
| Jejak langkah agen (trace viewer) | `angka_besar` | GAP | maks 1600 |
| Jejak langkah agen (trace viewer) | `tanggal_lampau` | TERBUKTI | 106 baris |
| Jejak langkah agen (trace viewer) | `tanggal_hari_ini` | TERBUKTI | 103 baris |
| Jejak langkah agen (trace viewer) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Jejak langkah agen (trace viewer) | `unicode` | GAP | teks hanya ASCII |
| Jejak langkah agen (trace viewer) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| KPI (jendela periode) | `kosong` | TERBUKTI | 370 kunci dimensi tanpa baris |
| KPI (jendela periode) | `satu_item` | TERBUKTI | 290 kunci dimensi berisi tepat 1 baris |
| KPI (jendela periode) | `banyak_halaman` | TERBUKTI | 290 baris > 10/halaman |
| KPI (jendela periode) | `filter_tanpa_hasil` | TERBUKTI | 370 kunci dimensi tanpa baris |
| KPI (jendela periode) | `sort` | TERBUKTI | 98 nilai berbeda |
| KPI (jendela periode) | `error` | TERBUKTI | HTTP 401 pada /kpi (tanpa parameter query) |
| KPI (jendela periode) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| KPI (jendela periode) | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| KPI (jendela periode) | `teks_panjang` | GAP | panjang maks 0 karakter |
| KPI (jendela periode) | `angka_nol` | GAP | tidak ada nilai 0 |
| KPI (jendela periode) | `angka_negatif` | GAP | tidak ada nilai negatif |
| KPI (jendela periode) | `angka_besar` | GAP | maks 1224 |
| KPI (jendela periode) | `tanggal_lampau` | TERBUKTI | 140 baris |
| KPI (jendela periode) | `tanggal_hari_ini` | TERBUKTI | 10 baris |
| KPI (jendela periode) | `tanggal_masa_depan` | TERBUKTI | 150 baris |
| KPI (jendela periode) | `unicode` | GAP | teks hanya ASCII |
| KPI (jendela periode) | `format_lokal` | TERBUKTI | formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang |
| Kualitas agen (sampel run) | `kosong` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Kualitas agen (sampel run) | `satu_item` | TERBUKTI | 3 kunci dimensi berisi tepat 1 baris |
| Kualitas agen (sampel run) | `banyak_halaman` | TERBUKTI | 106 baris > 10/halaman |
| Kualitas agen (sampel run) | `filter_tanpa_hasil` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Kualitas agen (sampel run) | `sort` | TERBUKTI | 8 nilai berbeda |
| Kualitas agen (sampel run) | `error` | TERBUKTI | HTTP 401 pada /decisions/00000000-0000-0000-0000-000000000000/traces |
| Kualitas agen (sampel run) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Kualitas agen (sampel run) | `null_opsional` | TERBUKTI | 82 baris NULL |
| Kualitas agen (sampel run) | `teks_panjang` | GAP | panjang maks 24 karakter |
| Kualitas agen (sampel run) | `angka_nol` | GAP | tidak ada nilai 0 |
| Kualitas agen (sampel run) | `angka_negatif` | GAP | tidak ada nilai negatif |
| Kualitas agen (sampel run) | `angka_besar` | GAP | maks 1600 |
| Kualitas agen (sampel run) | `tanggal_lampau` | TERBUKTI | 106 baris |
| Kualitas agen (sampel run) | `tanggal_hari_ini` | TERBUKTI | 103 baris |
| Kualitas agen (sampel run) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Kualitas agen (sampel run) | `unicode` | GAP | teks hanya ASCII |
| Kualitas agen (sampel run) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Pengguna (admin) | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Pengguna (admin) | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Pengguna (admin) | `banyak_halaman` | GAP | 7 baris <= 10/halaman |
| Pengguna (admin) | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Pengguna (admin) | `sort` | TERBUKTI | 3 nilai berbeda |
| Pengguna (admin) | `error` | TERBUKTI | HTTP 401 pada /admin/users?limit=abc |
| Pengguna (admin) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Pengguna (admin) | `null_opsional` | TERBUKTI | 1 baris NULL |
| Pengguna (admin) | `teks_panjang` | GAP | panjang maks 31 karakter |
| Pengguna (admin) | `angka_nol` | GAP | tidak ada nilai 0 |
| Pengguna (admin) | `angka_negatif` | GAP | tidak ada nilai negatif |
| Pengguna (admin) | `angka_besar` | GAP | maks 0 |
| Pengguna (admin) | `tanggal_lampau` | TERBUKTI | 7 baris |
| Pengguna (admin) | `tanggal_hari_ini` | TERBUKTI | 7 baris |
| Pengguna (admin) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Pengguna (admin) | `unicode` | GAP | teks hanya ASCII |
| Pengguna (admin) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Lokasi (admin) | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Lokasi (admin) | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Lokasi (admin) | `banyak_halaman` | GAP | 10 baris <= 10/halaman |
| Lokasi (admin) | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Lokasi (admin) | `sort` | TERBUKTI | 10 nilai berbeda |
| Lokasi (admin) | `error` | TERBUKTI | HTTP 401 pada /admin/locations?limit=abc |
| Lokasi (admin) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Lokasi (admin) | `null_opsional` | GAP | kolom opsional terisi semua / tidak ada kolom opsional |
| Lokasi (admin) | `teks_panjang` | GAP | panjang maks 16 karakter |
| Lokasi (admin) | `angka_nol` | GAP | tidak ada nilai 0 |
| Lokasi (admin) | `angka_negatif` | GAP | tidak ada nilai negatif |
| Lokasi (admin) | `angka_besar` | GAP | maks 0 |
| Lokasi (admin) | `tanggal_lampau` | TERBUKTI | 10 baris |
| Lokasi (admin) | `tanggal_hari_ini` | TERBUKTI | 10 baris |
| Lokasi (admin) | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Lokasi (admin) | `unicode` | GAP | teks hanya ASCII |
| Lokasi (admin) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Status data demo & sesi | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Status data demo & sesi | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Status data demo & sesi | `banyak_halaman` | GAP | 4 baris <= 10/halaman |
| Status data demo & sesi | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Status data demo & sesi | `sort` | TERBUKTI | 4 nilai berbeda |
| Status data demo & sesi | `error` | TERBUKTI | HTTP 401 pada /demo/data-status?limit=abc |
| Status data demo & sesi | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Status data demo & sesi | `null_opsional` | TERBUKTI | 1 baris NULL |
| Status data demo & sesi | `teks_panjang` | GAP | panjang maks 7 karakter |
| Status data demo & sesi | `angka_nol` | GAP | tidak ada nilai 0 |
| Status data demo & sesi | `angka_negatif` | GAP | tidak ada nilai negatif |
| Status data demo & sesi | `angka_besar` | GAP | maks 0 |
| Status data demo & sesi | `tanggal_lampau` | TERBUKTI | 3 baris |
| Status data demo & sesi | `tanggal_hari_ini` | TERBUKTI | 2 baris |
| Status data demo & sesi | `tanggal_masa_depan` | TERBUKTI | 1 baris |
| Status data demo & sesi | `unicode` | GAP | teks hanya ASCII |
| Status data demo & sesi | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Jalankan agent + bukti pipeline | `kosong` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Jalankan agent + bukti pipeline | `satu_item` | TERBUKTI | 3 kunci dimensi berisi tepat 1 baris |
| Jalankan agent + bukti pipeline | `banyak_halaman` | TERBUKTI | 106 baris > 10/halaman |
| Jalankan agent + bukti pipeline | `filter_tanpa_hasil` | TERBUKTI | 9 kunci dimensi tanpa baris |
| Jalankan agent + bukti pipeline | `sort` | TERBUKTI | 8 nilai berbeda |
| Jalankan agent + bukti pipeline | `error` | TERBUKTI | HTTP 401 pada /demo/agent/last-run?limit=abc |
| Jalankan agent + bukti pipeline | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Jalankan agent + bukti pipeline | `null_opsional` | TERBUKTI | 82 baris NULL |
| Jalankan agent + bukti pipeline | `teks_panjang` | GAP | panjang maks 26 karakter |
| Jalankan agent + bukti pipeline | `angka_nol` | GAP | tidak ada nilai 0 |
| Jalankan agent + bukti pipeline | `angka_negatif` | GAP | tidak ada nilai negatif |
| Jalankan agent + bukti pipeline | `angka_besar` | GAP | maks 1600 |
| Jalankan agent + bukti pipeline | `tanggal_lampau` | TERBUKTI | 106 baris |
| Jalankan agent + bukti pipeline | `tanggal_hari_ini` | TERBUKTI | 103 baris |
| Jalankan agent + bukti pipeline | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Jalankan agent + bukti pipeline | `unicode` | GAP | teks hanya ASCII |
| Jalankan agent + bukti pipeline | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Login & identitas sesi | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Login & identitas sesi | `satu_item` | GAP | belum ada kunci dimensi berisi tepat 1 baris |
| Login & identitas sesi | `banyak_halaman` | GAP | 7 baris <= 10/halaman |
| Login & identitas sesi | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Login & identitas sesi | `sort` | TERBUKTI | 3 nilai berbeda |
| Login & identitas sesi | `error` | TERBUKTI | HTTP 401 pada /auth/me?limit=abc |
| Login & identitas sesi | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Login & identitas sesi | `null_opsional` | TERBUKTI | 1 baris NULL |
| Login & identitas sesi | `teks_panjang` | GAP | panjang maks 31 karakter |
| Login & identitas sesi | `angka_nol` | GAP | tidak ada nilai 0 |
| Login & identitas sesi | `angka_negatif` | GAP | tidak ada nilai negatif |
| Login & identitas sesi | `angka_besar` | GAP | maks 0 |
| Login & identitas sesi | `tanggal_lampau` | TERBUKTI | 7 baris |
| Login & identitas sesi | `tanggal_hari_ini` | TERBUKTI | 7 baris |
| Login & identitas sesi | `tanggal_masa_depan` | GAP | tidak ada tanggal masa depan |
| Login & identitas sesi | `unicode` | GAP | teks hanya ASCII |
| Login & identitas sesi | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Top bar: notifikasi & cakupan lokasi | `kosong` | GAP | belum ada kunci dimensi yang kosong |
| Top bar: notifikasi & cakupan lokasi | `satu_item` | TERBUKTI | 6 kunci dimensi berisi tepat 1 baris |
| Top bar: notifikasi & cakupan lokasi | `banyak_halaman` | TERBUKTI | 47 baris > 10/halaman |
| Top bar: notifikasi & cakupan lokasi | `filter_tanpa_hasil` | GAP | belum ada kunci dimensi yang kosong |
| Top bar: notifikasi & cakupan lokasi | `sort` | TERBUKTI | 37 nilai berbeda |
| Top bar: notifikasi & cakupan lokasi | `error` | TERBUKTI | HTTP 401 pada /decisions?limit=abc |
| Top bar: notifikasi & cakupan lokasi | `loading` | GAP | komponen tanpa cabang memuat |
| Top bar: notifikasi & cakupan lokasi | `null_opsional` | TERBUKTI | 37 baris NULL |
| Top bar: notifikasi & cakupan lokasi | `teks_panjang` | GAP | panjang maks 63 karakter |
| Top bar: notifikasi & cakupan lokasi | `angka_nol` | GAP | tidak ada nilai 0 |
| Top bar: notifikasi & cakupan lokasi | `angka_negatif` | GAP | tidak ada nilai negatif |
| Top bar: notifikasi & cakupan lokasi | `angka_besar` | TERBUKTI | maks 28775093.86 |
| Top bar: notifikasi & cakupan lokasi | `tanggal_lampau` | TERBUKTI | 9 baris |
| Top bar: notifikasi & cakupan lokasi | `tanggal_hari_ini` | TERBUKTI | 28 baris |
| Top bar: notifikasi & cakupan lokasi | `tanggal_masa_depan` | TERBUKTI | 38 baris |
| Top bar: notifikasi & cakupan lokasi | `unicode` | TERBUKTI | 9 baris non-ASCII |
| Top bar: notifikasi & cakupan lokasi | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |
| Status integrasi (panel tidak terpasang) | `kosong` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `satu_item` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `banyak_halaman` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `filter_tanpa_hasil` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `sort` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `error` | TERBUKTI | HTTP 401 pada /integrations/status?limit=abc |
| Status integrasi (panel tidak terpasang) | `loading` | TERBUKTI | cabang 'Memuat'/LoadingState ditemukan di komponen |
| Status integrasi (panel tidak terpasang) | `null_opsional` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `teks_panjang` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `angka_nol` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `angka_negatif` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `angka_besar` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `tanggal_lampau` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `tanggal_hari_ini` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `tanggal_masa_depan` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `unicode` | N/A | baris tanpa tabel data |
| Status integrasi (panel tidak terpasang) | `format_lokal` | GAP | tidak ada kolom uang pada baris ini / formatter tidak ditemukan |

## 5. Ringkasan GAP

### 5.1 Baris tanpa data demo

Tidak ada: setiap baris matriks punya minimal satu baris data.

### 5.2 Panel yang sengaja dipensiunkan (bukan GAP, ada bukti tes)

| Layar | Bagian | Bukti keputusan |
|---|---|---|
| Recommendations | Konsol operasi — snapshot kondisi | sengaja: `tests/prd-nav.test.tsx:60` menuntut `page.tsx` TANPA `<OpsConsole` |
| Recommendations | Konsol operasi — analisis agent & usulan | sengaja: sama, `tests/prd-nav.test.tsx:60` (console tidak dipasang) |
| Global (di luar tab) | Status integrasi (panel tidak terpasang) | sengaja: `tests/prd-nav.test.tsx:50-52` menuntut `page.tsx` TANPA `IntegrationStatusPanel`/`useIntegrationStatus` |

### 5.3 Baris GAP karena klaim gagal (bukan karena data kosong)

Tidak ada.

### 5.4 State tampilan yang belum bisa dibuktikan

| State | Jumlah layar | Layar |
|---|---|---|
| `kosong` | 26 | Tile status hari ini, Agenda harian, Rantai audit (Merkle ledger), Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Kartu informasi pengiriman, Telemetri node, Feed rekomendasi + filter/sort + pager, Konsol operasi — snapshot kondisi, Konsol operasi — analisis agent & usulan, Panel anomali harga (Event 2), Integritas bukti & dossier, Daftar purchase order (SAP simulasi), Papan batch & uji keamanan, Karantina batch, Rencana alokasi surplus, Pencatatan limbah, Daftar pemasok + pencarian, Jalur kiriman (jalan), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Login & identitas sesi, Top bar: notifikasi & cakupan lokasi |
| `satu_item` | 23 | Agenda harian, Rantai audit (Merkle ledger), Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Kartu informasi pengiriman, Telemetri node, Konsol operasi — snapshot kondisi, Konsol operasi — analisis agent & usulan, Panel anomali harga (Event 2), Integritas bukti & dossier, Daftar purchase order (SAP simulasi), Papan batch & uji keamanan, Karantina batch, Rencana alokasi surplus, Pencatatan limbah, Daftar pemasok + pencarian, Jalur kiriman (jalan), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Login & identitas sesi |
| `banyak_halaman` | 6 | Penerimaan barang, Supplier governance (eksklusi/pemulihan), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Login & identitas sesi |
| `filter_tanpa_hasil` | 26 | Tile status hari ini, Agenda harian, Rantai audit (Merkle ledger), Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Kartu informasi pengiriman, Telemetri node, Feed rekomendasi + filter/sort + pager, Konsol operasi — snapshot kondisi, Konsol operasi — analisis agent & usulan, Panel anomali harga (Event 2), Integritas bukti & dossier, Daftar purchase order (SAP simulasi), Papan batch & uji keamanan, Karantina batch, Rencana alokasi surplus, Pencatatan limbah, Daftar pemasok + pencarian, Jalur kiriman (jalan), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Login & identitas sesi, Top bar: notifikasi & cakupan lokasi |
| `loading` | 6 | Kartu informasi pengiriman, Feed rekomendasi + filter/sort + pager, Supplier governance (eksklusi/pemulihan), Status provider model, Jejak langkah agen (trace viewer), Top bar: notifikasi & cakupan lokasi |
| `null_opsional` | 20 | Agenda harian, Rantai audit (Merkle ledger), Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Kartu informasi pengiriman, Telemetri node, Konsol operasi — snapshot kondisi, Konsol operasi — analisis agent & usulan, Panel anomali harga (Event 2), Ringkasan keputusan & bukti, Jejak & riwayat persetujuan, Integritas bukti & dossier, Papan batch & uji keamanan, Rencana alokasi surplus, Daftar pemasok + pencarian, Jalur kiriman (jalan), KPI (jendela periode), Lokasi (admin) |
| `teks_panjang` | 31 | Tile status hari ini, Agenda harian, Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Kartu informasi pengiriman, Telemetri node, Feed rekomendasi + filter/sort + pager, Konsol operasi — snapshot kondisi, Konsol operasi — analisis agent & usulan, Panel anomali harga (Event 2), Ringkasan keputusan & bukti, Jejak & riwayat persetujuan, Daftar purchase order (SAP simulasi), Papan batch & uji keamanan, Karantina batch, Rencana alokasi surplus, Pencatatan limbah, Daftar pemasok + pencarian, Jalur kiriman (jalan), Status provider model, Jejak langkah agen (trace viewer), KPI (jendela periode), Kualitas agen (sampel run), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Jalankan agent + bukti pipeline, Login & identitas sesi, Top bar: notifikasi & cakupan lokasi |
| `angka_nol` | 30 | Tile status hari ini, Agenda harian, Rantai audit (Merkle ledger), Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Telemetri node, Feed rekomendasi + filter/sort + pager, Konsol operasi — snapshot kondisi, Ringkasan keputusan & bukti, Jejak & riwayat persetujuan, Integritas bukti & dossier, Papan batch & uji keamanan, Penerimaan barang, Karantina batch, Rencana alokasi surplus, Pencatatan limbah, Daftar pemasok + pencarian, Supplier governance (eksklusi/pemulihan), Status provider model, Jejak langkah agen (trace viewer), KPI (jendela periode), Kualitas agen (sampel run), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Jalankan agent + bukti pipeline, Login & identitas sesi, Top bar: notifikasi & cakupan lokasi |
| `angka_negatif` | 21 | Tile status hari ini, Agenda harian, Rantai audit (Merkle ledger), Feed rekomendasi + filter/sort + pager, Ringkasan keputusan & bukti, Jejak & riwayat persetujuan, Integritas bukti & dossier, Penerimaan barang, Karantina batch, Pencatatan limbah, Supplier governance (eksklusi/pemulihan), Status provider model, Jejak langkah agen (trace viewer), KPI (jendela periode), Kualitas agen (sampel run), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Jalankan agent + bukti pipeline, Login & identitas sesi, Top bar: notifikasi & cakupan lokasi |
| `angka_besar` | 33 | Tile status hari ini, Agenda harian, Rantai audit (Merkle ledger), Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Kartu informasi pengiriman, Telemetri node, Konsol operasi — snapshot kondisi, Konsol operasi — analisis agent & usulan, Panel anomali harga (Event 2), Ringkasan keputusan & bukti, Jejak & riwayat persetujuan, Integritas bukti & dossier, Daftar purchase order (SAP simulasi), Papan batch & uji keamanan, Penerimaan barang, Karantina batch, Rencana alokasi surplus, Pencatatan limbah, Daftar pemasok + pencarian, Jalur kiriman (jalan), Supplier governance (eksklusi/pemulihan), Status provider model, Jejak langkah agen (trace viewer), KPI (jendela periode), Kualitas agen (sampel run), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Jalankan agent + bukti pipeline, Login & identitas sesi |
| `tanggal_masa_depan` | 19 | Rantai audit (Merkle ledger), Grafik kecukupan pasokan, Kartu informasi pengiriman, Ringkasan keputusan & bukti, Jejak & riwayat persetujuan, Integritas bukti & dossier, Daftar purchase order (SAP simulasi), Penerimaan barang, Karantina batch, Daftar pemasok + pencarian, Jalur kiriman (jalan), Supplier governance (eksklusi/pemulihan), Status provider model, Jejak langkah agen (trace viewer), Kualitas agen (sampel run), Pengguna (admin), Lokasi (admin), Jalankan agent + bukti pipeline, Login & identitas sesi |
| `unicode` | 30 | Agenda harian, Rantai audit (Merkle ledger), Ringkasan peta pasokan (bento KPI), Peta kondisi komoditas, Grafik kecukupan pasokan, Grafik keseimbangan pasokan, Kartu informasi pengiriman, Telemetri node, Konsol operasi — snapshot kondisi, Konsol operasi — analisis agent & usulan, Panel anomali harga (Event 2), Ringkasan keputusan & bukti, Jejak & riwayat persetujuan, Integritas bukti & dossier, Daftar purchase order (SAP simulasi), Papan batch & uji keamanan, Karantina batch, Rencana alokasi surplus, Pencatatan limbah, Daftar pemasok + pencarian, Jalur kiriman (jalan), Status provider model, Jejak langkah agen (trace viewer), KPI (jendela periode), Kualitas agen (sampel run), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Jalankan agent + bukti pipeline, Login & identitas sesi |
| `format_lokal` | 21 | Tile status hari ini, Agenda harian, Rantai audit (Merkle ledger), Kartu informasi pengiriman, Jejak & riwayat persetujuan, Integritas bukti & dossier, Papan batch & uji keamanan, Penerimaan barang, Karantina batch, Jalur kiriman (jalan), Supplier governance (eksklusi/pemulihan), Status provider model, Jejak langkah agen (trace viewer), Kualitas agen (sampel run), Pengguna (admin), Lokasi (admin), Status data demo & sesi, Jalankan agent + bukti pipeline, Login & identitas sesi, Top bar: notifikasi & cakupan lokasi, Status integrasi (panel tidak terpasang) |

### 5.4 Ketidaksinkronan enum

Lihat §3.1 — 3 enum dengan 4 temuan. Yang paling berdampak: decision_type (kontrak tulis vs skema).

### 5.5 Catatan model vs DB

| Tabel | Kolom hanya di model | Kolom hanya di DB |
|---|---|---|
| `alembic_version` | — | version_num |
| `ledger_blocks` | — | action, actor_id, created_at, entity_id, height, id, payload, payload_hash, prev_hash |

## 6. Metode & query

### 6.1 Parameter nyata yang dipakai probe

| Parameter | Nilai | Asal |
|---|---|---|
| `decision_id` | `661695b2-c685-5eb2-83e9-d705e0b37960` | keputusan dengan jejak terbanyak pada cakupan Jakarta (`agent_traces`) |
| `batch_id` | `45204477-090b-5f69-94ba-bf1544be4b99` | batch Jakarta yang punya baris penerimaan (`batch_receipts`) |
| `receipt_id` | `126d2330-f98a-5df2-88e9-cb108919c0ac` | `batch_receipts.id` pertama |
| `exclusion_id` | `05dbb8ed-3f19-58ee-8b51-1448ae13f491` | `supplier_exclusions.id` pertama |
| `po_number` | `MC-661695B2C685` | PO pertama yang punya `decision_id` |
| `start_iso` | `2026-10-08T00:00:00+07:00` | `min(delivery_events.delivered_at)` WIB |
| `end_iso` | `2026-11-05T23:59:59+07:00` | `max(delivery_events.delivered_at)` WIB |

### 6.2 Template query state per baris

Setiap baris memakai satu query agregat dengan bentuk berikut (kolom opsional dilewati bila baris tidak menampilkan kolom itu):

```sql
select
  (select count(*) from <tabel> where <saringan>),                         -- baris total
  (select count(*) from (select d.id from <dimensi> d
     where not exists (select 1 from <tabel> x
       where x.<fk>=d.id and <saringan>)) z),                            -- kunci kosong
  (select count(*) from (select d.id from <dimensi> d
     where (select count(*) from <tabel> x
       where x.<fk>=d.id and <saringan>)=1) z),                          -- tepat 1 item
  (select count(distinct (<kolom_urut>)::text) from <tabel> where <saringan>),
  (select count(*) from <tabel> where <saringan> and <kolom_null> is null),
  (select max(length((<kolom_teks>)::text)) from <tabel> where <saringan>),
  (select count(*) from <tabel> where <saringan> and (<kolom_teks>)::text ~ '[^ -~]'),
  (select count(*) from <tabel> where <saringan> and <kolom_angka>=0),
  (select count(*) from <tabel> where <saringan> and <kolom_angka><0),
  (select max(abs(<kolom_angka>)) from <tabel> where <saringan>),
  (select count(*) from <tabel> where <saringan> and (<tanggal>) < now()),
  (select count(*) from <tabel> where <saringan>
     and ((<tanggal>) at time zone 'Asia/Jakarta')::date
     = (now() at time zone 'Asia/Jakarta')::date),                      -- hari ini WIB
  (select count(*) from <tabel> where <saringan> and (<tanggal>) > now())
```

### 6.3 Cara menjalankan ulang

```bash
cd mealchain-guardian
python3 scripts/audit/db_coverage.py          # tulis docs/db-coverage-matrix.md
python3 scripts/audit/db_coverage.py --check  # tulis + periksa angka ringkasan
```

Skrip hanya membaca: `SELECT` ke DB demo dan `GET`/satu `POST /balance/analyze` (tanpa penulisan keputusan) ke API. Tidak ada migrasi, tidak ada DELETE.
