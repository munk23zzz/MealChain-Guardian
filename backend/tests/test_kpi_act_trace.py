"""KPI "Decision Time" — penulis trace ACT di jalur eksekusi (TDD, 16 Okt 2026).

Gap terukur yang ditutup berkas ini: metrik **Decision Time**
(`app/services/kpi_service.py`) menghitung mean(first DETECT → last ACT)
per keputusan, dengan syarat keputusan sudah committed (PO mock ada).
`ACT` memenuhi semuanya — whitelist `trace_persistence._VALID_STEPS`, CHECK
`agent_traces_step_name_check`, `docs/Schema.md`, `docs/PRD.md`, dan prompt
supervisor ("ACT menunggu manusia") — tetapi TIDAK ADA kode yang menulisnya
(terukur: 0 baris ACT dari 255 trace), sehingga kartu KPI itu `no_data`
permanen apa pun datanya. Membaca whitelist/constraint sebagai bukti
"fiturnya ada" adalah kesalahan yang sama seperti mempercayai docstring.

Ruling yang diuji di sini: **ACT ditulis saat EKSEKUSI berhasil**
(`POST /actions/execute`), karena di situlah PO mock benar-benar terbit —
itulah arti "committed" yang dipakai metriknya. Eksekusi yang ditolak (409)
TIDAK boleh meninggalkan ACT palsu, dan jalur eksekusi administratif
(eksklusi pemasok, tanpa PO) sengaja tidak diuji di sini.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.main import app
from tests.test_actions import _cleanup, _login, _mk_user

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _force_server_verdict(verdict: str, reason: str = "uji"):
    """Rantai verifier di-override server-side (kontrak O-SEC-3).

    Pola sama dengan `tests/test_action_boundary_e2e.py`; selalu dipulihkan
    supaya override tidak bocor ke modul tes lain.
    """

    def _chain():
        return [
            (
                "test_provider",
                lambda prompt: json.dumps({"verdict": verdict, "reason": reason}),
                "test",
            )
        ]

    app.dependency_overrides[get_verifier_chain] = _chain

    def _restore():
        app.dependency_overrides.pop(get_verifier_chain, None)

    return _restore


def _event1_decision_id() -> str:
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    return outcome["decision_id"]


def _act_rows(decision_id: str) -> list[tuple]:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT step_name, tool_called, output_summary, step_at "
                    "FROM agent_traces WHERE decision_id = :d "
                    "AND step_name = 'ACT' ORDER BY step_at"
                ),
                {"d": decision_id},
            ).fetchall()
    finally:
        engine.dispose()


def _run_execute_flow(client, head) -> tuple[str, str]:
    """Event 1 → propose → verify CONSISTENT → approve → execute.

    Mengembalikan (decision_id, po_number).
    """
    decision_id = _event1_decision_id()
    client.post(
        "/actions/propose",
        json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
        headers=_login(client, head),
    )
    client.post(
        "/actions/verify", json={"decision_id": decision_id}, headers=_login(client, head)
    )
    client.post(
        "/actions/approve",
        json={"decision_id": decision_id, "approved": True},
        headers=_login(client, head),
    )
    resp = client.post(
        "/actions/execute", json={"decision_id": decision_id}, headers=_login(client, head)
    )
    assert resp.status_code == 200, resp.text
    return decision_id, resp.json()["po_number"]


def _kpi_metric(client, headers, name: str) -> dict:
    """Satu metrik dari GET /kpi pada jendela yang memuat hari ini."""
    now = datetime.now(timezone.utc)
    params = {
        "start": (now - timedelta(hours=2)).isoformat(),
        "end": (now + timedelta(hours=2)).isoformat(),
    }
    resp = client.get("/kpi", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    metrics = {m["name"]: m for m in resp.json()["metrics"]}
    return metrics[name]


def test_eksekusi_menulis_trace_act_dengan_nomor_po(client):
    """Eksekusi yang berhasil = satu baris ACT, dan PO-nya disebut di bukti."""
    head = _mk_user("sppg_head", "Jakarta")
    restore = _force_server_verdict("CONSISTENT")
    try:
        decision_id, po_number = _run_execute_flow(client, head)
        rows = _act_rows(decision_id)
        assert len(rows) == 1, rows
        step_name, tool_called, output_summary, _step_at = rows[0]
        assert step_name == "ACT"
        assert tool_called, "ACT tanpa tool_called tidak bisa dilacak"
        summary = output_summary
        if isinstance(summary, str):
            summary = json.loads(summary)
        assert summary["po_number"] == po_number
        # PO yang benar-benar tersimpan harus disebut juga di input_summary
        assert summary["status"] == "submitted"
    finally:
        restore()
        _cleanup(decision_id, [head["email"]])


def test_eksekusi_yang_ditolak_tidak_menulis_act(client):
    """Eksekusi 409 (belum di-approve) tidak boleh meninggalkan ACT palsu."""
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409, resp.text
        assert _act_rows(decision_id) == []
    finally:
        _cleanup(decision_id, [head["email"]])


def test_decision_time_tersedia_setelah_eksekusi(client, monitor_headers):
    """Kartu Decision Time berhenti jadi `no_data` setelah satu eksekusi nyata.

    Metrik hanya menghitung keputusan ber-`demo_case IS NULL` yang sudah
    committed (PO ada) — keputusan Event 1 memenuhi keduanya setelah eksekusi.
    """
    head = _mk_user("sppg_head", "Jakarta")
    restore = _force_server_verdict("CONSISTENT")
    decision_id: str | None = None
    try:
        before = _kpi_metric(client, monitor_headers, "Decision Time")
        # JANGAN mengandaikan DB kosong. DB kerja adalah DB DEMO yang dipakai
        # bersama: keputusan nyata yang sudah dieksekusi (beserta PO-nya) bisa
        # sudah ada di jendela metrik, sehingga keadaannya `available` sebelum
        # tes ini jalan. Yang diuji adalah TRANSISI: keputusan yang baru
        # dieksekusi ikut terhitung.
        sebelum_sampel = int(before.get("sample_count") or 0)
        decision_id, _po = _run_execute_flow(client, head)
        after = _kpi_metric(client, monitor_headers, "Decision Time")
        assert after["state"] == "available", after
        assert after["value"] is not None
        assert int(after["sample_count"]) == sebelum_sampel + 1, after
        assert float(after["value"]) >= 0
    finally:
        restore()
        _cleanup(decision_id, [head["email"]])
