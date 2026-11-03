"""Template demo wajib menyemai DERET waktu, bukan hanya 7 hari fakta.

Temuan 26 Okt 2026: tombol "Siapkan data demo" (`build_into`) hanya memanggil
`load_seed`, yang menulis tujuh hari fakta. Dataset hasilnya jauh lebih miskin
daripada `init-demo`: `supply_records` 40 baris (bukan 5.240), `price_signals`
124 (bukan 6.019), `menu_plans` 70 dan tidak ada rencana untuk hari ini. Di
panggung efeknya: grafik riwayat nyaris kosong.

Berkas ini mengunci dua hal yang bisa diuji tanpa membangun ulang database:

1. `build_into` benar-benar memanggil penyemai deret, dan memanggilnya SESUDAH
   data kanonik ada (jangkar generator) tetapi SEBELUM kasus skrip;
2. kegagalan generator dilaporkan apa adanya (`gagal`) dan tidak menghapus
   laporan langkah lain — status jujur, bukan build yang mengaku sukses.
"""

from __future__ import annotations

import inspect

import pytest

from app.seed import demo_template as tpl
from app.seed import timeseries


def test_build_into_memanggil_penyemai_deret_setelah_kanonik_sebelum_kasus() -> None:
    sumber = inspect.getsource(tpl.build_into)
    assert "_semai_deret" in sumber, "build_into tidak menyemai deret waktu"
    pos_inti = sumber.index('laporan["inti"]')
    pos_deret = sumber.index('laporan["deret"]')
    pos_kasus = sumber.index('laporan["kasus"]')
    assert pos_inti < pos_deret < pos_kasus, (
        "urutan salah: deret harus sesudah data kanonik dan sebelum kasus skrip"
    )


@pytest.mark.asyncio
async def test_generator_gagal_dilaporkan_bukan_ditelan(monkeypatch) -> None:
    async def meledak(*_args, **_kwargs):
        raise RuntimeError("jangkar tidak ditemukan")

    monkeypatch.setattr(timeseries, "generate_timeseries", meledak)
    hasil = await tpl._semai_deret()
    assert "gagal" in hasil
    assert "jangkar tidak ditemukan" in hasil["gagal"]
