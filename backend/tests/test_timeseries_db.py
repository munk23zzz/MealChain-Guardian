"""Generator deret waktu demo menyentuh DB (Fase 4) — aturan yang mengikat.

Fokus tes ini BUKAN "apakah barisnya banyak", tapi **apakah jangkar kanonik
selamat**. Data demo yang bagus tapi menggeser angka kanonik (1.400 kg Cianjur,
300 kg Jakarta, jendela KPI 7→8 Okt) adalah kerusakan, bukan kemajuan.

Fixture `restore_demo` mengembalikan DB ke keadaan sebelum tes: kalau memang
sudah ada baris demo (dataset demo memang disiapkan), ia digenerate ulang;
kalau tidak ada, ia dibersihkan. Jadi menjalankan suite tidak menghapus
dataset demo yang sengaja disiapkan untuk demo hari-H.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.seed.timeseries import (
    CANONICAL_REF,
    DEFAULT_END,
    DEFAULT_START,
    actual_cutoff,
    generate_timeseries,
    preview_timeseries,
    purge_demo_rows,
)

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

WINDOW_START = CANONICAL_REF - timedelta(days=1)  # 7 Okt 12:00 UTC

TABLES = (
    "supply_records",
    "price_signals",
    "menu_plans",
    "delivery_events",
    "disposal_events",
)


def _engine():
    return create_engine(DB_URL)


def _count(conn, table: str, origin: str) -> int:
    return int(
        conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE origin = :origin"),
            {"origin": origin},
        ).scalar()
        or 0
    )


def _counts() -> dict[str, int]:
    with _engine().connect() as conn:
        return {
            f"{table}:{origin}": _count(conn, table, origin)
            for table in TABLES
            for origin in ("seed", "demo")
        }


async def _generate(**kwargs):
    return await generate_timeseries(**kwargs)


@pytest.fixture()
def restore_demo():
    """Kembalikan keadaan baris demo seperti sebelum tes (lihat docstring modul)."""
    before = _counts()
    yield
    had_demo = any(
        value for key, value in before.items() if key.endswith(":demo")
    )
    if had_demo:
            asyncio.run(
            _generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12)
        )
    else:
        asyncio.run(purge_demo_rows())


def test_generate_menambah_demo_tanpa_mengubah_kanonik(restore_demo):
    # Kanvas bersih dulu supaya tes tidak bergantung apakah dataset demo sudah ada.
    asyncio.run(purge_demo_rows())
    before = _counts()
    summary = asyncio.run(
        _generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12)
    )
    after = _counts()

    for name, table in (
        ("supply", "supply_records"),
        ("prices", "price_signals"),
        ("menu_plans", "menu_plans"),
    ):
        assert after[f"{table}:seed"] == before[f"{table}:seed"], (
            f"baris kanonik {table} berubah — generator tidak boleh menyentuhnya"
        )
        assert summary["counts"][name]["added"] > 0, (
            f"generator tidak menambah baris demo di {table}"
        )
        assert after[f"{table}:demo"] == summary["counts"][name]["added"]
    assert summary["counts"]["supply"]["planned"] == 30 * summary["actual_timestamps"]
    # Cakupan rencana menu harus utuh: (demo + kanonik) = grid 10 lokasi × 66 hari.
    assert after["menu_plans:demo"] + after["menu_plans:seed"] == 660


def test_generate_idempoten(restore_demo):
    first = asyncio.run(
        _generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12)
    )
    second = asyncio.run(
        _generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12)
    )
    for name, table in (
        ("supply", "supply_records"),
        ("prices", "price_signals"),
        ("menu_plans", "menu_plans"),
    ):
        assert second["counts"][name]["added"] == 0, (
            f"jalan kedua menambah baris {table} — upsert tidak idempoten"
        )
    assert second["counts"]["supply"]["in_db"] == first["counts"]["supply"]["in_db"]
    assert second["counts"]["prices"]["in_db"] == first["counts"]["prices"]["in_db"]


def test_deret_aktual_berhenti_di_ujung_rencana(restore_demo):
    """Deret AKTUAL demo mengisi sampai ujung rencana — dan tidak melewatinya.

    Menggantikan butir C2 rencana ("jendela KPI tetap murni kanonik"). Aturan itu
    DIGANTI 2026-10-17 atas permintaan pemilik: pagar lama menyisakan 9 Okt → 5 Nov
    kosong, sehingga kalender menulis "tidak ada catatan" dan jendela KPI 24 jam /
    7 hari kosong. Kontrak baru: tidak ada baris aktual MELEWATI `DEFAULT_END`, dan
    rentang sesudah REF tetap terisi.
    """
    asyncio.run(_generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12))
    with _engine().connect() as conn:
        for table, column in (
            ("supply_records", "recorded_at"),
            ("price_signals", "recorded_at"),
        ):
            lewat_ujung = conn.execute(
                text(
                    f"SELECT count(*) FROM {table} WHERE origin = 'demo' "
                    f"AND {column} >= :batas"
                ),
                {"batas": DEFAULT_END},
            ).scalar()
            assert int(lewat_ujung or 0) == 0, (
                f"{table} punya baris demo MELEWATI ujung rencana (5 Nov)"
            )
            isi_sesudah_ref = conn.execute(
                text(
                    f"SELECT count(*) FROM {table} WHERE origin = 'demo' "
                    f"AND {column} > :ref"
                ),
                {"ref": CANONICAL_REF},
            ).scalar()
            assert int(isi_sesudah_ref or 0) > 0, (
                f"{table}: rentang 9 Okt → 5 Nov wajib terisi"
            )
        latest = conn.execute(
            text(
                "SELECT max(recorded_at) FROM supply_records WHERE origin = 'demo'"
            )
        ).scalar()
    assert latest is not None
    assert latest < actual_cutoff()
    assert latest == datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def test_record_terbaru_per_pasangan_dari_deret_dan_kanonik_tetap_ada(restore_demo):
    """Record terbaru per lokasi×komoditas = stamp terakhir deret; kanonik tetap ada.

    Dulu tes ini menuntut record terbaru SEMUA pasangan tetap kanonik (butir C1).
    Sejak 2026-10-17 deret aktual berjalan sampai 5 Nov, jadi yang terbaru memang
    baris demo; yang wajib tetap benar adalah baris KANONIK per pasangan masih ada
    dan nilainya tidak bergeser.
    """
    asyncio.run(_generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12))
    with _engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT ON (location_id, commodity_id)
                       location_id, commodity_id, quantity_kg, origin, recorded_at
                FROM supply_records
                ORDER BY location_id, commodity_id, recorded_at DESC
                """
            )
        ).all()
        assert len(rows) == 30
        assert {row.origin for row in rows} == {"demo"}
        assert {row.recorded_at for row in rows} == {
            datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
        }
        kanonik = conn.execute(
            text(
                "SELECT count(*) FROM supply_records "
                "WHERE origin = 'seed' AND recorded_at = :ref"
            ),
            {"ref": CANONICAL_REF},
        ).scalar()
        cianjur_telur = conn.execute(
            text(
                """
                SELECT s.quantity_kg
                FROM supply_records s
                JOIN locations l ON l.id = s.location_id
                JOIN commodities c ON c.id = s.commodity_id
                WHERE l.name = 'Cianjur' AND c.name = 'telur'
                ORDER BY s.recorded_at DESC
                LIMIT 1
                """
            )
        ).scalar()
    assert int(kanonik or 0) == 30, "baris kanonik per pasangan harus tetap ada"
    # Nilai terbaru kini dari deret (deterministik, bukan angka kanonik 1.400 kg).
    assert float(cianjur_telur) != 1400.0


