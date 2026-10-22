# Laporan Perbaikan Database — Mode DEFAULT/DEMO, Cakupan Data, dan Joule

Tanggal: 22 Oktober 2026
Branch: `feature/db-modes-demo-coverage`
Ruang lingkup: `E:\hackathon\HackathonAWS\mealchain-guardian` (backend FastAPI + Postgres + Alembic,
frontend Next.js, `sap-joule/` jembatan A2A).

---

## 1. Ringkasan: masalah dan akar penyebab

Keluhan awal "database tidak sesuai kebutuhan project" ternyata **bukan satu bug**, melainkan
lima cacat yang saling menutupi. Semuanya dibuktikan dengan menjalankan sistem, bukan membaca kode.

| # | Gejala yang bisa dilihat | Akar penyebab (terukur) |
|---|---|---|
| 1 | Overview menampilkan `0 kg`, semua panel kosong, Joule menjawab "belum ada data" | Database demo hanya berisi baris kanonik (`origin='seed'`); deret waktu/aktivitas demo tidak pernah dibangun di DB itu. Tidak ada konsep "mode database", jadi tidak ada cara memastikan isi DB sesuai yang diharapkan frontend |
| 2 | `init-demo` gagal: `duplicate key value violates unique constraint "commodities_name_key"` | Id referensi di DB lama memakai UUID acak versi awal, bukan `stable_uuid(nama)`; seeder kanonik menyisipkan ulang berdasarkan id kanonik sehingga bentrok pada `name` |
| 3 | `GET /batches` dan `GET /balance/map` balas **500**; tombol "Siapkan data demo" gagal | `supplier_exclusions.source_decision_id` dan `restoration_decision_id` memakai FK **NO ACTION**, sehingga penghapusan keputusan (bagian dari purge template demo) ditolak `ForeignKeyViolationError` |
| 4 | Data demo tidak bisa dibersihkan tanpa menyentuh data kerja | PO (`sap_mock_purchase_orders`) satu-satunya tabel bisnis tanpa penanda `origin` |
| 5 | Jawaban Joule lambat / query memindai seluruh tabel | `sap_mock_purchase_orders.decision_id`, `agent_traces.decision_id`, `approvals.decision_id`, `decision_evidence.decision_id`, `batch_receipts(status, recorded_at)` tanpa index, padahal semuanya dipakai setiap jawaban |

Cacat lain yang ditemukan saat verifikasi dan ikut diperbaiki:

- **Tombol "Siapkan data demo" menghapus cakupan**: endpoint `POST /demo/template/rebuild` mem-purge
  seluruh baris demo lalu hanya membangun ulang template. Terukur: `supply_records` 5.200 → 40,
  PO demo 20 → 12, penerimaan 5 → 0. Sekarang langkah itu juga membangun ulang deret waktu,
  aktivitas, dan pelengkap cakupan.
- **3 dari 13 skill Joule tidak punya scenario** (`supplier_directory`, `receipts_queue`,
  `quarantine_status`), jadi tidak mungkin dipicu dari chat meski jembatannya mendukung.
- **Akun baca untuk Joule**: jembatan yang login sebagai `sppg_head` ditolak `GET /admin/locations`
  (403). Akun baca yang benar adalah `bgn_monitor`, sesuai aturan read-only repo.

## 2. Perubahan schema (migrasi `028_demo_marker_indexes`)

Satu migrasi baru, reversible (`upgrade`/`downgrade`), dijalankan dari database kosong dan dari
database lama.

| Objek | Perubahan | Alasan |
|---|---|---|
| `sap_mock_purchase_orders.origin` | kolom `varchar(16) NOT NULL DEFAULT 'seed'` + CHECK `IN ('seed','demo')` | penanda data demo agar `reset-demo` tepat sasaran |
| `ix_sap_mock_purchase_orders_decision_id` | index baru | `GET /sap/purchase-orders?decision_id=`, skill `purchase_order` |
| `ix_agent_traces_decision_id` | index baru | `GET /decisions/{id}/traces`, skill `decision_evidence` |
| `ix_approvals_decision_id` | index baru | `GET /decisions/{id}/approval-summary`, skill `approval_queue` |
| `ix_decision_evidence_decision_id` | index baru | `GET /decisions/{id}/compliance` |
| `ix_batch_receipts_status_recorded` | index baru | `GET /receipts/menunggu`, skill `receipts_queue` |
| `supplier_exclusions_source_decision_id_fkey` | NO ACTION → **CASCADE** | kolom NOT NULL; eksklusi lahir dari keputusan (pola sama dengan PO, migrasi 027) |
| `supplier_exclusions_restoration_decision_id_fkey` | NO ACTION → **SET NULL** | kolom opsional; pencabutan tetap tercatat walau keputusan pemulihnya hilang |

