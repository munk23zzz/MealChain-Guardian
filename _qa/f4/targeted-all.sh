#!/usr/bin/env bash
# Fase 4 (verifikasi 100% checkbox) — seluruh berkas uji backend yang
# membuktikan butir 1..8, dijalankan pada klon DB sekali pakai.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

DB=mealchain_f4v
sandi="$(grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"
OUT="_qa/f4/verify-$(date +%H%M).txt"

# CATATAN PENTING (27 Okt 2026): kontainer `mealchain-backend` yang sedang
# berjalan TIDAK me-mount repo ini (mount /app-nya diarahkan sesi lain ke
# salinan scratch), sehingga `docker compose exec backend pytest` menjalankan
# kode yang bukan kode repo. Skrip ini memakai kontainer sekali pakai dengan
# `-v "$PWD/backend:/app"` — pola yang juga ditulis AGENTS.md.
JARINGAN=mealchain-guardian_mealchain-network
jalankan() {
  docker run --rm --network "$JARINGAN" --env-file .env \
    -e DATABASE_URL="$DSN" -e DEMO_SESSION_ENFORCE=false \
    -v "$PWD/backend:/app" -w /app mealchain-guardian-backend:latest "$@"
}

echo "== siapkan klon $DB dari DB demo (head $(docker exec mealchain-postgres psql -U mealchain -d mealchain -tAc 'select version_num from alembic_version')) =="
docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1
docker exec mealchain-postgres sh -lc "pg_dump -U mealchain -d mealchain | psql -q -U mealchain -d ${DB}" >/dev/null 2>&1 || exit 1
echo "klon: batch=$(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from batches') keputusan=$(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from decisions')"
jalankan alembic upgrade head 2>&1 | tail -1
echo "head klon: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"

jalankan python -m pytest -q -p no:cacheprovider -rs \
  tests/test_batch_eligibility.py \
  tests/test_dispatch_safety_gate.py \
  tests/test_decision_fingerprint.py \
  tests/test_decision_fingerprint_wiring.py \
  tests/test_delivery_policy.py \
  tests/test_delivery_window_wiring.py \
  tests/test_execute_safety_wiring.py \
  tests/test_can_execute_parity.py \
  tests/test_approval_summary.py \
  tests/test_receipt_quarantine.py \
  tests/test_receipts_api.py \
  tests/test_receipts_approval.py \
  tests/test_receipts_quarantine_gate.py \
  tests/test_receipts_safety_gate.py \
  tests/test_quarantine_api.py \
  tests/test_actions.py \
  tests/test_procurement_execute_guard.py \
  > "$OUT" 2>&1
KODE=$?
echo "EXIT=$KODE"
grep -E "^(FAILED|ERROR)" "$OUT" | head -40
tail -3 "$OUT"
echo "log: $OUT"
