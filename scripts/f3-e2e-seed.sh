#!/usr/bin/env bash
# Fase 3 — bukti celah "DB baru = 0 profil" tertutup: DB KOSONG → migrasi → seed → profil.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DB="${F3_E2E_DB:-mealchain_f3_e2e}"
sandi="$(grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"
mkdir -p _qa/f3

echo "== DB kosong ${DB}"
docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1

echo "== migrasi ke head"
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head > _qa/f3/e2e-up.txt 2>&1
echo "UPGRADE_EXIT=$?"
echo "commodity_policies setelah MIGRASI: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from commodity_policies')"

echo "== seed kanonik (REF jangkar 2026-10-08T12:00:00+00:00)"
docker compose exec -T -e DATABASE_URL="$DSN" -e SEED_DATABASE_URL="$DSN" backend \
  python -m app.seed.seed_data --reference-time 2026-10-08T12:00:00+00:00 > _qa/f3/e2e-seed.txt 2>&1
echo "SEED_EXIT=$?"
tail -5 _qa/f3/e2e-seed.txt
echo "commodity_policies setelah SEED: $(docker exec mealchain-postgres psql -U mealchain -d ${DB} -tAc 'select count(*) from commodity_policies')"
echo "per komoditas:"
docker exec mealchain-postgres psql -U mealchain -d ${DB} -c \
  "select c.name, p.cold_chain_required, p.safe_temp_min_c, p.safe_temp_max_c, p.shelf_life_days, p.min_temperature_samples, p.max_observation_age_minutes, p.policy_kind from commodity_policies p join commodities c on c.id=p.commodity_id where p.is_active order by c.name;"
