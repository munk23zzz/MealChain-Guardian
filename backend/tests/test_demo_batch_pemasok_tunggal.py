"""Satu pasangan (lokasi, komoditas) tidak boleh punya dua pemasok batch.

Kenapa ada (audit 18 Okt 2026): `seed_demo_activity` membuat empat kiriman per
lokasi dengan pemasok bergilir. Bila pasangan (lokasi, komoditas) itu SUDAH
punya batch kanonik dari pemasok lain, seed demo menambah batch kedua dengan
pemasok berbeda. Akibatnya `resolve_binding` tidak bisa menyimpulkan pemasok
untuk keputusan yang dibuat tanpa `allocation_binding` dan menolak dengan
"supplier_unknown: keputusan lama perlu binding batch eksplisit" — pagar yang
benar, tetapi dipicu oleh data yang kita buat sendiri.

Aturan yang dikunci tes ini: bila sebuah pasangan SUDAH punya tepat satu
pemasok kanonik, batch demo untuk pasangan itu memakai pemasok yang SAMA.
Pasangan yang sejak awal punya beberapa pemasok kanonik (mis. Jakarta×telur)
tidak dipaksa menjadi satu — itu data kanonik, bukan buatan seed demo.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Batch
from app.seed.demo_activity import seed_demo_activity

NOW = datetime(2026, 10, 18, 5, 0, tzinfo=UTC)


async def _pemasok_per_pasangan(origin_demo: bool | None = None) -> dict[tuple, set]:
    """(lokasi, komoditas) → himpunan supplier_id; origin_demo=None berarti semua."""
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as s:
            q = select(Batch.location_id, Batch.commodity_id, Batch.supplier_id)
            if origin_demo is True:
                q = q.where(Batch.origin == "demo")
            elif origin_demo is False:
                q = q.where(Batch.origin != "demo")
            hasil: dict[tuple, set] = {}
            for loc, com, sup in (await s.execute(q)).all():
                hasil.setdefault((loc, com), set()).add(sup)
            return hasil
    finally:
        await engine.dispose()


async def _jalankan_seeder() -> dict:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as s:
            hasil = await seed_demo_activity(s, NOW)
            await s.commit()
        return hasil
    finally:
        await engine.dispose()


def _pairs_tunggal_kanonik(kanonik: dict) -> set[tuple]:
    return {pair for pair, sups in kanonik.items() if len(sups) == 1}


def test_demo_memakai_pemasok_kanonik_untuk_pasangan_tunggal() -> None:
    import asyncio

    async def skenario():
        sebelum = await _pemasok_per_pasangan(origin_demo=False)
        tunggal = _pairs_tunggal_kanonik(sebelum)
        assert tunggal, "butuh minimal satu pasangan dengan tepat satu pemasok kanonik"

        await _jalankan_seeder()

        sesudah_semua = await _pemasok_per_pasangan()
        demo = await _pemasok_per_pasangan(origin_demo=True)

        dilanggar = {
            pair: sups
            for pair, sups in sesudah_semua.items()
            if pair in tunggal and len(sups) > 1
        }
        assert not dilanggar, (
            "seed demo menambah pemasok kedua untuk pasangan yang tadinya tunggal: "
            f"{[(str(p[0]), str(p[1]), len(s)) for p, s in dilanggar.items()]}"
        )
        # batch demo untuk pasangan itu memang memakai pemasok kanonik
        for pair in tunggal & set(demo):
            assert demo[pair] == sebelum[pair], (
                "batch demo memakai pemasok berbeda dari kanonik: "
                f"pair={pair} demo={demo[pair]} kanonik={sebelum[pair]}"
            )
        # lebih umum: batch demo TIDAK PERNAH menambah pemasok baru ke pasangan
        # yang sudah punya batch kanonik (walau kanoniknya berlapis-lapis).
        asing = {
            pair: (demo[pair] - sebelum[pair])
            for pair in set(demo) & set(sebelum)
            if demo[pair] - sebelum[pair]
        }
        assert not asing, (
            "seed demo menambah pemasok yang tidak ada di data kanonik: "
            f"{[(str(p[0]), str(p[1]), len(s)) for p, s in asing.items()]}"
        )

    asyncio.run(skenario())
