# Skill.md — Domain Knowledge MealChain Guardian

Ini bukan skill generik (testing, planning, dst — itu sudah ada di Hermes). Ini "kamus kerja"
domain proyek: istilah, formula, threshold, dan kontrak tool. Kalau ragu soal definisi
sesuatu di domain ini, cek di sini dulu sebelum menebak.

---

## 1. Glosarium

| Istilah | Arti |
|---|---|
| **SPPG** | Satuan Pelayanan Pemenuhan Gizi — dapur yang mengolah & mendistribusikan makanan MBG |
| **MBG** | Program Makan Bergizi Gratis — program pemerintah, killer use case proyek ini |
| **BGN** | Badan Gizi Nasional — otoritas pengawas program MBG |
| **Safe Delivered Cost** | Biaya pengadaan yang memperhitungkan bukan hanya harga beli, tapi juga transport, handling, potensi kerugian, risiko kesegaran, dan penalti risiko keamanan |
| **Hard constraint** | Syarat mutlak yang kalau gagal, kandidat langsung gugur — TIDAK bisa "dikompensasi" oleh skor tinggi di aspek lain |
| **Temperature excursion** | Kondisi suhu batch keluar dari rentang aman selama periode tertentu |
| **Regional demand shock** | Perubahan permintaan mendadak di suatu wilayah akibat aktif/tidaknya distribusi MBG |
| **Physical inventory ≠ usable inventory** | Prinsip inti: stok fisik yang tercatat tidak sama dengan stok yang benar-benar layak dialokasikan setelah dikurangi yang gagal freshness/safety check |

## 2. Hard constraint hierarchy (urutan prioritas keputusan)

```
1. Safety           (mutlak — gagal = kandidat gugur, tidak ada negosiasi)
2. Kecukupan gizi/menu
3. Kontinuitas makan
4. Biaya
5. Pengurangan limbah
```

Implikasi teknis: kode di `core/constraints.py` HARUS mengecek safety PALING PERTAMA dan
tidak boleh ada jalur di mana skor tinggi di kriteria 2-5 mengoverride kegagalan di kriteria 1.

## 3. Formula inti

### Candidate Score
```
Candidate Score = Demand Fit × Supply Availability × Freshness × Safety Eligibility
                   × Supplier Reliability × Logistics Feasibility
```
Semua faktor dinormalisasi 0-1. `Safety Eligibility` bernilai 0 (bukan pecahan kecil) kalau
`batches.safety_status = 'fail'` — ini membuat skor total otomatis 0, bukan sekadar berkurang.

### Safe Delivered Cost
```
Safe Delivered Cost = Purchase Cost
                     + Transportation Cost
                     + Handling Cost
                     + Expected Loss
                     + Freshness Risk Penalty
                     + Safety Risk Penalty
```
Hard constraints yang harus lolos SEBELUM cost ini dihitung untuk suatu kandidat:
`safety_status != 'fail'`, `freshness_score >= threshold` (default 0.6, taruh di config,
jangan hardcode), `quantity_kg >= required_quantity`, `estimated_delivery_time <=
delivery_window`.

### Freshness threshold default (final — keputusan Roy 2026-10-01)
- `freshness_score >= 0.85` → `pass`
- `0.60 <= freshness_score < 0.85` → `needs_verification` (bukan otomatis gagal)
- `< 0.60` → `fail` / tidak layak

## 4. 7 KPI — definisi & cara hitung

| KPI | Formula/definisi |
|---|---|
| **Meal Continuity Rate** | % rencana menu yang terpenuhi tanpa substitusi tidak aman = (menu terpenuhi aman / total menu direncanakan) × 100% |
| **Avoidable Food Loss** | Total kg (atau nilai Rp) batch yang terbuang karena TIDAK teralokasikan padahal freshness_score masih lolos threshold saat itu |
| **Regional Imbalance Resolution Rate** | % kasus surplus/shortage terdeteksi yang berhasil diselesaikan (decisions.status = 'executed') dalam window waktu tertentu |
| **Safe Delivered Cost** | Rata-rata `safe_delivered_cost` dari semua decisions yang executed dalam periode |
| **Procurement Price Deviation** | \|price_per_kg pemasok − price_signals referensi\| / referensi × 100% |
| **Decision Time** | Rata-rata durasi dari `agent_traces` step pertama (DETECT) sampai step terakhir (ACT) per decision |
| **Evidence Completeness** | % decisions yang punya ≥2 `decision_evidence` dengan `is_consistent = true` sebelum status berubah ke `approved` |

## 5. Kontrak tool (dipakai AgentCore Gateway untuk generate MCP tool dari OpenAPI)

Format: `nama_tool(input) → output`. Ini HARUS konsisten dengan endpoint di
`backend/app/api/*.py` — kalau endpoint berubah, update di sini juga.

