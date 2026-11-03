# BUSINESS_LOGIC_AUDIT — MealChain Guardian

Status: **audit selesai (bukti terkumpul)** — 26 Oktober 2026.
Objek: logika keputusan, approval empat mata, gerbang keselamatan, eligibility
pemasok, dan Safe Delivered Cost (SDC).
Lingkungan: stack berjalan (`mealchain-backend` :8000, `mealchain-postgres`
:15432, DB `mealchain`), commit kerja `feature/db-modes-demo-coverage`.

## 0. Aturan dan batas audit

1. **DB demo `mealchain` hanya dibaca (SELECT).** Tidak ada satu pun `INSERT`/
   `UPDATE`/`DELETE` ke DB demo selama audit. Diperiksa ulang di akhir:
   `decisions=32, approvals=13, agent_traces=69, sap_mock_purchase_orders=12,
   batches=78, batches.quarantine_status='quarantined'=1` — identik dengan
   angka yang diukur sebelum audit dimulai.
2. **Transisi state diuji pada DB klon** `audit_logic`
   (`CREATE DATABASE audit_logic TEMPLATE mealchain` gagal — "source database
   mealchain is being accessed by other users" — sehingga klon dibuat dengan
   `pg_dump -U mealchain -d mealchain | psql -U mealchain -d audit_logic`).
   Aplikasi dijalankan in-process (`fastapi.testclient.TestClient`) di dalam
   kontainer `mealchain-backend` dengan `DATABASE_URL=…/audit_logic`,
   `DEMO_SESSION_ENFORCE=false`, `DEMO_MODE=true`. Klon **dihapus** setelah
   audit (`DROP DATABASE audit_logic`); hanya klon itu yang disentuh.
3. Tidak ada rebuild data demo, tidak ada perubahan `.env`, tidak ada restart
   kontainer, tidak ada instalasi paket.
4. Kredensial demo dibaca dari `app/seed/demo_credentials.py` saat runtime dan
   tidak ditulis di dokumen ini.

Perintah kunci yang dipakai (bentuk asli):

```bash
# klon sekali pakai
docker exec mealchain-postgres psql -U mealchain -d postgres -c "CREATE DATABASE audit_logic;"
docker exec mealchain-postgres sh -c \
  "pg_dump -U mealchain -d mealchain --no-owner --no-privileges | psql -q -U mealchain -d audit_logic"

# menjalankan probe (skrip sementara, dihapus sesudah audit)
docker exec -e DATABASE_URL='postgresql+asyncpg://<user>:<pw>@postgres:5432/audit_logic' \
  -e DEMO_MODE=true -e DEMO_SESSION_ENFORCE=false -e MULTI_AGENT_REVIEW=false \
  mealchain-backend python _audit_tmp/probe_<bagian>.py

# suite tes milik repo pada klon
docker exec -e DATABASE_URL='postgresql+asyncpg://<user>:<pw>@postgres:5432/audit_logic' \
  -e MULTI_AGENT_REVIEW=false mealchain-backend python -m pytest \
  tests/test_approval_four_eyes.py tests/test_approval_matrix.py \
  tests/test_can_execute_parity.py tests/test_safety_gate_rules.py \
  tests/test_quarantine_core.py tests/test_quarantine_api.py \
  tests/test_verifier_tidak_bisa_diulang.py -q
# hasil: 66 passed, 1 warning in 28.94s
```

## 1. Ringkasan temuan

