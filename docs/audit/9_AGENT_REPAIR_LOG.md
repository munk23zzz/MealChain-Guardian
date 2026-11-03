# 9 Agent — Repair Log (P0/P1 aman saja)

Tanggal: 27 Oktober 2026 · Basis: `57db099` (`docs(sec): contoh sandi demo dihapus dari dokumen`)
Lingkungan: Windows 11, bash (MSYS), container `mealchain-backend` / `mealchain-postgres` / `mealchain-frontend`.
Database uji: **klon sekali pakai** (`pg_dump` → `createdb`), DSN diambil dari `os.environ['DATABASE_URL']`
di dalam container lalu nama DB diganti — DB demo `mealchain` hanya dibaca (SELECT).

## 0. Aturan yang dipegang

| Aturan | Konsekuensi di log ini |
|---|---|
| Maksimum 3 patch, hanya P0/P1 yang aman | 3 patch dilakukan (FIX-1, FIX-2, FIX-3/AUD-9B-29), 1 kandidat **ditolak karena tidak terbukti** |
| Tanpa melonggarkan assertion | 2 assertion lama **diperketat** (CONSISTENT → FLAGGED) + 4 assertion guardian diperketat/disesuaikan ke aturan sumber (AUD-9B-29), tidak ada tes yang di-skip |
| Tanpa mengubah ambang/KPI | `PASS_THRESHOLD 0,85` dan `VERIFY_THRESHOLD 0,60` **tidak diubah** pada ketiga patch — justru mulai dipakai |
| Tidak ada perubahan `.env`, tidak ada paket baru, tidak ada push | Dipatuhi |

## 1. Ringkasan hasil

| # | Temuan | Prioritas | Keputusan | Regression test |
|---|---|---|---|---|
| FIX-1 | AUD-9A-03 / AUD-9A-05 — verifier LLM mengembalikan `CONSISTENT` untuk `freshness_score` yang menurut `core/freshness.py` = `needs_verification` | P1 | **DIPERBAIKI** — guard deterministik memakai gerbang certified | `backend/tests/test_verifier_freshness_guard.py` (14 kasus) |
| FIX-2 | AUD-9A-05 — worker Freshness tidak memakai gerbang certified 0,85/0,60; 0,82 dilaporkan `ok` tanpa status | P1 | **DIPERBAIKI sebagian** — klasifikasi certified kini fakta + warning; `blocking`/veto sengaja tidak diubah (butuh keputusan owner) | `backend/tests/test_agent_freshness_gate.py` (5 kasus) |
| FIX-3 | **AUD-9B-29** — Safety & Freshness menilai batch lokasi **tujuan**, bukan sumber; exclusion dihitung tanpa cakupan | **P0** | **DIPERBAIKI** — guardian memakai himpunan batch sumber (binding/lokasi sumber), exclusion ber-cakupan pemasok+lokasi, sumber tak teridentifikasi → fail-closed; revalidasi `execute` memakai aturan yang sama | `backend/tests/test_agent_guardian_scope.py` (13 kasus) + `backend/tests/test_execute_source_scope.py` (3 kasus) |
| — | Prioritas (iii) — retry/duplikat menghasilkan keputusan/PO ganda | P1 (dugaan) | **TIDAK TERBUKTI → tidak dipatch** | bukti di §4 |
| — | AUD-9A-04, AUD-9A-06/9B-07, AUD-9B-16, AUD-9B-01/02, independensi model verifier | P1–P2 | **Tidak dipatch** (alasan di §5) | — |

## 2. FIX-1 — Verifier tidak bisa menaikkan kesegaran yang belum lolos gerbang

### Reproduksi (sebelum patch)
```
# in-process, fungsi produksi, ctx identik dengan yang disusun _verifier_ctx
run_verifier({...,"freshness_score": 0.82, "safety_status": "PASS"}, sap_primary=<model CONSISTENT>)
→ verdict CONSISTENT   # provider: sap_ai_core_primary
# runtime nyata (Event 1 pada klon, 2026-10-26 17:20Z)
POST /demo/event1 {"commodity":"telur","target_location":"Jakarta"}
→ verifier {"verdict":"CONSISTENT","provider":"primary:agentcore",
            "reason":"... freshness scores (0.965–0.934) align with PASS status ..."}
# review 8 agent pada keputusan 749bdc55 (batch Jakarta/telur)
freshness finding: worst_freshness_score 0.82, status ok, blocking false
```
`backend/app/core/freshness.py:7-8` menyebut 0,82 = `needs_verification` (0,60 ≤ 0,82 < 0,85).
Jadi dua komponen sistem menyatakan hal berbeda tentang batch yang sama, dan penilai
(mode/prompt sama dengan penulis narasi) memenangkan yang lebih longgar.

### Root cause
`enforce_verifier_guard()` hanya memeriksa satu dimensi:
```python
if (safety_status or "").strip().upper() == "FAIL" and verdict == "CONSISTENT":
    return "FLAGGED"
```
`freshness_score` sama sekali tidak diperiksa (`verifier_client.py:86-102`), padahal nilainya
sudah ada di `ctx` yang dikirim (`_build_user_prompt`, `ctx["freshness_score"]`) dan sudah
dipakai `event1_orchestrator.py:139-154`.

### Patch (minimal)
`backend/app/ai_providers/verifier_client.py`
1. `freshness_gate_score(score)` — klasifikasi memakai `classify_freshness()` dari
   `app.core.freshness` (satu sumber aturan, bukan angka kembar). `None` → tidak ada klaim;
   nilai tak terbaca/NaN/bool/di luar [0,1] → `invalid` (fail-closed).
