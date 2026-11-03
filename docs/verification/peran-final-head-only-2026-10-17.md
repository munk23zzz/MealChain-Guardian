# Peran final: Head-only propose/execute + dua approval + pagar tata kelola

> **Snapshot 17 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tanggal:** 2026-10-17 · **Repo:** `E:\hackathon\HackathonAWS\mealchain-guardian`
**Dasar keputusan owner:** PLAN.md §13.1, §13.3, dan pilihan "a" untuk jalur admin
Monitor (dipertahankan + pagar). Ceklis pembanding: `docs/verification/ceklis-role-vs-plan-2026-10-17.md`.

## Yang diubah

| Berkas | Perubahan |
|---|---|
| `backend/app/api/actions.py` | `PROPOSER_ROLES = ("sppg_head",)`; `propose`, `repropose`, `execute` kini Head-only. `verify` & `approve` tetap dua role. `_requirement_for()` menandai keputusan operasional sebagai wajib dua role. |
| `backend/app/core/approval_matrix.py` | `approval_requirement(verdict, *, dua_role_wajib=False)`. Operasional → selalu 2 grup (`sppg_head` + `sppg_nutritionist`), apa pun verdict. |
| `backend/app/services/approval_summary.py` | `_requirement_for()` ikut aturan yang sama supaya `can_execute`/`approval_state` parity dengan execute (dulu hanya sempat diubah di `actions.py`). |
| `backend/app/api/supplier_exclusions.py` | `POST /supplier-exclusions/proposals` Head-only (Nutritionist tidak mengusulkan). `restore` tidak diubah. |
| `backend/app/api/admin.py` | Pagar tata kelola: `bgn_monitor` tidak boleh mengubah peran akunnya sendiri (`422 "tidak boleh mengubah peran sendiri"`). Mengelola pengguna/lokasi lain tetap boleh. |
| `frontend/components/DecisionActions.tsx` | `execute` & `repropose` hanya untuk `sppg_head`; `approve` tetap untuk Head dan Nutritionist. |
| `backend/tests/test_peran_final_head_only.py` | **Baru**, 10 tes: 3 penolakan Nutritionist (propose/repropose/execute), 2 jalur yang tetap boleh (Head propose, Nutritionist verify), 2 tes matriks requirement, 2 tes pagar admin, 1 tes proposal supplier exclusion. |
| `backend/tests/{test_actions,test_action_boundary_e2e,test_approval_summary,test_supplier_exclusion_api}.py` | Tes lama yang mengunci kebijakan "1 approval cukup" / "Nutritionist mengeksekusi" diselaraskan. |
| `frontend/tests/decision-loop.test.tsx` | Ekspektasi `visibleActions` diselaraskan (Nutritionist: approve saja; Head: approve + execute). |

## Bukti hidup (probe RBAC, akun demo)

Metode: body sengaja salah tipe. Dependency `require_roles` dinilai sebelum validasi body, jadi
**403 = diblokir**, **422 = lolos gerbang**. Tidak ada data yang berubah.

| Endpoint | Sebelum | Sesudah |
|---|---|---|
| `POST /actions/propose` | head 422 · **nut 422** · monitor 403 | head 422 · **nut 403** · monitor 403 |
| `POST /actions/execute` | head 422 · **nut 422** · monitor 403 | head 422 · **nut 403** · monitor 403 |
| `POST /actions/repropose` | head 422 · **nut 422** · monitor 403 | head 422 · **nut 403** · monitor 403 |
| `POST /actions/verify` | nut 422 | nut 422 (tetap) |
| `POST /actions/approve` | nut 422 | nut 422 (tetap) |
| `POST /supplier-exclusions/proposals` | nut 422 | **nut 403** |
| `PATCH /admin/users/{id}`, `PATCH /admin/locations/{id}` | monitor 422 | monitor 422 (tata kelola dipertahankan) |

Pagar peran sendiri diuji di `test_monitor_tidak_boleh_ubah_peran_sendiri` (422 + pesan "sendiri") dan
`test_monitor_tetap_boleh_atasi_pengguna_lain` (200).

## Hasil gerbang

- `pytest tests/test_peran_final_head_only.py` → **10 passed** (diulang 3×, stabil).
- Kelompok berkas terdampak (actions, action_boundary_e2e, approval_matrix, approval_summary,
  supplier_exclusion_api, demo_event1, admin, decision_read, event1_e2e, dossier, rejection_loop,
  s4_rulings) → **73 passed** pada run saat suite sesi lain sedang tidak aktif; pada run berikutnya
  kegagalan BERPINDAH-PINDAH di tes yang memakai akun fixture, dengan galat
  `401 {"detail":"email atau password salah"}` — sebabnya terukur: **dua proses pytest sesi lain
  hidup bersamaan di kontainer yang sama** (`/proc` menunjukkan `python -m pytest`), dan fixture
  `conftest.py` memakai email TETAP (`pytest-monitor-national@test.local`, dst.) sehingga teardown
  proses lain menghapus baris yang sedang dipakai. Bukan regresi kode.
