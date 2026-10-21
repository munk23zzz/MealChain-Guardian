"""Kasus surplus Jakarta untuk wortel (permintaan pemilik, 20 Okt 2026).

Konteks: pada seed kanonik `data/seed/sprint1_seed.json`, Jakarta **shortage di
keempat komoditas** (telur 0,29×, beras 0,30×, ayam 0,97×, wortel 0,98×) sehingga
tidak ada satu pun kasus surplus di Jakarta; satu-satunya kota surplus adalah
Cianjur (+ Bogor/Bandung untuk telur & beras).

Berkas ini mengunci keputusan itu sebagai kontrak data:

1. Jakarta/wortel WAJIB surplus (pasokan > kebutuhan).
2. Rasionya tetap "masuk akal": di dalam rentang surplus yang sudah ada di
   dataset (1,9×–2,6×). Di luar 1,6×–3,0× dianggap data di luar nalar.
3. Jakarta TETAP shortage untuk telur, ayam, beras — profil kota tetap campuran,
   bukan kota surplus murni (jangan sampai satu perubahan menghapus tiga kasus
   shortage yang dipakai skenario transfer).
4. Cianjur/wortel TETAP surplus (sumber transfer yang sudah ada tidak dicabut).

Tes membaca JSON kanonik, bukan DB, supaya perubahan ini bertahan pada seed
ulang berikutnya.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parents[2] / "data" / "seed" / "sprint1_seed.json"

# Rentang "masuk akal" untuk sebuah kasus surplus di dataset ini.
RASIO_MIN = 1.6
RASIO_MAKS = 3.0

# Biaya penanganan tetap per pengiriman (HANDLING_FLAT,
# app/services/recommendation_service.py:68) dan harga acuan wortel — dipakai
# untuk menguji bahwa lot tidak terlalu kecil untuk layak dikirim.
HANDLING_FLAT = Decimal("150000")
HARGA_WORTEL = Decimal("23500")
BAGIAN_BIAYA_MAKS = Decimal("0.05")  # biaya tetap maksimum 5% nilai barang


@pytest.fixture(scope="module")
def seed() -> dict:
    return json.loads(SEED.read_text(encoding="utf-8"))


def _pasokan(seed: dict) -> dict[tuple[str, str], float]:
    return {
        (x["location"], x["commodity"]): float(x["quantity_kg"]) for x in seed["supply"]
    }


def _batch(seed: dict) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = defaultdict(float)
    for b in seed["batches"]:
        out[(b["location"], b["commodity"])] += float(b["quantity_kg"])
    return dict(out)


def _kebutuhan(seed: dict) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for x in seed["demand"]:
        obs = x.get("observations_kg") or []
        out[(x["location"], x["commodity"])] = sum(obs) / len(obs) if obs else 0.0
    return out


def _rasio(seed: dict, lokasi: str, komoditas: str) -> float:
    supply = _pasokan(seed)[(lokasi, komoditas)]
    demand = _kebutuhan(seed)[(lokasi, komoditas)]
    assert demand > 0, f"{lokasi}/{komoditas} tidak punya permintaan kanonik"
    return supply / demand


def test_pasokan_sama_dengan_jumlah_batch(seed: dict) -> None:
    """Invarian dataset: supply_kg = Σ batch (kalau tidak, transfer pakai batch basi)."""
    pasokan, batch = _pasokan(seed), _batch(seed)
    beda = [
        f"{lok}/{kom}: supply {pasokan[(lok, kom)]} vs batch {batch.get((lok, kom), 0)}"
        for lok, kom in pasokan
        if abs(pasokan[(lok, kom)] - batch.get((lok, kom), 0.0)) > 0.01
    ]
    assert not beda, "pasokan tidak sama dengan jumlah batch: " + "; ".join(beda)


def test_jakarta_wortel_surplus(seed: dict) -> None:
    supply = _pasokan(seed)[("Jakarta", "wortel")]
    demand = _kebutuhan(seed)[("Jakarta", "wortel")]
    assert supply > demand, (
        f"Jakarta/wortel harus surplus, ternyata pasokan {supply} "
        f"<= kebutuhan {demand}"
    )


def test_rasio_surplus_jakarta_wortel_masuk_akal(seed: dict) -> None:
    rasio = _rasio(seed, "Jakarta", "wortel")
    assert RASIO_MIN <= rasio <= RASIO_MAKS, (
        f"rasio Jakarta/wortel {rasio:.2f}× di luar rentang wajar "
        f"{RASIO_MIN}–{RASIO_MAKS}× (data di luar nalar)"
    )


def test_defisit_tujuan_cukup_besar_untuk_satu_pengiriman(seed: dict) -> None:
    """Tujuan transfer harus menerima lot yang layak: biaya tetap ≤ 5% nilai barang."""
    pasokan, kebutuhan = _pasokan(seed), _kebutuhan(seed)
    defisit = kebutuhan[("Bogor", "wortel")] - pasokan[("Bogor", "wortel")]
    surplus = pasokan[("Jakarta", "wortel")] - kebutuhan[("Jakarta", "wortel")]
    assert defisit > 0, "Bogor harus shortage untuk menjadi tujuan transfer"
    assert defisit <= surplus * 1.1, (
        f"defisit Bogor {defisit:.0f} kg melebihi surplus Jakarta {surplus:.0f} kg — "
        "muatan tidak akan tertutup (over-delivery)"
    )
    lot = Decimal(str(min(defisit, surplus)))
    bagian = HANDLING_FLAT / (lot * HARGA_WORTEL)
    assert bagian <= BAGIAN_BIAYA_MAKS, (
        f"lot {lot:.0f} kg: biaya penanganan tetap Rp {HANDLING_FLAT} = "
        f"{bagian:.1%} nilai barang, di atas {BAGIAN_BIAYA_MAKS:.0%} — "
        "pengiriman sekecil itu tidak wajar"
    )


@pytest.mark.parametrize("komoditas", ["telur", "ayam", "beras"])
def test_jakarta_tetap_shortage_komoditas_lain(seed: dict, komoditas: str) -> None:
    supply = _pasokan(seed)[("Jakarta", komoditas)]
    demand = _kebutuhan(seed)[("Jakarta", komoditas)]
    assert supply < demand, (
        f"Jakarta/{komoditas} seharusnya tetap shortage; "
        f"pasokan {supply} vs kebutuhan {demand}"
    )


def test_semua_rasio_di_dataset_masuk_akal(seed: dict) -> None:
    """Tidak ada pasokan yang mustahil: surplus > 4,5× atau shortage < 0,15× ditolak.

    Batas longgar dipakai karena shortage ekstrem memang ada di dataset kanonik
    (Jakarta telur 0,29× justru kasus demo utama), jadi yang dijaga adalah nilai
    yang mustahil secara fisik, bukan yang kebetulan mencolok.
    """
    buruk = []
    for (lokasi, komoditas), supply in _pasokan(seed).items():
        demand = _kebutuhan(seed)[(lokasi, komoditas)]
        if demand <= 0:
            continue
        rasio = supply / demand
        if rasio > RASIO_MAKS * 1.5 or rasio < 0.15:
            buruk.append(f"{lokasi}/{komoditas} = {rasio:.2f}×")
    assert not buruk, "rasio di luar nalar: " + ", ".join(buruk)


def test_cianjur_wortel_tetap_surplus(seed: dict) -> None:
    assert _rasio(seed, "Cianjur", "wortel") > 1.0, (
        "Cianjur/wortel adalah sumber transfer yang sudah ada; "
        "jangan dicabut saat menambah kasus surplus Jakarta"
    )
