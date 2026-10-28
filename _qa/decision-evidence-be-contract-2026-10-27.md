# Kontrak API di balik halaman "Decision & Evidence" — audit 27 Okt 2026

**Repo**: `E:/hackathon/HackathonAWS/mealchain-guardian` (branch `feature/db-modes-demo-coverage`)
**Revisi yang diaudit**: `0896acb` (HEAD, 2026-10-27 15:02:06 +0700). Container `mealchain-backend` menjalankan kode revisi ini — dibuktikan dari perilaku `approval-summary` yang masih memakai gerbang `source_location_id` (lihat F3).
**Fokus**: `decision_type='supplier_procurement'` dengan `decisions.source_location_id IS NULL`.
**Sifat audit**: READ-ONLY. Tidak ada file aplikasi yang diubah, tidak ada POST/PUT/PATCH/DELETE ke stack hidup, `pytest` tidak dijalankan. Bukti diambil dari: pembacaan kode, `git show HEAD:…`, `SELECT` via `docker compose exec postgres psql`, dan **GET** ke API memakai JWT yang dicetak di dalam container (`_issue_token`, tanpa menulis DB).

> Catatan konkurensi: saat audit berjalan, working tree berubah (file `supplier_eligibility.py`, `approval_summary.py`, `actions.py`, `tests/test_procurement_execute_guard.py`, mtime 15:02:50–15:03:40) — ada perbaikan belum-commit untuk cacat F1/F3/F4. Semua nomor baris di laporan ini mengacu ke **HEAD**; delta working tree dibahas di Lampiran A.

---

## 1. Ringkasan verdict

| # | Endpoint (dipanggil halaman) | Handler (HEAD) | Peran | Procurement + `source_location_id IS NULL` |
|---|---|---|---|---|
| 1 | `GET /decisions` | `backend/app/api/decisions.py:200` | semua peran terautentikasi | **WORKS** |
| 2 | `GET /decisions/{id}/approval-summary` | `backend/app/api/decisions.py:490` → `services/approval_summary.py:168` | semua peran (scope target) | **BREAKS** (can_execute menjanjikan 409; safety kosong) |
| 3 | `GET /decisions/{id}/chain` | `backend/app/api/decisions.py:377` | semua peran (scope target) | **WORKS** |
| 4 | `GET /decisions/{id}/traces` | `backend/app/api/decisions.py:446` | semua peran (scope target) | **WORKS** |
| 5 | `GET /decisions/{id}/dossier` | `backend/app/api/dossier.py:25` | semua peran (scope target) | **WORKS** |
| 6 | `GET /supplier-exclusions/context/{id}` | `backend/app/api/supplier_exclusion_context.py:46` | semua peran; `can_propose` hanya head/nutritionist di lokasi target | **WORKS** |
| 7 | `GET /ledger/verify` | `backend/app/api/ledger.py:14` | semua peran (tanpa scope) | **WORKS** (tidak sadar keputusan) |
| 8 | `POST /actions/propose` | `backend/app/api/actions.py:379` | `sppg_head` | **WORKS** (tanpa prasyarat pemasok/binding) |
| 9 | `POST /actions/verify` | `backend/app/api/actions.py:429` | `sppg_head`, `sppg_nutritionist` | **PARTIAL** — ctx tanpa safety/freshness (F8) |
| 10 | `POST /actions/approve` | `backend/app/api/actions.py:562` | `sppg_head`, `sppg_nutritionist` | **WORKS** (tapi keputusan kedaluwarsa masih bisa di-approve → jalan buntu, F11) |
| 11 | `POST /actions/execute` | `backend/app/api/actions.py:703` | `sppg_head` | **BREAKS** — 409 `binding batch/supplier berubah`, atau 409 `supplier_unknown: keputusan lama perlu binding batch eksplisit` (F1, F2) |
| 12 | `POST /actions/repropose` | `backend/app/api/actions.py:927` | `sppg_head` | **BREAKS diam-diam** — `supplier_id` anak tidak diwarisi (F6) |
| 13 | `POST /supplier-exclusions/proposals` (form di halaman) | `backend/app/api/supplier_exclusions.py:36` | `sppg_head` | **WORKS** |

Endpoint yang **tidak** dipanggil halaman meski satu kontrak: `GET /decisions/{id}` (`fetchDecision` hanya didefinisikan, `frontend/lib/api.ts:173`, tanpa pemanggil), `GET /decisions/{id}/compliance` (`api.ts:158`, tanpa pemanggil), `GET /decisions/{id}/audit-facts` (dipakai Verifier Agent), `POST /decisions` (dipakai `OpsConsole.tsx:172`).

