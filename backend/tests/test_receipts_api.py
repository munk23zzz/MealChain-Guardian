"""Catatan penerimaan barang (`/receipts`) — opsi "Lainnya" yang tersimpan.

Diuji terhadap DB nyata (pola conftest repo ini): 201 benar-benar tersimpan,
scope lokasi berlaku untuk pencatat, dan catatan kosong tidak jadi string kosong.
"""

import uuid

from fastapi.testclient import TestClient


def _client():
    from app.main import app

    return TestClient(app)


def _batch_jakarta_id() -> str:
    from sqlalchemy import create_engine, text

    engine = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    try:
        with engine.begin() as conn:
            return str(
                conn.execute(
                    text(
                        "SELECT b.id FROM batches b JOIN locations l ON l.id = b.location_id "
                        "WHERE l.name = 'Jakarta' ORDER BY b.created_at DESC LIMIT 1"
                    )
                ).scalar_one()
            )
    finally:
        engine.dispose()


def _batch_luar_jakarta_id() -> str:
    from sqlalchemy import create_engine, text

    engine = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    try:
        with engine.begin() as conn:
            return str(
                conn.execute(
                    text(
                        "SELECT b.id FROM batches b JOIN locations l ON l.id = b.location_id "
                        "WHERE l.name <> 'Jakarta' ORDER BY b.created_at DESC LIMIT 1"
                    )
                ).scalar_one()
            )
    finally:
        engine.dispose()


def _bersihkan(batch_id: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM batch_receipts WHERE batch_id = :b"), {"b": batch_id}
            )
    finally:
        engine.dispose()


def test_catat_penerimaan_tersimpan_dan_terbaca_kembali(auth_headers):
    batch_id = _batch_jakarta_id()
    _bersihkan(batch_id)
    try:
        with _client() as c:
            resp = c.post(
                "/receipts",
                headers=auth_headers,
                json={
                    "batch_id": batch_id,
                    "checked": {"kemasan": True, "suhu": True, "warna": False},
                    "other_note": "  Karung lapis kedua basah, isi masih kering.  ",
                },
            )
            assert resp.status_code == 201, resp.text
            badan = resp.json()
            assert badan["checked_count"] == 2
            assert badan["other_note"] == "Karung lapis kedua basah, isi masih kering."
            assert badan["recorded_by_name"]
            assert badan["recorded_at"]

            lagi = c.get(f"/receipts?batch_id={batch_id}", headers=auth_headers)
            assert lagi.status_code == 200, lagi.text
            item = lagi.json()["items"]
            assert len(item) == 1
            assert item[0]["id"] == badan["id"]
            assert item[0]["checked"] == {"kemasan": True, "suhu": True, "warna": False}
    finally:
        _bersihkan(batch_id)


def test_catatan_kosong_disimpan_sebagai_null(auth_headers):
    """Menulis spasi ≠ menulis catatan; UI harus bisa membedakannya."""
    batch_id = _batch_jakarta_id()
    _bersihkan(batch_id)
    try:
        with _client() as c:
            resp = c.post(
                "/receipts",
                headers=auth_headers,
                json={"batch_id": batch_id, "checked": {}, "other_note": "   "},
            )
            assert resp.status_code == 201, resp.text
            assert resp.json()["other_note"] is None
            assert resp.json()["checked_count"] == 0
    finally:
        _bersihkan(batch_id)


def test_batch_tidak_ada_dibalas_404(auth_headers):
    with _client() as c:
        resp = c.post(
            "/receipts",
            headers=auth_headers,
            json={"batch_id": str(uuid.uuid4()), "checked": {}, "other_note": None},
        )
        assert resp.status_code == 404, resp.text


def test_batch_lokasi_lain_dibalas_403(auth_headers):
    """Peran SPPG hanya boleh mencatat penerimaan di dapurnya sendiri."""
    batch_id = _batch_luar_jakarta_id()
    with _client() as c:
        resp = c.post(
            "/receipts",
            headers=auth_headers,
            json={"batch_id": batch_id, "checked": {"kemasan": True}},
        )
        assert resp.status_code == 403, resp.text


def test_monitor_nasional_hanya_bisa_membaca(monitor_headers, auth_headers):
    batch_id = _batch_jakarta_id()
    _bersihkan(batch_id)
    try:
        with _client() as c:
            dibuat = c.post(
                "/receipts",
                headers=auth_headers,
                json={"batch_id": batch_id, "checked": {"kemasan": True}},
            )
            assert dibuat.status_code == 201, dibuat.text

            # bgn_monitor: boleh baca (pengawas), tidak boleh mencatat.
            baca = c.get(f"/receipts?batch_id={batch_id}", headers=monitor_headers)
            assert baca.status_code == 200, baca.text
            assert len(baca.json()["items"]) == 1

            tulis = c.post(
                "/receipts",
                headers=monitor_headers,
                json={"batch_id": batch_id, "checked": {"kemasan": True}},
            )
            assert tulis.status_code == 403, tulis.text
    finally:
        _bersihkan(batch_id)


def test_urutan_terbaru_dulu_dan_batas_limit(auth_headers):
    batch_id = _batch_jakarta_id()
    _bersihkan(batch_id)
    try:
        with _client() as c:
            pertama = c.post(
                "/receipts",
                headers=auth_headers,
                json={
                    "batch_id": batch_id,
                    "checked": {"kemasan": True},
                    "other_note": "catatan satu",
                },
            ).json()
            kedua = c.post(
                "/receipts",
                headers=auth_headers,
                json={
                    "batch_id": batch_id,
                    "checked": {"suhu": True},
                    "other_note": "catatan dua",
                },
            ).json()

            items = c.get(f"/receipts?batch_id={batch_id}", headers=auth_headers).json()["items"]
            assert [x["id"] for x in items][0] == kedua["id"]
            assert [x["id"] for x in items][1] == pertama["id"]

            satu = c.get(
                f"/receipts?batch_id={batch_id}&limit=1", headers=auth_headers
            ).json()["items"]
            assert len(satu) == 1 and satu[0]["id"] == kedua["id"]
    finally:
        _bersihkan(batch_id)


def test_snapshot_terlalu_besar_dibalas_422(auth_headers):
    batch_id = _batch_jakarta_id()
    with _client() as c:
        resp = c.post(
            "/receipts",
            headers=auth_headers,
            json={
                "batch_id": batch_id,
                "checked": {f"titik{i}": True for i in range(21)},
            },
        )
        assert resp.status_code == 422, resp.text
