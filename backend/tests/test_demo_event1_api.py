"""Endpoint Event 1 penuh (panel Demo Control): `POST /demo/event1`.

Konteks kenapa endpoint ini ada: sebelum 16 Okt 2026 `run_event1` hanya
dipanggil berkas tes, sehingga langkah SUPERVISE (narasi supervisor) tidak
pernah muncul di `agent_traces` pada aplikasi yang dilihat juri (terukur:
SUPERVISE 1 baris vs DETECT 83 baris). Endpoint ini membuka jalur itu dari UI.

Yang dibuktikan di sini adalah KONTRAK ENDPOINT-nya (guard peran + cakupan
lokasi + pemetaan galat + penerusan parameter). Orkestratornya sendiri sudah
dipaku `tests/test_event1_supervisor_flow.py`; jadi di sini `run_event1`
diganti fake supaya tes tidak memanggil provider nyata dan tidak menulis
keputusan ke DB demo yang dipakai presentasi.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.test_actions import _drop_user, _login, _mk_user

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def pemakai():
    """Kepala SPPG Jakarta + token; dibersihkan sesudah tes."""
    dibuat: list[str] = []

    def _buat(role: str, lokasi: str | None):
        user = _mk_user(role, lokasi)
        dibuat.append(user["email"])
        return user

    yield _buat
    for email in dibuat:
        _drop_user(email)


def _fake_outcome(**kwargs) -> dict:
    """Bentuk balasan orkestrator yang cukup untuk menguji penerusan."""
    return {
        "decision_id": "00000000-0000-0000-0000-000000000001",
        "detect": {"commodity": kwargs.get("commodity")},
        "verifier": {"verdict": "PASS"},
        "forecast": {"forecast_qty_kg": 360.5},
        "supervisor": {
            "status": "narrated",
            "summary": "ringkasan uji",
            "provider": "primary:sap_ai_core",
            "fallback_used": False,
            "attempts": [],
        },
        "recommendations": [],
        "decision_snapshot": {"status": "proposed", "approved": False},
        "kpi": {"candidates_total": 0},
        "trace_steps": ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE",
                        "DECIDE", "SUPERVISE"],
    }


def _jumlah_keputusan() -> int:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(conn.execute(text("SELECT count(*) FROM decisions")).scalar() or 0)
    finally:
        engine.dispose()


# --- guard -----------------------------------------------------------------


def test_tanpa_token_ditolak_401(client):
    resp = client.post(
        "/demo/event1", json={"commodity": "telur", "target_location": "Jakarta"}
    )
    assert resp.status_code == 401


def test_bgn_monitor_read_only_ditolak_403(client, monitor_headers):
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta"},
        headers=monitor_headers,
    )
    assert resp.status_code == 403


def test_kepala_sppg_lokasi_lain_ditolak_403(client, pemakai):
    """Cakupan ditegakkan atas lokasi TUJUAN (Ruling 2026-10-14)."""
    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Cianjur"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "cakupan" in resp.json()["detail"].lower()


def test_lokasi_tujuan_tidak_dikenal_404(client, pemakai):
    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Narnia"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_ttl_di_luar_batas_422(client, pemakai):
    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta", "ttl_minutes": 0},
        headers=headers,
    )
    assert resp.status_code == 422


# --- jalur sukses & pemetaan galat ----------------------------------------


def test_sukses_meneruskan_hasil_orkestrator_dan_parameter(client, monkeypatch, pemakai):
    dipanggil: dict = {}

    def _fake(commodity, target_location, **kwargs):
        dipanggil.update(commodity=commodity, target_location=target_location, **kwargs)
        return _fake_outcome(commodity=commodity)

    monkeypatch.setattr("app.api.demo.run_event1", _fake)
    before = _jumlah_keputusan()

    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta", "ttl_minutes": 45},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Parameter diteruskan apa adanya (tanpa nilai karangan di endpoint).
    assert dipanggil == {
        "commodity": "telur",
        "target_location": "Jakarta",
        "ttl_minutes": 45,
    }
    # Blok supervisor ikut terkirim ke UI — itu inti endpoint ini.
    assert body["supervisor"]["status"] == "narrated"
    assert body["supervisor"]["provider"] == "primary:sap_ai_core"
    assert "SUPERVISE" in body["trace_steps"]
    # Endpoint tidak menulis apa pun sendiri: fake tidak menyentuh DB.
    assert _jumlah_keputusan() == before


def test_kandidat_kosong_dijawab_409_bukan_500(client, monkeypatch, pemakai):
    def _fake(commodity, target_location, **kwargs):
        raise ValueError(
            "tidak ada kandidat eligible untuk Event 1 "
            f"({commodity} -> {target_location}); decision tidak dibuat"
        )

    monkeypatch.setattr("app.api.demo.run_event1", _fake)

    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "kandidat eligible" in resp.json()["detail"]


# --- review 7 agen (P4) ----------------------------------------------------


def test_agent_review_off_mengembalikan_disabled_tanpa_panggilan(
    client, monkeypatch, pemakai
):
    panggilan: list = []

    def _fake_review(*args, **kwargs):
        panggilan.append((args, kwargs))
        raise AssertionError("review_decision tidak boleh dipanggil saat flag mati")

    monkeypatch.setattr(
        "app.api.demo.run_event1",
        lambda commodity, target_location, **kwargs: _fake_outcome(
            commodity=commodity
        ),
    )
    monkeypatch.setattr("app.api.demo.review_decision", _fake_review)
    monkeypatch.setattr("app.api.demo.settings.multi_agent_review", False)

    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta"},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["agent_review"] == {"status": "disabled", "run_id": None}
    assert panggilan == []


def test_agent_review_on_runtime_mati_tetap_201(
    client, monkeypatch, pemakai
):
    from app.services.agent_review_client import AgentReviewResult

    dipanggil: dict = {}

    def _fake_review(decision_id, *, timeout_seconds):
        dipanggil.update(
            decision_id=decision_id, timeout_seconds=timeout_seconds
        )
        return AgentReviewResult(status="unavailable", error="ARN kosong")

    monkeypatch.setattr(
        "app.api.demo.run_event1",
        lambda commodity, target_location, **kwargs: _fake_outcome(
            commodity=commodity
        ),
    )
    monkeypatch.setattr("app.api.demo.review_decision", _fake_review)
    monkeypatch.setattr("app.api.demo.settings.multi_agent_review", True)
    monkeypatch.setattr("app.api.demo.settings.agent_review_timeout_seconds", 75)
    before = _jumlah_keputusan()

    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta"},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["agent_review"]["status"] == "unavailable"
    assert resp.json()["supervisor"]["status"] == "narrated"
    assert dipanggil == {
        "decision_id": "00000000-0000-0000-0000-000000000001",
        "timeout_seconds": 45.0,
    }
    assert _jumlah_keputusan() == before


def test_agent_review_on_completed_membawa_run_id(
    client, monkeypatch, pemakai
):
    from app.services.agent_review_client import AgentReviewResult

    monkeypatch.setattr(
        "app.api.demo.run_event1",
        lambda commodity, target_location, **kwargs: _fake_outcome(
            commodity=commodity
        ),
    )
    monkeypatch.setattr(
        "app.api.demo.review_decision",
        lambda decision_id, *, timeout_seconds: AgentReviewResult(
            status="completed",
            run_id="run-abc",
            payload={"findings": [{} for _ in range(7)]},
        ),
    )
    monkeypatch.setattr("app.api.demo.settings.multi_agent_review", True)

    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta"},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["agent_review"] == {
        "status": "completed",
        "run_id": "run-abc",
    }
