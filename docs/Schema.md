# Schema.md — MealChain Guardian Database

**Engine:** PostgreSQL 16. Semua tabel pakai `id UUID DEFAULT gen_random_uuid()` sebagai PK
kecuali disebutkan lain. Semua tabel punya `created_at TIMESTAMPTZ DEFAULT now()`.

> **Status dokumen & persetujuan pemilik (Rules.md §5).** Rekonsiliasi 25 Okt 2026 terhadap
> katalog Postgres nyata (lihat `DATABASE_LINEAGE_AND_USAGE_AUDIT.md`, temuan F-02…F-04, F-09):
> tabel yang tidak ada dihapus, tabel yang belum terdokumentasi ditambahkan, dan kosakata
> status disamakan dengan `CHECK` di basis data. Perubahan ini **menunggu flag/persetujuan
> pemilik domain (Roy)** sebelum dianggap final. Angka baris sengaja tidak ditulis di sini
> supaya dokumen tidak cepat basi; lihat audit untuk angka terukur.

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
- **Isi tabel (diukur ulang 26 Okt 2026, lihat `docs/state-snapshot.md`)**: **60 baris** —
  sertifikasi `hygiene` 35, `haccp` 17, `none` 8. Catatan sejarah: setelah Fase 7 (2026-10-15)
  tabel berisi 14 pemasok kanonik (`data/seed/sprint1_seed.json`, nama pola `Supplier <Kota>-N`,
  tanpa koordinat — terikat 14 kutipan harga) + 21 pemasok demo (`data/seed/suppliers_demo.json`)
  = 35 baris; template demo sekarang menyemai 60. Angka 35 itu **historis**, jangan dipakai
  untuk memeriksa keadaan sekarang — pakai snapshot.
  Pada set 21 pemasok demo itu: **12 pemasok hub Jakarta** berkoordinat ABSOLUT di Jakarta + kota penyangga
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

### `menu_plans`
Rencana porsi per lokasi dan tanggal. **Tidak** menyimpan daftar hidangan/bahan —
komposisi menu hidup di luar basis data (deck/dokumen); tabel ini hanya jangkar porsi
yang dipakai `delivery_events` untuk menghitung sisa kebutuhan hari itu.

| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| location_id | UUID | FK → locations.id, NOT NULL, ON DELETE CASCADE |
| plan_date | DATE | NOT NULL |
| planned_portions | INTEGER | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| origin | VARCHAR | NOT NULL, DEFAULT 'seed', CHECK IN ('seed','demo') |
| generated_at | TIMESTAMPTZ | NULLABLE — NULL = baris kanonik (lihat §2b penanda asal) |
| demo_session_id | UUID | FK → demo_sessions.id, NULLABLE, ON DELETE SET NULL |

- **UNIQUE `(location_id, plan_date)`** — satu rencana per lokasi per hari.
- Tidak ada kunci unik yang memuat `origin`, jadi generator deret memakai `DO NOTHING`
  (baris kanonik menang) — lihat catatan penanda asal di bawah.

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
| temperature_log | JSONB | NOT NULL, DEFAULT '[]' — array of `{timestamp, temperature_c}` (kunci **`temperature_c`**, bukan `celsius`; diperbaiki 25 Okt 2026) |
| certification_status | TEXT | NOT NULL, DEFAULT 'none' — 'none'\|'hygiene'\|'haccp' |
| freshness_score | NUMERIC(3,2) | nullable, CHECK BETWEEN 0 AND 1 — diisi oleh `/freshness/evaluate` |
| safety_status | TEXT | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','pass','fail','needs_verification') |
| usable_until | TIMESTAMPTZ | nullable — `harvested_at + shelf_life_days × freshness_score`; batas layak pakai |
| dispatched_at | TIMESTAMPTZ | nullable — **jam barang meninggalkan pemasok** (migrasi `015_batch_dispatch`). `NULL` = belum berangkat, jadi estimasi tiba belum bisa dihitung — bukan jam nol. CHECK `batches_dispatch_after_harvest`: `dispatched_at IS NULL OR dispatched_at >= harvested_at`. Estimasi tiba TIDAK disimpan: dihitung saat baca dari `dispatched_at` + `road_routes.duration_s` (`app/core/journey.py`) |
| quarantine_status | TEXT | NOT NULL, DEFAULT 'none', CHECK IN ('none','quarantined','released','failed') — status karantina terpisah dari `safety_status` |
| quarantine_reason | TEXT | nullable — alasan karantina, wajib diisi saat status `quarantined` (dijaga aplikasi) |
| quarantined_at | TIMESTAMPTZ | nullable — saat masuk karantina |
| quarantine_updated_at | TIMESTAMPTZ | nullable — saat status karantina terakhir berubah |
| quarantine_actor_id | UUID | FK → users.id, nullable — siapa yang memutuskan |
| demo_session_id | UUID | FK → demo_sessions.id, nullable, ON DELETE SET NULL |

