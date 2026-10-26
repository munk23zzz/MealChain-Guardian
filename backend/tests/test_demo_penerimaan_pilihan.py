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
