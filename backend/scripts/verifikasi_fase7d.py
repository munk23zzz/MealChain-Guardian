"""Bukti Fase 7d — tabel dampak angka SEBELUM/SESUDAH jarak pemasok masuk biaya.

Dipakai untuk syarat plan §7.4b: (a) tabel dampak angka sebelum/sesudah untuk
4 kasus skrip, (b) ruling bertanggal, (c) jangkar kanonik tetap hijau,
(d) fallback jelas bila pemasok tanpa koordinat.

Cara kerja (bukan klaim, angka nyata dari DB):
- pipeline dijalankan DUA KALI dengan facts yang sama dari DB. Bedanya hanya
  elemen ke-7 (peta jarak pemasok): ada = "sesudah", kosong = "sebelum"
  (perilaku sebelum 7d, yaitu 6-tuple Task 9).
- Setiap kandidat untuk tujuan Jakarta (target demo) dicetak: nilai SDC
  sebelum/sesudah, delta, km kaki pertama, label kejujuran, dan rank.
- Baris terakhir membandingkan angka tersimpan di DB untuk 4 kasus skrip
  (`POST /demo/seed`) dengan angka mesin sekarang — supaya selisih fixture
  tidak pernah tersembunyi.

Jalankan di kontainer: `docker compose exec -T backend python scripts/verifikasi_fase7d.py`
"""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

# Skrip dijalankan langsung (`python scripts/...`) → pastikan root backend
# ada di sys.path supaya `app` bisa diimpor seperti di dalam suite pytest.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import recommendation_service as rs

URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain",
)

# 4 kasus skrip demo (`POST /demo/seed`): (nama kasus, sumber, tujuan, komoditas)
# gangguan-logistik punya DUA keputusan (v1 Bogor ditolak → v2 Cianjur).
KASUS = [
    ("rejection-loop-kuota", "Cianjur", "Jakarta", "telur"),
    ("shortage-darurat", "Bogor", "Jakarta", "telur"),
    ("supplier-janggal", "Cianjur", "Jakarta", "telur"),
    ("gangguan-logistik v1", "Bogor", "Jakarta", "telur"),
    ("gangguan-logistik v2", "Cianjur", "Jakarta", "telur"),
]


async def _recs(session, with_leg: bool):
    async def _fetch():
        facts = await rs.fetch_operational_facts(session, None)
        return facts if with_leg else facts[:6]

    return await rs.build_recommendations(_fetch)


def _index(out):
    return {
        (
            r["candidate"]["source_location"],
            r["candidate"]["destination_location"],
            r["candidate"]["commodity"],
        ): r
        for r in out["recommendations"]
    }


async def main() -> None:
    engine = create_async_engine(URL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        before = _index(await _recs(session, with_leg=False))
        after = _index(await _recs(session, with_leg=True))

        print("=" * 108)
        print("DAMPAK FASE 7d — jarak pemasok (kaki pertama) masuk biaya SDC")
        print("=" * 108)
        print(f"{'kasus':22} {'kandidat':26} {'SDC sebelum':>16} {'SDC sesudah':>16}"
              f" {'delta':>11} {'leg km':>8} {'label':28}")
        print("-" * 108)
        for nama, src, dst, com in KASUS:
            key = (src, dst, com)
            b, a = before.get(key), after.get(key)
            if b is None or a is None:
                print(f"{nama:22} {src+'→'+dst+':'+com:26} KANDIDAT TIDAK ADA")
                continue
            sdc_b = Decimal(b["safe_delivered_cost"])
            sdc_a = Decimal(a["safe_delivered_cost"])
            leg = a["supplier_leg"]
            print(
                f"{nama:22} {src+'→'+dst+':'+com:26} {str(sdc_b):>16} {str(sdc_a):>16}"
                f" {str(sdc_a - sdc_b):>11} {str(leg['km']):>8} {str(leg['reference']):28}"
            )

        print("-" * 108)
        print("PERINGKAT (rank) sebelum → sesudah — memperlihatkan apakah keputusan berubah")
        changed = []
        for key in sorted(set(before) | set(after)):
            rb = before.get(key, {}).get("rank")
            ra = after.get(key, {}).get("rank")
            if rb != ra:
                changed.append((key, rb, ra))
        if not changed:
            print(
                "  tidak ada kandidat yang berpindah peringkat "
                "(rank identik untuk semua kandidat)"
            )
        for key, rb, ra in changed:
            print(f"  {key[0]}→{key[1]}:{key[2]}  rank {rb} → {ra}")

        print("-" * 108)
        print("KANDIDAT DENGAN KAKI PERTAMA TERPANJANG (5 teratas, sesudah)")
        rows = sorted(
            (r for r in after.values() if r["supplier_leg"]["km"] is not None),
            key=lambda r: Decimal(r["supplier_leg"]["km"]),
            reverse=True,
        )[:5]
        for r in rows:
            c = r["candidate"]
            print(
                f"  {c['source_location']:11}→{c['destination_location']:11} {c['commodity']:7}"
                f" leg {r['supplier_leg']['km']:>9} km  biaya kaki {r['supplier_leg']['cost']:>12}"
                f"  SDC {r['safe_delivered_cost']}"
            )

        print("-" * 108)
        print("TOTAL KAKI PERTAMA YANG TIDAK DIKETAHUI (tidak ditebak, biaya 0 + label)")
        unknown = [
            r for r in after.values()
            if r["supplier_leg"]["reference"] != "supplier_coordinates"
        ]
        print(f"  {len(unknown)} dari {len(after)} kandidat")
        for r in unknown[:5]:
            c = r["candidate"]
            print(f"    {c['source_location']}→{c['destination_location']}:{c['commodity']}"
                  f"  label={r['supplier_leg']['reference']}")

        print("-" * 108)
        rows = (
            await session.execute(
                text(
                    "select d.demo_case, l.name as src, t.name as tgt, c.name as com,"
                    " d.quantity_kg, d.safe_delivered_cost"
                    " from decisions d"
                    " left join locations l on l.id = d.source_location_id"
                    " left join locations t on t.id = d.target_location_id"
                    " left join commodities c on c.id = d.commodity_id"
                    " where d.demo_case is not null"
                    " order by d.demo_case, d.iteration"
                )
            )
        ).all()
        print("ANGKA TERSIMPAN DI DB UNTUK 4 KASUS SKRIP vs angka mesin sekarang")
        for row in rows:
            key = (row.src, row.tgt, row.com)
            now = after.get(key)
            now_sdc = Decimal(now["safe_delivered_cost"]) if now else None
            print(
                f"  {row.demo_case:22} {str(row.src):9}→{str(row.tgt):8} {str(row.com):6}"
                f" DB={str(row.safe_delivered_cost):>16}  mesin={str(now_sdc):>16}"
                f"  {'sama' if now_sdc == row.safe_delivered_cost else 'BERBEDA'}"
            )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
