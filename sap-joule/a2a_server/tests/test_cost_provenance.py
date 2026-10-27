"""Laporan PO Joule: total yang DITAGIHKAN vs SDC analitis (Fase 5 butir 7).

Cacat yang dikunci: sebelum Fase 5 satu-satunya angka biaya di laporan PO
adalah `harga per kg` yang dulu berarti `SDC ÷ jumlah` — sehingga pembaca
mengira penalti risiko internal ikut ditagihkan ke pemasok. Sekarang laporan
memisahkan:

- **Total PO** (bahan + transportasi + penanganan) = yang dibayar pemasok;
- **SDC analitis** = pembanding internal, TIDAK ditagihkan;
- **basis biaya** (`cost_legacy`) supaya PO lama tidak terbaca berkontrak baru.

Tanpa `sdcTotal`, laporan tidak boleh menulis Rp 0 — absen ditulis sebagai absen.
"""

import report


def _po(**over):
    dasar = {
        "poNumber": "MC-AAAA00000001",
        "status": "submitted",
        "createdAt": "2026-10-27T02:20:00Z",
        "locationName": "SPPG Jakarta",
        "supplierName": "CV Contoh",
        "commodityName": "Telur",
        "quantityKg": 200.0,
        "pricePerKg": 29421.0,
        "totalValue": 5884200.0,
        "invoiceUnitPrice": 29421.0,
        "invoiceTotal": 5884200.0,
        "sdcTotal": 7434200.0,
        "costLegacy": "migrated",
        "decisionId": "d1",
        "decisionStatus": "executed",
        "origin": "execution",
    }
    dasar.update(over)
    return dasar


def test_total_po_dan_sdc_dipisah():
    teks = report.purchase_order_report([_po()], po_number="MC-AAAA00000001")

    assert "Total PO" in teks
    assert "Rp5.884.200" in teks
    assert "SDC" in teks
    assert "Rp7.434.200" in teks
    assert "tidak ditagihkan" in teks.lower()


def test_tanpa_sdc_tidak_menulis_rp0():
    teks = report.purchase_order_report([_po(sdcTotal=None)], po_number="MC-AAAA00000001")

    assert "Rp0" not in teks
    assert "SDC" in teks  # absennya tetap disebut, bukan dihilangkan


def test_basis_biaya_lama_ditandai():
    teks = report.purchase_order_report(
        [_po(costLegacy="legacy_unmigrated")], po_number="MC-AAAA00000001"
    )

    assert "legacy" in teks.lower() or "dimigrasi" in teks.lower()


def test_keputusan_tanpa_biaya_tidak_menampilkan_rp0():
    """PO tanpa angka komersial (baris impor SAP) tetap terbaca jujur."""
    teks = report.purchase_order_report(
        [
            _po(
                invoiceUnitPrice=None,
                invoiceTotal=None,
                sdcTotal=None,
                costLegacy="not_applicable",
                pricePerKg=None,
                totalValue=None,
            )
        ],
        po_number="MC-AAAA00000001",
    )

    assert "Rp0" not in teks