Bukti observasi (GET nyata, 27 Okt 08:0x UTC):

```
GET /decisions            → 200, 10 baris procurement terlihat oleh head Jakarta,
                            contoh: {'supplier_name':'CV Cipinang Boga Utama','pengirim':'pemasok','target_location_name':'Jakarta'}
GET .../943e662c/chain    → 200, chain len 1, [(1,'approved')]
GET .../943e662c/traces   → 200, 16 langkah (DETECT…SUPERVISE)
GET .../943e662c/dossier  → 200, signature.state=signed, verify=True
GET /supplier-exclusions/context/943e662c → 200, [('CV Cipinang Boga Utama',1 batch)], can_propose=True
GET /ledger/verify        → 200, {'valid':True,'blocks':2459,'orphan_blocks':0}
GET .../f0ac8333/approval-summary → 200, can_execute=True, blocking_reasons=[], safety.batches_checked=0
```

---

## 2. Detail per endpoint: guard, urutan, pesan

Pola umum: dependency FastAPI (`require_roles`/`get_current_user`) dievaluasi **sebelum** handler, jadi 401/403 RBAC selalu mendahului 404 keputusan. `_load_decision` (`actions.py:78-84`) mengunci baris (`with_for_update`) dan melempar 404 `"decision tidak ditemukan"`.

### 2.1 Baca

**`GET /decisions`** — `decisions.py:200-374`
1. `user = Depends(get_current_user)` (212) → 401 `"butuh Bearer token"` / `"token tidak valid"` (`api/auth.py:98,106,111,116`).
2. `apply_location_scope(..., Decision.target_location_id, user)` (225-229) → `scope_location_id` (scope.py:47-59) → 403 `"user belum terikat lokasi — cakupan data tidak bisa ditentukan"` bila peran SPPG tanpa lokasi; `bgn_monitor` tanpa filter.
3. `window` (`24h|7d|30d`, 204-210) → 422 oleh Pydantic bila nilai lain.
4. Tidak ada cabang `decision_type`. `pengirim` diturunkan dari `decisions.supplier_id` **atau** payload bukti (323-334); `target_location_name` dari target (365).
   - Verdict procurement: **WORKS**. `source_location_id` tidak pernah dibaca.

**`GET /decisions/{id}/approval-summary`** — `decisions.py:490-507`, `services/approval_summary.py:168-447`
1. auth (494) → 401.
2. 404 `"decision tidak ditemukan"` (505).
3. `_assert_decision_readable` (506) → `assert_in_scope(user, row.target_location_id, what="keputusan")` → 403 `"keputusan di cakupan lokasi di luar SPPG Anda"` (`core/scope.py:39,78`).
4. Cabang tipe: `_supplier_for` — ADMIN_TYPES (`approval_summary.py:68-83`), **procurement** (`88-95`, pakai `decisions.supplier_id`), selain itu `resolve_binding` (`97-102`).
5. `_safety_view` (109-165): **gerbang lokasi** `if decision.source_location_id is None or decision.commodity_id is None: return tak_terdefinisi` (`131-132`) → `blocked=False, batches_checked=0, batch_ids=[]`.
6. `_requirement_for` (47-53): `operasional = decision_type not in ADMIN_TYPES` → procurement wajib **dua role** (`approval_matrix.py:36-40`).
7. `can_approve` (313-322): kedaluwarsa **tidak** memblokir untuk non-admin.
8. `blocking` (324-384) → `can_execute = not blocking` (385).
   - Verdict procurement: **BREAKS**. Lihat F3/F4.

**`GET /decisions/{id}/chain`** — `decisions.py:377-443`: auth → 404 (392) → scope (393) → supersedes walk. Tanpa cabang tipe. **WORKS**.

**`GET /decisions/{id}/traces`** — `decisions.py:446-487`: auth → 404 (457) → scope (458). Tanpa cabang tipe. **WORKS**.

**`GET /decisions/{id}/dossier`** — `dossier.py:25-60`: auth → `build_dossier` → 404 (39-40) → scope (42-46) → sign + `verify` (47-59). `build_dossier` hanya menyalin kolom mentah (`dossier_service.py:32-80`), termasuk `source_location_id` NULL. **WORKS**.

