"""Tes aturan keras data pemasok (lintas berkas).

Membuktikan dua hal:
1. Data seed yang dikirim lolos SEMUA aturan (nol pelanggaran).
2. Validator benar-benar menangkap pelanggaran (bukan selalu kosong) — tiap
   aturan diuji dengan data rusak buatan di salinan, berkas asli tidak disentuh.
"""

from __future__ import annotations

import copy

from app.seed.validate_supplier_data import (
    DEFAULT_DEMO,
    DEFAULT_SEED,
    load_json,
    validate,
)


def _real() -> tuple[dict, dict]:
    return load_json(DEFAULT_SEED), load_json(DEFAULT_DEMO)


def test_real_seed_files_have_zero_violations() -> None:
    seed, demo = _real()
    assert validate(seed, demo) == []


def test_detects_name_set_mismatch() -> None:
    seed, demo = _real()
    demo = copy.deepcopy(demo)
    demo["suppliers"].pop()
    errors = validate(seed, demo)
    assert any(error.startswith("S1:") for error in errors), errors


def test_detects_supplier_far_from_its_hub() -> None:
    seed, demo = _real()
    demo = copy.deepcopy(demo)
    row = next(r for r in demo["suppliers"] if r["location"] == "Medan")
    row["latitude"], row["longitude"] = -6.2088, 106.8456  # Jakarta
    errors = validate(seed, demo)
    assert any(
        error.startswith("R1:") and row["name"] in error for error in errors
    ), errors


def test_detects_batch_commodity_mismatch_with_supplier_focus() -> None:
    seed, demo = _real()
    seed = copy.deepcopy(seed)
    batch = next(b for b in seed["batches"] if b["commodity"] == "beras")
    batch["commodity"] = "telur"
    errors = validate(seed, demo)
    assert any(error.startswith("B2:") for error in errors), errors


def test_detects_price_supplier_in_wrong_city() -> None:
    seed, demo = _real()
    seed = copy.deepcopy(seed)
    price = next(p for p in seed["prices"] if p.get("supplier"))
    other = next(
        loc["name"] for loc in seed["locations"] if loc["name"] != price["location"]
    )
    price["location"] = other
    errors = validate(seed, demo)
    assert any(error.startswith("P1:") for error in errors), errors


def test_detects_non_sppg_location_role() -> None:
    seed, demo = _real()
    seed = copy.deepcopy(seed)
    seed["locations"][0]["role_hint"] = "supplier"
    errors = validate(seed, demo)
    assert any(error.startswith("L1:") for error in errors), errors


def test_detects_batch_to_non_sppg_location() -> None:
    seed, demo = _real()
    seed = copy.deepcopy(seed)
    # Jadikan salah satu lokasi tujuan "supplier" — batch ke sana harus ditolak.
    dest = seed["batches"][0]["location"]
    for loc in seed["locations"]:
        if loc["name"] == dest:
            loc["role_hint"] = "supplier"
    errors = validate(seed, demo)
    assert any(error.startswith("B1:") for error in errors), errors


def test_detects_half_coordinates() -> None:
    seed, demo = _real()
    demo = copy.deepcopy(demo)
    demo["suppliers"][0]["longitude"] = None
    errors = validate(seed, demo)
    assert any(error.startswith("S2:") for error in errors), errors
