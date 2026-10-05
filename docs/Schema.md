# Schema.md — MealChain Guardian Database

**Engine:** PostgreSQL 16. Semua tabel pakai `id UUID DEFAULT gen_random_uuid()` sebagai PK
kecuali disebutkan lain. Semua tabel punya `created_at TIMESTAMPTZ DEFAULT now()`.

---

## 1. Master data

### `locations`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| name | TEXT | NOT NULL, UNIQUE — e.g. "Jakarta", "Cianjur" |
| region | TEXT | NOT NULL — "West", "Central", "East", "Sumatera" |
| latitude | NUMERIC(9,6) | NOT NULL |
| longitude | NUMERIC(9,6) | NOT NULL |
| role_hint | TEXT | nullable — "demand_hub", "producer_hub", dst. (sesuai proposal) |

### `commodities`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| name | TEXT | NOT NULL, UNIQUE — "telur", "ayam", "wortel" |
| unit | TEXT | NOT NULL — "kg" |

### `users`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| name | TEXT | NOT NULL |
| email | TEXT | NOT NULL, UNIQUE |
| password_hash | TEXT | NOT NULL |
| role | TEXT | NOT NULL, CHECK IN ('sppg_head','sppg_nutritionist','bgn_monitor') |
| location_id | UUID | FK → locations.id, NULLABLE (NULL = akses semua lokasi, khusus bgn_monitor) |

### `suppliers`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| name | TEXT | NOT NULL |
| location_id | UUID | FK → locations.id, NOT NULL |
| reliability_score | NUMERIC(3,2) | NOT NULL, DEFAULT 0.80, CHECK BETWEEN 0 AND 1 |

## 2. Data operasional (time-series-ish)

### `supply_records`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| location_id | UUID | FK → locations.id, NOT NULL |
| commodity_id | UUID | FK → commodities.id, NOT NULL |
| quantity_kg | NUMERIC(10,2) | NOT NULL, CHECK >= 0 |
| recorded_at | TIMESTAMPTZ | NOT NULL |
| source | TEXT | NOT NULL — 'mock_sap' \| 'manual' \| 'sensor' |

### `demand_records`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| location_id | UUID | FK → locations.id, NOT NULL |
| commodity_id | UUID | FK → commodities.id, NOT NULL |
| quantity_kg | NUMERIC(10,2) | NOT NULL, CHECK >= 0 |
| needed_by | TIMESTAMPTZ | NOT NULL |
| recorded_at | TIMESTAMPTZ | NOT NULL |

### `price_signals`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| location_id | UUID | FK → locations.id, NOT NULL |
| commodity_id | UUID | FK → commodities.id, NOT NULL |
| price_per_kg | NUMERIC(10,2) | NOT NULL, CHECK > 0 |
| supplier_id | UUID | FK → suppliers.id, NULLABLE — WAJIB terisi saat source='supplier_quote', WAJIB NULL saat 'pihps_reference' (revisi kedua Roy 2026-10-03) |
| recorded_at | TIMESTAMPTZ | NOT NULL |
| source | TEXT | NOT NULL — 'pihps_reference' \| 'supplier_quote' (dua nilai generik; identitas supplier di kolom supplier_id, BUKAN dienkode ke string source) |

### `batches`
Unit inti untuk freshness/safety check.
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| commodity_id | UUID | FK → commodities.id, NOT NULL |
| location_id | UUID | FK → locations.id, NOT NULL |
| supplier_id | UUID | FK → suppliers.id, NOT NULL |
| quantity_kg | NUMERIC(10,2) | NOT NULL |
| harvested_at | TIMESTAMPTZ | NOT NULL |
| temperature_log | JSONB | NOT NULL, DEFAULT '[]' — array of `{timestamp, celsius}` |
| certification_status | TEXT | NOT NULL, DEFAULT 'none' — 'none'\|'hygiene'\|'haccp' |
| freshness_score | NUMERIC(3,2) | nullable, CHECK BETWEEN 0 AND 1 — diisi oleh `/freshness/evaluate` |
| safety_status | TEXT | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','pass','fail','needs_verification') |

## 3. Keputusan & audit trail