2. `enforce_verifier_guard(..., freshness_score=None)` — `CONSISTENT` diturunkan menjadi
   `FLAGGED` bila status kesegaran `needs_verification`/`fail`/`invalid`. `safety FAIL` tetap
   menang lebih dulu; `FLAGGED`/`UNAVAILABLE` dari model tidak diubah.
3. `run_verifier()` meneruskan `ctx["freshness_score"]` ke guard.

Tidak ada ambang baru, tidak ada nilai yang diciptakan: guard hanya **menurunkan** klaim model
ke tingkat yang dibuktikan core (tidak pernah menaikkannya).

### Regression test
`backend/tests/test_verifier_freshness_guard.py` — 14 kasus:
skor 0,82/0,60/0,84/0,5/0,0/0,35 → `FLAGGED`; 0,85/0,9/0,95/1,0 → `CONSISTENT`;
`None` → tidak diklaim; `NaN`/`"bukan angka"`/`True`/1,7/−0,2 → `FLAGGED`;
safety FAIL menang atas freshness 0,99; `FLAGGED` model tidak diubah;
plus dua kasus lewat `run_verifier()` penuh (0,82 → `FLAGGED`, 0,965 → `CONSISTENT`).

### Tes terkait yang ikut berubah (diperketat, bukan dilonggarkan)

Karena data demo membawa `freshness_score 0,82` (AUD-9B-01), guard menurunkan setiap `CONSISTENT`
model pada jalur `POST /actions/verify`. Sembilan assertion di empat berkas tes mengunci perilaku
lama; semuanya diperketat ke nilai yang benar-menurut-gerbang, tanpa ada tes yang dihapus/di-skip:

| Berkas | Assertion lama → baru | Alasan |
|---|---|---|
| `test_s4_verifier_independence.py::test_verify_memakai_chain_server_side` | `verdict == "CONSISTENT"` → `"FLAGGED"`; `note == "consistent"` → `"flagged"` | ctx demo 0,82; subjek tes (chain server-side) tetap dibuktikan `provider == "test_provider"` |
| `test_s4_verifier_independence.py::test_verify_ditolak_409_setelah_approved` | `note == "consistent"` → `"flagged"` | subjek (verify telat tidak menimpa) tidak berubah |
| `test_approval_four_eyes.py::test_akun_sama_tidak_bisa_memberi_keputusan_dua_kali` | `decision_status == "pending_approval"` → `"verifier_flagged"` | setelah verify FLAGGED, status keputusan = `verifier_flagged` (approve tetap 200, kuorum tetap 2 role) |
| `test_verifier_tidak_bisa_diulang.py` (4 tes) | `note == "consistent"` → `"flagged"`; `status == "pending_approval"` → `"verifier_flagged"`; trace `verdict = 'CONSISTENT'` → `'FLAGGED'`; blok ledger `verdict = 'CONSISTENT'` → `'FLAGGED'` | subjek tiap tes (verdict tidak bisa ditimpa, retry setelah UNAVAILABLE, satu trace per percobaan, satu blok ledger per verdict) tidak berubah |
| `test_verifier_verdict_recorded.py::test_consistent_mencatat_verified_by` | `verifier_note == "consistent"` → `"flagged"` | `verified_by` tetap tercatat; nilainya kini `flagged` |

Jalur "CONSISTENT dihormati bila skor pass" dibuktikan tes baru
(`test_run_verifier_consistent_untuk_skor_pass`, `test_consistent_kept_when_freshness_certified_pass`),
jadi cakupan tidak hilang — hanya berpindah ke berkas regresi yang eksplisit.

### Hasil
```
$ docker exec -e DATABASE_URL=.../mealchain_a9_t001654 -w /app mealchain-backend \
    python -m pytest -q tests/test_verifier_freshness_guard.py tests/test_verifier_safety_guard.py \
    tests/test_verifier_client.py tests/test_s4_verifier_independence.py
→ 85 passed  (gabungan dengan FIX-2, 13,81 s)
```
Bukti pasca-patch pada stack E2E klon (bukan DB demo):
```
run_verifier(ctx freshness_score=0.82, model CONSISTENT) → FLAGGED (provider sap_ai_core_primary)
```

**Sisa yang tidak diselesaikan FIX-1 (P1, audit):** verifier masih memakai runtime & system
prompt Supervisor (`AGENTCORE_RUNTIME_ARN` → `mealchain_supervisor_agent`, model
`claude-haiku-4-5`, prompt `supervisor_system_prompt.md`). Guard ini menutup akibatnya
(verdict tidak bisa mengangkat fakta core), tetapi **bukan** independensi model. Perbaikan
sebenarnya = mengubah konfigurasi slot model verifier (env/AgentCore runtime terpisah) →
keputusan owner (§5a).

## 3. FIX-2 — Worker Freshness memakai gerbang certified 0,85/0,60

### Reproduksi (sebelum patch)
Review nyata pada klon (in-process, jalur yang sama dengan `runtime_server`), keputusan
`749bdc55` (Jakarta/telur, 3 batch):
```
freshness facts: {"batch_count":3,"expired_count":0,"worst_freshness_score":0.82,...}
status: ok      blocking: false
warnings: ["skor kesegaran terburuk 0.82; belum sempurna, jangan menyimpulkan aman"]
summary : "3 batch; 0 kedaluwarsa; skor kesegaran terburuk 0.82."
```
Tidak ada `needs_verification` di kosakata worker (`agent/workers/freshness.py:111-139`).