**Aturan lintas kolom yang dijaga aplikasi (bukan trigger):** batch berstatus
`quarantine_status = 'quarantined'` atau `safety_status = 'fail'` tidak boleh masuk stok
lewat penerimaan, dan tidak boleh menjadi sumber eksekusi keputusan
(`app/core/safety_gate.py`). Basis data hanya menolak bila CHECK/FK yang cocok; tidak ada
trigger yang menegakkan aturan ini.

### Penanda asal data (`origin`) & `generated_at` — migrasi `013_origin_generated_at`
**Sembilan** tabel membawa penanda asal baris (semula dokumen menulis "enam"; tiga tabel
berikutnya ditambahkan belakangan dan baru dicatat 25 Okt 2026):

| Tabel | Kolom | Catatan |
|---|---|---|
| supply_records, demand_records, price_signals, menu_plans, batches, decisions, delivery_events, disposal_events, sap_mock_purchase_orders | `origin` | VARCHAR/TEXT NOT NULL, DEFAULT `'seed'`, CHECK `origin IN ('seed','demo')` |
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

## 2b. Penerimaan, pengiriman, pembuangan

Tiga tabel ini sebelumnya tidak terdokumentasi padahal dipakai UI (Keamanan Pangan,
papan pengiriman, Surplus & Limbah). Ditambahkan 25 Okt 2026.

### `batch_receipts`
Penerimaan barang per batch di lokasi penerima. Satu batch bisa punya beberapa baris
(mis. penerimaan bertahap); keputusan penerimaan keluar dari sini.

| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| batch_id | UUID | FK → batches.id, NOT NULL, ON DELETE CASCADE |
| checked | JSONB | NOT NULL, DEFAULT '{}' — hasil pemeriksaan (suhu, kondisi, dokumen) |
| other_note | TEXT | nullable |
| recorded_by | UUID | FK → users.id, NOT NULL — pemeriksa |
| recorded_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| demo_session_id | UUID | FK → demo_sessions.id, NULLABLE, ON DELETE SET NULL |
| status | TEXT | NOT NULL, DEFAULT 'menunggu', CHECK IN ('menunggu','disetujui','ditolak') |
| reviewed_by | UUID | FK → users.id, NULLABLE, ON DELETE SET NULL |
| reviewed_at | TIMESTAMPTZ | nullable |
| review_note | TEXT | nullable |
| supply_record_id | UUID | FK → supply_records.id, NULLABLE, ON DELETE SET NULL — baris stok yang lahir dari penerimaan ini |

- **Status `disetujui` hanya boleh menghasilkan tepat satu baris stok.** Penerimaan
  menyetujui → menulis `supply_records` → menyimpan `supply_record_id`; persetujuan
  ganda ditolak aplikasi (bukan oleh constraint).
- Penolakan (`ditolak`) tidak menulis stok sama sekali.
- Gerbang keselamatan: batch `fail`/`quarantined`/kedaluwarsa/bukti suhu tidak lengkap
  ditolak `409` sebelum stok ditulis (`app/core/safety_gate.py`).

### `delivery_events`
Peristiwa porsi terkirim untuk satu rencana menu; dipakai menghitung sisa kebutuhan hari itu.

| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| menu_plan_id | UUID | FK → menu_plans.id, NOT NULL, ON DELETE CASCADE |
| delivered_portions | INTEGER | NOT NULL |
| status | TEXT | NOT NULL, DEFAULT 'delivered' — **tidak ada CHECK**; nilai lain tidak ditolak basis data |
| delivered_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| origin | VARCHAR | NOT NULL, DEFAULT 'seed', CHECK IN ('seed','demo') |
| generated_at | TIMESTAMPTZ | NULLABLE |
| demo_session_id | UUID | FK → demo_sessions.id, NULLABLE, ON DELETE SET NULL |
| source_ref | TEXT | nullable — kunci idempotensi (mis. `receipt:<uuid>`), dijaga aplikasi |

### `disposal_events`
Pembuangan/limbah: bahan yang tidak terpakai beserta alasan dan mitra pembuangan.

| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| location_id | UUID | FK → locations.id, NOT NULL, ON DELETE CASCADE |
| commodity_id | UUID | FK → commodities.id, NOT NULL, **ON DELETE RESTRICT** (komoditas tidak boleh hilang bila sudah ada limbah tercatat) |
| quantity_kg | NUMERIC(10,2) | NOT NULL |
| reason | TEXT | NOT NULL |
| disposed_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| origin | VARCHAR | NOT NULL, DEFAULT 'seed', CHECK IN ('seed','demo') |
| generated_at | TIMESTAMPTZ | NULLABLE |
| partner_name | TEXT | nullable — mitra pembuangan/pengolah |
| demo_session_id | UUID | FK → demo_sessions.id, NULLABLE, ON DELETE SET NULL |
| source_ref | TEXT | nullable — idempotensi |

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
| decision_type | TEXT | NOT NULL — 'regional_balance'\|'price_anomaly'\|'safety_disruption'\|'supplier_exclusion'\|'supplier_exclusion_restoration'\|'supplier_procurement' (enam nilai, disamakan dengan CHECK 25 Okt 2026) |
| status | TEXT | NOT NULL, DEFAULT 'proposed', CHECK IN ('proposed','verifier_flagged','pending_approval','approved','rejected','executed','review_only') |
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
| rejection_reason | TEXT | nullable — alasan penolakan terakhir |
| iteration | INTEGER | NOT NULL, DEFAULT 1 — usulan ulang menaikkan nomor iterasi |
| supersedes_id | UUID | FK → decisions.id, nullable — keputusan yang digantikan usulan ini |
| demo_case | TEXT | nullable — penanda skenario demo (bukan data operasional) |
| origin | VARCHAR | NOT NULL, DEFAULT 'seed', CHECK IN ('seed','demo') |
| generated_at | TIMESTAMPTZ | nullable — NULL = baris kanonik |
| supplier_id | UUID | FK → suppliers.id, nullable — diisi untuk keputusan pengadaan/eksklusi pemasok |
| demo_session_id | UUID | FK → demo_sessions.id, nullable, ON DELETE SET NULL |

- **Tidak ada kolom `po_number`.** PO yang terbit ditautkan lewat
  `sap_mock_purchase_orders.decision_id` (dan payload blok ledger), bukan dari tabel ini.
- `quantity_kg` **nullable**: keputusan administratif (eksklusi/restorasi pemasok) selalu
  null kuantitas dan biaya. CHECK hanya menolak nilai `<= 0` bila kolom terisi.

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
| step_name | TEXT | NOT NULL — 'DETECT'\|'VERIFY'\|'TRACE'\|'PREDICT'\|'OPTIMIZE'\|'DECIDE'\|'SUPERVISE'\|'ACT'\|'LEARN' (CHECK `agent_traces_step_name_check`; `SUPERVISE` sempat hilang dari dokumen, dikembalikan 25 Okt 2026) |
| tool_called | TEXT | nullable |
| input_summary | JSONB | nullable |
| output_summary | JSONB | nullable |
| duration_ms | INTEGER | nullable |
| step_at | TIMESTAMPTZ | NOT NULL |
| run_id | UUID | nullable — id satu eksekusi agen; langkah-langkah satu run berbagi `run_id` |
| agent_name | TEXT | nullable — agen/worker yang menulis langkah |
| confidence | DOUBLE PRECISION | nullable — keyakinan langkah (bila dilaporkan) |
| citations | JSONB | nullable — rujukan bukti yang dipakai langkah |

