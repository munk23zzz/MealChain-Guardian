# Ceklis fitur per role vs PLAN.md

**Tanggal pengukuran:** 2026-10-17 (pagi WIB) · **Repo:** `E:\hackathon\HackathonAWS\mealchain-guardian`
**Acuan:** `PLAN.md` §13 (kebijakan final owner) + §7A (modul & prioritas) + §13.2 (scope).
§5 PLAN.md adalah **arsip** perilaku lama, bukan target.

## Metode & bukti

- Probe RBAC hidup dengan tiga akun demo (`sppg.head@`, `sppg.nutritionist@`, `bgn.monitor@`), token dari `POST /auth/login`, 54 path dari `GET /openapi.json`.
- Baca: setiap GET ditembak ketiga peran (parameter diisi otomatis dari skema).
- Mutasi: **tanpa efek samping** — satu field dikirim dengan tipe salah. Urutan FastAPI membuat dependency `require_roles` dinilai lebih dulu daripada validasi body, sehingga **403 = diblokir di gerbang rute**, **422 = lolos gerbang** (handler tidak pernah jalan).
- Cakupan: `/balance/map` dan `/balance/{lokasi}/{komoditas}` diukur jumlah lokasi + statusnya.
- Statis: pembacaan `require_roles(...)` per endpoint dan aturan di `backend/app/api/actions.py`, `core/approval_matrix.py`, `admin_rules.py`.

## Ringkasan verdict

| Sumbu | Verdict |
|---|---|
| Tiga role resmi | **SAMA** (tidak ada role keempat di kode) |
| `bgn_monitor` diblokir di semua mutasi operasional | **SAMA** (403 di 22 endpoint mutasi yang diuji) |
| Scope satu SPPG (baca balance lintas SPPG ditolak) | **SAMA** (Head/Nutritionist 403 di Bogor & Cianjur; monitor 200) |
| Head-only propose / purpose / execute | **SAMA** (ditegakkan 17 Okt; `peran-final-head-only-2026-10-17.md`) |
| Approval kedua Nutritionist sebagai syarat khusus transfer | **SAMA** (dua role wajib untuk tipe operasional, apa pun verdict) |
| Nutritionist hanya approval kedua | **SAMA** (propose/repropose/execute → 403) |
| `bgn_monitor` read-only murni | **LEBIH** (jalur admin user & lokasi) + pagar larangan ubah peran sendiri |
| Modul & prioritas per role | **SAMA** (8 modul; demo-control approver-only; agent-log semua role) |

## 1. Yang SAMA dengan PLAN.md

| Capability | Bukti |
|---|---|
| Tepat tiga role (`sppg_head`, `sppg_nutritionist`, `bgn_monitor`) | `backend/app/core/admin_rules.py:21`; `/auth/me` ketiga akun sesuai |
| Monitor tidak bisa propose/verify/approve/execute/repropose | probe: `bgn_monitor=403` di kelima endpoint `/actions/*` |
| Monitor tidak bisa mutasi demo, event, supplier exclusion, safety/freshness, receipt, logistik, harga | probe: 403 di `/demo/seed`, `/demo/timeseries`, `/demo/event1`, `/events/*`, `/supplier-exclusions/*`, `/evidence/fuse` (guard dependency), `/safety/evaluate`, `/freshness/evaluate`, `/receipts`, `/logistics/estimate`, `/price/deviation`, `/cost/safe-delivered` |
| Monitor membaca lintas lokasi; role SPPG hanya lokasinya | `/balance/map?commodity=telur`: Head **1**, Nutritionist **1**, Monitor **10** lokasi. `/balance/Bogor/telur` & `/balance/Cianjur/telur` → **403** untuk Head/Nutritionist, **200** untuk Monitor |
| Monitor tidak melihat tab Demo Control | `frontend/app/page.tsx:1236` (`tab === "demo-control" && isApprover`); `APPROVER_ROLES` = head+nutritionist (`lib/evidence.ts:165`) |
| Monitor melihat Agent Log, dan aksi keputusan read-only | `page.tsx:696,1337`; `DecisionActions.tsx:72-73` menampilkan "Peran … bersifat read-only" |
| Assignment dari data persisten, bukan parameter klien | `users.location_id` (Head & Nutritionist punya, monitor null); `decisions.py:43-46`; `actions.py:65` `_require_decision_scope` |
| Satu user tidak boleh approve dua kali | `actions.py:316` → 409 "approval sudah tercatat" |
| Approval hanya dihitung dari approver berlokasi sama dengan lokasi target | `actions.py:429-441` (ruling 2026-10-14 §3) |
| Freshness satu kontrak 0.85 / 0.60 | `backend/app/core/freshness.py:7-8` |
| Safety `FAIL` memblokir (bukan bisa di-override UI) | `core/constraints.py` + endpoint safety/freshness |