- `ruff check` pada berkas yang diubah → **All checks passed**.
- Frontend: `vitest run` **1130 passed / 93 berkas**, `tsc --noEmit` **0 error**, `next lint` **0 warning**.

**Pelajaran untuk gerbang berikutnya:** tes yang membuat akun sendiri sebaiknya memakai domain unik
per-run (contoh di `test_peran_final_head_only.py`: `@uji-peran.local`, bukan `@test.local`) supaya
aman dijalankan berdampingan dengan sesi lain. Suite penuh tetap tidak bisa dijadikan verdikt selama
ada proses pytest lain di kontainer yang sama.

## Konsekuensi yang perlu diketahui

1. **Alur demo**: satu approval tidak lagi cukup untuk transfer. Demo/juri harus menekan Setuju
   sebagai Head **dan** sebagai Nutritionist sebelum menekan Eksekusi. Layar approval kini
   menampilkan requirement dua role.
2. **Keputusan administrasi** (`supplier_exclusion`, `supplier_exclusion_restoration`) tetap
   mengikuti verdict verifier (1 approval bila `consistent`) — sesuai PLAN.md §13.3 yang meminta
   workflow administrasi tidak ikut diperketat.
3. **Approval lintas SPPG** tetap tidak dihitung: approver harus se-lokasi dengan lokasi target
   (`actions.py`, ruling 2026-10-14 §3).

## Lanjutan 17 Okt: usul, pemicu event, dan pemulihan (tiga butir terbuka DITUTUP)

Keputusan owner: "kerjakan saja". Yang berlaku sekarang:

| Endpoint / aksi | Sebelum | Sesudah |
|---|---|---|
| `POST /decisions` (draf keputusan operasional) | Head + Nutritionist | **Head saja** (`DECISION_MUTATING_ROLES`) |
| `POST /events/safety-disruption`, `POST /events/price-anomaly` | kedua role SPPG | **Head saja** |
| `POST /demo/event1` (Event 1 penuh) | kedua role SPPG | **Head saja** |
| `POST /supplier-exclusions/{id}/restore` | kedua role SPPG | **Head saja** |
| `POST /demo/seed`, `/demo/timeseries`, `/demo/timeseries/purge`, `/demo/refresh` | kedua role SPPG | **tetap dua role** — penyiapan data demo, bukan usul keputusan |

Alasan pemisahan: yang ditutup adalah aksi yang **melahirkan keputusan operasional** (usul); alat
data demo hanya menyiapkan bahan. `bgn_monitor` tetap 403 di semua endpoint di atas.

Sisi UI ikut diselaraskan supaya tombol tidak menawarkan hal yang akan ditolak 403:
`OpsConsole` (usul rekomendasi + "Jalankan Event 1 penuh"), `ChaosPanel` (Event 3),
`Event2Panel` (Event 2), dan tombol "Ajukan keputusan" di `FoodSafetyBoard` (prop baru
`canPropose`, terpisah dari `canMutate` supaya "Uji ulang" dan catat terima tetap untuk kedua role).
Ahli gizi melihat catatan "Mode baca — pengajuan & Event 1 hanya untuk Kepala SPPG" dan tetap
bisa memberi approval di feed.

Bukti: `backend/tests/test_peran_lanjutan_head_only.py` — 11 tes. Nutritionist 403 di
`/decisions`, `/events/*`, `/demo/event1`, `restore`; Head lolos gerbang (422 dari validasi body,
201 untuk `/decisions`); `/demo/seed` tetap lolos untuk nutritionist. Gerbang mutasi memakai trik
body-salah-tipe (403 = diblokir, 422 = lolos), sehingga tidak ada data demo yang berubah.

---

## Diagnosis 17 Okt: "approve di role SPPG dan Nutrisi tidak bisa"

Gejala yang dilaporkan owner: menekan **Setuju** sebagai Kepala SPPG maupun Ahli Gizi tidak
menghasilkan apa-apa. Yang diukur saat itu (DB + probe API, bukan dugaan):