- **Urutan bukan jaminan basis data.** `step_at` diisi aplikasi; `persist_trace_steps()`
  menjamin urutan di dalam satu panggilan, sedangkan orkestrator memanggilnya per langkah.
  Klien yang butuh urutan pipeline harus memakai urutan langkah baku, bukan `step_at` saja.

### `approvals`
| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| decision_id | UUID | FK → decisions.id, NOT NULL |
| approved_by | UUID | FK → users.id, NOT NULL |
| approved | BOOLEAN | NOT NULL |
| comment | TEXT | nullable |
| approved_at | TIMESTAMPTZ | NOT NULL |

### KPI tidak dipersistensikan

Dokumen ini sebelumnya memuat tabel `kpi_snapshots` (kolom `kpi_name`, `scope`, `value`,
`computed_at`). **Tabel itu tidak ada di basis data dan tidak ada di kode** — dihapus dari
dokumen 25 Okt 2026 (audit lineage F-02). KPI dihitung saat baca dari tabel operasional
(`app/services/kpi_service.py`), sehingga tidak ada baris KPI yang bisa basi atau perlu
dibersihkan. Bila kelak KPI perlu disimpan, itu harus lewat migrasi baru + model + tes,
bukan dengan menghidupkan kembali bagian dokumen ini.

## 3b. Sesi demo & ledger (append-only)

Ditambahkan 25 Okt 2026 (sebelumnya tidak terdokumentasi).

### `demo_sessions`
Penanda kepemilikan baris demo, jam simulasi, dan masa berlaku sesi. Baris demo diberi
`demo_session_id`; pembersihan sesi menyaring lewat kolom itu (dan `origin='demo'` bila
kolomnya ada).

| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| status | VARCHAR | NOT NULL, DEFAULT 'active', CHECK IN ('active','expired','ended') |
| started_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| expires_at | TIMESTAMPTZ | NOT NULL — batas sesi; `DEMO_SESSION_MINUTES`/`MAX_MINUTES` menentukan nilainya |
| anchor_now | TIMESTAMPTZ | NOT NULL — "sekarang" versi simulasi yang dipakai seluruh UI demo |
| ended_at | TIMESTAMPTZ | nullable — diisi saat sesi diakhiri manual |
| template_version | TEXT | nullable — versi template data demo yang membangun sesi ini |
| created_by | UUID | FK → users.id, NULLABLE, ON DELETE SET NULL |
| mode | TEXT | NOT NULL, DEFAULT 'replay', CHECK IN ('replay','realtime') — migrasi `040_session_modes_and_ownership` |
| evaluation_anchor | TIMESTAMPTZ | NOT NULL, DEFAULT `2026-10-08 12:00:00+00` — jangkar waktu EVALUASI (freshness, umur dataset, timestamp simulasi), bukan waktu kejadian operator |
| dataset_version | TEXT | nullable — identitas versi dataset sesi (mis. `kanon-2026-10-08T12:00:00Z`) |

- **Tidak ada sesi aktif** berarti alur yang menuntut sesi (`/demo/session/*`,
  `/demo/template/rebuild`) menolak dengan `409`. Itu perilaku yang diinginkan, bukan bug.
- Sesi `expired` tetap disimpan (riwayat), tidak dihapus.
- **Satu sesi aktif** dijamin DB lewat indeks unik parsial `uq_demo_sessions_satu_aktif`
  (migrasi `032`), bukan hanya kunci `asyncio` satu proses.
- **Dua sumbu waktu:** `evaluation_anchor` dipakai evaluasi; `approvals`, PO, dan
  `batch_receipts` tetap memakai jam dinding (`now()`) supaya Decision Time bukan selisih hari.

### `demo_session_id` — daftar tabel pemilik baris demo (terukur 27 Okt 2026)

`demo_session_id UUID NULL → demo_sessions.id ON DELETE SET NULL` ada di **13 tabel**:

```
batches · batch_receipts · decisions · delivery_events · demand_records · disposal_events ·
menu_plans · price_signals · road_routes · sap_mock_material_stock · sap_mock_purchase_orders ·
supplier_exclusions · supply_records
```

`NULL` = baris operasional/seed; `NOT NULL` = baris milik satu sesi demo. KPI memakai aturan ini
langsung: `include_demo=false` menyaring `demo_session_id IS NULL`, `include_demo=true` menyaring
ke **satu** `demo_session_id` eksplisit (tidak ada jalur "sesi terbaru").


