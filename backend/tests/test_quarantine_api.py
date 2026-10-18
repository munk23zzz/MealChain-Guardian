"""API karantina batch — kontrol manusia, bukan kewenangan agent.

Kontrak yang diuji (RED dulu):
- autentikasi wajib (401), bgn_monitor read-only (403);
- hanya peran SPPG pemilik lokasi batch yang boleh menahan/melepas (403 bila
  lokasi lain — pola `core/scope.py`);
- transisi tidak sah → 409, alasan wajib → 422;
- setiap transisi menambah satu blok evidence ledger (audit trail);
- batch berstatus `quarantined` hilang dari kandidat alokasi, dan kembali
  setelah dilepas.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


def _db_conn():
    return create_engine(DB_URL)


def _scalar(query: str, params: dict | None = None):
    engine = _db_conn()
    try:
        with engine.connect() as conn:
            row = conn.execute(text(query), params or {}).scalar_one()
            conn.commit()
            return row
    finally:
        engine.dispose()


def _exec(query: str, params: dict | None = None):
    engine = _db_conn()
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


@pytest.fixture()
def batch_jakarta():
    """Batch baru di Jakarta dengan log suhu bersih; dihapus setelah tes."""
    loc = _scalar("SELECT id FROM locations WHERE name = 'Jakarta'")
    com = _scalar("SELECT id FROM commodities WHERE name = 'telur'")
    sup = _scalar("SELECT id FROM suppliers LIMIT 1")
    bid = str(uuid.uuid4())
    _exec(
        "INSERT INTO batches (id, commodity_id, location_id, supplier_id, quantity_kg, "
        "harvested_at, temperature_log, certification_status, freshness_score, "
        "safety_status, origin) VALUES (:i, :c, :l, :s, 120, :h, :t, 'hygiene', 0.9, "
        "'needs_verification', 'demo')",
        {
            "i": bid,
            "c": str(com),
            "l": str(loc),
            "s": str(sup),
            "h": datetime.now(timezone.utc) - timedelta(hours=6),
            "t": json.dumps([]),
        },
    )
    yield bid
    _exec("DELETE FROM batches WHERE id = :i", {"i": bid})


@pytest.fixture()
def batch_bandung():
    """Batch di lokasi lain — untuk menguji penolakan scope."""
    loc = _scalar("SELECT id FROM locations WHERE name = 'Bandung'")
    com = _scalar("SELECT id FROM commodities WHERE name = 'telur'")
    sup = _scalar("SELECT id FROM suppliers LIMIT 1")
    bid = str(uuid.uuid4())
    _exec(
        "INSERT INTO batches (id, commodity_id, location_id, supplier_id, quantity_kg, "
        "harvested_at, temperature_log, certification_status, freshness_score, "
        "safety_status, origin) VALUES (:i, :c, :l, :s, 120, :h, :t, 'hygiene', 0.9, "
        "'needs_verification', 'demo')",
        {
            "i": bid,
            "c": str(com),
            "l": str(loc),
            "s": str(sup),
            "h": datetime.now(timezone.utc) - timedelta(hours=6),
            "t": json.dumps([]),
        },
    )
    yield bid
    _exec("DELETE FROM batches WHERE id = :i", {"i": bid})


def _post(headers, batch_id, aksi, alasan="log suhu janggal, perlu cek fisik"):
    with TestClient(app) as c:
        return c.post(
            f"/batches/{batch_id}/quarantine",
            json={"aksi": aksi, "alasan": alasan},
            headers=headers or {},
        )


def test_tanpa_token_401(batch_jakarta):
    resp = _post(None, batch_jakarta, "tahan")
    assert resp.status_code == 401


def test_monitor_nasional_tidak_boleh_menahan(monitor_headers, batch_jakarta):
    resp = _post(monitor_headers, batch_jakarta, "tahan")
    assert resp.status_code == 403
    status = _scalar(
        "SELECT quarantine_status FROM batches WHERE id = :i", {"i": batch_jakarta}
    )
    assert status == "none"


def test_sppg_menahan_batch_lokasinya(auth_headers, batch_jakarta):
    resp = _post(auth_headers, batch_jakarta, "tahan")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["quarantine_status"] == "quarantined"
    assert body["quarantine_reason"].startswith("log suhu")
    assert body["quarantined_at"] is not None
    status = _scalar(
        "SELECT quarantine_status FROM batches WHERE id = :i", {"i": batch_jakarta}
    )
    assert status == "quarantined"


def test_sppg_tidak_boleh_menahan_batch_lokasi_lain(auth_headers, batch_bandung):
    resp = _post(auth_headers, batch_bandung, "tahan")
    assert resp.status_code == 403
    status = _scalar(
        "SELECT quarantine_status FROM batches WHERE id = :i", {"i": batch_bandung}
    )
    assert status == "none"


def test_alasan_wajib_diisi(auth_headers, batch_jakarta):
    with TestClient(app) as c:
        resp = c.post(
            f"/batches/{batch_jakarta}/quarantine",
            json={"aksi": "tahan", "alasan": "   "},
            headers=auth_headers,
        )
    assert resp.status_code == 422


def test_aksi_tidak_dikenal_ditolak(auth_headers, batch_jakarta):
    resp = _post(auth_headers, batch_jakarta, "bakar")
    assert resp.status_code == 422


def test_batch_tidak_ada_404(auth_headers):
    resp = _post(auth_headers, str(uuid.uuid4()), "tahan")
    assert resp.status_code == 404


def test_melepas_batch_harus_dari_status_quarantined(auth_headers, batch_jakarta):
    resp = _post(auth_headers, batch_jakarta, "lepas")
    assert resp.status_code == 409


def test_alur_penuh_tahan_lepas(auth_headers, batch_jakarta):
    assert _post(auth_headers, batch_jakarta, "tahan").status_code == 201
    resp = _post(auth_headers, batch_jakarta, "lepas", alasan="sudah dicek, aman dipakai")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quarantine_status"] == "released"
    assert body["quarantined_at"] is None


def test_alur_tahan_lalu_gagal(auth_headers, batch_jakarta):
    assert _post(auth_headers, batch_jakarta, "tahan").status_code == 201
    resp = _post(auth_headers, batch_jakarta, "gagal", alasan="suhu rusak, tidak layak")
    assert resp.status_code == 200, resp.text
    assert resp.json()["quarantine_status"] == "failed"


def test_setiap_transisi_masuk_evidence_ledger(auth_headers, batch_jakarta):
    sebelum = _scalar("SELECT count(*) FROM ledger_blocks")
    assert _post(auth_headers, batch_jakarta, "tahan").status_code == 201
    assert _post(auth_headers, batch_jakarta, "lepas").status_code == 200
    sesudah = _scalar("SELECT count(*) FROM ledger_blocks")
    assert sesudah == sebelum + 2
    aksi = _scalar(
        "SELECT action FROM ledger_blocks WHERE entity_id = :i ORDER BY height DESC LIMIT 1",
        {"i": batch_jakarta},
    )
    assert aksi == "batch_quarantine_release"


def test_daftar_batch_menampilkan_status_karantina(auth_headers, batch_jakarta):
    assert _post(auth_headers, batch_jakarta, "tahan").status_code == 201
    with TestClient(app) as c:
        resp = c.get("/batches", headers=auth_headers)
    assert resp.status_code == 200
    baris = [b for b in resp.json()["batches"] if b["id"] == batch_jakarta]
    assert len(baris) == 1
    assert baris[0]["quarantine_status"] == "quarantined"
