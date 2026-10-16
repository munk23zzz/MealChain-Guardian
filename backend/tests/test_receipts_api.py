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


def _bersihkan(*ids: str) -> None:
    """Hapus HANYA catatan yang dibuat tes ini — per id, bukan per batch.

    Dulu fungsi ini `DELETE FROM batch_receipts WHERE batch_id = <Jakarta>`, yaitu
    menghapus SELURUH riwayat penerimaan batch itu. Batch Jakarta kebetulan satu-
    satunya batch dalam scope peran SPPG, jadi sapuan itu ikut menghapus catatan
    yang sah (isian demo untuk juri) setiap kali suite dijalankan — persis kelas
    cacat isolasi yang dulu mengosongkan deret kanonik. Efek sampingnya dulu
    tersamarkan karena asersi memakai `len(items) == 1`, yang justru BENAR hanya
    bila tak ada catatan lain.
    """
    if not ids:
        return
    from sqlalchemy import bindparam, create_engine, text

    engine = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM batch_receipts WHERE id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": list(ids)},
            )
    finally:
        engine.dispose()


def test_catat_penerimaan_tersimpan_dan_terbaca_kembali(auth_headers):
    batch_id = _batch_jakarta_id()
    dibuat: list[str] = []
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
            dibuat.append(badan["id"])
            assert badan["checked_count"] == 2
            assert badan["other_note"] == "Karung lapis kedua basah, isi masih kering."
            assert badan["recorded_by_name"]
            assert badan["recorded_at"]

            lagi = c.get(f"/receipts?batch_id={batch_id}", headers=auth_headers)
            assert lagi.status_code == 200, lagi.text
            item = lagi.json()["items"]
            # Bukan `len(items) == 1`: batch ini boleh punya riwayat lain (mis.
            # isian demo). Yang dipaku: catatan yang baru dibuat TERBACA dan
            # berada paling depan (terbaru dulu).
            assert item[0]["id"] == badan["id"]
            assert item[0]["checked"] == {"kemasan": True, "suhu": True, "warna": False}
    finally:
        _bersihkan(*dibuat)


def test_catatan_kosong_disimpan_sebagai_null(auth_headers):
    """Menulis spasi ≠ menulis catatan; UI harus bisa membedakannya."""
    batch_id = _batch_jakarta_id()
    dibuat: list[str] = []
    try:
        with _client() as c:
            resp = c.post(
                "/receipts",
                headers=auth_headers,
                json={"batch_id": batch_id, "checked": {}, "other_note": "   "},
            )
            assert resp.status_code == 201, resp.text
            dibuat.append(resp.json()["id"])
            assert resp.json()["other_note"] is None
            assert resp.json()["checked_count"] == 0
    finally:
        _bersihkan(*dibuat)


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
    dibuat: list[str] = []
    try:
        with _client() as c:
            catat = c.post(
                "/receipts",
                headers=auth_headers,
                json={"batch_id": batch_id, "checked": {"kemasan": True}},
            )
            assert catat.status_code == 201, catat.text
            dibuat.append(catat.json()["id"])

            # bgn_monitor: boleh baca (pengawas), tidak boleh mencatat.
            baca = c.get(f"/receipts?batch_id={batch_id}", headers=monitor_headers)
            assert baca.status_code == 200, baca.text
            assert any(x["id"] == dibuat[0] for x in baca.json()["items"])

            tulis = c.post(
                "/receipts",
                headers=monitor_headers,
                json={"batch_id": batch_id, "checked": {"kemasan": True}},
            )
            assert tulis.status_code == 403, tulis.text
    finally:
        _bersihkan(*dibuat)


def test_urutan_terbaru_dulu_dan_batas_limit(auth_headers):
    batch_id = _batch_jakarta_id()
    dibuat: list[str] = []
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
            dibuat.append(pertama["id"])
            kedua = c.post(
                "/receipts",
                headers=auth_headers,
                json={
                    "batch_id": batch_id,
                    "checked": {"suhu": True},
                    "other_note": "catatan dua",
                },
            ).json()
            dibuat.append(kedua["id"])

            items = c.get(f"/receipts?batch_id={batch_id}", headers=auth_headers).json()["items"]
            # Dua catatan ini yang TERBARU, jadi harus menempati dua posisi depan
            # walaupun batch punya riwayat lain (mis. isian demo).
            assert [x["id"] for x in items][:2] == [kedua["id"], pertama["id"]]

            satu = c.get(
                f"/receipts?batch_id={batch_id}&limit=1", headers=auth_headers
            ).json()["items"]
            assert len(satu) == 1 and satu[0]["id"] == kedua["id"]
    finally:
        _bersihkan(*dibuat)


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
