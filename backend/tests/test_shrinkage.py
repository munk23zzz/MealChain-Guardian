"""Laju susut per komoditas — penjaga rentang yang ditetapkan pemilik."""

from decimal import Decimal

from app.core.shrinkage import (
    DEFAULT_LAJU,
    LAJU_SUSUT,
    SUMBER_DEFAULT,
    SUMBER_TABEL,
    laju_susut,
)


def test_rentang_pemilik_dihormati():
    """beras < 1% · telur 2–5% · sayur 10–20% (wortel = sayur akar)."""
    assert LAJU_SUSUT["beras"] < Decimal("0.01")
    assert Decimal("0.02") <= LAJU_SUSUT["telur"] <= Decimal("0.05")
    assert Decimal("0.10") <= LAJU_SUSUT["wortel"] <= Decimal("0.20")


def test_empat_komoditas_di_seed_punya_laju_sendiri():
    """Nama harus cocok tabel `commodities`: ayam, beras, telur, wortel."""
    assert set(LAJU_SUSUT) == {"ayam", "beras", "telur", "wortel"}


def test_urutan_kewajaran_beras_paling_ringan():
    """Beras (umur 180 hari, kering) tidak boleh lebih berat dari protein/buah."""
    assert LAJU_SUSUT["beras"] < LAJU_SUSUT["telur"] < LAJU_SUSUT["wortel"]
    assert LAJU_SUSUT["telur"] < LAJU_SUSUT["ayam"] < LAJU_SUSUT["wortel"]


def test_laju_dan_sumber_dikembalikan_untuk_tiap_komoditas():
    for nama, nilai in LAJU_SUSUT.items():
        assert laju_susut(nama) == (nilai, SUMBER_TABEL)


def test_nama_tidak_peka_huruf_dan_spasi():
    assert laju_susut("  TELUR ") == (LAJU_SUSUT["telur"], SUMBER_TABEL)


def test_komoditas_tak_terdaftar_memakai_cadangan_dan_mengatakannya():
    """Bukan meminjam angka komoditas lain, bukan nol, dan sumbernya jujur."""
    assert laju_susut("ubi-jalar") == (DEFAULT_LAJU, SUMBER_DEFAULT)
    assert laju_susut(None) == (DEFAULT_LAJU, SUMBER_DEFAULT)
    assert laju_susut("") == (DEFAULT_LAJU, SUMBER_DEFAULT)


def test_cadangan_sama_dengan_kontrak_lama():
    """20% tetap ada sebagai cadangan — bukan dihapus, hanya bukan default."""
    assert DEFAULT_LAJU == Decimal("0.2")