| ID | Severity | Temuan | Status |
|---|---|---|---|
| BL-01 | **P2** | `cost_breakdown` disalin apa adanya saat kuantitas diskalakan 0,7 → komponen `purchase` lebih besar dari `safe_delivered_cost` pada 4 keputusan; rekonsiliasi 6 komponen gagal 4/25 | Terbuka |
| BL-02 | **P2** | `execute` menerbitkan PO dan menulis status `executed` walaupun **semua** batch terikat ditahan (bukti suhu kosong): `dikirim=[]`, `ditahan=[…]` — "executed" tidak berarti "berangkat" | Terbuka (perilaku sadar, label menyesatkan) |
| BL-03 | **P2** | Gerbang batch menganggap "log suhu lengkap" = "aman": log 33 °C selama 60 menit **LOLOS** `batch_blokir_eksekusi` | Terbuka (laten: belum ada endpoint penambah log) |
| BL-04 | **P2** | `quarantine_status='failed'` **tidak** dikecualikan dari pembentukan kandidat (hanya `quarantined`) → rekomendasi eligible yang pasti ditolak 409 saat execute | Terbuka |
| BL-05 | P3 | Pesan `execute` selalu "batch sumber kini FAIL" untuk karantina/kedaluwarsa, bukan penyebab sebenarnya | Terbuka |
| BL-06 | P3 | `/demo/event1` mencatat verdict `flagged` tetapi status tetap `proposed`; `/actions/verify` menulis `verifier_flagged` | Terbuka |
| BL-07 | P3 | `docs/kamus-kpi-dan-state-machine.md` §4.2 salah: "Event 2 (safety disruption) → review_only" — kode: `safety_disruption` = Event 3 dan `proposed`; `price_anomaly` (Event 2) yang `review_only` | Terbuka (dokumen) |
| BL-08 | P3 | Keputusan administratif (eksklusi/restorasi pemasok) dengan verdict `consistent` cukup **1** approval — bukan empat mata | Sesuai dokumen (risiko dicatat) |
| BL-09 | P3 | Batch yang sudah `dispatched_at` tidak muncul di `dikirim` maupun `ditahan`; respons execute bisa `dikirim=[] ditahan=[]` tanpa penjelasan | Terbuka |

Tidak ada temuan **P0** (jalur yang mengeksekusi tanpa approval/verifikasi) dan
tidak ada **P1** pada keadaan data hari ini; BL-03 menjadi P1 begitu ada kanal
telemetri suhu yang menambah sampel setelah evaluasi.

## 2. State machine keputusan

CHECK constraint: `proposed | verifier_flagged | pending_approval | approved |
rejected | executed | review_only` (`app/models/decisions.py:51-55`).

### 2.1 Transisi yang SAH (diturunkan dari kode)

| Dari | Ke | Pemicu | Pagar (berkas:baris) |
|---|---|---|---|
| — | `proposed` | `POST /decisions`, `/actions/repropose`, Event 1/3 | `api/decisions.py`, `api/actions.py:955-970`, `services/event1_orchestrator.py:205-233` |
| — | `review_only` | Event 2 (anomali harga) | `services/event2_service.py:219-237` |
| `proposed`/`verifier_flagged` | `pending_approval` | `POST /actions/propose` | `api/actions.py:373-409` (status, scope, expiry, komoditas) |
| `proposed`/`verifier_flagged`/`pending_approval` | `verifier_flagged` | `POST /actions/verify` verdict FLAGGED | `api/actions.py:423-553` |
| `pending_approval`/`verifier_flagged` | `approved` | approve sampai kuorum matriks | `api/actions.py:634-656` |
| `pending_approval`/`verifier_flagged` | `rejected` | approve `approved=false` + komentar | `api/actions.py:628-633` |
| `pending_approval`/`verifier_flagged`/`approved` | `executed` | `POST /actions/execute` | `api/actions.py:697-909` |
| `rejected` | (anak baru `proposed`) | `POST /actions/repropose` | `api/actions.py:921-999` |
| `review_only` | — | terminal | `api/actions.py:709-713` |
| `executed` | — | terminal (idempoten hanya untuk tipe administratif) | `api/actions.py:714-722` |

### 2.2 Transisi TERLARANG — diuji nyata (klon)

Kode yang dipakai: `a1002661…` (safety_disruption Jakarta), `3e2e3cc7…`
(regional_balance Jakarta), `5e969ff1…` (regional_balance Bandung), `b9593aa1…`
(price_anomaly review_only Bandung), `d2c7131c…` (supplier_exclusion executed),
`098eccdd…` (supplier_procurement rejected), `2ae7e0f9…` (restorasi tanpa verdict).

