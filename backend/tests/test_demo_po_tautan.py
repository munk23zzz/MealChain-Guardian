"""Tautan keputusan→PO (D-05 / NUM-01): hanya yang pemicunya TERBUKTI.

Latar: KPI `Safe Delivered Cost` hanya menghitung PO yang tertaut ke keputusan
(`kpi_service.py:349-353`), sedangkan builder meninggalkan PO tanpa `decision_id`
sehingga rantai keputusan→PO tidak terbukti dan invarian ">1 PO per keputusan"
lulus secara vakum.

Dua hal dikunci di sini:

1. pemetaan material→komoditas dan pemilihan keputusan pemicu TIDAK menebak:
   kandidat nol atau lebih dari satu menghasilkan None;
2. PO impor SAP yang tidak punya pemicu dibiarkan NULL — dan itu dibuktikan
   lewat query, bukan diasumsikan. Memasangkannya ke keputusan berkomoditas
   sama akan menjadi relasi karangan.
"""

from __future__ import annotations

from decimal import Decimal

from app.seed.demo_template import komoditas_material, pilih_keputusan_pemicu

KOMODITAS = {"telur", "ayam", "wortel", "beras", "jagung"}


def test_material_sap_angka_dipetakan():
    assert komoditas_material("1000", KOMODITAS) == "telur"
    assert komoditas_material("1001", KOMODITAS) == "ayam"
    assert komoditas_material("1002", KOMODITAS) == "wortel"
    assert komoditas_material("1003", KOMODITAS) == "beras"


def test_material_po_eksekusi_dipetakan():
    assert komoditas_material("MAT-BERA", KOMODITAS) == "beras"
    assert komoditas_material("MAT-TELU", KOMODITAS) == "telur"


def test_material_tak_dikenal_tidak_ditebak():
    assert komoditas_material("9999", KOMODITAS) is None
    assert komoditas_material(None, KOMODITAS) is None
    assert komoditas_material("MAT-UMUM", KOMODITAS) is None


def test_keputusan_pemicu_tunggal_dipilih():
    kandidat = [
        {"id": "a", "quantity_kg": Decimal("600.00")},
        {"id": "b", "quantity_kg": Decimal("500.00")},
    ]
    assert pilih_keputusan_pemicu(Decimal("500.00"), kandidat)["id"] == "b"


def test_keputusan_pemicu_ambigu_tidak_dipilih():
    """Dua kandidat sama-sama cocok = tidak ada bukti mana pemicunya."""
    kandidat = [
        {"id": "a", "quantity_kg": Decimal("600.00")},
        {"id": "b", "quantity_kg": Decimal("600.00")},
    ]
    assert pilih_keputusan_pemicu(Decimal("600.00"), kandidat) is None


def test_keputusan_pemicu_kuantitas_beda_tidak_dipilih():
    kandidat = [{"id": "a", "quantity_kg": Decimal("600.00")}]
    assert pilih_keputusan_pemicu(Decimal("500.00"), kandidat) is None
    assert pilih_keputusan_pemicu(Decimal("600.00"), []) is None


def test_po_impor_tanpa_keputusan_tidak_punya_kandidat():
    """Bukti bahwa mengisi `decision_id` PO impor = mengarang relasi.

    Untuk SETIAP PO tanpa keputusan, tidak ada satu pun keputusan `executed`
    dengan pemasok + komoditas + kuantitas yang sama. Kalau angka ini bukan 0,
    berarti ada relasi yang bisa diisi secara sah dan builder wajib mengisinya.
    """
    from sqlalchemy import create_engine, text

    from tests.dsn import DSN_SYNC

    mesin = create_engine(DSN_SYNC, pool_pre_ping=True)
    with mesin.connect() as conn:
        baris = conn.execute(
            text(
                """
                SELECT o.po_number, count(d.id) AS kandidat
                FROM sap_mock_purchase_orders o
                JOIN suppliers s ON s.id = o.supplier_id
                LEFT JOIN commodities c
                  ON c.name = CASE o.material_number
                       WHEN '1000' THEN 'telur'
                       WHEN '1001' THEN 'ayam'
                       WHEN '1002' THEN 'wortel'
                       WHEN '1003' THEN 'beras'
                     END
                LEFT JOIN decisions d
                  ON d.supplier_id = o.supplier_id
                 AND d.commodity_id = c.id
                 AND d.status = 'executed'
                 AND abs(d.quantity_kg - o.ordered_quantity) <= 0.01
                WHERE o.decision_id IS NULL
                GROUP BY o.po_number
                ORDER BY o.po_number
                """
            )
        ).all()

    dengan_kandidat = [r[0] for r in baris if r[1] > 0]
    assert not dengan_kandidat, (
        "PO berikut punya keputusan pemicu yang sah tetapi masih NULL: "
        f"{dengan_kandidat}"
    )
