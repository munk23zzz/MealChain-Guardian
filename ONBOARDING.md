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

# SATU perintah untuk seluruh rantai: backend, 3 akun demo, RBAC, trace 7 agen,
# runtime AgentCore READY + invoke review_decision (7 finding).
uv run --no-project --with boto3 python scripts/smoke_e2e.py
# tanpa kredensial AWS:
python scripts/smoke_e2e.py --skip-aws

# tes satuan
docker compose exec backend pytest
docker compose exec frontend npm run test
```

Angka yang diharapkan (per 2026-10-18): backend **1013 passed** (3 skip), frontend
**102 berkas / 1209 tes**, smoke **13 lulus · 0 gagal · 0 skip**. Kalau beda tipis karena
commit baru, wajar — yang penting exit 0.

## 3b. Frontend di Windows/exFAT (drive E:)

```bash
cd frontend
npm ci            # WAJIB; lockfile sudah disinkronkan (npm 11)
npm run test      # vitest (jsdom sudah ada di devDependencies)
npm run typecheck # tsc --noEmit
npm run lint
npm run build     # sudah memuat scripts/exfat-readlink-patch.cjs
```

Kenapa ada patch: di exFAT, `fs.readlink()` pada berkas biasa melempar `EISDIR`, sedangkan
webpack hanya memahami `EINVAL` sebagai "bukan symlink" — tanpa patch, `next build` gagal
`EISDIR ... readlink '...next/dist/pages/_app.js'`. Script `build` sudah memuatnya otomatis
(`node -r ./scripts/exfat-readlink-patch.cjs`), jadi tidak perlu `NODE_OPTIONS` manual; di
NTFS/Linux patch ini tidak berpengaruh.

Catatan operasional: `npm ci` menghapus `node_modules` — matikan dulu yang memegang folder itu
(container frontend sudah memakai volume sendiri, tapi LSP/tsserver Hermes bisa mengunci).

## 3c. Agen di AgentCore Runtime (agar review 7 agen hidup)

1. `.env` (root): `MULTI_AGENT_REVIEW=true`, `AGENTCORE_RUNTIME_ARN=<arn runtime>`.
2. Kredensial AWS di `secrets/aws-app.env` (jangan di `.env` yang ter-commit).
3. Token baca untuk worker (30 hari, role `bgn_monitor`):

   ```bash
   uv run --no-project --with boto3 --with "psycopg[binary]" --with pyjwt \
     python backend/scripts/buat_token_agen.py --email bgn.monitor@demo.local \
     --hari 30 --tulis-env \
     --database-url "postgresql://mealchain:<password-di-.env>@localhost:15432/mealchain"
   ```

4. URL backend yang bisa dijangkau DARI AWS (runtime tidak bisa memakai `localhost`).
   Untuk demo lokal pakai tunnel tetap (cloudflared/ngrok); untuk produksi pakai VPS/domain.
   Setelah URL berubah, **satu perintah** memindahkan env runtime:

   ```bash
   python agent/set_runtime_env.py --api-url https://<url-publik-backend>
   python agent/set_runtime_env.py --tampilkan     # cek env runtime sekarang
   ```

5. Ulangi `scripts/smoke_e2e.py` — `invoke review_decision` harus `7 finding · 8 trace row`.

Kalau URL backend mati (tunnel berhenti), invoke runtime akan gagal/menggantung walau runtime
`READY`; itu gejala URL, bukan kerusakan agent — perbaiki dengan langkah 4.

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

## 9. Mode demo — apa yang nyata dan apa yang belum (17 Okt 2026)

Bagian ini supaya tidak ada yang salah klaim saat presentasi. Sumbernya pengukuran langsung
di stack lokal, bukan proposal.

- **Data**: sintetis terkalibrasi (10 lokasi × 3 komoditas). Bukan transaksi SPPG nyata.
- **SAP**: masih **mock** (`mock-sap` di :8001). PO yang "dibuat" tersimpan di tabel
  `sap_mock_purchase_orders`; belum ada koneksi SAP asli maupun AWS for SAP MCP
  (`AwsMcpSapProvider` masih stub).
- **AgentCore**: runtime **belum dibuat** (0 runtime, `AGENTCORE_RUNTIME_ARN` kosong).
  Artefak (Dockerfile, runtime server, deploy script, role IAM) sudah siap.
- **Supervisor**: Strands Agent memegang **4 tool baca** (`get_supply_demand`,
  `get_safety_freshness`, `get_cost_eligibility`, `get_evidence_digest`) yang memanggil
  API backend. Ini bukan 7 agen otonom; angka keputusan tetap dihitung pipeline
  deterministik di `backend/app/core/`.
- **Bukti**: ledger hash chain PostgreSQL (Merkle + tanda tangan ECDSA), bisa diverifikasi
  di tab Decision & Evidence → Integritas Bukti.
- **KPI**: 7 indikator; yang belum bisa dihitung menulis alasan "belum ada data",
  bukan diisi nol.
- **Status integrasi terlihat di aplikasi**: tab **Agent Log → Bukti integrasi per komponen**
  (SAP AI Core, Mock SAP, AgentCore Runtime/Gateway/Memory, Observability, AWS for SAP MCP).

Saat demo, hindari tombol **Bersihkan data demo** dan **Bangun ulang dari nol** kecuali
memang ingin membangun ulang dataset. Tombol **Muat kasus demo** idempotent dan aman diulang.

Jangan mengubah label `mock` / `belum` / `tidak tersedia` menjadi klaim sukses tanpa artefak
yang bisa ditunjuk.
