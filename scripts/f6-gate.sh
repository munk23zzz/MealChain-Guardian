#!/usr/bin/env bash
# Fase 6 — gerbang pada klon DB sekali pakai (bukan DB demo).
# Pemakaian: bash scripts/f6-gate.sh [berkas-tes ...]
#
# Kenapa klon: DB demo `mealchain` hanya boleh SELECT. Suite pytest menulis
# (users, decisions, evidence), jadi gerbang dijalankan pada klon yang dibuat
# dari DB demo lalu dimigrasikan ke head. Kunci gerbang `tests/gate_lock.py`
# bersifat per-database, sehingga suite sesi lain di `mealchain` tidak
# memblokir run ini dan tidak pula dicampuri.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DB="${F6_DB:-mealchain_f6}"
SUMBER="${F6_SUMBER:-mealchain}"
REUSE="${F6_REUSE:-0}"
sandi="$(grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"
mkdir -p _qa/f6

if [ "${REUSE}" != "1" ]; then
  echo "== siapkan klon ${DB} dari ${SUMBER}"
  docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
    "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
  docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1
  docker exec mealchain-postgres sh -lc "pg_dump -U mealchain -d ${SUMBER} | psql -q -U mealchain -d ${DB}" >/dev/null 2>&1 || exit 1

  echo "== migrate ke head"
  docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head > _qa/f6/alembic.txt 2>&1
  echo "ALEMBIC_EXIT=$?"
  tail -2 _qa/f6/alembic.txt
fi

echo "klon ${DB}: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from batches') batch, \
alembic $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"

if [ "$#" -eq 0 ]; then
  echo "tidak ada berkas tes yang disebut; selesai setelah migrasi"
  exit 0
fi

echo "== pytest"
docker compose exec -T -e DATABASE_URL="$DSN" -e DEMO_SESSION_ENFORCE=false backend \
  python -m pytest -q -p no:cacheprovider "$@" > _qa/f6/pytest-gate.txt 2>&1
echo "PYTEST_EXIT=$?"
grep -E "^(FAILED|ERROR)" _qa/f6/pytest-gate.txt | head -30
tail -5 _qa/f6/pytest-gate.txt
echo "log: _qa/f6/pytest-gate.txt"
