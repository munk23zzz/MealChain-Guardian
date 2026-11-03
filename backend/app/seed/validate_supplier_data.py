"""Validasi silang berkas seed pemasok — aturan keras, murni (tanpa DB).

Kenapa modul terpisah: `suppliers_demo.py` memvalidasi SATU berkas saat dimuat,
tetapi integritas LINTAS berkas (nama sama, batch menunjuk pemasok yang ada,
komoditas cocok, harga sekota, jarak ke hub) tidak diperiksa di mana pun.
Modul ini menjadi satu tempat aturan itu; dipakai oleh tes dan bisa dijalankan:

    python -m app.seed.validate_supplier_data

Aturan (semua FATAL):
- L1 setiap lokasi ber-nama unik dan ber-role ``sppg`` (tujuan, bukan hub semu)
- L2 koordinat lokasi di dalam Indonesia
- K1 nama komoditas unik
- S1 nama pemasok unik di KEDUA berkas dan himpunannya identik
- S2 koordinat pemasok ada, berpasangan, di dalam Indonesia
- S3 sertifikasi ∈ {none, hygiene, haccp}; kapasitas > 0; reliabilitas 0..1
- S4 lokasi & komoditas pemasok menunjuk baris yang ADA
- S5 lokasi + skor pemasok di berkas demo == berkas kanonik (tanpa drift)
- R1 jarak pemasok → hub-nya <= ``REACH_KM_MAX`` (haversine)
- B1 batch menunjuk pemasok/komoditas/lokasi yang ADA; lokasi ber-role ``sppg``
- B2 komoditas batch == komoditas fokus pemasok itu (bila pemasok punya fokus)
- B3 berat batch > 0
- P1 harga yang menyebut pemasok: pemasok ADA dan terdaftar di kota yang sama
- M1 ``_meta.provenance`` menyatakan SINTETIS dan ``canonical_overlap`` SAMA

Catatan: pemasok TANPA batch sah (terdaftar tetapi belum mengirim). Yang tidak
boleh adalah batch menunjuk pemasok yang tidak ada, atau komoditas yang berbeda
dari fokus pemasoknya.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from app.core.geo import haversine_km

INDONESIA_LAT = (-11.5, 6.5)
INDONESIA_LON = (94.5, 141.5)
REACH_KM_MAX = 150.0
CERTIFICATIONS = {"none", "hygiene", "haccp"}

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED = REPO_ROOT / "data" / "seed" / "sprint1_seed.json"
DEFAULT_DEMO = REPO_ROOT / "data" / "seed" / "suppliers_demo.json"


def load_json(path: Path | str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _in_indonesia(lat, lon) -> bool:
    return (
        INDONESIA_LAT[0] <= float(lat) <= INDONESIA_LAT[1]
        and INDONESIA_LON[0] <= float(lon) <= INDONESIA_LON[1]
    )


def validate(seed: Mapping[str, Any], demo: Mapping[str, Any]) -> list[str]:
    """Kembalikan daftar pelanggaran (kosong = data sah)."""
    errors: list[str] = []

    # --- lokasi & komoditas -------------------------------------------------
    locations = {loc["name"]: loc for loc in seed.get("locations", [])}
    commodities = {c["name"]: c for c in seed.get("commodities", [])}

    if len(locations) != len(seed.get("locations", [])):
        errors.append("L1: nama lokasi duplikat")
    for name, loc in locations.items():
        if loc.get("role_hint") != "sppg":
            errors.append(
                f"L1: lokasi {name} role_hint={loc.get('role_hint')!r}, wajib 'sppg'"
            )
        try:
            if not _in_indonesia(loc["latitude"], loc["longitude"]):
                errors.append(f"L2: koordinat lokasi {name} di luar Indonesia")
        except (KeyError, TypeError, ValueError):
            errors.append(f"L2: koordinat lokasi {name} tidak valid")

    if len(commodities) != len(seed.get("commodities", [])):
        errors.append("K1: nama komoditas duplikat")

    # --- himpunan nama pemasok ---------------------------------------------
    canonical = seed.get("suppliers", [])
    profiles = demo.get("suppliers", [])
    canonical_names = [s["name"] for s in canonical]
    profile_names = [s["name"] for s in profiles]
    if len(canonical_names) != len(set(canonical_names)):
        errors.append("S1: nama pemasok duplikat di sprint1_seed.json")
    if len(profile_names) != len(set(profile_names)):
        errors.append("S1: nama pemasok duplikat di suppliers_demo.json")
    if set(canonical_names) != set(profile_names):
        errors.append(
            "S1: himpunan nama pemasok beda — hanya kanonik: "
            f"{sorted(set(canonical_names) - set(profile_names))}; hanya profil: "
            f"{sorted(set(profile_names) - set(canonical_names))}"
        )

    canonical_by_name = {s["name"]: s for s in canonical}
    profile_by_name = {s["name"]: s for s in profiles}

    # --- pemasok kanonik (identitas) ---------------------------------------
    for name, row in canonical_by_name.items():
        if row.get("location") not in locations:
            errors.append(
                f"S4: pemasok {name} menunjuk lokasi tak dikenal {row.get('location')!r}"
            )
        try:
            score = float(row["reliability_score"])
            if not 0 <= score <= 1:
                errors.append(f"S3: reliabilitas {name}={score} di luar 0..1")
        except (KeyError, TypeError, ValueError):
            errors.append(f"S3: reliabilitas {name} tidak valid")

    # --- pemasok profil (koordinat/kapasitas/sertifikasi) ------------------
    for name, row in profile_by_name.items():
        loc_name = row.get("location")
        if loc_name not in locations:
            errors.append(
                f"S4: profil {name} menunjuk lokasi tak dikenal {loc_name!r}"
            )
        if row.get("commodity") not in commodities:
            errors.append(
                f"S4: profil {name} menunjuk komoditas tak dikenal {row.get('commodity')!r}"
            )

        lat, lon = row.get("latitude"), row.get("longitude")
        if (lat is None) != (lon is None):
            errors.append(f"S2: profil {name} koordinat separuh")
        elif lat is None:
            errors.append(f"S2: profil {name} tanpa koordinat")
        else:
            try:
                if not _in_indonesia(lat, lon):
                    errors.append(f"S2: koordinat profil {name} di luar Indonesia")
            except (TypeError, ValueError):
                errors.append(f"S2: koordinat profil {name} bukan angka")

        if row.get("certification_status") not in CERTIFICATIONS:
            errors.append(
                f"S3: sertifikasi {name}={row.get('certification_status')!r} "
                f"di luar {sorted(CERTIFICATIONS)}"
            )
        try:
            if float(row.get("capacity_kg_per_week") or 0) <= 0:
                errors.append(f"S3: kapasitas {name} harus > 0")
        except (TypeError, ValueError):
            errors.append(f"S3: kapasitas {name} bukan angka")

        canon = canonical_by_name.get(name)
        if canon is not None:
            if canon.get("location") != loc_name:
                errors.append(
                    f"S5: lokasi {name} beda antar berkas "
                    f"({canon.get('location')!r} vs {loc_name!r})"
                )
            try:
                if float(canon["reliability_score"]) != float(row["reliability_score"]):
                    errors.append(f"S5: skor {name} beda antar berkas")
            except (KeyError, TypeError, ValueError):
                errors.append(f"S5: skor {name} tidak bisa dibandingkan")

        # R1: pemasok harus terjangkau dari hub tempat ia terdaftar.
        hub = locations.get(loc_name)
        if hub is not None and lat is not None and lon is not None:
            try:
                km = haversine_km(
                    float(lat), float(lon),
                    float(hub["latitude"]), float(hub["longitude"]),
                )
                if km > REACH_KM_MAX:
                    errors.append(
                        f"R1: {name} berjarak {km:.1f} km dari hub {loc_name} "
                        f"(> {REACH_KM_MAX:.0f} km)"
                    )
            except (KeyError, TypeError, ValueError):
                pass  # sudah dilaporkan sebagai L2/S2

    # --- batch -------------------------------------------------------------
    for i, b in enumerate(seed.get("batches", []), start=1):
        label = b.get("code") or f"batch#{i}"
        supplier_name = b.get("supplier")
        dest = b.get("location")

        if supplier_name not in profile_by_name:
            errors.append(f"B1: {label} menunjuk pemasok tak dikenal {supplier_name!r}")
        if b.get("commodity") not in commodities:
            errors.append(f"B1: {label} menunjuk komoditas tak dikenal {b.get('commodity')!r}")
        if dest not in locations:
            errors.append(f"B1: {label} menunjuk lokasi tak dikenal {dest!r}")
        elif locations[dest].get("role_hint") != "sppg":
            errors.append(f"B1: {label} menuju lokasi bukan SPPG {dest!r}")

        profile = profile_by_name.get(supplier_name)
        if profile is not None and profile.get("commodity"):
            if profile["commodity"] != b.get("commodity"):
                errors.append(
                    f"B2: {label} komoditas {b.get('commodity')!r} != fokus "
                    f"pemasok {profile['commodity']!r} ({supplier_name})"
                )

        try:
            if float(b.get("quantity_kg") or 0) <= 0:
                errors.append(f"B3: {label} berat harus > 0")
        except (TypeError, ValueError):
            errors.append(f"B3: {label} berat bukan angka")

    # --- harga -------------------------------------------------------------
    for i, p in enumerate(seed.get("prices", []), start=1):
        supplier_name = p.get("supplier")
        if not supplier_name:
            continue
        profile = profile_by_name.get(supplier_name)
        if profile is None:
            errors.append(f"P1: harga#{i} menunjuk pemasok tak dikenal {supplier_name!r}")
            continue
        if profile.get("location") != p.get("location"):
            errors.append(
                f"P1: harga#{i} {supplier_name} terdaftar di "
                f"{profile.get('location')!r}, kutipan di {p.get('location')!r}"
            )

    # --- provenance --------------------------------------------------------
    meta = demo.get("_meta", {})
    if "SINTETIS" not in str(meta.get("provenance", "")):
        errors.append("M1: _meta.provenance tidak menyatakan SINTETIS")
    if "SAMA" not in str(meta.get("canonical_overlap", "")):
        errors.append("M1: _meta.canonical_overlap tidak menyatakan SAMA")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validasi silang seed pemasok")
    parser.add_argument("--seed", default=str(DEFAULT_SEED))
    parser.add_argument("--demo", default=str(DEFAULT_DEMO))
    args = parser.parse_args(argv)

    errors = validate(load_json(args.seed), load_json(args.demo))
    if errors:
        print(f"DITEMUKAN {len(errors)} pelanggaran:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("OK: semua aturan data pemasok lolos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
