# Snapshot keadaan MealChain Guardian

Diambil **2026-10-26T20:43:42+07:00** oleh `scripts/snapshot_state.py` (baca-saja).
Dokumen ini adalah sumber angka untuk dokumen lain: kalau angka di dokumen lain
berbeda, dokumen ini yang berlaku sampai snapshot berikutnya.

## Volume tabel

| Tabel | Baris |
| --- | ---: |
| `agent_traces` | 118 |
| `approvals` | 28 |
| `batch_receipts` | 7 |
| `batches` | 125 |
| `commodities` | 4 |
| `decision_evidence` | 61 |
| `decisions` | 48 |
| `delivery_events` | 180 |
| `demand_records` | 1360 |
| `demo_sessions` | 6 |
| `disposal_events` | 83 |
| `ledger_blocks` | 1742 |
| `locations` | 10 |
| `menu_plans` | 660 |
| `price_signals` | 6015 |
| `road_routes` | 54 |
| `sap_mock_material_stock` | 40 |
| `sap_mock_purchase_orders` | 20 |
| `supplier_exclusions` | 6 |
| `suppliers` | 60 |
| `supply_records` | 5240 |
| `users` | 8 |

## Keputusan

- Terbuka (menunggu / ditandai verifier): **22**
- Kartu di jendela 24 jam: **14**
- status `pending_approval`: 17
- status `rejected`: 10
- status `executed`: 9
- status `verifier_flagged`: 5
- status `approved`: 3
- status `proposed`: 2
- status `review_only`: 2

## Batch & keamanan

- Total batch: **125**
- Batch kedaluwarsa < 48 jam: **8**
- Batch ditahan (karantina): **2**
- safety `needs_verification`: 15
- safety `fail`: 3
- safety `pending`: 5
- safety `pass`: 102

## Pemasok

- Total: **60**
- sertifikat `hygiene`: 35
- sertifikat `none`: 8
- sertifikat `haccp`: 17
- eksklusi `proposed`: 2
- eksklusi `active`: 2
- eksklusi `rejected`: 1
- eksklusi `revoked`: 1

## Kiriman & rantai audit

- Rute kiriman (cakupan Jakarta): **15** (berjalur 14, tanpa jalur 1)
- Tahap perjalanan: {'belum_berangkat': 1, 'di_jalan': 7, 'sudah_tiba': 6, 'tidak_diketahui': 1}
- Ledger: **1742** blok (arsip 1670, yatim 0, valid=True)
- Jejak agen: **118** langkah
- PO mock SAP: **20**
- Bukti keputusan: **61**
- Approval: **28**

## Agenda & KPI hari ini

- Agenda: menu 1 rencana · pengiriman 0 · limbah 3 catatan · pasokan 12 baris · harga 33 baris · batch kedaluwarsa 1 · keputusan 14
- Meal Continuity: — (no_data)
- Avoidable Food Loss: 0.59 percent (sampel 3)
- Regional Imbalance: 100.00 percent (sampel 2)
- Safe Delivered Cost: 18472767.67 IDR (sampel 2)
- Price Deviation: 2.66 percent (sampel 17)
- Decision Time: 20.00 minutes (sampel 2)
- Evidence Completeness: 66.67 percent (sampel 3)
- Sesi demo: active=True, sisa=2716 detik

## Catatan data

- Deret pasokan: 2026-09-01 07:00:00 .. 2026-11-04 19:00:00
- Baris bertanggal **masa depan**: pasokan 720, harga 858 (artefak penyemai, bukan data live)
- Semua baris berasal dari template demo (`origin` seed/demo), bukan data operasional nyata.

_Dokumen ini dihasilkan otomatis; jangan diedit tangan._
