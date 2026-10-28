#!/usr/bin/env bash
# Fase 4 — baseline targeted suite pada klon DB sekali pakai.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DB=mealchain_f4base
sandi="$(grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"
OUT="_qa/f4/baseline-targeted.txt"
mkdir -p _qa/f4

echo "== siapkan klon $DB dari mealchain_fase4 =="
docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1
docker exec mealchain-postgres sh -lc "pg_dump -U mealchain -d mealchain_fase4 | psql -q -U mealchain -d ${DB}" >/dev/null 2>&1 || exit 1
echo "klon terbentuk: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from batches') batch"

echo "== migrasi ke head =="
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head 2>&1 | tail -3
echo "alembic: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"

echo "== pytest targeted =="
docker compose exec -T -e DATABASE_URL="$DSN" -e DEMO_SESSION_ENFORCE=false backend \
  python -m pytest -q -p no:cacheprovider \
  tests/test_batch_eligibility.py tests/test_receipt_quarantine.py \
  tests/test_actions.py tests/test_receipts_api.py tests/test_receipts_approval.py \
  tests/test_receipts_quarantine_gate.py tests/test_receipts_safety_gate.py \
  tests/test_quarantine_api.py tests/test_can_execute_parity.py \
  tests/test_execute_safety_wiring.py tests/test_approval_summary.py \
  > "$OUT" 2>&1
KODE=$?
echo "EXIT=$KODE"
grep -E "^(FAILED|ERROR)" "$OUT" | head -40
tail -3 "$OUT"
echo "log: $OUT"
