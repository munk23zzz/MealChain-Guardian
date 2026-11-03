"""GET /waste/summary — jawaban untuk baris "Komposter / bank pangan".

Sebelum ini panel menulis "—" karena tidak ada sumbernya. Tes ini mengunci
kontrak yang membuat angkanya bisa dipercaya:

1. `recorded = diverted + unassigned` (tidak ada kg yang hilang/berlipat);
2. limbah yang PUNYA mitra tidak dicampur dengan yang DIBUANG (dua keadaan
   berbeda, keduanya jujur);
3. cakupan peran ditegakkan: SPPG hanya lokasi sendiri, BGN seluruh lokasi.
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.main import app
from app.seed.demo_activity import seed_demo_completed_decisions
from app.seed.seed_data import DEMO_USERS


def _token(client: TestClient, role: str) -> dict[str, str]:
    user = next(u for u in DEMO_USERS if u["role"] == role)
    tok = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


async def _semai() -> None:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as s:
            await seed_demo_completed_decisions(s, datetime.now(UTC))
            await s.commit()
    finally:
        await engine.dispose()


def test_ringkasan_limbah_konsisten_dan_memisahkan_mitra() -> None:
    import asyncio

    asyncio.run(_semai())
    with TestClient(app) as c:
        badan = c.get("/waste/summary", params={"days": 2}, headers=_token(c, "sppg_head")).json()

    tercatat = badan["recorded"]
    dialihkan = badan["diverted"]
    tanpa_mitra = badan["unassigned"]

    assert tercatat["available"] is True
    assert tercatat["events"] >= 2
    assert round(dialihkan["kg"] + tanpa_mitra["kg"], 2) == tercatat["kg"]
    assert dialihkan["kg"] > 0, "satu kejadian demo dialihkan ke mitra"
    assert tanpa_mitra["kg"] > 0, "satu kejadian demo dibuang tanpa mitra"

    mitra = {m["name"]: m for m in badan["partners"]}
    assert "Bank Sampah Melati" in mitra
    assert mitra["Bank Sampah Melati"]["kg"] == dialihkan["kg"]
    assert mitra["Bank Sampah Melati"]["events"] == dialihkan["events"]


def test_bgn_melihat_lebih_banyak_lokasi_daripada_sppg() -> None:
    with TestClient(app) as c:
        sppg = c.get("/waste/summary", params={"days": 2}, headers=_token(c, "sppg_head")).json()
        bgn = c.get("/waste/summary", params={"days": 2}, headers=_token(c, "bgn_monitor")).json()

    assert sppg["scope"]["location_id"] is not None
    assert bgn["scope"]["location_id"] is None
    assert bgn["recorded"]["kg"] >= sppg["recorded"]["kg"]
