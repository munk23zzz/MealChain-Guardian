# AUDIT_04 — Backend & API

Cakupan: 34 modul router, **77 operasi** di `backend/openapi.json`, 237 berkas tes backend.
Bukti runtime diambil dari suite `verify/*.spec.json` (lihat AUDIT_10) dan probe API langsung.

## 4.1 Inventaris endpoint (kelompok)

| Kelompok | Endpoint | Auth | Catatan |
|---|---|---|---|
| Aksi keputusan | `POST /actions/{propose,verify,approve,execute,repropose}` | JWT + peran | empat mata ditegakkan; `execute` butuh 2 approval |
| Keputusan | `GET /decisions`, `/{id}`, `/{id}/{approval-summary,chain,compliance,dossier,traces}` | JWT + scope | 404/422 diuji |
| KPI | `GET /kpi` | JWT + scope | `periode` **atau** `start`+`end` |
| Demo | 12 endpoint `/demo/*` | JWT + peran demo | mutasi digerbangi middleware sesi |
| Penerimaan | `POST /receipts`, `/receipts/menunggu`, `/{id}/{approve,reject}` | JWT + peran | gerbang keselamatan deterministik |
| Batch/pemasok/rute | `/batches*`, `/suppliers`, `/supplier-routes` | JWT + scope | `journey` di `/supplier-routes` (bukan `/balance/map`) |
| Admin | `/admin/{locations,users}` (+ by id) | `MANAGE_ROLES` | 403 untuk kepala SPPG (teruji) |
| Ledger | `GET /ledger/verify` | JWT | rantai valid (teruji) |
| Lain | `safety/evaluate`, `freshness/evaluate`, `evidence/fuse`, `logistics/estimate`, `waste/*`, `surplus/allocations`, `quarantine/*` | JWT | sebagian deterministik (tanpa DB) |

## 4.2 Hasil pengujian kontrak (bukti runtime)

| Skenario | Endpoint | Hasil terukur | Sumber |
|---|---|---|---|
| Tanpa token | `GET /decisions`, `/batches`, `/ledger/verify` | **401** (3/3) | invariants.spec |
| Peran salah | `GET /admin/users` sebagai `sppg_head` | **403** | invariants + roles.spec |
| Monitor menulis demo | `GET /demo/data-status` sebagai `bgn_monitor` | **403** | stack.spec |
| Lintas lokasi | `GET /balance/Bandung` sebagai kepala Jakarta | **403** | roles.spec |
| ID tidak ada | `GET /decisions/{uuid-palsu}/chain` | **404** | invariants.spec |
| ID bukan UUID | `GET /decisions/bukan-uuid/chain` | **422** | invariants.spec |
| Parameter batas | `GET /batches?limit=0`, `limit=1000` | **422** keduanya | invariants.spec |
| Periode salah | `GET /kpi?periode=24h` | **422** | probe + tes |
| Argumen periode ganda | `GET /kpi?periode=today&start=…` | **422** | probe + tes |
| Mutasi tanpa sesi demo | `POST /actions/approve` | **409** "sesi demo belum aktif atau sudah kedaluwarsa" | probe |
| Empat mata | `POST /actions/approve` akun sama dua kali | **409** "approval sudah tercatat untuk akun ini" | probe |
| Eksekusi belum 2 approval | `POST /actions/execute` | **409** | tes `test_can_execute*` |
| Eksekusi tanpa verifikasi | `POST /actions/execute` | **409** "belum terverifikasi" | tes + probe |
| Body tidak valid | `POST /receipts` batch karantina | **409** dengan alasan spesifik | `test_receipts_safety_gate.py` |

## 4.3 Business logic di backend (bukan hanya UI)

| Aturan | Lokasi | Ditegakkan di backend? |
|---|---|---|
| Empat mata (2 peran berbeda, akun berbeda) | `app/core/approval_matrix.py`, `app/api/actions.py` | Ya — 409 untuk akun sama, 409 untuk peran salah |
| Transisi status (`proposed`→`pending_approval`→`approved`→`executed`) | `decisions` CHECK constraint + service | Ya — CHECK di DB menolak status di luar daftar |
| Scope lokasi | `app/core/scope.py` | Ya — 403 lintas lokasi (roles.spec) |
| Gerbang keselamatan penerimaan | `app/core/safety_gate.py` | Ya — urutan: kedaluwarsa → karantina → safety → suhu |
| Sesi demo | `app/main.py` middleware + `demo_sessions` | Ya — 409 tanpa sesi |
| Idempotensi reset | `app/api/demo.py` (`dilewati: "snapshot kanonik sudah ada"`) | Ya — tes `test_refresh_hari_ini_tidak_menggandakan_snapshot_kanonik` |

## 4.4 Transaksi & konkurensi

- Approval dan eksekusi memakai transaksi per-request; empat mata dijaga **unique constraint** di `approvals` (satu baris per `decision_id`+`approved_by`) sehingga dua request bersamaan tidak bisa membuat dua approval akun sama.
- Satu sesi demo aktif dijaga partial unique index; dua request `start` bersamaan tidak bisa menghasilkan dua sesi (tes `test_demo_session_mulai_atomik.py` 14/14 di DB salinan).
- Eksekusi menulis PO + `batches.dispatched_at` + trace ACT dalam satu transaksi; kegagalan parsial tidak terlihat di data saat ini (0 keputusan `executed` tanpa approval, 0 PO ganda per keputusan).

## 4.5 Error handling & kebocoran informasi

- Respons galat memakai `{"detail": "..."}` berbahasa Indonesia; tidak ada stack trace di respons (diuji 404/409/422).
- Tidak ditemukan endpoint yang mengembalikan dump SQL atau path internal pada sampel yang diuji.
- Log container tidak diuji untuk kebocoran PII secara sistematis (lihat AUDIT_08).

## 4.6 Temuan backend

| ID | Temuan | Prioritas | Status |
|---|---|---|---|
| BUG-001 | `alembic check` gagal: 22 indeks FK dari migrasi 033 tidak dideklarasikan di model → autogenerate berikutnya akan menghapusnya | P2 | **DIPERBAIKI** (22 `Index` ditambahkan ke `__table_args__`; `alembic check` → "No new upgrade operations detected") |
| AUD-API-01 | `/balance/map` mewajibkan `commodity` dan **tidak** memuat `journey`; konsumen yang salah membaca endpoint ini akan menampilkan peta tanpa animasi | P3 | Terdokumentasi (kamus + skill reference) |
| AUD-API-02 | Definisi 3 KPI berbeda dari `docs/Skill.md` | P2 | Terbuka (keputusan owner) |
