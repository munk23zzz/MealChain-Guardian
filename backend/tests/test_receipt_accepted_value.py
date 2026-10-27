"""Nilai penerimaan memakai HARGA INVOICE PO (Fase 5 butir 4b).

Kontrak yang dikunci:

1. PO yang mendanai sebuah batch dirujuk lewat bukti `allocation_binding` hasil
   `persist_supplier_binding` (`decision_evidence.payload.batch_ids`) — bukan
   tebakan dari pasangan (pemasok, komoditas, lokasi). Batch tanpa bukti itu
   TIDAK diatribusikan.
2. `accepted_value_idr = kg diterima × po.price`, dan `po.price` sejak Fase 5
   adalah harga satuan INVOICE (bahan + transportasi + penanganan) — penalti
   risiko internal tidak ikut.
3. Tanpa ikatan/PO, nilainya `null`. Bukan 0, bukan harga pasar, bukan
   `sdc / qty`: pembaca harus melihat absennya.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.dsn import DSN_SYNC

_FILTER_LAYAK = (
    "b.safety_status = 'pass' "
    "AND jsonb_array_length(COALESCE(b.temperature_log, '[]'::jsonb)) >= 2 "
    "AND (b.usable_until IS NULL OR b.usable_until > now()) "
    "AND NOT EXISTS (SELECT 1 FROM batch_receipts r "
    "  WHERE r.batch_id = b.id AND r.status IN ('menunggu','disetujui'))"
)


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _db():
    return create_engine(DSN_SYNC)


def _batch_terikat() -> tuple[str, str, str, float, float]:
    """Batch yang punya bukti `allocation_binding` + PO, dan layak diterima."""
    engine = _db()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT b.id, b.location_id, b.commodity_id, b.quantity_kg, po.price "
                    "FROM batches b JOIN locations l ON l.id = b.location_id "
                    "JOIN decision_evidence e ON e.evidence_type = 'human_inspection' "
                    "  AND jsonb_exists(e.payload->'batch_ids', b.id::text) "
                    "JOIN decisions d ON d.id = e.decision_id "
                    "JOIN sap_mock_purchase_orders po ON po.decision_id = d.id "
                    f"WHERE l.name = 'Jakarta' AND {_FILTER_LAYAK} "
                    "ORDER BY b.usable_until DESC NULLS LAST LIMIT 1"
                )
            ).one()
        return str(row[0]), str(row[1]), str(row[2]), float(row[3]), float(row[4])
    finally:
        engine.dispose()


def _batch_tanpa_ikatan() -> tuple[str, str, str, float]:
    """Batch layak yang TIDAK muncul di bukti `allocation_binding` mana pun."""
    engine = _db()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT b.id, b.location_id, b.commodity_id, b.quantity_kg "
                    "FROM batches b JOIN locations l ON l.id = b.location_id "
                    "WHERE l.name = 'Jakarta' "
                    "AND NOT EXISTS (SELECT 1 FROM decision_evidence e "
                    "  WHERE e.evidence_type = 'human_inspection' "
                    "  AND jsonb_exists(e.payload->'batch_ids', b.id::text)) "
                    f"AND {_FILTER_LAYAK} "
                    "ORDER BY b.usable_until DESC NULLS LAST LIMIT 1"
                )
            ).one()
        return str(row[0]), str(row[1]), str(row[2]), float(row[3])
    finally:
        engine.dispose()


def _bersihkan(receipt_ids: list[str], supply_ids: list[str]) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            for rid in receipt_ids:
                conn.execute(text("DELETE FROM batch_receipts WHERE id = :i"), {"i": rid})
            for sid in supply_ids:
                conn.execute(text("DELETE FROM supply_records WHERE id = :i"), {"i": sid})
    finally:
        engine.dispose()


def _catat(client, headers, batch_id: str) -> dict:
    resp = client.post(
        "/receipts",
        headers=headers,
        json={"batch_id": batch_id, "checked": {"kemasan": True}, "other_note": "uji nilai"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_nilai_diterima_memakai_harga_invoice_po(auth_headers):
    batch_id, _loc, _com, kg, price = _batch_terikat()
    receipt_ids: list[str] = []
    supply_ids: list[str] = []
    try:
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])
            assert badan["accepted_value_idr"] is None, "belum disetujui = belum ada nilai"

            setuju = c.post(f"/receipts/{badan['id']}/approve", headers=auth_headers)
            assert setuju.status_code == 200, setuju.text
            hasil = setuju.json()
            supply_ids.append(hasil["supply_record_id"])
            assert hasil["status"] == "disetujui"
            assert hasil["stock_kg"] == kg
            assert hasil["accepted_value_idr"] == pytest.approx(kg * price, abs=0.01)
    finally:
        _bersihkan(receipt_ids, supply_ids)


def test_tanpa_ikatan_bukti_nilai_null_bukan_nol(auth_headers):
    batch_id, _loc, _com, _kg = _batch_tanpa_ikatan()
    receipt_ids: list[str] = []
    supply_ids: list[str] = []
    try:
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])
            setuju = c.post(f"/receipts/{badan['id']}/approve", headers=auth_headers)
            assert setuju.status_code == 200, setuju.text
            hasil = setuju.json()
            supply_ids.append(hasil["supply_record_id"])
            assert hasil["accepted_value_idr"] is None
    finally:
        _bersihkan(receipt_ids, supply_ids)


def test_antrean_menunggu_membawa_kunci_nilai_kosong(auth_headers):
    """Kunci harus SELALU ada supaya UI tidak membedakan dua bentuk payload."""
    batch_id, _loc, _com, _kg, _harga = _batch_terikat()
    receipt_ids: list[str] = []
    try:
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])
            antrean = c.get("/receipts/menunggu", headers=auth_headers)
            assert antrean.status_code == 200, antrean.text
            baris = [i for i in antrean.json()["items"] if i["id"] == badan["id"]]
            assert baris, "catatan menunggu harus muncul di antrean"
            assert "accepted_value_idr" in baris[0]
            assert baris[0]["accepted_value_idr"] is None
    finally:
        _bersihkan(receipt_ids, [])
