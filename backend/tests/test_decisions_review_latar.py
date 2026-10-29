"""Setiap keputusan dari `POST /decisions` ikut direview agent (bila dinyalakan).

Latar: review 7 worker dulu hanya terpasang di `POST /demo/event1`. Keputusan
yang lahir dari konsol operator (`createDecision` → `POST /decisions`) tidak
pernah direview sama sekali, jadi panel Agent Log kosong untuk keputusan itu.

Kontrak yang dikunci:
1. `MULTI_AGENT_REVIEW=false` → tidak ada penjadwalan, respons bilang `disabled`.
2. `MULTI_AGENT_REVIEW=true`  → review dijadwalkan SETELAH respons, dengan
   `decision_id` keputusan yang baru dibuat; 201 tidak menunggu model.
3. Penjadwalan tidak boleh menggagalkan pembuatan keputusan.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import agent_review_hook as hook
from tests.test_actions import RECOMMENDATION, _cleanup, _drop_user, _login, _mk_user


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _rekam_tugas_latar(monkeypatch) -> list[tuple]:
    """Ganti tugas latar dengan perekam: tidak ada model, tidak ada DB kedua."""
    rekaman: list[tuple] = []

    async def _rekam(decision_id: str, user) -> None:  # noqa: ANN001 - meniru signature
        rekaman.append((decision_id, getattr(user, "email", None)))

    monkeypatch.setattr(hook, "_review_latar", _rekam)
    return rekaman


def test_review_tidak_berjalan_saat_flag_mati(client, monkeypatch):
    monkeypatch.setattr(settings, "multi_agent_review", False)
    rekaman = _rekam_tugas_latar(monkeypatch)
    user = _mk_user("sppg_head", "Jakarta")
    decision_id = None
    try:
        headers = _login(client, user)
        resp = client.post(
            "/decisions", json={"recommendation": RECOMMENDATION}, headers=headers
        )
        assert resp.status_code == 201, resp.text
        badan = resp.json()
        decision_id = badan["decision_id"]
        assert badan["agent_review"]["status"] == "disabled"
        assert rekaman == [], "tidak boleh ada review saat flag mati"
    finally:
        _cleanup(decision_id, [user["email"]])
        _drop_user(user["email"])


def test_review_berjalan_untuk_keputusan_baru(client, monkeypatch):
    monkeypatch.setattr(settings, "multi_agent_review", True)
    rekaman = _rekam_tugas_latar(monkeypatch)
    user = _mk_user("sppg_head", "Jakarta")
    decision_id = None
    try:
        headers = _login(client, user)
        resp = client.post(
            "/decisions", json={"recommendation": RECOMMENDATION}, headers=headers
        )
        assert resp.status_code == 201, resp.text
        badan = resp.json()
        decision_id = badan["decision_id"]

        # 201 menjawab "queued" — bukan menunggu model selesai.
        assert badan["agent_review"]["status"] == "queued"
        assert len(rekaman) == 1, "review tidak dijadwalkan"
        assert rekaman[0][0] == decision_id, "yang dijadwalkan bukan keputusan baru"
        assert rekaman[0][1] == user["email"], "identitas pemanggil harus ikut"
    finally:
        _cleanup(decision_id, [user["email"]])
        _drop_user(user["email"])


def test_review_latar_menelan_kegagalan_model(monkeypatch):
    """Kegagalan model di latar tidak boleh menjatuhkan proses atau keputusan."""
    import asyncio
    import uuid

    from app.services import agent_review_hook as hook

    async def _meledak(*_a, **_k):
        raise RuntimeError("model mati")

    monkeypatch.setattr(hook, "jalankan_agent_review", _meledak)

    # Tidak boleh melempar ke pemanggil (FastAPI akan mencatatnya sebagai error
    # di luar respons, dan jejak keputusan tidak boleh ikut hilang).
    asyncio.run(hook._review_latar(str(uuid.uuid4()), None))