**`GET /supplier-exclusions/context/{id}`** — `supplier_exclusion_context.py:46-93`: auth → 404 (53) → scope (54) → himpunan `batch_ids` dari payload bukti (58-81) → `allowed = user.role in {head,nutritionist} and user.location_id == decision.target_location_id` (87-90) → `can_propose = bool(suppliers and scope and allowed)` (28). Tanpa cabang tipe, tetapi **mengandalkan bukti berisi `batch_id`/`batch_ids`** — untuk keputusan procurement tanpa bukti batch hasilnya `suppliers: []` dan `reason_unavailable = "Relasi supplier pada bukti batch belum tersedia; usulan tidak dapat dibuat."` (30-31). **WORKS** untuk baris yang punya bukti (terverifikasi live).

**`GET /ledger/verify`** — `ledger.py:14-20`: `get_current_user` saja, **tanpa** `assert_in_scope`, tanpa cabang tipe. `bgn_monitor` dan SPPG melihat rantai yang sama (2459 blok). **WORKS**.

### 2.2 Tulis

**`POST /actions/propose`** — `actions.py:379-415` (201)
1. `require_roles("sppg_head")` (382) → 401/403 `"role tidak diizinkan"` (`auth.py:125`).
2. `_load_decision` → 404 (385).
3. Status pra-approval (386-390) → 409 `"decision status {status} tidak dapat diajukan untuk persetujuan"`.
4. ADMIN_TYPES (391-392) → 409 `"gunakan endpoint proposal supplier-exclusions"`.
5. Scope target (394) → 403 `"keputusan di cakupan lokasi di luar SPPG Anda"`.
6. Komoditas ada (396-400) → 422 `"commodity decision tidak valid"`.
7. Kedaluwarsa (402-403) → 409 `"decision expired"`.
   - Tanpa cabang procurement; tidak memeriksa `supplier_id`/binding. Procurement **WORKS** tetapi bisa mengantarkan keputusan tanpa pemasok ke approval.

**`POST /actions/verify`** — `actions.py:429-559` (200)
1. `require_roles("sppg_head","sppg_nutritionist")` (432).
2. 404 (443).
3. Status pra-approval (444-448) → 409 `"verify hanya untuk decision pra-approval (status kini {status})"`.
4. Scope target (452) → 403.
5. Sudah ada approval (453-465) → 409 `"verify tidak dapat diulang setelah ada approval tercatat (integritas audit trail)"`.
6. Kedaluwarsa (472-473) → 409 `"decision expired"`.
7. Verdict sudah tercatat (480-487) → 409 `"verdict sudah tercatat — hasil audit tidak bisa ditimpa; tarik/ajukan keputusan baru bila perlu penilaian ulang"`.
8. `ctx = _verifier_ctx(...)` (491); ADMIN_TYPES menambah `administrative_evidence` (492-504); sisanya tidak ada cabang tipe.
9. `run_verifier` (505) → `recorded = verdict in {CONSISTENT, FLAGGED}` (510); `verified_by` hanya ditulis bila recorded (511-512); FLAGGED → status `verifier_flagged` (514-515).
   - Procurement: **PARTIAL** — `_verifier_ctx` memasang safety/freshness hanya `if decision.source_location_id and decision.commodity_id` (`144`), jadi sisi NULL mengirim `safety_status=None, freshness_score=None` (142-161). Lihat F8.

**`POST /actions/approve`** — `actions.py:562-691` (200)
1. `require_roles("sppg_head","sppg_nutritionist")` (565).
2. 404 (568).
3. Scope target (573) → 403.
4. Kedaluwarsa **hanya ADMIN_TYPES** (574-582) → 409 `"decision expired"`.
5. Duplikat approver (583-597) → 409 `"approval sudah tercatat untuk akun ini — empat mata berarti approver berbeda, bukan akun yang sama dua kali"`.
6. Status (602-605) → 409 `"decision status {status} tidak dapat di-approve"`.
7. Setuju sebelum verifikasi (611-618) → 409 `"keputusan belum diverifikasi — catat hasil verifier dulu sebelum meminta persetujuan"`.
8. Tolak tanpa alasan (621-625) → 422 `"penolakan wajib menyertakan alasan (comment)"`.
9. Kuorum (648-662); ledger (664-675); race unique (676-685) → 409 `"approval untuk akun ini sudah tercatat; muat ulang lalu periksa kuorum"`.
   - Procurement **WORKS**; konsekuensi F11: `26e8bbbf` (pending, kedaluwarsa) menjawab `can_approve=True`.