| Uji | Harapan | Hasil nyata |
|---|---|---|
| execute `review_only` (head Bandung, dalam cakupan) | 409 | **409** `decision tinjauan (review-only) — tidak untuk dieksekusi` |
| execute `pending_approval` tanpa approval | 409 | **409** `approval belum memenuhi requirement (missing/rejected)` |
| execute `executed` (ulang) | 409 | **409** `decision sudah dieksekusi` |
| execute setelah 1 setuju + 1 tolak | 409 | **409** `decision ditolak` |
| execute keputusan kedaluwarsa | 409 | **409** `decision expired` |
| execute oleh `sppg_nutritionist` | 403 | **403** `role tidak diizinkan` |
| execute oleh `bgn_monitor` | 403 | **403** `role tidak diizinkan` |
| execute keputusan SPPG lain | 403 | **403** `keputusan di cakupan lokasi di luar SPPG Anda` |
| approve `executed` (akun baru) | 409 | **409** `decision status executed tidak dapat di-approve` |
| approve `rejected` (akun baru) | 409 | **409** `decision status rejected tidak dapat di-approve` |
| approve `review_only` (setuju maupun tolak) | 409 | **409** `decision status review_only tidak dapat di-approve` |
| verify `executed` / `review_only` | 409 | **409** `verify hanya untuk decision pra-approval (status kini …)` |
| verify ulang setelah verdict tercatat | 409 | **409** `verdict sudah tercatat — hasil audit tidak bisa ditimpa` |
| verify keputusan kedaluwarsa | 409 | **409** `decision expired` |
| propose `executed` / `review_only` | 409 | **409** `decision status … tidak dapat diajukan untuk persetujuan` |
| propose keputusan kedaluwarsa | 409 | **409** `decision expired` |
| repropose yang belum `rejected` | 409 | **409** `re-propose hanya untuk decision rejected` |
| reject tanpa komentar | 422 | **422** `penolakan wajib menyertakan alasan (comment)` |
| approve saat `verifier_note='unavailable'` | 409 | **409** `keputusan belum diverifikasi …` |
| execute saat `verifier_note='unavailable'` | 409 | **409** `decision belum terverifikasi` |

Catatan urutan pagar (bukan cacat, tetapi memengaruhi pesan yang dibaca
pengguna): pagar **scope** berjalan sebelum pagar status (`api/actions.py:705`
vs `:709`), sehingga pengguna di luar cakupan menerima 403 — bukan pesan
review-only. Pagar **duplikat akun** pada `approve` berjalan sebelum pagar
status (`:577-599`): akun yang sudah pernah menyetujui keputusan `executed`
membaca "approval sudah tercatat untuk akun ini", bukan "status tidak dapat
di-approve". Ini disengaja (komentar kode `:592-595`) dan terbukti pada uji
pertama; uji ulang dengan **akun berbeda** menghasilkan 409 status.

## 3. Approval empat mata

Matriks: `app/core/approval_matrix.py`. Keputusan operasional memakai
`dua_role_wajib=True` (`api/actions.py:104-112`), jadi **dua role berbeda**
(`sppg_head` **dan** `sppg_nutritionist`) wajib, apa pun verdict verifier.
Keputusan administratif mengikuti verdict (CONSISTENT = 1 approval).

