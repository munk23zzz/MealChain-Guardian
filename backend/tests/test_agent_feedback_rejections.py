"""Agent LEARN harus bisa MEMBACA data yang ditolak.

Konteks (permintaan pemilik 29 Okt 2026): data demo sudah memuat kasus ditolak
(1 penerimaan ayam 300 kg + 10 keputusan), tetapi tidak ada satu pun jalan baca
yang memperlihatkannya kepada agent. Gateway tool agent hanya punya 10 tool
pasokan/harga/rute/pengajuan — tidak ada tool riwayat penolakan. Akibatnya
langkah LEARN hanya bisa mencatat penolakan yang kebetulan sedang diproses,
tidak pernah membaca pola penolakan yang sudah ada.

Kontrak yang diuji di sini:
- `GET /agent/feedback/rejections` mengembalikan keputusan DITOLAK beserta
  alasannya, dan penerimaan yang DITOLAK beserta catatan pemeriksaannya.
- Cakupan lokasi mengikuti aturan yang sama dengan feed keputusan: peran SPPG
  hanya melihat kotanya, `bgn_monitor` melihat semua.
- Baris yang tidak ditolak TIDAK ikut (bukan "riwayat semua keputusan").
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from tests.conftest import DSN_SYNC  # noqa: F401  (memastikan konfigurasi tes dimuat)

AWAL = datetime(2033, 5, 1, tzinfo=timezone.utc)


def _conn():
    from sqlalchemy import create_engine

    from tests.dsn import DSN_SYNC as dsn

    return create_engine(dsn)


def _lokasi(conn, nama: str) -> uuid.UUID:
    return conn.execute(
        text("SELECT id FROM locations WHERE name = :n LIMIT 1"), {"n": nama}
    ).scalar_one()


def _komoditas(conn):
    return conn.execute(text("SELECT id FROM commodities ORDER BY name LIMIT 1")).scalar_one()


def _keputusan(conn, *, lokasi_id, status: str, alasan: str | None, komoditas_id):
    did = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO decisions (id, decision_type, status, proposed_by, "
            "target_location_id, commodity_id, quantity_kg, created_at, "
            "expires_at, rejection_reason, iteration) VALUES "
            "(:id, 'regional_balance', :status, 'supervisor_agent', :lok, :kom, "
            "120, :dibuat, :kedaluwarsa, :alasan, 1)"
        ),
        {
            "id": did,
            "status": status,
            "lok": lokasi_id,
            "kom": komoditas_id,
            "dibuat": AWAL,
            "kedaluwarsa": AWAL + timedelta(minutes=30),
            "alasan": alasan,
        },
    )
    return did


def _bersihkan(conn, ids):
    for did in ids:
        conn.execute(text("DELETE FROM agent_traces WHERE decision_id = :d"), {"d": did})
        conn.execute(text("DELETE FROM decision_evidence WHERE decision_id = :d"), {"d": did})
        conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": did})


def test_agent_membaca_keputusan_ditolak_beserta_alasannya(auth_headers):
    from fastapi.testclient import TestClient

    from app.main import app

    eng = _conn()
    ids = []
    try:
        with eng.begin() as conn:
            kom = _komoditas(conn)
            jakarta = _lokasi(conn, "Jakarta")
            bandung = _lokasi(conn, "Bandung")
            ids.append(_keputusan(conn, lokasi_id=jakarta, status="rejected",
                                  alasan="Harga di atas acuan PIHPS 15%", komoditas_id=kom))
            ids.append(_keputusan(conn, lokasi_id=jakarta, status="approved",
                                  alasan=None, komoditas_id=kom))
            ids.append(_keputusan(conn, lokasi_id=bandung, status="rejected",
                                  alasan="Kuota SPPG Bandung penuh", komoditas_id=kom))

        with TestClient(app) as c:
            resp = c.get("/agent/feedback/rejections", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        alasan = [k["rejection_reason"] for k in body["keputusan"]]
        assert "Harga di atas acuan PIHPS 15%" in alasan, alasan
        # Yang tidak ditolak tidak boleh ikut, dan kota lain di luar cakupan.
        assert all(k["status"] == "rejected" for k in body["keputusan"])
        assert "Kuota SPPG Bandung penuh" not in alasan, alasan
        # Bentuk minimal yang dibutuhkan LEARN.
        baris = next(k for k in body["keputusan"] if k["rejection_reason"].startswith("Harga"))
        assert baris["decision_type"] == "regional_balance"
        assert baris["lokasi_tujuan"] == "Jakarta"
        assert baris["komoditas"], baris
        assert baris["iteration"] == 1
    finally:
        with eng.begin() as conn:
            _bersihkan(conn, ids)
        eng.dispose()


def test_riwayat_penolakan_untuk_langkah_learn():
    """Fungsi yang dibaca LEARN: hanya yang ditolak, terbaru dulu, bisa dikecualikan."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.services.rejection_feedback import riwayat_penolakan
    from tests.dsn import DSN_ASYNC

    eng = _conn()
    ids = []
    jakarta = kom = None
    try:
        with eng.begin() as conn:
            kom = _komoditas(conn)
            jakarta = _lokasi(conn, "Jakarta")
            ids.append(_keputusan(conn, lokasi_id=jakarta, status="rejected",
                                  alasan="Harga di atas acuan PIHPS 15%", komoditas_id=kom))
            ids.append(_keputusan(conn, lokasi_id=jakarta, status="rejected",
                                  alasan="Kuota SPPG penuh", komoditas_id=kom))
            ids.append(_keputusan(conn, lokasi_id=jakarta, status="approved",
                                  alasan=None, komoditas_id=kom))

        async def _baca():
            e = create_async_engine(DSN_ASYNC)
            maker = async_sessionmaker(e, expire_on_commit=False)
            try:
                async with maker() as db:
                    semua = await riwayat_penolakan(
                        db, target_location_id=jakarta, commodity_id=kom
                    )
                    kecuali = await riwayat_penolakan(
                        db,
                        target_location_id=jakarta,
                        commodity_id=kom,
                        kecuali_decision_id=ids[0],
                    )
                    return semua, kecuali
            finally:
                await e.dispose()

        semua, kecuali = asyncio.run(_baca())
        alasan = [k["alasan"] for k in semua["keputusan"]]
        assert "Harga di atas acuan PIHPS 15%" in alasan
        assert "Kuota SPPG penuh" in alasan
        assert semua["jumlah"]["keputusan"] == 2, semua
        assert ids[0] is not None
        # Dua baris dibuat pada detik yang sama; yang penting: satu tersisa dan
        # baris yang dikecualikan tidak ikut.
        assert len(kecuali["keputusan"]) == 1, kecuali
        assert kecuali["keputusan"][0]["decision_id"] != str(ids[0])
    finally:
        with eng.begin() as conn:
            _bersihkan(conn, ids)
        eng.dispose()