Tidak ada tabel/kolom yang dihapus. Skema lain sudah memadai: 21 tabel SQLAlchemy, penanda
`origin`/`demo_session_id` sudah ada di tabel deret waktu sejak migrasi 017/024/025.

Dua tabel ada di DB tetapi tidak punya model SQLAlchemy: `ledger_blocks` (ditulis lewat SQL di
layanan ledger) dan `alembic_version`. Dicatat, tidak diubah — ledger bersifat append-only.

## 3. Dua skill yang dibuat

### 3.1 `.claude/skills/db-mode/SKILL.md`
Memilih dan menyiapkan mode database. Mode dibaca dari **isi** database (`mode_isi`) dan
dibandingkan dengan `DB_MODE` (`mode_env`); bila tidak cocok, `status` melaporkannya.

| Mode | Isi |
|---|---|
| **DEFAULT** | schema + referensi/master: komoditas, 10 lokasi/SPPG, akun RBAC. Tabel bisnis kosong → empty state yang benar |
| **DEMO** | DEFAULT + dataset demo penuh (kanonik, deret 1 Sep–5 Nov, aktivitas, kasus per kota, pelengkap cakupan) |

Perintah persis (dari akar repo):

```bash
bash scripts/db-mode.sh status
DB_MODE=default bash scripts/db-mode.sh init-default
DB_MODE=demo    bash scripts/db-mode.sh init-demo          # --refresh untuk deret hari ini
DB_MODE=default bash scripts/db-mode.sh reset-demo --yes
```

Pengaman: `reset-demo` menolak host non-lokal dan menolak `DB_MODE_ENV=production`, serta menolak
tanpa `--yes`. Semua perintah idempoten.

### 3.2 `.claude/skills/demo-data-builder/SKILL.md`
Cara membangun/menyegarkan dataset demo: deterministik (`stable_uuid`), tanggal relatif hari ini,
urutan insert menjaga FK, semua baris bisnis `origin='demo'`, plus checklist cakupan (enam
`decision_type`, tujuh status keputusan, empat status keamanan/karantina, tiga status penerimaan,
empat status eksklusi, tiga status PO, limbah dengan/tanpa mitra, jejak pipeline, angka ekstrem,
teks panjang/Unicode, tanggal lampau/hari ini/masa depan).

## 4. Cakupan data demo

Sesudah `DB_MODE=demo bash scripts/db-mode.sh init-demo` (dan setelah tombol rebuild yang diperbaiki):

| Tabel | Baris |
|---|---|
| commodities / locations / users (referensi) | 4 / 10 / 7 |
| suppliers | 61 |
| batches | 125 |
| batch_receipts | 7 |
| decisions | 45 |
| approvals | 13 |
| decision_evidence | 18 |
| agent_traces | 34 |
| supply_records | 5.240 |
| demand_records | 1.360 |
| price_signals | 6.015 |
| menu_plans | 660 |
| delivery_events | 360 |
| disposal_events | 83 |
| supplier_exclusions | 6 |
| sap_mock_purchase_orders | 20 (7 lahir dari keputusan) |
| sap_mock_material_stock | 40 |
| demo_sessions | 2 (status `ended`, `expired`) |

Cakupan enum (dihitung `group by` dari DB, bukan klaim):

- `decision_type`: 6/6 — regional_balance, price_anomaly, safety_disruption, supplier_exclusion,
  supplier_exclusion_restoration, supplier_procurement.
- `decision.status`: 7/7 — proposed, verifier_flagged, pending_approval, approved, rejected,
  executed, review_only.
- `batches.safety_status` 4/4, `quarantine_status` 4/4, `batch_receipts.status` 3/3,
  `supplier_exclusions.status` 4/4, `sap_mock_purchase_orders.status` 3/3.

