"""Semai data kanonik satu perintah (dipakai CI dan lingkungan bersih).

Kenapa ada skrip ini: suite tes mengharapkan data dengan **jangkar waktu yang
dipaku** — `--reference-time 2026-10-08T12:00:00+00:00` lalu `generate_timeseries()`
(lihat `docs/design.md`). Menjalankan `seed_data` dengan "hari ini" menggeser
jangkar dan membuat `test_agenda_api` serta KPI merah, sehingga urutan dua
langkah itu tidak boleh dihafal orang — harus jadi satu perintah.

Contoh:
    DATABASE_URL=postgresql+asyncpg://... python scripts/semai_kanonik.py --skip-routes

`--skip-routes` wajib di lingkungan tanpa OSRM (CI), karena `seed_data` secara
default menyinkronkan rute jalan dan akan menunggu timeout.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Dijalankan sebagai berkas (`python scripts/semai_kanonik.py`), sys.path[0]
# adalah folder scripts/ — bukan akar backend — sehingga `import app` gagal
# (terbukti saat menguji stack produksi 24 Okt 2026). Sisipkan akar backend.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed.timeseries import generate_timeseries  # noqa: E402

REFERENSI_BAKU = "2026-10-08T12:00:00+00:00"


def _semai_dasar(reference_time: str, *, skip_routes: bool) -> None:
    perintah = [
        sys.executable,
        "-m",
        "app.seed.seed_data",
        "--reference-time",
        reference_time,
        "--with-demo-users",
        "--with-demo-suppliers",
    ]
    if skip_routes:
        perintah.append("--skip-routes")
    print("+ " + " ".join(perintah[1:]), flush=True)
    # Seeder kanonik ini memang menyalakan data demo, jadi DEMO_MODE=true
    # diberikan eksplisit (temuan D-01: password demo tidak boleh dipasang
    # tanpa pernyataan bahwa ini lingkungan demo).
    subprocess.run(perintah, check=True, env={**os.environ, "DEMO_MODE": "true"})


async def _deret_waktu() -> dict:
    # `generate_timeseries` membuka engine-nya sendiri dari DATABASE_URL dan
    # commit per tahap; tidak perlu sesi dari pemanggil.
    return await generate_timeseries()


def main() -> None:
    parser = argparse.ArgumentParser(description="Semai data kanonik (deterministik)")
    parser.add_argument(
        "--reference-time",
        default=REFERENSI_BAKU,
        help=f"ISO 8601 tz-aware (default: {REFERENSI_BAKU})",
    )
    parser.add_argument(
        "--skip-routes",
        action="store_true",
        help="Jangan sinkronkan rute OSRM (wajib di CI)",
    )
    args = parser.parse_args()

    datetime.fromisoformat(args.reference_time)  # gagal cepat bila format salah

    _semai_dasar(args.reference_time, skip_routes=args.skip_routes)
    hasil = asyncio.run(_deret_waktu())
    print(f"deret waktu: {hasil}")


if __name__ == "__main__":
    main()