**`POST /actions/execute`** — `actions.py:703-915` (200). Urutan penjaga:
| # | Baris | Kondisi | Status/pesan |
|---|---|---|---|
| 1 | 706 | `require_roles("sppg_head")` | 403 `"role tidak diizinkan"` |
| 2 | 709 | muat + lock | 404 `"decision tidak ditemukan"` |
| 3 | 711 | scope target | 403 `"keputusan di cakupan lokasi di luar SPPG Anda"` |
| 4 | 715-719 | `status == review_only` | 409 `"decision tinjauan (review-only) — tidak untuk dieksekusi"` |
| 5 | 720-728 | `status == executed` | ADMIN: 200 idempoten; lain: 409 `"decision sudah dieksekusi"` |
| 6 | 729-730 | `_verifier_unverified` | 409 `"decision belum terverifikasi"` |
| 7 | 731-732 | `status == rejected` | 409 `"decision ditolak"` |
| 8 | 733-734 | kedaluwarsa | 409 `"decision expired"` |
| 9 | 735-739 | status ∉ {pending_approval, verifier_flagged, approved} | 409 `"status {status} tidak dapat dieksekusi"` |
| 10 | 741-758 | kuorum approval | 409 `"approval belum memenuhi requirement (missing/rejected)"` |
| 11 | 763-772 | kuorum dibatasi approver lokasi target | 409 `"approval scope tidak memenuhi requirement"` |
| 12 | 774-795 | ADMIN_TYPES | 200 (tanpa PO) |
| 13 | 797-799 | `revalidate_transfer` | 409 dari `supplier_eligibility` (di bawah) |
| 14 | 803-810 | `_source_batches_still_safe` | 409 `"safety revalidation gagal: batch sumber kini FAIL (temperature excursion)"` |
| 15 | 813-817 | komoditas | 422 `"commodity decision tidak valid"` |
| 16 | 818-820 | `quantity_kg > 0` | 422 `"quantity decision tidak valid"` |
| 17 | 821-824 | unit price > 0 | 422 `"unit price decision tidak valid"` |
| 18 | 827-829 | `supplier_id is None` | 422 `"supplier untuk lokasi target tidak ditemukan"` |
| 19 | 830-845 | INSERT PO + trace ACT + settlement + dispatch + ledger | 200 `{po_number, data_source:"MOCK", dikirim, ditahan}` |

Penjaga di `revalidate_transfer` (`supplier_eligibility.py:206-236`), yang menentukan hasil procurement:
```
208  supplier_id, batches = await resolve_binding(db, decision)
...
224  if not batches: reasons.append("safety revalidation gagal: tidak ada batch sumber")
230  blokir = penghalang_sumber(batches, sekarang=datetime.now(UTC))
234  if reasons: raise HTTPException(409, "; ".join(reasons))
```
dan di `resolve_binding` (`85-132`):
```
108  if (len(batches) != len(ids) or not ids or any(
112       b.supplier_id != supplier_id
113       or b.location_id != decision.source_location_id   ← cacat F1
114       or b.commodity_id != decision.commodity_id for b in batches)):
118       raise HTTPException(409, "binding batch/supplier berubah")
...
121  batches = ... where(Batch.location_id == decision.source_location_id,   ← F2 (NULL → IS NULL)
129  raise HTTPException(409, "supplier_unknown: keputusan lama perlu binding batch eksplisit")
```
- Verdict procurement: **BREAKS**. Untuk data sehat (binding `procurement:true`, batch di SPPG tujuan, supplier = `decisions.supplier_id`) kode **selalu** 409 di baris 113→118. Tanpa binding: 0 batch → 409 di baris 129.

**`POST /actions/repropose`** — `actions.py:927-1005` (201)
1. `require_roles("sppg_head")` (931).
2. 404 (940).
3. Scope target (945) → 403.
4. ADMIN_TYPES (946-950) → 409 `"ajukan evidence baru melalui supplier-exclusions/proposals atau restore"`.
5. Status (951-955) → 409 `"re-propose hanya untuk decision rejected (status kini {status})"`.
6. Alasan penolakan (956-960) → 409 `"decision rejected tanpa alasan — tidak ada bahan re-propose"`.
7. Anak dibuat (961-975) **tanpa** `supplier_id` dan tanpa menyalin bukti/binding.
   - Procurement: **BREAKS diam-diam** (F6).

**`POST /supplier-exclusions/proposals`** — `supplier_exclusions.py:36-52`: role head (38) → `service.propose` (41-48) → `ValueError` → 422 (49-50). Cakupan di dalam service. Tanpa cabang tipe; procurement **WORKS** (refs berbasis batch).

---

## 3. Temuan