| Kriteria | Bukti |
|---|---|
| Dua akun berbeda | approve #1 head → 200 `pending_approval`; approve #2 akun **head lain** (lokasi sama) → 200 tetapi status **tetap** `pending_approval`; approve #3 nutritionist → 200 `approved` |
| Akun sama dua kali | **409** `approval sudah tercatat untuk akun ini — empat mata berarti approver berbeda…` |
| Kunci DB | unique index `uq_approvals_decision_user (decision_id, approved_by)`; kueri duplikat = **0 baris** |
| Role sah | `bgn_monitor` → **403**; nutritionist boleh approve, **tidak** boleh execute (403) |
| Scope lokasi | head/nutritionist SPPG lain → **403** pada approve, verify, propose, execute, repropose |
| Approval lokasi lain tidak dihitung saat execute | 1 approval sah (head Bandung) + 1 approval nutritionist **Jakarta** yang disisipkan langsung ke DB → execute **409** `approval scope tidak memenuhi requirement` |
| Kuorum divalidasi backend saat execute | `pending_approval` tanpa approval → 409; approve baru (bukan status) yang menaikkan ke `approved`; `execute` menghitung ulang `evaluate_approvals` global **dan** ter-scope (`api/actions.py:735-766`) |
| Satu penolakan menggugurkan kuorum | head setuju (200, `satisfied=false`, `missing=[["sppg_nutritionist"]]`) → nutritionist menolak + komentar (200, `decision_status=rejected`) → execute **409** `decision ditolak` |
| Penolakan wajib alasan | reject tanpa komentar → **422**; 0 baris `approvals` dengan `approved=false` tanpa komentar di DB demo |
| Status `approved` ≠ terkirim | `approved` → `executed` hanya lewat `execute` (PO + `dispatched_at`), terbukti pada uji B6→B7 |
| Jejak audit | `approvals` (aktor+komentar), `agent_traces`, `ledger_blocks` (`append_block` pada approve/reject/execute) |

Keterbatasan yang tercatat: (a) role approver dibaca dari `users.role` **saat
evaluasi**, bukan disimpan per-approval — perubahan role historis akan
mengubah tafsir kuorum lama; (b) keputusan administratif `consistent` cukup
1 approval (BL-08); (c) race dua approval simultan hanya dijaga unique index,
tidak diuji dengan thread paralel (**NOT TESTED**).

## 4. Gerbang keselamatan (safety gate)

Modul murni `app/core/safety_gate.py`; dipakai `execute`, `approval-summary`
(`can_execute`), dan penerimaan barang (`api/receipts.py:228-241`).

### 4.1 `batch_blokir_eksekusi` — hasil ukur

| Keadaan batch | Hasil |
|---|---|
| `pass` + `none` + log 2 sampel dalam rentang + belum kedaluwarsa | **LOLOS** |
| `quarantine_status='quarantined'` | **dikarantina** |
| `quarantine_status='failed'` | **dikarantina** |
| `safety_status='pending'` | **safety_status_bukan_pass** |
| `safety_status='needs_verification'` | **safety_status_bukan_pass** |
| `usable_until` sudah lewat | **kedaluwarsa** |
| log suhu `[]` | **bukti_suhu_tidak_lengkap** |
| log suhu 1 sampel | **bukti_suhu_tidak_lengkap** |
| log 2 sampel dengan timestamp duplikat | **bukti_suhu_tidak_lengkap** |
| **log 2 sampel, 33 °C dan 34 °C (60 menit di luar rentang 0–8 °C)** | **LOLOS** ← BL-03 |

Penyebab BL-03: `_bukti_suhu_lengkap` hanya memeriksa `summary.complete` dan
`observed_minutes > 0` (`safety_gate.py:53-59`); nilai `outside_minutes` tidak
pernah dibaca. `evaluate_safety` pada log yang sama mengembalikan `fail`
(60 ≥ ambang 30 menit), jadi dua modul memberi kesimpulan berbeda untuk data
yang sama. Hari ini dampaknya laten karena belum ada endpoint yang menambah
sampel suhu setelah evaluasi (`grep temperature_log app/api/*.py` → hanya
pembaca); begitu telemetri reefer masuk, batch berstatus `pass` lama bisa
diberangkatkan dengan bukti yang justru menunjukkan ekskursi.

### 4.2 `penghalang_sumber` — pagar revalidasi saat `execute`

| Himpunan batch sumber | Hasil |
|---|---|
| kosong | **tidak_ada_batch_sumber** |
| ada satu `fail` + satu `pass` | **safety_status_fail_sumber** |
| hanya `pending` | **LOLOS** (disengaja: `pending` normal pra-uji) |
| `quarantined` | **dikarantina** |
| `failed` | **dikarantina** |
| `usable_until` lewat | **kedaluwarsa** |

