# AGENTS.md

## Apa proyek ini
MealChain Guardian — agentic AI untuk cross-regional food supply balancing, dibangun untuk
kompetisi Sokrates x SAP x AWS. Baca `IDEA.md` untuk konteks lengkap sebelum melakukan apapun.

## Urutan baca dokumen (wajib, di awal sesi)
1. `IDEA.md` — kenapa proyek ini ada
2. `TODO.md` — status kerja saat ini (sumber kebenaran, jangan asumsi dari memori sesi lalu)
3. `Rules.md` — batasan yang tidak boleh dilanggar
4. `workflows.md` — cara kerja step-by-step, termasuk skill mana dipakai kapan
5. `Roadmap.md` — sprint aktif saat ini
6. `docs/PRD.md`, `docs/Architecture.md`, `docs/design.md`, `docs/Schema.md`, `docs/Skill.md` —
   sesuai kebutuhan task

## Perintah penting

```bash
# Jalankan seluruh environment lokal
docker compose up -d

# Migration database
docker compose exec backend alembic upgrade head

# Test backend
docker compose exec backend pytest

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
