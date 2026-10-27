"""Sidik keputusan (fingerprint approval) — Fase 4 MG butir 4.

Kenapa modul ini ada: approval manusia diberikan atas **bukti tertentu**, bukan
atas "keputusan dengan id ini". Hari ini yang mengikat approval ke keputusan
hanya kolom dasar (kuantitas, biaya, lokasi, komoditas). Batch dan pemasok yang
menentukan kelayakan tidak ikut disidik, begitu pula versi policy komoditas dan
hasil evaluator. Akibatnya urutan berikut tidak pernah menggugurkan approval
lama:

1. batch sumber diganti batch lain (stok berbeda, suhu berbeda),
2. pemasok pada pasangan itu bertambah sehingga binding berubah,
3. profil komoditas naik versi (rentang suhu/sampel minimum berubah),
4. evaluator berubah dari `usable` menjadi `on_hold` (bukti suhu kurang).

Modul ini membuat keempat perubahan itu **terlihat sebagai sidik yang berbeda**,
sehingga `sidik_cocok(tersimpan=None) -> False` dan keputusan wajib direview
ulang. Ia tidak menyimpan atau membaca apa pun: pemanggil menyimpan nilainya.

Modul MURNI: tanpa DB, tanpa HTTP, tanpa jam dinding, tanpa SQLAlchemy/FastAPI.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = [
    "SidikApproval",
    "dari_decision",
    "hitung_sidik",
    "sidik_cocok",
]

#: Status evaluator yang boleh menjadi bagian sidik. `rejected`/`quarantined`
#: tidak pernah sampai ke approval, jadi tidak perlu masuk kontrak.
_STATUS_EVALUASI = frozenset({"usable", "on_hold"})

_PREFIX = "sha256:"


def _teks_wajib(nilai: Any, nama: str) -> str:
    teks = str(nilai or "").strip()
    if not teks:
        raise ValueError(f"{nama} wajib diisi untuk sidik keputusan")
    return teks


def _angka(nilai: Any, nama: str) -> str:
    """Bentuk kanonik angka: `600`, `600.0`, dan `600.00` harus sama."""
    try:
        angka = Decimal(str(nilai))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{nama} bukan angka valid: {nilai!r}") from exc
    if not angka.is_finite():
        raise ValueError(f"{nama} wajib angka finite: {nilai!r}")
    teks = format(angka.normalize(), "f")
    return "0" if teks in ("-0", "") else teks


def _daftar_unik(nilai: Any) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in (nilai or ()) if str(item).strip()}))


@dataclass(frozen=True)
class SidikApproval:
    """Bukti yang disetujui manusia; setiap bidang ikut disidik."""

    decision_id: str
    batch_ids: tuple[str, ...]
    supplier_id: str | None
    quantity_kg: Any
    cost_idr: Any
    source_location_id: str | None
    target_location_id: str | None
    commodity_id: str
    policy_version: str
    evaluation_status: str
    blocking_reasons: tuple[str, ...] = field(default_factory=tuple)


def _kanonik(seed: SidikApproval) -> dict:
    status = _teks_wajib(seed.evaluation_status, "evaluation_status").lower()
    if status not in _STATUS_EVALUASI:
        raise ValueError(
            f"evaluation_status wajib salah dari {sorted(_STATUS_EVALUASI)}, "
            f"dapat {seed.evaluation_status!r}"
        )
    return {
        "decision_id": _teks_wajib(seed.decision_id, "decision_id").lower(),
        "batch_ids": list(_daftar_unik(seed.batch_ids)),
        "supplier_id": (
            _teks_wajib(seed.supplier_id, "supplier_id").lower()
            if seed.supplier_id
            else None
        ),
        "quantity_kg": _angka(seed.quantity_kg, "quantity_kg"),
        "cost_idr": _angka(seed.cost_idr, "cost_idr"),
        "source_location_id": (
            str(seed.source_location_id).strip().lower()
            if seed.source_location_id
            else None
        ),
        "target_location_id": (
            str(seed.target_location_id).strip().lower()
            if seed.target_location_id
            else None
        ),
        "commodity_id": _teks_wajib(seed.commodity_id, "commodity_id").lower(),
        "policy_version": _teks_wajib(seed.policy_version, "policy_version"),
        "evaluation_status": status,
        "blocking_reasons": list(_daftar_unik(seed.blocking_reasons)),
    }


def hitung_sidik(seed: SidikApproval) -> str:
    """Sidik heksadesimal deterministik dari bukti yang disetujui."""
    muatan = json.dumps(
        _kanonik(seed), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return _PREFIX + hashlib.sha256(muatan.encode("utf-8")).hexdigest()


def sidik_cocok(seed: SidikApproval, tersimpan: str | None) -> bool:
    """True hanya bila sidik tersimpan ADA dan sama persis.

    `None`/kosong berarti approval lama tanpa sidik. Itu **tidak** boleh
    dianggap cocok: kalau dianggap cocok, seluruh tujuan modul ini hilang untuk
    setiap keputusan yang lahir sebelum perubahan ini.
    """
    if not tersimpan:
        return False
    return hitung_sidik(seed) == str(tersimpan).strip()


def dari_decision(
    decision: Any,
    *,
    batch_ids: Any,
    supplier_id: str | None = None,
    policy_version: str,
    evaluation_status: str,
    blocking_reasons: Any = (),
) -> SidikApproval:
    """Bangun sidik dari baris keputusan + hasil evaluator yang disetujui.

    `supplier_id=None` berarti "pakai kolom keputusan" (bukan "tanpa
    pemasok"): pemanggil yang sudah me-resolve binding mengirim id eksplisit.
    Tidak ada nilai yang ditebak di sini — kolom yang tidak ada menjadi
    `None`, dan kolom wajib yang kosong melempar ValueError.
    """
    identitas = getattr(decision, "id", None) or getattr(decision, "decision_id", None)
    return SidikApproval(
        decision_id=_teks_wajib(identitas, "decision.id"),
        batch_ids=_daftar_unik(batch_ids),
        supplier_id=(
            _teks_wajib(supplier_id, "supplier_id")
            if supplier_id
            else (str(getattr(decision, "supplier_id", "") or "") or None)
        ),
        quantity_kg=getattr(decision, "quantity_kg", None),
        cost_idr=getattr(decision, "safe_delivered_cost", None),
        source_location_id=getattr(decision, "source_location_id", None),
        target_location_id=getattr(decision, "target_location_id", None),
        commodity_id=_teks_wajib(
            getattr(decision, "commodity_id", None), "decision.commodity_id"
        ),
        policy_version=policy_version,
        evaluation_status=evaluation_status,
        blocking_reasons=blocking_reasons,
    )
