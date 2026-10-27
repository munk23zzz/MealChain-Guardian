"""Hierarki keputusan pada ranah bahan + bukti yang tidak lengkap (Fase 6).

Kontrak yang dikunci berkas ini (MG/phase-06-decision-boundary.md butir 1, 2):

1. **Bukti yang gagal tidak boleh menjadi kandidat aman.** Batch yang buktinya
   tidak lengkap (log suhu kosong untuk komoditas rantai dingin, `safety`
   `pending`/`needs_verification`, masa layak tidak tercatat) menghasilkan
   `on_hold`/`rejected` BESERTA alasan — bukan `evidence_error` yang tetap
   meloloskan kandidat ke daftar usulan.
2. **Hierarki eksplisit di core.** Lapis 1 keselamatan/bukti, lapis 2
   kecukupan bahan & waktu tiba, lapis 3 kontinuitas pasokan, lapis 4 invoice &
   SDC, lapis 5 mitigasi susut. Kandidat yang lebih MURAH tidak menang bila
   lapis 1-3 gagal; kandidat mahal yang memenuhi seluruh gate yang menang.
   Ranking lama (`Candidate Score DESC`, lalu SDC ASC) TIDAK diubah — gate
   berjalan sebelum ranking.

Semua tes di sini MURNI: tanpa DB, tanpa HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core import batch_eligibility as be
from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates
from app.core.commodity_policy import policy_for
from app.core.proposal_explain import PRIORITY_LAYERS, explain_hold

SEKARANG = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)

LOG_SAH = [
    {"timestamp": (SEKARANG - timedelta(hours=3)).isoformat(), "temperature_c": 4.0},
    {"timestamp": (SEKARANG - timedelta(hours=1)).isoformat(), "temperature_c": 4.5},
]


def logistik(feasible: bool = True) -> dict:
    return {
        "feasible": feasible,
        "distance_km": 150.0,
        "estimated_time_min": 180,
    }


def batch(
    batch_id: str,
    *,
    lokasi: str,
    komoditas: str = "telur",
    supplier_id: str = "sup-a",
    kg: float = 200.0,
    safety_status: str = "pass",
    temperature_log: list | None = None,
    usable_until: datetime | None | str = "default",
    quarantine_status: str = "none",
) -> dict:
    """Satu batch dengan keadaan yang ditentukan pemanggil."""
    if usable_until == "default":
        usable_until = SEKARANG + timedelta(days=4)
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "location": lokasi,
        "commodity": komoditas,
        "quantity_kg": Decimal(str(kg)),
        "freshness_score": Decimal("0.95"),
        "freshness_status": "pass",
        "safety_status": safety_status,
        "quarantine_status": quarantine_status,
        "usable_until": usable_until,
        "temperature_log": LOG_SAH if temperature_log is None else temperature_log,
        "temperature_observation": "observed",
        "evidence_state": "sufficient",
    }


def _peta_harga(*pasangan: tuple[str, str, str, str]) -> dict:
    """{(source, dest, komoditas): PriceInfo(reference_price=...)}."""
    return {
        (src, dst, kom): PriceInfo(reference_price=Decimal(harga))
        for src, dst, kom, harga in pasangan
    }


# ---------------------------------------------------------------------------
# Butir 1 — bukti yang gagal berarti on_hold + alasan
# ---------------------------------------------------------------------------


def test_log_suhu_kosong_menghasilkan_on_hold_dengan_alasan() -> None:
    """Batch rantai dingin tanpa satu pun sampel TIDAK boleh jadi kandidat aman."""
    held: list = []
    kandidat = generate_candidates(
        source_records={
            ("Bandung", "telur"): Decimal("500"),
            ("Jakarta", "telur"): Decimal("0"),
        },
        destination_records={
            ("Jakarta", "telur"): Decimal("300"),
            ("Bandung", "telur"): Decimal("0"),
        },
        batches=[
            batch("b-kosong", lokasi="Bandung", temperature_log=[]),
        ],
        logistics_by_pair={("Bandung", "Jakarta"): logistik()},
        prices=_peta_harga(("Bandung", "Jakarta", "telur", "30000")),
        policies={"telur": policy_for("telur")},
        evaluation_time=SEKARANG,
        held=held,
    )

    assert kandidat == [], "batch tanpa bukti suhu tidak boleh menghasilkan kandidat"
    assert len(held) == 1
    tahan = held[0]
    assert tahan.status == be.ON_HOLD
    assert be.TEMPERATURE_INCOMPLETE in tahan.blocking_reasons
    assert tahan.layer == 1, "bukti suhu milik lapis 1 (keselamatan/bukti)"
    assert tahan.next_step, "on_hold wajib menyebut langkah verifikasi berikutnya"


def test_safety_pending_ditahan_bukan_direkomendasikan() -> None:
    held: list = []
    kandidat = generate_candidates(
        source_records={
            ("Bandung", "telur"): Decimal("500"),
            ("Jakarta", "telur"): Decimal("0"),
        },
        destination_records={
            ("Jakarta", "telur"): Decimal("300"),
            ("Bandung", "telur"): Decimal("0"),
        },
        batches=[batch("b-pending", lokasi="Bandung", safety_status="pending")],
        logistics_by_pair={("Bandung", "Jakarta"): logistik()},
        prices=_peta_harga(("Bandung", "Jakarta", "telur", "30000")),
        policies={"telur": policy_for("telur")},
        evaluation_time=SEKARANG,
        held=held,
    )

    assert kandidat == []
    assert held[0].status == be.ON_HOLD
    assert be.SAFETY_PENDING in held[0].blocking_reasons
    assert "uji keamanan" in (held[0].next_step or "")


def test_batch_tanpa_masa_layak_ditolak_bukan_ditahan() -> None:
    """`usable_until` NULL = tidak terbukti layak → ditolak, bukan on_hold."""
    held: list = []
    kandidat = generate_candidates(
        source_records={
            ("Bandung", "telur"): Decimal("500"),
            ("Jakarta", "telur"): Decimal("0"),
        },
        destination_records={
            ("Jakarta", "telur"): Decimal("300"),
            ("Bandung", "telur"): Decimal("0"),
        },
        batches=[batch("b-tanpa-uu", lokasi="Bandung", usable_until=None)],
        logistics_by_pair={("Bandung", "Jakarta"): logistik()},
        prices=_peta_harga(("Bandung", "Jakarta", "telur", "30000")),
        policies={"telur": policy_for("telur")},
        evaluation_time=SEKARANG,
        held=held,
    )

    assert kandidat == []
    assert held[0].status == be.REJECTED
    assert be.EXPIRY_UNKNOWN in held[0].blocking_reasons


def test_fuse_evidence_memisahkan_usable_dari_ditahan() -> None:
    """Satu grup dengan dua batch: yang berbukti dipakai, yang tidak ditahan."""
    fusion = be.fuse_evidence(
        [
            batch("b-baik", lokasi="Bandung", supplier_id="sup-a"),
            batch("b-kosong", lokasi="Bandung", supplier_id="sup-a", temperature_log=[]),
        ],
        policy=policy_for("telur"),
        evaluation_time=SEKARANG,
    )

    assert fusion.status == be.USABLE, "satu batch berbukti cukup untuk grup ini"
    assert [e.batch_id for e in fusion.usable] == ["b-baik"]
    assert [e.batch_id for e in fusion.held] == ["b-kosong"]
    assert be.TEMPERATURE_INCOMPLETE in fusion.blocking_reasons


# ---------------------------------------------------------------------------
# Butir 2 — hierarki: mahal-tapi-memenuhi menang atas murah-tapi-gagal
# ---------------------------------------------------------------------------


def _dua_sumber(murah_gagal: dict) -> tuple[list, list]:
    hel: list = []
    kasus = generate_candidates(
        source_records={
            ("Bandung", "telur"): Decimal("500"),
            ("Surabaya", "telur"): Decimal("500"),
            ("Jakarta", "telur"): Decimal("0"),
        },
        destination_records={
            ("Jakarta", "telur"): Decimal("300"),
            ("Bandung", "telur"): Decimal("0"),
            ("Surabaya", "telur"): Decimal("0"),
        },
        batches=[
            murah_gagal,
            batch("b-mahal", lokasi="Surabaya", supplier_id="sup-mahal"),
        ],
        logistics_by_pair={
            ("Bandung", "Jakarta"): logistik(),
            ("Surabaya", "Jakarta"): logistik(),
        },
        prices=_peta_harga(
            ("Bandung", "Jakarta", "telur", "20000"),
            ("Surabaya", "Jakarta", "telur", "32000"),
        ),
        policies={"telur": policy_for("telur")},
        evaluation_time=SEKARANG,
        held=hel,
    )
    return kasus, hel


def test_kandidat_murah_tanpa_bukti_tidak_menang_atas_kandidat_mahal_yang_layak() -> None:
    kandidat, held = _dua_sumber(
        batch("b-murah", lokasi="Bandung", temperature_log=[], supplier_id="sup-murah")
    )

    assert [k.source_location for k in kandidat] == ["Surabaya"]
    assert held[0].source_location == "Bandung"
    assert held[0].status == be.ON_HOLD


def test_kandidat_murah_dengan_pengiriman_tidak_layak_tidak_mendapat_po() -> None:
    """Lapis 2: waktu tiba tidak memenuhi jendela → tidak boleh diranking."""
    held: list = []
    kandidat = generate_candidates(
        source_records={
            ("Bandung", "telur"): Decimal("500"),
            ("Surabaya", "telur"): Decimal("500"),
            ("Jakarta", "telur"): Decimal("0"),
        },
        destination_records={
            ("Jakarta", "telur"): Decimal("300"),
            ("Bandung", "telur"): Decimal("0"),
            ("Surabaya", "telur"): Decimal("0"),
        },
        batches=[
            batch("b-bandung", lokasi="Bandung", supplier_id="sup-b"),
            batch("b-surabaya", lokasi="Surabaya", supplier_id="sup-s"),
        ],
        logistics_by_pair={
            ("Bandung", "Jakarta"): logistik(feasible=False),
            ("Surabaya", "Jakarta"): logistik(),
        },
        prices=_peta_harga(
            ("Bandung", "Jakarta", "telur", "20000"),
            ("Surabaya", "Jakarta", "telur", "32000"),
        ),
        policies={"telur": policy_for("telur")},
        evaluation_time=SEKARANG,
        held=held,
    )

    assert [k.source_location for k in kandidat] == ["Surabaya"]
    assert held[0].source_location == "Bandung"
    assert held[0].status == be.REJECTED
    assert be.DELIVERY_WINDOW_EXCEEDED in held[0].blocking_reasons
    assert held[0].layer == 2


def test_hierarki_lima_lapis_tertulis_dan_tidak_ada_lapis_harga_yang_memblokir() -> None:
    assert [lapis.nama for lapis in PRIORITY_LAYERS][:3] == [
        "Keselamatan dan kelengkapan bukti",
        "Kelayakan kebutuhan bahan dan waktu tiba",
        "Kontinuitas pasokan bahan",
    ]
    assert len(PRIORITY_LAYERS) == 5
    # Lapis 4 (invoice/SDC) dan 5 (susut) adalah PEMBANDING, bukan gerbang:
    # tidak ada kode blokir yang boleh memetakan ke sana.
    for kode in (
        be.SAFETY_FAIL,
        be.SAFETY_PENDING,
        be.TEMPERATURE_INCOMPLETE,
        be.DELIVERY_WINDOW_EXCEEDED,
        be.FRESHNESS_FAIL,
    ):
        lapis, _, _ = explain_hold((kode,))
        assert lapis in (1, 2, 3)
