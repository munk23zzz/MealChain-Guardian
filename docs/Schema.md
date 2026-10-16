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
| location_id | UUID | FK → locations.id, NOT NULL — hub SPPG tempat pemasok terdaftar |
| reliability_score | NUMERIC(3,2) | NOT NULL, DEFAULT 0.80, CHECK BETWEEN 0 AND 1 |

Kolom profil & peta (migrasi `012_supplier_profile`, Fase 2 rencana 2026-10-14):

| Kolom | Tipe | Constraint |
|---|---|---|
| latitude | NUMERIC(9,6) | NULLABLE, CHECK −90…90 |
| longitude | NUMERIC(9,6) | NULLABLE, CHECK −180…180 |
| commodity_id | UUID | FK → commodities.id, NULLABLE (pemasok multi-komoditas boleh NULL) |
| capacity_kg_per_week | NUMERIC(10,2) | NULLABLE, CHECK >= 0 |
| certification_status | TEXT | NULLABLE, CHECK IN ('none','hygiene','haccp') |
| address | TEXT | NULLABLE |
| contact_name | TEXT | NULLABLE |
| updated_at | TIMESTAMPTZ | NULLABLE |

- **CHECK koordinat BERPASANGAN**: `(latitude IS NULL) = (longitude IS NULL)` — separuh
  koordinat dilarang, karena baris seperti itu akan tampak seperti data nyata di peta.
- Index: `location_id`, `commodity_id`.
- **Isi tabel saat ini (setelah Fase 7, 2026-10-15)**: 14 pemasok kanonik
  (`data/seed/sprint1_seed.json`, nama pola `Supplier <Kota>-N`, tanpa koordinat — terikat 14 kutipan
  harga) + **21 pemasok demo** (`data/seed/suppliers_demo.json`) = **35 baris**.
  Dari 21 itu: **12 pemasok hub Jakarta** berkoordinat ABSOLUT di Jakarta + kota penyangga
  (Bekasi, Depok, Tangerang, Bogor, Karawang, Cisarua, Serang, Subang, Cianjur) dengan jarak
  berjenjang 0–25 / 25–60 / 60–150 km dari SPPG Jakarta (ambang `REACH_KM_MAX = 150 km`),
  dan **9 pemasok hub lain** (satu per hub) berkoordinat hub + geseran tetap.
  Sebelum Fase 7: 30 pemasok demo (3 per hub × 10 kota) — jumlah itu **berubah sadar**, aturan
  kanonik vs demo tidak.

Profil pemasok kanonik — **DITURUNKAN dari batch, bukan dikarang** (keputusan pemilik 2026-10-16):

- `commodity_id` dan `certification_status` 14 pemasok kanonik diisi dari batch kiriman mereka
  di `data/seed/sprint1_seed.json` (`app/seed/supplier_profile.py`): komoditas = total
  `quantity_kg` terbesar (seri → batch terbaru; masih seri → `NULL`), sertifikasi = nilai
  terbanyak (seri → `NULL`). Seeder mengisi **hanya bila kolomnya masih NULL** — nilai yang
  sudah ada tidak pernah ditimpa.
- Hanya **3 pemasok kanonik punya batch** (`Supplier A/B/C Cianjur` → `telur` + `haccp`); 11
  sisanya tidak punya batch sehingga tetap `NULL` (jujur, bukan nilai default).
- `capacity_kg_per_week` kanonik **tetap NULL**: batch hanya memuat berat per kiriman, bukan
  kapasitas mingguan — tidak ada satu pun sumbernya. Kolom ini terisi hanya untuk 21 baris demo.
- Catatan: baris kanonik **punya** koordinat di DB (di-backfill migrasi 012); yang tidak memuat
  koordinat hanyalah berkas seed kanoniknya.

Turunan "sedang mengirim" (`GET /suppliers`, kunci `shipping`) — keputusan pemilik 2026-10-16:
pemasok dianggap sedang mengirim bila punya batch dengan `usable_until >= sekarang`
(`app/core/supplier_shipping.py`). Bentuknya `{count, total_kg, until, commodities,
safety_fail_count}`; `null` bila tidak ada. Batch dengan `safety_status='fail'` tetap dihitung
dan dilaporkan lewat `safety_fail_count`.

### `road_routes`
Cache geometri rute **jalan** (OSRM) — migrasi `014_road_routes`, diisi saat seeding/sync
(`app/seed/road_routes.py`), TIDAK pernah diambil saat peta dibuka.

| Kolom | Tipe | Constraint |
|---|---|---|
| `id` | uuid | PK, `gen_random_uuid()` |
| `route_key` | varchar(120) | UNIQUE (`uq_road_routes_key`) — `profil:lat_a,lon_a>lat_b,lon_b` 4 desimal |
| `profile` | varchar(20) | NOT NULL, default `driving` |
| `origin_lat`/`origin_lon`/`destination_lat`/`destination_lon` | numeric(9,6) | NOT NULL |
| `distance_m`, `duration_s` | int | NOT NULL, CHECK ≥ 0 |
| `geometry` | jsonb | NOT NULL — GeoJSON LineString apa adanya dari OSRM (`[lon, lat]`) |
| `source` | varchar(20) | NOT NULL, CHECK `source = 'osrm'` (data pihak ketiga, disebut di UI) |
| `fetched_at` | timestamptz | NOT NULL, default `now()` |

