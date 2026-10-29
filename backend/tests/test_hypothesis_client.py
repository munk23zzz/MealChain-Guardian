"""Test `hypothesis_client`: langkah ANALYZE yang memakai LLM tanpa memindahkan angka.

Kontrak yang dikunci:

1. Fakta masuk apa adanya; prompt melarang menghitung angka baru.
2. Output JSON tiga kunci (`penyebab`, `rekomendasi`, `keyakinan`) diurai.
3. Angka yang tidak ada di fakta → status `ungrounded` + daftar angkanya, teks tetap
   disimpan (pembaca bisa menilai), TIDAK dibuang diam-diam.
4. Chain kosong / semua provider gagal → `unavailable`; output tak terbaca → `error`.
   Keduanya tidak boleh mengarang hipotesis.
5. Label provider jujur slot:kind, termasuk saat pemenangnya slot fallback.
"""

from __future__ import annotations

import json

import pytest

from app.services import hypothesis_client
from app.services.hypothesis_client import build_prompt, run_hypothesis

FAKTA = {
    "commodity": "beras",
    "target_location": "Jakarta",
    "supply_kg": 900.0,
    "demand_kg": 3010.0,
    "gap_kg": 2110.0,
    "chosen": {"supplier": "CV Padi Jaya", "available_kg": 1500.0, "leg_km": 4.923},
    "forecast": {"forecast_qty_kg": 20056.3, "method": "sap_rpt_1_6"},
}


def _chain(*jawaban: str | Exception):
    """Chain palsu: tiap entri satu slot, label & kind lengkap."""
    slots = []
    for index, item in enumerate(jawaban):
        nama = "primary" if index == 0 else f"fallback_{index}"

        def fn(prompt: str, _item=item) -> str:
            if isinstance(_item, Exception):
                raise _item
            return _item

        slots.append((f"{nama}:uji", fn, "uji"))
    return slots


JAWABAN_BAGUS = json.dumps(
    {
        "penyebab": "Stok beras 900 kg tidak menutup kebutuhan 3010 kg, selisih 2110 kg.",
        "rekomendasi": "Tambahkan pasokan dari CV Padi Jaya yang punya 1500 kg di jarak 4,923 km.",
        "keyakinan": "sedang",
    },
    ensure_ascii=False,
)


def test_prompt_memuat_fakta_dan_melarang_menghitung_angka_baru():
    prompt = build_prompt(FAKTA)
    data = json.loads(prompt)

    assert data["facts"]["gap_kg"] == 2110.0
    assert data["facts"]["chosen"]["supplier"] == "CV Padi Jaya"
    assert "JANGAN menghitung" in data["task"]
    # Tidak ada kredensial/URL provider di prompt.
    assert "token" not in prompt.lower()


def test_output_json_diurai_menjadi_hipotesis_dan_rekomendasi():
    hasil = run_hypothesis(FAKTA, chain=_chain(JAWABAN_BAGUS))

    assert hasil.status == "analyzed"
    assert hasil.hypothesis and hasil.hypothesis.startswith("Stok beras 900 kg")
    assert hasil.recommendation and "CV Padi Jaya" in hasil.recommendation
    assert hasil.confidence == "sedang"
    assert hasil.ungrounded_numbers == []
    assert hasil.provider == "primary:uji"


def test_angka_yang_tidak_ada_di_fakta_ditandai_bukan_diterima():
    jawaban = json.dumps(
        {
            "penyebab": "Deviasi harga mencapai -3,7% dibanding acuan.",
            "rekomendasi": "Naikkan pasokan 42 kg.",
            "keyakinan": "tinggi",
        },
        ensure_ascii=False,
    )
    hasil = run_hypothesis(FAKTA, chain=_chain(jawaban))

    assert hasil.status == "ungrounded"
    assert set(hasil.ungrounded_numbers) == {"-3.7", "42"}
    # Teks tetap disimpan supaya manusia bisa membaca; statusnya yang memberi tahu.
    assert "Deviasi harga" in (hasil.hypothesis or "")


def test_angka_dari_fakta_tidak_dianggap_liar():
    jawaban = json.dumps(
        {
            "penyebab": "Kekurangan 2110 kg karena stok hanya 900 kg.",
            "rekomendasi": "Ambil 1500 kg dari CV Padi Jaya (4,923 km).",
            "keyakinan": "sedang",
        },
        ensure_ascii=False,
    )
    hasil = run_hypothesis(FAKTA, chain=_chain(jawaban))

    assert hasil.status == "analyzed"
    assert hasil.ungrounded_numbers == []


def test_chain_kosong_menghasilkan_unavailable_tanpa_mengarang():
    hasil = run_hypothesis(FAKTA, chain=[])

    assert hasil.status == "unavailable"
    assert hasil.hypothesis is None
    assert hasil.recommendation is None


def test_semua_provider_gagal_menghasilkan_unavailable():
    hasil = run_hypothesis(FAKTA, chain=_chain(RuntimeError("mati"), RuntimeError("mati juga")))

    assert hasil.status == "unavailable"
    assert hasil.hypothesis is None
    assert hasil.attempts  # jejak percobaan tetap dicatat


def test_output_tak_terbaca_menghasilkan_error_bukan_teks_karangan():
    hasil = run_hypothesis(FAKTA, chain=_chain("maaf, saya tidak bisa"))

    assert hasil.status == "error"
    assert hasil.hypothesis is None


