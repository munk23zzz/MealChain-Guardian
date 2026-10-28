"""Dua gerbang eksekusi: PO draft → review Kepala SPPG → kirim ke SAP mock.

Latar (dokumen `02-approval-action.md` §6, keputusan pemilik 28 Okt 2026):
"Disetujui" bukan keadaan akhir. Sebelum perubahan ini `POST /actions/execute`
menerbitkan PO berstatus `submitted` dan langsung menandai keputusan
`executed` — satu klik menyelesaikan approval, penerbitan dokumen, dan
pengiriman ke SAP sekaligus. Akibatnya tidak ada tempat bagi langkah review PO
yang disebut dokumen, dan keadaan "sudah cukup approval, menunggu review PO"
tidak pernah bisa terjadi.

Kontrak yang dikunci tes ini:

1. `execute` (operasional) menerbitkan PO **draft**, keputusan tetap `approved`,
   batch TIDAK diberangkatkan, trace ACT TIDAK ditulis, dan blok ledger yang
   lahir bernama `po_draft`.
2. `execute` kedua tidak menerbitkan PO kedua — ditolak 409 dengan sebabnya.
3. `POST /actions/purchase-orders/{po_number}/approve` (Kepala SPPG, cakupan
   lokasi target) mengubah PO menjadi `submitted`, keputusan menjadi
   `executed`, menulis ACT, memberangkatkan batch, dan menambah blok ledger
   `execute`.
4. Read model `approval-summary` menyebut PO-nya (`purchase_order`) dan
   mematikan `can_execute` selama PO masih draft.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.main import app
from tests.dsn import DSN_SYNC
from tests.test_actions import (
    _cleanup,
    _login,
    _mk_decision,
    _mk_user,
    _verify_decision,
)

DB_URL = DSN_SYNC


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _db():
    return create_engine(DB_URL)


def _po_rows(decision_id: str) -> list[dict]:
    engine = _db()
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT po_number, status FROM sap_mock_purchase_orders "
                    "WHERE decision_id = :d ORDER BY created_at"
                ),
                {"d": decision_id},
            ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        engine.dispose()


def _decision_row(decision_id: str) -> dict:
    engine = _db()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT status, expires_at FROM decisions WHERE id = :d"),
                {"d": decision_id},
            ).mappings().one()
        return dict(row)
    finally:
        engine.dispose()


def _batch_terikat(decision_id: str) -> str:
    """Batch yang diikat `_ikat_binding` (jalur bukti yang sama dengan produksi)."""
    engine = _db()
    try:
        with engine.begin() as conn:
            payload = conn.execute(
                text(
                    "SELECT payload FROM decision_evidence "
                    "WHERE decision_id = :d AND payload->>'allocation_binding' = 'true' "
                    "LIMIT 1"
                ),
                {"d": decision_id},
            ).scalar_one()
        data = payload if isinstance(payload, dict) else json.loads(payload)
        return data["batch_ids"][0]
    finally:
        engine.dispose()


def _batch_dispatched(batch_id: str):
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(
                text("SELECT dispatched_at FROM batches WHERE id = :b"), {"b": batch_id}
            ).scalar_one()
    finally:
        engine.dispose()


def _reset_batch_berangkat(batch_id: str) -> None:
    """Kosongkan `dispatched_at` supaya "barang berangkat" bisa diukur.

    Batch seed Cianjur/telur sudah pernah diberangkatkan oleh deret aktivitas
    demo, sehingga `dispatched_at` yang tidak NULL tidak membuktikan apa pun
    tentang gerbang mana pun. Tes ini mengosongkannya DULU, lalu mengukur
    apakah gerbang 1 (draft) membiarkannya kosong dan gerbang 2 mengisinya.
    """
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE batches SET dispatched_at = NULL WHERE id = :b"),
                {"b": batch_id},
            )
    finally:
        engine.dispose()


def _act_trace_count(decision_id: str) -> int:
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT count(*) FROM agent_traces "
                    "WHERE decision_id = :d AND step_name = 'ACT'"
                ),
                {"d": decision_id},
            ).scalar_one()
    finally:
        engine.dispose()


def _ledger_actions(decision_id: str) -> list[str]:
    engine = _db()
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT action FROM ledger_blocks WHERE entity_id = :d "
                    "ORDER BY height"
                ),
                {"d": decision_id},
            ).scalars().all()
        return list(rows)
    finally:
        engine.dispose()


def _siap_disetujui(client, verdict: str = "consistent"):
    """Head + Nutritionist Jakarta untuk satu keputusan yang sudah 2 approval."""
    head = _mk_user("sppg_head", "Jakarta")
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = _mk_decision(client)
    client.post(
        "/actions/propose",
        json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
        headers=_login(client, head),
    )
    _verify_decision(decision_id, verdict)
    for user in (head, nutritionist):
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, user),
        )
        assert resp.status_code == 200, resp.text
    return decision_id, head, nutritionist


def test_execute_terbitkan_po_draft_bukan_langsung_kirim(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    batch_id = _batch_terikat(decision_id)
    _reset_batch_berangkat(batch_id)
    try:
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["po_number"].startswith("MC-")
        # PO belum dikirim: masih draft, dan keputusan belum executed.
        assert body["po_status"] == "draft"
        assert body["decision_status"] == "approved"
        assert body["awaiting"] == "po_review"

        po = _po_rows(decision_id)
        assert [row["status"] for row in po] == ["draft"]
        assert _decision_row(decision_id)["status"] == "approved"
        # Belum komit: tidak ada ACT, batch belum berangkat.
        assert _act_trace_count(decision_id) == 0
        assert _batch_dispatched(batch_id) is None
        assert _ledger_actions(decision_id)[-1] == "po_draft"
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_execute_kedua_tidak_menerbitkan_po_kedua(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    try:
        first = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert first.status_code == 200, first.text
        second = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert second.status_code == 409
        assert "review" in second.json()["detail"].lower()
        # Tetap satu baris PO, dan nomornya sama dengan yang pertama.
        po = _po_rows(decision_id)
        assert len(po) == 1
        assert po[0]["po_number"] == first.json()["po_number"]
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_review_po_mengirim_ke_sap_dan_mengeksekusi(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    batch_id = _batch_terikat(decision_id)
    _reset_batch_berangkat(batch_id)
    try:
        draft = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        po_number = draft.json()["po_number"]
        # Gerbang 1 belum memberangkatkan barang.
        assert _batch_dispatched(batch_id) is None

        resp = client.post(
            f"/actions/purchase-orders/{po_number}/approve",
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["po_number"] == po_number
        assert body["po_status"] == "submitted"
        assert body["decision_status"] == "executed"
        assert body["reviewed_by"] == head["id"]

        assert [row["status"] for row in _po_rows(decision_id)] == ["submitted"]
        assert _decision_row(decision_id)["status"] == "executed"
        assert _act_trace_count(decision_id) == 1
        assert _batch_dispatched(batch_id) is not None
        assert _ledger_actions(decision_id)[-1] == "execute"
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_review_po_hanya_kepala_sppg(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    monitor = _mk_user("bgn_monitor")
    try:
        draft = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        po_number = draft.json()["po_number"]
        for user in (nutritionist, monitor):
            resp = client.post(
                f"/actions/purchase-orders/{po_number}/approve",
                headers=_login(client, user),
            )
            assert resp.status_code == 403, f"{user['role']} seharusnya ditolak"
        # PO tetap draft: penolakan tidak mengubah keadaan.
        assert [row["status"] for row in _po_rows(decision_id)] == ["draft"]
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"], monitor["email"]])


def test_review_po_terikat_cakupan_lokasi(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    lain = _mk_user("sppg_head", "Bandung")
    try:
        draft = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        po_number = draft.json()["po_number"]
        resp = client.post(
            f"/actions/purchase-orders/{po_number}/approve",
            headers=_login(client, lain),
        )
        assert resp.status_code == 403, resp.text
        assert [row["status"] for row in _po_rows(decision_id)] == ["draft"]
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"], lain["email"]])


def test_review_po_tidak_ditemukan(client):
    head = _mk_user("sppg_head", "Jakarta")
    try:
        resp = client.post(
            "/actions/purchase-orders/MC-TIDAKADAXYZ/approve",
            headers=_login(client, head),
        )
        assert resp.status_code == 404
    finally:
        _cleanup(None, [head["email"]])


def test_review_po_kedua_ditolak(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    try:
        draft = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        po_number = draft.json()["po_number"]
        first = client.post(
            f"/actions/purchase-orders/{po_number}/approve",
            headers=_login(client, head),
        )
        assert first.status_code == 200, first.text
        second = client.post(
            f"/actions/purchase-orders/{po_number}/approve",
            headers=_login(client, head),
        )
        assert second.status_code == 409
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_review_po_menolak_keputusan_kedaluwarsa(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    try:
        draft = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        po_number = draft.json()["po_number"]
        # Jendela keputusan dilewatkan SETELAH PO draft terbit.
        engine = _db()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE decisions SET expires_at = :t WHERE id = :d"),
                    {
                        "t": datetime.now(timezone.utc) - timedelta(minutes=1),
                        "d": decision_id,
                    },
                )
        finally:
            engine.dispose()
        resp = client.post(
            f"/actions/purchase-orders/{po_number}/approve",
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        assert "expired" in resp.json()["detail"].lower()
        assert [row["status"] for row in _po_rows(decision_id)] == ["draft"]
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_approval_summary_menyebut_po_draft_dan_mematikan_eksekusi(client):
    decision_id, head, nutritionist = _siap_disetujui(client)
    try:
        draft = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        po_number = draft.json()["po_number"]
        resp = client.get(
            f"/decisions/{decision_id}/approval-summary",
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        summary = resp.json()
        assert summary["purchase_order"]["po_number"] == po_number
        assert summary["purchase_order"]["status"] == "draft"
        # Selama PO draft, eksekusi ulang bukan pilihan yang sah.
        assert summary["can_execute"] is False
        assert any("review" in alasan.lower() for alasan in summary["blocking_reasons"])
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_review_po_butuh_login(client):
    resp = client.post("/actions/purchase-orders/MC-APAPUNAAA/approve")
    assert resp.status_code == 401
