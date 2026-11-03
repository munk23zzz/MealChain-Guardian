"""Kontrak sidik keputusan (fingerprint approval) — Fase 4 MG butir 4.

Masalah yang dikunci: approval yang sudah tercatat hari ini hanya mengikat
"keputusan ini masih keputusan yang sama" lewat kolom-kolom dasar. Bukti batch
dan pemasok yang MENENTUKAN kelayakan tidak ikut disidik, sehingga bukti bisa
berubah (batch diganti, pemasok lain, policy komoditas naik versi, evaluasi
berubah dari usable menjadi on_hold) sementara approval lama tetap dianggap
sah. Sidik yang sama juga harus berubah bila `policy_version`/hasil evaluasi
berubah, karena approval diberikan atas DASAR itu, bukan atas angka biaya saja.

Kontrak modul ini murni: tanpa DB, tanpa HTTP, tanpa jam dinding.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core import decision_fingerprint as df

DASAR = df.SidikApproval(
    decision_id="11111111-1111-1111-1111-111111111111",
    batch_ids=("b-2", "b-1"),
    supplier_id="22222222-2222-2222-2222-222222222222",
    quantity_kg="600.00",
    cost_idr="16206000.00",
    source_location_id="33333333-3333-3333-3333-333333333333",
    target_location_id="44444444-4444-4444-4444-444444444444",
    commodity_id="55555555-5555-5555-5555-555555555555",
    policy_version="sim-2026-10-27.v1",
    evaluation_status="usable",
    blocking_reasons=(),
)


def test_sidik_deterministik() -> None:
    assert df.hitung_sidik(DASAR) == df.hitung_sidik(DASAR)
    assert df.hitung_sidik(DASAR).startswith("sha256:")


def test_urutan_dan_duplikat_batch_tidak_mengubah_sidik() -> None:
    lain = replace(DASAR, batch_ids=("b-1", "b-2", "b-1"))
    assert df.hitung_sidik(lain) == df.hitung_sidik(DASAR)


def test_huruf_besar_uuid_dinormalkan() -> None:
    lain = replace(DASAR, supplier_id=DASAR.supplier_id.upper())
    assert df.hitung_sidik(lain) == df.hitung_sidik(DASAR)


def test_format_angka_setara_menghasilkan_sidik_sama() -> None:
    """`600` dan `600.00` adalah kuantitas yang sama, bukan bukti berbeda."""
    lain = replace(DASAR, quantity_kg="600", cost_idr="16206000")
    assert df.hitung_sidik(lain) == df.hitung_sidik(DASAR)


@pytest.mark.parametrize(
    "perubahan",
    [
        {"batch_ids": ("b-1",)},
        {"batch_ids": ("b-1", "b-2", "b-3")},
        {"supplier_id": "99999999-9999-9999-9999-999999999999"},
        {"quantity_kg": "601"},
        {"cost_idr": "1"},
        {"policy_version": "sim-2026-10-30.v2"},
        {"evaluation_status": "on_hold"},
        {"blocking_reasons": ("temperature_evidence_incomplete",)},
        {"decision_id": "66666666-6666-6666-6666-666666666666"},
    ],
)
def test_setiap_bukti_yang_berubah_mengubah_sidik(perubahan) -> None:
    assert df.hitung_sidik(replace(DASAR, **perubahan)) != df.hitung_sidik(DASAR)


def test_sidik_kosong_tidak_pernah_dianggap_cocok() -> None:
    """Approval tanpa sidik tersimpan tidak boleh lolos sebagai "cocok"."""
    assert df.sidik_cocok(DASAR, None) is False
    assert df.sidik_cocok(DASAR, "") is False
    assert df.sidik_cocok(DASAR, df.hitung_sidik(DASAR)) is True


def test_input_wajib_tidak_boleh_kosong() -> None:
    with pytest.raises(ValueError):
        df.hitung_sidik(replace(DASAR, decision_id=""))
    with pytest.raises(ValueError):
        df.hitung_sidik(replace(DASAR, commodity_id=""))
    with pytest.raises(ValueError):
        df.hitung_sidik(replace(DASAR, quantity_kg="bukan angka"))
    with pytest.raises(ValueError):
        df.hitung_sidik(replace(DASAR, evaluation_status="aman-sekali"))


def test_tanpa_batch_tetap_menghasilkan_sidik_dari_bukti_lain() -> None:
    """Keputusan administratif tanpa transfer tidak punya batch — sah."""
    administratif = replace(DASAR, batch_ids=(), supplier_id=None)
    sidik = df.hitung_sidik(administratif)
    assert sidik != df.hitung_sidik(DASAR)


def test_dari_decision_mengambil_kolom_yang_ada_tanpa_menebak() -> None:
    class KeputusanPalsu:
        id = DASAR.decision_id
        supplier_id = DASAR.supplier_id
        quantity_kg = "600"
        safe_delivered_cost = "16206000"
        source_location_id = DASAR.source_location_id
        target_location_id = DASAR.target_location_id
        commodity_id = DASAR.commodity_id

    hasil = df.dari_decision(
        KeputusanPalsu(),
        batch_ids=["b-1", "b-2"],
        supplier_id=None,  # None = pakai kolom keputusan
        policy_version=DASAR.policy_version,
        evaluation_status="usable",
    )
    assert df.hitung_sidik(hasil) == df.hitung_sidik(DASAR)


def test_dari_decision_menolak_keputusan_tanpa_kolom_wajib() -> None:
    class TanpaKomoditas:
        id = DASAR.decision_id
        quantity_kg = "600"
        safe_delivered_cost = "16206000"
        source_location_id = None
        target_location_id = None

    with pytest.raises(ValueError):
        df.dari_decision(
            TanpaKomoditas(),
            batch_ids=[],
            supplier_id=None,
            policy_version=DASAR.policy_version,
            evaluation_status="usable",
        )
