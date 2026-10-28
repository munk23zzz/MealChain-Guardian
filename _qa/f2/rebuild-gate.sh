#!/usr/bin/env bash
# Bangun ulang DB klon `mealchain_gate` (Fase 2) lalu jalankan tes fase.
# Urutan mengikuti scripts/gerbang-db-terpisah.sh; langkah [1/4] semai penuh
# kedua dilewati karena `seed_data` kanonik sudah dijalankan sebelum template
# (menjalankannya lagi memicu bentrokan uq_supply_records_loc_com_time_source
# pada baris demo milik template).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

DB=mealchain_gate
sandi="$(grep -E '^POSTGRES_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '"'"'"'"'"'")"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"

echo "== [1/6] DB $DB dibuat ulang =="
docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null || exit 1
docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1

echo "== [2/6] alembic upgrade head ==="
docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head 2>&1 | tail -2 || exit 1

echo "== [3/6] canonical =="
DATABASE_URL="$DSN" bash scripts/semai-demo.sh --canonical >/tmp/f2-canonical.log 2>&1 || exit 1
echo "canonical ok"

echo "== [4/6] template =="
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
        print('template htt:', laporan.get('hitung'))
    await e.dispose()

asyncio.run(main())
" 2>&1 | tail -1 || exit 1

echo "== [5/6] deret waktu + aktivitas + kasus =="
docker compose exec -T -e DATABASE_URL="$DSN" -e DEMO_SESSION_ENFORCE=false -e PYTHONPATH=/app backend python -c "
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.api.demo import _seed_demo_cases, _sync_routes_aman, _target_lokasi
from app.core.config import settings
from app.models import User
from app.seed.demo_activity import (seed_demo_activity, seed_demo_completed_decisions, seed_demo_daily_prices)
from app.seed.timeseries import generate_timeseries

async def main():
    now = datetime.now(timezone.utc)
    r = await generate_timeseries()
    e = create_async_engine(settings.database_url)
    m = async_sessionmaker(e, expire_on_commit=False)
    async with m() as db:
        print('aktivitas:', await seed_demo_activity(db, now))
        print('selesai  :', await seed_demo_completed_decisions(db, now))
        print('harga    :', await seed_demo_daily_prices(db, now))
        routes, err = await _sync_routes_aman(now)
        print('rute     :', routes, err)
        user = (await db.execute(select(User).where(User.role == 'sppg_head').limit(1))).scalar_one()
        print('kasus    :', await _seed_demo_cases(db, force=True, target=await _target_lokasi(db, user)))
    await e.dispose()

asyncio.run(main())
" 2>&1 | tail -5 || exit 1

echo "== [6/6] ringkas isi DB =="
docker exec mealchain-postgres psql -U mealchain -d "$DB" -At -F ' | ' \
  -c "select 'supply:'||origin||'='||count(*) from supply_records group by origin" \
  -c "select 'decisions:'||origin||'='||count(*) from decisions group by origin" \
  -c "select 'batch='||count(*) from batches" \
  -c "select 'users='||count(*) from users" \
  -c "select 'sesi_aktif='||count(*) from demo_sessions where status='active'"

echo "== selesai =="
