"""Test seed akun demo (S3-01 + keputusan produk 3A 18 Okt 2026).

`ensure_demo_users()` idempoten: memastikan akun demo ada dengan role dan scope
lokasi yang benar. Sejak 18 Okt setiap kota demo (Jakarta, Bandung, Surabaya)
punya pasangan approver SENDIRI — tanpa itu keputusan bertarget kota lain
mustahil di-approve karena scope backend menolak (403).
"""

from sqlalchemy import create_engine, text

from app.seed.seed_data import DEMO_USERS, ensure_demo_users

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

KOTA_APPROVER = ("Jakarta", "Bandung", "Surabaya")


def test_demo_users_constant_menutup_tiga_role_dan_tiga_kota():
    roles = {u["role"] for u in DEMO_USERS}
    assert roles == {"sppg_head", "sppg_nutritionist", "bgn_monitor"}
    for kota in KOTA_APPROVER:
        pasangan = {u["role"] for u in DEMO_USERS if u["location"] == kota}
        assert pasangan == {"sppg_head", "sppg_nutritionist"}, (kota, pasangan)
    monitor = [u for u in DEMO_USERS if u["role"] == "bgn_monitor"]
    assert [u["location"] for u in monitor] == [None]


def test_ensure_demo_users_idempotent_and_scoped():
    ensure_demo_users()
    ensure_demo_users()  # panggil dua kali — tetap 1 set akun

    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT u.role, l.name AS location_name, u.email "
                    "FROM users u LEFT JOIN locations l ON l.id = u.location_id "
                    "WHERE u.email LIKE '%@demo.local'"
                )
            ).mappings().all()
        by_role = {(r["role"], r["location_name"]) for r in rows}
        for kota in KOTA_APPROVER:
            assert ("sppg_head", kota) in by_role, kota
            assert ("sppg_nutritionist", kota) in by_role, kota
        assert ("bgn_monitor", None) in by_role
        # idempoten: tidak ada duplikat
        assert len(rows) == len(DEMO_USERS), rows
    finally:
        engine.dispose()
