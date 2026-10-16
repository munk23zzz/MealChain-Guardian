"""Kalender agenda harian — GET /agenda (permintaan pemilik 2026-10-16).

Latar: tab "Hari Ini" adalah satu-satunya halaman yang NAMANYA harian, tetapi
seluruh isinya dihitung dari "sekarang" — tak ada cara bertanya "bagaimana kalau
saya lihat tanggal lain?". Sementara itu `menu_plans` menyimpan rencana menu 10
lokasi untuk SETIAP hari 1 Sep–5 Nov, dan tak pernah muncul di layar.

Kontrak yang dikunci di sini:
- `start`/`end` berisi tanggal ISO (YYYY-MM-DD) yang diartikan sebagai HARI WIB
  (Asia/Jakarta, UTC+7) — bukan hari UTC. Batas hari diuji lewat baris kiriman
  yang jatuh pukul 00:30 WIB: ia harus masuk hari WIB-nya, bukan hari UTC-nya.
- Setiap hari dalam rentang SELALU muncul (kalender butuh deret tanpa lubang).
- Bagian tanpa catatan menulis `available: false`, bukan angka nol yang
  berpura-pura terukur (aturan repo: dilarang menampilkan angka palsu).
- Cakupan mengikuti `app/core/scope.py`: rencana/kiriman/limbah/keputusan
  = sisi TUJUAN (ikut scope SPPG); batch = sisi SUMBER (lintas lokasi, sama
  seperti GET /batches). Read-only, idempoten.
"""

import uuid
from datetime import datetime, timezone

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app

ENGINE_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
HARI_SEED = "2026-10-02"      # ada rencana + kiriman + pasokan
HARI_KOSONG = "2026-10-20"    # rencana saja; tanpa catatan operasional
WIB_8_OKT_0030 = datetime(2026, 10, 7, 17, 30, tzinfo=timezone.utc)
WIB_9_OKT_0030 = datetime(2026, 10, 8, 17, 30, tzinfo=timezone.utc)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _engine():
    from sqlalchemy import create_engine

    return create_engine(ENGINE_URL)


def _mk_token(user_id, role, loc_id=None) -> str:
    import os

    now = int(datetime.now(timezone.utc).timestamp())
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "loc": str(loc_id) if loc_id else None,
            "iat": now,
            "exp": now + 15 * 60,
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )


def _lokasi_jakarta(conn) -> uuid.UUID:
    from sqlalchemy import text

    return conn.execute(
        text("SELECT id FROM locations WHERE name = 'Jakarta'")
    ).scalar_one()


@pytest.fixture()
def sppg_head():
    """User SPPG Head terikat lokasi Jakarta (pemilik data seed)."""
    from sqlalchemy import text

    eng = _engine()
    jkt = None
    uid = uuid.uuid4()
    pw = bcrypt.hashpw(b"agenda-test-pw", bcrypt.gensalt()).decode()
    with eng.begin() as conn:
        jkt = _lokasi_jakarta(conn)
        conn.execute(
            text(
                "INSERT INTO users (id, email, name, role, location_id, password_hash)"
                " VALUES (:id, :e, :n, 'sppg_head', :l, :p)"
            ),
            {
                "id": uid,
                "e": f"agenda-{uid.hex[:8]}@test.local",
                "n": "Agenda Test",
                "l": jkt,
                "p": pw,
            },
        )
    yield {"token": _mk_token(uid, "sppg_head", jkt), "location_id": jkt}
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
    eng.dispose()


@pytest.fixture()
def monitor():
    from sqlalchemy import text

    eng = _engine()
    uid = uuid.uuid4()
    pw = bcrypt.hashpw(b"agenda-test-pw", bcrypt.gensalt()).decode()
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, name, role, location_id, password_hash)"
                " VALUES (:id, :e, :n, 'bgn_monitor', NULL, :p)"
            ),
            {
                "id": uid,
                "e": f"agenda-mon-{uid.hex[:8]}@test.local",
                "n": "Agenda Monitor",
                "p": pw,
            },
        )
    yield {"token": _mk_token(uid, "bgn_monitor")}
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
    eng.dispose()


def _get(client, token, start, end):
    return client.get(
        "/agenda",
        params={"start": start, "end": end},
        headers={"Authorization": f"Bearer {token}"},
    )


def _hari(payload: dict, tanggal: str) -> dict:
    for d in payload["days"]:
        if d["date"] == tanggal:
            return d
    raise AssertionError(f"hari {tanggal} tidak ada di payload: {payload['days']}")


# ------------------------------------------------------------------ kontrak

def test_setiap_hari_dalam_rentang_selalu_muncul_tanpa_lubang(client, sppg_head):
    r = _get(client, sppg_head["token"], "2026-10-01", "2026-10-05")
    assert r.status_code == 200, r.text
    assert [d["date"] for d in r.json()["days"]] == [
        "2026-10-01",
        "2026-10-02",
        "2026-10-03",
        "2026-10-04",
        "2026-10-05",
    ]
    assert r.json()["period"]["timezone"] == "Asia/Jakarta"


