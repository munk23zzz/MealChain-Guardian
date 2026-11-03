"""Perbaikan data jejak agent (audit 29 Okt 2026) — logika murni.

Yang dijaga:
- langkah yang mendahului keputusan digeser ke SESUDAH keputusan dibuat,
- urutan langkah tidak berubah,
- idempoten: dijalankan dua kali, putaran kedua tidak mengubah apa pun,
- data yang sudah benar tidak disentuh.
"""

from datetime import datetime, timedelta, timezone

from app.seed.rapikan_jejak import jadwal_ulang_jejak, langkah_pelengkap

LAHIR = datetime(2026, 10, 29, 2, 42, tzinfo=timezone.utc)


def test_keputusan_tanpa_detect_dilengkapi_detect():
    """Tanpa DETECT, Decision Time kehilangan titik kiri dan panel jejak
    menulis \"tidak ada langkah awal\" padahal keputusannya jelas ada."""
    assert langkah_pelengkap("pending_approval", ["DECIDE"]) == ["DETECT"]
    assert langkah_pelengkap("rejected", []) == ["DETECT"]


def test_keputusan_executed_wajib_punya_act():
    """Status `executed` berarti eksekusi SUDAH terjadi — jejaknya harus
    mencatat ACT, bukan hanya mengandalkan kolom status."""
    assert langkah_pelengkap("executed", ["DETECT", "DECIDE"]) == ["ACT"]
    assert langkah_pelengkap("executed", ["DECIDE"]) == ["DETECT", "ACT"]


def test_tidak_menambah_apa_pun_bila_sudah_lengkap():
    assert langkah_pelengkap("executed", ["DETECT", "DECIDE", "ACT"]) == []
    assert langkah_pelengkap("pending_approval", ["DETECT", "VERIFY"]) == []


def test_act_tidak_diminta_untuk_status_selain_executed():
    """Keputusan yang belum dieksekusi tidak boleh diberi ACT: itu mengarang
    eksekusi yang belum terjadi."""
    for status in ("pending_approval", "proposed", "approved", "rejected", "verifier_flagged"):
        assert "ACT" not in langkah_pelengkap(status, ["DETECT"])


def test_seluruh_langkah_sebelum_keputusan_digeser_ke_sesudahnya():
    langkah = [
        ("a", LAHIR - timedelta(days=1, hours=1)),
        ("b", LAHIR - timedelta(days=1, hours=1) + timedelta(minutes=2)),
    ]
    baru = jadwal_ulang_jejak(langkah, LAHIR)
    assert baru is not None
    assert set(baru) == {"a", "b"}
    waktunya = [baru["a"], baru["b"]]
    assert all(w >= LAHIR for w in waktunya)
    assert waktunya == sorted(waktunya)
    assert baru["a"] > LAHIR


def test_urutan_dipertahankan_walau_jarak_aslinya_hilang():
    langkah = [
        ("z", LAHIR - timedelta(hours=30)),
        ("y", LAHIR - timedelta(hours=1)),
    ]
    baru = jadwal_ulang_jejak(langkah, LAHIR)
    assert list(baru) == ["z", "y"]
    assert baru["y"] - baru["z"] == timedelta(seconds=120)


def test_idempoten():
    langkah = [("a", LAHIR - timedelta(days=2))]
    sekali = jadwal_ulang_jejak(langkah, LAHIR)
    assert sekali is not None
    lagi = jadwal_ulang_jejak([("a", sekali["a"])], LAHIR)
    assert lagi is None


def test_data_sehat_tidak_disentuh():
    langkah = [("a", LAHIR + timedelta(minutes=5))]
    assert jadwal_ulang_jejak(langkah, LAHIR) is None


def test_daftar_kosong():
    assert jadwal_ulang_jejak([], LAHIR) is None
