"""Biaya komersial PO/invoice dan SDC analitis — satu resolver, dua arti.

Kontrak (rencana Fase 5, dipakai Fase 9):

- `invoice_total = bahan + transportasi + handling`. Penalti risiko **tidak**
  pernah masuk invoice; PO menagih barang dan logistik, bukan kerugian internal.
- `sdc_total = invoice_total + expected_loss + freshness_risk + safety_penalty`
  (enam komponen). SDC adalah biaya analitis untuk membandingkan pilihan.
- `risk_method` menyebut dasar bobotnya: `simulated_policy` (bobot demo),
  `calibrated_model` (hanya bila benar-benar ada kalibrasi), atau `unavailable`
  (tidak ada dasar). Tidak ada jalur yang diam-diam mengubah bobot demo menjadi
  "kerugian aktual".
- Keputusan administratif tanpa kuantitas/biaya transfer mengembalikan `None`
  supaya UI menampilkan "tidak berlaku", bukan Rp 0 karangan.

Nilai uang keluar sebagai string desimal 2 angka supaya tidak kehilangan
presisi di JSON; frontend memformatnya, tidak menghitung ulang.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Mapping

_TWO_DP = Decimal("0.01")

#: Tempat bobot risiko hidup hari ini. Dipakai sebagai `source` default.
_BOBOT_SOURCE = "app/core/safe_delivered_cost.py:bobot_demo"
_BOBOT_VERSION = "sdc-policy-1"

KIND_VALID = ("simulated_policy", "calibrated_model", "unavailable")

_KOMPONEN_INVOICE = ("purchase", "transport", "handling")
_KOMPONEN_PENALTI = ("expected_loss", "freshness_risk", "safety_penalty")

_HILANG = object()


def _desimal(nilai: Any) -> Decimal | None:
    """Parse uang dari string/angka; `None` bila tidak bisa diartikan.

    `bool` ditolak karena `True` bukan nominal. NaN/inf ditolak karena tidak
    bisa dibulatkan dan akan merusak total tanpa galat.
    """
    if nilai is None or isinstance(nilai, bool):
        return None
    if isinstance(nilai, Decimal):
        hasil = nilai
    else:
        try:
            hasil = Decimal(str(nilai).strip())
        except (InvalidOperation, ValueError):
            return None
    if not hasil.is_finite():
        return None
    return hasil


def _uang(nilai: Decimal) -> Decimal:
    return nilai.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class RiskMethod:
    """Dasar dan versi metode risiko; bagian dari bukti, bukan hiasan."""

    kind: str
    source: str
    version: str
    period: str | None = None
    baseline: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "kind": self.kind,
            "source": self.source,
            "version": self.version,
            "period": self.period,
            "baseline": self.baseline,
        }


@dataclass(frozen=True)
class CommercialCost:
    purchase_total: Decimal
    transport_total: Decimal
    handling_total: Decimal
    invoice_total: Decimal
    invoice_unit_price: Decimal
    expected_loss: Decimal | None
    freshness_risk: Decimal | None
    safety_penalty: Decimal | None
    sdc_total: Decimal | None
    sdc_unit_price: Decimal | None
    risk_method: RiskMethod

    def as_dict(self) -> dict[str, Any]:
        def _str_atau_none(nilai: Decimal | None) -> str | None:
            return None if nilai is None else str(nilai)

        return {
            "purchase_total": str(self.purchase_total),
            "transport_total": str(self.transport_total),
            "handling_total": str(self.handling_total),
            "invoice_total": str(self.invoice_total),
            "invoice_unit_price": str(self.invoice_unit_price),
            # Komponen penalti dikirim terpisah supaya UI bisa menampilkannya di
            # blok SDC saja — bukan sebagai biaya yang ditagihkan.
            "expected_loss": _str_atau_none(self.expected_loss),
            "freshness_risk": _str_atau_none(self.freshness_risk),
            "safety_penalty": _str_atau_none(self.safety_penalty),
            "sdc_total": _str_atau_none(self.sdc_total),
            "sdc_unit_price": _str_atau_none(self.sdc_unit_price),
            "risk_method": self.risk_method.as_dict(),
        }


def _risk_method(
    breakdown: Mapping[str, Any], ada_sdc: bool
) -> RiskMethod:
    mentah = breakdown.get("risk_method")
    if isinstance(mentah, Mapping):
        kind = mentah.get("kind")
        source = mentah.get("source")
        version = mentah.get("version")
        if (
            isinstance(kind, str)
            and kind in KIND_VALID
            and kind != "unavailable"
            and isinstance(source, str)
            and source.strip()
            and isinstance(version, str)
            and version.strip()
        ):
            period = mentah.get("period")
            baseline = mentah.get("baseline")
            return RiskMethod(
                kind=kind,
                source=source.strip(),
                version=version.strip(),
                period=period if isinstance(period, str) and period.strip() else None,
                baseline=(
                    baseline if isinstance(baseline, str) and baseline.strip() else None
                ),
            )
        # Ada `risk_method` tapi tidak bisa dibaca: produsennya berniat menyebut
        # dasar tertentu yang tidak kita pahami. Menebak "simulated_policy" akan
        # mengarang dasar, jadi nyatakan tidak tersedia.
        return RiskMethod(
            kind="unavailable",
            source="cost_breakdown.risk_method",
            version="n/a",
            baseline="metode risiko tidak terbaca",
        )
    if ada_sdc:
        # Komponen SDC dihitung dari bobot demo di `safe_delivered_cost.py`.
        return RiskMethod(
            kind="simulated_policy", source=_BOBOT_SOURCE, version=_BOBOT_VERSION
        )
    return RiskMethod(
        kind="unavailable",
        source="cost_breakdown",
        version="n/a",
        baseline="komponen penalti tidak tercatat",
    )


def commercial_cost(
    quantity_kg: Any, breakdown: Mapping[str, Any] | None
) -> CommercialCost | None:
    """Resolver tunggal invoice+SDC; `None` bila tidak ada biaya transfer.

    `None` dikembalikan untuk kuantitas kosong/nol/negatif, rincian kosong,
    harga bahan tidak terbaca atau nol, komponen wajib yang bukan angka, dan
    rincian invoice yang tidak lengkap (mis. transportasi tidak tercatat) —
    karena invoice yang lebih kecil dari kenyataan adalah angka yang salah.
    Tidak ada pembagian dengan nol dan tidak ada invoice dummy.
    """
    kuantitas = _desimal(quantity_kg)
    if kuantitas is None or kuantitas <= 0:
        return None
    if not isinstance(breakdown, Mapping):
        return None

    purchase = _desimal(breakdown.get("purchase", _HILANG))
    if purchase is None or purchase <= 0:
        return None

    komponen: dict[str, Decimal] = {"purchase": _uang(purchase)}
    for kunci in _KOMPONEN_INVOICE:
        if kunci == "purchase":
            continue
        mentah = breakdown.get(kunci, _HILANG)
        if mentah is _HILANG:
            # Transportasi/handling yang tidak tercatat membuat total invoice
            # lebih kecil dari kenyataan (dua keputusan `regional_balance` di
            # data demo hanya berisi `purchase`). Lebih baik tidak mengklaim
            # biaya sama sekali daripada menerbitkan PO yang salah.
            return None
        dibaca = _desimal(mentah)
        # Komponen yang ADA tapi tidak terbaca bukan nol: biaya yang tidak bisa
        # diartikan tidak boleh disamarkan jadi Rp 0.
        if dibaca is None or dibaca < 0:
            return None
        komponen[kunci] = _uang(dibaca)

    invoice_total = _uang(
        komponen["purchase"] + komponen["transport"] + komponen["handling"]
    )
    invoice_unit = _uang(invoice_total / kuantitas)

    penalti: dict[str, Decimal] = {}
    for kunci in _KOMPONEN_PENALTI:
        dibaca = _desimal(breakdown.get(kunci))
        if dibaca is None or dibaca < 0:
            penalti = {}
            break
        penalti[kunci] = _uang(dibaca)

    if penalti:
        sdc_total = _uang(invoice_total + sum(penalti.values(), Decimal("0.00")))
        sdc_unit: Decimal | None = _uang(sdc_total / kuantitas)
    else:
        sdc_total = None
        sdc_unit = None

    return CommercialCost(
        purchase_total=komponen["purchase"],
        transport_total=komponen["transport"],
        handling_total=komponen["handling"],
        invoice_total=invoice_total,
        invoice_unit_price=invoice_unit,
        expected_loss=penalti.get("expected_loss"),
        freshness_risk=penalti.get("freshness_risk"),
        safety_penalty=penalti.get("safety_penalty"),
        sdc_total=sdc_total,
        sdc_unit_price=sdc_unit,
        risk_method=_risk_method(breakdown, ada_sdc=sdc_total is not None),
    )


def commercial_cost_payload(
    quantity_kg: Any, breakdown: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    """Bentuk siap-JSON untuk endpoint; `None` = tidak berlaku (bukan Rp 0)."""
    biaya = commercial_cost(quantity_kg, breakdown)
    return None if biaya is None else biaya.as_dict()