def test_agent_membaca_penerimaan_ditolak(auth_headers):
    """Penerimaan yang ditolak saat serah terima = bahan belajar, bukan stok."""
    from fastapi.testclient import TestClient

    from app.main import app

    eng = _conn()
    batch_id = None
    try:
        with eng.begin() as conn:
            kom = _komoditas(conn)
            jakarta = _lokasi(conn, "Jakarta")
            pemasok = conn.execute(text("SELECT id FROM suppliers LIMIT 1")).scalar_one()
            pengguna = conn.execute(
                text("SELECT id FROM users WHERE location_id = :l LIMIT 1"), {"l": str(jakarta)}
            ).scalar()
            batch_id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO batches (id, commodity_id, location_id, supplier_id, "
                    "quantity_kg, harvested_at, temperature_log, certification_status, "
                    "freshness_score, safety_status, usable_until, origin) VALUES "
                    "(:id, :kom, :lok, :pem, 300, :panen, :log, 'hygiene', 0.9, 'pass', "
                    ":layak, 'seed')"
                ),
                {
                    "id": batch_id,
                    "kom": kom,
                    "lok": jakarta,
                    "pem": pemasok,
                    "panen": AWAL - timedelta(hours=8),
                    "log": json.dumps([{"timestamp": (AWAL - timedelta(hours=8)).isoformat(),
                                        "temperature_c": 4}]),
                    "layak": AWAL + timedelta(days=10),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO batch_receipts (id, batch_id, checked, recorded_by, "
                    "recorded_at, status, reviewed_by, reviewed_at, review_note, ordered_kg) "
                    "VALUES (:id, :batch, CAST(:cek AS jsonb), :oleh, :catat, 'ditolak', "
                    ":oleh, :tinjau, :catatan, 300)"
                ),
                {
                    "id": uuid.uuid4(),
                    "batch": batch_id,
                    "cek": json.dumps({"suhu": True, "kemasan": True, "jumlah": True}),
                    "oleh": pengguna,
                    "catat": AWAL - timedelta(minutes=20),
                    "tinjau": AWAL,
                    "catatan": "Kemasan bocor dan suhu di atas batas saat tiba.",
                },
            )

        with TestClient(app) as c:
            resp = c.get("/agent/feedback/rejections", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        ditolak = resp.json()["penerimaan"]
        assert any(
            p["review_note"] == "Kemasan bocor dan suhu di atas batas saat tiba."
            for p in ditolak
        ), ditolak
        baris = next(p for p in ditolak if p["batch_id"] == str(batch_id))
        assert baris["lokasi"] == "Jakarta"
        assert baris["ordered_kg"] == pytest.approx(300.0)
        # Ditolak = tidak masuk stok.
        assert baris["received_kg"] is None
    finally:
        with eng.begin() as conn:
            if batch_id is not None:
                conn.execute(text("DELETE FROM batch_receipts WHERE batch_id = :b"), {"b": batch_id})
                conn.execute(text("DELETE FROM batches WHERE id = :b"), {"b": batch_id})
        eng.dispose()