## 2. Yang LEBIH dari PLAN.md (aplikasi memberi lebih banyak)

1. ~~**Nutritionist bisa propose, verify, approve, execute, repropose.**~~ **SELESAI 2026-10-17.**
   `actions.py` kini punya `PROPOSER_ROLES = ("sppg_head",)` untuk `propose`/`repropose`/`execute`;
   `verify` dan `approve` tetap dua role. Probe hidup: `sppg_nutritionist=403` di ketiganya,
   `=422` (lolos) di `verify`/`approve`. Tes: `tests/test_peran_final_head_only.py`.
   PLAN.md §13.1: Nutritionist "no transfer/supplier proposal, no operational purpose, no execute".

2. ~~**Matriks approval tidak membedakan transfer.**~~ **SELESAI 2026-10-17.**
   `approval_requirement(..., dua_role_wajib=True)` dipakai untuk semua tipe operasional, sehingga
   transfer selalu butuh **2 approval** dari **Head + Nutritionist** (dua user persisten berbeda),
   terlepas dari verdict verifier. `approval_summary` memakai aturan yang sama (parity).
   Keputusan administrasi (`supplier_exclusion*`) tetap mengikuti verdict sesuai §13.3.

3. **`bgn_monitor` bukan read-only murni: dia pemegang jalur admin user & lokasi.**
   `admin.py:98,143` → `require_roles("bgn_monitor")` untuk `PATCH /admin/users/{user_id}` dan `PATCH /admin/locations/{location_id}`; Head/Nutritionist dapat **403**, Monitor **422** (lolos gerbang). Sisi UI: tab **Pengaturan** hanya untuk monitor (`page.tsx:731` `roles: Array.from(MANAGE_ROLES)`, `lib/settings.ts:7 MANAGE_ROLES = ["bgn_monitor"]`).
   PLAN.md §13.1 menulis monitor "Read-only"; §7A/PLAN-015 menyatakan Settings/Admin **di luar scope** dan tidak ada role admin. Jadi kemampuan ini ada di aplikasi tetapi tidak dideskripsikan di PLAN.md.

4. **Daftar keputusan sudah menyempit per role.** (dikoreksi 17 Okt)
   `/decisions` menyaring per lokasi: Head/Nutritionist hanya melihat keputusan lokasinya, monitor
   melihat semua. Angka "228 identik" yang sempat dilaporkan terjadi karena seluruh keputusan demo
   bertarget Jakarta — bukan bukti daftar tak tersaring.

5. **UI kini membedakan Head vs Nutritionist pada aksi keputusan.** (17 Okt)
   `frontend/components/DecisionActions.tsx` → `execute`/`repropose` hanya `sppg_head`; `approve`
   tetap dua role. Sebelumnya `isApprover` menyamakan keduanya sehingga Nutritionist melihat tombol
   Eksekusi yang kini akan ditolak 403 oleh backend.

## 3. Yang KURANG dari PLAN.md (diminta, belum ada)

| Tuntutan PLAN.md | Keadaan sekarang |
|---|---|
| Head-only propose & purpose (§13.1, PLAN-021) | **SELESAI 17 Okt** — `PROPOSER_ROLES` di `actions.py`; Nutritionist 403 |
| Head-only execute transfer (§13.3) | **SELESAI 17 Okt** — `execute` dijaga `PROPOSER_ROLES` |
| Dua approval user berbeda sebagai syarat transfer (§13.3) | **SELESAI 17 Okt** — `dua_role_wajib=True` untuk tipe operasional |
| Supplier exclusion diusulkan Head saja (§13.2) | **SELESAI 17 Okt** — proposals Head-only; `restore` masih kedua role (administratif) |
| Kebijakan final mutasi demo (mana yang Head saja) (§13.3A) | **Terbuka** — kedua role SPPG masih boleh |
| Modul Settings/Admin resmi (PLAN-015) | Sengaja di luar scope — tetapi kemampuan adminnya sudah hidup di jalur `bgn_monitor` |
| SAP AI Core & AWS for SAP MCP (PLAN-011/013) | Bukan soal role; tetap belum siap (caller unimplemented / provider stub) |

