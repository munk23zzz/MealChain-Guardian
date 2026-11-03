"""Kontrak pemilihan batch untuk penerimaan demo (tab Keamanan Pangan).

Sejak gate penerimaan diperketat (temuan F-01, 25 Okt 2026), menerima barang
dari batch yang belum `pass` DITOLAK 409. Dulu `_semai_penerimaan` memasang
KEDUA penerimaan "menunggu" pada batch `pending`, sehingga tombol Setujui di
demo selalu gagal.

Kontrak baru: satu penerimaan pada batch `pass` (bisa disetujui → stok
bergerak) dan satu pada batch `pending` (mendemonstrasikan penolakan beserta
alasannya). Helper di bawah murni (tanpa DB) supaya bisa diuji di gate mana pun.
"""

from __future__ import annotations

from app.seed.demo_template import pilih_batch_penerimaan


class _B:
    def __init__(self, nama: str) -> None:
        self.id = nama


def test_ambil_satu_pending_dan_satu_pass():
    pending = [_B("pending-1"), _B("pending-2")]
    lulus = [_B("pass-1"), _B("pass-2")]
    terpilih = pilih_batch_penerimaan(pending, lulus)
    assert [b.id for b in terpilih] == ["pending-1", "pass-1"]


def test_tanpa_batch_pass_tetap_mengambil_dua_pending():
    pending = [_B("pending-1"), _B("pending-2")]
    assert [b.id for b in pilih_batch_penerimaan(pending, [])] == ["pending-1", "pending-2"]


def test_tanpa_batch_pending_memakai_dua_batch_pass():
    lulus = [_B("pass-1"), _B("pass-2")]
    assert [b.id for b in pilih_batch_penerimaan([], lulus)] == ["pass-1", "pass-2"]


def test_tidak_pernah_lebih_dari_dua_dan_tidak_duplikat():
    pending = [_B("pending-1")]
    lulus = [_B("pass-1")]
    terpilih = pilih_batch_penerimaan(pending, lulus)
    assert len(terpilih) == 2
    assert len({b.id for b in terpilih}) == 2


def test_kosong_sama_sekali_tidak_melempar():
    assert pilih_batch_penerimaan([], []) == []


# --------------------------------------------------------------------------
# Demo "kasus pengiriman" (29 Okt 2026): baris penerimaan yang dipakai mendemokan
# persetujuan harus (a) duduk di batch DEMO — supaya sesi demo memiliki barisnya,
# bukan menumpang batch kanonik — dan (b) membawa BERAT TIMBANGAN, supaya
# "diterima 513 dari 540 kg" bisa diperagakan. Dua helper di bawah murni supaya
# kontraknya bisa diuji tanpa DB.
# --------------------------------------------------------------------------


def test_batch_demo_diurutkan_lebih_dulu():
    from app.seed.demo_template import urutkan_demo_dulu

    seed = _B("seed-1")
    seed.origin = "seed"
    demo_a = _B("demo-a")
    demo_a.origin = "demo"
    demo_b = _B("demo-b")
    demo_b.origin = "demo"

    hasil = urutkan_demo_dulu([seed, demo_b, demo_a])
    assert [b.id for b in hasil] == ["demo-a", "demo-b", "seed-1"]


def test_berat_timbangan_selalu_kurang_dari_pesanan():
    from decimal import Decimal

    from app.seed.demo_template import berat_timbangan

    for pesanan in (Decimal("540"), Decimal("120"), Decimal("90.5"), Decimal("1000")):
        terima = berat_timbangan(pesanan)
        assert terima < pesanan, (pesanan, terima)
        # Dua desimal (kolom NUMERIC(10,2)) dan tidak pernah nol/negatif.
        assert -terima.as_tuple().exponent <= 2, terima
        assert terima > 0, terima


def test_berat_timbangan_nol_tidak_dikarang():
    from decimal import Decimal

    from app.seed.demo_template import berat_timbangan

    assert berat_timbangan(Decimal("0")) is None
    assert berat_timbangan(None) is None
