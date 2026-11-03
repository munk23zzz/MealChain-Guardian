"""Jawaban tool supervisor harus MENJUMLAH ke total (audit 29 Okt 2026).

Keluhan nyata: panel "Tanya supervisor" menjawab "Keputusan per status: approved
1, executed 6, pending_approval 27, rejected 9." — 43, padahal total 49. Tiga
status lain (proposed, review_only, verifier_flagged) tidak pernah disebut,
sehingga pembaca yang menjumlahkan angkanya menemukan selisih dan menyimpulkan
sistemnya salah hitung.
"""

from app.services.supervisor_answers import ringkas_keputusan_per_status


def test_semua_status_disebut_dan_menjumlah():
    hitung = {
        "pending_approval": 27,
        "approved": 1,
        "executed": 6,
        "rejected": 9,
        "proposed": 1,
        "review_only": 1,
        "verifier_flagged": 4,
    }
    hasil = ringkas_keputusan_per_status(hitung)
    for kunci in hitung:
        assert kunci in hasil["answer"], kunci
    assert "49" in hasil["answer"]
    assert hasil["data"]["total"] == 49


def test_kosong_ditulis_apa_adanya():
    hasil = ringkas_keputusan_per_status({})
    assert hasil["answer"] == "Belum ada keputusan tercatat."
    assert hasil["data"] == {"total": 0, "per_status": {}}


def test_status_tak_dikenal_tetap_dihitung():
    hasil = ringkas_keputusan_per_status({"pending_approval": 2, "arsip_lama": 3})
    assert "arsip_lama 3" in hasil["answer"]
    assert hasil["data"]["total"] == 5
