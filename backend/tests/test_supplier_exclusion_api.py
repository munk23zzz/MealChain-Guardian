"""Real PostgreSQL + HTTP administrative lifecycle, isolated rollback fixture."""

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.api.auth import get_current_user
from app.main import app
from app.models import User
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL


@pytest.fixture(autouse=True)
def _verdict_konsisten():
    """Kunci verdict provider agar alur administratif deterministik.


    Sejak audit M1 (18 Okt 2026) approve mensyaratkan verdict hasil audit, dan
    provider nyata bisa menjawab UNAVAILABLE. Tes ini mengukur pagar siklus
    administratif (DUA approver), jadi verdict-nya dikunci FLAGGED — CONSISTENT
    akan menurunkan syarat menjadi satu approval dan mengubah arti tes.
    """
    def _chain():
        return [
            (
                "test_provider",
                lambda prompt: json.dumps({"verdict": "FLAGGED", "reason": "uji"}),
                "test",
            )
        ]

    app.dependency_overrides[get_verifier_chain] = _chain
    yield
    app.dependency_overrides.pop(get_verifier_chain, None)


@pytest.fixture
def scenario():
    engine = create_engine(DSN_SYNC)
    ids = {k: uuid.uuid4() for k in ("supplier", "batch", "head", "nutritionist", "monitor")}
    with engine.begin() as conn:
        ids["scope"] = conn.execute(
            text("SELECT id FROM locations WHERE name='Jakarta'")
        ).scalar_one()
        ids["source"] = conn.execute(
            text("SELECT id FROM locations WHERE name='Bogor'")
        ).scalar_one()
        ids["commodity"] = conn.execute(
            text("SELECT id FROM commodities WHERE name='telur'")
        ).scalar_one()
        conn.execute(
            text("INSERT INTO suppliers (id,name,location_id) VALUES (:id,'Exclusion test',:loc)"),
            {"id": ids["supplier"], "loc": ids["source"]},
        )
        conn.execute(
            text(
                "INSERT INTO batches (id,commodity_id,location_id,supplier_id,"
                "quantity_kg,harvested_at,safety_status) VALUES "
                "(:id,:com,:loc,:sup,100,:at,'fail')"
            ),
            {
                "id": ids["batch"],
                "com": ids["commodity"],
                "loc": ids["source"],
                "sup": ids["supplier"],
                "at": datetime.now(timezone.utc),
            },
        )
        for name, role in (
            ("head", "sppg_head"),
            ("nutritionist", "sppg_nutritionist"),
            ("monitor", "bgn_monitor"),
        ):
            conn.execute(
                text(
                    "INSERT INTO users(id,name,email,password_hash,role,location_id) "
                    "VALUES (:id,:name,:email,'unused',:role,:loc)"
                ),
                {
                    "id": ids[name],
                    "name": name,
                    "email": f"{ids[name]}@test.local",
                    "role": role,
                    "loc": None if name == "monitor" else ids["scope"],
                },
            )

    def actor(name="head", location=None):
        app.dependency_overrides[get_current_user] = lambda: User(
            id=ids[name],
            role={
                "head": "sppg_head",
                "nutritionist": "sppg_nutritionist",
                "monitor": "bgn_monitor",
            }[name],
            location_id=location or ids["scope"],
        )

    actor()
    with TestClient(app) as client:
        yield client, ids, engine, actor
    app.dependency_overrides.pop(get_current_user, None)
    with engine.begin() as conn:
        # Decisions created by this fixture are exclusively actor-owned.
        conn.execute(
            text("DELETE FROM supplier_exclusions WHERE supplier_id=:s"), {"s": ids["supplier"]}
        )
        conn.execute(
            text("DELETE FROM decisions WHERE proposed_by IN (:h,:n)"),
            {"h": str(ids["head"]), "n": str(ids["nutritionist"])},
        )
        conn.execute(text("DELETE FROM batches WHERE id=:b"), {"b": ids["batch"]})
        conn.execute(text("DELETE FROM suppliers WHERE id=:s"), {"s": ids["supplier"]})
        conn.execute(
            text("DELETE FROM users WHERE id IN (:h,:n,:m)"),
            {"h": ids["head"], "n": ids["nutritionist"], "m": ids["monitor"]},
        )
    engine.dispose()


def body(ids):
    return {
        "supplier_id": str(ids["supplier"]),
        "scope_location_id": str(ids["scope"]),
        "reason": "Measured excursion",
        "evidence_refs": [{"type": "batch", "id": str(ids["batch"])}],
    }


