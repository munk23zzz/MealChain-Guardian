"""Template demo wajib menyisakan CELAH pasokan untuk kota yang punya akun SPPG.

Temuan 28 Okt 2026: tombol "Jalankan agent" pada Demo Control menjawab 409
"SPPG ini tidak kekurangan komoditas tersebut" untuk **wortel**. Sebabnya bukan
bug tombol: seed kanonik sengaja menyimpan Jakarta/wortel SURPLUS (kontrak
`test_seed_kasus_surplus_jakarta.py`), sedangkan pengadaan hanya bisa membuat
keputusan bila `gap_kg > 0`. Akibatnya juri melihat satu dari empat komoditas
yang tombolnya tidak pernah berhasil.

Berkas ini mengunci perbaikan yang dipilih: template demo menaikkan KEBUTUHAN
(baris `demand_records`, bukan pasokan) sampai ada celah, hanya untuk kota yang
punya akun SPPG, dan hanya bila komoditas itu belum kekurangan.

Yang diuji di sini murni (tanpa DB, tanpa jam) supaya bisa jalan di gate mana pun:
1. rumus kebutuhan menghasilkan celah yang wajar (≥25%, tidak melebihi 1,3×);
2. komoditas yang sudah kekurangan TIDAK diubah;
3. `build_into` memanggil langkah ini SEBELUM stok dibuka, dan langkahnya
   menyaring kota lewat akun SPPG (bukan semua lokasi, supaya kota sumber
   surplus seperti Cianjur/Bogor tetap utuh).
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from app.seed import demo_template as tpl


def test_target_kebutuhan_membuat_celah_wajar() -> None:
    for pasokan in (Decimal("100"), Decimal("360"), Decimal("360.55"), Decimal("3010")):
        target = tpl.target_kebutuhan_demo(pasokan)
        celah = target - pasokan
        assert celah > 0, f"pasokan {pasokan}: tidak ada celah"
        # Celah = 25% pasokan + 40 kg (konstanta untuk lot kecil). Diperiksa
        # sebagai batas bawah dan atas, bukan rasio: pada pasokan kecil
        # konstanta 40 kg memang mendominasi.
        assert celah >= Decimal("0.25") * pasokan, f"pasokan {pasokan}: celah terlalu kecil"
        assert celah <= Decimal("0.25") * pasokan + Decimal("40.01"), (
            f"pasokan {pasokan}: celah melebihi aturan"
        )


def test_target_kebutuhan_jakarta_wortel_konkret() -> None:
    # Angka nyata yang terukur 28 Okt 2026 di stack rehearsi: pasokan 360 kg.
    assert tpl.target_kebutuhan_demo(Decimal("360.00")) == Decimal("490.00")


def test_pasokan_nol_ditolak_bukan_dikarang() -> None:
    with pytest.raises(ValueError):
        tpl.target_kebutuhan_demo(Decimal("0"))
    with pytest.raises(ValueError):
        tpl.target_kebutuhan_demo(Decimal("-5"))


def test_komoditas_yang_sudah_kekurangan_tidak_disentuh() -> None:
    # permintaan > pasokan = sudah kekurangan → jangan diubah.
    assert tpl.butuh_penyesuaian_kebutuhan(Decimal("300"), Decimal("1080")) is False
    # tepat impas = belum ada celah → harus disesuaikan.
    assert tpl.butuh_penyesuaian_kebutuhan(Decimal("360"), Decimal("360")) is True
    # belum ada baris permintaan = tidak ada celah yang bisa dibuktikan.
    assert tpl.butuh_penyesuaian_kebutuhan(Decimal("360"), None) is True


def test_build_into_menyisakan_celah_sebelum_stok_dibuka() -> None:
    sumber = inspect.getsource(tpl.build_into)
    assert "_pastikan_kebutuhan_demo" in sumber, "build_into tidak menyisakan celah"
    pos_celah = sumber.index('laporan["kebutuhan_demo"]')
    pos_stok = sumber.index('laporan["stok_siap_dibeli"]')
    assert pos_celah < pos_stok, "celah harus dibuat sebelum stok dibuka"


def test_langkah_hanya_menyentuh_kota_berakun_sppg() -> None:
    sumber = inspect.getsource(tpl._pastikan_kebutuhan_demo)
    assert "User.location_id" in sumber, (
        "langkah ini harus menyaring lokasi lewat akun SPPG; tanpa itu kota "
        "sumber surplus (Cianjur/Bogor) ikut berubah dan cerita surplus hilang"
    )
    assert "evaluate_suppliers" in sumber or "JAM DINDING" in sumber, (
        "patokan waktu harus dijelaskan: pengadaan menilai pada jam dinding"
    )


def test_replay_tidak_menambah_celah() -> None:
    """Replay = dataset kanonik: surplus Jakarta/wortel harus utuh."""
    assert tpl.boleh_menambah_celah("replay") is False
    assert tpl.boleh_menambah_celah("REPLAY") is False
    assert tpl.boleh_menambah_celah("realtime") is True
    assert tpl.boleh_menambah_celah(None) is True


def test_build_into_meneruskan_mode_ke_langkah_celah() -> None:
    sumber = inspect.getsource(tpl.build_into)
    awal = sumber.index("_pastikan_kebutuhan_demo")
    potongan = sumber[awal : awal + 200]
    assert "mode=mode" in potongan, "mode sesi wajib diteruskan; tanpa itu replay ikut diubah"


def test_panen_dijepit_sebelum_keberangkatan() -> None:
    """CHECK `batches_dispatch_after_harvest` tidak boleh dilanggar build."""
    from datetime import datetime, timedelta, timezone

    berangkat = datetime(2026, 10, 8, 7, 0, tzinfo=timezone.utc)
    panen = datetime(2026, 10, 8, 7, 29, tzinfo=timezone.utc)
    hasil = tpl.panen_aman(panen, berangkat)
    assert hasil < berangkat
    assert berangkat - hasil == timedelta(minutes=5)

    # Batch yang belum berangkat: panen dibiarkan apa adanya.
    assert tpl.panen_aman(panen, None) == panen
    # Panen yang sudah lebih awal dari keberangkatan: tidak diubah.
    awal = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)
    assert tpl.panen_aman(awal, berangkat) == awal