```
supply.get(location_id, commodity_id) → { quantity_kg, recorded_at, source }
demand.get(location_id, commodity_id) → { quantity_kg, needed_by }
freshness.evaluate(batch_id) → { freshness_score, status, usable_until }
safety.evaluate(batch_id) → { safety_status: PASS|FAIL|NEEDS_VERIFICATION, reasons[] }
price.deviation(location_id, commodity_id, supplier_price) → { deviation_pct, reference_price, flagged }
logistics.estimate(source_location_id, target_location_id, quantity_kg)
    → { distance_km, estimated_time_min, feasible }
evidence.fuse(decision_id) → { evidences[], overall_consistent }
cost.safe_delivered(candidate) → { total, breakdown }
balance.recommend(location_id, commodity_id) → { candidates[], recommended_candidate }
actions.propose(decision_id) → { status: 'pending_approval' }
actions.execute(decision_id) → { status: 'executed', sap_po_number }
```

## 6. Mock SAP — field reference (supaya mirip real SAP kalau nanti diganti)

### API_MATERIAL_STOCK (mock)
`MaterialNumber, Plant, StorageLocation, Batch, MatlStkQty, BaseUnit`

### API_PURCHASEORDER_PROCESS_SRV (mock)
`PurchaseOrder, Supplier, MaterialNumber, OrderQuantity, NetPriceAmount, PurchasingDocumentDate`

### API_BUSINESS_PARTNER (mock)
`BusinessPartner, BusinessPartnerName, PurchasingOrganization`

Semua response mock HARUS punya header `X-Data-Source: MOCK` — lihat `Architecture.md` §7.

## 7. Real SAP field mapping — untuk AWSforSAPMCPProvider (lihat Architecture.md §9)

Ini kontrak yang HARUS dipatuhi `AWSforSAPMCPProvider` supaya field yang keluar identik
dengan `MockSAPProvider` — model domain kita di kolom kiri, tidak boleh berubah.

| Domain model kita | Field SAP asli (via AWS for SAP MCP Server) | API asal |
|---|---|---|
| `locations.name` (dipetakan ke plant) | `Plant` | API_MATERIAL_STOCK |
| `batches.id` | `Batch` | API_MATERIAL_STOCK |
| `commodities.name` (dipetakan ke material) | `MaterialNumber` | API_MATERIAL_STOCK, API_PRODUCT_SRV |
| `supply_records.quantity_kg` | `MatlStkQty` (+ `BaseUnit`) | API_MATERIAL_STOCK |
| `decisions.id` → saat execute | `PurchaseOrder` (nomor PO yang di-generate SAP) | API_PURCHASEORDER_PROCESS_SRV |
| `suppliers.id` | `Supplier` / `BusinessPartner` | API_BUSINESS_PARTNER |
| `decisions.quantity_kg` | `OrderQuantity` | API_PURCHASEORDER_PROCESS_SRV |
| `decisions.safe_delivered_cost` (komponen purchase saja) | `NetPriceAmount` | API_PURCHASEORDER_PROCESS_SRV |
| goods receipt (evidence) | `MaterialDocument` | API_MATERIAL_DOCUMENT |

**Perbedaan penting vs mock:** field asli SAP punya lebih banyak metadata wajib (approval
status, fiscal year, company code) yang tidak ada di mock. `AWSforSAPMCPProvider` harus
mengisi default yang masuk akal untuk field ini (dikonfirmasi ke tim SAP kompetisi saat
provisioning), TAPI tidak boleh mengubah kontrak `SAPDataProvider` — kompleksitas tambahan
diserap di dalam provider, tidak bocor ke `core/` atau agent.

**Auth:** AWS for SAP MCP Server butuh kredensial ke SAP tenant (biasanya OAuth2/Basic Auth
di level SAP BTP) — disimpan lewat AgentCore Identity, bukan `.env` biasa (beda dari mock yang
tidak butuh auth sama sekali).

## 8. Contoh perhitungan (buat validasi manual saat testing)

```
Batch: 500 kg telur, Cianjur, freshness_score = 0.75, safety_status = PASS
Purchase cost: Rp25.000/kg × 500 = Rp12.500.000
Transport (Cianjur→Jakarta, 120 km): Rp150.000
Handling: Rp50.000
Expected loss (freshness 0.75 → 5% buffer): Rp625.000
Freshness risk penalty: Rp0 (di atas threshold 0.6)
Safety Risk Penalty: Rp0 (PASS)
─────────────────────────────────────
Safe Delivered Cost = Rp13.325.000 (≈ Rp26.650/kg)
```
Gunakan contoh ini sebagai test case pertama di `backend/tests/test_safe_delivered_cost.py`.

> **Catatan threshold (Roy 2026-10-01):** dengan ambang freshness final (pass ≥0.85,
> verify 0.60–<0.85, fail <0.60), contoh `freshness_score = 0.75` di atas berada di band
> `needs_verification` — bukan kandidat PASS. Angka biaya tetap valid sebagai contoh
> aritmetika Safe Delivered Cost untuk Sprint 2; formula §3 tidak berubah.