Konsekuensi yang perlu disadari: karena `pending` tidak memblokir dan
`penghalang_sumber` tidak membaca `temperature_log`, keputusan bisa
`executed` + PO terbit sementara **semua** batch ditahan saat pengiriman
(BL-02, §7). Respons `execute` melaporkan `ditahan` beserta alasannya; UI
tidak boleh menggambar batch itu sebagai truk (lihat kamus §4.4).

### 4.3 Bukti API pada klon

| Uji | Hasil |
|---|---|
| `execute` saat batch terikat `quarantined` | **409** `safety revalidation gagal: batch sumber kini FAIL` |
| `execute` saat batch terikat `quarantine_status='failed'` | **409** (pesan sama — BL-05) |
| `execute` saat batch terikat kedaluwarsa | **409** (pesan sama — BL-05) |
| `execute` saat bukti suhu batch terikat `[]` | **200** `status=executed`, `dikirim=[]`, `ditahan=[{batch, "bukti_suhu_tidak_lengkap"}]`; `dispatched_at` tetap `NULL`; `usable_until` **tidak** diperpanjang |
| `POST /batches/{id}/quarantine` tahan batch `pass` | **201** |
| tahan ulang batch yang sudah ditahan | **409** `transisi tidak sah: quarantined + tahan` |
| lepas batch ditahan | **200** `released` |
| `gagal` pada batch `released` | **409** `transisi tidak sah: released + gagal` |
| tahan batch `safety_status='fail'` | **409** `batch sudah fail; karantina tidak diperlukan` |
| tahan/lepas batch SPPG lain | **403** `cakupan lokasi di luar SPPG Anda` |
| `POST /receipts/{id}/approve` batch terkarantina | **409** `barang masih berstatus karantina — tidak boleh masuk stok…` |

Tabel transisi karantina yang diuji menyeluruh (12 pasangan status×aksi):
`none→quarantined` (tahan), `quarantined→released` (lepas),
`quarantined→failed` (gagal), `released→quarantined` (tahan); **semua**
pasangan lain ditolak, termasuk seluruh aksi atas `failed` (terminal).

## 5. Eligibility pemasok

| Kriteria | Bukti |
|---|---|
| Skor tidak mengalahkan hard gate | `calculate_candidate_score(safety_status='fail', reliability=1, freshness=1)` → `score=0`, `eligible=false` (`core/scoring.py:70-73`) |
| `pending`/`needs_verification` tidak dieksklusi | skor 0,9801 (reliability 0,99) untuk keduanya; `needs_verification` diberi `review_required=true` |
| Exklusi pemasok dihormati di kandidat | batch dengan `excluded_destinations=["B"]` → **0 kandidat** ke B (`candidate_generation.py:171-174`) |
| Exklusi dihormati saat execute | `revalidate_transfer` menolak 409 bila ada `supplier_exclusions` aktif untuk `supplier_id`+`scope_location_id=target` (`supplier_eligibility.py:201-219`) |
| Karantina mengeluarkan kg dari kandidat | `quarantine_status='quarantined'` → 0 kandidat (dari 100 kg) |
| **Karantina `failed`** | **tetap** menghasilkan kandidat 100 kg → **BL-04** |
| `released` | kembali menjadi kandidat (benar) |
| Pengadaan pemasok (`supplier_procurement`) | mengecualikan **semua** status karantina ≠ `none` (`supplier_procurement.py:270-272`) — konsisten dengan safety gate |
| supplier tidak dapat ditebak | `resolve_binding` menolak 409 `supplier_unknown` bila batch sumber punya >1 supplier (`supplier_eligibility.py:107-118`) |

BL-04 adalah ketidaksesuaian definisi antar-dua modul: gerbang eksekusi
memperlakukan `quarantined` **dan** `failed` sebagai penghalang
(`safety_gate.py:37`), pembentuk kandidat hanya `quarantined`
(`candidate_generation.py:131`). Akibatnya UI bisa menawarkan rekomendasi yang
dijamin 409 saat dieksekusi — persis kelas cacat yang dicegah oleh komentar
"paritas `can_execute`" di modul yang sama. Tidak ada tes yang menutup kasus
ini (`tests/test_quarantine_candidates.py` hanya menguji `quarantined`,
`released`, dan batch tanpa kunci).