Matriks cakupan lengkap ada di `docs/db-coverage-matrix.md`, dihasilkan ulang oleh
`scripts/audit/db_coverage.py` dari kondisi live (route, skema, respons HTTP, dan satu query SQL
per baris). Angka ringkasnya (run terakhir, data DEMO final): 11 layar sidebar, 36 baris matriks,
**33 baris terbukti penuh, 3 baris GAP**, 612 sel state tampilan (287 terbukti, 294 GAP, 31 N/A),
**3 enum** yang masih tidak sinkron antara kode, CHECK constraint, dan nilai di DB.

**GAP yang jujur harus disebut:**

1. Tiga baris GAP = tiga komponen yang ada di repo tetapi **tidak dirender layar mana pun** —
   "Konsol operasi — snapshot kondisi", "Konsol operasi — analisis agent & usulan",
   "Supplier governance (eksklusi/pemulihan)". Ini cacat frontend, bukan data; tidak saya ubah
   karena di luar lingkup database. (Sebelum data demo dibangun ulang sempat terbaca 4 GAP karena
   satu penanda data belum ada; sekarang 3.)

2. 294 sel state tampilan (mis. `kosong`, `filter_tanpa_hasil`, `error`) tidak bisa dibuktikan
   lewat baris database — perlu interaksi UI atau tes komponen. Yang bisa dibuktikan lewat data
   (volume > 1 halaman, angka ekstrem, teks panjang/Unicode, tanggal lampau/hari ini/masa depan)
   sudah disediakan builder.
3. 3 enum masih tidak sinkron antara kode, CHECK constraint, dan nilai yang benar-benar ada di DB
   (turun dari 9 setelah builder mengisi seluruh nilai yang sah). Daftar rincinya di §3.1 dan §5.4
   matriks; yang berdampak pada kontrak tulis perlu keputusan pemilik domain.

## 5. Perubahan backend

| Berkas | Perubahan |
|---|---|
| `backend/app/core/config.py` | setelan `db_mode: str = "default"` (mode yang diharapkan) |
| `backend/app/seed/reference.py` (baru) | seeder referensi saja (komoditas, lokasi, akun) — isi mode DEFAULT |
| `backend/app/seed/db_mode.py` (baru) | CLI `status`/`init-default`/`init-demo`/`reset-demo`, pengaman, normalisasi id referensi, laporan JSON |
| `backend/app/seed/demo_extra.py` (baru) | pelengkap cakupan demo: semua enum/status, bukti konsisten & tidak, jejak pipeline, PO dari keputusan, penerimaan menunggu/ditolak, karantina, eksklusi 4 status, limbah dengan/tanpa mitra, menu masa depan, harga anomali, sesi `ended`/`expired`, pemasok Unicode |
| `backend/app/services/demo_template_reset.py` | rebuild tidak lagi menghapus cakupan: deret waktu + aktivitas + pelengkap dibangun ulang sesudah template |
| `backend/app/seed/demo_activity.py`, `demo_template.py`, `jakarta_lengkap.py` | PO yang ditulis jalur demo memakai `origin="demo"` |
| `backend/app/models/sap_mock.py`, `supplier_exclusions.py` | kolom `origin` + aturan FK sesuai migrasi 028 |
| `scripts/db-mode.sh` (baru) | pembungkus `docker compose exec` dengan DSN, tanpa mencetak sandi |
| `.env.example` | blok `DB_MODE` + perintah penyiapan |

Perilaku dua mode sudah diuji pada endpoint yang dipakai UI: mode DEFAULT mengembalikan bentuk
kosong yang benar (`{"count":0,"total":0,"items":[]}`, `items:[]`, `routes:[]`) tanpa 500; mode DEMO
mengembalikan data penuh.

## 6. Integrasi SAP Joule

Yang diperiksa dan diubah:

- **Skill vs scenario**: server A2A punya 13 skill; skenario Joule sebelumnya 10. Ditambahkan
  `direktori_pemasok.yaml`, `antrean_penerimaan.yaml`, `status_karantina.yaml` (gaya sama:
  deskripsi Inggris, kata pemicu Indonesia, `target: mealchain_query_function`).
  `capability.sapdas.yaml` naik `1.3.0 → 1.4.0`.
- **Peta skill**: `sap-joule/docs/peta-skill-joule.md` (413 baris) memetakan 13 skill → endpoint
  backend → tabel/kolom yang harus berisi data → contoh pertanyaan → bentuk jawaban.