def test_proposal_preserves_fail_and_creates_null_quantity_decision(scenario):
    client, ids, engine, _ = scenario
    response = client.post("/supplier-exclusions/proposals", json=body(ids))
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["status"] == "proposed"
    with engine.connect() as conn:
        decision = conn.execute(
            text("SELECT quantity_kg,safe_delivered_cost,verified_by FROM decisions WHERE id=:d"),
            {"d": row["source_decision_id"]},
        ).one()
        assert decision == (None, None, None)
        assert (
            conn.execute(
                text("SELECT safety_status FROM batches WHERE id=:b"), {"b": ids["batch"]}
            ).scalar_one()
            == "fail"
        )
    assert client.get("/supplier-exclusions").json()["items"][0]["id"] == row["id"]


def test_exclusion_requires_verify_dual_approval_then_execute_once(scenario):
    client, ids, engine, actor = scenario
    row = client.post("/supplier-exclusions/proposals", json=body(ids)).json()
    did = row["source_decision_id"]
    assert client.post("/actions/execute", json={"decision_id": did}).status_code == 409
    assert client.post("/actions/verify", json={"decision_id": did}).status_code == 200
    assert (
        client.post("/actions/approve", json={"decision_id": did, "approved": True}).status_code
        == 200
    )
    assert client.post("/actions/execute", json={"decision_id": did}).status_code == 409
    actor("nutritionist")
    assert (
        client.post("/actions/approve", json={"decision_id": did, "approved": True}).status_code
        == 200
    )
    # Eksekusi milik Head (PLAN.md §13.3); Nutritionist hanya approval kedua.
    actor("head")
    execution = client.post("/actions/execute", json={"decision_id": did})
    assert execution.status_code == 200, execution.text
    assert execution.json()["exclusion"]["status"] == "active"
    assert client.post("/actions/execute", json={"decision_id": did}).status_code == 200
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM ledger_blocks WHERE entity_id=:d AND action='execute'"),
                {"d": did},
            ).scalar_one()
            == 1
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM sap_mock_purchase_orders WHERE decision_id=:d"),
                {"d": did},
            ).scalar_one()
            == 0
        )
    summary = client.get(f"/decisions/{did}/approval-summary").json()
    assert summary["supplier_governance"]["supplier_id"] == str(ids["supplier"])
    assert summary["execution_target"] == "LOCAL"
    assert summary["quantity_kg"] is None


def activate(client, ids, actor):
    actor("head")
    row = client.post("/supplier-exclusions/proposals", json=body(ids)).json()
    did = row["source_decision_id"]
    context = client.get(f"/supplier-exclusions/context/{did}")
    assert context.status_code == 200, context.text
    context_body = context.json()
    assert context_body["scope_location_id"] == str(ids["scope"])
    assert context_body["suppliers"][0]["id"] == str(ids["supplier"])
    assert context_body["suppliers"][0]["batch_ids"] == [str(ids["batch"])]
    assert client.post("/actions/verify", json={"decision_id": did}).status_code == 200
    assert (
        client.post("/actions/approve", json={"decision_id": did, "approved": True}).status_code
        == 200
    )
    actor("nutritionist")
    assert (
        client.post("/actions/approve", json={"decision_id": did, "approved": True}).status_code
        == 200
    )
    # Eksekusi milik Head (PLAN.md §13.3).
    actor("head")
    assert client.post("/actions/execute", json={"decision_id": did}).status_code == 200
    return row


def test_restoration_needs_new_evidence_and_fresh_approvals_without_changing_fail(scenario):
    client, ids, engine, actor = scenario
    row = activate(client, ids, actor)
    url = f"/supplier-exclusions/{row['id']}/restore"
    payload = {
        "reason": "Corrective action documented",
        "evidence_refs": body(ids)["evidence_refs"],
    }
    assert client.post(url, json=payload).status_code == 422
    evidence_id = uuid.uuid4()
    with engine.begin() as conn:
        import json

        conn.execute(
            text(
                "INSERT INTO decision_evidence(id,decision_id,evidence_type,payload) "
                "VALUES (:id,:d,'temperature',CAST(:p AS jsonb))"
            ),
            {
                "id": evidence_id,
                "d": row["source_decision_id"],
                "p": json.dumps({"batch_id": str(ids["batch"]), "note": "Corrective inspection"}),
            },
        )
    payload["evidence_refs"] = [{"type": "incident", "id": str(evidence_id)}]
    restored = client.post(url, json=payload)
    assert restored.status_code == 201, restored.text
    did = restored.json()["restoration_decision_id"]
    assert restored.json()["status"] == "active"
    assert client.post("/actions/execute", json={"decision_id": did}).status_code == 409
    assert client.post("/actions/verify", json={"decision_id": did}).status_code == 200
    assert (
        client.post("/actions/approve", json={"decision_id": did, "approved": True}).status_code
        == 200
    )
    assert client.post("/actions/execute", json={"decision_id": did}).status_code == 409
    # Approval kedua oleh role berbeda (Head sudah approve di atas).
    actor("nutritionist")
    assert (
        client.post("/actions/approve", json={"decision_id": did, "approved": True}).status_code
        == 200
    )
    # Eksekusi milik Head (PLAN.md §13.3).
    actor("head")
    result = client.post("/actions/execute", json={"decision_id": did})
    assert result.status_code == 200, result.text
    assert result.json()["exclusion"]["status"] == "revoked"
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT safety_status FROM batches WHERE id=:b"), {"b": ids["batch"]}
            ).scalar_one()
            == "fail"
        )