## 6. Safe Delivered Cost (SDC)

Rumus terkunci (`core/safe_delivered_cost.py:104-141`):
`total = purchase + transport + handling + expected_loss + freshness_risk +
safety_penalty`, tiap komponen dibulatkan HALF_UP 2 desimal, total = jumlah
komponen terbulatkan.

### 6.1 Rekonsiliasi pada data demo (25 keputusan ber-`cost_breakdown`)

| Ukuran | Hasil |
|---|---|
| `sum(6 komponen) == safe_delivered_cost` | **21 / 25** |
| Gagal rekonsiliasi | **4** — `a689f24e…` (420 kg), `552ef62b…` (420 kg), `30bce401…` (420 kg), `ed68955c…` (546 kg) |
| `purchase > safe_delivered_cost` (mustahil secara aritmetika) | **4** keputusan yang sama |
| `logistics == transport` (alias) | 25/25 |
| `transport_linehaul + transport_supplier_leg == transport` | 25/25 |
| Satuan & presisi | rupiah, 2 desimal, semua string numerik; `purchase/quantity` konsisten sebagai harga per kg (`27.764,32`, `25.449,00`, …) |
| `purchase = quantity × harga/kg` | benar pada semua 21 keputusan yang cocok |

Contoh nyata (`ed68955c…`, shortage-darurat 546 kg):

```
safe_delivered_cost   = 15.456.603,67
purchase              = 21.656.169,60   ← lebih besar dari total
transport             =     14.818,75
handling              =    150.000,00
expected_loss         =    259.874,04
freshness_risk        =          0,00
safety_penalty        =          0,00
jumlah 6 komponen     = 22.080.862,39
selisih               = -6.624.258,72
```

Akar masalah (bukan pembulatan): `app/seed/demo_template.py:788-811` membuat
"kejadian kedua hari ini" dengan `kuantitas = d.quantity_kg * 0.7`,
`biaya = d.safe_delivered_cost * 0.7`, tetapi **`cost_breakdown=d.cost_breakdown`
disalin tanpa dihitung ulang**. Totalnya diskalakan linear padahal `handling`
adalah biaya tetap dan `expected_loss` bergantung pada `purchase`, sehingga
rincian tidak mungkin menjumlah ke total. Empat keputusan yang gagal adalah
persis salinan 0,7 itu (420/600 dan 546/780 = 0,7 tepat).

Dampak: kartu bukti UI menghitung ulang enam komponen dan menolak mengutip
total (`frontend/lib/evidence.ts:1070-1086`, baris "Rekonsiliasi rincian"
dengan hint "jangan dikutip sampai dihitung ulang") — jadi UI jujur, tetapi
angka yang terpampang memang tidak bisa direkonsiliasi. Jalur perbaikan yang
sudah ada: `services/demo_cost.py::hitung_biaya_demo` menghitung ulang dari
batch+harga nyata (dan menolak batch `safety_status='fail'`), hanya belum
dipakai untuk keputusan salinan ini.

### 6.2 Komposisi `cost_breakdown`

Kunci yang dikirim: `purchase, transport, logistics, transport_linehaul,
transport_supplier_leg, handling, expected_loss, freshness_risk,
safety_penalty, supplier_leg_km, supplier_leg_reference, basis`.

`logistics` adalah **alias** `transport` dan `transport` adalah jumlah dua
pecahan angkut. Menjumlahkan seluruh kunci rupiah akan menghitung angkut dua
kali; UI menanganinya dengan mengambil `transport` saja
(`evidence.ts:1038-1041`). Ini bukan cacat, tetapi dokumentasi kontrak wajib
menyebutkannya agar konsumen baru tidak menjumlah semua kunci.

### 6.3 SDC saat eksekusi