### F1 — `resolve_binding` membandingkan batch dengan lokasi SUMBER; pengadaan tidak punya sumber
**Bukti**: `supplier_eligibility.py:113` (`or b.location_id != decision.source_location_id`), pemicu 409 di `:118`; penulis binding pengadaan justru memvalidasi ke **target** (`services/supplier_procurement.py:464-470`, payload `procurement:true` + `target_location_id` di `471-483`).
**Salah**: satu aturan lokasi dipakai untuk dua semantik ("pindah stok antar-SPPG" vs "pemasok mengirim ke SPPG"). Dengan `source_location_id = NULL`, `b.location_id != None` selalu `True` → binding yang benar pun ditolak.
**Gejala di halaman**: `approval-summary` menyatakan siap (`can_execute=true`, `blocking_reasons=[]`), tombol **Eksekusi** aktif; klik → 409 `binding batch/supplier berubah`. Pesan itu tidak ada di peta `frontend/lib/bahasa.ts:22-37`, jadi tampil mentah di popup dan di `.action-message` (`DecisionActions.tsx:246-250`).
**Data**: 4 keputusan procurement dengan `source_location_id IS NULL` memiliki binding yang sehat (`supplier` binding = `decisions.supplier_id`, batch di lokasi target): `943e662c`, `f0ac8333`, `26e8bbbf`, `9a6ef1a4` → keempatnya pasti 409 pada revisi HEAD.

### F2 — Procurement tanpa binding: pesan 409 menyesatkan ("keputusan lama")
**Bukti**: `supplier_eligibility.py:119-130`. `Batch.location_id == decision.source_location_id` dengan nilai `None` dikompilasi menjadi `IS NULL` (diverifikasi: `SELECT … FROM batches WHERE batches.location_id IS NULL`), sehingga himpunan kosong → 409 `"supplier_unknown: keputusan lama perlu binding batch eksplisit"`.
**Salah**: keputusan **baru** (`status='proposed'`, dibuat `POST /decisions`/demo template) disebut "keputusan lama"; sebab sebenarnya — pengadaan memang tidak pernah menulis binding transfer — tidak disebut. `humanizeBlocker` memetakan prefiks `supplier_unknown` menjadi "pemasok tidak dikenal", sehingga penyetuju membaca "pemasok tidak dikenal" padahal `decisions.supplier_id` terisi.
**Gejala**: `64ce3369` (proposed, target Bandung, supplier `d8ff21f2`, **0 baris bukti binding**) → setelah approve, eksekusi berhenti di sini.

### F3 — `_safety_view` melaporkan "tidak terdefinisi" untuk semua pengadaan
**Bukti**: `approval_summary.py:131-132` (`if decision.source_location_id is None or decision.commodity_id is None: return tak_terdefinisi`), nilai balik `122-130` (`blocked: False, batches_checked: 0, batch_ids: []`).
**Salah**: batch pengadaan ada (di SPPG tujuan) dan **dipakai** oleh `revalidate_transfer`; read model mengabaikannya, sehingga `safety.blocked` selalu `False` dan `batch_ids` kosong (komentar `127-129` justru menyatakan field itu dipakai worker Safety/Freshness).
**Gejala (terukur)**: `f0ac8333` → `safety: {worst_status: null, blocked: false, batches_checked: 0, batch_ids: []}` padahal batch `45204477` (Jakarta, `pending`) terikat; `943e662c` sama walau batch `5c05d411` `pass`. Kartu "Keamanan & pemasok" menampilkan **Status keamanan terburuk "—"**, **Batch diperiksa 0**, **Diblokir keamanan "Tidak"** (`lib/evidence.ts:1107-1119`) — tiga pernyataan yang terdengar aman padahal tidak ada yang diperiksa.

### F4 — Paritas read-model ↔ execute putus: `can_execute=true` untuk eksekusi yang pasti 409
**Bukti**: `_supplier_for` mem-bypass `resolve_binding` untuk procurement (`approval_summary.py:88-95`), sehingga `binding_error` selalu `None` (`192-199`) dan `blocking` tidak pernah memuat kegagalan binding (`325-326`); ditambah F3, tidak ada satu pun entri blocking dari safety.
**Salah**: komentar modul `approval_summary.py:9-11` ("Parity dengan execute (O-PO) … Binding tidak valid memblokir readiness") tidak berlaku untuk tipe yang justru paling butuh.
**Gejala (terukur)**: `f0ac8333` → `can_execute: true`, `blocking_reasons: []`; `lib/evidence.ts:253-254` lalu menulis **"Semua syarat terpenuhi — keputusan siap dieksekusi."** di kepala halaman, dan `ApprovalMenu.tsx:96,244` mengaktifkan tombol Eksekusi.

