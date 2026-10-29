"""Lapis 5 hierarki keputusan: pengurangan limbah sebagai tie-break ranking.

Kontrak yang diuji (proposal ¶15 — keamanan → gizi/menu → kontinuitas → biaya →
pengurangan limbah):

1. Urutan utama TIDAK berubah: score DESC, lalu Safe Delivered Cost ASC.
   Limbah tidak boleh mengalahkan biaya — kalau boleh, lapis 4 bukan lagi lapis 4.
2. Limbah hanya menengahi saat score DAN SDC seri: expected_loss lebih kecil menang.
3. Expected loss yang tidak diketahui diurutkan SESUDAH yang diketahui
   (tidak tahu bukan berarti nol).
4. Tie-break leksikal lama tetap berlaku bila score, SDC, dan limbah semuanya seri
   → determinisme kontrak Task 7 tidak rusak.
"""

from decimal import Decimal

from app.core.candidate import BalancingCandidate, PriceInfo
from app.core.ranking import ScoredCandidate, rank_candidates

_SUP = "11111111-1111-1111-1111-111111111111"


def _candidate(source="Cianjur", dest="Jakarta", commodity="telur", supplier_id=_SUP,
               cid="c1", quantity=Decimal("500")):
    return BalancingCandidate(
        source_location=source,
        destination_location=dest,
        commodity=commodity,
        quantity_kg=quantity,
        demand_fit=Decimal("1"),
        supply_availability=Decimal("1"),
        freshness_score=Decimal("0.9"),
        freshness_status="pass",
        safety_status="pass",
        supplier_reliability=Decimal("0.8"),
        logistics_feasible=True,
        logistics_distance_km=Decimal("120"),
        logistics_time_min=150,
        price=PriceInfo(
            reference_price=Decimal("26500"),
            supplier_quote=Decimal("26200"),
            supplier_id=supplier_id,
        ),
    )


def _scored(score, sdc, cid, expected_loss=None, **kw):
    return ScoredCandidate(
        candidate=_candidate(cid=cid, **kw),
        candidate_id=cid,
        score=Decimal(str(score)),
        eligible=True,
        review_required=False,
        safe_delivered_cost=Decimal(str(sdc)),
        **({} if expected_loss is None else {"expected_loss": Decimal(str(expected_loss))}),
    )


def test_score_dan_sdc_seri_susut_lebih_kecil_menang():
    """Lapis 5: saat biaya seri, yang membuang lebih sedikit dipilih."""
    kandidat = [
        _scored("0.80", "1000", "mahal_limbah", expected_loss="120", source="Bogor"),
        _scored("0.80", "1000", "hemat_limbah", expected_loss="40", source="Cianjur"),
    ]
    urutan = [c.candidate_id for c in rank_candidates(kandidat)]
    assert urutan == ["hemat_limbah", "mahal_limbah"]
    assert [c.rank for c in rank_candidates(kandidat)] == [1, 2]


def test_sdc_lebih_kecil_tetap_menang_walau_susut_lebih_besar():
    """Lapis 4 tidak boleh dikalahkan lapis 5."""
    kandidat = [
        _scored("0.80", "1000", "murah_limbah_besar", expected_loss="500", source="Bogor"),
        _scored("0.80", "1100", "mahal_limbah_kecil", expected_loss="1", source="Cianjur"),
    ]
    urutan = [c.candidate_id for c in rank_candidates(kandidat)]
    assert urutan == ["murah_limbah_besar", "mahal_limbah_kecil"]


def test_susut_tidak_diketahui_diurutkan_setelah_yang_diketahui():
    kandidat = [
        _scored("0.80", "1000", "tanpa_data", source="Bogor"),
        _scored("0.80", "1000", "ada_data", expected_loss="999", source="Cianjur"),
    ]
    urutan = [c.candidate_id for c in rank_candidates(kandidat)]
    assert urutan == ["ada_data", "tanpa_data"]


def test_semua_seri_tetap_leksikal_deterministik():
    kandidat = [
        _scored("0.80", "1000", "b", expected_loss="10", source="Semarang"),
        _scored("0.80", "1000", "a", expected_loss="10", source="Bandung"),
    ]
    assert [c.candidate.to_dict()["source_location"] for c in rank_candidates(kandidat)] == [
        "Bandung",
        "Semarang",
    ]


def test_kandidat_tidak_eligible_tetap_dikecualikan():
    kandidat = [
        _scored("0.90", "900", "aman", expected_loss="10", source="Cianjur"),
        ScoredCandidate(
            candidate=_candidate(cid="fail", source="Bogor"),
            candidate_id="fail",
            score=Decimal("0.99"),
            eligible=False,
            review_required=False,
            safe_delivered_cost=Decimal("100"),
            expected_loss=Decimal("1"),
        ),
    ]
    urutan = [c.candidate_id for c in rank_candidates(kandidat)]
    assert urutan == ["aman"]
