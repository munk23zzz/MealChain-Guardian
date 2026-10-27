"""`GET /decisions/{id}` mengirim blok biaya komersial (Fase 9 butir 3).

Kontrak: endpoint mengirim `commercial_cost` **atau** `null`. `null` berarti
tidak ada biaya transfer (keputusan administratif) — bukan Rp 0. Angka invoice
tidak boleh memuat penalti risiko; penalti hanya hidup di SDC.

Baris dipilih dari DB (bukan id yang dipaku) supaya tes tidak merah hanya karena
dataset demo dibangun ulang.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC


@pytest.fixture()
def client(auth_headers):
    with TestClient(app) as c:
        c.headers.update(auth_headers)
        yield c


def _db():
    return create_engine(DSN_SYNC)


def _pilih_keputusan(ada_biaya: bool):
    """Keputusan Jakarta milik SPPG pengguna; pilih yang punya/tidak punya biaya.

    Untuk baris berbiaya, rinciannya harus LENGKAP (bahan+transport+handling):
    resolver sengaja tidak menerbitkan invoice dari rincian yang bolong.
    """
    sql = """
        SELECT d.id::text, d.quantity_kg, d.cost_breakdown
        FROM decisions d
        JOIN locations l ON l.id = d.target_location_id
        WHERE l.name = 'Jakarta'
          AND d.cost_breakdown IS {banding}
        {kuantitas}
        ORDER BY d.created_at DESC
        LIMIT 1
    """.format(
        banding="NOT NULL" if ada_biaya else "NULL",
        kuantitas=(
            "AND d.quantity_kg > 0"
            " AND d.cost_breakdown ? 'transport'"
            " AND d.cost_breakdown ? 'handling'"
            " AND d.cost_breakdown ? 'expected_loss'"
            if ada_biaya
            else ""
        ),
    )
    with _db().connect() as conn:
        return conn.execute(text(sql)).mappings().first()


def _pilih_keputusan_rincian_bolong():
    """Rincian berisi `purchase` saja (data demo punya dua baris seperti ini)."""
    sql = """
        SELECT d.id::text
        FROM decisions d
        JOIN locations l ON l.id = d.target_location_id
        WHERE l.name = 'Jakarta'
          AND d.cost_breakdown ? 'purchase'
          AND NOT (d.cost_breakdown ? 'transport')
        LIMIT 1
    """
    with _db().connect() as conn:
        return conn.execute(text(sql)).mappings().first()


def test_keputusan_berbiaya_mengirim_invoice_dan_sdc(client):
    baris = _pilih_keputusan(ada_biaya=True)
    if baris is None:
        pytest.skip("tidak ada keputusan Jakarta berbiaya pada dataset ini")

    resp = client.get(f"/decisions/{baris['id']}")
    assert resp.status_code == 200, resp.text
    biaya = resp.json()["commercial_cost"]
    assert biaya is not None, "keputusan berbiaya wajib mengirim commercial_cost"

    breakdown = baris["cost_breakdown"]
    purchase = Decimal(str(breakdown["purchase"]))
    transport = Decimal(str(breakdown["transport"]))
    handling = Decimal(str(breakdown["handling"]))
    penalti = sum(
        Decimal(str(breakdown.get(kunci, "0")))
        for kunci in ("expected_loss", "freshness_risk", "safety_penalty")
    )

    invoice = Decimal(biaya["invoice_total"])
    sdc = Decimal(biaya["sdc_total"] or "0")
    assert invoice == purchase + transport + handling
    assert invoice != invoice + penalti, "penalti tidak boleh masuk invoice"
    if biaya["sdc_total"] is not None:
        assert sdc == invoice + penalti
        assert sdc >= invoice

    # Harga satuan harus diturunkan dari total, bukan angka lain.
    kuantitas = Decimal(str(baris["quantity_kg"]))
    assert Decimal(biaya["invoice_unit_price"]) == (invoice / kuantitas).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def test_risk_method_menyebut_sumber_dan_versi(client):
    baris = _pilih_keputusan(ada_biaya=True)
    if baris is None:
        pytest.skip("tidak ada keputusan Jakarta berbiaya pada dataset ini")

    biaya = client.get(f"/decisions/{baris['id']}").json()["commercial_cost"]
    assert biaya is not None
    metode = biaya["risk_method"]
    assert metode["kind"] in ("simulated_policy", "calibrated_model", "unavailable")
    assert metode["source"]
    assert metode["version"]
    # Bobot demo tidak boleh diklaim sebagai model terkalibrasi.
    if metode["kind"] == "calibrated_model":
        assert metode["period"], "model terkalibrasi wajib menyebut periode kalibrasi"


def test_keputusan_administratif_mengirim_null(client):
    baris = _pilih_keputusan(ada_biaya=False)
    if baris is None:
        pytest.skip("tidak ada keputusan administratif Jakarta pada dataset ini")

    resp = client.get(f"/decisions/{baris['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commercial_cost"] is None
    # Jangan pernah menuliskan nol sebagai pengganti "tidak berlaku".
    assert body.get("commercial_cost") != {
        "invoice_total": "0.00",
        "sdc_total": "0.00",
    }


def test_rincian_bolong_tidak_menerbitkan_invoice(client):
    """Transportasi tidak tercatat → jangan klaim PO yang lebih kecil dari fakta."""
    baris = _pilih_keputusan_rincian_bolong()
    if baris is None:
        pytest.skip("tidak ada rincian biaya bolong pada dataset ini")

    resp = client.get(f"/decisions/{baris['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commercial_cost"] is None
    assert body["cost_breakdown"] is not None, "rincian mentah tetap dikirim apa adanya"