- **Uji nyata**: `sap-joule/scripts/uji-pertanyaan-joule.py` mengirim 14 pertanyaan meniru Joule
  (JSON-RPC `message/send` ke jembatan A2A), bukan memanggil backend langsung. Hasil:
  **DEMO 14/14 lulus**, **DEFAULT 14/14 lulus** (jawaban "belum ada data … belum bisa diambil"
  yang jujur, bukan nol palsu). Berkas hasil: `docs/qa/joule-pertanyaan-2026-10-22-demo.json` (14/14) dan
 `docs/qa/joule-pertanyaan-2026-10-22-default.json` (14/14).
- **Bug nyata yang ditemukan uji ini**:
  1. `/batches` 500 akibat FK eksklusi (§2);
  2. `403` `/admin/locations` saat jembatan login sebagai `sppg_head` — akun baca harus
     `bgn_monitor` (pola repo: `/admin/*` = BGN);
  3. kolom "Batch" pada jawaban karantina selalu `—` karena laporan membaca `code`/`batch_code`
     yang tidak dikirim `/batches` → kini jatuh ke potongan `id` (`467caaad`);
  4. `excluded_at_hub` di `/suppliers` membandingkan nama **lokasi pemasok** dengan daftar hub
     eksklusi, sehingga penanda "dikecualikan di hub" tidak pernah menyala walau eksklusi aktif;
     kini `bool(scopes)` (terukur: 2 dari 61 pemasok bertanda, sebelumnya 0);
  5. agent card jembatan masih `1.3.0` sementara capability `1.4.0` → disamakan.
  Sisa keterbatasan (bukan bug): tabel direktori pemasok dipangkas, sehingga pemasok bertanda
  eksklusi bisa berada di luar baris yang tampil pada satu jawaban.
- Tes `sap-joule/a2a_server/tests`: **123 passed, 14 skipped** (dijalankan dengan
  `a2a_server/requirements.txt` yang mematok `a2a-sdk[http-server]==0.3.25`; versi `a2a-sdk` bebas
  gagal impor `MessageSendParams`).

**Batasan pengujian yang harus disebut:** tenant SAP Joule dan destination BTP tidak dapat
dijalankan dari lingkungan ini (tanpa kredensial SAP). Yang diuji adalah kontrak yang dipakai Joule:
payload A2A, pemilihan skill deterministik, artefak `mealchain_report`, dan data yang menjawabnya.
Konfigurasi destination (`MEALCHAIN_AGENT_01`) tidak diubah.

## 7. Hasil verifikasi

| Verifikasi | Hasil |
|---|---|
| Migrasi dari database **kosong** | `init-default` pada DB baru: `alembic=028_demo_marker_indexes`, 4/10/7 baris referensi, semua tabel bisnis 0 |
| Migrasi dari database **lama** | DB demo lama (id referensi menyimpang) berhasil dinormalisasi lalu dibangun ulang; tidak ada error |
| `init-default` | berhasil, idempoten |
| `init-demo` dua kali | **21/21 tabel berjumlah identik** (tidak menggandakan) |
| `reset-demo` | 13.884 baris dihapus, tersisa hanya referensi (4 komoditas, 10 lokasi, 7 akun) |
| Guard `reset-demo` | tanpa `--yes` hanya menjelaskan rencana; host non-lokal ditolak |
| Tombol "Siapkan data demo" (rebuild) | HTTP 200, 34 detik; sesudahnya supply 5.240, price 6.015, PO 20 (7 dari keputusan), receipts 7, decisions 45 |
| Frontend mode DEMO | data penuh tanpa error console; angka utama: shortage −780 kg, surplus 300 kg, 11 keputusan, 7 pengiriman, pin pemasok di peta |
| Frontend mode DEFAULT | empty state benar ("Belum ada data …", 0 kg), tanpa error/NaN, tanpa spinner menggantung |
| 14 pertanyaan Joule DEMO / DEFAULT | 14/14 dan 14/14 |
| `ruff` berkas yang diubah | bersih (kecuali `N818` lama pada `Sibuk` di `demo_template_reset.py`, sudah ada sebelum pekerjaan ini) |
| Gerbang backend terpisah (`scripts/gerbang-db-terpisah.sh`) | **1282 passed, 18 skipped, 0 failed** (785,94 detik ≈ 13 menit), log `_qa/gerbang-db-terpisah-2026-10-22.txt` |
| Frontend/tes frontend | tidak diubah pada pekerjaan ini; suite terakhir 160 berkas / 1.746 tes lulus (sesi sebelumnya hari ini) |