### Root cause
Worker hanya membandingkan skor dengan **1,0** (`if worst_score < 1.0: warning`), sehingga
ambang certified tidak pernah dipakai. Kosakata status tidak memuat hasil klasifikasi.

### Patch (minimal)
`agent/workers/freshness.py`
1. `PASS_THRESHOLD = 0.85`, `VERIFY_THRESHOLD = 0.60` + `classify_freshness()` — cermin
   `backend/app/core/freshness.py`. Worker agen hidup di runtime terpisah yang **hanya** bicara
   HTTP ke backend, jadi ia tidak boleh mengimpor modul backend; kesamaan angka dikunci tes.
2. `facts["freshness_status"]` = `pass|needs_verification|fail` (string — setiap angka di
   `facts` wajib punya sitasi sesuai kontrak `AgentFinding`; ambang adalah aturan, bukan
   pengukuran batch).
3. Warning untuk `needs_verification`/`fail` menyebut status certified + "butuh verifikasi
   manusia, jangan menyimpulkan aman"; ringkasan menyertakan `(status …)`.
4. `blocking` **tidak diubah** (tetap `expired_count > 0`) — lihat §5b.

### Regression test
`backend/tests/test_agent_freshness_gate.py` — 5 kasus:
ambang worker ≡ ambang core (dan paritas `classify_freshness` pada 7 titik);
0,82 → `needs_verification` + warning menyebut verifikasi + tidak ada lagi warning "belum
sempurna"; 0,35 → `fail`; 0,95 → `pass` dan tidak memblokir; batch kedaluwarsa tetap memblokir.

### Hasil (pasca-patch, stack E2E klon)
```
freshness facts: {"batch_count":3,"expired_count":0,"worst_freshness_score":0.82,
                  "freshness_status":"needs_verification", ...}
status: ok   blocking: false
summary : "3 batch; 0 kedaluwarsa; skor kesegaran terburuk 0.82 (status needs_verification)."
warnings: ["skor kesegaran terburuk 0.82; status certified needs_verification (PASS >= 0.85)
            — butuh verifikasi manusia, jangan menyimpulkan aman"]
```

**Jujur soal batasnya:** worker tetap melaporkan `status: ok` dan tidak memveto. Itu disengaja
(§5b); temuan AUD-9A-05 karenanya **belum tertutup penuh** dan strategi readiness memakai label
"sebagian". Batas kedua: himpunan batch yang dinilai worker adalah batch pada **lokasi tujuan**
(`WorkerContext.location` = target keputusan) — perilaku yang oleh audit disebut **P0 AUD-9B-29**
(lokasi sumber seharusnya). FIX-2 memakai gerbang certified dengan benar, tetapi klasifikasinya
menggambarkan himpunan batch yang salah sampai AUD-9B-29 diperbaiki. Karena itu FIX-2 **tidak**
boleh dibaca sebagai "kesegaran batch sumber sudah tergerbang".

## 4. Prioritas (iii) — retry/duplikat: TIDAK TERBUKTI, tidak dipatch

Diuji pada klon dengan 4 request `POST /actions/execute` **bersamaan** (thread paralel) untuk
satu keputusan yang sudah memenuhi dua approval:
```
statuses: [200, 409, 409, 409]
PO rows : 1  (MC-248EFEA12ECE)
retry sesudah sukses → 409 "decision sudah dieksekusi", jumlah PO tetap 1
```
Mekanisme yang membuat ini aman (bukan kebetulan):
1. `_load_decision()` memakai `SELECT … FOR UPDATE` (`backend/app/api/actions.py:78-84`) →
   eksekusi serial per keputusan;
2. penjaga status `executed → 409` (`actions.py:712-720`);
3. nomor PO deterministik dari `decision.id` (`core/po_number.py`), jadi run ulang tidak
   pernah membentuk nomor kedua.

**Kesimpulan:** tidak ada keputusan/PO ganda yang dapat direproduksi → tidak ada patch. Yang
belum diuji: dua proses backend berbeda (bukan dua request) — tetap tertutup oleh row lock,
tetapi tidak dibuktikan di sini (dicatat sebagai NOT TESTED di laporan hasil).

## 5. Dipertimbangkan, TIDAK dilakukan (butuh keputusan owner)

### 5a. Independensi model verifier (AUD-9A-03, P1)
Mengubah `VERIFIER_MODEL_*`/`AGENTCORE_RUNTIME_ARN` berarti mengubah **konfigurasi produksi**
(provider, biaya, kredensial). Bukan patch kode, tidak bisa diuji tanpa kredensial AWS, dan
menyentuh `.env` yang dilarang diubah pada tugas ini. → keputusan owner: runtime/model/prompt
terpisah untuk verifier.

### 5b. `blocking=True` untuk `needs_verification` (AUD-9A-05, P1 sisa)
Audit merekomendasikan `blocking=True` untuk `needs_verification`. **Data demo menolak
konsekuensi itu sekarang:** **40 dari 40** pasangan (lokasi, komoditas) punya skor terburuk
< 0,85 (30 di antaranya tepat 0,82) — `SELECT count(*) filter (where worst < 0.85) … GROUP BY 1,2`
→ 40/40 — dan `safety_veto()` memveto
**setiap** putaran bila satu guardian `blocking`. Artinya demo akan menampilkan "JANGAN
EKSEKUSI" pada hampir semua keputusan — perubahan perilaku produk yang besar, bukan perbaikan
cacat lokal. Pilihan yang tersedia untuk owner:
(a) turunkan literal 0,82 pada data demo (AUD-9B-01/02 — skor tidak dapat direproduksi dari
`compute_freshness_score`), lalu naikkan `blocking`; atau (b) definisikan `needs_verification`
sebagai "minta manusia", bukan "veto", dan tampilkan sebagai status tersendiri di UI.
Sampai keputusan itu ada, worker melaporkan status certified sebagai fakta (§3) tanpa memveto.

