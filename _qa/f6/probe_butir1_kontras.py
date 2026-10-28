"""Kontras gerbang Fase 6 butir 1 — RED-equivalent tanpa menyentuh berkas repo.

Input IDENTIK dijalankan dua kali: jalur lama (tanpa profil komoditas, `policies=None`)
dan jalur bergerbang (profil komoditas). Jalur lama meloloskan batch yang log suhunya
kosong sebagai kandidat berskor tinggi — itulah perilaku yang diperbaiki; jalur
bergerbang menahannya sebagai `on_hold` beserta alasannya.

Jalankan di kontainer backend: python /tmp/probe.py  (tanpa DB, tanpa HTTP)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core import batch_eligibility as be
from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates
from app.core.commodity_policy import policy_for

SEKARANG = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def batch_tanpa_log() -> dict:
    return {
        "batch_id": "b-kosong",
        "supplier_id": "sup-a",
        "location": "Bandung",
        "commodity": "telur",
        "quantity_kg": Decimal("200"),
        "freshness_score": Decimal("0.95"),
        "freshness_status": "pass",
        "safety_status": "pass",
        "quarantine_status": "none",
        "usable_until": SEKARANG + timedelta(days=4),
        "temperature_log": [],
        "temperature_observation": "observed",
        "evidence_state": "sufficient",
    }


INPUT = dict(
    source_records={
        ("Bandung", "telur"): Decimal("500"),
        ("Jakarta", "telur"): Decimal("0"),
    },
    destination_records={
        ("Jakarta", "telur"): Decimal("300"),
        ("Bandung", "telur"): Decimal("0"),
    },
    batches=[batch_tanpa_log()],
    logistics_by_pair={("Bandung", "Jakarta"): {"feasible": True, "distance_km": 150.0, "estimated_time_min": 180}},
    prices={("Bandung", "Jakarta", "telur"): PriceInfo(reference_price=Decimal("30000"))},
    evaluation_time=SEKARANG,
)

held_lama: list = []
lama = generate_candidates(**INPUT, held=held_lama)
print("JALUR LAMA (policies=None)      :", len(lama), "kandidat,",
      len(held_lama), "ditahan",
      [(r.source_location, r.commodity, str(r.freshness_score)) for r in lama])

held_baru: list = []
baru = generate_candidates(**INPUT, policies={"telur": policy_for("telur")}, held=held_baru)
print("JALUR BERGERBANG (profil telur) :", len(baru), "kandidat,",
      len(held_baru), "ditahan")
for h in held_baru:
    print("   status =", h.status, "| lapis =", h.layer,
          "| alasan =", h.blocking_reasons, "| langkah =", h.next_step)
assert not lama and lama is not None or True  # noqa: SIM223 - hanya cetak
assert lama, "jalur lama harus meloloskan kandidat (bukti perilaku yang diperbaiki)"
assert not baru, "jalur bergerbang tidak boleh meloloskan batch tanpa bukti"
assert held_baru and held_baru[0].status == be.ON_HOLD
print("KONTRAS TERBUKTI: input sama → lama lolos, bergerbang menahan on_hold.")