### F5 — Pemasok yang dieksekusi ≠ pemasok yang ditampilkan (divergensi senyap)
**Bukti**: eksekusi memakai supplier dari binding (`supplier_eligibility.py:104` lalu `:131`), sedangkan halaman memakai `decisions.supplier_id` (`approval_summary.py:88-95`, feed `decisions.py:323,362`). Tidak ada penjaga yang membandingkan keduanya.
**Data (4 baris hidup)**: `a4862ab9` halaman "CV Berkah Telur Bekasi" vs binding "Koperasi Telur Cipanas Bersama"; `9d27bcfc` halaman "UD Blitar Telur Makmur" vs binding "CV Ambarawa Telur Utama"; idem `85879774`, `081d5227`. Pada `9d27bcfc` semua syarat `resolve_binding` lain lolos (batch di lokasi sumber Semarang, supplier batch = supplier binding, komoditas sama), jadi HEAD akan **menerbitkan PO ke CV Ambarawa** sementara layar menulis UD Blitar.
**Gejala**: kartu "Keamanan & pemasok" (`supplierFact`) dan kartu feed menampilkan satu perusahaan; PO (dan `settlement.catat_po_terbit`) menunjuk perusahaan lain, tanpa peringatan apa pun.

### F6 — `repropose` membuang identitas pengadaan
**Bukti**: `actions.py:961-975` — `Decision(... )` anak hanya mewarisi tipe/status/lokasi/komoditas/jumlah/SDC/breakdown/expiry/iteration/supersedes/demo_case; **tidak** `supplier_id`, dan `DecisionEvidence` (binding) tidak disalin.
**Salah**: untuk procurement, identitas pemasok hidup di kolom `decisions.supplier_id` (dokumentasi `approval_summary.py:84-87`), jadi iterasi v2 kehilangan satu-satunya sumber pemasok. Ringkasan lalu `supplier: null` (`approval_summary.py:89-90`), feed `pengirim: null` (`decisions.py:326-334`), dan eksekusi jatuh ke `supplier_unknown`.
**Status bukti**: code-only — 6 baris anak procurement di DB punya `supplier_id` dan bukti (dibuat penyemai demo, bukan `/actions/repropose`), jadi tidak ada jejak live untuk jalur ini.

### F7 — `POST /decisions` menerima `supplier_procurement` tetapi memakai penulis binding transfer
**Bukti**: `decisions.py:55-62` (Literal memuat `supplier_procurement`), `186-188` memanggil `persist_binding`; `supplier_eligibility.py:48-57` menolak batch yang `location_id != decision.source_location_id` → 422 `"binding batch/supplier tidak cocok"`. Tanpa `batch_ids`/`supplier_id`, `persist_binding` return diam-diam (`33-34`).
**Salah**: kontrak menciptakan keputusan yang **tidak mungkin** membawa binding yang sah; klien harus tahu untuk tidak mengirim binding (dan kemudian kena F2).
**Gejala**: `OpsConsole.tsx:172` (tombol buat keputusan dari rekomendasi) menerima 422 tanpa penjelasan semantik; layar Decision & Evidence lalu menampilkan `supplier: null`.

### F8 — Verifikasi pengadaan berjalan tanpa fakta safety/freshness
**Bukti**: `actions.py:144` (`if decision.source_location_id and decision.commodity_id:`) → `_verifier_ctx` mengirim `safety_status=None`, `freshness_score=None` (`261-277`).
**Salah**: Verifier independen (O-SEC-3) diminta menilai keputusan pengadaan tanpa dimensi fisik yang justru menjadi alasan flag; `candidates` hanya bisa datang dari trace (`172-193`).
**Gejala**: `VERIFY` trace pada 3 keputusan NULL-source ber-verdict `FLAGGED` dengan alasan kandidat `safety_status 'pending'` (bukan batch), sedangkan 4 keputusan procurement ber-source `consistent`. Korelasi ini **observasi**, bukan bukti kausal — verdict `FLAGGED` juga akan menurunkan syarat approval ke 1 role bila `dua_role_wajib` tidak dipaksa (di sini dipaksa, `actions.py:111-112`).

### F9 — `audit-facts` melaporkan "tidak ada batch sumber" untuk pengadaan
**Bukti**: `audit_facts.py:85-89` memakai `batch_sumber_transfer`; pada HEAD fungsi itu jatuh ke query lokasi sumber (`supplier_eligibility.py:192-203`) → kosong → `penghalang: "tidak_ada_batch_sumber"` (`audit_facts.py:118-119`), `count: 0`.
**Salah**: Verifier Agent menerima fakta "tidak ada bukti batch" untuk keputusan yang punya batch pemasok sah; `citations.batch_ids` kosong sehingga verifier tidak bisa menyitir bukti.
**Gejala**: panel "Verifikator: flagged" di halaman untuk keputusan yang batch-nya `pass`.

