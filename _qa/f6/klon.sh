#!/usr/bin/env bash
# Fase 6 — buat/segarkan klon DB demo untuk gerbang tes (baca dari DB demo, tulis ke klon).
# Pemakaian: bash _qa/f6/klon.sh <nama_db>   (default mealchain_f6_base)
set -u
DB="${1:-mealchain_f6_base}"
PG=mealchain-postgres
docker exec "$PG" dropdb --if-exists -U mealchain "$DB" || exit 1
docker exec "$PG" createdb -U mealchain "$DB" || exit 1
docker exec "$PG" bash -c "pg_dump -U mealchain -d mealchain --no-owner --no-privileges | psql -q -U mealchain -d $DB" >/dev/null 2>&1 || exit 1
echo "clone=$DB decisions=$(docker exec "$PG" psql -U mealchain -d "$DB" -tAc 'select count(*) from decisions')"
