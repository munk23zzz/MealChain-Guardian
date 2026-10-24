"""Batch A+B audit 24 Okt 2026: bukti untuk kasus skrip, dan draf usang.

Dua aturan yang dikunci di sini:

1. Setiap keputusan kasus skrip (`demo_case` terisi) punya minimal satu baris
   bukti — termasuk versi yang berakhir `rejected`/`verifier_flagged`, karena
   bukti itulah alasan penolakannya.
2. Pembersih draf hanya membuang `proposed` yang benar-benar tak tersentuh:
   tanpa approval, tanpa PO, tanpa bukti. Draf yang sudah punya jejak apa pun
   tidak boleh hilang.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio

try:
    from sqlalchemy import text

    from app.api.demo import _buang_draf_usang
    from app.core.config import settings
    from app.db import create_engine, create_session_maker
except Exception:  # pragma: no cover - guard impor
    text = None


def _url() -> str:
    return settings.database_url.replace("+asyncpg", "+psycopg")


@pytest.mark.skipif(text is None, reason="app/sqlalchemy tidak tersedia")
async def test_kasus_skrip_punya_bukti_termasuk_yang_ditolak():
    eng = create_engine(_url())
    async with eng.connect() as conn:
        baris = (
            await conn.execute(
                text(
                    """
                    SELECT left(d.id::text, 8) AS id, d.decision_type, d.status, d.demo_case
                    FROM decisions d
                    WHERE d.demo_case IS NOT NULL
                      AND d.created_at > now() - interval '2 days'
                      AND NOT EXISTS (
                        SELECT 1 FROM decision_evidence e WHERE e.decision_id = d.id
                      )
                    ORDER BY d.created_at DESC
                    LIMIT 10
                    """
                )
            )
        ).fetchall()
    await eng.dispose()
    assert baris == [], f"kasus skrip tanpa bukti: {baris}"


@pytest.mark.skipif(text is None, reason="app/sqlalchemy tidak tersedia")
async def test_pembersih_draf_hanya_membuang_yang_tak_tersentuh():
    eng = create_engine(_url())
    maker = create_session_maker(eng)
    sekarang = datetime.now(timezone.utc)
    tua = sekarang - timedelta(days=3)
    # Tiga draf: (a) tua & tak tersentuh → dibuang, (b) tua & punya approval → tetap,
    # (c) baru → tetap.
    id_a, id_b, id_c = (uuid.uuid4() for _ in range(3))
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO decisions (id, decision_type, status, proposed_by, source_location_id,
                    target_location_id, quantity_kg, created_at, expires_at, origin, generated_at)
                SELECT :id, 'regional_balance', 'proposed', 'uji-draf', l1.id, l1.id, 10, :dibuat,
                       :dibuat + interval '1 hour', 'demo', :dibuat
                FROM locations l1 ORDER BY l1.name LIMIT 1
                """
            ),
            {"id": id_a, "dibuat": tua},
        )
        await s.execute(
            text(
                """
                INSERT INTO decisions (id, decision_type, status, proposed_by, source_location_id,
                    target_location_id, quantity_kg, created_at, expires_at, origin, generated_at)
                SELECT :id, 'regional_balance', 'proposed', 'uji-draf', l1.id, l1.id, 10, :dibuat,
                       :dibuat + interval '1 hour', 'demo', :dibuat
                FROM locations l1 ORDER BY l1.name LIMIT 1
                """
            ),
            {"id": id_b, "dibuat": tua},
        )
        await s.execute(
            text(
                """
                INSERT INTO decisions (id, decision_type, status, proposed_by, source_location_id,
                    target_location_id, quantity_kg, created_at, expires_at, origin, generated_at)
                SELECT :id, 'regional_balance', 'proposed', 'uji-draf', l1.id, l1.id, 10, :dibuat,
                       :dibuat + interval '1 hour', 'demo', :dibuat
                FROM locations l1 ORDER BY l1.name LIMIT 1
                """
            ),
            {"id": id_c, "dibuat": sekarang - timedelta(minutes=5)},
        )
        await s.execute(
            text(
                """
                INSERT INTO decision_evidence (id, decision_id, evidence_type, payload, recorded_at)
                VALUES (:id, :keputusan, 'human_inspection', '{"uji": true}', :kini)
                """
            ),
            {"id": uuid.uuid4(), "keputusan": id_b, "kini": sekarang},
        )
        await s.commit()
        hasil = await _buang_draf_usang(s, sekarang)
        await s.commit()
        sisa = set(
            (
                await s.execute(
                    text("SELECT id FROM decisions WHERE id = ANY(:ids)"),
                    {"ids": [id_a, id_b, id_c]},
                )
            )
            .scalars()
            .all()
        )
        await s.execute(
            text("DELETE FROM decisions WHERE id = ANY(:ids)"), {"ids": [id_b, id_c]}
        )
        await s.commit()
    await eng.dispose()

    assert hasil["draf_usang_dihapus"] >= 1
    assert id_a not in sisa, "draf tua tanpa jejak seharusnya dibuang"
    assert id_b in sisa, "draf yang punya bukti tidak boleh dibuang"
    assert id_c in sisa, "draf baru tidak boleh dibuang"
