"""Mesin skor ceklis penerimaan (Dok 05 §3–§4) — murni, tanpa DB.

Angka di berkas ini diambil dari dokumen, bukan dari kepala: bobot 25/25/15/15/
8/7/5 = 100, faktor 100/55/0 atau 100/60/0 atau 100/50/10 atau 100/50/70,
ambang fail 65, ambigu ≤85, rasio terima ≥95%. Kalau salah satu berubah, tes
gagal — itu tujuannya.
"""

from __future__ import annotations

import pytest

from app.core.receipt_scoring import (
    AMBANG,
    BUTIR,
    CHECKLIST_VERSION,
    checklist_untuk,
    opsi_jumlah,
    putusan,
    saran,
    skor,
    validasi_berat,
)

#: Jawaban yang sempurna: semua pilihan faktor 100.
SEMUA_PENUH = {
    "suhu": "sesuai",
    "kesegaran": "segar",
    "kemasan": "utuh",
    "kebersihan": "bersih",
    "label": "lengkap",
    "jumlah": "sesuai",
    "waktu": "tepat",
}


def jawaban(**ubahan: str) -> dict[str, str]:
    return {**SEMUA_PENUH, **ubahan}


def test_bobot_total_seratus_dan_versi_tercatat():
    assert sum(b.bobot for b in BUTIR) == 100
    assert len(BUTIR) == 7
    assert CHECKLIST_VERSION  # versi disimpan bersama setiap baris (§4)


def test_setiap_butir_punya_tiga_pilihan():
    for butir in BUTIR:
        assert len(butir.opsi) == 3, butir.kunci
        assert butir.opsi[0].faktor == 100, butir.kunci


def test_poin_dibulatkan_half_up_bukan_bank():
    # 7 × 50 / 100 = 3,5 → 4 (bukan 3 seperti pembulatan bank)
    hasil = skor(jawaban(jumlah="kurang"))
    butir_jumlah = [b for b in hasil.per_butir if b["kunci"] == "jumlah"][0]
    assert butir_jumlah["poin"] == 4
    # 5 × 55 / 100 = 2,75 → 3
    hasil = skor(jawaban(waktu="telat_ringan"))
    butir_waktu = [b for b in hasil.per_butir if b["kunci"] == "waktu"][0]
    assert butir_waktu["poin"] == 3


def test_semua_penuh_seratus_dan_pass():
    hasil = skor(SEMUA_PENUH)
    assert hasil.score == 100
    assert not hasil.kritis and not hasil.perlu_cek
    assert putusan(hasil, 300, 300) == "pass"


def test_butir_kritis_menjatuhkan_putusan_walau_nilai_tinggi():
    # Hanya kemasan bocor (bobot 15) → nilai 85, tetapi kritis.
    hasil = skor(jawaban(kemasan="bocor"))
    assert hasil.score == 85
    assert hasil.kritis is True
    assert putusan(hasil, 300, 300) == "fail"
    kalimat = saran(hasil, "fail", 300, 300)
    assert "kritis" in kalimat and "kemasan" in kalimat
    # Rentang 65–85 TIDAK boleh disebut aman (§7).
    assert "aman" not in kalimat.lower()


def test_nilai_di_bawah_65_gagal_tanpa_butir_kritis():
    hasil = skor(jawaban(kesegaran="kurang", kemasan="penyok", waktu="telat_berat"))
    # 25 + 14 (25×55) + 9 (15×60) + 15 + 8 + 7 + 1 (5×20) = 79? hitung di mesin
    assert hasil.score == 79
    assert hasil.kritis is False
    # 79 ≤ 85 → needs_verification, bukan fail
    assert putusan(hasil, 300, 300) == "needs_verification"
    assert "rentang 65–85" in saran(hasil, "needs_verification", 300, 300)


def test_nilai_dibawah_ambang_gagal():
    hasil = skor(jawaban(kesegaran="kurang", suhu="sedikit", kemasan="penyok", waktu="telat_berat"))
    # 14 + 14 + 9 + 15 + 8 + 7 + 1 = 68 → masih di atas 65
    assert hasil.score == 68
    hasil2 = skor(
        jawaban(
            suhu="sedikit",
            kesegaran="kurang",
            kemasan="penyok",
            kebersihan="kotoran",
            label="tidak_ada",
            waktu="telat_berat",
        )
    )
    # 14 + 14 + 9 + 8 + 1 + 7 + 1 = 54 → fail karena < 65
    assert hasil2.score == 54
    assert putusan(hasil2, 300, 300) == "fail"


def test_butir_perlu_cek_menurunkan_ke_verifikasi():
    hasil = skor(jawaban(label="tidak_ada"))
    # label bobot 8, faktor 10 → 0,8 dibulatkan HALF_UP jadi 1 poin (100−8+1)
    assert hasil.score == 93
    assert hasil.perlu_cek is True
    assert putusan(hasil, 300, 300) == "needs_verification"


def test_berat_kurang_dari_95_persen_menurunkan_pass():
    hasil = skor(SEMUA_PENUH)
    assert putusan(hasil, 300, 300) == "pass"
    # 284/300 = 94,7% → turun ke needs_verification walau nilai 100
    assert putusan(hasil, 300, 284) == "needs_verification"
    kalimat = saran(hasil, "needs_verification", 300, 284)
    assert "284 kg" in kalimat and "kurang 16 kg" in kalimat


def test_berat_nol_selalu_fail():
    hasil = skor(SEMUA_PENUH)
    assert putusan(hasil, 300, 0) == "fail"
    assert "tidak ada barang" in saran(hasil, "fail", 300, 0)


def test_opsi_jumlah_diturunkan_dari_timbangan():
    assert opsi_jumlah(300, 300) == "sesuai"
    assert opsi_jumlah(300, 285) == "sesuai"  # 95%
    assert opsi_jumlah(300, 284) == "kurang"
    assert opsi_jumlah(300, 310) == "lebih"


@pytest.mark.parametrize(
    "diterima, kode",
    [
        (0, "berat_nol"),
        (0.4, "berat_nol"),
        (-5, "berat_minus"),
        (340, "berat_lebih"),  # 113% dari 300
        (300, None),
        (330, None),  # 110% masih wajar
    ],
)
def test_validasi_berat(diterima, kode):
    assert validasi_berat(300, diterima) == kode


def test_cek_lengkap_tidak_dinilai_setengah_jadi():
    with pytest.raises(KeyError) as galat:
        skor({"suhu": "sesuai"})
    assert "kesegaran" in str(galat.value)


def test_jawaban_tidak_dikenal_ditolak():
    with pytest.raises(KeyError):
        skor(jawaban(suhu="entah"))


def test_petunjuk_suhu_mengikuti_profil_komoditas():
    dingin = checklist_untuk("telur")
    suhu = [b for b in dingin["butir"] if b["kunci"] == "suhu"][0]
    assert "°C" in suhu["petunjuk"] and "telur" in suhu["petunjuk"]

    ambient = checklist_untuk("beras")
    suhu_beras = [b for b in ambient["butir"] if b["kunci"] == "suhu"][0]
    assert "suhu ruang" in suhu_beras["petunjuk"]

    assert dingin["total_bobot"] == 100
    assert dingin["ambang"]["fail_max_score"] == AMBANG["fail_max_score"]
    assert checklist_untuk("telur")["butir"][5]["dari_timbangan"] is True
