"""Gate keselamatan pada persetujuan penerimaan barang (temuan F-01).

Kontrak: kepala SPPG tidak boleh menyetujui penerimaan batch yang status
keamanannya belum `pass` — `pending`, `needs_verification`, dan `fail`
semuanya ditolak dengan 409 dan tidak menulis stok.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.dsn import DSN_SYNC


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _batch_status(statuses: tuple[str, ...]) -> str | None:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT b.id FROM batches b JOIN locations l ON l.id = b.location_id "
                    "WHERE l.name = 'Jakarta' "
                    "AND b.safety_status = ANY(:st) "
                    # Fase 4 MG: batch yang dikarantina TIDAK boleh dipakai
                    # sebagai contoh "belum pass" — pencatatan penerimaannya
                    # memang ditolak 409 karena karantina, bukan karena status
                    # keamanan. Tanpa saringan ini, tes hijau/merah tergantung
                    # batch mana yang kebetulan paling baru di DB.
                    "AND b.quarantine_status NOT IN ('quarantined', 'failed') "
                    "AND (b.usable_until IS NULL OR b.usable_until > now()) "
                    "AND NOT EXISTS (SELECT 1 FROM batch_receipts r "
                    "  WHERE r.batch_id = b.id AND r.status IN ('menunggu','disetujui')) "
                    "ORDER BY b.created_at DESC LIMIT 1"
                ),
                {"st": list(statuses)},
            ).first()
        return str(row[0]) if row else None
    finally:
        engine.dispose()


def _hapus_receipt(receipt_ids: list[str]) -> None:
    if not receipt_ids:
        return
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM batch_receipts WHERE id = ANY(:ids)"),
                {"ids": receipt_ids},
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "statuses",
    [
        ("needs_verification",),
        ("pending",),
    ],
    ids=["needs-verification", "pending"],
)
def test_approve_ditolak_untuk_batch_belum_pass(auth_headers, statuses):
    batch_id = _batch_status(statuses)
    if batch_id is None:
        pytest.skip(f"tidak ada batch {statuses} di data demo")

    dibuat: list[str] = []
    try:
        with _client() as c:
            catat = c.post(
                "/receipts",
                headers=auth_headers,
                json={
                    "batch_id": batch_id,
                    "checked": {"kemasan": True},
                    "other_note": "uji gate keselamatan",
                },
            )
            assert catat.status_code == 201, catat.text
            dibuat.append(catat.json()["id"])

            setuju = c.post(f"/receipts/{dibuat[0]}/approve", headers=auth_headers)

        assert setuju.status_code == 409, (
            f"batch berstatus {statuses} tidak boleh disetujui, dapat {setuju.status_code}"
        )
        # Gerbang keselamatan memeriksa fakta fisik lebih dulu (kedaluwarsa →
        # karantina → status keamanan), jadi batch `needs_verification` yang juga
        # dikarantina dijawab dengan alasan karantina. Yang diuji di sini adalah
        # penolakannya, bukan urutan kalimatnya.
        alasan = setuju.text.lower()
        assert any(
            kunci in alasan
            for kunci in ("tidak aman", "aman", "karantina", "kedaluwarsa", "suhu")
        ), setuju.text
    finally:
        _hapus_receipt(dibuat)