### 5c. Guard sesi demo memblokir POST komputasi murni (AUD-9A-06 / AUD-9B-07, P2)
`POST /price/deviation` dan `POST /logistics/estimate` tidak ada di `_JALUR_TANPA_SESI`
(`backend/app/main.py:156-167`). Menambahkannya = melonggarkan gerbang tulis yang merupakan
keputusan keamanan owner (aturan "data hanya berubah selama sesi"). Catatan: lapis kedua sudah
tidak berlaku — `POST /price/deviation` kini `get_current_user` (`api/price.py:150-160`),
sehingga `bgn_monitor` boleh memakainya; pada stack E2E (`DEMO_SESSION_ENFORCE=false`) deviasi
memang terhitung (review Price `ok`, deviasi −0,37% normal).

### 5d. `POST /price/deviation` membalas 500 untuk harga tidak valid (AUD-9B-31, P2)
```
POST /price/deviation {"supplier_price": -5} → 500 Internal Server Error
POST /price/deviation {"supplier_price": 0}  → 500 Internal Server Error
```
`core/price.py:_to_price()` melempar `ValueError` dan endpoint tidak menangkapnya
(`api/price.py:163-190`). Ini input klien tidak valid → seharusnya 422, bukan 500. Tidak
dipatch karena di luar pagar "hanya P0/P1" dan bukan bagian dari tiga prioritas tugas; dicatat
di readiness sebagai temuan terbuka (AUD-9B-31, sudah ada di audit data & math).

### 5e. Veto Safety tidak di-scope ke keputusan (AUD-9A-04, P2)
Review nyata pada klon: `safety_veto=True` dengan `safety_facts {pass:3, fail:0,
active_exclusion_count:1}`; satu-satunya exclusion aktif milik pemasok lain (scope Jakarta).
Memakai `GET /supplier-exclusions/context/{decision_id}` mengubah **hasil** banyak keputusan
demo (over-blocking saat ini "aman"), dan endpoint konteks itu belum terbukti setara. Butuh
keputusan owner + uji data; di luar tiga prioritas.

### 5f. Kelengkapan bukti tidak diperiksa saat approve/execute (AUD-9B-16, P1)
Menjadikan bukti wajib pada approve/execute akan mengubah alur demo (keputusan
`3e2e3cc7`/`64ce3369` ber-SDC tanpa bukti) — keputusan produk. Data demo-nya sendiri adalah
sumber kegagalan 1 tes invarian (§6), jadi urutan yang benar: perbaiki/segarkan data demo,
lalu tegakkan gerbang.

## 6. Catatan: 1 tes gagal pada suite penuh BUKAN akibat patch

`tests/test_bukti_dan_draf_demo.py::test_kasus_skrip_punya_bukti_termasuk_yang_ditolak` gagal
pada klon **pristine** (sebelum patch apa pun):
```
kasus skrip tanpa bukti: [('3e2e3cc7','regional_balance','pending_approval','bukti-hari-ini')]
```
Penyebabnya data demo, bukan kode: keputusan `3e2e3cc7-f53e-5cee-963d-728e87b6b949`
(= `stable_uuid("kasus-bukti","bukti-hari-ini","Jakarta")`) kehilangan **dua** baris
`decision_evidence` (`98b23ee1…` human_inspection, `7d6c714c…` gps) di DB demo; dua baris itu
ada pada klon yang sudah menjalankan penyemai ulang. Ini bukti eksekusi untuk **AUD-9B-16**
("2 keputusan ber-SDC tanpa bukti sama sekali"). Assertion tes **tidak** dilonggarkan dan tidak
di-skip: tes itu benar, datanya yang salah.

## 7. Verifikasi akhir

| Perintah | Exit | Hasil |
|---|---|---|
| `cd backend && .venv/Scripts/ruff.exe check .` | 0 | `All checks passed!` |
| `pytest` penuh di klon (`DATABASE_URL=…/mealchain_a9_final2`, `DEMO_SESSION_ENFORCE=false`, `-q -rs`) | 1 | **1 failed** (data AUD-9B-16), **1612 passed**, 25 skipped, **549,07 s** |
| tes yang sama pada klon setelah kasus demo disemai ulang | 0 | `tests/test_bukti_dan_draf_demo.py` → 2 passed |
| `npx tsc --noEmit` | 0 | bersih, 10 s |
| `npx vitest run` | 0 | 167 berkas / 1822 tes lulus, 35,87 s |
| `verify_stack.py verify/invariants.spec.json` | 0 | PASS 59 / FAIL 0 / SKIP 1, 6 s |

Rincian perintah, jumlah skip beserta alasannya, dan seluruh skenario E2E ada di
`9_AGENT_TEST_RESULTS.md`.

## 8. FIX-3 — AUD-9B-29 (P0): guardian menilai batch SUMBER + exclusion ber-cakupan

Ditambahkan 27 Oktober 2026 sesudah laporan audit 9 agent. Berbasis `0a0eeee`, DB uji
klon `mealchain_a9b29` (`pg_dump` dari `mealchain`, `DROP DATABASE` sesudah selesai).
**DB demo `mealchain` hanya dibaca (SELECT).**

### Reproduksi (sebelum patch)

