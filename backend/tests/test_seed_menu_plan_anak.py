"""Regresi: id baris `menu_plans` demo tidak boleh diganti selagi ada anak FK.

Bug yang dijaga (ditemukan 2026-10-17 saat menguji "Segarkan ke hari ini"):
`load_seed` memakai upsert pada (location_id, plan_date) dan, kalau yang menempati
tanggal itu baris `origin='demo'`, ia MENGGANTI `id` baris tersebut menjadi id
kanonik. `delivery_events` milik deret waktu demo masih menunjuk id lama →
`ForeignKeyViolationError` → seluruh refresh 500, bukan hanya satu baris gagal.

Kontrak yang diharapkan: anak-anak baris demo DIPINDAHKAN ke id kanonik lebih
dulu, sehingga tanggal kanonik tetap menang tanpa memutus relasi.
"""

import asyncio
from datetime import UTC, datetime

import asyncpg

from app.seed.seed_data import build_seed_rows, load_seed, stable_uuid

DSN = "postgresql://mealchain:mealchain_local@postgres:5432/mealchain"
REF = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _item():
    """Satu tanggal menu kanonik sebagai panggung uji."""
    item = build_seed_rows(REF)["menu_plans"][0]
    return item


async def _pasang_demo(item):
    conn = await asyncpg.connect(DSN)
    try:
        loc_id = await conn.fetchval("select id from locations where name=$1", item["location"])
        # panggung bersih: tidak ada baris (lokasi, tanggal) lain
        await conn.execute(
            "delete from delivery_events where menu_plan_id in "
            "(select id from menu_plans where location_id=$1 and plan_date=$2)",
            loc_id,
            item["plan_date"],
        )
        await conn.execute(
            "delete from menu_plans where location_id=$1 and plan_date=$2",
            loc_id,
            item["plan_date"],
        )
        id_demo = stable_uuid(
            "menu_plan", "demo-uji", item["location"], item["plan_date"].isoformat()
        )
        id_kirim = stable_uuid(
            "delivery", "demo-uji", item["location"], item["plan_date"].isoformat()
        )
        await conn.execute(
            "insert into menu_plans (id, location_id, plan_date, planned_portions, origin) "
            "values ($1,$2,$3,999,'demo')",
            str(id_demo),
            loc_id,
            item["plan_date"],
        )
        await conn.execute(
            "insert into delivery_events "
            "(id, menu_plan_id, delivered_portions, status, delivered_at, origin) "
            "values ($1,$2,999,'delivered', now(), 'demo')",
            str(id_kirim),
            str(id_demo),
        )
        return loc_id, id_demo, id_kirim
    finally:
        await conn.close()


async def _bongkar(item, id_kirim):
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute("delete from delivery_events where id=$1", str(id_kirim))
        await conn.execute(
            "delete from menu_plans where location_id="
            "(select id from locations where name=$1) and plan_date=$2 and origin='demo'",
            item["location"],
            item["plan_date"],
        )
    finally:
        await conn.close()
    await load_seed(REF)  # pulihkan baris kanonik yang tadi dihapus


def test_seed_memindahkan_anak_baris_demo_sebelum_mengganti_id() -> None:
    item = _item()

    async def alur():
        loc_id, id_demo, id_kirim = await _pasang_demo(item)
        try:
            await load_seed(REF)  # dulu: ForeignKeyViolationError
            conn = await asyncpg.connect(DSN)
            try:
                baris = await conn.fetch(
                    "select id, origin, planned_portions from menu_plans "
                    "where location_id=$1 and plan_date=$2",
                    loc_id,
                    item["plan_date"],
                )
                anak = await conn.fetchval(
                    "select menu_plan_id from delivery_events where id=$1", str(id_kirim)
                )
            finally:
                await conn.close()
        finally:
            await _bongkar(item, id_kirim)

        assert len(baris) == 1, "tanggal kanonik harus menyisakan tepat satu baris menu"
        assert baris[0]["origin"] == "seed", "isi kanonik menang: origin jadi seed"
        assert baris[0]["planned_portions"] == item["planned_portions"]
        assert str(anak) == str(baris[0]["id"]), (
            "kiriman harus menunjuk id baris yang benar-benar ada"
        )

    asyncio.run(alur())
