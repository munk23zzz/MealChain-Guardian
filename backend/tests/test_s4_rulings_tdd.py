"""S4-05 ruling p10 (arah Owner 2026-10-08, "a lalu b") — TDD RED dulu.

Dua temuan rehearsal dibuat kontrak baru via ruling eksplisit:

1. Ruling A — scope baca approval-summary selaras write path.
   `POST /actions/approve` memakai VERIFIER_ROLES tanpa cek lokasi, tapi
   `GET /decisions/{id}/approval-summary` masih 403 untuk VERIFIER_ROLES
   lintas lokasi → approver ke-2 sah secara API tapi buta di UI.
   Ruling: VERIFIER_ROLES (sppg_head/sppg_nutritionist) boleh MEMBACA
   summary keputusan di lokasi mana pun; bgn_monitor read-only semua
   lokasi (tetap); O-SEC-2 untuk role lain tidak berubah.

2. Ruling B — filter komoditas pada analisis OpsConsole.
   Panel memilih lokasi+komoditas, tapi `POST /balance/analyze` selalu
   memakai facts GLOBAL → proposal selalu kandidat rank-1 lintas
   komoditas. Ruling: `build_recommendations` menerima `commodity`
   (opsional) untuk memfilter facts; `POST /balance/analyze` meneruskan
   komoditas panel; `POST /balance/recommend` + orchestrator Event 1/3
   TIDAK berubah (deterministik global, dipakai event services).
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

NOW = datetime.now(timezone.utc)


# ----------------------------- helpers DB ---------------------------------
def _db_all(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), params or {}).fetchall()
            conn.commit()
            return rows
    finally:
        engine.dispose()


def _db_exec(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


def _db_exec_returning(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            row = conn.execute(text(query), params or {}).fetchone()
            return row[0] if row else None
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# Password demo statis (seed_data.py DEMO_USERS; bukan secret produksi).
def _head_user(client: TestClient) -> dict:
    return _login(client, "sppg.head@demo.local", "Demo#SPPG2026")


def _nut_user(client: TestClient) -> dict:
    return _login(client, "sppg.nutritionist@demo.local", "Demo#Nut2026")


def _jakarta_id() -> str:
    return str(_db_all("SELECT id FROM locations WHERE name='Jakarta'")[0][0])


def _bogor_id() -> str:
    return str(_db_all("SELECT id FROM locations WHERE name='Bogor'")[0][0])


def _mk_decision(
    source_location_id: str,
    target_location_id: str,
    expires_minutes: int = 30,
) -> str:
    """Decision uji target komoditas telur (fixture DB langsung)."""
    did = str(_db_exec_returning(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration) "
        "SELECT :id, 'regional_balance', 'pending_approval', "
        "'supervisor_agent', :src, :tgt, "
        "c.id, 488.88, 16206000.00, now() + make_interval(mins => :m), "
        "'{\"purchase\": \"15720000\"}'::jsonb, 1 "
        "FROM commodities c WHERE c.name='telur' RETURNING id",
        {
            "id": str(uuid.uuid4()),
            "src": source_location_id,
            "tgt": target_location_id,
            "m": expires_minutes,
        },
    ))
    return did


def _cleanup_decision(decision_id: str) -> None:
    _db_exec("DELETE FROM approvals WHERE decision_id = :d", {"d": decision_id})
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": decision_id})


# ============================================================================
# RULING A — scope baca approval-summary selaras write path (VERIFIER_ROLES)
# ============================================================================

def test_ruling_a_nutritionist_baca_summary_lintas_lokasi_200(client):
    """Nutritionist (Bogor) BOLEH membaca summary decision Jakarta."""
    did = _mk_decision(_jakarta_id(), _jakarta_id())
    try:
        resp = client.get(
            f"/decisions/{did}/approval-summary", headers=_nut_user(client)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision_id"] == did
    finally:
        _cleanup_decision(did)


def test_ruling_a_head_baca_summary_lintas_lokasi_200(client):
    """SPPG Head (Jakarta) membaca summary decision Bogor — simetris."""
    did = _mk_decision(_bogor_id(), _bogor_id())
    try:
        resp = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        )
        assert resp.status_code == 200, resp.text
    finally:
        _cleanup_decision(did)


# ============================================================================
# RULING B — filter komoditas pada build_recommendations (opsional)
# ============================================================================

SUPPLY = {
    ("Cianjur", "telur"): 1400,
    ("Jakarta", "telur"): 300,
    ("Bogor", "ayam"): 200,
    ("Jakarta", "ayam"): 0,
}
DEMAND = {
    ("Cianjur", "telur"): 500,
    ("Jakarta", "telur"): 1000,
    ("Bogor", "ayam"): 0,
    ("Jakarta", "ayam"): 15,
}
REFS = {
    ("Cianjur", "telur"): 26500,
    ("Jakarta", "telur"): 30500,
    ("Bogor", "ayam"): 38200,
    ("Jakarta", "ayam"): 41500,
}
QUOTES = {
    ("Cianjur", "telur"): (26200, "11111111-1111-1111-1111-111111111111"),
    ("Bogor", "ayam"): (38500, "22222222-2222-2222-2222-222222222222"),
}
RELIABILITY = {
    "11111111-1111-1111-1111-111111111111": 0.80,
    "22222222-2222-2222-2222-222222222222": 0.80,
}
BATCHES = [
    {
        "batch_id": "b-1",
        "location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": 600,
        "freshness_score": 0.90,
        "freshness_status": "pass",
        "safety_status": "pass",
    },
    {
        "batch_id": "b-2",
        "location": "Bogor",
        "commodity": "ayam",
        "quantity_kg": 200,
        "freshness_score": 0.88,
        "freshness_status": "pass",
        "safety_status": "pass",
    },
]
LOGI = {
    ("Cianjur", "Jakarta"): {
        "distance_km": 120,
        "estimated_time_min": 150.0,
        "feasible": True,
    },
    ("Bogor", "Jakarta"): {
        "distance_km": 50,
        "estimated_time_min": 60.0,
        "feasible": True,
    },
}


def _facts():
    return (
        {k: __import__("decimal").Decimal(str(v)) for k, v in SUPPLY.items()},
        {k: __import__("decimal").Decimal(str(v)) for k, v in DEMAND.items()},
        {k: __import__("decimal").Decimal(str(v)) for k, v in REFS.items()},
        {k: (__import__("decimal").Decimal(str(v[0])), v[1])
         for k, v in QUOTES.items()},
        [
            {**b, "quantity_kg": __import__("decimal").Decimal(str(b["quantity_kg"])),
             "freshness_score": __import__("decimal").Decimal(str(b["freshness_score"]))}
            for b in BATCHES
        ],
        {k: __import__("decimal").Decimal(str(v)) for k, v in RELIABILITY.items()},
    )


AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def test_ruling_b_tanpa_filter_semua_komoditas(client=None):
    """Tanpa argumen commodity: perilaku lama (global) tidak berubah."""
    out = _run(_import_rs().build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    coms = {r["candidate"]["commodity"] for r in out["recommendations"]}
    assert {"telur", "ayam"} <= coms


def test_ruling_b_filter_ayam_hanya_ayam(client=None):
    """commodity='ayam' → hanya kandidat ayam (telur tersaring)."""
    out = _run(_import_rs().build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI, commodity="ayam"
    ))
    recs = out["recommendations"]
    assert recs, "kandidat ayam wajib ada"
    assert all(r["candidate"]["commodity"] == "ayam" for r in recs)


def test_ruling_b_filter_ayam_kandidat_bogor_rank1(client=None):
    """Filter ayam → rank-1 = Bogor→Jakarta (bukan kandidat telur global)."""
    out = _run(_import_rs().build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI, commodity="ayam"
    ))
    top = out["recommendations"][0]
    assert top["candidate"]["commodity"] == "ayam"
    assert top["candidate"]["source_location"] == "Bogor"
    assert top["candidate"]["destination_location"] == "Jakarta"


def test_ruling_b_filter_komoditas_tanpa_data_kosong(client=None):
    """commodity tanpa data → daftar kosong JUJUR, bukan kandidat lain."""
    out = _run(_import_rs().build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI, commodity="wortel"
    ))
    assert out["recommendations"] == []


def _import_rs():
    from app.services import recommendation_service as rs

    return rs