```python
# in-process, worker produksi, klon, konteks Bandung/telur (sumber Cianjur)
SafetyWorker().run(WorkerContext(location="Bandung", commodity="telur",
                                 source_location="Cianjur", api=api))
→ ok  blocking=True
  facts: {location: "Bandung", batch_count: 3, failed_count: 0, pass_count: 3,
          active_exclusion_count: 1,
          active_exclusion_ids: ["55bb6ed8-948a-594c-b243-0cae49d304fe"]}
```
Dua cacat sekaligus pada keluaran yang sama:

1. **Batch yang dinilai batch Jakarta**, bukan Cianjur. `batch_count: 3` = tiga batch
   Jakarta/telur (semua `pass`); batch Cianjur/telur yang benar-benar dikirim tidak
   pernah dibaca. Variasi yang diuji di skrip E2E: batch sumber `safety_status='fail'`
   → worker tetap melaporkan `failed_count: 0`.
2. **Exclusion tanpa cakupan**: `55bb6ed8` adalah exclusion **CV Ambarawa Telur Utama**
   (supplier `d8ff21f2…`) untuk **SPPG Jakarta**; keputusan Bandung tidak ada
   kaitannya, tetapi exclusion itu tetap memveto (`blocking=True`).

### Root cause

- `agent/workers/safety.py:47-53` dan `agent/workers/freshness.py:74-80` (versi lama)
  menyaring `/batches` dengan `context.location` — dan `context.location` diisi
  `target_location` oleh `context_from_approval`. Lokasi **sumber** sudah ada di
  `context.source_location` tetapi hanya dipakai worker Logistics.
- `agent/workers/safety.py:79-85` (versi lama) mengambil **semua** baris
  `/supplier-exclusions` berstatus `active` tanpa membandingkan `supplier_id`/
  `scope_location_id` — padahal kedua kolom itu ada di skema dan di respons API.
- `approval-summary` tidak membeberkan identitas yang dibutuhkan untuk mencakupkan
  exclusion (`target_location_id`, `supplier.id`) maupun himpunan batch sumber
  (`batch_sumber_transfer`), sehingga worker tidak punya pilihan selain menebak.
- `backend/app/api/actions.py::_source_batches_still_safe` mengembalikan `True` bila
  keputusan tidak punya lokasi/komoditas sumber — jalur "tidak dapat dibuktikan =
  boleh". (Jalur `execute` tetap tertutup oleh `revalidate_transfer`, tetapi guard-nya
  sendiri fail-open.)

### Patch (minimal, 9 berkas kode)

| Berkas | Perubahan |
|---|---|
| `agent/workers/sumber.py` (baru) | `pilih_batch_sumber()` — urutan: `source_batch_ids` binding → lokasi **sumber** + komoditas; tidak pernah lokasi tujuan; `exclusion_berlaku()`/`pisahkan_exclusion()` — cocokkan `supplier_id` + `scope_location_id`, baris tanpa kolom cakupan tetap berlaku (konservatif) dan dilaporkan |
| `agent/workers/base.py` | `WorkerContext` + `target_location_id`, `source_location_id`, `supplier_id`, `source_batch_ids` |
| `agent/workers/safety.py` | menilai batch sumber; `quarantined_count`/`quarantined_batch_ids` memblokir; `active_exclusion_ids` = yang berlaku, `ignored_exclusion_ids` = yang cakupannya lain; sumber tak teridentifikasi → `degraded` + `blocking=True`; exclusion tak terbaca → memblokir |
| `agent/workers/freshness.py` | himpunan batch sumber; sumber tak teridentifikasi / kosong → `blocking=True`; ambang 0,85/0,60 **tidak berubah** |
| `agent/orchestrator.py` | `context_from_approval` mengisi identitas sumber dari `approval-summary` (`target_location_id`, `source_location_id`, `supplier.id`, `safety.batch_ids`) |
| `backend/app/services/approval_summary.py` | + `source_location_id`, `target_location_id`, `safety.batch_ids` (additif); cek exclusion memakai helper bersama |
| `backend/app/services/supplier_exclusion_service.py` | `exclusion_aktif_untuk(db, supplier_id, target_location_id)` — SATU definisi cakupan untuk execute & `can_execute` |
| `backend/app/services/supplier_eligibility.py` | `revalidate_transfer` memakai helper cakupan di atas + pesan blokir menyebut kode sebenarnya (dikarantina ≠ FAIL) |
| `backend/app/api/actions.py` | `_source_batches_still_safe` fail-closed bila identitas sumber tidak lengkap |

Batas skema yang dilaporkan apa adanya: `supplier_exclusions` **tidak punya kolom
komoditas**, jadi exclusion hanya bisa di-scope pada (pemasok, SPPG penerima). Untuk
data demo ini cukup — satu pemasok hanya memasok satu komoditas — tetapi exclusion
"pemasok X untuk komoditas Y" tidak dapat dinyatakan. Tidak ada kolom baru, tidak ada
migrasi.

### Regression test (TDD: RED dulu, 13 kasus)

`backend/tests/test_agent_guardian_scope.py` — sebelum patch **13 failed**, sesudah
**13 passed**:

| Skenario | Kasus |
|---|---|
| (a) batch sumber dinilai | `test_safety_menilai_batch_sumber_bukan_lokasi_tujuan`, `test_freshness_menilai_batch_sumber_bukan_lokasi_tujuan`, `test_batch_terikat_menentukan_himpunan_sumber` |
| (b) karantina/hilang | `test_safety_batch_sumber_dikarantina_memblokir`, `test_safety_batch_terikat_hilang_fail_closed` |
| (c) exclusion cakupan lain | `test_exclusion_lokasi_lain_tidak_memveto`, `test_exclusion_pemasok_lain_lokasi_sama_tidak_memveto` |
| (d) exclusion cocok | `test_exclusion_cakupan_cocok_tetap_memveto`, `test_exclusion_tanpa_kolom_cakupan_tidak_lolos_diam_diam` |
| (e) sumber tak teridentifikasi | `test_safety_tanpa_identitas_sumber_fail_closed`, `test_freshness_tanpa_identitas_sumber_fail_closed`, `test_konteks_tidak_memakai_lokasi_tujuan_sebagai_sumber` |
| konteks | `test_context_dari_approval_summary_membawa_identitas_sumber` |

