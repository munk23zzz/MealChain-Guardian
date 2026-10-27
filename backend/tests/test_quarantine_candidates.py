"""Batch berstatus karantina tidak pernah menjadi kandidat alokasi.

Ini pembeda penting dari `needs_verification`: batch yang ditahan berarti
kilogramnya TIDAK boleh dipakai menyusun rekomendasi, walaupun stok fisiknya
masih tercatat (physical inventory != usable inventory).
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates

REF = Decimal("26500")
SUPPLIER = "11111111-1111-1111-1111-111111111111"


def _batch(**overrides):
    base = {
        "location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": Decimal("600"),
        "freshness_score": Decimal("0.92"),
        "freshness_status": "pass",
        "usable_until": datetime(2099, 1, 1, tzinfo=timezone.utc),
        "safety_status": "needs_verification",
        "supplier_id": SUPPLIER,
        "batch_id": "b-1",
        "quarantine_status": "none",
    }
    base.update(overrides)
    return base


def _inputs(batches):
    source = {("Cianjur", "telur"): Decimal("1400"), ("Jakarta", "telur"): Decimal("300")}
    dest = {("Cianjur", "telur"): Decimal("500"), ("Jakarta", "telur"): Decimal("1000")}
    logistics = {
        ("Cianjur", "Jakarta"): {
            "distance_km": 120,
            "estimated_time_min": 150.0,
            "feasible": True,
        }
    }
    prices = {
        ("Cianjur", "Jakarta", "telur"): PriceInfo(
            reference_price=REF, supplier_quote=Decimal("26200"), supplier_id=SUPPLIER
        )
    }
    return source, dest, batches, logistics, prices


def test_batch_needs_verification_tetap_jadi_kandidat():
    """Kontrol positif: tanpa karantina, batch ini memang masuk kandidat."""
    s, d, b, lg, p = _inputs([_batch()])
    out = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    assert len(out) == 1
    assert out[0].safety_status == "needs_verification"


def test_batch_karantina_tidak_menjadi_kandidat():
    s, d, b, lg, p = _inputs([_batch(quarantine_status="quarantined")])
    out = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    assert out == []


def test_batch_dilepas_kembali_masuk_kandidat():
    s, d, b, lg, p = _inputs([_batch(quarantine_status="released")])
    out = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    assert len(out) == 1


def test_hanya_batch_karantina_yang_menyisakan_pasokan_terbatas():
    """Dua batch, satu ditahan: kuantitas kandidat hanya dari yang bebas."""
    batches = [
        _batch(batch_id="b-1", quantity_kg=Decimal("600"), quarantine_status="quarantined"),
        _batch(batch_id="b-2", quantity_kg=Decimal("150"), quarantine_status="none"),
    ]
    s, d, b, lg, p = _inputs(batches)
    out = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    assert len(out) == 1
    assert out[0].quantity_kg == Decimal("150")
    assert out[0].batch_ids == ("b-2",)


def test_batch_tanpa_kunci_karantina_diperlakukan_sebagai_bebas():
    """Kontrak lama (7-tuple facts) tidak mengenal kolom ini — jangan pecah."""
    batch = _batch()
    batch.pop("quarantine_status")
    s, d, b, lg, p = _inputs([batch])
    out = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    assert len(out) == 1
