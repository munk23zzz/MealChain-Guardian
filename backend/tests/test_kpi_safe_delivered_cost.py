"""KPI "Safe Delivered Cost" — hanya eksekusi nyata yang mengisi metrik (TDD, 16 Okt 2026).

Gap terukur: query SDC (`kpi_service.py`) men-join
`sap_mock_purchase_orders po ON po.decision_id = d.id`, sedangkan satu-satunya
penulis `decision_id` adalah `POST /actions/execute` — PO yang di-seed
(`data/seed/sprint1_seed.json` baris `4500000001` + dua baris mock lain) tidak
punya keputusan yang bisa dirujuk, jadi metriknya `no_data` di setiap jendela.

Ruling yang diuji: baris seed itu DIBIARKAN apa adanya. Menyambungkannya ke
keputusan mana pun berarti mengarang provenance ("PO ini bukti eksekusi
keputusan X") — persis yang dilarang aturan repo ini. Sebagai gantinya
dibuktikan bahwa jalur nyata bekerja: setelah eksekusi lewat API, metrik SDC
berisi angka keputusan yang dieksekusi itu (mean satu PO).
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL
from tests.test_actions import _cleanup, _login, _mk_user

DB_URL = DSN_SYNC


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _force_server_verdict(verdict: str = "CONSISTENT", reason: str = "uji"):
    import json as _json

    def _chain():
        return [
            (
                "test_provider",
                lambda prompt: _json.dumps({"verdict": verdict, "reason": reason}),
                "test",
            )
        ]

    app.dependency_overrides[get_verifier_chain] = _chain

    def _restore():
        app.dependency_overrides.pop(get_verifier_chain, None)

    return _restore


def _db_one(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            return conn.execute(text(query), params or {}).fetchone()
    finally:
        engine.dispose()


def _sdc_metric(client, headers) -> dict:
    now = datetime.now(timezone.utc)
    resp = client.get(
        "/kpi",
        params={
            "start": (now - timedelta(hours=2)).isoformat(),
            "end": (now + timedelta(hours=2)).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return {m["name"]: m for m in resp.json()["metrics"]}["Safe Delivered Cost"]


def test_safe_delivered_cost_tersedia_setelah_eksekusi(client, monitor_headers):
    """Eksekusi nyata menambah satu sampel SDC di jendela metrik."""
    from app.services.event1_orchestrator import run_event1

    head = _mk_user("sppg_head", "Jakarta")
    # Keputusan operasional (transfer) wajib DUA approval dari dua role berbeda
    # (matriks S3-01 `dua_role_wajib`); satu approval head menyisakan 409.
    gizi = _mk_user("sppg_nutritionist", "Jakarta")
    restore = _force_server_verdict()
    decision_id = run_event1(commodity="telur", target_location="Jakarta")["decision_id"]
    try:
        before = _sdc_metric(client, monitor_headers)
        # JANGAN mengandaikan DB kosong: DB kerja adalah DB DEMO, jadi keputusan
        # yang sudah dieksekusi nyata (ber-PO) bisa membuat metrik ini `available`
        # sebelum tes ini jalan. Yang diuji transisinya — keputusan ini menambah
        # satu sampel, dan nilainya masuk ke daftar sampel jendela.
        sebelum_sampel = int(before.get("sample_count") or 0)

        for path, payload in (
            ("propose", {"decision_id": decision_id, "material_number": "MAT-TELUR"}),
            ("verify", {"decision_id": decision_id}),
            ("approve", {"decision_id": decision_id, "approved": True}),
        ):
            resp = client.post(
                f"/actions/{path}", json=payload, headers=_login(client, head)
            )
            assert resp.status_code in (200, 201), resp.text
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, gizi),
        )
        assert resp.status_code in (200, 201), resp.text
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text

        stored = _db_one(
            "SELECT d.safe_delivered_cost, po.created_at FROM decisions d "
            "JOIN sap_mock_purchase_orders po ON po.decision_id = d.id "
            "WHERE d.id = :d",
            {"d": decision_id},
        )
        assert stored is not None, "eksekusi wajib menulis PO ber-decision_id"
        sdc_value = stored[0]

        after = _sdc_metric(client, monitor_headers)
        assert after["state"] == "available", after
        assert int(after["sample_count"]) == sebelum_sampel + 1, after
        assert float(after["value"]) > 0
        # Nilai metrik = RATAAN PO di jendela, jadi ia hanya sama dengan SDC
        # keputusan ini bila tak ada sampel lain. Yang dibuktikan di sini: SDC
        # keputusan ini benar-benar menjadi salah satu sampel jendela.
        sampel_jendela = _db_one(
            "SELECT array_agg(round(d.safe_delivered_cost, 2)) "
            "FROM sap_mock_purchase_orders po "
            "JOIN decisions d ON d.id = po.decision_id "
            "WHERE po.created_at >= now() - interval '2 hours' "
            "AND po.created_at < now() + interval '2 hours' "
            "AND d.safe_delivered_cost IS NOT NULL"
        )
        assert sampel_jendela is not None and sampel_jendela[0] is not None
        assert round(float(sdc_value), 2) in [float(v) for v in sampel_jendela[0]]
    finally:
        restore()
        _cleanup(decision_id, [head["email"], gizi["email"]])


def test_po_seed_tetap_tanpa_decision_id(client):
    """Penjaga ruling: baris PO seed TIDAK boleh disambung ke keputusan karangan.

    Kalau kelak seseorang "memperbaiki" metrik dengan mengaitkan PO seed ke
    keputusan mana pun, tes ini memerah — dan itu memang tujuannya: provenance
    yang dikarang pada bukti eksekusi lebih buruk daripada kartu KPI kosong.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT po_number, decision_id FROM sap_mock_purchase_orders "
                    "WHERE po_number = '4500000001'"
                )
            ).fetchall()
    finally:
        engine.dispose()
    assert rows, "PO kanonik §11 wajib ada di dataset demo"
    assert all(row[1] is None for row in rows)


def test_tidak_ada_po_karangan_untuk_keputusan_lain(client):
    """Setiap PO ber-decision_id harus menunjuk keputusan yang benar-benar ada."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            orphan = conn.execute(
                text(
                    "SELECT count(*) FROM sap_mock_purchase_orders po "
                    "WHERE po.decision_id IS NOT NULL AND NOT EXISTS ("
                    "SELECT 1 FROM decisions d WHERE d.id = po.decision_id)"
                )
            ).scalar_one()
    finally:
        engine.dispose()
    assert orphan == 0, f"{orphan} PO menunjuk keputusan yang tidak ada"