Jalur tulis: `backend/tests/test_execute_source_scope.py` (3 kasus) — exclusion lokasi
lain tidak memblokir `can_execute`, exclusion lokasi target memblokir, dan
`approval-summary` membeberkan identitas batch sumber yang dipakai agen.
`backend/tests/test_execute_safety_wiring.py` diperketat: sumber tak teridentifikasi
kini **harus** memblokir.

Assertion lama yang disesuaikan (bukan dilonggarkan):

| Tes | Dulu | Sekarang | Alasan |
|---|---|---|---|
| `test_freshness_daftar_kosong_adalah_nol_nyata` | `blocking is False` | `blocking is True` | nol batch sumber = tidak ada bukti; dulu "kosong" berarti "penyaringan lokasi tujuan tidak menemukan apa pun" |
| `test_safety_menandai_fail_dan_exclusion_aktif` | sitasi tanpa `quarantined_count` | + `quarantined_count: 0` | fakta karantina kini dihitung & disitasi |
| `_context()` 3 berkas tes | tanpa `source_location` | `source_location=location` | konteks uji menyatakan sumber secara eksplisit; angka yang diuji tidak berubah |
| `test_golden_04/05` | `_context(api)` | `_context(api, source_location="Jakarta")` | idem |

### Hasil retest

| Perintah | Exit | Hasil |
|---|---|---|
| `cd backend && .venv/Scripts/ruff.exe check .` | 0 | `All checks passed!` |
| `pytest -q tests/test_agent_guardian_scope.py` (sebelum patch) | 1 | **13 failed** (RED) |
| tes yang sama sesudah patch | 0 | **13 passed** |
| `pytest` penuh di klon `mealchain_a9b29` (`-q -rs`) | 1 | **1 failed, 1628 passed, 25 skipped**, 552,44 s — satu-satunya kegagalan tetap `test_bukti_dan_draf_demo.py` (data `3e2e3cc7`/`bukti-hari-ini`, AUD-9B-16), bukan kode |
| E2E HTTP + review agen di klon (`/tmp/a9b29_e2e.py`, 10 assertion) | 0 | **10/10 PASS** (rincian di `9_AGENT_TEST_RESULTS.md` §E) |

Ringkas E2E (klon `mealchain_a9b29`, batch sumber Cianjur/telur `7ed8ff62…`):

```
A. batch sumber safety_status='fail'   → execute 409  "safety revalidation gagal: batch sumber kini FAIL (temperature excursion)"
B. batch sumber kembali 'pass'         → execute 200  po=MC-… (kontrol: 409 di A berasal dari gate)
C. batch sumber quarantine='quarantined' → execute 409 "… batch sumber dikarantina/gagal"
D. keputusan tanpa identitas sumber    → execute 409  (fail-closed)
E. review Jakarta/telur sumber Cianjur → safety source=Cianjur, batch_count=1 (binding), blocking=False,
                                          ignored_exclusion_ids=['55bb6ed8…']  ← veto palsu hilang
F. batch sumber FAIL + review          → safety blocking=True, failed_batch_ids=['7ed8ff62…'], safety_veto=True
G. exclusion Jakarta (pemasok sama) + review Bandung → blocking=False, exclusion diabaikan
H. exclusion Bandung (pemasok sama) + review Bandung → blocking=True, active_exclusion_ids=[…]
```

### Sisa risiko khusus AUD-9B-29

- Identitas batch sumber bergantung pada `approval-summary`. Bila endpoint itu gagal,
  worker Safety/Freshness menjadi `degraded` **dan memblokir** (fail-closed) — jujur,
  tetapi berarti review bisa berhenti karena gangguan baca, bukan karena barangnya
  benar-benar tidak aman. Alternatif "lolos diam-diam" sengaja tidak dipilih.
- Cakupan exclusion tidak bisa memuat komoditas (tidak ada kolomnya). Exclusion yang
  pemasoknya memasok dua komoditas akan memveto keduanya.
- Data demo tetap memuat 0,82 (`AUD-9B-01/02`), jadi `freshness_status` masih
  `needs_verification` pada banyak batch; `blocking` hanya naik bila batch sumber
  benar-benar lewat `usable_until` atau kosong. Ambang tidak diubah.


---

## 9. AUD-9A-03 / AUD-9A-12 — verifier memeriksa fakta sendiri (basis `b5d97e1`)

Tanggal: 27 Oktober 2026. Basis commit: `b5d97e1` (tree bersih). Lingkungan dan aturan DB
sama seperti §0: uji tulis hanya di klon sekali pakai (`pg_dump` → `createdb`), DB demo
`mealchain` dibaca saja — kecuali satu migrasi skema aditif yang dijelaskan di §9.4.

### 9.1 Masalah yang diselesaikan

`VerifierWorker.audit` hanya **mewarisi** `run.verification` (verdict gerbang) dan tidak
pernah membaca data. Ia juga tidak punya prompt sendiri: `run_verifier` menempelkan teks
verifier ke dalam prompt supervisor, dan `VerifierWorker()` dibuat tanpa model di produksi,
sehingga "agent ke-8" adalah presenter verdict, bukan penilai. Akibatnya lima klaim palsu
lolos tanpa jejak (kolom LAMA di §9.2).