def test_menu_plans_kanonik_tidak_ditimpa(restore_demo):
    """Hari kanonik (24 Sep–7 Okt) harus tetap `seed` dengan porsi aslinya."""
    with _engine().connect() as conn:
        before = dict(
            conn.execute(
                text(
                    "SELECT location_id::text || '|' || plan_date, planned_portions "
                    "FROM menu_plans WHERE origin = 'seed'"
                )
            ).all()
        )
    asyncio.run(_generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12))
    with _engine().connect() as conn:
        after = dict(
            conn.execute(
                text(
                    "SELECT location_id::text || '|' || plan_date, planned_portions "
                    "FROM menu_plans WHERE origin = 'seed'"
                )
            ).all()
        )
        kembar = conn.execute(
            text(
                "SELECT count(*) FROM (SELECT location_id, plan_date "
                "FROM menu_plans GROUP BY 1,2 HAVING count(*) > 1) d"
            )
        ).scalar()
        demo_hari = conn.execute(
            text("SELECT count(DISTINCT plan_date) FROM menu_plans WHERE origin = 'demo'")
        ).scalar()
    assert after == before
    assert int(kembar or 0) == 0
    assert int(demo_hari or 0) > 0


def test_rencana_menu_menjangkau_5_november(restore_demo):
    """Rencana menu menutup sampai ujung rentang; deret aktual ikut terisi, tak lewat."""
    asyncio.run(_generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12))
    with _engine().connect() as conn:
        terjauh = conn.execute(
            text("SELECT max(plan_date) FROM menu_plans WHERE origin = 'demo'")
        ).scalar()
        aktual_setelah_ref = conn.execute(
            text(
                "SELECT count(*) FROM supply_records "
                "WHERE origin = 'demo' AND recorded_at > :ref"
            ),
            {"ref": CANONICAL_REF},
        ).scalar()
        aktual_lewat_ujung = conn.execute(
            text(
                "SELECT count(*) FROM supply_records "
                "WHERE origin = 'demo' AND recorded_at >= :batas"
            ),
            {"batas": DEFAULT_END},
        ).scalar()
    assert str(terjauh) == DEFAULT_END.date().isoformat()
    # Sejak 2026-10-17 aktual memang mengisi 9 Okt → 5 Nov (dulu dilarang karena
    # "jendela KPI harus murni kanonik"). Yang tetap dilarang: melewati ujung rencana.
    assert int(aktual_setelah_ref or 0) > 0, "aktual 9 Okt → 5 Nov wajib terisi"
    assert int(aktual_lewat_ujung or 0) == 0, "aktual tidak boleh melewati ujung rencana"


