"""Read model `DecisionEvidencePacket` (Fase 6 butir 4).

Kontrak yang dikunci berkas ini (MG/phase-06-decision-boundary.md):

- SATU pembangun paket keputusan (`GET /decisions/{id}/packet`) yang dipakai
  tampilan biaya, approval, trace, dan Joule. Frontend tidak merakit ulang
  evaluasi batch.
- Paket memuat `decision_id`, sesi demo, `batch_evaluations[]` (dari evaluator
  tunggal `app.core.batch_eligibility`), `supplier`, `candidate`,
  `costs` (bentuk `CommercialCost` atau `null`), `delivery{due_at, needed_by,
  feasible}`, `evidence{source_types, source_refs, completeness}`, dan
  `review{verifier, approvals, human_reviews, blocking_reasons}`.
- Angka di paket HARUS sama dengan angka sumbernya: `costs` == resolver
  `commercial_cost_payload`, alasan batch == `eligibility` pada
  `GET /batches/{id}`, `review.blocking_reasons` == `approval-summary`.
- Tidak ada angka karangan: rincian biaya tidak lengkap → `costs` null
  ("tidak berlaku"), bukan Rp 0.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC

PW = "TestPass#2026"


def _db():
    return create_engine(DSN_SYNC)


def _exec(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.begin() as conn:
            res = conn.execute(text(sql), params or {})
            try:
                return res.fetchall()
            except Exception:  # noqa: BLE001 - statement tanpa resultset
                return []
    finally:
        engine.dispose()


def _scalar(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(text(sql), params or {}).scalar_one_or_none()
    finally:
        engine.dispose()


def _lokasi(kota: str) -> str:
    return str(_scalar("SELECT id FROM locations WHERE name = :k", {"k": kota}))


def _komoditas(nama: str) -> str:
    return str(_scalar("SELECT id FROM commodities WHERE name = :c", {"c": nama}))


def _supplier() -> str:
    return str(_scalar("SELECT id FROM suppliers ORDER BY id LIMIT 1"))


def _mk_user(role: str, kota: str = "Jakarta") -> dict:
    uid = str(uuid.uuid4())
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-f6-packet.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    _exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "SELECT :i, 'Uji F6 paket', :e, :h, :r, "
        "CASE WHEN :k IS NULL OR :k = '' THEN NULL ELSE l.id END "
        "FROM (SELECT CAST(:k AS text) AS k) x LEFT JOIN locations l ON l.name = x.k",
        {"i": uid, "e": email, "h": digest, "r": role, "k": kota},
    )
    return {"id": uid, "email": email, "password": PW, "role": role}


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _buat_batch(*, kota: str = "Bandung", safety_status: str = "pass") -> dict:
    bid = str(uuid.uuid4())
    log = [
        {
            "timestamp": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
            "temperature_c": 4.0,
        },
        {
            "timestamp": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "temperature_c": 4.2,
        },
    ]
    _exec(
        "INSERT INTO batches (id, commodity_id, location_id, supplier_id, "
        "quantity_kg, harvested_at, temperature_log, certification_status, "
        "freshness_score, safety_status, usable_until, quarantine_status, origin) "
        "VALUES (CAST(:i AS uuid), CAST(:c AS uuid), CAST(:l AS uuid), "
        "CAST(:s AS uuid), 150, :h, CAST(:t AS jsonb), 'hygiene', 0.95, :ss, "
        ":uu, 'none', 'demo')",
        {
            "i": bid,
            "c": _komoditas("telur"),
            "l": _lokasi(kota),
            "s": _supplier(),
            "h": datetime.now(UTC) - timedelta(hours=6),
            "t": json.dumps(log),
            "ss": safety_status,
            "uu": datetime.now(UTC) + timedelta(days=4),
        },
    )
    return {
        "batch_id": bid,
        "location_id": _lokasi(kota),
        "commodity_id": _komoditas("telur"),
        "supplier_id": _supplier(),
    }


def _buat_keputusan(batch: dict, *, breakdown: dict, quantity_kg: float = 150) -> str:
    did = str(uuid.uuid4())
    _exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
        "verified_by, verifier_note, supplier_id) "
        "VALUES (CAST(:i AS uuid), 'regional_balance', 'pending_approval', "
        "'supervisor_agent', CAST(:src AS uuid), CAST(:tgt AS uuid), "
        "CAST(:kom AS uuid), :kg, 2475000, now() + interval '45 minutes', "
        "CAST(:cb AS jsonb), 1, 'verifier_agent', 'consistent', CAST(:sup AS uuid))",
        {
            "i": did,
            "src": batch["location_id"],
            "tgt": _lokasi("Jakarta"),
            "kom": batch["commodity_id"],
            "kg": quantity_kg,
            "cb": json.dumps(breakdown),
            "sup": batch["supplier_id"],
        },
    )
    _exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (CAST(:d AS uuid), 'human_inspection', CAST(:p AS jsonb))",
        {
            "d": did,
            "p": json.dumps(
                {
                    "allocation_binding": True,
                    "supplier_id": batch["supplier_id"],
                    "batch_ids": [batch["batch_id"]],
                    "source_location_id": batch["location_id"],
                    "commodity_id": batch["commodity_id"],
                }
            ),
        },
    )
    _exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (CAST(:d AS uuid), 'gps', CAST(:p AS jsonb))",
        {"d": did, "p": json.dumps({"route": "Bandung-Jakarta", "source": "gps_sim"})},
    )
    return did


RINCIAN_LENGKAP = {
    "purchase": "2250000.00",
    "transport": "45000.00",
    "handling": "150000.00",
    "expected_loss": "30000.00",
    "freshness_risk": "0.00",
    "safety_penalty": "0.00",
}


def _buat_demand(
    kota: str, needed_by: datetime, *, recorded_at: datetime | None = None
) -> str:
    """Sisipkan baris permintaan untuk (kota, telur).

    `recorded_at` bisa dipaksa NEWER daripada baris lain: paket memilih baris
    permintaan TERBARU (`recorded_at DESC`) sebagai tenggat yang berlaku, jadi
    tes yang ingin menguji tenggat lewat harus menulis barisnya sebagai yang
    terbaru — kalau tidak, baris fixture dari sesi lain menang dan asersinya
    merah/hijau karena urutan id acak, bukan karena logika.
    """
    rid = str(uuid.uuid4())
    _exec(
        "INSERT INTO demand_records (id, location_id, commodity_id, quantity_kg, "
        "needed_by, recorded_at, origin) VALUES (CAST(:i AS uuid), "
        "CAST(:l AS uuid), CAST(:c AS uuid), 200, :nb, :ra, 'demo')",
        {
            "i": rid,
            "l": _lokasi(kota),
            "c": _komoditas("telur"),
            "nb": needed_by,
            "ra": recorded_at or datetime.now(UTC) - timedelta(hours=3),
        },
    )
    return rid


@pytest.fixture()
def klien():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def aktor():
    user = _mk_user("bgn_monitor", kota="")
    try:
        yield user
    finally:
        _exec("DELETE FROM users WHERE id = CAST(:i AS uuid)", {"i": user["id"]})


@pytest.fixture()
def kasus():
    batch = _buat_batch()
    decision_id = _buat_keputusan(batch, breakdown=RINCIAN_LENGKAP)
    demand_id = _buat_demand("Jakarta", datetime.now(UTC) + timedelta(hours=12))
    try:
        yield {
            "batch": batch,
            "decision_id": decision_id,
            "demand_id": demand_id,
            "quantity_kg": 150.0,
        }
    finally:
        _exec("DELETE FROM demand_records WHERE id = CAST(:i AS uuid)", {"i": demand_id})
        _exec("DELETE FROM decisions WHERE id = CAST(:d AS uuid)", {"d": decision_id})
        _exec("DELETE FROM batches WHERE id = CAST(:b AS uuid)", {"b": batch["batch_id"]})


def test_paket_memuat_bentuk_lengkap_dan_sama_dengan_sumbernya(klien, aktor, kasus) -> None:
    from app.core.commercial_cost import commercial_cost_payload

    h = _login(klien, aktor)
    resp = klien.get(f"/decisions/{kasus['decision_id']}/packet", headers=h)
    assert resp.status_code == 200, resp.text
    paket = resp.json()

    for kunci in (
        "decision_id",
        "demo_session_id",
        "decision_type",
        "status",
        "batch_evaluations",
        "supplier",
        "candidate",
        "costs",
        "delivery",
        "evidence",
        "review",
    ):
        assert kunci in paket, kunci

    # Biaya: bentuk CommercialCost, angkanya dari resolver yang sama.
    harap = commercial_cost_payload(kasus["quantity_kg"], RINCIAN_LENGKAP)
    assert paket["costs"] == harap
    assert paket["costs"]["invoice_total"] == "2445000.00"
    assert paket["costs"]["risk_method"]["kind"] == "simulated_policy"

    # Evaluasi batch: alasan & status dari evaluator tunggal, bukan hitungan UI.
    resp_batch = klien.get(f"/batches/{kasus['batch']['batch_id']}", headers=h)
    assert resp_batch.status_code == 200, resp_batch.text
    eligibility = resp_batch.json()["eligibility"]
    baris = paket["batch_evaluations"][0]
    assert baris["batch_id"] == kasus["batch"]["batch_id"]
    assert baris["status"] == eligibility["status"]
    assert baris["blocking_reasons"] == eligibility["blocking_reasons"]
    assert baris["next_step"] == eligibility["next_step"]

    # Review: alasan blokir sama dengan approval-summary (satu kesimpulan server).
    summary = klien.get(
        f"/decisions/{kasus['decision_id']}/approval-summary", headers=h
    ).json()
    assert paket["review"]["blocking_reasons"] == summary["blocking_reasons"]
    assert paket["review"]["verifier"]["verdict"] == "consistent"
    assert paket["review"]["human_reviews"] == []

    # Bukti: tipe & referensi apa adanya.
    assert "human_inspection" in paket["evidence"]["source_types"]
    assert "gps" in paket["evidence"]["source_types"]
    assert paket["evidence"]["completeness"]["types_recorded"] == 2

    # Pengiriman: needed_by dari baris permintaan, feasible dari jendela waktu.
    assert paket["delivery"]["needed_by"] is not None
    assert paket["delivery"]["feasible"] is True
    assert paket["delivery"]["due_at"] == paket["delivery"]["needed_by"]


def test_paket_biaya_null_bila_rincian_tidak_lengkap(klien, aktor) -> None:
    batch = _buat_batch()
    # Dua keputusan demo lama hanya berisi `purchase`; invoice dari rincian
    # seperti itu lebih kecil dari kenyataan, jadi TIDAK boleh diterbitkan.
    decision_id = _buat_keputusan(batch, breakdown={"purchase": "2250000.00"})
    try:
        h = _login(klien, aktor)
        paket = klien.get(f"/decisions/{decision_id}/packet", headers=h).json()
        assert paket["costs"] is None
    finally:
        _exec("DELETE FROM decisions WHERE id = CAST(:d AS uuid)", {"d": decision_id})
        _exec("DELETE FROM batches WHERE id = CAST(:b AS uuid)", {"b": batch["batch_id"]})


def test_paket_menyatakan_pengiriman_tidak_layak_bila_tenggat_lewat(klien, aktor) -> None:
    batch = _buat_batch()
    decision_id = _buat_keputusan(batch, breakdown=RINCIAN_LENGKAP)
    # Baris permintaan TERBARU untuk (Jakarta, telur) dengan tenggat 2 jam lalu:
    # jendela waktu tersisa = 0, sehingga waktu tiba (>= 30 menit) melewatinya.
    demand_id = _buat_demand(
        "Jakarta", datetime.now(UTC) - timedelta(hours=2), recorded_at=datetime.now(UTC)
    )
    try:
        h = _login(klien, aktor)
        paket = klien.get(f"/decisions/{decision_id}/packet", headers=h).json()
        assert paket["delivery"]["feasible"] is False
        assert paket["delivery"]["needed_by"] is not None
    finally:
        _exec("DELETE FROM demand_records WHERE id = CAST(:i AS uuid)", {"i": demand_id})
        _exec("DELETE FROM decisions WHERE id = CAST(:d AS uuid)", {"d": decision_id})
        _exec("DELETE FROM batches WHERE id = CAST(:b AS uuid)", {"b": batch["batch_id"]})
