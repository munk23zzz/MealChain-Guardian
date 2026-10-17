# Peran final: Head-only propose/execute + dua approval + pagar tata kelola

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

## Yang masih terbuka (perlu keputusan owner)

1. `POST /decisions` (membuat draf keputusan) masih terbuka untuk kedua role SPPG. Bila "mengusulkan"
   dimaknai sampai pembuatan draf, endpoint ini juga perlu Head-only.
2. Kebijakan mutasi demo (`/demo/*`, `/events/*`) belum dibedakan Head vs Nutritionist; sekarang
   keduanya boleh, monitor 403.
3. `restore` supplier exclusion masih untuk kedua role SPPG (dianggap tindakan administratif).

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
