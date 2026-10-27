"""Lapis gizi/menu & kontinuitas benar-benar mengubah kandidat — bukan dokumen.

Dua pembeda yang diuji di sini:
- destinasi yang permintaan historisnya sudah tertutup stok lokal TETAPI menu-nya
  belum (kebutuhan menu > permintaan) harus tetap jadi destinasi kandidat;
- sumber yang stoknya besar tetapi sebagian harus tinggal untuk kontinuitas
  lokasi asal hanya boleh mengekspor sisanya.
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
        "safety_status": "pass",
        "supplier_id": SUPPLIER,
        "batch_id": "b-1",
        "quarantine_status": "none",
    }
    base.update(overrides)
    return base


def _inputs(source=(1400, 300), demand=(500, 1000), batches=None):
    s_loc_supply, d_loc_supply = source
    s_loc_demand, d_loc_demand = demand
    source_records = {
        ("Cianjur", "telur"): Decimal(str(s_loc_supply)),
        ("Jakarta", "telur"): Decimal(str(d_loc_supply)),
    }
    dest_records = {
        ("Cianjur", "telur"): Decimal(str(s_loc_demand)),
        ("Jakarta", "telur"): Decimal(str(d_loc_demand)),
    }
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
    return source_records, dest_records, batches or [_batch()], logistics, prices


def test_tanpa_peta_menu_perilaku_lama_berlaku():
    """Kontrol: permintaan 300 sudah tertutup stok 400 → tidak ada kandidat."""
    s, d, b, lg, p = _inputs(source=(1400, 400), demand=(500, 300))
    assert generate_candidates(s, d, b, lg, prices=p, commodity="telur") == []


def test_kebutuhan_menu_membuat_destinasi_tetap_dilayani():
    """Menu butuh 90 kg tetapi stok lokal 400 → tetap tanpa kandidat.

    Supaya lantai menu terlihat bekerja, menu harus melebihi stok lokal:
    porsi 8.000 × 60 g = 480 kg > stok 400 kg → kekurangan 80 kg.
    """
    s, d, b, lg, p = _inputs(source=(1400, 400), demand=(500, 300))
    out = generate_candidates(
        s,
        d,
        b,
        lg,
        prices=p,
        commodity="telur",
        menu_requirements={("Jakarta", "telur"): Decimal("480")},
    )
    assert len(out) == 1
    assert out[0].destination_location == "Jakarta"
    assert out[0].quantity_kg == Decimal("80")


def test_kebutuhan_menu_tidak_menurunkan_kekurangan_permintaan():
    s, d, b, lg, p = _inputs(source=(1400, 300), demand=(500, 1000))
    tanpa_menu = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    dengan_menu = generate_candidates(
        s,
        d,
        b,
        lg,
        prices=p,
        commodity="telur",
        menu_requirements={("Jakarta", "telur"): Decimal("60")},
    )
    assert len(tanpa_menu) == 1 and len(dengan_menu) == 1
    # Kekurangan 700 kg (1000 demand - 300 stok) tetap 700; menu 60 tidak memotong.
    assert dengan_menu[0].quantity_kg == tanpa_menu[0].quantity_kg == Decimal("600")


def test_cadangan_kontinuitas_membatasi_ekspor_sumber():
    """Stok 1400 kg, cadangan kontinuitas 1300 kg → ekspor maksimum 100 kg."""
    s, d, b, lg, p = _inputs(source=(1400, 300), demand=(500, 1000))
    out = generate_candidates(
        s,
        d,
        b,
        lg,
        prices=p,
        commodity="telur",
        continuity_reserve={("Cianjur", "telur"): Decimal("1300")},
    )
    assert len(out) == 1
    assert out[0].quantity_kg == Decimal("100")


def test_cadangan_melebihi_stok_menghapus_kandidat():
    s, d, b, lg, p = _inputs(source=(1400, 300), demand=(500, 1000))
    out = generate_candidates(
        s,
        d,
        b,
        lg,
        prices=p,
        commodity="telur",
        continuity_reserve={("Cianjur", "telur"): Decimal("1500")},
    )
    assert out == []


def test_cadangan_kontinuitas_destinasi_tidak_dihitung_dua_kali():
    """Cadangan milik destinasi tidak boleh memotong pasokan yang ia terima."""
    s, d, b, lg, p = _inputs(source=(1400, 300), demand=(500, 1000))
    out = generate_candidates(
        s,
        d,
        b,
        lg,
        prices=p,
        commodity="telur",
        continuity_reserve={("Jakarta", "telur"): Decimal("999")},
    )
    assert len(out) == 1
    assert out[0].quantity_kg == Decimal("600")
