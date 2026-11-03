#!/usr/bin/env bash
# Semai ulang data demo di DB lokal (canonical + deret waktu + kasus skrip).
#
# Kapan dipakai:
#   - sesudah menjalankan suite backend (tes memakai DB demo bersama dan
#     meninggalkan/menghapus baris), atau
#   - sebelum demo bila tombol "Siapkan data demo" tidak dipakai.
#
# Kenapa reference-time DIPAKU 2026-10-08T12:00:00Z, bukan "hari ini":
#   seed_data menaruh menu plan 1..7 hari SEBELUM reference; tes backend memaku
#   rencana 2 Okt (HARI_SEED) dan rencana 20 Okt..5 Nov (deret waktu demo).
#   Menyemai dengan referensi "hari ini" menggeser jangkar itu dan membuat
#   test_agenda_api merah.
#
# Pemakaian:
#   bash scripts/semai-demo.sh            # canonical + deret waktu + kasus
#   bash scripts/semai-demo.sh --canonical # hanya snapshot canonical
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose exec -T -e DEMO_SESSION_ENFORCE=false)

# Kalau pemanggil mengekspor DATABASE_URL, teruskan ke dalam kontainer. Dengan
# begitu skrip ini bisa menyemai DB LAIN (mis. `mealchain_gate`) tanpa menyentuh
# DB demo yang sedang dipakai aplikasi:
#   DATABASE_URL=postgresql+asyncpg://.../mealchain_gate bash scripts/semai-demo.sh
if [[ -n "${DATABASE_URL:-}" ]]; then
  COMPOSE+=(-e "DATABASE_URL=${DATABASE_URL}")
fi

echo "[1/4] snapshot canonical (8 Okt 2026 12.00 UTC)"
"${COMPOSE[@]}" -e DEMO_MODE=true backend python -m app.seed.seed_data \
  --reference-time 2026-10-08T12:00:00+00:00 --with-demo-users --with-demo-suppliers

if [[ "${1:-}" == "--canonical" ]]; then
  echo "selesai (canonical saja)."
  exit 0
fi

echo "[2/4] deret waktu demo 1 Sep – 5 Nov 2026 (origin='demo')"
"${COMPOSE[@]}" -e PYTHONPATH=/app backend python -c "
import asyncio
from app.seed.timeseries import generate_timeseries
r = asyncio.run(generate_timeseries())
print('deret waktu:', r.get('counts'))
"

echo "[3/4] aktivitas demo + keputusan selesai + harga hari ini"
"${COMPOSE[@]}" -e PYTHONPATH=/app backend python -c "
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
"

echo "[4/4] 4 kasus skrip + rute jalan"
"${COMPOSE[@]}" -e PYTHONPATH=/app backend python -c "
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
"

# Terukur 20 Okt 2026: sesudah langkah 2-4, batch kanonik (origin='seed')
# tidak ada lagi sehingga test_actions kehabisan batch "telur @ Cianjur".
# Seed kanonik diulang di akhir — idempoten, ±10 detik.
echo "[5/5] pastikan snapshot kanonik utuh (origin='seed')"
"${COMPOSE[@]}" -e DEMO_MODE=true backend python -m app.seed.seed_data \
  --reference-time 2026-10-08T12:00:00+00:00 --with-demo-users --with-demo-suppliers >/dev/null

echo "selesai. Cek: GET /demo/data-status (tabel terisi, 0 baris tanpa stempel)."
