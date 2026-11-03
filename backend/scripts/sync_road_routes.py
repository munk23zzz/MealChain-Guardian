"""Ambil rute JALAN (OSRM) untuk kiriman aktif → tabel cache `road_routes`.

Jalankan SEKALI saat menyiapkan demo (keputusan pemilik 2026-10-16). Sesudahnya
peta tidak butuh internet sama sekali: geometrinya dibaca dari DB.

Contoh:
    PYTHONPATH=/app python scripts/sync_road_routes.py
    PYTHONPATH=/app python scripts/sync_road_routes.py --semua-batch
    PYTHONPATH=/app python scripts/sync_road_routes.py --timeout 5 --wajib

Rujukan waktu: kiriman "aktif" = `usable_until >= --reference-time`
(default: sekarang). Dipakai untuk meniru keadaan demo pada tanggal tertentu.

Keluar dengan kode 1 hanya kalau `--wajib` dan ada rute yang gagal diambil —
tanpa `--wajib`, laporan tetap dicetak apa adanya (demo tidak batal hanya
karena OSRM sedang tidak bisa dihubungi).
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.seed.road_routes import OSRM_BASE_URL_DEFAULT, sync_road_routes


async def _jalankan(args: argparse.Namespace) -> dict:
    ref = datetime.fromisoformat(args.reference_time) if args.reference_time else datetime.now(UTC)
    if ref.tzinfo is None:
        raise SystemExit("--reference-time wajib tz-aware (mis. 2026-10-16T06:00:00+00:00)")

    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            return await sync_road_routes(
                session,
                now=ref,
                base_url=args.base_url,
                timeout=args.timeout,
                semua_batch=args.semua_batch,
            )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sinkronkan rute jalan (OSRM) ke cache")
    parser.add_argument("--base-url", default=OSRM_BASE_URL_DEFAULT, help="server OSRM")
    parser.add_argument("--timeout", type=float, default=20.0, help="detik per permintaan")
    parser.add_argument(
        "--reference-time",
        default=None,
        help="ISO 8601 tz-aware; kiriman aktif = usable_until >= waktu ini",
    )
    parser.add_argument(
        "--semua-batch",
        action="store_true",
        help="ikutkan kiriman kedaluwarsa (tidak pernah digambar; hanya untuk kelengkapan)",
    )
    parser.add_argument(
        "--wajib",
        action="store_true",
        help="keluar kode 1 bila ada rute yang gagal diambil",
    )
    args = parser.parse_args()

    laporan = asyncio.run(_jalankan(args))

    cakupan = "semua batch" if args.semua_batch else "hanya kiriman aktif"
    print(f"Rute jalan (OSRM) — sumber {laporan['sumber_rute']} — {cakupan}")
    print(f"  permintaan unik   : {laporan['diperiksa']}")
    print(f"  sudah ada di cache: {laporan['sudah_ada']}")
    print(f"  duplikat dilewati : {laporan['duplikat']}")
    print(f"  diambil sekarang  : {laporan['diambil']}")
    print(f"  gagal             : {laporan['gagal']}")
    for alasan, jumlah in sorted(laporan["alasan_gagal"].items()):
        print(f"    - {alasan}: {jumlah}")
    for rincian in laporan["rincian_gagal"]:
        print(
            f"      {rincian['key']} ({rincian['nama']}): "
            f"{rincian['alasan']} — {rincian['detail']}"
        )

    if laporan["gagal"] == 0:
        print("Semua rute kiriman aktif tersimpan di cache. Peta tidak butuh internet.")
    elif args.wajib:
        print("ADA RUTE GAGAL (--wajib).")
        return 1
    else:
        print(
            "Ada rute gagal; peta akan menyebutnya 'belum disinkronkan' "
            "(jujur, tanpa garis karangan)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
