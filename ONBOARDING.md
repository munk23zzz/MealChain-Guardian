# ONBOARDING — Dev 2 (Nabil)

> Baca ini SEBELUM mulai ngoding. Urutan: clone → restore data → jalan → baca aturan →
> pick task. Kalau ada langkah gagal, jangan di-retake asal-asalan — tanya Roy.

## 1. Clone & jalan

```bash
git clone https://github.com/RGjordien/mealchain-guardian.git
cd mealchain-guardian

# pastikan di branch kerja aktif
git checkout feature/sprint2-decision-intelligence

# hidupkan environment
docker compose up -d
docker compose ps          # backend, frontend, postgres, mock-sap harus Up (postgres healthy)
```

## 2. Restore data container (dump lokal dari mesin Roy)

Dump `data/export/mealchain_full_dump.sql` berisi SEMUA data lokal: seed, decisions,
agent_traces, ledger blocks, KPI facts, akun demo.

```bash
# volume postgres harus kosong/baru — kalau compose baru pertama kali up, aman.
docker compose exec -T postgres psql -U mealchain -d mealchain < data/export/mealchain_full_dump.sql

# cek masuk
docker compose exec postgres psql -U mealchain -d mealchain -c "SELECT count(*) FROM decisions;"
# angka > 0 = restore sukses

# (opsional) samakan schema migration state
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current   # harus = heads (012_supplier_profile)
```

Kalau TIDAK memakai dump (schema dari nol), jalankan seed kanonik + data demo:

```bash
docker compose exec -T backend python -m app.seed.seed_data \
  --reference-time 2026-10-08T12:00:00+00:00 --with-demo-users --with-demo-suppliers
# --with-demo-suppliers = 30 pemasok demo (data/seed/suppliers_demo.json) supaya
# pemasok bisa ditampilkan di peta; tanpa flag ini hanya 14 pemasok kanonik ada.
docker compose exec -T backend python -m app.seed.suppliers_demo   # bisa diulang, idempoten
```

Kalau dump gagal karena schema bentrok (volume sudah terisi migration awal), reset dulu:

```bash
docker compose down -v        # HAPUS volume — hanya kalau memang mau reset
docker compose up -d postgres
sleep 5
docker compose exec -T postgres psql -U mealchain -d mealchain < data/export/mealchain_full_dump.sql
docker compose up -d
```

## 3. Verifikasi jalan

```bash
curl http://localhost:8000/health        # 200
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:3010   # 200 (FRONTEND_PORT di .env)

# test backend + frontend
docker compose exec backend pytest
docker compose exec frontend npm run test
```

Angka yang diharapkan (per 2026-10-14, sesudah Fase 2 pemasok): backend 720 passed (3 skip),
frontend 53 berkas / 449 passed. Kalau beda tipis karena commit baru, wajar — yang penting exit 0.

## 4. Akun demo (login UI di localhost:3010)

> Konsol aktif ada di **`http://localhost:3010`** (nilai `FRONTEND_PORT` di `.env`).
> Di mesin demo port 3000 dipakai aplikasi acuan (`HackathonBil\MealchainGuardian`)
> yang dibiarkan berjalan untuk pembanding, jadi jangan kembalikan ke 3000 tanpa
> mematikan proses itu dulu.


| Role | Kegunaan |
|---|---|
| sppg_head | approver utama (ajukan, approve, execute) |
| sppg_nutritionist | verifier + approver kedua (4-eyes) |
| bgn_monitor | read-only (403 di semua mutasi) |

Password lihat `backend/.../seed_data.py` (search `password`). JANGAN menulis password
ke file apapun yang ter-commit.

## 5. Aturan yang TIDAK BOLEH dilanggar (Rules.md — berlaku untuk semua dev)

1. **LLM tidak pernah menghitung angka safety-critical** — semua angka lewat tool
   deterministik di `app/core/`.
2. **Tidak ada auto-execute** aksi berisiko tinggi tanpa human approval (4-eyes).
3. **Safety status (PASS/FAIL/NEEDS_VERIFICATION) tidak pernah di-override.**
4. **Anti-fabricate:** label `SAP-RPT-1.6` / `MOCK` hanya untuk response asli.
5. **Secrets hanya di `.env`** — jangan buat `.env.example`, jangan commit kredensial baru.
   ⚠️ Saat ini `.env` SENGAJA ter-commit oleh Roy untuk onboarding — setelah semua dev
   beres clone, `.env` akan dikeluarkan lagi + keys di-rotate. Jangan tambah secret baru
   ke file apapun yang ter-commit. **Status 2026-10-11: `.env` MASIH ter-track**
   (`.gitignore` tidak berpengaruh pada berkas yang sudah dilacak — untuk melepas:
   `git rm --cached .env`). Karena berkas ini ter-track, riwayatnya memuat rahasia NYATA
   yang harus di-rotate SEBELUM repo dipublikasikan: `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, `AWS_BEARER_TOKEN_BEDROCK`, `SAP_AI_CORE_CLIENT_SECRET`,
   `SIGNING_KEY_HEX`, `POSTGRES_PASSWORD`. Rotate dulu, baru purge riwayat.
   ⚠️ **Escape `$` wajib**: nilai `.env` yang memuat `$` harus ditulis `$$`, karena
   interpolasi docker compose memotong nilai setelah `$` (terbukti: `SAP_AI_CORE_CLIENT_SECRET`
   81 char → 37 char di kontainer, sehingga OAuth SAP AI Core gagal). Pembaca `.env` di host
   (bukan docker) harus mengembalikan `$$` menjadi `$` lebih dulu.
6. **Update `TODO.md`** setiap status task berubah — bukan opsional.
7. Keputusan arsitektur/arah baru → append `memory/global/decisions.md`.
8. Komentar kode & dokumen berbahasa Indonesia.

## 6. Urutan baca dokumen (WAJIB, sebelum ngoding)

1. `IDEA.md` — kenapa proyek ini ada
2. `memory/global/active_context.md` — kondisi kerja saat ini + next step
3. `memory/global/project_memory.md` → `architecture.md` → `decisions.md` — memory build
4. `TODO.md` — status task (sumber kebenaran)
5. `Rules.md`, `workflows.md`, `Roadmap.md`
6. `docs/PRD.md`, `docs/Architecture.md`, `docs/Schema.md`, `docs/Skill.md` — sesuai task

## 7. Task untuk dev 2 (cek TODO.md untuk status terbaru)

- **S4-10** — Hidupkan SAP AI Core: RPT-1.6 + Verifier primary (detail langkah di
  `memory/global/active_context.md` §Next step)
- **S4-11** — Settings/Admin screen (eks BL-01; desain bisa dari mockup Stitch)

Koordinasi: jangan kerjakan task yang sama dengan Roy tanpa kompak di TODO.md (kolom Assignee).

## 8. Alur kerja git

- Branch kerja aktif: `feature/sprint2-decision-intelligence`.
- Sebelum push: `docker compose exec backend pytest` + `ruff check .` harus hijau;
  frontend `npm run test` + `npm run lint` + `npm run build` harus hijau.
- Commit message: bahasa Indonesia, pola `feat:/fix:/docs:/chore: <ringkas>`.
- Jangan commit di `master` langsung; jangan force-push.
