"""Konsistensi bukti — payload diturunkan ULANG dari sumbernya (murni, tanpa I/O).

Ruling 2026-10-16: `decision_evidence.is_consistent` tidak boleh lagi selalu
NULL (dua penulis bukti menulisnya apa adanya `None`, sehingga metrik
**Evidence Completeness** — "≥2 tipe bukti konsisten sebelum approval pertama"
— mustahil terpenuhi dan menampilkan 0,00% berlabel "tersedia"). Nilainya kini
dihitung di sini dengan definisi yang tegas:

- ``True``  — payload bukti **cocok** dengan fakta yang ia kutip, setelah
  diturunkan ulang: harga & klasifikasi dihitung ulang dari baris
  `price_signals`, status suhu dihitung ulang dari log mentah batch, binding
  batch dibandingkan dengan baris `batches` yang dibaca dari DB.
- ``False`` — payload **tidak** cocok dengan sumbernya. Itu temuan integritas
  (bukti diubah, batch pindah pemasok, alasan eksklusi dikosongkan), dan
  sengaja TIDAK diubah menjadi kegagalan penulisan.
- ``None``  — tidak bisa dinilai karena fakta yang dibutuhkan tidak ada
  (keputusan lama tanpa lokasi sumber, baris harga acuan hilang). NULL tetap
  berarti "belum dinilai"; ia tidak boleh diisi ``True`` supaya metrik penuh.

Batasnya jujur: fungsi-fungsi ini menilai **kecocokan bukti dengan rekaman
DB**, bukan kualitas/kebenaran keputusan — dan untuk bukti yang ditulis
pipeline deterministik hasilnya pasti ``True`` selama sumber mentahnya tidak
berubah. Yang ditangkapnya adalah bukti yang tidak lagi sesuai sumbernya.

Semua fungsi murni: tanpa DB, tanpa jaringan, tanpa LLM.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.kpi import quantize2


def _text(value: Any) -> str | None:
    """Normalisasi id/nilai teks; None tetap None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    """Decimal dari nilai payload/DB; nilai tak terbaca → None (tidak dinilai)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _same_text(payload_value: Any, fact: Any) -> bool:
    return _text(payload_value) == _text(fact)


def _same_decimal(payload_value: Any, fact: Decimal | None, *, places: int | None = 2) -> bool:
    left = _decimal(payload_value)
    right = _decimal(fact)
    if left is None or right is None:
        return False
    if places is not None:
        left, right = quantize2(left), quantize2(right)
    return left == right


# ---------------------------------------------------------------------------
# human_inspection — binding batch/supplier (services/supplier_eligibility.py)
# ---------------------------------------------------------------------------


def binding_consistency(
    payload: dict,
    *,
    batch_ids,
    batch_suppliers,
    batch_locations,
    batch_commodities,
    supplier_id,
    source_location_id,
    commodity_id,
) -> bool | None:
    """Bukti "semua batch ini milik supplier ini di lokasi sumber ini".

    Dinilai dengan membandingkan payload terhadap baris `batches` yang dibaca
    dari DB. Fakta tidak lengkap (keputusan lama tanpa lokasi/komoditas, tanpa
    batch) → None: menilai dengan fakta separuh akan menghasilkan True palsu.
    """
    if payload.get("allocation_binding") is not True:
        return None
    if supplier_id is None or source_location_id is None or commodity_id is None:
        return None
    if not batch_ids:
        return None

    claimed = sorted({str(value) for value in (payload.get("batch_ids") or [])})
    actual = sorted({str(value) for value in batch_ids})
    return (
        claimed == actual
        and _same_text(payload.get("supplier_id"), supplier_id)
        and {str(value) for value in batch_suppliers} == {_text(supplier_id)}
        and {str(value) for value in batch_locations} == {_text(source_location_id)}
        and {str(value) for value in batch_commodities} == {_text(commodity_id)}
    )


# ---------------------------------------------------------------------------
# human_inspection — aksi administratif (services/supplier_exclusion_service.py)
# ---------------------------------------------------------------------------


def administrative_consistency(
    payload: dict, *, supplier_id, scope_location_id, supplier_exists: bool
) -> bool | None:
    """Bukti aksi administratif: pemasok ada, scope cocok, alasan tertulis.

    Alasan kosong bukan detail kosmetik: eksklusi tanpa alasan tidak bisa
    ditinjau, jadi buktinya dihitung tidak konsisten.
    """
    if payload.get("administrative_action") is None:
        return None
    if supplier_id is None or scope_location_id is None:
        return None
    return (
        bool(supplier_exists)
        and _same_text(payload.get("supplier_id"), supplier_id)
        and _same_text(payload.get("scope_location_id"), scope_location_id)
        and bool(_text(payload.get("reason")) or "")
    )


# ---------------------------------------------------------------------------
# market_price (services/event2_service.py)
# ---------------------------------------------------------------------------


def market_price_consistency(
    payload: dict,
    *,
    quote_price,
    reference_price,
    deviation_pct,
    classification,
) -> bool | None:
    """Bukti harga: kutipan & acuan cocok barisnya, deviasi/klasifikasi sama.

    `quote_price`/`reference_price`/`deviation_pct`/`classification` adalah
    hasil BACA ULANG dari baris `price_signals` + hitungan ulang
    `core.price.price_deviation` oleh pemanggil — bukan dari payload.
    """
    if any(
        value is None
        for value in (quote_price, reference_price, deviation_pct, classification)
    ):
        return None
    return (
        _same_decimal(payload.get("quoted_price_per_kg"), Decimal(str(quote_price)))
        and _same_decimal(payload.get("reference_price_per_kg"), Decimal(str(reference_price)))
        and _same_decimal(payload.get("deviation_pct"), Decimal(str(deviation_pct)))
        and _same_text(payload.get("classification"), classification)
    )


# ---------------------------------------------------------------------------
# temperature (services/event3_service.py)
# ---------------------------------------------------------------------------


def temperature_consistency(
    payload: dict, *, safety_status, excursion_minutes
) -> bool | None:
    """Bukti suhu: status & menit penyimpangan sama dengan hitung ulang log.

    Toleransi 0,01 menit hanya untuk pembulatan float->Decimal pada menit;
    status harus sama persis (kosakata tertutup: pending/pass/fail/
    needs_verification).
    """
    if safety_status is None or excursion_minutes is None:
        return None
    payload_status = _text(payload.get("safety_status"))
    payload_minutes = _decimal(payload.get("excursion_minutes"))
    if payload_status is None or payload_minutes is None:
        return False
    recomputed = _decimal(excursion_minutes)
    if recomputed is None:
        return None
    return payload_status == _text(safety_status) and abs(payload_minutes - recomputed) <= Decimal(
        "0.01"
    )