def test_hari_berdata_dihitung_benar(client, sppg_head):
    r = _get(client, sppg_head["token"], HARI_SEED, HARI_SEED)
    assert r.status_code == 200, r.text
    d = _hari(r.json(), HARI_SEED)
    # Jakarta: 1 rencana menu 1200 porsi pada 2 Okt (deret seed).
    assert d["menu"]["rows"] == 1
    assert d["menu"]["planned_portions"] == 1200
    assert d["delivery"]["rows"] >= 1
    assert d["delivery"]["delivered_portions"] == 1200
    assert d["supply"]["rows"] > 0
    assert d["supply"]["available"] is True
    assert d["activity"] > 0


def test_hari_tanpa_catatan_menulis_available_false(client, sppg_head):
    """Hari tanpa baris TIDAK boleh jadi deretan nol yang tampak terukur."""
    r = _get(client, sppg_head["token"], HARI_KOSONG, HARI_KOSONG)
    assert r.status_code == 200, r.text
    d = _hari(r.json(), HARI_KOSONG)
    for bagian in ("delivery", "disposal", "supply", "price", "decisions"):
        assert d[bagian]["available"] is False, f"{bagian} harus available=false"
        assert d[bagian]["rows"] == 0
    # Rencana menu tetap ada (menjorok ke depan sampai 5 Nov).
    assert d["menu"]["rows"] == 1
    assert d["menu"]["available"] is True


def test_batas_hari_pakai_wib_bukan_utc(client, monitor):
    """Kiriman 00:30 WIB masuk hari WIB-nya, bukan hari UTC-nya.

    2026-10-08T17:30Z = 9 Okt 00:30 WIB → harus terhitung di 9 Okt.
    """
    from sqlalchemy import text

    eng = _engine()
    with eng.begin() as conn:
        plan_id = conn.execute(
            text(
                "SELECT m.id FROM menu_plans m JOIN locations l ON l.id=m.location_id"
                " WHERE m.plan_date = DATE '2026-10-09' AND l.name = 'Bandung'"
            )
        ).scalar_one()
        event_id = conn.execute(
            text(
                "INSERT INTO delivery_events (id, menu_plan_id, delivered_portions,"
                " status, delivered_at) VALUES (gen_random_uuid(), :m, 7, 'delivered', :t)"
                " RETURNING id"
            ),
            {"m": plan_id, "t": WIB_9_OKT_0030},
        ).scalar_one()
    try:
        r = _get(client, monitor["token"], "2026-10-09", "2026-10-09")
        assert r.status_code == 200, r.text
        d = _hari(r.json(), "2026-10-09")
        assert d["delivery"]["rows"] == 1
        assert d["delivery"]["delivered_portions"] == 7

        # Kalau memakai hari UTC, baris ini akan bocor ke 8 Okt.
        r8 = _get(client, monitor["token"], "2026-10-08", "2026-10-08")
        d8 = _hari(r8.json(), "2026-10-08")
        assert d8["delivery"]["delivered_portions"] == 0
    finally:
        with eng.begin() as conn:
            conn.execute(
                text("DELETE FROM delivery_events WHERE id = :id"), {"id": event_id}
            )
        eng.dispose()


def test_scope_sppg_sempit_monitor_luas(client, sppg_head, monitor):
    r_sppg = _get(client, sppg_head["token"], HARI_SEED, HARI_SEED).json()
    r_mon = _get(client, monitor["token"], HARI_SEED, HARI_SEED).json()
    d_sppg = _hari(r_sppg, HARI_SEED)
    d_mon = _hari(r_mon, HARI_SEED)
    assert d_sppg["menu"]["rows"] == 1      # hanya Jakarta
    assert d_mon["menu"]["rows"] == 10      # sepuluh lokasi
    assert d_mon["menu"]["planned_portions"] == 12000
    assert r_sppg["scope"]["national"] is False
    assert r_mon["scope"]["national"] is True


def test_rentang_terlalu_panjang_dan_terbalik_ditolak(client, sppg_head):
    assert _get(client, sppg_head["token"], "2026-11-01", "2026-09-01").status_code == 422
    assert _get(client, sppg_head["token"], "2026-01-01", "2026-12-31").status_code == 422
    assert _get(client, sppg_head["token"], "2026-10-40", "2026-10-41").status_code == 422


def test_tanpa_token_401(client):
    r = client.get("/agenda", params={"start": "2026-10-01", "end": "2026-10-02"})
    assert r.status_code == 401


def test_hanya_baca_dan_idempoten(client, sppg_head):
    a = _get(client, sppg_head["token"], HARI_SEED, HARI_SEED).json()
    b = _get(client, sppg_head["token"], HARI_SEED, HARI_SEED).json()
    a.pop("computed_at")
    b.pop("computed_at")
    assert a == b
