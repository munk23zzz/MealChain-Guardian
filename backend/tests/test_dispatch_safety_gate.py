"""Gerbang dispatch pada ENDPOINT: `/actions/execute` menolak bukti tak-usable.

Fase 4 MG butir 1 meminta kondisi merahnya direproduksi lewat jalur nyata.
Berkas ini melakukannya di HTTP: satu keputusan `approved` yang benar-benar ada
di DB dipasangkan dengan batch sumber yang statusnya diturunkan menjadi
`pending`/`needs_verification`, lalu `/actions/execute` harus menjawab 409
dengan alasan safety — bukan 200, dan bukan pula 500.

Status batch dikembalikan di teardown supaya sisa suite tidak mewarisi data
yang sengaja dirusak tes ini.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from tests.dsn import DSN_SYNC


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _db():
    return create_engine(DSN_SYNC)


def _keputusan_dengan_batch():
    """Keputusan transfer berstatus `approved` + batch sumbernya."""
    engine = _db()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    # Lokasi acuan mengikuti jenis keputusan (pengadaan memakai
                    # SPPG TUJUAN); SQL ini menyalin aturan `lokasi_batch_acuan`.
                    "SELECT d.id, l.id, l.name, d.commodity_id, t.name "
                    "FROM decisions d "
                    "JOIN locations l ON l.id = CASE WHEN d.decision_type = 'supplier_procurement' "
                    "     THEN d.target_location_id ELSE d.source_location_id END "
                    "LEFT JOIN locations t ON t.id = d.target_location_id "
                    "WHERE d.status = 'approved' "
                    "AND d.commodity_id IS NOT NULL "
                    "AND EXISTS (SELECT 1 FROM batches b "
                    "  WHERE b.commodity_id = d.commodity_id "
                    "  AND b.location_id = CASE WHEN d.decision_type = 'supplier_procurement' "
                    "       THEN d.target_location_id ELSE d.source_location_id END) "
                    "ORDER BY d.created_at DESC LIMIT 1"
                )
            ).first()
            if row is None:
                return None
            batch = conn.execute(
                text(
                    "SELECT b.id, b.safety_status FROM batches b "
                    "WHERE b.location_id = :loc AND b.commodity_id = :com "
                    "ORDER BY b.created_at DESC"
                ),
                {"loc": row[1], "com": row[3]},
            ).all()
        # Otoritas eksekusi melekat pada SPPG TUJUAN (penerima barang).
        return str(row[0]), row[4] or row[2], [(str(b[0]), b[1]) for b in batch]
    finally:
        engine.dispose()


def _set_status(batch_ids: list[str], status: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE batches SET safety_status = :s WHERE id = ANY(:ids)"),
                {"s": status, "ids": batch_ids},
            )
    finally:
        engine.dispose()


def _pulihkan(asli: list[tuple[str, str]]) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            for batch_id, status in asli:
                conn.execute(
                    text("UPDATE batches SET safety_status = :s WHERE id = :i"),
                    {"s": status, "i": batch_id},
                )
    finally:
        engine.dispose()


def _eksekusi(decision_id: str, lokasi: str):
    from tests.test_actions import _login, _mk_user

    kepala = _mk_user("sppg_head", lokasi)
    try:
        # `with` menjalankan lifespan aplikasi: `app.state.session_maker`
        # dipasang saat startup, dan tanpa itu endpoint menolak dengan
        # AttributeError alih-alih menilai gate.
        with _client() as client:
            return client.post(
                "/actions/execute",
                json={"decision_id": decision_id},
                headers=_login(client, kepala),
            )
    finally:
        _db_admin = _db()
        try:
            with _db_admin.begin() as conn:
                conn.execute(
                    text("DELETE FROM users WHERE email = :e"), {"e": kepala["email"]}
                )
        finally:
            _db_admin.dispose()


def test_execute_ditolak_bila_batch_sumber_belum_pass():
    target = _keputusan_dengan_batch()
    if target is None:
        import pytest

        pytest.skip("tidak ada keputusan approved dengan batch sumber di DB uji")
    decision_id, lokasi, batch = target
    asli = [(b[0], b[1]) for b in batch]
    try:
        _set_status([b[0] for b in batch], "pending")
        resp = _eksekusi(decision_id, lokasi)
        assert resp.status_code == 409, resp.text
        assert "safety revalidation gagal" in resp.text
        assert "safety_pending" in resp.text or "belum" in resp.text.lower()
    finally:
        _pulihkan(asli)


def test_execute_ditolak_untuk_batch_butuh_verifikasi():
    target = _keputusan_dengan_batch()
    if target is None:
        import pytest

        pytest.skip("tidak ada keputusan approved dengan batch sumber di DB uji")
    decision_id, lokasi, batch = target
    asli = [(b[0], b[1]) for b in batch]
    try:
        _set_status([b[0] for b in batch], "needs_verification")
        resp = _eksekusi(decision_id, lokasi)
        assert resp.status_code == 409, resp.text
        assert "safety revalidation gagal" in resp.text
    finally:
        _pulihkan(asli)
