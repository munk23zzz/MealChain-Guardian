# Snapshot keadaan MealChain Guardian

Diambil **2026-10-26T22:34:34+07:00** oleh `scripts/snapshot_state.py` (baca-saja).
Dokumen ini adalah sumber angka untuk dokumen lain: kalau angka di dokumen lain
berbeda, dokumen ini yang berlaku sampai snapshot berikutnya.

## Volume tabel

| Tabel | Baris |
| --- | ---: |
| `agent_traces` | 85 |
| `approvals` | 21 |
| `batch_receipts` | 2 |
| `batches` | 120 |
| `commodities` | 4 |
| `decision_evidence` | 51 |
| `decisions` | 36 |
| `delivery_events` | 190 |
| `demand_records` | 1360 |
| `demo_sessions` | 11 |
| `disposal_events` | 80 |
| `ledger_blocks` | 2034 |
| `locations` | 10 |
| `menu_plans` | 660 |
| `price_signals` | 5924 |
| `road_routes` | 53 |
| `sap_mock_material_stock` | 40 |
| `sap_mock_purchase_orders` | 16 |
| `supplier_exclusions` | 2 |
| `suppliers` | 60 |
| `supply_records` | 5240 |
| `users` | 7 |

## Keputusan

- Terbuka (menunggu / ditandai verifier): **19**
- Kartu di jendela 24 jam: **11**
- status `pending_approval`: 15
- status `rejected`: 9
- status `executed`: 5
- status `verifier_flagged`: 4
- status `proposed`: 1
- status `review_only`: 1
- status `approved`: 1

## Batch & keamanan

- Total batch: **120**
- Batch kedaluwarsa < 48 jam: **8**
- Batch ditahan (karantina): **1**
- safety `needs_verification`: 14
- safety `fail`: 3
- safety `pending`: 3
- safety `pass`: 100

## Pemasok

- Total: **60**
- sertifikat `hygiene`: 35
- sertifikat `none`: 8
- sertifikat `haccp`: 17
- eksklusi `proposed`: 1
- eksklusi `active`: 1

## Kiriman & rantai audit

- Rute kiriman (cakupan Jakarta): **12** (berjalur 11, tanpa jalur 1)
- Tahap perjalanan: {'belum_berangkat': 0, 'di_jalan': 3, 'sudah_tiba': 8, 'tidak_diketahui': 1}
- Ledger: **2034** blok (arsip 1960, yatim 0, valid=True)
- Jejak agen: **85** langkah
- PO mock SAP: **16**
- Bukti keputusan: **51**
- Approval: **21**

## Agenda & KPI hari ini

- Agenda: menu 1 rencana · pengiriman 2 · limbah 3 catatan · pasokan 12 baris · harga 33 baris · batch kedaluwarsa 2 · keputusan 11
- Meal Continuity: 100.00 percent (sampel 1)
- Avoidable Food Loss: 0.59 percent (sampel 3)
- Regional Imbalance: — (no_data)
- Safe Delivered Cost: — (no_data)
- Price Deviation: 2.81 percent (sampel 17)
- Decision Time: — (no_data)
- Evidence Completeness: — (no_data)
- Sesi demo: active=True, sisa=5954 detik

## Catatan data

- Deret pasokan: 2026-09-01 07:00:00 .. 2026-11-04 19:00:00
- Baris bertanggal **masa depan**: pasokan 720, harga 840 (artefak penyemai, bukan data live)
- Semua baris berasal dari template demo (`origin` seed/demo), bukan data operasional nyata.

_Dokumen ini dihasilkan otomatis; jangan diedit tangan._
