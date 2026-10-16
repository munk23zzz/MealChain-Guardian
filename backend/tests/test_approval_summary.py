"""S4-04 — GET /decisions/{id}/approval-summary (RED dulu, TDD).

Kontrak plan §S4-04 + prompt Owner §21–22:
- Read model kanonik server-side: decision + lokasi/komoditas/supplier/
  material + safety/freshness batch sumber + evidence + verifier + expiry
  + approval_requirement + approvals tercatat + approval_state + can_approve
  + can_execute + blocking_reasons + target eksekusi MOCK.
- UI TIDAK menghitung requirement — semua dari backend (approval_matrix).
- Parity summary↔execute (O-PO): supplier/material/quantity pada PO hasil
  execute WAJIB sama dengan yang dijanjikan summary.
- Auth: unauth 401; scope lokasi (O-SEC-2) — SPPG lain 403; monitor
  read-only boleh membaca; 404 unknown.
  REVISI S4-05 (Ruling Owner 2026-10-08): VERIFIER_ROLES
  (sppg_head/sppg_nutritionist) boleh membaca summary lintas lokasi
  (selaras write path approve — matriks AND butuh approver ke-2).
- Missing facts → null/unavailable, tidak ada default palsu.

Dokumen Bahasa Indonesia. Tanpa mutation pada endpoint read ini.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

NOW = datetime.now(timezone.utc)


def _db_all(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), params or {}).fetchall()
            conn.commit()
            return rows
    finally:
        engine.dispose()


def _db_exec(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


def _db_exec_returning(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            row = conn.execute(text(query), params or {}).fetchone()
            return row[0] if row else None
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# Password demo statis (seed_data.py DEMO_USERS; bukan secret produksi).
def _head_user(client: TestClient) -> dict:
    return _login(client, "sppg.head@demo.local", "Demo#SPPG2026")


def _nut_user(client: TestClient) -> dict:
    return _login(client, "sppg.nutritionist@demo.local", "Demo#Nut2026")


def _monitor_user(client: TestClient) -> dict:
    return _login(client, "bgn.monitor@demo.local", "Demo#BGN2026")


def _mk_batch(location_id: str, fail: bool) -> dict:
    """Batch uji di lokasi uji; log suhu relatif now (anti time-bomb)."""
    suffix = uuid.uuid4().hex[:8]
    t0 = NOW - timedelta(hours=3)
    log = (
        [
            {"timestamp": (t0).isoformat(), "temperature_c": 4.0},
            {
                "timestamp": (t0 + timedelta(minutes=30)).isoformat(),
                "temperature_c": 20.0,
            },
            {
                "timestamp": (t0 + timedelta(minutes=90)).isoformat(),
                "temperature_c": 4.0,
            },
        ]
        if fail
        else [
            {"timestamp": (t0).isoformat(), "temperature_c": 4.0},
            {
                "timestamp": (t0 + timedelta(minutes=90)).isoformat(),
                "temperature_c": 4.2,
            },
        ]
    )
    sup_id = _db_exec_returning(
        "INSERT INTO suppliers (name, location_id, reliability_score) "
        "SELECT :n, :lid, 0.8 RETURNING id",
        {"n": f"SUM-sup-{suffix}", "lid": location_id},
    )
    batch_id = _db_exec_returning(
        "INSERT INTO batches (commodity_id, location_id, supplier_id, "
        "quantity_kg, harvested_at, temperature_log, freshness_score, "
        "safety_status) "
        "SELECT c.id, :lid, :s, 488.88, :h, CAST(:tl AS jsonb), 0.90, 'pending' "
        "FROM commodities c WHERE c.name='telur' RETURNING id",
        {
            "lid": location_id,
            "s": str(sup_id),
            "h": (NOW - timedelta(days=2)).isoformat(),
            "tl": __import__("json").dumps(log),
        },
    )
    return {
        "supplier_id": str(sup_id),
        "batch_id": str(batch_id),
        "suffix": suffix,
    }


def _cleanup_batch(b: dict) -> None:
    _db_exec("DELETE FROM batches WHERE id = :b", {"b": b["batch_id"]})
    _db_exec("DELETE FROM suppliers WHERE id = :s", {"s": b["supplier_id"]})


def _mk_decision(
    source_location_id: str,
    target_location_id: str,
    expires_minutes: int = 30,
    status: str = "pending_approval",
    commodity: str = "telur",
) -> str:
    """Decision uji target Jakarta (fixture DB langsung), komoditas bisa dipilih.

    Komoditas perlu bisa diganti sejak Fase 10: kiriman kanonik A Cianjur → Jakarta
    (telur) membuat pemasok keputusan telur Jakarta BISA disimpulkan dari batch
    sumber, sehingga skenario "pemasok tak diketahui" harus memakai komoditas yang
    memang belum punya kiriman ke Jakarta.
    """
    did = str(_db_exec_returning(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration) "
        "SELECT :id, 'regional_balance', :st, 'supervisor_agent', :src, :tgt, "
        "c.id, 488.88, 16206000.00, now() + make_interval(mins => :m), "
        "'{\"purchase\": \"15720000\"}'::jsonb, 1 "
        "FROM commodities c WHERE c.name=:komoditas RETURNING id",
        {
            "id": str(uuid.uuid4()),
            "st": status,
            "src": source_location_id,
            "tgt": target_location_id,
            "m": expires_minutes,
            "komoditas": commodity,
        },
    ))
    return did


def _bind_decision(decision_id: str, batch: dict) -> None:
    _db_exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (:d, 'human_inspection', CAST(:p AS jsonb))",
        {
            "d": decision_id,
            "p": __import__("json").dumps({
                "allocation_binding": True,
                "supplier_id": batch["supplier_id"],
                "batch_ids": [batch["batch_id"]],
            }),
        },
    )


def _cleanup_decision(decision_id: str) -> None:
    _db_exec(
        "DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d",
        {"d": decision_id},
    )
    _db_exec("DELETE FROM approvals WHERE decision_id = :d", {"d": decision_id})
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": decision_id})


def _jakarta_id() -> str:
    return str(_db_all("SELECT id FROM locations WHERE name='Jakarta'")[0][0])


def _bogor_id() -> str:
    return str(_db_all("SELECT id FROM locations WHERE name='Bogor'")[0][0])


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_approval_summary_unauth_401(client):
    resp = client.get(f"/decisions/{uuid.uuid4()}/approval-summary")
    assert resp.status_code == 401


def test_approval_summary_unknown_404(client):
    resp = client.get(
        f"/decisions/{uuid.uuid4()}/approval-summary",
        headers=_head_user(client),
    )
    assert resp.status_code == 404


def test_approval_summary_verifier_lintas_lokasi_403(client, far_nutritionist_headers):
    """Ruling 2026-10-14 MENGGANTIKAN ruling 2026-10-08: nutritionist Bogor
    TIDAK boleh membaca summary decision Jakarta.

    Alasan pencabutan ada di docs/ruling-2026-10-14-scope-lokasi.md: jalur
    tulis (POST /actions/approve) memang sudah terkunci ke lokasi sendiri,
    jadi jalur baca dibuat simetris dan matriks AND dua verifier berlaku di
    dalam satu SPPG.
    """
    did = _mk_decision(_jakarta_id(), _jakarta_id())
    try:
        resp = client.get(
            f"/decisions/{did}/approval-summary", headers=far_nutritionist_headers
        )
        assert resp.status_code == 403, resp.text
        assert "cakupan lokasi" in resp.json()["detail"]
    finally:
        _cleanup_decision(did)


def test_approval_summary_sppg_sendiri_tetap_200(client):
    """Yang tidak berubah: kepala SPPG membaca summary SPPG-nya sendiri."""
    did = _mk_decision(_jakarta_id(), _jakarta_id())
    try:
        resp = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision_id"] == did
    finally:
        _cleanup_decision(did)


def test_approval_summary_monitor_readonly_200(client):
    """bgn_monitor read-only TETAP boleh membaca summary (semua lokasi)."""
    did = _mk_decision(_jakarta_id(), _jakarta_id())
    try:
        resp = client.get(
            f"/decisions/{did}/approval-summary", headers=_monitor_user(client)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision_id"] == did
    finally:
        _cleanup_decision(did)


def test_approval_summary_canonical_fields(client):
    """Field kanonik tampil dari DB; verifier UNAVAILABLE → AND matrix."""
    did = _mk_decision(_jakarta_id(), _jakarta_id())
    try:
        # Verifikasi server-side (test env tanpa provider → UNAVAILABLE).
        rv = client.post(
            "/actions/verify", headers=_head_user(client), json={"decision_id": did}
        )
        assert rv.status_code == 200, rv.text
        resp = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Identitas decision.
        assert body["decision_id"] == did
        assert body["decision_type"] == "regional_balance"
        assert body["iteration"] >= 1
        assert body["status"] == "pending_approval"
        # Konteks material.
        assert body["source_location"] == "Jakarta"
        assert body["target_location"] == "Jakarta"
        assert body["commodity"] == "telur"
        assert body["quantity_kg"] == 488.88
        assert body["safe_delivered_cost"] is not None
        assert body["cost_breakdown"] is not None
        assert body["execution_target"] == "MOCK"
        assert body["material_number"] == "MAT-TELUR"
        # Sejak Fase 10 ada kiriman kanonik Supplier A Cianjur → Jakarta (telur), jadi
        # pemasok untuk keputusan telur Jakarta BISA disimpulkan dari batch sumber
        # (satu pemasok, tidak ambigu). Aturan "jangan menebak pemasok" tetap berlaku
        # dan diuji di test_approval_summary_or_complete_then_execute_parity[missing]
        # lewat komoditas yang memang belum punya kiriman ke Jakarta.
        assert body["supplier"]["name"] == "Supplier A Cianjur"
        assert not any("supplier_unknown" in r for r in body["blocking_reasons"])
        # Verifier hasil server (bukan karangan UI).
        assert body["verifier"]["verdict"] in {
            "consistent",
            "flagged",
            "unavailable",
        }
        # Matrix UNAVAILABLE → dua grup AND.
        assert body["approval_requirement"]["min_approvals"] == 2
        # Belum ada approval → missing lengkap + can_execute false.
        assert body["approval_state"]["satisfied"] is False
        assert len(body["approval_state"]["missing"]) == 2
        assert body["approvals"] == []
        assert body["can_execute"] is False
        assert body["can_approve"] is True
        assert body["blocking_reasons"]
        # Expiry kanonik.
        assert body["expiry"]["valid"] is True
        assert body["expiry"]["seconds_remaining"] > 0
    finally:
        _cleanup_decision(did)


@pytest.mark.parametrize("binding", ["explicit", "missing"])
def test_approval_summary_or_complete_then_execute_parity(client, binding):
    """Only a bound transfer promises a supplier and can execute."""
    batch = _mk_batch(_bogor_id(), fail=False) if binding == "explicit" else None
    # "missing" sengaja memakai komoditas AYAM: kiriman kanonik ke Jakarta hanya telur,
    # jadi tidak ada satu pun batch sumber yang bisa dipakai menyimpulkan pemasok.
    did = (
        _mk_decision(_bogor_id(), _jakarta_id())
        if batch
        else _mk_decision(_jakarta_id(), _jakarta_id(), commodity="ayam")
    )
    try:
        if batch:
            _bind_decision(did, batch)
        # Verifikasi + verdict konsisten (fixture DB level, server verdict).
        client.post(
            "/actions/verify", headers=_head_user(client), json={"decision_id": did}
        )
        _db_exec(
            "UPDATE decisions SET verifier_note='consistent' WHERE id=:d",
            {"d": did},
        )
        # Approval satu role (OR).
        ra = client.post(
            "/actions/approve",
            headers=_head_user(client),
            json={"decision_id": did, "approved": True},
        )
        assert ra.status_code == 200, ra.text

        summary = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        ).json()
        assert summary["approval_state"]["satisfied"] is True
        if binding == "missing":
            rx = client.post(
                "/actions/execute", headers=_head_user(client), json={"decision_id": did}
            )
            assert rx.status_code == 409, rx.text
            assert "supplier_unknown" in rx.json()["detail"]
            assert summary["can_execute"] is False
            assert summary["supplier"] is None
            assert rx.json()["detail"] in summary["blocking_reasons"]
            assert not _db_all(
                "SELECT id FROM sap_mock_purchase_orders WHERE decision_id=:d", {"d": did}
            )
            return
        assert summary["supplier"]["id"] == batch["supplier_id"]
        assert summary["can_execute"] is True
        assert summary["can_approve"] is True
        assert summary["approvals"], "approval tercatat harus tampil"
        assert summary["approvals"][0]["role"] == "sppg_head"
        assert summary["approvals"][0]["approved"] is True

        # Execute → PO parity dengan summary.
        rx = client.post(
            "/actions/execute", headers=_head_user(client), json={"decision_id": did}
        )
        assert rx.status_code == 200, rx.text
        po = _db_all(
            "SELECT s.name, p.material_number, p.ordered_quantity, p.status "
            "FROM sap_mock_purchase_orders p JOIN suppliers s ON s.id=p.supplier_id "
            "WHERE p.decision_id = :d",
            {"d": did},
        )
        assert po, "PO mock harus tercipta"
        assert po[0][0] == summary["supplier"]["name"]
        assert po[0][1] == summary["material_number"]
        assert float(po[0][2]) == summary["quantity_kg"]
        assert po[0][3] == "submitted"
    finally:
        _cleanup_decision(did)
        if batch:
            _cleanup_batch(batch)


def test_approval_summary_dual_missing_role(client):
    """Same role dua kali TIDAK memenuhi AND matrix; missing role tampil."""
    did = _mk_decision(_bogor_id(), _jakarta_id())
    try:
        client.post(
            "/actions/verify", headers=_head_user(client), json={"decision_id": did}
        )
        # Dua approval dari role SAMA (dua user head berbeda dari DB).
        users = _db_all(
            "SELECT id FROM users WHERE role='sppg_head' ORDER BY id LIMIT 2"
        )
        assert len(users) == 2
        for (uid,) in users:
            _db_exec(
                "INSERT INTO approvals (decision_id, approved_by, approved) "
                "VALUES (:d, :u, True)",
                {"d": did, "u": str(uid)},
            )
        summary = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        ).json()
        # verdict UNAVAILABLE → dua grup AND; dua head tidak memenuhi grup
        # nutritionist.
        assert summary["approval_state"]["satisfied"] is False
        assert summary["approval_state"]["missing"] == [["sppg_nutritionist"]]
        assert summary["can_execute"] is False
        roles = {a["role"] for a in summary["approvals"]}
        assert roles == {"sppg_head"}
    finally:
        _cleanup_decision(did)


def test_approval_summary_expired_blocks(client):
    """Decision expired → valid false + blocking + can_execute false."""
    did = _mk_decision(_jakarta_id(), _jakarta_id(), expires_minutes=-10)
    try:
        _db_exec(
            "UPDATE decisions SET verifier_note='consistent' WHERE id=:d",
            {"d": did},
        )
        users = _db_all(
            "SELECT id FROM users WHERE role='sppg_head' ORDER BY id LIMIT 1"
        )
        _db_exec(
            "INSERT INTO approvals (decision_id, approved_by, approved) "
            "VALUES (:d, :u, True)",
            {"d": did, "u": str(users[0][0])},
        )
        summary = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        ).json()
        assert summary["expiry"]["valid"] is False
        assert summary["expiry"]["seconds_remaining"] == 0
        assert summary["can_execute"] is False
        assert any("expired" in r.lower() for r in summary["blocking_reasons"])
    finally:
        _cleanup_decision(did)


def test_approval_summary_safety_revalidation_block(client):
    """Batch sumber kini FAIL → summary menandai safety block + can_execute
    false — sejajar dengan revalidation hook execute (O-EVENT-2)."""
    suffix = uuid.uuid4().hex[:8]
    loc_id = str(_db_exec_returning(
        "INSERT INTO locations (name, region, latitude, longitude) "
        "VALUES (:n, 'Test', -6.9, 107.6) RETURNING id",
        {"n": f"SUM-src-{suffix}"},
    ))
    b = _mk_batch(loc_id, fail=False)
    did = _mk_decision(loc_id, _jakarta_id())
    try:
        _db_exec(
            "UPDATE decisions SET verifier_note='consistent' WHERE id=:d",
            {"d": did},
        )
        users = _db_all(
            "SELECT id FROM users WHERE role='sppg_head' ORDER BY id LIMIT 1"
        )
        _db_exec(
            "INSERT INTO approvals (decision_id, approved_by, approved) "
            "VALUES (:d, :u, True)",
            {"d": did, "u": str(users[0][0])},
        )
        # Summary saat batch masih aman → tidak ada safety block.
        s1 = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        ).json()
        assert s1["safety"]["blocked"] is False
        # Batch jadi FAIL (event 3 setelah decision dibuat).
        _db_exec(
            "UPDATE batches SET safety_status='fail' WHERE id=:b",
            {"b": b["batch_id"]},
        )
        s2 = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        ).json()
        assert s2["safety"]["blocked"] is True
        assert s2["safety"]["worst_status"] == "fail"
        assert s2["can_execute"] is False
        assert any("safety" in r.lower() for r in s2["blocking_reasons"])
    finally:
        _cleanup_decision(did)
        _cleanup_batch(b)
        _db_exec("DELETE FROM locations WHERE id = :l", {"l": loc_id})


def test_approval_summary_missing_facts_null_not_fake(client):
    """Decision tanpa lokasi/komoditas → field null + safety unavailable,
    BUKAN default palsu.

    Catatan cakupan (Ruling 2026-10-14): baris tanpa lokasi TUJUAN tidak
    dimiliki SPPG mana pun, jadi hanya bgn_monitor yang boleh membacanya;
    kepala SPPG menerima 403 (bukan 200 dengan tebakan lokasi).
    """
    did = str(_db_exec_returning(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "expires_at, iteration) VALUES (:id, 'price_anomaly', "
        "'pending_approval', 'supervisor_agent', "
        "now() + interval '30 minutes', 1) RETURNING id",
        {"id": str(uuid.uuid4())},
    ))
    try:
        _db_exec(
            "UPDATE decisions SET verifier_note='consistent', "
            "verified_by='verifier_agent' WHERE id=:d",
            {"d": did},
        )
        users = _db_all(
            "SELECT id FROM users WHERE role='sppg_head' ORDER BY id LIMIT 1"
        )
        _db_exec(
            "INSERT INTO approvals (decision_id, approved_by, approved) "
            "VALUES (:d, :u, True)",
            {"d": did, "u": str(users[0][0])},
        )
        assert (
            client.get(
                f"/decisions/{did}/approval-summary", headers=_head_user(client)
            ).status_code
            == 403
        )
        summary = client.get(
            f"/decisions/{did}/approval-summary", headers=_monitor_user(client)
        ).json()
        assert summary["source_location"] is None
        assert summary["commodity"] is None
        assert summary["supplier"] is None
        assert summary["material_number"] is None
        assert summary["safety"]["blocked"] is False
        assert summary["safety"]["worst_status"] is None
        assert summary["can_execute"] is False
        assert any("supplier_unknown" in r for r in summary["blocking_reasons"])
    finally:
        _cleanup_decision(did)


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Parity summary ↔ execute (temuan audit 2026-10-11)
# ---------------------------------------------------------------------------


def _siapkan_verified_approved(did: str) -> None:
    """Loloskan prasyarat execute: terverifikasi + approval memenuhi matriks."""
    _db_exec(
        "UPDATE decisions SET verifier_note='consistent', "
        "verified_by='verifier_agent' WHERE id=:d",
        {"d": did},
    )
    users = _db_all("SELECT id FROM users WHERE role='sppg_head' ORDER BY id LIMIT 1")
    _db_exec(
        "INSERT INTO approvals (decision_id, approved_by, approved) VALUES (:d, :u, True)",
        {"d": did, "u": str(users[0][0])},
    )


def _sumber_baru(prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    return str(
        _db_exec_returning(
            "INSERT INTO locations (name, region, latitude, longitude) "
            "VALUES (:n, 'Test', -6.9, 107.6) RETURNING id",
            {"n": f"{prefix}-{suffix}"},
        )
    )


def _ikat_batch(decision_id: str, supplier_id: str, batch_ids: list) -> None:
    """Binding eksplisit (allocation_binding) satu supplier + N batch."""
    _db_exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (:d, 'human_inspection', CAST(:p AS jsonb))",
        {
            "d": decision_id,
            "p": __import__("json").dumps({
                "allocation_binding": True,
                "supplier_id": supplier_id,
                "batch_ids": batch_ids,
            }),
        },
    )


def test_approval_summary_parity_execute_batch_sumber_campuran(client):
    """Parity can_execute ↔ execute saat batch terikat CAMPURAN (1 FAIL, 1 aman).

    Guard execute (supplier_eligibility.revalidate_transfer) memblokir bila ADA
    batch terikat yang FAIL, sedangkan approval-summary dulu memakai `all(...)`
    sehingga hanya memblokir bila SEMUA batch sumber FAIL. Akibatnya summary
    menjanjikan can_execute=true padahal POST /actions/execute membalas 409.
    """
    src = _sumber_baru("SUM-mix")
    b1 = _mk_batch(src, fail=False)
    b2 = _mk_batch(src, fail=False)
    # Satu supplier untuk kedua batch — prasyarat binding valid.
    _db_exec(
        "UPDATE batches SET supplier_id=:s WHERE id=:b",
        {"s": b1["supplier_id"], "b": b2["batch_id"]},
    )
    did = _mk_decision(src, _jakarta_id())
    try:
        _siapkan_verified_approved(did)
        _ikat_batch(did, b1["supplier_id"], [b1["batch_id"], b2["batch_id"]])
        # Hanya satu dari dua batch terikat yang FAIL.
        _db_exec(
            "UPDATE batches SET safety_status='fail' WHERE id=:b",
            {"b": b2["batch_id"]},
        )
        summary = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        ).json()
        eksekusi = client.post(
            "/actions/execute", json={"decision_id": did}, headers=_head_user(client)
        )
        assert eksekusi.status_code == 409, eksekusi.text
        assert "safety" in eksekusi.json()["detail"].lower()
        # Inti bug: summary TIDAK boleh mengaku bisa dieksekusi.
        assert summary["safety"]["blocked"] is True, summary["safety"]
        assert summary["can_execute"] is False, summary
    finally:
        _cleanup_decision(did)
        # b2 dulu: batch-nya memakai supplier milik b1 (FK batches.supplier_id).
        _cleanup_batch(b2)
        _cleanup_batch(b1)
        _db_exec("DELETE FROM suppliers WHERE name=:n", {"n": f"SUM-sup-{b2['suffix']}"})
        _db_exec("DELETE FROM locations WHERE id = :l", {"l": src})


def test_approval_summary_parity_execute_batch_terikat_hilang(client):
    """Batch terikat hilang (dikonsumsi) → execute 409, summary blocked.

    Keadaan ini hanya terlihat oleh cek safety batch sumber, jadi kalau summary
    mengabaikannya, UI menampilkan tombol eksekusi untuk aksi yang pasti gagal.
    """
    src = _sumber_baru("SUM-hilang")
    b1 = _mk_batch(src, fail=False)
    did = _mk_decision(src, _jakarta_id())
    try:
        _siapkan_verified_approved(did)
        _ikat_batch(did, b1["supplier_id"], [b1["batch_id"]])
        _db_exec("DELETE FROM batches WHERE id=:b", {"b": b1["batch_id"]})
        summary = client.get(
            f"/decisions/{did}/approval-summary", headers=_head_user(client)
        ).json()
        eksekusi = client.post(
            "/actions/execute", json={"decision_id": did}, headers=_head_user(client)
        )
        assert eksekusi.status_code != 200, eksekusi.text
        assert summary["safety"]["blocked"] is True, summary["safety"]
        assert summary["can_execute"] is False, summary
        # Tidak ada batch → tidak ada status untuk dilaporkan (jangan mengarang).
        assert summary["safety"]["worst_status"] is None
    finally:
        _cleanup_decision(did)
        _cleanup_batch(b1)
        _db_exec("DELETE FROM locations WHERE id = :l", {"l": src})
