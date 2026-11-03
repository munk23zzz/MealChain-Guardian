"""Kontrak resolver `CommercialCost` — prasyarat Fase 9 (inti Fase 5).

Angka contoh diambil dari rencana Fase 5 butir 1 (bukan disalin mentah): purchase
5.700.000, transport 34.200, handling 150.000, expected loss 100.000,
freshness risk 0, safety penalty 0, kuantitas 200 kg.

- invoice_total = bahan + transportasi + handling = 5.884.200
- sdc_total     = enam komponen               = 5.984.200
- invoice_unit_price = 5.884.200 / 200 = 29.421,00
- sdc_unit_price     = 5.984.200 / 200 = 29.921,00

Tes ini murni logika (tanpa DB), sehingga bisa dijalankan pada DB klon apa pun.
"""

from decimal import Decimal

import pytest

from app.core.commercial_cost import RiskMethod, commercial_cost


def _breakdown(**override: object) -> dict[str, object]:
    """Rincian biaya dengan bentuk yang sama seperti yang disimpan backend."""
    nilai: dict[str, object] = {
        "purchase": "5700000.00",
        "transport": "34200.00",
        "handling": "150000.00",
        "expected_loss": "100000.00",
        "freshness_risk": "0.00",
        "safety_penalty": "0.00",
        "basis": "dihitung: kutipan pemasok + rute",
    }
    nilai.update(override)
    return nilai


class TestInvoiceDanSdc:
    def test_invoice_hanya_bahan_transport_handling(self):
        biaya = commercial_cost(Decimal("200"), _breakdown())

        assert biaya is not None
        assert biaya.invoice_total == Decimal("5884200.00")

    def test_sdc_memuat_enam_komponen(self):
        biaya = commercial_cost(Decimal("200"), _breakdown())

        assert biaya is not None
        assert biaya.sdc_total == Decimal("5984200.00")

    def test_harga_satuan_dua_desimal(self):
        biaya = commercial_cost(Decimal("200"), _breakdown())

        assert biaya is not None
        assert biaya.invoice_unit_price == Decimal("29421.00")
        assert biaya.sdc_unit_price == Decimal("29921.00")

    def test_penalti_risiko_tidak_masuk_invoice(self):
        """Penalti hanya mengubah SDC: invoice tidak boleh ikut naik."""
        dasar = commercial_cost(Decimal("200"), _breakdown())
        berisiko = commercial_cost(
            Decimal("200"),
            _breakdown(
                expected_loss="900000.00",
                freshness_risk="250000.00",
                safety_penalty="400000.00",
            ),
        )

        assert dasar is not None and berisiko is not None
        assert berisiko.invoice_total == dasar.invoice_total
        assert berisiko.sdc_total > dasar.sdc_total
        # 5.884.200 + (900.000 + 250.000 + 400.000) = 7.434.200
        assert berisiko.sdc_total == Decimal("7434200.00")

    def test_pembulatan_half_up_per_kg(self):
        """11 / 3 = 3,666… → 3,67 (HALF_UP), bukan 3,66."""
        biaya = commercial_cost(
            Decimal("3"),
            _breakdown(
                purchase="10.00",
                transport="1.00",
                handling="0.00",
                expected_loss="1.00",
                freshness_risk="0.00",
                safety_penalty="0.00",
            ),
        )

        assert biaya is not None
        assert biaya.invoice_total == Decimal("11.00")
        assert biaya.invoice_unit_price == Decimal("3.67")
        assert biaya.sdc_total == Decimal("12.00")
        assert biaya.sdc_unit_price == Decimal("4.00")


class TestTanpaBiaya:
    """Keputusan administratif tanpa transfer: `None`, bukan invoice nol."""

    @pytest.mark.parametrize("kuantitas", [None, Decimal("0"), Decimal("-5")])
    def test_kuantitas_kosong_atau_nol(self, kuantitas):
        assert commercial_cost(kuantitas, _breakdown()) is None

    def test_breakdown_kosong(self):
        assert commercial_cost(Decimal("200"), {}) is None

    def test_breakdown_bukan_mapping(self):
        assert commercial_cost(Decimal("200"), None) is None

    def test_purchase_nol(self):
        assert commercial_cost(Decimal("200"), _breakdown(purchase="0.00")) is None

    def test_harga_bukan_angka(self):
        assert commercial_cost(Decimal("200"), _breakdown(purchase="n/a")) is None


class TestRiskMethod:
    def test_bobot_demo_ditandai_kebijakan_simulasi(self):
        biaya = commercial_cost(Decimal("200"), _breakdown())

        assert biaya is not None
        assert isinstance(biaya.risk_method, RiskMethod)
        assert biaya.risk_method.kind == "simulated_policy"
        # Sumber harus menunjuk tempat bobotnya hidup, bukan nama kosong.
        assert "safe_delivered_cost" in biaya.risk_method.source
        assert biaya.risk_method.version

    def test_risk_method_dari_breakdown_dipakai(self):
        biaya = commercial_cost(
            Decimal("200"),
            _breakdown(
                risk_method={
                    "kind": "calibrated_model",
                    "source": "model_risiko_v2.pkl",
                    "version": "v2.1",
                    "period": "2026-Q1..2026-Q2",
                    "baseline": "actual_loss",
                }
            ),
        )

        assert biaya is not None
        assert biaya.risk_method.kind == "calibrated_model"
        assert biaya.risk_method.version == "v2.1"
        assert biaya.risk_method.period == "2026-Q1..2026-Q2"

    def test_risk_method_tak_dikenal_tidak_dipaksakan(self):
        """Kind asing tidak boleh diam-diam jadi klaim 'model terkalibrasi'."""
        biaya = commercial_cost(
            Decimal("200"), _breakdown(risk_method={"kind": "karangan"})
        )

        assert biaya is not None
        assert biaya.risk_method.kind == "unavailable"

    def test_transport_tidak_tercatat_tidak_membuat_invoice(self):
        """Rincian hanya berisi `purchase`: invoice akan menutupi biaya logistik.

        Data demo punya dua keputusan `regional_balance` ber-rincian
        `{"purchase": ...}` saja. Mencetak PO dari angka itu berarti mengklaim
        total yang lebih kecil dari kenyataan, jadi tidak ada invoice sama sekali.
        """
        assert (
            commercial_cost(Decimal("600"), {"purchase": "15720000.00"}) is None
        )

    def test_komponen_penalti_hilang_sdc_tidak_tercatat(self):
        biaya = commercial_cost(
            Decimal("200"),
            {
                "purchase": "5700000.00",
                "transport": "34200.00",
                "handling": "150000.00",
            },
        )

        assert biaya is not None
        assert biaya.invoice_total == Decimal("5884200.00")
        assert biaya.sdc_total is None
        assert biaya.sdc_unit_price is None
        assert biaya.expected_loss is None
        assert biaya.risk_method.kind == "unavailable"


class TestSerialisasi:
    def test_as_dict_memakai_string_desimal(self):
        biaya = commercial_cost(Decimal("200"), _breakdown())

        assert biaya is not None
        data = biaya.as_dict()
        assert data["invoice_total"] == "5884200.00"
        assert data["sdc_total"] == "5984200.00"
        # Komponen penalti dikirim terpisah: UI menaruhnya di blok SDC.
        assert data["expected_loss"] == "100000.00"
        assert data["freshness_risk"] == "0.00"
        assert data["safety_penalty"] == "0.00"
        assert data["risk_method"]["kind"] == "simulated_policy"
        assert data["risk_method"]["version"]
