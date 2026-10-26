# AGENTS.md

## Apa proyek ini
MealChain Guardian — agentic AI untuk cross-regional food supply balancing, dibangun untuk
kompetisi Sokrates x SAP x AWS. Baca `IDEA.md` untuk konteks lengkap sebelum melakukan apapun.

## Urutan baca dokumen (wajib, di awal sesi)
1. `IDEA.md` — kenapa proyek ini ada
2. `TODO.md` — status kerja saat ini (sumber kebenaran, jangan asumsi dari memori sesi lalu)
3. `docs/state-snapshot.md` — angka keadaan terbaru (diukur mesin; kalau dokumen lain berbeda,
   snapshot yang berlaku). Regenerasi: `python scripts/snapshot_state.py` (baca-saja)
4. `Rules.md` — batasan yang tidak boleh dilanggar
5. `workflows.md` — cara kerja step-by-step, termasuk skill mana dipakai kapan
6. `Roadmap.md` — sprint aktif saat ini
7. `docs/PRD.md`, `docs/Architecture.md`, `docs/design.md`, `docs/Schema.md`, `docs/Skill.md` —
   sesuai kebutuhan task
8. `docs/MEALCHAIN_GUARDIAN_LENGKAP.md` — **gambaran menyeluruh satu berkas** (runtime, model data,
   peran, state machine, API, KPI, arsitektur demo, keamanan, pengujian, batasan). Mulai dari sini
   kalau butuh konteks penuh dengan cepat; angka operasional tetap dari `docs/state-snapshot.md`.

## Memory vault Obsidian (wajib dibaca)
`memory/` adalah vault Obsidian project ini (memory build lintas sesi). Mulai dari
`memory/global/MOC.md` → `active_context.md` → `project_memory.md` → `architecture.md` →
`decisions.md`. Keputusan baru WAJIB di-append ke `memory/global/decisions.md`;
kondisi kerja diperbarui di `memory/global/active_context.md`. `TODO.md` tetap
sumber kebenaran status task.

## Perintah penting

```bash
# Jalankan seluruh environment lokal
docker compose up -d

# Migration database
docker compose exec backend alembic upgrade head

# Test backend — JANGAN lewat `docker compose exec` pada database kerja:
# perintah itu mem-purge baris demo (keputusan 36 → 9, pasokan 5.240 → 40).
# Jalankan pada DB klon + mount read-only:
#   docker run --rm --network mealchain-guardian_mealchain-network \
#     --env-file .env -e DATABASE_URL=postgresql+asyncpg://.../mealchain_sesiuji \
#     -v "$PWD/backend:/app" -w /app mealchain-guardian-backend pytest

# Test frontend
docker compose exec frontend npm run test

# Lint
docker compose exec backend ruff check .
docker compose exec frontend npm run lint
```

## Batasan kritis (ringkasan — detail di `Rules.md`)

- LLM tidak pernah menghitung angka safety-critical — selalu lewat tool deterministik
- Tidak ada auto-execute aksi berisiko tinggi tanpa human approval
- Safety status (PASS/FAIL/NEEDS_VERIFICATION) tidak pernah di-override
- Update `TODO.md` setiap kali status task berubah — ini bukan opsional

## Siapa yang mengerjakan apa

Roy (dev utama, pakai Hermes agent) + 1 teman (dev kedua). Rules.md berlaku untuk keduanya,
tool-agnostic.

## Kalau bingung mulai dari mana

Cek `TODO.md` untuk task yang statusnya "Not Started" di sprint aktif (`Roadmap.md`), lalu
ikuti alur di `workflows.md` §1-2.
