#!/usr/bin/env bash
# Resep gerbang Fase 6 — sama dengan scripts/gerbang-db-terpisah.sh (3a→3→3c),
# tetapi berhenti setelah DB siap agar berkas tes yang dijalankan bisa dipilih.
# DB demo `mealchain` hanya dibaca (pg_dump) dan TIDAK ditulis.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

DB="${F6_DB:-mealchain_f6_gate}"
DSN_DB="$(docker compose exec -T backend printenv DATABASE_URL | tr -d '\r')"
DSN="$(echo "$DSN_DB" | sed -E "s#/[A-Za-z0-9_]+(\\?|$)#/${DB}\\1#")"
echo "DSN DB = ${DSN##*@}"

echo "== [1] siapkan DB $DB =="
docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1

echo "== [2] migrasi ke head =="
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head 2>&1 | tail -2 || exit 1

echo "== [3a] canonical + akun demo =="
DATABASE_URL="$DSN" bash scripts/semai-demo.sh --canonical 2>&1 | tail -2 || exit 1

echo "== [3] template demo (jalur tombol 'Siapkan data demo') =="
docker compose exec -T -e DATABASE_URL="$DSN" -e PYTHONPATH=/app backend python -c "
import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings
from app.seed.demo_template import build_into

async def main():
    e = create_async_engine(settings.database_url)
    m = async_sessionmaker(e, expire_on_commit=False)
    async with m() as db:
        laporan = await build_into(db, purge=True, freeze=True, bersihkan_sisa=False)
        await db.commit()
        print('template:', {k: v for k, v in laporan.items() if k != 'rincian'})
    await e.dispose()

asyncio.run(main())
" 2>&1 | tail -2 || exit 1

echo "== [3c] semai penuh (deret waktu + aktivitas + kasus) =="
DATABASE_URL="$DSN" bash scripts/semai-demo.sh 2>&1 | tail -3 || exit 1

echo "== [4] ringkas isi DB gate =="
docker exec mealchain-postgres psql -U mealchain -d "$DB" -At -F ' | ' \
  -c "select 'supply:'||origin||'='||count(*) from supply_records group by origin" \
  -c "select 'decisions:'||origin||'='||count(*) from decisions group by origin" \
  -c "select 'batch='||count(*) from batches" \
  -c "select 'batch_le_anchor='||count(*) from batches where harvested_at <= '2026-10-08 12:00+00'" \
  -c "select 'menu='||count(*) from menu_plans"

echo "== [5] DB demo tidak disentuh =="
docker exec mealchain-postgres psql -U mealchain -d mealchain -At \
  -c "select 'demo_batch='||count(*)||' demo_decision='||(select count(*) from decisions) from batches"
echo "SELESAI"