Yang dibangun:

| Komponen | Berkas | Isi |
|---|---|---|
| System prompt sendiri | `agent/prompts/verifier_system_prompt.md` | identitas VERIFIER, "klaim supervisor bukan fakta", angka wajib bersitasi, DILARANG menghitung, DILARANG menaikkan verdict, kosakata tiga verdict, skema JSON wajib |
| Toolset baca-saja | `agent/verifier_facts.py` | `VerifierFactsSource.baca()` → `GET /decisions/{id}/audit-facts` + `/approval-summary`; tanpa POST, tanpa tulis |
| Fakta yang dihitung kode | `backend/app/services/audit_facts.py` + `GET /decisions/{id}/audit-facts` | SDC vs rincian (memakai `recommendation_numbers`), evidence, batch sumber (safety/freshness via `supplier_eligibility` + `core/freshness`), exclusion (`supplier_exclusion_service`), blok ledger |
| Cek deterministik | `agent/verifier_checks.py` | 8 cek: angka bersitasi, SDC, safety batch, kesegaran, bukti, exclusion, ledger, konsistensi gerbang |
| Output tervalidasi | `agent/verifier_contracts.py` | pydantic: `verdict` ∈ {consistent, flagged, unavailable}, `checks[]` {nama, klaim, aktual, lulus}, `citations[]` {decision_id/batch_id/evidence_id/ledger_block_id}, `catatan`; tidak sah → `unavailable` |
| Guard pasca-LLM | `agent/verifier_checks.py::jaga_verdict` | model hanya boleh menurunkan/menandai; `consistent` + ada cek gagal / tanpa sitasi / gerbang flag → `flagged`; fakta tidak terbaca → `unavailable`; `blocking` selalu `False` |
| Jejak run | `agent/telemetry.py`, `backend/app/models/decisions.py`, migrasi 039, `backend/app/services/trace_persistence.py` | baris VERIFY = **run anak**: `run_id` sendiri + `parent_run_id` = run review; `persist_agent_review` menerima satu run induk + satu run anak (bentuk 8 baris lama tetap sah) |
| Model produksi | `agent/verifier_model.py` | callable opsional dari `VERIFIER_AGENT_MODEL`/`SUPERVISOR_MODEL_PRIMARY`; tanpa model, verifier tetap deterministik dan `consistent` tidak pernah dikarang |

Empat pagar skill `verifier-agent-adapter` yang **sudah ada** dan dipertahankan: (1) verifier
berjalan sesudah narasi dan tidak masuk `run.findings`; (2) temuannya di `run.verifier_finding`,
status/veto run tetap milik worker analitik; (3) verifier tidak dipakai lane paralel dan
`blocking_allowed=false` di `agent/hierarchy.json`; (4) model hanya membaca fakta, tidak
menghitung ulang angka bisnis.

### 9.2 Red-team sebelum vs sesudah (diukur, bukan diklaim)

Probe memakai lima klaim supervisor yang sama dan fakta yang sama; kolom LAMA = kode `HEAD`
b5d97e1, BARU = kode setelah patch. Model pada kedua kolom diminta menjawab `consistent`.

```
skenario                 LAMA (HEAD)                  BARU                         cek_gagal
a_sdc_selisih            ok/pass                      flagged/degraded             ['sdc_vs_cost_breakdown']
b_safety_fail            ok/pass                      flagged/degraded             ['safety_batch_sumber']
c_bukti_hilang           ok/pass                      flagged/degraded             ['bukti_keputusan']
d_angka_tanpa_sumber     ok/pass                      flagged/degraded             ['angka_bersitasi']
e_freshness_082          ok/pass                      flagged/degraded             ['kesegaran_certified']
```

Kelimanya kini dikunci sebagai tes otomatis `backend/tests/test_agent_verifier_independence.py`
(14 tes): 5 skenario di atas + skema tidak sah, `consistent` tanpa sitasi, model tidak bisa
menaikkan `flagged`, cek ledger, koreksi skema sekali, fakta tidak terbaca (fail-closed),
toolset hanya GET, prompt verifier ≠ prompt supervisor, dan baris VERIFY membawa
`run_id`/`parent_run_id`/sitasi.

### 9.3 Patch yang menyentuh kontrak/perilaku lama

1. **`build_workers()`** kini memberi verifier model dari env (bila ada). Tanpa kredensial,
   perilakunya sama seperti sebelumnya (deterministik).
2. **`test_agent_verifier.py`** — tiga assertion lama yang mengunci "tanpa fakta boleh `ok`"
   **diperketat**: tanpa fakta terbaca hasilnya `unavailable`/`degraded` (fail-closed), bukan
   `ok`. Tidak ada tes yang di-skip atau dilonggarkan.
3. **`test_agent_orchestrator.py`** — daftar endpoint yang dipanggil bertambah
   `/audit-facts` (verifier membaca fakta sendiri). Assertion tetap eksak.
4. **`persist_agent_review`** — aturan baru: baris tanpa `parent_run_id` wajib satu `run_id`
   (regresi lama tetap ditolak dengan pesan "satu run_id"); baris ber-`parent_run_id` wajib
   menunjuk run induk.
5. **`agent/verifier_checks.py`** — cek angka hanya memeriksa **narasi supervisor**, bukan
   ringkasan tujuh worker: ringkasan worker adalah bahan masukan, bukan klaim yang diaudit.
   Tanpa ini setiap review dini ditandai karena angka turunan worker.

