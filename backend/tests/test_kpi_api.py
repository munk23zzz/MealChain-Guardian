"""S4-03 API test — GET /kpi (plan §11 baris KPI).

Kontrak §11: Required start/end RFC3339; optional location_id UUID; omit
scope = own location for SPPG, global for monitor; max range 366 days.
Response 200 envelope `period`, `scope`, `computed_at`, `data_source`,
`metrics` exactly seven entries. Invalid range/naive time 422; foreign
scope 403; unauthenticated 401. Read idempotent; no mutation.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=1)
END = NOW



@pytest.fixture
def suffix():
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def client():
    """TestClient dengan lifespan → app.state.session_maker tersedia."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------- helpers


def _mk_token(user_id, role, loc_id=None) -> str:
    import os

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(user_id),
        "role": role,
        "loc": str(loc_id) if loc_id else None,
        "iat": now,
        "exp": now + 15 * 60,
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def _mk_user(role: str, location_id=None) -> str:
    """Buat user test; return token. Cleanup via fixture fixture."""
    import uuid

    from sqlalchemy import create_engine, text

    eng = create_engine(
        DSN_SYNC
    )
    uid = uuid.uuid4()
    pw_hash = bcrypt.hashpw(b"kpi-test-pw", bcrypt.gensalt()).decode()
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, name, role, location_id, "
                "password_hash) VALUES (:id, :e, :n, :r, :l, :p)"
            ),
            {
                "id": str(uid),
                "e": f"evk-kpi-{uid.hex[:10]}@test.local",
                "n": "KPI API Test",
                "r": role,
                "l": location_id,
                "p": pw_hash,
            },
        )
    eng.dispose()
    return str(uid), _mk_token(uid, role, location_id)


def _cleanup_user(uid: str) -> None:
    from sqlalchemy import create_engine, text

    eng = create_engine(
        DSN_SYNC
    )
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
    eng.dispose()


@pytest.fixture
def scope_ctx(suffix):
    """User SPPG + monitor; lokasi uji EVK-loc-<suffix> untuk scope test."""
    from sqlalchemy import create_engine, text

    eng = create_engine(
        DSN_SYNC
    )
    with eng.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO locations (name, region, latitude, longitude) "
                "VALUES (:n, 'test', -6.9, 107.6) RETURNING id"
            ),
            {"n": f"EVK-loc-{suffix}"},
        ).fetchone()
    loc_id = str(row[0])
    head_uid, head_tok = _mk_user("sppg_head", loc_id)
    mon_uid, mon_tok = _mk_user("bgn_monitor", None)
    try:
        yield {
            "loc": loc_id,
            "head": head_tok,
            "monitor": mon_tok,
            "head_uid": head_uid,
            "mon_uid": mon_uid,
        }
    finally:
        _cleanup_user(head_uid)
        _cleanup_user(mon_uid)
        with eng.begin() as conn:
            conn.execute(
                text("DELETE FROM locations WHERE id=:l"), {"l": loc_id}
            )
    eng.dispose()


def _qs(start=START, end=END, loc=None) -> str:
    import urllib.parse

    p = {"start": start.isoformat(), "end": end.isoformat()}
    if loc:
        p["location_id"] = str(loc)
    return urllib.parse.urlencode(p)


# ------------------------------------------------------------------ tests


def test_kpi_unauthenticated_401(client):
    r = client.get(f"/kpi?{_qs()}")
    assert r.status_code == 401


def test_kpi_monitor_global_scope_ok(scope_ctx, client):
    r = client.get(f"/kpi?{_qs()}", headers={
        "Authorization": f"Bearer {scope_ctx['monitor']}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"period", "scope", "computed_at", "data_source",
                         "metrics"}
    assert len(body["metrics"]) == 7
    names = [m["name"] for m in body["metrics"]]
    assert len(set(names)) == 7
    for m in body["metrics"]:
        assert m["state"] in {"available", "no_data", "unavailable"}
        assert set(m) >= {"name", "unit", "state", "value", "reason",
                          "sample_count", "coverage", "previous_value",
                          "trend"}


def test_kpi_sppg_omit_location_defaults_own(scope_ctx, client):
    """Omit location_id → SPPG = own location (terlihat dari scope response)."""
    r = client.get(f"/kpi?{_qs()}", headers={
        "Authorization": f"Bearer {scope_ctx['head']}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scope"]["location_id"] == scope_ctx["loc"]


def test_kpi_sppg_foreign_location_403(scope_ctx, suffix, client):
    from sqlalchemy import create_engine, text

    eng = create_engine(
        DSN_SYNC
    )
    with eng.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO locations (name, region, latitude, longitude) "
                "VALUES (:n, 'test', -6.9, 107.6) RETURNING id"
            ),
            {"n": f"EVK-other-{suffix}"},
        ).fetchone()
    other = str(row[0])
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM locations WHERE id=:l"), {"l": other})
    eng.dispose()
    r = client.get(f"/kpi?{_qs(loc=other)}", headers={
        "Authorization": f"Bearer {scope_ctx['head']}"})
    assert r.status_code == 403


def test_kpi_sppg_own_location_ok(scope_ctx, client):
    r = client.get(f"/kpi?{_qs(loc=scope_ctx['loc'])}", headers={
        "Authorization": f"Bearer {scope_ctx['head']}"})
    assert r.status_code == 200, r.text