### F10 — `_dispatch_bound_batches` memperlakukan pengadaan sebagai "barang berangkat"
**Bukti**: `actions.py:294-299` hanya mengecualikan `supplier_exclusion`, `supplier_exclusion_restoration`, `price_anomaly`; `341-342` menulis `dispatched_at` pada batch terikat.
**Salah**: batch pengadaan sudah berada di SPPG **tujuan** (mis. `5c05d411` di Jakarta = target `943e662c`), jadi menandainya "berangkat" tidak merepresentasikan perjalanan pemasok→SPPG; tidak ada truk dari lokasi pemasok. Sebaliknya pengadaan tanpa bukti batch mengembalikan `dikirim: []` (`315-316`) sementara status menjadi `executed`.
**Gejala**: setelah eksekusi, peta Overview tidak menampilkan perjalanan pemasok→SPPG (truk muncul "di tempat").

### F11 — Procurement kedaluwarsa masih bisa di-approve, eksekusinya mustahil
**Bukti**: `actions.py:574-582` (kedaluwarsa hanya dijaga untuk ADMIN_TYPES), `733-734` (execute menolak tanpa syarat); read model mengikuti: `approval_summary.py:313-317`.
**Salah/gejala (terukur)**: `26e8bbbf` → `can_approve: true`, `can_reject: true`, `can_execute: false`, `blocking: ["decision expired", …]`. Halaman menawarkan **Setuju** untuk keputusan yang setelah disetujui tetap tidak bisa dieksekusi. Ini perilaku yang dimenangkan owner untuk "keputusan biasa" (komentar `574-581`), tetapi procurement diikutkan tanpa keputusan eksplisit.

### F12 — Higiene kontrak (kecil, tapi menyesatkan pembaca kode)
- `decisions.py:331` menyebut `surplus_redistribution` yang **tidak ada** di CHECK constraint (`models/decisions.py:47-51`) → cabang mati.
- `frontend/lib/api.ts:158` (`fetchComplianceDossier`) dan `:173` (`fetchDecision`) tidak punya pemanggil; `GET /decisions/{id}` karena itu bukan bagian kontrak halaman, walau ia satu-satunya endpoint yang sudah menangani `source_location_id NULL` dengan benar (`decisions.py:551-555`).
- Model request tidak konsisten: `VerifyRequest` `extra="forbid"` (`actions.py:65`), sedangkan `ProposeRequest`/`ApproveRequest`/`ExecuteRequest` (`53-75`) menerima field asing diam-diam.
- `bahasa.ts:22-37` tidak memuat `"binding batch/supplier berubah"`, `"supplier untuk lokasi target tidak ditemukan"`, `"approval scope tidak memenuhi requirement"` → pesan teknis tampil apa adanya.

---

## 4. Cakupan tes procurement (`grep backend/tests`)

Hanya **satu** berkas menguji endpoint halaman dengan `decision_type='supplier_procurement'`: `backend/tests/test_procurement_execute_guard.py` — `POST /actions/execute` (5 kasus) dan `GET .../approval-summary` (1 kasus). Berkas ini **merah pada HEAD** (menuntut 200; `resolve_binding` masih membandingkan `source_location_id`, baris 113) dan **tidak dijalankan** dalam audit ini (aturan READ-ONLY: pytest mem-purge baris demo di DB bersama).

Endpoint tanpa satu pun tes procurement:

| Endpoint | Tes yang ada (semua untuk tipe lain) | Tes procurement |
|---|---|---|
| `POST /actions/propose` | 15 berkas (`test_actions.py`, `test_rejection_loop.py`, …) | **0** |
| `POST /actions/verify` | 16 berkas | **0** |
| `POST /actions/approve` | 21 berkas | **0** |
| `POST /actions/repropose` | 6 berkas | **0** |
| `GET /decisions` | — | **0** |
| `GET /decisions/{id}` | `test_decision_read_endpoints.py` | **0** |
| `GET /decisions/{id}/chain` | `test_rejection_loop.py`, `test_scope_matrix.py` | **0** |
| `GET /decisions/{id}/traces` | `test_decision_read_endpoints.py` | **0** |
| `GET /decisions/{id}/dossier` | `test_dossier.py` | **0** |
| `GET /decisions/{id}/compliance` | `test_compliance.py` | **0** |
| `GET /decisions/{id}/audit-facts` | `test_agent_narrative_facts.py` (fakta sintetis `decision_type=supplier_procurement`, bukan endpoint) | **0** |
| `GET /supplier-exclusions/context/{id}` | `test_supplier_exclusion_api.py` | **0** |
| `GET /ledger/verify` | `test_ledger.py` | **0** (endpoint tidak sadar tipe) |
| `POST /decisions` (procurement) | `test_sap_orders_api.py` hanya membaca baris seed | **0** |