### 9.4 Migrasi 039 (skema aditif)

`backend/alembic/versions/039_agent_trace_parent_run_id.py` menambah
`agent_traces.parent_run_id` (UUID NULL) + indeks, `downgrade` menghapus keduanya.

Diuji pada DB **kosong**: `alembic upgrade head` → 24 tabel, `version_num =
039_agent_trace_parent_run_id`; `downgrade -1` → kolom hilang; `upgrade head` → kembali.
DB demo dimigrasikan (skema saja, tanpa mengubah baris) karena model `AgentTrace` sudah
memetakan kolom itu — tanpa migrasi, setiap INSERT jejak pada demo akan gagal.

### 9.5 Satu putaran review NYATA (bukan stub)

Dijalankan di container backend terhadap API yang hidup (baca-saja); provider
`primary:agentcore` menjawab. Keputusan `dea2227f…`:

- fakta yang dibaca verifier sendiri: `sdc_check.cocok=true` (komponen = 16.132.215,46),
  `evidence_count=1`, `batch_sumber=[45268526…, 97b17fd4…]`, `ledger.count=0`;
- verdict model: `flagged`; cek deterministik 8, gagal 0 (gerbang sudah `flag`, narasi disebut
  jujur sebagai memblokir);
- sitasi: `decision_id` + 2 `batch_id` + 1 `evidence_id` (tanpa duplikat);
- baris jejak VERIFY: `run_id=8e7dbebe…`, `parent_run_id=bcf187a5…`, `citations=6`
  (2 hitungan + 4 id) di `AgentFinding`, `audit_verdict=flagged`, `checks_total=8`,
  `checks_failed=0`;
- potongan `catatan` model: "…freshness_score=0.82 berada di bawah ambang pass (0.85) dengan
  status 'needs_verification'… SDC dan bukti konsisten dengan fakta, tetapi kesegaran…".

Ini penting: verifier **tidak** menyalin narasi supervisor dan **tidak** mewarisi verdict —
ia membaca fakta yang sama dari DB dan menilai sendiri, lalu guard menahan `consistent`
karena gerbang sudah `flag`.

### 9.6 Verifikasi (exit code nyata)

| Perintah | Exit | Hasil |
|---|---|---|
| `cd backend && .venv/Scripts/ruff.exe check .` | 0 | `All checks passed!` |
| `ruff check` berkas agent baru | 0 | `All checks passed!` |
| `pytest` verifier/agent/trace di klon `mealchain_verifverif` | 0 | **53 passed** |
| `pytest` tes angka audit (`test_audit_facts_numbers.py`) | 0 | **6 passed** |
| `pytest` penuh di klon baru `mealchain_verif2` | 1 | **9 failed, 1644 passed, 28 skipped**, 562,75 s |
| `pytest` penuh di klon baru `mealchain_headbase` pada **HEAD `b5d97e1`** (pembanding) | 1 | **8 failed, 1618 passed, 28 skipped**, 550,39 s |
| `cd frontend && npx tsc --noEmit` | 0 | tanpa error |
| `cd frontend && npx vitest run` | 0 | suite lulus (48 s) |
| gate `verify_stack.py verify/invariants.spec.json` | 1 | **FAIL 56 / FAIL 4 / SKIP 1** — 4 invarian **data demo**, lihat di bawah |

Sembilan kegagalan pytest penuh = 8 kegagalan yang **sama persis** dengan baseline HEAD
(`test_akun_multi_kota` ×2, `test_demo_seed_per_kota` ×4, `test_demo_session_mulai_atomik`,
`test_demo_template_provenance_ledger`) + 1 tes milik patch ini yang gagal karena pytest
mengumpulkan versi berkas sebelum konstanta uji diperbaiki (lolos saat dijalankan ulang: 6
passed). Delapan sisanya adalah tes penyemaian demo yang bergantung urutan pada klon
`pg_dump` — bukan akibat patch ini, dibuktikan oleh run pembanding di HEAD.

Empat kegagalan gate juga **data**, bukan kode: `baris kanonik batch/keputusan/pasokan
berstempel sesi` (78/7/40 baris) dan `PO tanpa decision_id` (1 baris) — baris-baris itu
ber-`created_at` 2026-10-27 01:34–01:35 UTC (08:34–08:35 WIB), **sebelum** sesi ini mulai
(08:56 WIB); gate PASS terakhir 08:03 WIB. Invarian baru
`kolom agent_traces.parent_run_id` **PASS**.

### 9.7 Sisa risiko

- **Model masih boleh sama dengan supervisor** (`SUPERVISOR_MODEL_PRIMARY`). Yang independen:
  prompt + sumber fakta + cek deterministik. Bila model yang sama keliru membaca fakta, guard
  deterministik tetap menahan `consistent`; tetapi penalaran kualitatifnya tidak independen.
  Untuk independensi penuh, isi `VERIFIER_AGENT_MODEL` dengan model lain.
- **Endpoint `/actions/{id}/verify`** (`backend/app/ai_providers/verifier_client.py`) masih
  memakai runtime + prompt supervisor. Perbaikan ini menyentuh auditor lapis agent, bukan
  endpoint itu — AUD-9A-03 karena itu **sebagian** diperbaiki.
- Cek `angka_bersitasi` hanya memeriksa narasi supervisor; angka turunan di ringkasan worker
  tidak diaudit (kesengajaan, lihat §9.3 butir 5).
- `parent_run_id` hanya terisi untuk baris VERIFY baru; baris historis tetap NULL (tanpa backfill).
