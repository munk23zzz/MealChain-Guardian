"""Penerimaan manusia atas bukti batch (Fase 6 butir 3 & 5).

Kontrak yang dikunci berkas ini (MG/phase-06-decision-boundary.md):

1. `POST /decisions/{id}/review` menuntut **alasan** dan **bukti**; tanpa itu
   → 422. Identitas reviewer dan waktu TIDAK boleh dipasok klien (server yang
   mencatat), jadi upaya memalsukannya juga 422.
2. Review yang sah mencatat `DecisionEvidence` bertipe `human_inspection`
   berisi reviewer, waktu, alasan, referensi bukti, dan sampel suhu yang
   ditambahkan.
3. Review hanya boleh mengubah `batch.safety_status` bila BUKTI memenuhi profil
   komoditas (`needs_verification` → `pass` hasil evaluasi ulang). Teks reviewer
   tidak pernah menjadi dasar `pass`; tanpa bukti baru status tetap.
4. Verdict LLM (`verifier_note=consistent`) TIDAK dapat menggantikan bukti
   manusia: batch tetap `on_hold` dan `human_reviews` kosong.
5. `bgn_monitor` tetap read-only (403).

DB: file ini membuat barisnya sendiri (user, batch, keputusan, bukti) lalu
menghapusnya lagi; tidak bergantung pada data demo.
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
LOG_RUSAK = []  # rantai dingin tanpa satu pun sampel → bukti tidak cukup


# ---------------------------------------------------------------------------
# Helper DB
# ---------------------------------------------------------------------------


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
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-f6-review.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    _exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "SELECT :i, 'Uji F6 review', :e, :h, :r, "
        "CASE WHEN :k IS NULL THEN NULL ELSE l.id END "
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


def _buat_batch(
    *,
    kota: str = "Jakarta",
    komoditas: str = "telur",
    safety_status: str = "needs_verification",
    temperature_log: list | None = None,
    quantity_kg: float = 150,
) -> dict:
    bid = str(uuid.uuid4())
    log = LOG_RUSAK if temperature_log is None else temperature_log
    _exec(
        "INSERT INTO batches (id, commodity_id, location_id, supplier_id, "
        "quantity_kg, harvested_at, temperature_log, certification_status, "
        "freshness_score, safety_status, usable_until, quarantine_status, origin) "
        "VALUES (CAST(:i AS uuid), CAST(:c AS uuid), CAST(:l AS uuid), "
        "CAST(:s AS uuid), :kg, :h, CAST(:t AS jsonb), 'hygiene', 0.95, :ss, "
        ":uu, 'none', 'demo')",
        {
            "i": bid,
            "c": _komoditas(komoditas),
            "l": _lokasi(kota),
            "s": _supplier(),
            "kg": quantity_kg,
            "h": datetime.now(UTC) - timedelta(hours=6),
            "t": json.dumps(log),
            "ss": safety_status,
            "uu": datetime.now(UTC) + timedelta(days=4),
        },
    )
    return {
        "batch_id": bid,
        "location_id": _lokasi(kota),
        "commodity_id": _komoditas(komoditas),
        "supplier_id": _supplier(),
    }


def _hapus_batch(batch_id: str) -> None:
    _exec("DELETE FROM batches WHERE id = CAST(:b AS uuid)", {"b": batch_id})


def _buat_keputusan(
    batch: dict,
    *,
    status: str = "pending_approval",
    verifier_note: str = "consistent",
    verified_by: str | None = "verifier_agent",
) -> str:
    did = str(uuid.uuid4())
    _exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
        "verified_by, verifier_note, supplier_id) "
        "VALUES (CAST(:i AS uuid), 'regional_balance', :st, 'supervisor_agent', "
        "CAST(:src AS uuid), CAST(:tgt AS uuid), CAST(:kom AS uuid), 150, "
        "2250000, now() + interval '45 minutes', CAST(:cb AS jsonb), 1, "
        ":vb, :vn, CAST(:sup AS uuid))",
        {
            "i": did,
            "st": status,
            "src": batch["location_id"],
            "tgt": _lokasi("Jakarta"),
            "kom": batch["commodity_id"],
            "sup": batch["supplier_id"],
            "cb": json.dumps(
                {
                    "purchase": "2250000.00",
                    "transport": "45000.00",
                    "handling": "150000.00",
                    "expected_loss": "30000.00",
                    "freshness_risk": "0.00",
                    "safety_penalty": "0.00",
                }
            ),
            "vb": verified_by,
            "vn": verifier_note,
        },
    )
    # Binding batch/supplier: jalur yang dipakai execute & `batch_sumber_transfer`.
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
    return did


def _hapus_keputusan(decision_id: str) -> None:
    # decision_evidence / approvals / agent_traces ikut terhapus (FK CASCADE).
    _exec("DELETE FROM decisions WHERE id = CAST(:d AS uuid)", {"d": decision_id})


def _hapus_user(user: dict | None) -> None:
    if not user:
        return
    _exec("DELETE FROM approvals WHERE approved_by = CAST(:i AS uuid)", {"i": user["id"]})
    _exec("DELETE FROM users WHERE id = CAST(:i AS uuid)", {"i": user["id"]})


def _status_batch(batch_id: str) -> str:
    return str(
        _scalar(
            "SELECT safety_status FROM batches WHERE id = CAST(:b AS uuid)",
            {"b": batch_id},
        )
    )


def _log_batch(batch_id: str) -> list:
    raw = _scalar(
        "SELECT temperature_log FROM batches WHERE id = CAST(:b AS uuid)",
        {"b": batch_id},
    )
    return json.loads(raw) if isinstance(raw, str) else list(raw or [])


def _evidence_review(decision_id: str) -> list[dict]:
    rows = _exec(
        "SELECT payload FROM decision_evidence WHERE decision_id = CAST(:d AS uuid) "
        "AND evidence_type = 'human_inspection' ORDER BY recorded_at",
        {"d": decision_id},
    )
    return [json.loads(r[0]) if isinstance(r[0], str) else r[0] for r in rows]


def _payload_review(batch: dict, **ubah) -> dict:
    data = {
        "batch_id": batch["batch_id"],
        "reason": "Sampel suhu gudang diperiksa ulang; hasil sesuai rentang dingin.",
        "evidence_refs": ["inspeksi-gudang-2026-10-27", "berita-acara-suhu-27"],
        "temperature_samples": [
            {
                "timestamp": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
                "temperature_c": 4.1,
            },
            {
                "timestamp": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                "temperature_c": 4.4,
            },
        ],
    }
    data.update(ubah)
    return data


@pytest.fixture()
def klien():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def aktor():
    """Kepala SPPG + Nutritionist Jakarta (boleh review) + monitor nasional."""
    dibuat = []
    try:
        head = _mk_user("sppg_head")
        nut = _mk_user("sppg_nutritionist")
        mon = _mk_user("bgn_monitor", kota="")
        dibuat = [head, nut, mon]
        yield {"head": head, "nutritionist": nut, "monitor": mon}
    finally:
        for u in dibuat:
            _hapus_user(u)


@pytest.fixture()
def kasus():
    """Satu batch `needs_verification` (Bandung → Jakarta) + keputusan terikat."""
    batch = _buat_batch(kota="Bandung")
    decision_id = _buat_keputusan(batch)
    try:
        yield {"batch": batch, "decision_id": decision_id}
    finally:
        _hapus_keputusan(decision_id)
        _hapus_batch(batch["batch_id"])


# ---------------------------------------------------------------------------
# Butir 3 — review tanpa alasan/bukti/identitas ditolak 422
# ---------------------------------------------------------------------------


def test_review_tanpa_alasan_ditolak_422(klien, aktor, kasus) -> None:
    h = _login(klien, aktor["head"])
    for alasan in ("", "aman"):
        resp = klien.post(
            f"/decisions/{kasus['decision_id']}/review",
            headers=h,
            json=_payload_review(kasus["batch"], reason=alasan),
        )
        assert resp.status_code == 422, resp.text
    assert _status_batch(kasus["batch"]["batch_id"]) == "needs_verification"
    assert len(_evidence_review(kasus["decision_id"])) == 1  # hanya binding


def test_review_tanpa_referensi_bukti_ditolak_422(klien, aktor, kasus) -> None:
    h = _login(klien, aktor["head"])
    for refs in ([], [""]):
        resp = klien.post(
            f"/decisions/{kasus['decision_id']}/review",
            headers=h,
            json=_payload_review(kasus["batch"], evidence_refs=refs),
        )
        assert resp.status_code == 422, resp.text


def test_review_tidak_boleh_memalsukan_reviewer_dan_waktu(klien, aktor, kasus) -> None:
    """Reviewer & waktu dicatat server; klien yang mencoba memasoknya ditolak."""
    h = _login(klien, aktor["head"])
    resp = klien.post(
        f"/decisions/{kasus['decision_id']}/review",
        headers=h,
        json=_payload_review(
            kasus["batch"],
            reviewed_by=str(uuid.uuid4()),
            reviewed_at="2020-01-01T00:00:00+00:00",
        ),
    )
    assert resp.status_code == 422, resp.text


def test_bgn_monitor_tidak_boleh_mereview(klien, aktor, kasus) -> None:
    h = _login(klien, aktor["monitor"])
    resp = klien.post(
        f"/decisions/{kasus['decision_id']}/review",
        headers=h,
        json=_payload_review(kasus["batch"]),
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Butir 3 & 5 — review sah mencatat bukti; status hanya berubah bila bukti cukup
# ---------------------------------------------------------------------------


def test_review_sah_mencatat_decision_evidence_dan_mengubah_status(klien, aktor, kasus) -> None:
    h = _login(klien, aktor["head"])
    resp = klien.post(
        f"/decisions/{kasus['decision_id']}/review",
        headers=h,
        json=_payload_review(kasus["batch"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["safety_status_before"] == "needs_verification"
    assert body["safety_status_after"] == "pass"
    assert body["status_changed"] is True
    assert body["evidence_state"] == "sufficient"
    assert body["reviewed_by_user_id"] == aktor["head"]["id"]

    assert _status_batch(kasus["batch"]["batch_id"]) == "pass"
    assert len(_log_batch(kasus["batch"]["batch_id"])) == 2

    ulasan = [p for p in _evidence_review(kasus["decision_id"]) if p.get("review_reason")]
    assert len(ulasan) == 1, ulasan
    baris = ulasan[0]
    assert baris["reviewed_by_user_id"] == aktor["head"]["id"]
    assert baris["reviewed_at"]
    assert baris["evidence_refs"] == [
        "inspeksi-gudang-2026-10-27",
        "berita-acara-suhu-27",
    ]
    assert baris["batch_id"] == kasus["batch"]["batch_id"]
    assert baris["safety_status_after"] == "pass"
    assert baris["policy_version"]


def test_review_tanpa_bukti_baru_tidak_mengubah_status(klien, aktor, kasus) -> None:
    """Teks reviewer bukan bukti: tanpa sampel, batch tetap `needs_verification`."""
    h = _login(klien, aktor["nutritionist"])
    resp = klien.post(
        f"/decisions/{kasus['decision_id']}/review",
        headers=h,
        json=_payload_review(kasus["batch"], temperature_samples=[]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status_changed"] is False
    assert body["safety_status_after"] == "needs_verification"
    assert body["evidence_state"] != "sufficient"
    assert body["next_step"], "on_hold harus menyebut langkah verifikasi berikutnya"
    assert _status_batch(kasus["batch"]["batch_id"]) == "needs_verification"


def test_review_batch_di_luar_binding_ditolak(klien, aktor, kasus) -> None:
    lain = _buat_batch(safety_status="needs_verification")
    try:
        h = _login(klien, aktor["head"])
        resp = klien.post(
            f"/decisions/{kasus['decision_id']}/review",
            headers=h,
            json=_payload_review(lain, batch_id=lain["batch_id"]),
        )
        assert resp.status_code == 409, resp.text
        assert _status_batch(lain["batch_id"]) == "needs_verification"
    finally:
        _hapus_batch(lain["batch_id"])


def test_batch_fail_tidak_dapat_direview_menjadi_aman(klien, aktor) -> None:
    """`fail` adalah keputusan mesin; review tidak boleh membalikkannya."""
    batch = _buat_batch(safety_status="fail")
    decision_id = _buat_keputusan(batch)
    try:
        h = _login(klien, aktor["head"])
        resp = klien.post(
            f"/decisions/{decision_id}/review",
            headers=h,
            json=_payload_review(batch),
        )
        assert resp.status_code == 409, resp.text
        assert _status_batch(batch["batch_id"]) == "fail"
    finally:
        _hapus_keputusan(decision_id)
        _hapus_batch(batch["batch_id"])


# ---------------------------------------------------------------------------
# Butir 3 — verdict LLM bukan bukti manusia
# ---------------------------------------------------------------------------


def test_verdict_llm_tidak_menggantikan_bukti_manusia(klien, aktor, kasus) -> None:
    h = _login(klien, aktor["head"])
    packet = klien.get(f"/decisions/{kasus['decision_id']}/packet", headers=h)
    assert packet.status_code == 200, packet.text
    data = packet.json()

    assert data["review"]["verifier"]["verdict"] == "consistent"
    assert data["review"]["human_reviews"] == [], "verdict LLM tidak membuat bukti manusia"
    tahan = [b for b in data["batch_evaluations"] if b["batch_id"] == kasus["batch"]["batch_id"]]
    assert tahan and tahan[0]["status"] == "on_hold"
    assert tahan[0]["blocking_reasons"]


# ---------------------------------------------------------------------------
# Butir 5 — review disimpan, lalu kelayakan DIHITUNG ULANG (bukan hanya kolom)
# ---------------------------------------------------------------------------


def test_review_diikuti_evaluasi_ulang_pada_paket_keputusan(klien, aktor, kasus) -> None:
    """Sesudah review sah, paket keputusan menunjukkan batch itu LAYAK.

    Butir 5 menuntut re-evaluasi: yang berubah bukan hanya `batches.safety_status`
    tetapi kesimpulan gerbang yang dibaca dispatch/PO. Kalau hanya kolomnya yang
    berubah, layar tetap menampilkan `on_hold` sesudah review dan keputusan berikutnya
    memakai kesimpulan lama.
    """
    h = _login(klien, aktor["head"])
    id_batch = kasus["batch"]["batch_id"]

    sebelum = klien.get(f"/decisions/{kasus['decision_id']}/packet", headers=h).json()
    baris = [b for b in sebelum["batch_evaluations"] if b["batch_id"] == id_batch][0]
    assert baris["status"] == "on_hold", baris
    assert baris["blocking_reasons"], baris
    assert baris["next_step"], "on_hold harus menyebut langkah verifikasi berikutnya"

    resp = klien.post(
        f"/decisions/{kasus['decision_id']}/review",
        headers=h,
        json=_payload_review(kasus["batch"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status_changed"] is True

    sesudah = klien.get(f"/decisions/{kasus['decision_id']}/packet", headers=h).json()
    ulang = [b for b in sesudah["batch_evaluations"] if b["batch_id"] == id_batch][0]
    assert ulang["status"] == "usable", ulang
    assert ulang["blocking_reasons"] == [], ulang
    assert ulang["next_step"] in (None, ""), ulang
    # Review manusia muncul pada read model yang SAMA (bukan tabel terpisah).
    assert len(sesudah["review"]["human_reviews"]) == 1
    assert sesudah["review"]["human_reviews"][0]["batch_id"] == id_batch