def test_json_tanpa_dua_kunci_utama_dianggap_error():
    hasil = run_hypothesis(FAKTA, chain=_chain(json.dumps({"keyakinan": "tinggi"})))

    assert hasil.status == "error"


def test_label_provider_jujur_saat_pemenang_slot_fallback():
    hasil = run_hypothesis(
        FAKTA,
        chain=_chain(RuntimeError("primary mati"), JAWABAN_BAGUS, JAWABAN_BAGUS),
    )

    assert hasil.status == "analyzed"
    assert hasil.provider == "fallback_1:uji"
    assert hasil.fallback_used is True


def test_status_yang_dihasilkan_selalu_dikenal():
    for jawaban in (JAWABAN_BAGUS, "bukan json"):
        hasil = run_hypothesis(FAKTA, chain=_chain(jawaban))
        assert hasil.status in hypothesis_client.VALID_STATUSES


@pytest.mark.parametrize("status", hypothesis_client.VALID_STATUSES)
def test_daftar_status_stabil(status: str):
    # Kunci kecil: UI dan trace memetakan status ini; menambah/menghapus harus sadar.
    assert status in ("analyzed", "ungrounded", "unavailable", "error")


# --- format angka Indonesia & ID karangan (29 Okt 2026) -----------------------------------
#
# Kejadian nyata: model menulis "kekurangan 2.110 kg" sementara fakta menyimpan 2110.0.
# Tanpa normalisasi pemisah ribuan, setiap jawaban berformat Indonesia ditandai
# "tidak berdasar" — peringatan palsu yang membuat peringatan yang benar diabaikan.


def test_angka_format_ribuan_indonesia_dianggap_sama():
    jawaban = json.dumps(
        {
            "penyebab": "Kekurangan 2.110 kg dari kebutuhan 3.010 kg.",
            "rekomendasi": "Ambil 1.500 kg dari CV Padi Jaya.",
            "keyakinan": "sedang",
        },
        ensure_ascii=False,
    )
    hasil = run_hypothesis(FAKTA, chain=_chain(jawaban))

    assert hasil.status == "analyzed"
    assert hasil.ungrounded_numbers == []


def test_id_karangan_dibuang_dari_teks_dan_ditandai():
    jawaban = json.dumps(
        {
            "penyebab": "Batch 45268526-1af2-5879-806f-2d62bd77f583 gagal uji keamanan.",
            "rekomendasi": "Isolasi batch tersebut lalu tambah pasokan 2110 kg.",
            "keyakinan": "sedang",
        },
        ensure_ascii=False,
    )
    hasil = run_hypothesis(FAKTA, chain=_chain(jawaban))

    assert "45268526-1af2-5879-806f-2d62bd77f583" not in (hasil.hypothesis or "")
    assert "(id tidak ada di fakta)" in (hasil.hypothesis or "")
    # Angka dari fakta tetap lolos; tidak ada angka liar.
    assert hasil.ungrounded_numbers == []


# ---------------------------------------------------------------------------
# Narasi per tahap (DETECT/VERIFY/TRACE/PREDICT/OPTIMIZE/DECIDE/ACT/LEARN)
# ---------------------------------------------------------------------------


def test_narasi_tahap_memakai_penjaga_yang_sama_dengan_analisis():
    """Semua tahap lewat model, tetapi angka/ID tetap dijaga sama."""
    from app.services.hypothesis_client import build_prompt_tahap, narasi_tahap

    prompt = build_prompt_tahap("OPTIMIZE", FAKTA)
    assert "OPTIMIZE" in prompt
    assert "JANGAN menghitung" in prompt

    jawaban = json.dumps(
        {
            "narasi": "Pemasok terpilih CV Padi Jaya memasok 1500 kg dengan jarak 4.923 km.",
            "keyakinan": "tinggi",
        },
        ensure_ascii=False,
    )
    hasil = narasi_tahap("OPTIMIZE", FAKTA, chain=_chain(jawaban))

    assert hasil.status == "analyzed"
    assert hasil.recommendation is None
    assert "CV Padi Jaya" in (hasil.hypothesis or "")
    assert hasil.ungrounded_numbers == []


def test_narasi_tahap_menandai_angka_karangan_dan_id_palsu():
    from app.services.hypothesis_client import narasi_tahap

    jawaban = json.dumps(
        {
            "narasi": (
                "Batch 45268526-1af2-5879-806f-2d62bd77f583 tinggal 42 kg, "
                "jadi tambah 3000 kg."
            ),
            "keyakinan": "sedang",
        },
        ensure_ascii=False,
    )
    hasil = narasi_tahap("DETECT", FAKTA, chain=_chain(jawaban))

    assert hasil.status == "ungrounded"
    assert set(hasil.ungrounded_numbers) == {"42", "3000"}
    assert "45268526-1af2-5879-806f-2d62bd77f583" not in (hasil.hypothesis or "")


def test_narasi_tahap_tanpa_chain_jujur_unavailable():
    from app.services.hypothesis_client import narasi_tahap

    hasil = narasi_tahap("DECIDE", FAKTA, chain=[])
    assert hasil.status == "unavailable"
    assert hasil.hypothesis is None