def test_validation_scope_monitor_rejection_and_generic_bypass(scenario):
    client, ids, engine, actor = scenario
    actor("monitor")
    assert client.post("/supplier-exclusions/proposals", json=body(ids)).status_code == 403
    actor("head", ids["source"])
    assert client.post("/supplier-exclusions/proposals", json=body(ids)).status_code == 403
    actor("head")
    for change in [
        {"reason": "  "},
        {"supplier_id": str(uuid.uuid4())},
        {"evidence_refs": [{"type": "batch", "id": str(uuid.uuid4())}]},
    ]:
        assert client.post(
            "/supplier-exclusions/proposals", json={**body(ids), **change}
        ).status_code in {404, 422}
    bypass = client.post(
        "/decisions", json={"decision_type": "supplier_exclusion", "recommendation": {}}
    )
    assert bypass.status_code == 422
    row = client.post("/supplier-exclusions/proposals", json=body(ids)).json()
    did = row["source_decision_id"]
    actor("head", ids["source"])
    assert (
        client.post("/actions/approve", json={"decision_id": did, "approved": True}).status_code
        == 403
    )
    actor("head")
    assert (
        client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": False, "comment": "Need better evidence"},
        ).status_code
        == 200
    )
    assert client.post("/actions/repropose", json={"decision_id": did}).status_code == 409
    assert client.post("/actions/execute", json={"decision_id": did}).status_code == 409
    assert (
        client.get("/supplier-exclusions", params={"supplier_id": str(ids["supplier"])}).json()[
            "items"
        ][0]["status"]
        == "rejected"
    )
    again = client.post("/supplier-exclusions/proposals", json=body(ids))
    assert again.status_code == 201
    assert again.json()["source_decision_id"] != did


def test_old_transfer_revalidates_supplier_and_exact_batch(scenario):
    client, ids, engine, actor = scenario
    import json

    transfer = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE batches SET safety_status='pass' WHERE id=:b"), {"b": ids["batch"]}
        )
        conn.execute(
            text(
                "INSERT INTO decisions(id,decision_type,status,proposed_by,verified_by,"
                "verifier_note,source_location_id,target_location_id,commodity_id,"
                "quantity_kg,safe_delivered_cost,expires_at) VALUES "
                "(:d,'regional_balance','pending_approval',:a,'verifier_agent',"
                "'consistent',:s,:t,:c,50,5000,now()+interval '30 minutes')"
            ),
            {
                "d": transfer,
                "a": str(ids["head"]),
                "s": ids["source"],
                "t": ids["scope"],
                "c": ids["commodity"],
            },
        )
        conn.execute(
            text(
                "INSERT INTO decision_evidence(decision_id,evidence_type,payload) "
                "VALUES (:d,'human_inspection',CAST(:p AS jsonb))"
            ),
            {
                "d": transfer,
                "p": json.dumps(
                    {
                        "allocation_binding": True,
                        "supplier_id": str(ids["supplier"]),
                        "batch_ids": [str(ids["batch"])],
                    }
                ),
            },
        )
    assert (
        client.post(
            "/actions/approve", json={"decision_id": str(transfer), "approved": True}
        ).status_code
        == 200
    )
    # Transfer operasional butuh approval kedua (PLAN.md §13.3), supaya yang
    # diuji di bawah benar-benar blokir "excluded", bukan approval kurang.
    actor("nutritionist")
    assert (
        client.post(
            "/actions/approve", json={"decision_id": str(transfer), "approved": True}
        ).status_code
        == 200
    )
    actor("head")
    activate(client, ids, actor)
    result = client.post("/actions/execute", json={"decision_id": str(transfer)})
    assert result.status_code == 409, result.text
    assert "excluded" in result.json()["detail"]
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM sap_mock_purchase_orders WHERE decision_id=:d"),
                {"d": transfer},
            ).scalar_one()
            == 0
        )
