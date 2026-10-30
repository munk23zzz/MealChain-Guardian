# Peta cakupan data Joule ↔ MealChain Guardian

Langkah 1 — probe baca-saja. Dikerjakan 30 Okt 2026 terhadap backend yang hidup
(`http://localhost:8000`, DB `mealchain`), akun baca-saja **bgn_monitor**.

Reproduksi:

```bash
cd sap-joule
./.venv/Scripts/python.exe scripts/probe-cakupan-data.py
# berkas: _qa/cakupan-data/<tanggal>/<nama>.json + ringkasan.txt
```

Skrip hanya `GET` + `POST /auth/login`; tidak menulis ke DB. Kata sandi tidak
pernah dicetak.

## 1. Inventaris tabel (count(\*), bukan `n_live_tup`)

`n_live_tup` tertinggal jauh pada satu tabel di sini: `ledger_blocks` dilaporkan
156 baris sementara `count(*)` = **8153**. Angka di bawah yang berlaku.

| Tabel | Baris | Jalur baca |
|---|---:|---|
| price_signals | 5925 | `/price/monitor`, `/price/{lok}/{kom}`, `/price/quotes/…` |
| supply_records | 5244 | `/balance/map`, `/supply/{lok}/{kom}` |
| demand_records | 1380 | `/demand/{lok}/{kom}`, `/demand/forecast/…` |
| menu_plans | 660 | **hanya agregat** lewat `/agenda` |
| delivery_events | 240 | **hanya agregat** lewat `/agenda` |
| agent_traces | 186 | `/decisions/{id}/traces` |
| decision_evidence | 123 | `/decisions/{id}/compliance\|packet` |
| batches | 103 | `/batches`, `/batches/{id}` |
| disposal_events | 80 | `/waste/summary` (agregat) |
| decisions | 78 | `/decisions`, `/decisions/{id}` |
| approvals | 67 | `/decisions/{id}/approval-summary` |
| road_routes | 53 | `/supplier-routes` |
| sap_mock_material_stock | 40 | **tidak ada endpoint HTTP** |
| sap_mock_purchase_orders | 38 | `/sap/purchase-orders`, `/detail` |
| ledger_blocks | 8153 | `/ledger/verify`, `/decisions/{id}/ledger` |
| batch_receipts | 6 | `/receipts`, `/receipts/menunggu`, `/receipts/riwayat` |
| supplier_exclusions | 2 | `/supplier-exclusions` |
| demo_sessions | 1 | `/demo/session` |

## 2. Skill jembatan yang sudah ada (14) dan sumber datanya

| Skill | Endpoint yang dipanggil |
|---|---|
| supply_situation | `/balance/map`, `/admin/locations`, `/supply/…`, `/demand/…` |
| kpi_snapshot | `/kpi` |
| approval_queue | `/decisions`, `/decisions/{id}/approval-summary` |
| purchase_order | `/sap/purchase-orders`, `/sap/purchase-orders/{po}/detail` |
| supplier_directory | `/suppliers` |
| price_intelligence | `/price/monitor`, `/price/{lok}/{kom}`, `/price/quotes/…` |
| demand_forecast | `/demand/forecast/{lok}/{kom}` |
| food_loss | `/waste/summary` |
| supplier_risk | `/supplier-exclusions`, `/supplier-routes` |
| receipts_queue | `/receipts/menunggu`, `/receipts?batch_id=…` |
| quarantine_status | `/batches` (disaring status karantina) |
| batch_detail | `/batches/{id}` |
| decision_evidence | `/decisions/{id}/compliance`, `/packet`, `/chain`, `/traces` |
| system_status | `/integrations/status`, `/ledger/verify` |

## 3. Endpoint yang ADA dan sudah dicoba, tapi belum punya skill

Semua di bawah ini **HTTP 200** dengan akun baca-saja; bentuk payload sudah
disimpan di `_qa/cakupan-data/2026-10-30/`.

