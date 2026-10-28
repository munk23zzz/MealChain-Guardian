#!/usr/bin/env bash
# Semai DB klon untuk uji isolasi Fase 2 (kode dari commit, bukan working tree).
# Meniru urutan scripts/semai-demo.sh, tetapi tiap langkah dijalankan di
# kontainer sekali-pakai yang me-mount WORKTREE (commit 840897f + prasyarat
# untracked), supaya yang diuji benar-benar kode commit.
set -euo pipefail

AKAR="$(cd "$(dirname "$0")/../.." && pwd)"
WT="$(cygpath -w "$TMPDIR")/wt-fase2"
NET=mealchain-guardian_mealchain-network
IMG=mealchain-guardian-backend
DB=mealchain_f2_uji

DSN=$(docker inspect mealchain-backend --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep '^DATABASE_URL=' | sed 's/^DATABASE_URL=//' \
  | sed -E "s#/mealchain(\\?|\$)#/${DB}\\1#")

JALAN=(docker run --rm --network "$NET"
  -v "$WT/backend:/app" -v "$WT/agent:/agent" -v "$WT/data:/data"
  -w /app -e "DATABASE_URL=$DSN" -e PYTHONPATH=/app:/:/agent -e DEMO_MODE=true)

echo "== [1/5] canonical =="
"${JALAN[@]}" "$IMG" python -m app.seed.seed_data \
  --reference-time 2026-10-08T12:00:00+00:00 --with-demo-users --with-demo-suppliers 2>&1 | tail -3

echo "== [2/5] deret waktu =="
"${JALAN[@]}" "$IMG" python -c "
import asyncio
from app.seed.timeseries import generate_timeseries
print('deret:', asyncio.run(generate_timeseries()).get('counts'))
" 2>&1 | tail -3

echo "== [3/5] aktivitas + keputusan selesai + harga =="
"${JALAN[@]}" "$IMG" python -c "
import asyncio
from datetime import datetime, timezone
from app.seed.demo_activity import (
    seed_demo_activity, seed_demo_completed_decisions, seed_demo_daily_prices,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings

async def main():
    now = datetime.now(timezone.utc)
    e = create_async_engine(settings.database_url)
    m = async_sessionmaker(e, expire_on_commit=False)
    async with m() as db:
        print('aktivitas:', await seed_demo_activity(db, now))
        print('selesai  :', await seed_demo_completed_decisions(db, now))
        print('harga    :', await seed_demo_daily_prices(db, now))
    await e.dispose()

asyncio.run(main())
" 2>&1 | tail -4

echo "== [4/5] kasus skrip + rute =="
"${JALAN[@]}" "$IMG" python -c "
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.api.demo import _seed_demo_cases, _sync_routes_aman, _target_lokasi
from app.core.config import settings
from app.models import User

async def main():
    now = datetime.now(timezone.utc)
    e = create_async_engine(settings.database_url)
    m = async_sessionmaker(e, expire_on_commit=False)
    async with m() as db:
        routes, err = await _sync_routes_aman(now)
        user = (await db.execute(select(User).where(User.role == 'sppg_head').limit(1))).scalar_one()
        print('rute :', routes, 'err:', err)
        print('kasus:', await _seed_demo_cases(db, force=True, target=await _target_lokasi(db, user)))
    await e.dispose()

asyncio.run(main())
" 2>&1 | tail -4

echo "== [5/5] canonical ulang =="
"${JALAN[@]}" "$IMG" python -m app.seed.seed_data \
  --reference-time 2026-10-08T12:00:00+00:00 --with-demo-users --with-demo-suppliers 2>&1 | tail -2

echo "== bentuk data =="
docker exec mealchain-postgres psql -U mealchain -d "$DB" -t -c "
select 'supply:'||origin||'='||count(*) from supply_records group by origin
union all select 'decisions:'||origin||'='||count(*) from decisions group by origin
union all select 'batch_total='||count(*) from batches
union all select 'users='||count(*) from users
union all select 'sesi_aktif='||count(*) from demo_sessions where ended_at is null;
" | sed '/^$/d'
echo "== selesai =="