def test_kpi_invalid_range_422(scope_ctx, client):
    # end sebelum start
    r = client.get(
        f"/kpi?{_qs(start=NOW, end=NOW - timedelta(days=1))}",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422
    # range > 366 hari
    r = client.get(
        f"/kpi?{_qs(start=NOW - timedelta(days=400), end=NOW)}",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422


def test_kpi_naive_time_422(scope_ctx, client):
    r = client.get(
        "/kpi?start=2026-10-07T12:00:00&end=2026-10-08T12:00:00",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422


def test_kpi_read_idempotent(scope_ctx, client):
    """Dua panggilan beruntun (read-only) → envelope identik kecuali
    computed_at; tanpa write ke DB (cek via count tidak berubah sulit
    digeneralisasi — idempotensi read cukup: response konsisten)."""
    h = {"Authorization": f"Bearer {scope_ctx['monitor']}"}
    r1 = client.get(f"/kpi?{_qs()}", headers=h)
    r2 = client.get(f"/kpi?{_qs()}", headers=h)
    assert r1.status_code == r2.status_code == 200
    b1, b2 = r1.json(), r2.json()
    b1.pop("computed_at"), b2.pop("computed_at")
    assert b1 == b2


# ------------------------------------------------- periode dihitung server
# Sejak langkah periode-server, klien mengirim KUNCI periode dan backend
# menghitung rentangnya sendiri dalam hari kalender Asia/Jakarta. Tes di bawah
# mengunci kontrak itu: envelope menyebut kunci/label/zona, awal selalu tengah
# malam WIB, dan kombinasi yang membingungkan ditolak 422 — bukan ditafsirkan.


def _wib():
    return timezone(timedelta(hours=7))


def test_kpi_periode_today_envelope(scope_ctx, client):
    r = client.get(
        "/kpi?periode=today",
        headers={"Authorization": f"Bearer {scope_ctx['head']}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["period"]["key"] == "today"
    assert body["period"]["label"] == "Hari ini"
    assert body["period"]["timezone"] == "Asia/Jakarta"
    awal = datetime.fromisoformat(body["period"]["start"])
    akhir = datetime.fromisoformat(body["period"]["end"])
    assert awal.astimezone(_wib()).strftime("%H:%M:%S") == "00:00:00"
    assert awal <= akhir
    assert len(body["metrics"]) == 7


def test_kpi_periode_tujuh_hari_mulai_enam_hari_lalu(scope_ctx, client):
    r = client.get(
        "/kpi?periode=7d",
        headers={"Authorization": f"Bearer {scope_ctx['head']}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    awal = datetime.fromisoformat(body["period"]["start"]).astimezone(_wib())
    akhir = datetime.fromisoformat(body["period"]["end"]).astimezone(_wib())
    assert awal.strftime("%H:%M:%S") == "00:00:00"
    assert (akhir.date() - awal.date()).days == 6


def test_kpi_periode_bulan_berjalan(scope_ctx, client):
    r = client.get(
        "/kpi?periode=1bulan",
        headers={"Authorization": f"Bearer {scope_ctx['head']}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    awal = datetime.fromisoformat(body["period"]["start"]).astimezone(_wib())
    assert awal.day == 1
    assert awal.strftime("%H:%M:%S") == "00:00:00"
    assert body["period"]["label"] == "1 bulan"


def test_kpi_periode_tak_dikenal_422(scope_ctx, client):
    r = client.get(
        "/kpi?periode=24h",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422
    assert "periode" in r.text.lower()


def test_kpi_periode_dan_rentang_eksplisit_422(scope_ctx, client):
    """Dua sumber rentang sekaligus = ambigu; ditolak, bukan dipilih diam-diam."""
    r = client.get(
        f"/kpi?periode=today&{_qs()}",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422


def test_kpi_tanpa_periode_dan_tanpa_rentang_422(scope_ctx, client):
    r = client.get(
        "/kpi",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422



# ------------------------------------------------------- cakupan data (Fase 8)
#
# Kontrak yang dijanjikan docstring endpoint: kombinasi cakupan yang tidak masuk
# akal ditolak 422 — "demo tanpa sesi" dan "sesi tanpa include_demo". Sebelum ini
# keduanya tidak diuji di level HTTP: yang pertama berakhir 500 (ValueError lolos
# ke server) dan yang kedua diam-diam diabaikan (200 cakupan operasional), jadi
# klien yang salah kirim mendapat jawaban yang membingungkan alih-alih penolakan.


def test_kpi_include_demo_tanpa_sesi_422(scope_ctx, client):
    """Cakupan demo tanpa sesi = tebakan; harus 422, bukan 500."""
    r = client.get(
        f"/kpi?{_qs()}&include_demo=true",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422, r.text
    assert "demo_session_id" in r.text


def test_kpi_sesi_tanpa_include_demo_422(scope_ctx, client):
    """Sesi demo tanpa `include_demo` juga ambigu; jangan diabaikan diam-diam."""
    r = client.get(
        f"/kpi?{_qs()}&demo_session_id={uuid.uuid4()}",
        headers={"Authorization": f"Bearer {scope_ctx['monitor']}"},
    )
    assert r.status_code == 422, r.text
    assert "include_demo" in r.text
