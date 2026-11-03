#!/usr/bin/env bash
# Fase 3 — bukti migrasi: upgrade dari DB KOSONG, downgrade, upgrade lagi, alembic check.
# Dijalankan pada database sekali pakai (bukan DB demo).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DB="${F3_MIGRASI_DB:-mealchain_f3_migrasi}"
sandi="$(grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"
mkdir -p _qa/f3

echo "== DB kosong ${DB}"
docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1

echo "== upgrade head dari kosong"
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head > _qa/f3/migrasi-up.txt 2>&1
echo "UPGRADE_EXIT=$?"
tail -2 _qa/f3/migrasi-up.txt
echo "versi: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"

echo "== isi awal commodity_policies (komoditas belum ada di DB kosong → 0 baris, bukan karangan)"
echo "baris: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from commodity_policies')"

echo "== alembic check (tidak boleh mengusulkan op apa pun)"
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic check > _qa/f3/alembic-check.txt 2>&1
echo "CHECK_EXIT=$?"
tail -3 _qa/f3/alembic-check.txt

echo "== downgrade 041 → 040"
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic downgrade 040_session_modes_and_ownership > _qa/f3/migrasi-down.txt 2>&1
echo "DOWNGRADE_EXIT=$?"
echo "tabel ada? $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc "select count(*) from information_schema.tables where table_name='commodity_policies'") (harus 0)"
echo "versi: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"

echo "== upgrade lagi ke head"
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head > _qa/f3/migrasi-up2.txt 2>&1
echo "UPGRADE2_EXIT=$?"
echo "versi: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select version_num from alembic_version')"