| Endpoint | Bentuk payload nyata | Nilai untuk chat |
|---|---|---|
| `/procurement/summary?periode=today` | `period`, `scope`, `purchase_orders{count,total_value,by_status,last}`, `decisions_executed`, `batches_dispatched`, `receipts{count,kg,last}` | Ringkasan pengadaan satu periode — belum ada di 14 skill |
| `/receipts/riwayat?limit=5` | `items[]` berisi `checked`, `checked_count`, `other_note`, `recorded_by` | Riwayat penerimaan yang sudah selesai (skill sekarang hanya antrean) |
| `/receipts/checklist` | `version`, `total_bobot`, `ambang{fail_max_score,ambiguous_max_score,accepted_ratio_min,berat_lebih_maks_persen}`, `butir[7]` | Dasar aturan penilaian penerimaan — menjawab "kenapa batch ini gagal" |
| `/surplus/regions` | `totals{surplus_kg,layak_kg,source_locations,regions}`, `regions[]{region,surplus_kg,by_commodity,sources}` | Surplus **per wilayah** (Jawa Barat 3454 kg, DKI 330 kg hari ini) |
| `/surplus/allocations?commodity=ayam` | `totals{surplus_kg,shortage_kg,allocatable_kg}`, `pairs[]`, `available`, `reason` | Rencana alih lintas SPPG; hari ini `available:false`, `reason: alokasi_di_bawah_ambang`, `pairs:[]` |
| `/agenda?start=&end=` | `days[]{menu,delivery,disposal,supply,price,batches_expiring,decisions,activity}` | Agenda harian "Hari Ini" — satu-satunya jalan ke rencana menu & pengiriman |
| `/balance/{lok}/{kom}` | `location`, `commodity`, `supply_kg`, `demand_kg`, `surplus_kg`, `shortage_kg`, `status`, `data_state` | Pasokan satu pasangan tanpa perlu menyapu peta |
| `/decisions/{id}/audit-facts` | `status`, `sdc_check`, `evidence`, `batch_sumber{statuses,freshness}`, `exclusion`, `ledger`, `citations` | Fakta yang dipakai memutuskan — bahan "mengapa keputusan ini" |
| `/decisions/{id}/dossier` | `content_address`, `signature{state,algorithm,signature,public_key}`, `verify`, `evidence[]` | Paket bertanda tangan: bukti yang tak bisa diubah |
| `/decisions/{id}/ledger` | `blocks[]` (`height`, `action`, `created_at`) | Jejak ledger per keputusan |

## 4. Lubang nyata (tidak ada jalur sama sekali, atau hanya agregat)

1. **`menu_plans` (660 baris)** — `/agenda` hanya mengirim `{available, rows, planned_portions}`
   per hari. Joule bisa bilang "hari ini 10 baris rencana menu, 12.029 porsi", tetapi
   **tidak bisa menyebut menu apa** (nama masakan, komposisi). Butuh endpoint rincian menu.
2. **`delivery_events` (240 baris)** — sama: `{available, rows, delivered_portions}`. Joule tidak
   bisa menjawab "pengiriman ke SPPG mana yang telat / berapa porsi diterima per lokasi".
3. **`sap_mock_material_stock` (40 baris)** — nol endpoint HTTP. Hanya terjangkau lewat
   abstraksi provider internal (`get_material_stock(plant)`), dipakai pipeline, bukan HTTP.
   Stok material SAP tidak bisa ditanya lewat chat sampai ada rute baca.

## 5. Catatan bentuk yang mudah salah tampil (dari probe ini)

- `/receipts/riwayat` membungkus daftar dalam `items`, sedangkan `/receipts` polos berbeda
  bentuknya — envelope key per endpoint, wajib diprobe.
- `/procurement/summary` menolak tanpa `periode` ATAU `start`+`end` (422). `total_value`
  dikirim sebagai **string Decimal**, bukan float — jangan dijumlahkan di perender.
- `/surplus/allocations` memiliki `available:false` + `reason` yang **wajib** ditampilkan; kalau
  hanya `pairs` yang dicetak, jawaban terbaca "tidak ada alokasi" padahal ada surplus 232 kg
  yang sengaja tidak dialokasikan (di bawah ambang 150 kg per pasangan).
- `/agenda` wajib `start` + `end` (maks `MAX_DAYS` hari) — tidak ada mode "semua".
- `/decisions/{id}/dossier` mengirim `public_key`; jangan pernah meneruskan ke teks chat.

## 6. Keputusan yang menunggu Anda

1. Prioritas Langkah 2 — tiga kandidat termurah (endpoint sudah ada, cukup klien +
   perender + kata kunci): `/procurement/summary`, `/surplus/regions`+`/allocations`,
   `/receipts/riwayat`+`/checklist`.
2. Apakah rincian menu & pengiriman (lubang #1/#2) masuk lingkup sekarang — itu berarti
   menambah rute baca baru di backend, bukan hanya jembatan.
3. Apakah stok material SAP (lubang #3) perlu, atau cukup dinyatakan "belum tersedia" lewat
   skill `unsupported_domain` yang sudah ada.