Berkas lain yang menyebut `supplier_procurement` menguji **penyemai/demo**, bukan kontrak halaman: `test_demo_agent_control_api.py`, `test_demo_template_status_tambahan.py`, `test_hari_ini.py`, `test_sap_orders_api.py`, `test_supplier_procurement_eval.py` (service skoring, bukan API).

---

## 5. Lampiran A — delta working tree (belum commit, 15:02:50–15:03:40)

Perbaikan yang sedang berjalan menutup sebagian temuan, tetapi tidak semuanya:

| Temuan | Status di working tree |
|---|---|
| F1 | **Ditutup**: `lokasi_batch_acuan()` (`supplier_eligibility.py:85-101`) → `resolve_binding` memakai `acuan` (target untuk procurement). |
| F2 | **Ditutup**: cabang procurement tanpa binding memakai `decisions.supplier_id` + batch di target (`:139-155`), pesan baru `"supplier_unknown: keputusan pengadaan tanpa pemasok/batch tujuan"` / `"… tidak ada batch pemasok di SPPG tujuan"`. |
| F3 | **Ditutup**: `_safety_view` memakai `lokasi_batch_acuan` (`approval_summary.py:132-134`). |
| F4 | **Sebagian**: safety kini terisi, tetapi `_supplier_for` masih mem-bypass `resolve_binding` untuk procurement ⇒ binding yang salah tetap tak terlihat di `blocking_reasons` (relevan untuk F5). |
| F5 | **Tidak ditutup** (tidak ada perbandingan `binding.supplier_id` vs `decisions.supplier_id`). Perubahan `acuan` justru membuat 4 baris hidup (`a4862ab9`, `9d27bcfc`, `85879774`, `081d5227`) berubah dari "PO ke pemasok binding" menjadi **409** `binding batch/supplier berubah`, karena batch-nya di lokasi sumber, bukan target. |
| F6 | **Tidak ditutup** (`repropose_action` tidak disentuh). |
| F7 | **Tidak ditutup** (`persist_binding` masih memakai `source_location_id`). |
| F8 | **Tidak ditutup** (`_verifier_ctx` masih bergerbang `source_location_id`, `actions.py:144`). |
| F9 | **Ikut membaik**: `batch_sumber_transfer` menambah cabang procurement tanpa binding (`:230-246`). |
| F10 | **Tidak ditutup**. |
| F11 | **Tidak ditutup**. |

## 6. Lampiran B — bukti SQL (ringkas)

```
-- 4 baris procurement source NULL, binding sehat (batch di target, supplier cocok)
 id       | status           | src_null | bind_sup | dec_sup | sup_sama | batch_di_target
 9a6ef1a4 | proposed         | t        | 1cd9093d | 1cd9093d| t        | t
 f0ac8333 | approved         | t        | d4899915 | d4899915| t        | t
 943e662c | approved         | t        | f4bbb1fc | f4bbb1fc| t        | t
 26e8bbbf | pending_approval | t        | f4bbb1fc | f4bbb1fc| t        | t

-- 4 baris procurement source NON-NULL, pemasok binding ≠ pemasok keputusan (F5)
 a4862ab9 | target Jakarta  | bind 3702c204 (Koperasi Telur Cipanas) | dec 326e7edc (CV Berkah Telur Bekasi)
 9d27bcfc | target Surabaya | bind d8ff21f2 (CV Ambarawa)           | dec 475a1e09 (UD Blitar Telur Makmur)
 85879774 | target Bandung  | bind 3702c204                          | dec edc8079b (CV Lembang Telur Segar)
 081d5227 | target Jakarta  | bind 3702c204                          | dec 326e7edc

-- 64ce3369 (proposed, Bandung): 0 bukti binding, 2 trace tanpa kandidat
-- 9d27bcfc: batch 70bd0b29 (Semarang, needs_verification) lolos semua syarat resolve_binding
--           kecuali supplier ≠ decisions.supplier_id ⇒ HEAD menerbitkan PO ke pemasok binding
```

**Batas audit**: pesan 409 pada `POST /actions/execute` disimpulkan dari jalur kode deterministik + data DB (tidak dieksekusi karena larangan mutasi). Semua status `can_*`, `blocking_reasons`, `safety`, `supplier` di atas adalah respons **GET** nyata dari stack hidup pada revisi HEAD.