### `decisions`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| decision_type | TEXT | NOT NULL — 'regional_balance'\|'price_anomaly'\|'safety_disruption' |
| status | TEXT | NOT NULL, DEFAULT 'proposed', CHECK IN ('proposed','verifier_flagged','pending_approval','approved','rejected','executed') |
| proposed_by | TEXT | NOT NULL, DEFAULT 'supervisor_agent' |
| verified_by | TEXT | nullable — 'verifier_agent' |
| verifier_note | TEXT | nullable |
| source_location_id | UUID | FK → locations.id, nullable |
| target_location_id | UUID | FK → locations.id, nullable |
| commodity_id | UUID | FK → commodities.id, nullable |
| quantity_kg | NUMERIC(10,2) | nullable |
| safe_delivered_cost | NUMERIC(12,2) | nullable |
| cost_breakdown | JSONB | nullable — `{purchase, transport, handling, expected_loss, freshness_risk, safety_penalty}` |
| expires_at | TIMESTAMPTZ | NOT NULL — batas validitas keputusan. Aturan: `now < expires_at` valid; `now >= expires_at` expired. Keputusan expired tetap disimpan untuk audit trail, tidak dihapus, dan tidak dapat dihidupkan kembali oleh approval. (Keputusan Roy 2026-10-05, Sprint 2.) |

### `decision_evidence`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| decision_id | UUID | FK → decisions.id, NOT NULL |
| evidence_type | TEXT | NOT NULL — 'sap_purchase_order'\|'sap_goods_receipt'\|'gps'\|'temperature'\|'human_inspection'\|'market_price' |
| payload | JSONB | NOT NULL |
| is_consistent | BOOLEAN | nullable — hasil consistency check Evidence Fusion |
| recorded_at | TIMESTAMPTZ | NOT NULL |

### `agent_traces`
Cermin lokal dari AgentCore Observability, untuk ditampilkan di Agent Activity Log UI tanpa
bergantung real-time ke AWS console.
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| decision_id | UUID | FK → decisions.id, NOT NULL |
| step_name | TEXT | NOT NULL — 'DETECT'\|'VERIFY'\|'TRACE'\|'PREDICT'\|'OPTIMIZE'\|'DECIDE'\|'ACT'\|'LEARN' |
| tool_called | TEXT | nullable |
| input_summary | JSONB | nullable |
| output_summary | JSONB | nullable |
| duration_ms | INTEGER | nullable |
| step_at | TIMESTAMPTZ | NOT NULL |

### `approvals`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| decision_id | UUID | FK → decisions.id, NOT NULL |
| approved_by | UUID | FK → users.id, NOT NULL |
| approved | BOOLEAN | NOT NULL |
| comment | TEXT | nullable |
| approved_at | TIMESTAMPTZ | NOT NULL |

### `kpi_snapshots`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| kpi_name | TEXT | NOT NULL — sesuai 7 KPI di `Skill.md` |
| scope | TEXT | NOT NULL — 'global' atau location_id sebagai string |
| value | NUMERIC(14,4) | NOT NULL |
| computed_at | TIMESTAMPTZ | NOT NULL |

## 4. Mock SAP tables (meniru struktur OData asli)

### `sap_mock_material_stock` (≈ API_MATERIAL_STOCK)
| Kolom | Tipe |
|---|---|
| id | UUID PK |
| material_number | TEXT |
| plant | TEXT — dipetakan ke location_id |
| storage_location | TEXT |
| batch | TEXT — dipetakan ke batches.id |
| quantity | NUMERIC(10,2) |
| unit | TEXT |

### `sap_mock_purchase_orders` (≈ API_PURCHASEORDER_PROCESS_SRV)
| Kolom | Tipe |
|---|---|
| id | UUID PK |
| po_number | TEXT UNIQUE |
| supplier_id | UUID FK → suppliers.id |
| material_number | TEXT |
| ordered_quantity | NUMERIC(10,2) |
| price | NUMERIC(10,2) |
| decision_id | UUID FK → decisions.id, nullable — link balik ke keputusan yang memicu PO ini |
| status | TEXT — 'draft'\|'submitted'\|'confirmed' |

## 5. Indeks yang dibutuhkan

```sql
CREATE INDEX idx_supply_location_commodity ON supply_records(location_id, commodity_id);
CREATE INDEX idx_demand_location_commodity ON demand_records(location_id, commodity_id);
CREATE INDEX idx_batches_safety_status ON batches(safety_status);
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX idx_agent_traces_decision ON agent_traces(decision_id, step_at);
CREATE INDEX idx_kpi_name_scope ON kpi_snapshots(kpi_name, scope, computed_at);
```

## 6. Catatan integritas

- `batches.safety_status = 'fail'` → batch tersebut TIDAK BOLEH muncul di hasil
  `/balance/recommend` sebagai kandidat (enforced di application layer `core/constraints.py`,
  bukan cuma di query — defense in depth)
- `decisions.status = 'executed'` hanya boleh dicapai lewat `approvals` dengan `approved = true`
  terlebih dahulu — tidak ada jalur langsung `proposed → executed`
