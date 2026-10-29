"""Persetujuan penerimaan barang → stok masuk (`/receipts/{id}/approve`).

Kontrak yang dikunci (keputusan pemilik, 20 Okt 2026):

1. Mencatat penerimaan TIDAK menambah stok — catatan lahir `menunggu`.
2. Persetujuan kepala SPPG menulis satu baris `supply_records` sebesar kg batch
   DI ATAS stok terakhir (stok on-hand, bukan mengganti) → angka Overview naik.
3. Klik kedua idempoten: baris stok yang sama, tidak menambah lagi.
4. Penolakan wajib beralasan dan tidak menulis stok.
5. Hanya `sppg_head` yang memutuskan; batch harus di lokasi sendiri.
6. Barang berstatus keamanan `fail` tidak boleh disetujui.
7. Batch yang masa layaknya sudah lewat tidak lagi ditawarkan di antrean
   "Menunggu persetujuan" (permintaan pemilik, 29 Okt 2026).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DSN_SYNC = DSN_SYNC


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _db():
    return create_engine(DSN_SYNC)


def _batch(pilih: str = "jakarta") -> tuple[str, str, str, float]:
    """Batch (id, location_id, commodity_id, kg) yang belum punya penerimaan disetujui."""
    where = "l.name = 'Jakarta'" if pilih == "jakarta" else "l.name <> 'Jakarta'"
    engine = _db()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT b.id, b.location_id, b.commodity_id, b.quantity_kg "
                    "FROM batches b JOIN locations l ON l.id = b.location_id "
                    f"WHERE {where} "
                    # Sejak gate keselamatan 25 Okt 2026 (F-01) persetujuan
                    # hanya sah untuk batch `pass` yang bukti suhunya lengkap.
                    # Fixture ini mencari batch yang MEMANG layak disetujui,
                    # supaya yang diuji tetap idempotensi stok — bukan aturan
                    # keamanan (itu diuji di test_receipts_safety_gate.py).
                    "AND b.safety_status = 'pass' "
                    "AND jsonb_array_length(COALESCE(b.temperature_log, '[]'::jsonb)) >= 2 "
                    "AND (b.usable_until IS NULL OR b.usable_until > now()) "
                    "AND NOT EXISTS (SELECT 1 FROM batch_receipts r "
                    "  WHERE r.batch_id = b.id AND r.status IN ('menunggu','disetujui')) "
                    "ORDER BY b.usable_until DESC NULLS LAST, b.created_at DESC LIMIT 1"
                )
            ).one()
        return str(row[0]), str(row[1]), str(row[2]), float(row[3])
    finally:
        engine.dispose()


def _stok(location_id: str, commodity_id: str) -> float:
    engine = _db()
    try:
        with engine.begin() as conn:
            nilai = conn.execute(
                text(
                    # Stok on-hand = baris terakhir YANG SUDAH TERJADI. Deret
                    # waktu demo memuat baris masa depan (s/d 5 Nov); tanpa
                    # batas ini, "sebelum" membaca baris masa depan dan approve
                    # hari ini tampak tidak menambah apa pun.
                    "SELECT quantity_kg FROM supply_records "
                    "WHERE location_id = :l AND commodity_id = :c "
                    "AND recorded_at <= now() "
                    "ORDER BY recorded_at DESC, id DESC LIMIT 1"
                ),
                {"l": location_id, "c": commodity_id},
            ).scalar_one_or_none()
        return float(nilai) if nilai is not None else 0.0
    finally:
        engine.dispose()


def _bersihkan(receipt_ids: list[str], supply_ids: list[str]) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            for rid in receipt_ids:
                conn.execute(
                    text("DELETE FROM batch_receipts WHERE id = :i"), {"i": rid}
                )
            for sid in supply_ids:
                conn.execute(
                    text("DELETE FROM supply_records WHERE id = :i"), {"i": sid}
                )
    finally:
        engine.dispose()


def _catat(client, headers, batch_id: str, catatan: str = "tes approve") -> dict:
    resp = client.post(
        "/receipts",
        headers=headers,
        json={"batch_id": batch_id, "checked": {"kemasan": True}, "other_note": catatan},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_catat_penerimaan_belum_menambah_stok(auth_headers):
    batch_id, loc, com, _kg = _batch()
    dibuat: list[str] = []
    try:
        sebelum = _stok(loc, com)
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            dibuat.append(badan["id"])
            assert badan["status"] == "menunggu"
            assert badan["stock_kg"] is None
            assert badan["supply_record_id"] is None
        assert _stok(loc, com) == sebelum, "mencatat saja tidak boleh menulis stok"
    finally:
        _bersihkan(dibuat, [])


def test_antrean_menunggu_hanya_berisi_catatan_yang_belum_diputuskan(auth_headers):
    """Catatan yang sudah dinilai pindah ke antrean ini, bukan ke form penerimaan."""
    batch_id, loc, com, _kg = _batch()
    receipt_ids: list[str] = []
    try:
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])

            antrean = c.get("/receipts/menunggu", headers=auth_headers)
            assert antrean.status_code == 200, antrean.text
            baris = [i for i in antrean.json()["items"] if i["batch_id"] == batch_id]
            assert baris, "catatan menunggu harus muncul di antrean"
            assert baris[0]["id"] == badan["id"]
            assert baris[0]["checked_count"] == 1
            assert baris[0]["recorded_by_name"]

            tolak = c.post(
                f"/receipts/{badan['id']}/reject",
                headers=auth_headers,
                json={"note": "uji antrean"},
            )
            assert tolak.status_code == 200, tolak.text
            sesudah = c.get("/receipts/menunggu", headers=auth_headers).json()["items"]
            assert all(i["batch_id"] != batch_id for i in sesudah)
    finally:
        _bersihkan(receipt_ids, [])


def test_antrean_menyembunyikan_batch_yang_sudah_kedaluwarsa(auth_headers):
    """Batch yang masa layaknya lewat tidak ditawarkan lagi untuk disetujui.

    Permintaan pemilik (29 Okt 2026): barang kedaluwarsa tidak boleh muncul di
    "Menunggu persetujuan" — menyetujuinya hanya menambah stok yang tak boleh
    dipakai. Catatan tetap tersimpan (riwayat), jadi yang diuji adalah daftar
    antreannya, bukan penghapusan data.
    """
    batch_id, _loc, _com, _kg = _batch()
    receipt_ids: list[str] = []
    engine = _db()
    try:
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])

            sebelum = c.get("/receipts/menunggu", headers=auth_headers).json()["items"]
            assert any(i["batch_id"] == batch_id for i in sebelum), (
                "prasyarat: muncul saat masih layak"
            )

            with engine.begin() as conn:
                asli = conn.execute(
                    text("SELECT usable_until FROM batches WHERE id = :id"), {"id": batch_id}
                ).scalar_one()
                conn.execute(
                    text(
                        "UPDATE batches SET usable_until = :lewat WHERE id = :id"
                    ),
                    {"lewat": datetime.now(UTC) - timedelta(days=2), "id": batch_id},
                )
            try:
                sesudah = c.get("/receipts/menunggu", headers=auth_headers).json()["items"]
                assert all(i["batch_id"] != batch_id for i in sesudah), (
                    "kedaluwarsa harus disembunyikan"
                )
            finally:
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE batches SET usable_until = :asli WHERE id = :id"),
                        {"asli": asli, "id": batch_id},
                    )
    finally:
        _bersihkan(receipt_ids, [])


def test_antrean_hanya_memuat_batch_yang_sudah_aman(auth_headers):
    """Antrean keputusan hanya berisi barang yang sudah lolos (usable).

    Permintaan pemilik (29 Okt 2026): "Menunggu persetujuan" hanya menampilkan
    yang sudah aman — tinggal setujui atau tolak. Barang `on_hold` (belum
    diuji / bukti suhu kurang) tetap BOLEH dicatat, tetapi tidak ditawarkan
    untuk disetujui karena `/approve` pasti menolaknya (409).
    """
    engine = _db()
    with engine.begin() as conn:
        baris = conn.execute(
            text(
                "SELECT b.id FROM batches b JOIN locations l ON l.id = b.location_id "
                "WHERE l.name = 'Jakarta' AND b.safety_status = 'pending' "
                "AND b.usable_until > now() AND b.quarantine_status = 'none' "
                "ORDER BY b.id LIMIT 1"
            )
        ).first()
    if baris is None:
        pytest.skip("tidak ada batch `pending` di Jakarta pada data uji")
    batch_id = str(baris[0])

    receipt_ids: list[str] = []
    try:
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])
            assert badan["status"] == "menunggu"

            antrean = c.get("/receipts/menunggu", headers=auth_headers).json()["items"]
            assert all(i["batch_id"] != batch_id for i in antrean), (
                "batch on_hold tidak boleh ditawarkan untuk disetujui"
            )

            # Bukti bahwa penolakan bukan karena catatan hilang: keputusan
            # langsung ke endpoint tetap dijawab 409 dengan sebabnya.
            tolak = c.post(
                f"/receipts/{badan['id']}/approve", headers=auth_headers, json={}
            )
            assert tolak.status_code == 409, tolak.text
    finally:
        _bersihkan(receipt_ids, [])


def test_approve_menambah_stok_dan_idempoten(auth_headers):
    batch_id, loc, com, kg = _batch()
    receipt_ids: list[str] = []
    supply_ids: list[str] = []
    try:
        sebelum = _stok(loc, com)
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])

            setuju = c.post(f"/receipts/{badan['id']}/approve", headers=auth_headers)
            assert setuju.status_code == 200, setuju.text
            hasil = setuju.json()
            assert hasil["status"] == "disetujui"
            assert hasil["reviewed_by_name"]
            assert hasil["stock_kg"] == kg
            assert hasil["supply_record_id"]
            supply_ids.append(hasil["supply_record_id"])

            # kg dibaca dari DB sebagai float dan `_stok` juga float: 911,68 + 300,0
            # tidak sama dengan 1.211,68 dalam representasi biner, jadi perbandingan
            # harus bertoleransi. Dulu asersi ini lulus/gagal tergantung lot mana
            # yang dipilih `_batch()`.
            assert _stok(loc, com) == pytest.approx(sebelum + kg, abs=0.01)

            # Klik kedua: balasan sama, stok TIDAK bertambah lagi.
            lagi = c.post(f"/receipts/{badan['id']}/approve", headers=auth_headers)
            assert lagi.status_code == 200, lagi.text
            assert lagi.json()["sudah"] is True
            assert lagi.json()["supply_record_id"] == hasil["supply_record_id"]
            # kg dibaca dari DB sebagai float dan `_stok` juga float: 911,68 + 300,0
            # tidak sama dengan 1.211,68 dalam representasi biner, jadi perbandingan
            # harus bertoleransi. Dulu asersi ini lulus/gagal tergantung lot mana
            # yang dipilih `_batch()`.
            assert _stok(loc, com) == pytest.approx(sebelum + kg, abs=0.01)

            riwayat = c.get(f"/receipts?batch_id={batch_id}", headers=auth_headers)
            assert riwayat.status_code == 200
            teratas = riwayat.json()["items"][0]
            assert teratas["id"] == badan["id"]
            assert teratas["status"] == "disetujui"
    finally:
        _bersihkan(receipt_ids, supply_ids)


def test_reject_wajib_alasan_dan_tidak_menulis_stok(auth_headers):
    batch_id, loc, com, _kg = _batch()
    receipt_ids: list[str] = []
    try:
        sebelum = _stok(loc, com)
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id, "kemasan penyok")
            receipt_ids.append(badan["id"])

            kosong = c.post(
                f"/receipts/{badan['id']}/reject", headers=auth_headers, json={"note": "  "}
            )
            assert kosong.status_code == 422, kosong.text

            tolak = c.post(
                f"/receipts/{badan['id']}/reject",
                headers=auth_headers,
                json={"note": "kemasan penyok, minta ganti"},
            )
            assert tolak.status_code == 200, tolak.text
            assert tolak.json()["status"] == "ditolak"
            assert tolak.json()["review_note"] == "kemasan penyok, minta ganti"
            assert tolak.json()["stock_kg"] is None

            # Penerimaan yang sudah ditolak tidak bisa langsung disetujui.
            setuju = c.post(f"/receipts/{badan['id']}/approve", headers=auth_headers)
            assert setuju.status_code == 409, setuju.text
        assert _stok(loc, com) == sebelum
    finally:
        _bersihkan(receipt_ids, [])


def test_hanya_kepala_sppg_yang_boleh_memutuskan(auth_headers, monitor_headers):
    batch_id, _loc, _com, _kg = _batch()
    receipt_ids: list[str] = []
    try:
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])
            tolak = c.post(
                f"/receipts/{badan['id']}/approve", headers=monitor_headers
            )
            assert tolak.status_code == 403, tolak.text
    finally:
        _bersihkan(receipt_ids, [])


def test_tidak_boleh_menyetujui_batch_lokasi_lain(auth_headers):
    batch_id, _loc, _com, _kg = _batch("luar")
    receipt_ids: list[str] = []
    try:
        with _client() as c:
            # Catatan pun sudah ditolak scope (403) — persetujuan juga.
            catat = c.post(
                "/receipts",
                headers=auth_headers,
                json={"batch_id": batch_id, "checked": {}, "other_note": None},
            )
            assert catat.status_code == 403, catat.text
    finally:
        _bersihkan(receipt_ids, [])


def test_barang_kedaluwarsa_tidak_boleh_disetujui(auth_headers):
    """Barang lewat masa layak tidak boleh menambah stok — tolak, bukan setujui."""
    batch_id, _loc, _com, _kg = _batch()
    receipt_ids: list[str] = []
    engine = _db()
    try:
        with engine.begin() as conn:
            asli = conn.execute(
                text("SELECT usable_until FROM batches WHERE id = :b"), {"b": batch_id}
            ).scalar_one()
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE batches SET usable_until = now() - interval '1 day' WHERE id = :b"),
                {"b": batch_id},
            )
        with _client() as c:
            setuju = c.post(f"/receipts/{badan['id']}/approve", headers=auth_headers)
            assert setuju.status_code == 409, setuju.text
            assert "kedaluwarsa" in setuju.json()["detail"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE batches SET usable_until = :u WHERE id = :b"),
                {"u": asli, "b": batch_id},
            )
        engine.dispose()
        _bersihkan(receipt_ids, [])


def test_barang_tidak_aman_tidak_boleh_disetujui(auth_headers):
    batch_id, loc, com, _kg = _batch()
    receipt_ids: list[str] = []
    engine = _db()
    try:
        with engine.begin() as conn:
            asli = conn.execute(
                text("SELECT safety_status FROM batches WHERE id = :b"), {"b": batch_id}
            ).scalar_one()
        with _client() as c:
            badan = _catat(c, auth_headers, batch_id)
            receipt_ids.append(badan["id"])
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE batches SET safety_status = 'fail' WHERE id = :b"),
                {"b": batch_id},
            )
        with _client() as c:
            setuju = c.post(f"/receipts/{badan['id']}/approve", headers=auth_headers)
            assert setuju.status_code == 409, setuju.text
            assert "TIDAK AMAN" in setuju.json()["detail"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE batches SET safety_status = :s WHERE id = :b"),
                {"s": asli, "b": batch_id},
            )
        engine.dispose()
        _bersihkan(receipt_ids, [])
