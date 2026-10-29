"""Endpoint fakta audit verifier (AUD-9A-03) — read-only, server-side.

Verifier agent tidak boleh menerima angka dari narasi supervisor maupun dari
request body. Endpoint `GET /decisions/{id}/audit-facts` menyusun fakta dari DB
kanonik dengan fungsi domain yang sudah ada, lalu diverifikasi di sini:

- bentuk jawaban lengkap (sdc_check, batch_sumber, evidence, exclusion, ledger);
- SDC check memakai aturan `recommendation_numbers` (bukan hitungan kedua);
- 401 tanpa token, 404 untuk id tak dikenal.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC

DSN = DSN_SYNC


def _id_keputusan() -> str:
    engine = create_engine(DSN)
    try:
        with engine.connect() as conn:
            nilai = conn.execute(
                text("SELECT id FROM decisions ORDER BY created_at DESC LIMIT 1")
            ).scalar_one()
    finally:
        engine.dispose()
    return str(nilai)


def test_audit_facts_mengembalikan_fakta_lengkap(monitor_headers) -> None:
    decision_id = _id_keputusan()
    with TestClient(app) as client:
        response = client.get(
            f"/decisions/{decision_id}/audit-facts", headers=monitor_headers
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["decision_id"] == decision_id
    for kunci in (
        "sdc_check",
        "evidence",
        "batch_sumber",
        "exclusion",
        "ledger",
        "citations",
    ):
        assert kunci in data, f"fakta '{kunci}' wajib ada"
    assert isinstance(data["sdc_check"]["cocok"], (bool, type(None)))
    assert isinstance(data["evidence"]["count"], int)
    assert isinstance(data["batch_sumber"]["batch_ids"], list)
    assert isinstance(data["ledger"]["block_ids"], list)
    assert data["citations"]["decision_id"] == decision_id


def test_audit_facts_memakai_aturan_sdc_yang_sama_dengan_core(monitor_headers) -> None:
    """Nilai `cocok` harus sama dengan fungsi core, bukan hitungan endpoint."""
    from app.core.recommendation_numbers import ringkasan_rincian

    decision_id = _id_keputusan()
    with TestClient(app) as client:
        response = client.get(
            f"/decisions/{decision_id}/audit-facts", headers=monitor_headers
        )
    assert response.status_code == 200, response.text
    data = response.json()

    engine = create_engine(DSN)
    try:
        with engine.connect() as conn:
            baris = conn.execute(
                text(
                    "SELECT safe_delivered_cost, cost_breakdown FROM decisions "
                    "WHERE id = :d"
                ),
                {"d": decision_id},
            ).one()
    finally:
        engine.dispose()

    harapan = ringkasan_rincian(baris[0], baris[1])
    assert data["sdc_check"]["cocok"] == harapan["cocok"]
    assert data["sdc_check"]["breakdown_total"] == harapan["breakdown_total"]


def test_audit_facts_tanpa_token_401() -> None:
    with TestClient(app) as client:
        response = client.get(f"/decisions/{uuid.uuid4()}/audit-facts")
    assert response.status_code == 401


def test_audit_facts_id_tak_dikenal_404(monitor_headers) -> None:
    with TestClient(app) as client:
        response = client.get(
            f"/decisions/{uuid.uuid4()}/audit-facts", headers=monitor_headers
        )
    assert response.status_code == 404


def test_audit_facts_memuat_neraca_pasokan(monitor_headers) -> None:
    """Neraca pasokan/kebutuhan ikut jadi fakta audit (29 Okt 2026).

    Narasi supervisor menyebut "kekurangan 281,41 kg (pasokan 1.232,83 vs
    kebutuhan 1.514,24)". Angka itu lahir dari langkah `DETECT` pipeline, bukan
    dari model -- tetapi selama tidak ada di fakta audit, cek `angka_bersitasi`
    menandainya tanpa sumber dan verdict jatuh ke `flagged` pada putaran yang
    SEHAT. Kuncinya wajib ada; `null` jujur untuk keputusan yang tidak punya
    langkah DETECT pipeline (mis. kasus template dari seed).
    """
    decision_id = _id_keputusan()
    with TestClient(app) as client:
        response = client.get(
            f"/decisions/{decision_id}/audit-facts", headers=monitor_headers
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "balance" in data
    neraca = data["balance"]
    if neraca is not None:
        assert neraca["sumber"] == "agent_traces:DETECT"
        for kunci in ("supply_kg", "demand_kg", "gap_kg"):
            assert kunci in neraca
