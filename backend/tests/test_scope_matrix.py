"""Matriks cakupan lokasi per peran — Ruling 2026-10-14.

Uji ini menjaga janji yang paling mudah rusak diam-diam: "kepala SPPG hanya
melihat SPPG-nya sendiri". Karena itu ia memeriksa **pasangan** untuk setiap
permukaan baca — kepala SPPG Jakarta (harus ditolak untuk lokasi lain) dan
bgn_monitor (harus lolos, read-only nasional) — bukan salah satu saja.

Aturan yang dipegang test ini:
- lokasi TUJUAN terkunci ke `user.location_id` untuk peran SPPG;
- `bgn_monitor` tetap lintas lokasi (pengawasan nasional) — tapi tidak menulis;
- peran SPPG tanpa lokasi = 403 (gagal-tertutup).

Catatan data: seluruh 128 keputusan seed menyasar Jakarta, jadi "keputusan
asing" disiapkan sementara di sini (dan dihapus lagi). Lokasi lain yang dipakai
untuk uji baca-per-lokasi adalah kota pertama non-Jakarta yang punya data
demand — Bandung/Cianjur tidak punya demand_records sehingga endpoint-nya
membalas 404 dan itu bukan soal cakupan.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DSN = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(DSN)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def geo(db_engine):
    """Jakarta + satu kota lain yang punya data supply/demand/price lengkap."""
    with db_engine.begin() as conn:
        jakarta = conn.execute(
            text("SELECT id, name FROM locations WHERE name = 'Jakarta'")
        ).one()
        other = conn.execute(
            text(
                "SELECT l.id, l.name FROM locations l "
                "WHERE l.name <> 'Jakarta' AND EXISTS ("
                "  SELECT 1 FROM demand_records d WHERE d.location_id = l.id) "
                "ORDER BY l.name LIMIT 1"
            )
        ).one()
        telur = conn.execute(
            text("SELECT id FROM commodities WHERE name = 'telur'")
        ).scalar_one()
    return {
        "jakarta_id": str(jakarta.id),
        "jakarta_name": jakarta.name,
        "other_id": str(other.id),
        "other_name": other.name,
        "commodity_id": str(telur),
    }


@pytest.fixture(scope="module")
def foreign_decision(db_engine, geo):
    """Keputusan sementara ber-target lokasi lain (di luar cakupan kepala Jakarta)."""
    new_id = uuid.uuid4()
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                "source_location_id, target_location_id, commodity_id, quantity_kg, "
                "safe_delivered_cost, expires_at) "
                "VALUES (:i, 'regional_balance', 'pending_approval', 'supervisor_agent', "
                ":src, :tgt, :com, 100.00, 2700000.00, now() + interval '3 hours')"
            ),
            {
                "i": str(new_id),
                "src": str(geo["jakarta_id"]),
                "tgt": str(geo["other_id"]),
                "com": str(geo["commodity_id"]),
            },
        )
    yield str(new_id)
    with db_engine.begin() as conn:
        conn.execute(text("DELETE FROM decisions WHERE id = :i"), {"i": str(new_id)})


@pytest.fixture(scope="module")
def jakarta_decisions(db_engine, geo):
    with db_engine.begin() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT id FROM decisions WHERE target_location_id = :j "
                    "ORDER BY created_at DESC LIMIT 3"
                ),
                {"j": str(geo["jakarta_id"])},
            )
            .scalars()
            .all()
        )
    return [str(r) for r in rows]


def _feed_ids(client, headers) -> list[str]:
    r = client.get("/decisions", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body, list(body)
    return [item["decision_id"] for item in body["items"]]


# --------------------------------------------------------------- daftar/feed


def test_feed_kepala_tidak_memuat_keputusan_lokasi_lain(
    client, auth_headers, foreign_decision
):
    ids = _feed_ids(client, auth_headers)
    assert ids, "feed kepala SPPG kosong — seed harus punya keputusan Jakarta"
    assert foreign_decision not in ids, "feed bocor: keputusan SPPG lain terlihat"


def test_feed_monitor_memuat_keputusan_lokasi_lain(client, monitor_headers, foreign_decision):
    ids = _feed_ids(client, monitor_headers)
    assert foreign_decision in ids, "bgn_monitor harus tetap melihat seluruh lokasi"


def test_feed_monitor_lebih_luas_daripada_kepala(client, auth_headers, monitor_headers):
    assert len(_feed_ids(client, monitor_headers)) > len(_feed_ids(client, auth_headers)) - 1


# ------------------------------------------------------- baca satu keputusan


def test_keputusan_asing_ditolak_untuk_kepala(client, auth_headers, foreign_decision):
    r = client.get(f"/decisions/{foreign_decision}", headers=auth_headers)
    assert r.status_code == 403, r.text
    assert "cakupan lokasi" in r.json()["detail"]


def test_keputusan_asing_terbaca_untuk_monitor(client, monitor_headers, foreign_decision):
    r = client.get(f"/decisions/{foreign_decision}", headers=monitor_headers)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "path",
    [
        "/decisions/{id}/approval-summary",
        "/decisions/{id}/traces",
        "/decisions/{id}/chain",
        "/decisions/{id}/dossier",
        "/decisions/{id}/compliance",
        "/supplier-exclusions/context/{id}",
    ],
)
def test_permukaan_baca_keputusan_ikut_terkunci(client, auth_headers, foreign_decision, path):
    """Ruling 2026-10-14 mencabut pengecualian VERIFIER_ROLES dari 2026-10-08:
    approver TIDAK lagi boleh membaca detail keputusan SPPG lain."""
    r = client.get(path.format(id=foreign_decision), headers=auth_headers)
    assert r.status_code == 403, f"{path} → {r.status_code}: {r.text[:200]}"


def test_keputusan_sendiri_tetap_terbaca(client, auth_headers, jakarta_decisions):
    assert jakarta_decisions, "seed harus punya keputusan Jakarta"
    for did in jakarta_decisions:
        r = client.get(f"/decisions/{did}", headers=auth_headers)
        assert r.status_code == 200, r.text


# ------------------------------------------------- baca data per lokasi (GET)


@pytest.mark.parametrize(
    "template",
    [
        "/balance/{other}/telur",
        "/supply/{other}/telur",
        "/demand/{other}/telur",
        "/demand/forecast/{other}/telur?horizon_days=7",
        "/price/{other}/telur",
        "/price/quotes/{other}/telur",
    ],
)
def test_data_lokasi_asing_ditolak(client, auth_headers, geo, template):
    path = template.format(other=geo["other_name"])
    r = client.get(path, headers=auth_headers)
    assert r.status_code == 403, f"{path} → {r.status_code}: {r.text[:200]}"


@pytest.mark.parametrize(
    "template",
    [
        "/balance/{other}/telur",
        "/supply/{other}/telur",
        "/demand/{other}/telur",
        "/price/{other}/telur",
    ],
)
def test_data_lokasi_asing_terbaca_monitor(client, monitor_headers, geo, template):
    path = template.format(other=geo["other_name"])
    r = client.get(path, headers=monitor_headers)
    assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"


@pytest.mark.parametrize(
    "path",
    [
        "/balance/Jakarta/telur",
        "/supply/Jakarta/telur",
        "/demand/Jakarta/telur",
        "/demand/forecast/Jakarta/telur?horizon_days=7",
        "/price/Jakarta/telur",
        "/price/quotes/Jakarta/telur",
    ],
)
def test_data_lokasi_sendiri_tetap_terbaca(client, auth_headers, path):
    r = client.get(path, headers=auth_headers)
    assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"


# --------------------------------------------------------------- peta saldo


def test_peta_saldo_kepala_hanya_satu_titik(client, auth_headers, geo):
    r = client.get("/balance/map?commodity=telur", headers=auth_headers)
    assert r.status_code == 200, r.text
    locations = r.json()["locations"]
    assert len(locations) == 1, [loc.get("location") for loc in locations]
    assert locations[0]["location"] == geo["jakarta_name"]


def test_peta_saldo_monitor_seluruh_lokasi(client, monitor_headers):
    r = client.get("/balance/map?commodity=telur", headers=monitor_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["locations"]) > 1


def test_kpi_lokasi_asing_ditolak(client, auth_headers, geo):
    """Perilaku lama yang harus tetap hidup (pola acuan `app/core/scope.py`)."""
    r = client.get(
        "/kpi",
        params={
            "location_id": geo["other_id"],
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-12-31T23:59:59Z",
        },
        headers=auth_headers,
    )
    assert r.status_code == 403, r.text


# ------------------------------------------------------------------- events


def test_event_target_asing_ditolak(client, auth_headers, db_engine, geo):
    with db_engine.begin() as conn:
        batch = conn.execute(
            text("SELECT id, location_id FROM batches WHERE location_id <> :j LIMIT 1"),
            {"j": str(geo["jakarta_id"])},
        ).one()
    r = client.post(
        "/events/safety-disruption",
        headers=auth_headers,
        json={
            "batch_id": str(batch.id),
            "target_location_id": str(batch.location_id),
            "operation_key": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 403, r.text
    assert "cakupan lokasi" in r.json()["detail"]


def test_monitor_tidak_boleh_memicu_event(client, monitor_headers):
    """Read-only nasional tetap read-only — cakupan luas bukan izin menulis."""
    r = client.post(
        "/events/safety-disruption",
        headers=monitor_headers,
        json={
            "batch_id": str(uuid.uuid4()),
            "target_location_id": str(uuid.uuid4()),
            "operation_key": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------- register eksklusi pemasok


def test_register_eksklusi_monitor_lintas_lokasi(client, monitor_headers):
    r = client.get("/supplier-exclusions", headers=monitor_headers)
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_register_eksklusi_kepala_hanya_scope_sendiri(client, auth_headers, geo):
    ok = client.get("/supplier-exclusions", headers=auth_headers)
    assert ok.status_code == 200, ok.text
    scopes = {row["scope_location_id"] for row in ok.json()["items"]}
    assert scopes <= {geo["jakarta_id"]}, scopes


def test_register_eksklusi_cakupan_asing_ditolak(client, auth_headers, geo):
    r = client.get(
        f"/supplier-exclusions?scope_location_id={geo['other_id']}", headers=auth_headers
    )
    assert r.status_code == 403, r.text
    assert "cakupan lokasi" in r.json()["detail"]