1. `decisions`: 32 keputusan berstatus `pending_approval`/`verifier_flagged`, **29 di antaranya
   sudah lewat tenggat** (`expires_at <= now()`). Approve pada keputusan biasa yang lewat tenggat
   memang masih diterima backend (Keputusan owner 1b), tetapi **eksekusinya** selalu `409
   "decision expired"` — jadi alurnya tetap terasa "tidak bisa".
2. **Approval kepala sudah tercatat sejak seed.** Contoh terukur: keputusan `1aee6446` dibuat
   07 Okt 16:47:15 dan baris `approvals` untuk `sppg.head@demo.local` masuk 16:47:16 (data seed,
   bukan klik owner). Saat kepala menekan "Setuju" lagi, endpoint menjawab `409 "approval sudah
   tercatat"` — benar secara aturan, tetapi **UI tetap menawarkan tombol "Setuju"** karena read
   model tidak memberi tahu bahwa *user ini* sudah menyetujui. Itulah yang terbaca sebagai
   "tombol rusak".
3. Kasus demo yang memang masih berlaku hanya 3 (`rejection-loop-kuota`, `gangguan-logistik`,
   `supplier-janggal`), semuanya **belum punya approval** sehingga butuh dua peran berurutan.

### Perbaikan di kode

- `backend/app/services/approval_summary.py` — `build_approval_summary(..., viewer_id=None)`
  kini mengirim `approved_by_me` (dihitung dari baris `approvals` milik user yang MEMBACA, bukan
  dari role). Kontrak lama tidak berubah: `can_approve` tetap `true` untuk kedua role, penjaga
  409 tetap di endpoint.
- `backend/app/api/decisions.py` — endpoint summary meneruskan `viewer_id=user.id`.
- `frontend/components/ApprovalModal.tsx` — bila `approved_by_me`, tombol menjadi **"Sudah Anda
  setujui"** (nonaktif) + catatan "Approval Anda sudah tercatat. Keputusan ini menunggu role lain
  (`sppg_nutritionist`) — bukan tombol yang rusak."
- Tes: `backend/tests/test_approval_summary.py::test_summary_approved_by_me_hanya_untuk_user_yang_sudah_menyetujui`,
  `frontend/tests/approval-summary.test.tsx` (kasus `approved_by_me`).

### Bukti hidup (dua peran, urutan terbalik, lalu eksekusi)

Probe di dalam kontainer pada `rejection-loop-kuota` (`f8cd1043`, valid + `verified_by`):

| Langkah | Hasil |
|---|---|
| summary sebagai Kepala | `approved_by_me=false`, `can_approve=true`, `satisfied=false`, `missing=[head, nutritionist]` |
| **approve Nutritionist lebih dulu** | **200** — `missing` jadi `[head]` |
| **approve Kepala** | **200** — `satisfied=true`, `can_execute=true`, `blocking=[]` |
| approve Kepala kedua kali | **409 "approval sudah tercatat"** |
| **execute oleh Kepala** | **200** — `po_number=MC-F8CD1043434C`, status `executed` |

Lewat UI (browser, akun demo asli), pada `gangguan-logistik` (`44a99f93`, valid 4 jam):

1. Nutrisi: "Setuju" aktif → klik → pesan **"Approval tercatat"**, langkah "Persetujuan 1 dari 2 ·
   berikutnya: Kepala SPPG".
2. Kepala: tombol berubah **"Sudah Anda setujui"** setelah approval-nya masuk; "Eksekusi" aktif →
   klik → **"PO MC-44A99F93125E dibuat (mock)"**, langkah "Persetujuan 2 dari 2" + "Eksekusi ✓".

### Yang perlu dilakukan sebelum demo (data, bukan kode)

Data demo berumur pendek: keputusan lama tetap ada dan lewat tenggat. Sebelum presentasi, klik
**"Segarkan ke hari ini"** (`POST /demo/refresh`, Head) atau **"Jalankan Event 1 penuh"** supaya
keputusan baru lahir dengan TTL panjang (480/300 menit) dan `verified_by` terisi. Tanpa itu,
approve tetap tercatat tetapi eksekusi ditolak `decision expired` — dan itu bukan bug.

## Cara memverifikasi ulang

```bash
docker compose exec -T backend python -m pytest tests/test_peran_final_head_only.py -q
docker compose exec -T backend python -m pytest tests/test_actions.py tests/test_action_boundary_e2e.py \
  tests/test_approval_matrix.py tests/test_approval_summary.py tests/test_supplier_exclusion_api.py -q
docker compose exec -T backend ruff check .
docker compose exec -T frontend npx vitest run tests/decision-loop.test.tsx
# probe RBAC hidup:
python <scratch>/rbac_mutasi.py   # 403 = diblokir, 422 = lolos gerbang
```
