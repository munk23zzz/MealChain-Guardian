"""Test tool contracts + gateway config (S3-02, TDD).

Carry-over endpoint Sprint 2 yang wajib ada sebelum Gateway registration:
- POST /cost/safe-delivered (SDC standalone, formula Opsi A terkunci)
- POST /balance/analyze (pipeline penuh + summary)
- POST /evidence/fuse (perakitan evidence deterministik, pass-through)

Plus registry tool deterministik (10 nama logical) yang harus map 1:1 ke
route FastAPI aktif, dan artifact gateway_config.json tanpa drift.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent_tools.registry import TOOL_ROUTES, build_gateway_config
from app.main import app

GATEWAY_ARTIFACT = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "agent_tools"
    / "gateway_config.json"
)

EXPECTED_TOOLS = {
    "supply.get",
    "demand.get",
    "freshness.evaluate",
    "safety.evaluate",
    "price.deviation",
    "logistics.estimate",
    "evidence.fuse",
    "cost.safe_delivered",
    "balance.recommend",
    "actions.propose",
}


@pytest.fixture()
def client(auth_headers):
    with TestClient(app) as c:
        c.headers.update(auth_headers)
        yield c


# ---------------------------------------------------------------------------
# /cost/safe-delivered
# ---------------------------------------------------------------------------


def test_safe_delivered_locked_example_freshness_090(client):
    resp = client.post(
        "/cost/safe-delivered",
        json={
            "purchase_cost": "15720000",
            "transport_cost": "21600",
            "handling_cost": "150000",
            "freshness_score": "0.90",
            "safety_status": "pass",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["expected_loss"] == "314400.00"
    assert body["freshness_risk_penalty"] == "0.00"
    assert body["safety_risk_penalty"] == "0.00"
    assert body["total"] == "16206000.00"


def test_safe_delivered_safety_fail_rejected_422(client):
    resp = client.post(
        "/cost/safe-delivered",
        json={
            "purchase_cost": "15720000",
            "transport_cost": "21600",
            "handling_cost": "150000",
            "freshness_score": "0.90",
            "safety_status": "fail",
        },
    )
    assert resp.status_code == 422


def test_safe_delivered_invalid_inputs_422(client):
    resp = client.post(
        "/cost/safe-delivered",
        json={
            "purchase_cost": "0",
            "transport_cost": "21600",
            "handling_cost": "150000",
            "freshness_score": "0.90",
            "safety_status": "pass",
        },
    )
    assert resp.status_code == 422
    resp = client.post(
        "/cost/safe-delivered",
        json={
            "purchase_cost": "1000",
            "transport_cost": "21600",
            "handling_cost": "150000",
            "freshness_score": "1.50",
            "safety_status": "pass",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /balance/analyze
# ---------------------------------------------------------------------------


def test_balance_analyze_full_pipeline_with_summary(client):
    resp = client.post("/balance/analyze")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "recommendations" in body and isinstance(body["recommendations"], list)
    assert len(body["recommendations"]) > 0
    summary = body["summary"]
    assert summary["candidates_total"] == len(body["recommendations"])
    assert summary["eligible"] == sum(
        1 for r in body["recommendations"] if r.get("eligible")
    )
    assert summary["review_required"] == sum(
        1 for r in body["recommendations"] if r.get("review_required")
    )
    first = body["recommendations"][0]
    assert "cost_breakdown" in first
    assert "safe_delivered_cost" in first


# ---------------------------------------------------------------------------
# /evidence/fuse
# ---------------------------------------------------------------------------


def _first_recommendation(client) -> dict:
    resp = client.post("/balance/recommend")
    assert resp.status_code == 200, resp.text
    recs = resp.json()["recommendations"]
    assert recs, "seed harus menghasilkan minimal 1 rekomendasi"
    return recs[0]


def test_evidence_fuse_assembles_from_recommendation(client):
    rec = _first_recommendation(client)
    resp = client.post("/evidence/fuse", json={"recommendation": rec})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    expected_batches = sorted(set(rec["evidence"]["batch_ids"]))
    assert body["batch_ids"] == expected_batches
    assert body["price_sources"] == rec["evidence"]["price_sources"]
    assert body["price_anomaly"] == rec["price_anomaly"]
    assert body["cost_breakdown"] == rec["cost_breakdown"]
    assert body["source_count"] >= 1


def test_evidence_fuse_rejects_empty_recommendation(client):
    resp = client.post("/evidence/fuse", json={"recommendation": {}})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Registry + gateway artifact
# ---------------------------------------------------------------------------


def test_registry_has_exactly_ten_tools():
    assert set(TOOL_ROUTES) == EXPECTED_TOOLS


def test_registry_maps_to_live_fastapi_routes():
    openapi = app.openapi()
    live = {
        (method.upper(), path)
        for path, methods in openapi["paths"].items()
        for method in methods
    }
    for name, spec in TOOL_ROUTES.items():
        assert (spec["method"], spec["path"]) in live, (
            f"tool {name} → {spec['method']} {spec['path']} tidak ada di app"
        )


def test_gateway_artifact_matches_registry_no_drift():
    assert GATEWAY_ARTIFACT.exists(), "gateway_config.json wajib ada"
    on_disk = json.loads(GATEWAY_ARTIFACT.read_text(encoding="utf-8"))
    assert on_disk == build_gateway_config()
    names = {t["name"] for t in on_disk["tools"]}
    assert names == EXPECTED_TOOLS
    # Tidak ada secret/URL absolut — target memakai placeholder env.
    raw = GATEWAY_ARTIFACT.read_text(encoding="utf-8")
    assert "${BACKEND_BASE_URL}" in raw
    assert "AKIA" not in raw and "Bearer" not in raw