`unit_price = safe_delivered_cost / quantity_kg` (`api/actions.py:815-818`);
`quantity ≤ 0`, `unit_price ≤ 0`, `SDC` kosong, atau `commodity` hilang →
**422** (tidak ada PO dengan harga 0). Uji nyata pada klon: keputusan 300 kg /
SDC 9.750.000 → `POST /actions/execute` 200 dengan `po_number=MC-AAAAAAAA0000`,
`data_source=MOCK`, `status=executed`; harga satuan yang ditulis adalah
`9.750.000 / 300 = Rp32.500,00` (via `unit_price`, bukan angka lain). Jalur
`can_execute` juga memblokir kuantitas/biaya kosong
(`tests/test_can_execute_parity.py` — lulus pada klon).

**Catatan data (bukan cacat):** 12 baris `sap_mock_purchase_orders` di dataset
demo semuanya ber-`decision_id NULL` (nomor `4500000001…4500000012`). API
menandainya `origin="demo"` (`api/sap_orders.py:102-105`) dan metrik KPI
mem-join lewat `po.decision_id` (`kpi_service.py:350`), jadi PO demo tidak
pernah masuk Safe Delivered Cost maupun Decision Time. Konsekuensi yang wajar:
kedua metrik itu hanya bergerak setelah `execute` nyata — sesuai kamus §5.

## 7. Temuan rinci

### BL-01 — `cost_breakdown` tidak dihitung ulang saat kuantitas diskalakan (P2)

- **Klaim produk:** "rincian selalu menjumlah persis ke total" (`services/demo_cost.py:12-14`, `core/safe_delivered_cost.py:14-15`).
- **Kenyataan:** 4 dari 25 keputusan gagal rekonsiliasi; `purchase` > total.
- **Lokasi:** `backend/app/seed/demo_template.py:788-811`.
- **Bukti:** tabel §6.1 + kueri `select … (cost_breakdown->>'purchase')::numeric …`.
- **Saran:** panggil `hitung_biaya_demo` untuk setiap salinan, atau jangan skalakan SDC tanpa menghitung ulang komponen (handling tetap, transport tidak linear penuh).

### BL-02 — `executed` tidak berarti barang berangkat (P2)

- **Klaim:** "Eksekusi = barang berangkat" (`api/actions.py:880-882`), "approval bukan pengiriman" (kamus §4.3).
- **Kenyataan:** execute dengan batch ber-`temperature_log=[]` → **200 `executed`**, PO terbit, `dikirim=[]`, `ditahan=[1 batch]`, `dispatched_at` tetap `NULL`.
- **Lokasi:** `api/actions.py:697-909`, `:280-343`, `core/safety_gate.py:86-111`.
- **Risiko:** pembaca laporan demo menyimpulkan "sudah terkirim" dari status `executed`; satu-satunya koreksi ada di array `ditahan` yang mudah diabaikan.
- **Saran:** tambahkan penanda eksplisit (`executed_tanpa_kiriman` / `shipped_count`) atau tolak execute bila seluruh batch terikat ditahan.

### BL-03 — bukti suhu "lengkap" dianggap "aman" (P2, laten)

- Bukti, lokasi, dan saran: §4.1. Tambahkan `outside_minutes` ke gerbang (blokir bila > 0 selama pengiriman), atau panggil `evaluate_safety` di gerbang, bukan hanya `summarize_temperature_log`.

### BL-04 — `quarantine_status='failed'` masih menghasilkan kandidat (P2)

- **Klaim:** batch ditahan tidak boleh menyumbang kilogram (`candidate_generation.py:128-132`).
- **Kenyataan:** `failed` menghasilkan kandidat 100 kg (uji langsung `generate_candidates`).
- **Lokasi:** `core/candidate_generation.py:131` vs `core/safety_gate.py:37`.
- **Saran:** gunakan `KARANTINA_BLOKIR` (satu definisi) di kedua tempat; tambah tes `failed` pada `tests/test_quarantine_candidates.py`.

### BL-05 — pesan galat menyalahkan penyebab yang salah (P3)

- **Kenyataan:** batch `quarantined`, `failed`, dan kedaluwarsa semuanya dijawab `safety revalidation gagal: batch sumber kini FAIL`.
- **Lokasi:** `api/actions.py:797-804` + `services/supplier_eligibility.py:210-216` (pesan hardcode, alasan `penghalang_sumber` dibuang).
- **Saran:** teruskan `alasan` dari `penghalang_sumber`.