## 8. Asumsi, risiko, dan sisa pekerjaan

Asumsi yang diambil:

1. **"Data referensi" = komoditas + lokasi/SPPG + akun RBAC.** Pemasok, batch, keputusan, PO
   dianggap data bisnis sehingga tidak ada di mode DEFAULT.
2. **`reset-demo` mengosongkan seluruh tabel bisnis**, bukan hanya baris ber-`origin='demo'`.
   Alasannya: setelah `init-demo`, baris kanonik pun bagian dari demo (dan sudah ditandai `demo`),
   sedangkan menyisakan sebagian akan menghasilkan database setengah jadi. Pengaman host-lokal +
   `--yes` dipakai sebagai ganti pemilihan baris per baris.
3. **Mode dibaca dari isi database**, `DB_MODE` hanya pernyataan harapan; `status` yang memutuskan.
4. **Normalisasi id referensi hanya dijalankan bila tidak ada baris bisnis** (mode DEFAULT). Bila
   ada baris bisnis, skrip menolak menormalkan dan operator diminta membangun ulang DB demo.
5. `ledger_blocks` tidak dibersihkan `reset-demo` (append-only; tidak punya model maupun penanda).

Risiko / sisa pekerjaan:

- Tiga komponen frontend tidak terpasang di layar mana pun (Konsol operasi ×2, Supplier governance)
  — butuh keputusan produk, bukan data.
- 9 enum tidak sinkron kode↔skema↔data (rincian di `docs/db-coverage-matrix.md` §3.1/§5.4).
- 294 sel state tampilan belum terbukti; perlu tes komponen atau interaksi UI.
- `DEMO_SESSION_ENFORCE` di `.env` lokal diubah ke `false` agar data demo tampil tanpa sesi.
  Untuk demo berbatas waktu, nyalakan kembali dan pakai tombol Demo Control.
- Di luar lingkup dan tidak disentuh: kuota Bedrock TPM 0 (S0-04), rotasi `SIGNING_KEY_HEX` +
  `POSTGRES_PASSWORD`, integrasi S/4HANA (S5-01…06).

## 9. Backup, branch, commit

Backup sebelum tindakan destruktif (format `pg_dump -Fc`):

- `data/backups/pre-dbfix-mealchain-20261022-0810.dump` (372 KB) — DB demo sebelum reset/rebuild
- `data/backups/pre-dbfix-gate-20261022-0810.dump` (844 KB) — DB gerbang

Branch: `feature/db-modes-demo-coverage` (dari `feature/sprint2-decision-intelligence` @ `569266b`).
Delapan commit, tiap satu tema:

| Commit | Isi |
|---|---|
| `bf757fe` | Migrasi 028: penanda demo pada PO, index pencarian Joule, FK eksklusi CASCADE/SET NULL |
| `bf8c3df` | DB mode DEFAULT/DEMO: `app.seed.db_mode`, `reference`, `demo_extra`, `scripts/db-mode.sh`, rebuild mempertahankan cakupan, `.env.example` |
| `a747612` | Skills `db-mode` + `demo-data-builder` |
| `2de443d` | Joule: 3 scenario baru, capability 1.4.0, peta 13 skill, uji 14 pertanyaan |
| `68cf944` | Rebuild demo: langkah pelengkap jadi helper yang bisa diuji (+ tes menegaskan ketiganya dipanggil) |
| `ea03e60` | `docs/db-coverage-matrix.md`, `docs/db-fix-report.md`, `scripts/audit/db_coverage.py` |
| `42c475c` | `db-mode status` tidak lagi mengarang `DB_MODE` bawaan (menghindari peringatan palsu) |
| `d593832` | Onboarding: penyiapan DB diarahkan ke `scripts/db-mode.sh` |

Verifikasi ulang sesudah semua commit: gerbang backend **1282 passed / 18 skipped / 0 failed**,
sap-joule **123 passed / 14 skipped**, Joule DEMO **14/14**, DEFAULT **14/14**.
