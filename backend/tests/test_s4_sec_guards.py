"""S4-00 O-SEC-1/O-SEC-2 (TDD): auth + location scope guards entry point S4.

Kontrak plan §11/§14 (approved):
- POST /decisions, GET /decisions/{id}, POST /actions/repropose,
  POST /demo/seed wajib 401 tanpa JWT — sebelum lookup/mutasi apa pun.
- bgn_monitor read-only: 403 pada semua mutasi; boleh membaca semua lokasi.
- SPPG terikat lokasi: hanya boleh membuat keputusan dengan TARGET lokasi
  miliknya (source boleh lintas daerah — itu inti regional balancing).
- REVISI S4-05 (Ruling Owner 2026-10-08): VERIFIER_ROLES
  (sppg_head/sppg_nutritionist) selaku approver matriks AND boleh MEMBACA
  decision/summary lintas lokasi — selaras write path /actions/approve;
  role SPPG lain tetap 403 (lihat _assert_decision_readable).

RED pada HEAD 7089bcf: keempat endpoint masih tanpa guard / tanpa scope.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.test_actions import (
    RECOMMENDATION,
    _cleanup,
    _drop_user,
    _login,
    _mk_user,
)

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


def _rec(target: str) -> dict:
    """RECOMMENDATION dengan destination berbeda (source tetap Cianjur)."""
    return {
        "candidate": {
            **RECOMMENDATION["candidate"],
            "destination_location": target,
        },
        "safe_delivered_cost": RECOMMENDATION["safe_delivered_cost"],
        "cost_breakdown": RECOMMENDATION.get("cost_breakdown"),
    }


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _count_recent_target_decisions(target_name: str) -> int:
    """Readback no-side-effect: decision target `target_name` yang baru."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT count(*) FROM decisions d "
                    "JOIN locations l ON l.id = d.target_location_id "
                    "WHERE l.name = :n "
                    "AND d.created_at > now() - interval '2 minutes'"
                ),
                {"n": target_name},
            ).scalar_one()
    finally:
        engine.dispose()


# ---------------------------------------------------------------- 401 tanpa JWT
def test_post_decisions_unauth_401(client):
    resp = client.post("/decisions", json={"recommendation": RECOMMENDATION})
    assert resp.status_code == 401, resp.text


def test_get_decision_detail_unauth_401_sebelum_lookup(client):
    """Auth-first: id tak dikenal tanpa token → 401, bukan 404."""
    resp = client.get(f"/decisions/{uuid.uuid4()}")
    assert resp.status_code == 401, resp.text


def test_repropose_unauth_401(client):
    resp = client.post(
        "/actions/repropose", json={"decision_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 401, resp.text


def test_demo_seed_unauth_401(client):
    resp = client.post("/demo/seed", json={})
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------- monitor read-only
def test_monitor_cannot_mutate_decisions_repropose_seed(client):
    """bgn_monitor read-only: 403 pada POST /decisions, repropose, demo seed."""
    mon = _mk_user("bgn_monitor")
    try:
        for method, url, payload in (
            ("POST", "/decisions", {"recommendation": RECOMMENDATION}),
            (
                "POST",
                "/actions/repropose",
                {"decision_id": str(uuid.uuid4())},
            ),
            ("POST", "/demo/seed", {"force": False}),
        ):
            resp = client.request(
                method,
                url,
                json=payload,
                headers=_login(client, mon),
            )
            assert resp.status_code == 403, (
                f"{method} {url} -> {resp.status_code}: {resp.text[:200]}"
            )
    finally:
        _drop_user(mon["email"])


# ---------------------------------------------------------------- scope lokasi
def test_sppg_cannot_create_decision_targeting_foreign_location(client):
    """SPPG Bogor tidak boleh membuat decision target Jakarta (403).

    Readback no-side-effect: tidak ada decision Jakarta baru setelah 403.
    """
    user = _mk_user("sppg_head", "Bogor")
    try:
        before = _count_recent_target_decisions("Jakarta")
        resp = client.post(
            "/decisions",
            json={"recommendation": _rec("Jakarta")},
            headers=_login(client, user),
        )
        assert resp.status_code == 403, resp.text
        after = _count_recent_target_decisions("Jakarta")
        assert after == before, "403 harus tanpa side effect"
    finally:
        _drop_user(user["email"])


def test_sppg_can_create_decision_targeting_own_location(client):
    """SPPG Jakarta boleh membuat decision target Jakarta (201) — Happy path
    kontrak OpsConsole (create → propose → approve)."""
    user = _mk_user("sppg_head", "Jakarta")
    did = None
    try:
        resp = client.post(
            "/decisions",
            json={"recommendation": _rec("Jakarta")},
            headers=_login(client, user),
        )
        assert resp.status_code == 201, resp.text
        did = resp.json()["decision_id"]
    finally:
        if did:
            _cleanup(did, [])
        _drop_user(user["email"])


def test_sppg_foreign_decision_detail_read_allowed_by_ruling(client):
    """REVISI S4-05 (Ruling Owner 2026-10-08): approver VERIFIER_ROLES
    lintas lokasi BOLEH membaca detail decision (selaras write path
    /actions/approve yang tidak membatasi lokasi).

    Test lama mem-pin 403 untuk sppg_head Bogor membaca decision
    Jakarta — kontrak pra-ruling. Matriks AND butuh approver ke-2 lintas
    lokasi; tanpa baca, approver sah jadi buta di UI (temuan rehearsal
    p10: approve 200 vs summary/detail 403). Role selain VERIFIER_ROLES
    dan bgn_monitor tetap terikat O-SEC-2 (helper _assert_decision_readable).
    """
    owner = _mk_user("sppg_head", "Jakarta")
    foreign = _mk_user("sppg_head", "Bogor")
    did = None
    try:
        resp = client.post(
            "/decisions",
            json={"recommendation": _rec("Jakarta")},
            headers=_login(client, owner),
        )
        assert resp.status_code == 201, resp.text
        did = resp.json()["decision_id"]
        resp = client.get(f"/decisions/{did}", headers=_login(client, foreign))
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision_id"] == did
    finally:
        if did:
            _cleanup(did, [])
        _drop_user(owner["email"])
        _drop_user(foreign["email"])


def test_monitor_reads_any_location_but_no_mutation(client):
    """Monitor lintas lokasi: baca detail decision Jakarta OK (read-only role)."""
    owner = _mk_user("sppg_head", "Jakarta")
    mon = _mk_user("bgn_monitor")
    did = None
    try:
        resp = client.post(
            "/decisions",
            json={"recommendation": _rec("Jakarta")},
            headers=_login(client, owner),
        )
        assert resp.status_code == 201, resp.text
        did = resp.json()["decision_id"]
        resp = client.get(f"/decisions/{did}", headers=_login(client, mon))
        assert resp.status_code == 200, resp.text
    finally:
        if did:
            _cleanup(did, [])
        _drop_user(owner["email"])
        _drop_user(mon["email"])
