# Snapshot keadaan MealChain Guardian

Diambil **2026-10-29T11:12:49+07:00** oleh `scripts/snapshot_state.py` (baca-saja).
Dokumen ini adalah sumber angka untuk dokumen lain: kalau angka di dokumen lain
berbeda, dokumen ini yang berlaku sampai snapshot berikutnya.

## Volume tabel

| Tabel | Baris |
| --- | ---: |
| `agent_traces` | 109 |
| `approvals` | 21 |
| `batch_receipts` | 5 |
| `batches` | 133 |
| `commodities` | 4 |
| `decision_evidence` | 61 |
| `decisions` | 49 |
| `delivery_events` | 210 |
| `demand_records` | 1369 |
| `demo_sessions` | 6 |
| `disposal_events` | 80 |
| `ledger_blocks` | 3841 |
| `locations` | 10 |
| `menu_plans` | 660 |
| `price_signals` | 5933 |
| `road_routes` | 53 |
| `sap_mock_material_stock` | 40 |
| `sap_mock_purchase_orders` | 17 |
| `supplier_exclusions` | 2 |
| `suppliers` | 60 |
| `supply_records` | 5240 |
| `users` | 7 |

## Keputusan

- Terbuka (menunggu / ditandai verifier): **31**
- Kartu di jendela 24 jam: **17**
- status `pending_approval`: 27
- status `rejected`: 9
- status `executed`: 6
- status `verifier_flagged`: 4
- status `proposed`: 1
- status `approved`: 1
- status `review_only`: 1

## Batch & keamanan

- Total batch: **133**
- Batch kedaluwarsa < 48 jam: **14**
- Batch ditahan (karantina): **1**
- safety `needs_verification`: 18
- safety `fail`: 3
- safety `pending`: 2
- safety `pass`: 110

## Pemasok

- Total: **60**
- sertifikat `hygiene`: 35
- sertifikat `none`: 8
- sertifikat `haccp`: 17
- eksklusi `proposed`: 1
- eksklusi `active`: 1

## Kiriman & rantai audit

- Rute kiriman (cakupan Jakarta): **13** (berjalur 12, tanpa jalur 1)
- Tahap perjalanan: {'belum_berangkat': 4, 'di_jalan': 2, 'sudah_tiba': 6, 'tidak_diketahui': 1}
- Ledger: **3841** blok (arsip 3743, yatim 0, valid=True)
- Jejak agen: **109** langkah
- PO mock SAP: **17**
- Bukti keputusan: **61**
- Approval: **21**

## Agenda & KPI hari ini

- Agenda: menu 1 rencana · pengiriman 0 · limbah 3 catatan · pasokan 12 baris · harga 33 baris · batch kedaluwarsa 5 · keputusan 17
- Meal Continuity: — (no_data)
- Avoidable Food Loss: — (no_data)
- Regional Imbalance: 0.00 percent (sampel 2)
- Safe Delivered Cost: — (no_data)
- Price Deviation: 3.21 percent (sampel 13)
- Decision Time: — (no_data)
- Evidence Completeness: — (no_data)
- Sesi demo: active=True, sisa=5632 detik

## Catatan data

- Deret pasokan: 2026-09-01 07:00:00 .. 2026-11-04 19:00:00
- Baris bertanggal **masa depan**: pasokan 520, harga 580 (artefak penyemai, bukan data live)
- Semua baris berasal dari template demo (`origin` seed/demo), bukan data operasional nyata.

_Dokumen ini dihasilkan otomatis; jangan diedit tangan._
