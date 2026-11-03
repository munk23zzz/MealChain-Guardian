# AGENTS.md

## Apa proyek ini

MealChain Guardian — agentic AI untuk penyeimbangan pasokan pangan lintas daerah.
Dibangun untuk kompetisi Sokrates x SAP x AWS. Latar lengkap: `IDEA.md`.

## Urutan baca dokumen (awal sesi)

1. `IDEA.md` — kenapa proyek ini ada
2. `TODO.md` — status kerja saat ini; sumber kebenaran, jangan mengandalkan ingatan sesi lalu
3. `docs/state-snapshot.md` — angka keadaan terbaru. Regenerasi (baca-saja):
   `python scripts/snapshot_state.py`. Bila dokumen lain berbeda, snapshot yang berlaku
4. `Rules.md` — batasan yang tidak boleh dilanggar
5. `workflows.md` — cara kerja per langkah, termasuk skill mana dipakai kapan
6. `Roadmap.md` — sprint aktif
7. Sesuai kebutuhan: `docs/PRD.md`, `docs/Architecture.md`, `docs/design.md`,
   `docs/Schema.md`, `docs/Skill.md`, `docs/MEALCHAIN_GUARDIAN_LENGKAP.md` (gambaran
   menyeluruh satu berkas)

Rujukan kerja terbaru:

- `docs/audit/audit-2026-10-29-remediation-report.md` — audit 50 temuan + remediasi
- `docs/plans/sap-rpt-integration-plan.md` — integrasi peramalan SAP-RPT-1.6
- `docs/demo/alur-demo-juri.md` — demo langsung 11–14 menit
- `docs/demo/alur-video-demo-6-menit.md` — runbook rekaman video 6 menit

## Memory vault Obsidian

`memory/` adalah vault Obsidian proyek ini. Mulai dari `memory/global/MOC.md` ->
`active_context.md` -> `project_memory.md` -> `architecture.md` -> `decisions.md`.
Keputusan baru di-append ke `memory/global/decisions.md`; kondisi kerja di
`memory/global/active_context.md`. `TODO.md` tetap sumber kebenaran status task.

## Perintah penting

```bash
# Seluruh environment lokal
docker compose up -d

# Migrasi database
docker compose exec backend alembic upgrade head

# Gerbang backend
docker compose exec backend ruff check .

# Tes backend — HANYA pada DB klon, bukan DB demo.
# pytest menulis dan mem-purge baris demo (terukur: keputusan 36 -> 9, pasokan 5.240 -> 40).
bash scripts/gerbang-db-terpisah.sh                 # DB gate baru + suite penuh
bash scripts/gerbang-db-terpisah.sh --pakai-ulang   # pakai DB gate yang sudah ada
bash scripts/f6-gate.sh backend/tests/test_x.py     # klon sekali pakai, berkas tertentu
# hasil gerbang tertulis di _qa/gerbang-db-terpisah-<tanggal>.txt

# Mode database (satu pintu)
bash scripts/db-mode.sh status
bash scripts/db-mode.sh init-demo --refresh

# Gerbang frontend
docker compose exec frontend npm run test        # vitest run
docker compose exec frontend npm run typecheck   # tsc --noEmit
docker compose exec frontend npm run lint        # next lint
```

Suite penuh butuh ~17 menit dan memakai CPU + DB yang sama: hentikan sebelum
demo atau rekaman.

## Saklar environment yang mengubah perilaku

| Variabel | Arti |
|---|---|
| `MULTI_AGENT_REVIEW` | `true` = setiap keputusan dari `POST /decisions` dan `POST /demo/event1` dijadwalkan review 9 baris |
| `AGENT_REVIEW_MODE` | `local` = review berjalan in-process (tidak butuh tunnel); `advisory` = lewat runtime AgentCore yang memanggil balik API publik — gagal bila URL publik mati |
| `FORECAST_PROVIDER` | rem darurat biaya: `statistical` mematikan panggilan model peramalan |
| `STATIC_EXPORT` | `true` = ekspor statis untuk GitHub Pages |

Nilai rahasia tidak pernah dicetak atau disalin; cukup nama kunci + status terisi.

## Batasan kritis (ringkasan — detail di `Rules.md`)

- LLM tidak pernah menghitung angka safety-critical — selalu lewat tool deterministik
- Tidak ada auto-execute aksi berisiko tinggi tanpa persetujuan manusia
- Safety status (PASS / FAIL / NEEDS_VERIFICATION) tidak pernah di-override
- Review agent bersifat advisory: verdict-nya tidak boleh mengubah status keputusan
- Operasi tulis pada DB demo dilarang saat audit atau pengujian
- `TODO.md` diperbarui setiap status task berubah

## Siapa mengerjakan apa

Roy (dev utama, memakai Hermes agent) + satu rekan (dev kedua). `Rules.md`
berlaku untuk keduanya dan tidak bergantung pada tool.

## Kalau bingung mulai dari mana

Cek `TODO.md` untuk task "Not Started" di sprint aktif (`Roadmap.md`), lalu ikuti
alur di `workflows.md` §1–2.