Catatan: tabel §6 PLAN.md menandai `PLAN-021` "Done (policy gate)" dan `PLAN-022` "Done (scope gate)". Bukti hari ini: **PLAN-022 (scope) memang terlihat di kode dan di probe**; **PLAN-021 (Head-only) tidak terlihat** — konsisten dengan pengakuan §13.3 bahwa guard rute masih memakai kedua role.

## 4. Ceklis ringkas per role

### `sppg_head`
| Fitur | PLAN.md | Aplikasi | Verdict |
|---|---|---|---|
| Baca semua modul dalam scope | ya | ya (balance/map 1 lokasi, lintas SPPG 403) | SAMA |
| Proposal transfer + purpose | Head-only | Head boleh (Nutritionist juga) | LEBIH (bagi Nutritionist) |
| Verifikasi | bagian alur | boleh | SAMA |
| Approve / reject | approval Head | boleh; satu user tak bisa approve 2x | SAMA |
| Execute | Head-only, setelah 2 approval | boleh tanpa syarat Head-only | KURANG (gate) / LEBIH (Nutritionist ikut) |
| Supplier exclusion | Head mengusulkan | Head boleh (Nutritionist juga) | LEBIH (bagi Nutritionist) |
| Mutasi demo | Head (kebijakan final belum ditetapkan) | boleh | SAMA/belum diputuskan |
| Admin user & lokasi | tidak disebut | 403 | SAMA |
| Modul utama (Overview → Recommendations → Approvals → Network → Supply → Safety → Performance → Agent) | sesuai §7A | sesuai | SAMA |

### `sppg_nutritionist`
| Fitur | PLAN.md | Aplikasi | Verdict |
|---|---|---|---|
| Baca semua modul dalam scope | ya | ya (1 lokasi; lintas SPPG 403) | SAMA |
| Proposal / purpose / execute | dilarang | dilarang (**403**) | SAMA |
| Verifikasi | bagian alur | boleh | SAMA |
| Approval kedua setelah verifikasi | wajib | wajib (dua role, dua user berbeda) | SAMA |
| Safety/freshness: tidak boleh override | dilarang | tidak ada jalur override | SAMA |
| Mutasi demo | tidak disebut | boleh | LEBIH/belum diputuskan |
| Supplier exclusion | review/approve | usul: Head saja (403 utk Nutritionist); restore: kedua role | SAMA/nuansa |
| Admin user & lokasi | tidak disebut | 403 | SAMA |

### `bgn_monitor`
| Fitur | PLAN.md | Aplikasi | Verdict |
|---|---|---|---|
| Baca lintas lokasi (map, balance, KPI, trace, dossier, ledger) | ya | ya (10 lokasi; 200) | SAMA |
| Propose/verify/approve/execute | dilarang | 403 di semua | SAMA |
| Mutasi demo/event/supplier exclusion/safety/freshness/receipt | dilarang | 403 di semua | SAMA |
| Jalur demo (`/demo/*`) | tidak relevan | 403 | SAMA |
| Baca `/admin/users`, `/admin/locations` | tidak disebut | 200 | LEBIH |
| **Ubah** user (role/penugasan) & lokasi | tidak disebut (read-only menurut §13.1) | **boleh** (`require_roles("bgn_monitor")`) | LEBIH |
| Tab Pengaturan di UI | tidak ada modul | hanya untuk monitor | LEBIH |
| UI demo-control & tombol approve/execute | tidak boleh | tidak tampil (read-only) | SAMA |

## 5. Item yang perlu keputusan owner

1. Nutritionist: ditutup dari `propose`/`execute` (dan `repropose`) di kode, atau kebijakan §13.1 yang direvisi?
2. Transfer: wajib dua approval dua user berbeda untuk semua verdict, atau tetap mengikuti verdict verifier?
3. Jalur admin `bgn_monitor` (`/admin/users`, `/admin/locations`, tab Pengaturan): resmikan sebagai kapabilitas governance, atau pindahkan ke luar scope seperti PLAN-015?
4. Read-context daftar keputusan lintas peran: dipersempit atau dipertahankan (butuh kalimat eksplisit di dokumen)?

Semua angka pada dokumen ini berasal dari eksekusi hari ini kecuali baris yang ditandai "PLAN.md" (kutipan rencana) atau secara eksplisit disebut berasal dari ceklis sesi lain.