### `ledger_blocks`
Rantai hash append-only untuk bukti tindakan (create/verify/approve/reject/execute).
Tidak ada FK ke tabel domain: **blok sengaja hidup lebih lama daripada entitasnya**.

| Kolom | Tipe | Constraint |
|---|---|---|
| id | UUID | PK |
| height | BIGINT | NOT NULL, **UNIQUE** — posisi blok dalam rantai |
| prev_hash | TEXT | NOT NULL, CHECK `length(prev_hash) = 64` |
| payload_hash | TEXT | NOT NULL, CHECK `length(payload_hash) = 64` — `sha256(prev_hash ‖ payload)` |
| action | TEXT | NOT NULL — 'decision.created'\|'verify'\|'approve'\|'reject'\|'execute' (tidak ada CHECK; dijaga aplikasi) |
| entity_id | UUID | nullable — id keputusan/batch/entitas yang dirujuk; **tidak** ada FK, jadi bisa menunjuk baris yang sudah dihapus |
| actor_id | UUID | nullable — pelaku; tanpa FK dengan alasan yang sama |
| payload | TEXT | NOT NULL — JSON kanonik (kunci terurut) yang ikut di-hash |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| generation | INTEGER | NOT NULL, DEFAULT 1 — penanda "zaman" ledger setelah reset demo |

- Verifikasi rantai (`verify_chain`) murni baca: memeriksa `prev_hash` bersambung dan
  `payload_hash` cocok, lalu melaporkan **keterkaitan** blok secara terpisah
  (`linked_blocks`, `orphan_blocks`, `linked_ratio`, `coverage_warning`).
- Keterkaitan bisa turun tanpa rantai rusak: hapus entitas → bloknya menjadi yatim.
  `valid=true` **tidak** berarti semua blok bisa ditelusuri ke entitas yang masih ada.

### `ledger_meta`
Satu baris (`id` kecil) yang menyimpan generasi aktif dan kapan terakhir diperbarui.

| Kolom | Tipe | Constraint |
|---|---|---|
| id | SMALLINT | PK — selalu `1` |
| generation | INTEGER | NOT NULL, DEFAULT 1 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

`bump_generation()` menaikkan generasi **tanpa** harus menulis blok; karena itu nomor
generasi tidak boleh dibaca sebagai "jumlah reset" (pernah ada generasi tanpa blok).

## 3c. Kebijakan komoditas, karantina, dan tingkat bukti (as-built 27 Okt 2026)

Ditambahkan Fase 3/4/8 dan didokumentasikan Fase 12. Semua kolom di bawah **sudah ada di DB**
(migrasi `035_commodity_policy*`, `036`, `037`), bukan usulan perubahan kontrak.

### `commodity_policies` — kebijakan berversi per komoditas (migrasi `041`)

| Kolom | Tipe | Arti |
|---|---|---|
| id | UUID | PK |
| commodity_id | UUID | FK → commodities.id |
| cold_chain_required | BOOLEAN | `false` = komoditas ambient (beras): excursion **tidak** diukur |
| safe_temp_min_c / safe_temp_max_c | NUMERIC | rentang aman; `NULL` untuk ambient |
| shelf_life_days | NUMERIC | masa layak dasar pembentuk `usable_until` |
| min_temperature_samples | INTEGER | jumlah sampel minimum agar bukti suhu dianggap lengkap |
| max_observation_age_minutes | INTEGER | usia maksimum sampel terakhir; lebih tua = observasi basi |
| max_excursion_minutes | NUMERIC | ambang menit excursion yang membuat safety `fail` |
| policy_version / policy_basis | TEXT | versi + asal angka (mis. `sim-2026-10-27.v1`) |
| policy_kind | VARCHAR | `simulated_policy` selama belum divalidasi domain owner; `unavailable` bila tanpa dasar |
| is_active | BOOLEAN | baris aktif yang dipakai `policy_for()` |

Aturan: komoditas tanpa baris aktif **ditolak** (`KeyError`), bukan diberi default 0–8 °C.

### `batches` — karantina dan bukti suhu (migrasi `036`, `041`)

