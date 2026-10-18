"""Beras harus jadi komoditas PENUH, bukan chip kosong di layar.

Latar (permintaan pemilik, 17 Okt 2026: "tolong buat data beras"): UI menampilkan
chip komoditas "beras" (`frontend/app/page.tsx` COMMODITIES, `OpsConsole`), tetapi
seed hanya memuat telur/ayam/wortel. Akibatnya memilih beras memberi peta kosong,
tanpa kiriman, tanpa harga, tanpa pemasok — fitur yang terlihat tetapi tidak
berfungsi. Tes ini mengunci kelengkapan di lapisan seed (murni, tanpa DB) supaya
menambah komoditas tidak bisa lagi berhenti di daftar chip.

Yang dikunci:
1. beras ada di daftar komoditas dengan masa layak 180 hari (beras kering);
2. pasokan & permintaan tersebar, bukan satu baris;
3. ada KIRIMAN beras dari pemasok yang fokusnya beras (pemasok diturunkan dari
   batch, jadi tanpa batch beras daftar pemasok beras tetap kosong);
4. harga beras mengikuti aturan sumber yang sama: `supplier_quote` WAJIB punya
   `supplier`, `pihps_reference` TIDAK boleh punya;
5. jangkar telur tidak bergeser (Cianjur 1.400 kg, Jakarta 300 kg).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.seed.seed_data import build_seed_rows

REF = datetime(2026, 10, 17, 5, 0, tzinfo=UTC)
SEED_JSON = Path("/data/seed/sprint1_seed.json")
PEMASOK_BERAS = {"Beras Pandan Wangi Cianjur", "Beras Sari Bogor", "Beras Makmur Jakarta"}


def _rows() -> dict:
    return build_seed_rows(REF)


def _seed_json() -> dict:
    return json.loads(SEED_JSON.read_text(encoding="utf-8"))


def test_komoditas_beras_ada_dengan_masa_layak_beras() -> None:
    nama = {c["name"] for c in _rows()["commodities"]}
    assert "beras" in nama, "chip beras ada di UI, jadi komoditasnya wajib ada"

    json_seed = {c["name"]: c["shelf_life_days"] for c in _seed_json()["commodities"]}
    assert float(json_seed["beras"]) == 180.0, "beras kering: 180 hari, bukan 28"


def test_beras_punya_pasokan_tersebar() -> None:
    pasokan = [r for r in _rows()["supply"] if r["commodity"] == "beras"]
    assert len(pasokan) >= 6, pasokan
    assert len({r["location"] for r in pasokan}) >= 6
    assert all(float(r["quantity_kg"]) > 0 for r in pasokan)


def test_beras_punya_permintaan_di_lokasi_sppg() -> None:
    permintaan = [r for r in _rows()["demand"] if r["commodity"] == "beras"]
    assert len({r["location"] for r in permintaan}) >= 5, permintaan
    assert all(float(r["quantity_kg"]) > 0 for r in permintaan)

    # Riwayat 7 observasi hidup di JSON (baris DB menyimpan nilai terakhir saja).
    json_demand = [
        d for d in _seed_json()["demand"] if d["commodity"] == "beras"
    ]
    assert len(json_demand) >= 5
    assert all(len(d["observations_kg"]) == 7 for d in json_demand)


def test_beras_punya_kiriman_dari_pemasok_beras() -> None:
    batches = [b for b in _rows()["batches"] if b["commodity"] == "beras"]
    assert len(batches) >= 3, batches
    assert {b["supplier"] for b in batches} <= PEMASOK_BERAS
    assert all(float(b["quantity_kg"]) > 0 for b in batches)


def test_harga_beras_mengikuti_aturan_sumber() -> None:
    harga = [p for p in _rows()["price_signals"] if p["commodity"] == "beras"]
    assert len(harga) >= 6, harga
    for baris in harga:
        if baris["source"] == "supplier_quote":
            assert baris.get("supplier"), baris
        else:
            assert baris["source"] == "pihps_reference", baris
            assert not baris.get("supplier"), baris


def test_muatan_sap_beras_ada() -> None:
    stok = _rows()["material_stock"]
    beras = [m for m in stok if m["material_number"] == "1003"]
    assert beras, "material stock beras (1003) wajib ada agar mode SAP mock konsisten"
    assert all(float(m["quantity"]) > 0 for m in beras)


def test_jangkar_telur_tidak_bergeser() -> None:
    supply = _rows()["supply"]
    cianjur = [r for r in supply if r["location"] == "Cianjur" and r["commodity"] == "telur"]
    jakarta = [r for r in supply if r["location"] == "Jakarta" and r["commodity"] == "telur"]
    assert float(cianjur[0]["quantity_kg"]) == 1400.0
    assert float(jakarta[0]["quantity_kg"]) == 300.0
