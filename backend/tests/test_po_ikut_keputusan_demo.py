"""Kontrak: PO tidak boleh jadi yatim saat keputusannya dihapus.

Temuan audit 21 Okt 2026: `sap_mock_purchase_orders.decision_id` punya FK
`ON DELETE SET NULL` (kolomnya tidak punya `ForeignKey` di model, jadi ORM tidak
menjaga apa pun). Setiap tes yang membuang keputusan demo meninggalkan PO tanpa
induk; suite lalu gagal di `test_filter_decision_id` (StopIteration) dan
"PO demo beras belum ada". Relink deterministik tidak menolong karena induknya
sudah tidak ada. Kontrak yang benar: PO lahir dari keputusan, jadi ia ikut
terhapus bersama keputusannya.
"""

from __future__ import annotations

import os
import uuid

from sqlalchemy import create_engine, text

from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL
from tests.gate_lock import dsn_psycopg


def _koneksi():
    dsn = dsn_psycopg(
        os.environ.get(
            "DATABASE_URL",
            DSN_ASYNC,
        )
    )
    return create_engine(dsn, pool_pre_ping=True)


def test_aturan_hapus_fk_po_adalah_cascade():
    """Skema harus CASCADE, bukan SET NULL."""
    with _koneksi().connect() as conn:
        aturan = conn.execute(
            text(
                """
                select rc.delete_rule
                from information_schema.referential_constraints rc
                join information_schema.table_constraints tc
                  on tc.constraint_name = rc.constraint_name
                join information_schema.constraint_column_usage ccu
                  on ccu.constraint_name = rc.constraint_name
                where tc.table_name = 'sap_mock_purchase_orders'
                  and ccu.table_name = 'decisions'
                """
            )
        ).scalar_one()
    assert aturan == "CASCADE", f"FK PO→decisions masih {aturan}"


def test_hapus_keputusan_ikut_menghapus_po():
    """Hapus keputusan demo = hapus PO-nya, nol baris yatim."""
    did = uuid.uuid4()
    pid = uuid.uuid5(did, "po")
    koneksi = _koneksi()
    try:
        with koneksi.begin() as conn:
            supplier = conn.execute(
                text("select id from suppliers order by name limit 1")
            ).scalar_one()
            conn.execute(
                text(
                    """
                    insert into decisions
                        (id, decision_type, status, proposed_by, iteration,
                         expires_at, origin, created_at)
                    values (:id, 'price_anomaly', 'executed', 'detection_agent', 1,
                            now() + interval '1 day', 'demo', now())
                    """
                ),
                {"id": did},
            )
            conn.execute(
                text(
                    """
                    insert into sap_mock_purchase_orders
                        (id, po_number, supplier_id, material_number,
                         ordered_quantity, price, decision_id, status, created_at)
                    values (:pid, 'PO-UJI-CASCADE', :sup, 'T-001', 10, 1000,
                            :did, 'draft', now())
                    """
                ),
                {"pid": pid, "sup": supplier, "did": did},
            )

        with koneksi.begin() as conn:
            assert (
                conn.execute(
                    text(
                        "select count(*) from sap_mock_purchase_orders "
                        "where decision_id = :did"
                    ),
                    {"did": did},
                ).scalar_one()
                == 1
            )
            conn.execute(text("delete from decisions where id = :id"), {"id": did})

        with koneksi.connect() as conn:
            sisa = conn.execute(
                text("select count(*) from sap_mock_purchase_orders where id = :pid"),
                {"pid": pid},
            ).scalar_one()
        # Catatan: PO kanonik dari `sprint1_seed.json` memang tanpa keputusan
        # (PO historis SAP), jadi yang diperiksa di sini hanya PO milik
        # keputusan yang baru saja dihapus.
        assert sisa == 0, "PO harus ikut terhapus bersama keputusannya"
    finally:
        koneksi.dispose()