Kunci memakai KOORDINAT (bukan id pemasok/lokasi): dua batch dari pemasok→tujuan yang sama
cukup satu rute, dan `UNIQUE` membuat sinkronisasi idempoten. Rute hanya diambil untuk
kiriman yang masih layak (`usable_until >= now`) — kiriman kedaluwarsa tidak pernah digambar.

Turunan rute di `GET /supplier-routes`: tiap baris membawa `straight_km` (haversine server,
Fase 7) dan `road` **atau** `road_missing_reason` (`belum_disinkron`,
`layanan_rute_tidak_terjangkau`, `rute_tidak_ditemukan`, `respons_rute_tidak_dikenal`).
Tidak ada kolom di tabel ini yang dipakai untuk menghitung ulang klaim jarak di UI.

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
| usable_until | TIMESTAMPTZ | nullable — `harvested_at + shelf_life_days × freshness_score`; batas layak pakai |
| dispatched_at | TIMESTAMPTZ | nullable — **jam barang meninggalkan pemasok** (migrasi `015_batch_dispatch`). `NULL` = belum berangkat, jadi estimasi tiba belum bisa dihitung — bukan jam nol. CHECK `batches_dispatch_after_harvest`: `dispatched_at IS NULL OR dispatched_at >= harvested_at`. Estimasi tiba TIDAK disimpan: dihitung saat baca dari `dispatched_at` + `road_routes.duration_s` (`app/core/journey.py`) |

### Penanda asal data (`origin`) & `generated_at` — migrasi `013_origin_generated_at`
Enam tabel deret waktu/operasional membawa penanda asal baris:

| Tabel | Kolom | Catatan |
|---|---|---|
| supply_records, demand_records, price_signals, menu_plans, batches, decisions | `origin` | TEXT NOT NULL, DEFAULT `'seed'`, CHECK `origin IN ('seed','demo')` |
| idem | `generated_at` | TIMESTAMPTZ NULLABLE — **NULL = baris kanonik** (ditulis tangan), terisi = baris yang dibuat generator deret waktu |

- Index `(origin, <kolom tanggal>)` per tabel (`ix_<tabel>_origin_<kolom>`).
- **Kunci upsert** (Fase 4): `uq_supply_records_loc_com_time_source`
  (location, commodity, recorded_at, **source**) dan `uq_demand_records_loc_com_time`; untuk
  `price_signals` dua index parsial `uq_price_signals_reference` (`source='pihps_reference'`) dan
  `uq_price_signals_quote` (`source='supplier_quote'`). `menu_plans` **tidak** punya kunci yang
  memuat `origin` → generator memakai `DO NOTHING` supaya hari kanonik menang.
- **`downgrade()` MENGHAPUS baris `origin='demo'` lebih dulu.** Tanpa kolom `origin`, baris demo
  akan terbaca sebagai kanonik dan menggeser jangkar angka; baris demo turunan dan bisa dibangun
  ulang dalam detik (`POST /demo/timeseries`).
- Arti praktisnya untuk demo: **`origin='demo'` = yang boleh dihapus** ("Bersihkan data demo" di
  tab Demo Control), `origin='seed'` = snapshot kanonik yang tidak boleh disentuh panel mana pun.

## 3. Keputusan & audit trail

### `supplier_exclusions`
Status administratif historis, lokal pada `scope_location_id` (SPPG penerima), terpisah dari `batches.safety_status`. `proposed`/`rejected` tidak mengubah eligibility; `active` berlaku tanpa expiry sampai keputusan restoration baru, evidence baru, dan approval matrix existing dieksekusi; `revoked` tetap tersimpan. Partial unique index menjaga satu active per supplier+scope. Administrative decisions selalu null quantity/cost.

| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| supplier_id | UUID | FK suppliers, NOT NULL |
| scope_location_id | UUID | FK locations, NOT NULL; receiving SPPG |
| status | TEXT | proposed\|active\|rejected\|revoked |
| reason | TEXT | NOT NULL |
| evidence_refs | JSONB | NOT NULL; IDs persisten, supplier-associated |
| source_decision_id | UUID | FK decisions, NOT NULL |
| restoration_decision_id | UUID | FK decisions, nullable |
| proposed_by | UUID | FK users, NOT NULL |
| approved_at/activated_at/revoked_at | TIMESTAMPTZ | nullable |
| revocation_reason | TEXT | nullable |

`batches.supplier_id` adalah binding kandidat; lokasi tidak boleh menggantikan identitas supplier. Execute mengunci baris supplier stabil sebelum membaca exclusion (race-safe walau belum ada exclusion row), mengulang safety dan binding check, lalu menulis ledger/PO paling banyak sekali.

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
| cost_breakdown | JSONB | nullable — komponen SDC `{purchase, transport, handling, expected_loss, freshness_risk, safety_penalty}`. Sejak Fase 7d (2026-10-15) ikut memuat pecahan angkut: `transport_linehaul` (SPPG sumber → SPPG tujuan), `transport_supplier_leg` (pemasok → SPPG sumber), `supplier_leg_km` (string km atau null), `supplier_leg_reference` (`supplier_coordinates` \| `supplier_coordinates_missing` \| `no_supplier`), plus alias `logistics` = total `transport`. Lihat `docs/ruling-2026-10-15-jarak-pemasok-biaya.md`. |
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