def test_purge_hanya_menghapus_baris_demo(restore_demo):
    asyncio.run(_generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12))
    before_seed = {
        table: _counts()[f"{table}:seed"] for table in TABLES
    }
    result = asyncio.run(purge_demo_rows())
    after = _counts()
    assert result["total"] > 0
    for table in TABLES:
        assert after[f"{table}:demo"] == 0
        assert after[f"{table}:seed"] == before_seed[table]


def test_generated_at_terisi_demo_kosong_untuk_kanonik(restore_demo):
    asyncio.run(_generate(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12))
    with _engine().connect() as conn:
        for table in TABLES:
            kotor = conn.execute(
                text(
                    f"SELECT count(*) FROM {table} WHERE origin = 'demo' "
                    "AND generated_at IS NULL"
                )
            ).scalar()
            seed_kotor = conn.execute(
                text(
                    f"SELECT count(*) FROM {table} WHERE origin = 'seed' "
                    "AND generated_at IS NOT NULL"
                )
            ).scalar()
    assert int(kotor or 0) == 0, f"{table}: baris demo wajib punya generated_at"
    assert int(seed_kotor or 0) == 0, f"{table}: baris kanonik tidak punya generated_at"


def test_preview_tidak_menulis(restore_demo):
    before = _counts()
    preview = asyncio.run(
        preview_timeseries(start=DEFAULT_START, end=DEFAULT_END, interval_hours=12)
    )
    assert _counts() == before
    assert preview["writes"] is False
    assert preview["counts"]["supply"]["planned"] > 0
