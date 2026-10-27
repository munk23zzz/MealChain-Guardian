"""Kontrak dua tombol demo + sesi pemilik analisis (Fase 10 MG).

Yang dikunci berkas ini (rencana `MG/phase-10-demo-joule.md` butir 1 dan 3):

1. **Dua tombol = dua payload.** `POST /demo/session/start` menerima `mode`
   eksplisit (`replay`/`realtime`) dan meneruskannya ke pembuat sesi. Mode asing
   ditolak 422 oleh kontrak request, bukan diabaikan diam-diam.
2. **Muat ulang ≠ ganti mode.** Permintaan tanpa `replace` pada sesi yang
   bermode lain TIDAK mengganti sesi berjalan: ia mengembalikan sesi itu apa
   adanya (`created=false`) plus `conflict` yang menyebut mode yang diminta dan
   mode yang berjalan. Hanya `replace=true` yang menutup sesi lama lalu
   membangun sesi baru — itu yang dipakai tombol "Muat Demo …".
3. **Analisis membawa sesi.** `POST /demo/agent/run` menerima `demo_session`;
   keputusan yang lahir dari putaran itu menjadi MILIK sesi tersebut (kolom
   `decisions.demo_session_id`), dan sesi yang tidak ada dijawab 404.
4. **`POST /balance/analyze` menerima `demo_session`** (body-nya `extra=forbid`,
   jadi tanpa kolom ini klien tidak bisa menyebut sesi sama sekali) dan
   mengembalikan sesi yang dipakai, atau 404 bila sesi tidak ada.

Berkas ini MENULIS ke database (membuat sesi, satu baris keputusan, menutup
sesi), jadi jalankan pada DB sekali-pakai — pola yang sama dengan
`tests/test_session_modes.py`. Semua baris yang dibuat dihapus di `finally`,
dan status sesi operator dipulihkan.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api import demo as demo_api
from app.api import demo_session as demo_session_api
from app.main import app
from app.services import demo_session as sesi
from tests.dsn import DSN_SYNC

EMAIL = "sppg.head@demo.local"
PASSWORD = "Demo#SPPG2026"
REPLAY_ANCHOR = "2026-10-08T12:00:00+00:00"


def _db():
    return create_engine(DSN_SYNC)


def _login(client: TestClient) -> dict[str, str]:
    resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def klien():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sesi_bersih():
    """Catat sesi aktif operator, lalu pastikan bersih sesudah tes."""
    engine = _db()
    awal: list[tuple] = []
    try:
        with engine.begin() as conn:
            awal = conn.execute(
                text("SELECT id, status, expires_at FROM demo_sessions WHERE status='active'")
            ).all()
            for sid, _st, _exp in awal:
                conn.execute(
                    text("UPDATE demo_sessions SET status='expired' WHERE id = :i"),
                    {"i": sid},
                )
    finally:
        engine.dispose()
    dibuat: list[uuid.UUID] = []
    yield dibuat
    engine = _db()
    try:
        with engine.begin() as conn:
            for sid in dibuat:
                conn.execute(
                    text("DELETE FROM approvals WHERE decision_id IN "
                         "(SELECT id FROM decisions WHERE demo_session_id = :s)"),
                    {"s": sid},
                )
                # `agent_traces` tidak punya kolom `demo_session_id` (kolom itu
                # hanya ada di tabel yang menulisnya); jejak milik sesi ini
                # dibersihkan lewat keputusan pemiliknya.
                conn.execute(
                    text("DELETE FROM agent_traces WHERE decision_id IN "
                         "(SELECT id FROM decisions WHERE demo_session_id = :s)"),
                    {"s": sid},
                )
                conn.execute(
                    text("DELETE FROM decisions WHERE demo_session_id = :s"), {"s": sid}
                )
                conn.execute(text("DELETE FROM demo_sessions WHERE id = :s"), {"s": sid})
            # Pulihkan sesi operator yang ditutup fixture ini.
            for sid, status, expires in awal:
                conn.execute(
                    text("UPDATE demo_sessions SET status = :st, expires_at = :exp WHERE id = :i"),
                    {"st": status, "exp": expires, "i": sid},
                )
            for baris in conn.execute(
                text("SELECT id FROM demo_sessions WHERE status='active'")
            ).all():
                if all(str(baris[0]) != str(s[0]) for s in awal):
                    conn.execute(
                        text("UPDATE demo_sessions SET status='expired' WHERE id = :i"),
                        {"i": baris[0]},
                    )
    finally:
        engine.dispose()


def _sesi_aktif() -> tuple | None:
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT id, mode, evaluation_anchor::text, status "
                    "FROM demo_sessions WHERE status='active'"
                )
            ).first()
    finally:
        engine.dispose()


@pytest.fixture()
def pembuat_sesi_ringan(monkeypatch):
    """Ganti pembangun template BERAT dengan pembuat sesi biasa.

    Yang diuji di sini kontrak HTTP (mode diteruskan, sesi diganti atau tidak),
    bukan 41 detik pembangunan template. `tests/test_demo_session.py` sudah
    menguji jalur beratnya.
    """

    async def palsu(db, *, menit=None, created_by=None, mode="replay", anchor=None):
        row = await sesi.mulai(
            db,
            menit=menit,
            created_by=created_by,
            mode=mode,
            anchor=anchor,
            kosongkan=False,
        )
        return row, {"mode": "template-palsu", "kasus": 0}

    monkeypatch.setattr(demo_session_api.sesi, "mulai_dengan_template", palsu)
    return palsu


# --- butir 1: dua tombol, dua payload ---------------------------------------


def test_start_meneruskan_mode_realtime_ke_pembuat_sesi(klien, sesi_bersih, pembuat_sesi_ringan):
    headers = _login(klien)
    resp = klien.post("/demo/session/start", json={"mode": "realtime"}, headers=headers)
    assert resp.status_code == 200, resp.text
    isi = resp.json()
    sesi_bersih.append(uuid.UUID(isi["session_id"]))

    assert isi["created"] is True
    assert isi["mode"] == "realtime"
    # Jangkar realtime = waktu sesi dibuka, BUKAN jangkar kanon replay.
    assert isi["evaluation_anchor"] != REPLAY_ANCHOR
    assert isi["dataset_version"] != "kanon-2026-10-08"
    assert isi.get("conflict") in (None, {})


def test_start_replay_memakai_jangkar_kanon(klien, sesi_bersih, pembuat_sesi_ringan):
    headers = _login(klien)
    resp = klien.post("/demo/session/start", json={"mode": "replay"}, headers=headers)
    assert resp.status_code == 200, resp.text
    isi = resp.json()
    sesi_bersih.append(uuid.UUID(isi["session_id"]))
    assert isi["mode"] == "replay"
    assert isi["evaluation_anchor"].startswith("2026-10-08T12:00:00")


def test_start_menolak_mode_asing(klien, sesi_bersih, pembuat_sesi_ringan):
    headers = _login(klien)
    resp = klien.post("/demo/session/start", json={"mode": "live"}, headers=headers)
    assert resp.status_code == 422, resp.text


def test_muat_ulang_tanpa_replace_tidak_mengganti_mode_berjalan(
    klien, sesi_bersih, pembuat_sesi_ringan
):
    """Tombol lama ("Siapkan data demo") mengirim `mode=replay` eksplisit, tetapi
    tidak boleh menutup sesi realtime yang sedang berjalan."""
    headers = _login(klien)
    pertama = klien.post(
        "/demo/session/start", json={"mode": "realtime"}, headers=headers
    ).json()
    sesi_bersih.append(uuid.UUID(pertama["session_id"]))

    kedua = klien.post("/demo/session/start", json={"mode": "replay"}, headers=headers)
    assert kedua.status_code == 200, kedua.text
    isi = kedua.json()

    assert isi["created"] is False
    assert isi["session_id"] == pertama["session_id"], "sesi realtime tidak boleh diganti"
    assert isi["mode"] == "realtime"
    assert isi["conflict"] == {"requested_mode": "replay", "active_mode": "realtime"}


def test_tombol_muat_demo_dengan_replace_mengganti_sesi(
    klien, sesi_bersih, pembuat_sesi_ringan
):
    headers = _login(klien)
    pertama = klien.post(
        "/demo/session/start", json={"mode": "realtime"}, headers=headers
    ).json()
    sesi_bersih.append(uuid.UUID(pertama["session_id"]))

    kedua = klien.post(
        "/demo/session/start",
        json={"mode": "replay", "replace": True},
        headers=headers,
    )
    assert kedua.status_code == 200, kedua.text
    isi = kedua.json()
    sesi_bersih.append(uuid.UUID(isi["session_id"]))

    assert isi["created"] is True
    assert isi["mode"] == "replay"
    assert isi["session_id"] != pertama["session_id"]
    aktif = _sesi_aktif()
    assert str(aktif[0]) == isi["session_id"]
    assert aktif[1] == "replay"


# --- butir 3: analisis membawa sesi pemilik ---------------------------------


def _buat_keputusan_tanpa_stempel() -> uuid.UUID:
    """Satu baris keputusan mentah (tanpa stempel) untuk diuji penempelan."""
    engine = _db()
    did = uuid.uuid4()
    try:
        with engine.begin() as conn:
            target = conn.execute(text("SELECT id FROM locations LIMIT 1")).scalar()
            komoditas = conn.execute(text("SELECT id FROM commodities LIMIT 1")).scalar()
            saat = datetime.now(UTC)
            conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                    " target_location_id, commodity_id, quantity_kg, expires_at, origin) "
                    "VALUES (:i, 'supplier_procurement', 'proposed', 'uji-fase10', "
                    " :loc, :kom, 100, :exp, 'demo')"
                ),
                {
                    "i": did,
                    "loc": target,
                    "kom": komoditas,
                    "exp": saat + timedelta(minutes=30),
                },
            )
    finally:
        engine.dispose()
    return did


def test_agent_run_membawa_demo_session_dan_menempel_keputusan(
    klien, sesi_bersih, pembuat_sesi_ringan, monkeypatch
):
    headers = _login(klien)
    sesi_row = klien.post(
        "/demo/session/start", json={"mode": "realtime"}, headers=headers
    ).json()
    sid = uuid.UUID(sesi_row["session_id"])
    sesi_bersih.append(sid)

    did = _buat_keputusan_tanpa_stempel()
    dipanggil: dict = {}

    def fake_procurement(commodity, target_location, **kwargs):
        dipanggil["commodity"] = commodity
        dipanggil["target"] = target_location
        dipanggil["demo_session_id"] = kwargs.get("demo_session_id")
        # Stub ini menggantikan orchestrator yang MENULIS keputusan. Perilaku
        # yang sama harus ditiru: sesi yang diterima dicap pada baris yang
        # lahir. Kalau tidak, tes hanya membuktikan stub-nya sendiri.
        if kwargs.get("demo_session_id") is not None:
            engine = _db()
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE decisions SET demo_session_id = :s WHERE id = :i"
                        ),
                        {"s": kwargs["demo_session_id"], "i": did},
                    )
            finally:
                engine.dispose()
        return {
            "decision_id": str(did),
            "status": "proposed",
            "commodity": commodity,
            "target_location": target_location,
            "quantity_kg": "100",
        }

    async def fake_review(db, outcome, **kwargs):
        return {"status": "disabled", "error": None, "run_id": None}

    monkeypatch.setattr(demo_api, "run_supplier_procurement", fake_procurement)
    monkeypatch.setattr(demo_api, "_jalankan_agent_review", fake_review)

    resp = klien.post(
        "/demo/agent/run",
        json={"commodity": "beras", "demo_session": str(sid)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert dipanggil, "pipeline agent harus dijalankan"
    # Kontrak di batas API: sesi yang dipilih operator diteruskan ke orchestrator
    # penulis keputusan (bukan dibiarkan `None` lalu distempel sesi aktif).
    assert dipanggil.get("demo_session_id") is not None
    assert str(dipanggil["demo_session_id"]) == str(sid)

    isi = resp.json()
    assert isi["demo_session"]["id"] == str(sid)
    assert isi["demo_session"]["mode"] == "realtime"

    engine = _db()
    try:
        with engine.begin() as conn:
            tercatat = conn.execute(
                text("SELECT demo_session_id FROM decisions WHERE id = :i"), {"i": did}
            ).scalar()
    finally:
        engine.dispose()
    assert str(tercatat) == str(sid), "keputusan putaran ini harus milik sesi yang dipilih"


def test_agent_run_sesi_tidak_dikenal_dijawab_404(klien, sesi_bersih, monkeypatch):
    headers = _login(klien)
    resp = klien.post(
        "/demo/agent/run",
        json={"demo_session": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text
    assert "tidak ditemukan" in resp.text


def test_analyze_membawa_demo_session(klien, sesi_bersih, pembuat_sesi_ringan):
    headers = _login(klien)
    sesi_row = klien.post(
        "/demo/session/start", json={"mode": "realtime"}, headers=headers
    ).json()
    sid = uuid.UUID(sesi_row["session_id"])
    sesi_bersih.append(sid)

    resp = klien.post(
        "/balance/analyze",
        json={"commodity": "beras", "demo_session": str(sid)},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    isi = resp.json()
    assert isi["demo_session"]["id"] == str(sid)
    assert isi["demo_session"]["mode"] == "realtime"


def test_analyze_tanpa_sesi_tetap_berjalan(klien, sesi_bersih):
    headers = _login(klien)
    resp = klien.post("/balance/analyze", json={"commodity": "beras"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("demo_session") is None