| Kolom | Arti |
|---|---|
| quarantine_status | `none` · `quarantined` · `released` · `failed` — `quarantined`/`failed` tidak pernah jadi stok usable |
| quarantined_at / quarantine_updated_at | kapan transisi terjadi |
| quarantine_actor_id | siapa yang menahan/melepas (FK → users.id) |
| quarantine_reason | alasan manusia, wajib saat menahan |
| temperature_log | JSONB log observasi; **kosong ≠ `pass`** → `on_hold` / `temperature_evidence_incomplete` |
| origin | `seed` · `demo` (penanda asal baris; migrasi `013`) |

Setiap transisi karantina menulis satu blok `ledger_blocks` — pertanyaan "siapa menahan batch ini
dan kapan" punya jawaban yang bisa diverifikasi.

### `batch_receipts` — titik akhir rantai

| Kolom | Arti |
|---|---|
| checked | JSONB ceklis penerimaan yang diisi manusia |
| status | status penerimaan (`menunggu` → diterima/ditahan) |
| review_note / reviewed_by / reviewed_at | jejak review server-side |
| supply_record_id | kaitan ke pasokan yang bertambah bila diterima |
| demo_session_id | kepemilikan baris demo |

`can_receive` / `can_quarantine` **tidak** disimpan: keduanya dihitung server
(`services/receipt_gate.py`) dari pagar endpoint yang sama.

### Tingkat bukti (provenance) tidak dipersistensikan

`provenance` KPI dibentuk saat baca (`services/kpi_service.py`): `source`, `period`, `sample_count`,
`coverage`, `definition`, `formula`, `method_version`, `evidence_kind`, `baseline`. Karena tidak
disimpan, ia tidak bisa "basi" terhadap datanya — tetapi juga tidak bisa dijadikan bukti historis;
untuk itu dipakai blok `ledger_blocks` + snapshot `docs/state-snapshot.md`.

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

Daftar ini disamakan dengan nama indeks yang **benar-benar ada** di katalog Postgres
(25 Okt 2026, audit lineage F-09). Dokumen sebelumnya menyebut `idx_agent_traces_decision`
dan `idx_kpi_name_scope` — keduanya tidak ada: yang pertama bernama
`ix_agent_traces_decision_id` (satu kolom, bukan gabungan), yang kedua mustahil karena
tabel `kpi_snapshots` tidak ada.

```sql
CREATE INDEX idx_supply_location_commodity ON supply_records(location_id, commodity_id);
CREATE INDEX idx_demand_location_commodity ON demand_records(location_id, commodity_id);
CREATE INDEX idx_batches_safety_status ON batches(safety_status);
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX ix_agent_traces_decision_id ON agent_traces(decision_id);
```

**Celah indeks (ditutup 26 Okt 2026).** Audit lineage §13.3 (F-07) menemukan 22 foreign
key tanpa indeks yang menjadikan kolomnya kolom pertama. Migrasi
`033_indeks_fk_hilang` menambahkan semuanya (`ix_<tabel>_<kolom>`), dan
`tests/test_fk_index_coverage.py` membaca katalog supaya FK baru tidak bisa lahir
tanpa indeks. Ukuran: 22 indeks tambahan, semuanya satu kolom.

**Bloat indeks bukan urusan skema.** Pada data demo, indeks `supply_records` dan
`price_signals` pernah membengkak 15× ukuran heap (33 MB indeks vs 2,2 MB heap) setelah
siklus semai-hapus berulang. Itu bukan cacat definisi indeks: `REINDEX TABLE
CONCURRENTLY` memulihkannya (total DB 93 MB → 22 MB). Jalankan REINDEX berkala pada DB
demo, jangan menambah/menghapus indeks untuk "mengobati" bloat.

## 6. Catatan integritas

- `batches.safety_status = 'fail'` → batch tersebut TIDAK BOLEH muncul di hasil
  `/balance/recommend` sebagai kandidat (enforced di application layer `core/constraints.py`,
  bukan cuma di query — defense in depth)
- `decisions.status = 'executed'` hanya boleh dicapai lewat `approvals` dengan `approved = true`
  terlebih dahulu — tidak ada jalur langsung `proposed → executed`