### BL-06 — verdict FLAGGED tidak mengubah status pada jalur Event 1 (P3)

- `/actions/verify` → `verifier_flagged`; `/demo/event1` → status tetap `proposed`, `verifier_note='flagged'` (`event1_orchestrator.py:205-233`). Terukur pada keputusan hasil uji Event 1 di klon: `5ae2b9c1…` (`status=proposed`, `verifier_note=flagged`).
- Dampak: daftar/filter "verifier_flagged" dan hitungan notifikasi tidak memuat temuan Event 1. Pagar approve/execute tetap benar (verdict dibaca dari `verifier_note`, bukan dari status), jadi ini cacat representasi, bukan celah keamanan.

### BL-07 — kamus state machine salah menyebut Event 2 (P3, dokumen)

`docs/kamus-kpi-dan-state-machine.md:295` menulis "Event 2 (safety disruption)
──► review_only". Kode: `event2_service.py` = **price_anomaly** → `review_only`;
`event3_service.py` = **safety_disruption** → `proposed` (dapat di-approve dan
dieksekusi). Kesalahan ini berpotensi dipakai sebagai klaim audit yang salah.

### BL-08 — empat mata tidak berlaku untuk keputusan administratif `consistent` (P3)

`approval_requirement("consistent", dua_role_wajib=False)` → 1 approval dari
`sppg_head` **atau** `sppg_nutritionist` (`core/approval_matrix.py:30-35`).
Satu orang dapat mengeksekusi eksklusi pemasok. Konsisten dengan dokumen
(`kamus §4.3`), tetapi bertentangan dengan judul "approval empat mata" di UI
bila tidak diberi penjelasan.

### BL-09 — batch yang sudah berangkat tidak dilaporkan (P3)

`_dispatch_bound_batches` melewati batch dengan `dispatched_at is not null`
tanpa memasukkannya ke `dikirim` maupun `ditahan` (`api/actions.py:325-326`).
Pada data demo (65/78 batch sudah berangkat) hasilnya `dikirim=[] ditahan=[]`
meski PO terbit — keterangan "tidak ada batch baru yang berangkat" hilang.

## 8. Yang TIDAK diuji

| Butir | Alasan |
|---|---|
| Race dua approve/execute simultan (thread/worker nyata) | Hanya dijaga unique index; tidak diuji konkurensi — **NOT TESTED** |
| Endpoint `/decisions` (baca) vs klaim notifikasi | Di luar lingkup audit logika ini (lihat AUDIT_03/06) |
| Perilaku saat DB gagal di tengah `execute` (PO tertulis, trace gagal) | Tidak disimulasikan — **NOT TESTED** |
| Penambahan sampel suhu setelah evaluasi (BL-03) | Tidak ada endpoint penulis `temperature_log` — **NOT TESTED** |
| Perubahan role pengguna setelah approval (tafsir kuorum historis) | Tidak diuji — **NOT TESTED** |
| `POST /actions/verify` pada `pending_approval` tanpa approval (dengan provider hidup) | Sengaja dihindari agar tidak memanggil model eksternal saat audit; pagar status terbaca di kode — **NOT TESTED** |
| Kinerja/indeks pada volume besar | Di luar lingkup |

## 9. Kesimpulan

Pagar inti **bekerja**: tidak ada jalur yang mengeksekusi tanpa verdict dan
kuorum, empat mata menolak akun ganda dan role/lokasi yang salah, batch
`quarantined`/`failed`/kedaluwarsa tidak bisa dieksekusi maupun diterima, dan
skor pemasok tidak dapat mengalahkan hard safety gate. Yang perlu diperbaiki
adalah **ketepatan representasi**: rincian biaya yang tidak menjumlah (BL-01),
status `executed` yang tidak berarti barang berangkat (BL-02), definisi
"bukti suhu cukup" yang tidak memeriksa nilai suhu (BL-03), dan satu definisi
karantina yang dipakai berbeda oleh dua modul (BL-04).
