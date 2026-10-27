#!/usr/bin/env bash
# Fase 3 — gerbang pada klon DB sekali pakai (bukan DB demo).
# Pemakaian: bash scripts/f3-gate.sh [berkas-tes ...]
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DB="${F3_DB:-mealchain_f3}"
SUMBER="${F3_SUMBER:-mealchain}"
sandi="$(grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"
mkdir -p _qa/f3

echo "== siapkan klon ${DB} dari ${SUMBER}"
docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1
docker exec mealchain-postgres sh -lc "pg_dump -U mealchain -d ${SUMBER} | psql -q -U mealchain -d ${DB}" >/dev/null 2>&1 || exit 1
echo "klon terbentuk: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from batches') batch, alembic $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"

echo "== migrate ke head"
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head > _qa/f3/alembic.txt 2>&1
echo "ALEMBIC_EXIT=$?"
tail -3 _qa/f3/alembic.txt
echo "alembic sesudah: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"
echo "commodity_policies: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from commodity_policies') baris"

if [ "$#" -eq 0 ]; then
  echo "tidak ada berkas tes yang disebut; selesai setelah migrasi"
  exit 0
fi

echo "== pytest"
docker compose exec -T -e DATABASE_URL="$DSN" -e DEMO_SESSION_ENFORCE=false backend \
  python -m pytest -q -p no:cacheprovider "$@" > _qa/f3/pytest.txt 2>&1
echo "PYTEST_EXIT=$?"
grep -E "^(FAILED|ERROR)" _qa/f3/pytest.txt | head -30
tail -5 _qa/f3/pytest.txt
echo "log: _qa/f3/pytest.txt"
