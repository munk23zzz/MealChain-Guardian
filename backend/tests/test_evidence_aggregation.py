"""Agregasi bukti suhu satu grup batch (Fase 3 MG butir 6) — bagian mandiri.

Kutipan kontrak (`MG/phase-03-commodity-evidence.md`):

> Agregasi batch memakai status terburuk dan bukti paling lemah. `fail` tidak
> pernah berubah menjadi `pass` oleh komoditas, skor, atau prompt.
> **6. Uji agregasi dan Joule.** Campuran batch tidak boleh membuat bukti
> terlemah hilang.

Berkas ini sengaja HANYA menguji lapisan bukti (`app.services.batch_evidence`),
tanpa menyentuh `core/candidate_generation.py`. Alasannya kepemilikan, bukan
kelengkapan: modul generator sedang diubah sesi lain (parameter `held`/`policies`
dan `fuse_evidence` belum ada di HEAD), sehingga tes yang memanggilnya tidak akan
bisa berjalan pada commit ini. Uji integrasi generator ada di
`test_commodity_evidence_aggregation.py` dan ikut commit yang memuat modul itu.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.commodity_policy import policy_for
from app.services.batch_evidence import (
    blok_bukti_batch,
    blok_bukti_kandidat,
    blok_bukti_profil_hilang,
    weakest_observation,
)

AS_OF = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
EGG = policy_for("telur")


def _stamp(jam_lalu: float, suhu: float) -> dict:
    return {
        "timestamp": (AS_OF - timedelta(hours=jam_lalu)).isoformat(),
        "temperature_c": suhu,
    }


LOG_SAH = [_stamp(2, 4.0), _stamp(1, 4.5)]
LOG_KOSONG: list = []
LOG_LAMA = [_stamp(24 * 5, 4.0), _stamp(24 * 5 - 0.5, 4.5)]


def _blok(batch_id: str, log: list, origin: str = "seed") -> dict:
    return {
        "batch_id": batch_id,
        **blok_bukti_batch(
            temperature_log=log,
            policy=EGG,
            policy_source="commodity_policies",
            origin=origin,
            evaluation_time=AS_OF,
            safety_status="pass",
        ),
    }


# ── label terlemah ─────────────────────────────────────────────────────────


def test_weakest_observation_memilih_yang_terlemah():
    blok = [_blok("a", LOG_SAH), _blok("b", LOG_KOSONG), _blok("c", LOG_LAMA)]
    assert weakest_observation(blok) == "missing"


def test_weakest_observation_kosong_tanpa_blok_tidak_mengarang():
    assert weakest_observation([]) is None
    assert weakest_observation([{}, {"temperature_observation": None}]) is None


# ── grup campuran: bukti terlemah tidak hilang ─────────────────────────────


def test_grup_campuran_melaporkan_batch_tertahan():
    """Batch tanpa log yang dikeluarkan tetap meninggalkan jejak.

    Tanpa `held_batch_ids`, pembaca melihat "aman 300 kg" dan tidak tahu 300 kg
    lain menunggu verifikasi — persis "bukti terlemah hilang" yang dilarang.
    """
    agregat = blok_bukti_kandidat(
        batch_blok=[_blok("b-sah", LOG_SAH), _blok("b-kosong", LOG_KOSONG)],
        batch_ids=["b-sah"],
        held_batch_ids=["b-kosong"],
    )
    assert agregat["held_batch_ids"] == ["b-kosong"], agregat
    assert agregat["weakest_observation"] == "missing", agregat


def test_grup_campuran_tidak_menyatakan_bukti_cukup():
    """Sebagian terbukti + sebagian tertahan → `ambiguous`, bukan `sufficient`.

    `sufficient` akan menutupi kilogram yang tidak boleh diusulkan;
    `insufficient` akan menyangkal kilogram yang benar-benar terbukti.
    """
    agregat = blok_bukti_kandidat(
        batch_blok=[_blok("b-sah", LOG_SAH), _blok("b-kosong", LOG_KOSONG)],
        batch_ids=["b-sah"],
        held_batch_ids=["b-kosong"],
    )
    assert agregat["evidence_state"] == "ambiguous", agregat
    assert agregat["evidence_sufficient"] is False, agregat


def test_grup_terbukti_penuh_menyatakan_cukup():
    agregat = blok_bukti_kandidat(
        batch_blok=[_blok("b-1", LOG_SAH), _blok("b-2", LOG_SAH)],
        batch_ids=["b-1", "b-2"],
        held_batch_ids=[],
    )
    assert agregat["evidence_state"] == "sufficient", agregat
    assert agregat["temperature_observation"] == "observed", agregat
    assert agregat["sample_count"] == 4, agregat
    assert agregat["observed_at"] is not None, agregat
    assert agregat["source_label"] == "log simulasi", agregat
    assert {b["batch_id"] for b in agregat["batch_evidence"]} == {"b-1", "b-2"}


def test_grup_tanpa_batch_pengikut_tidak_cukup():
    agregat = blok_bukti_kandidat(
        batch_blok=[_blok("b-kosong", LOG_KOSONG)],
        batch_ids=[],
        held_batch_ids=["b-kosong"],
    )
    assert agregat["evidence_state"] == "insufficient", agregat
    assert agregat["evidence_sufficient"] is False, agregat


# ── staleness & profil hilang tidak boleh lolos sebagai "observed" ─────────


def test_log_lama_ditandai_stale_bukan_observed():
    """Sampel lima hari lalu bukan observasi real-time."""
    blok = _blok("b-lama", LOG_LAMA)
    assert blok["temperature_observation"] == "stale", blok
    agregat = blok_bukti_kandidat(
        batch_blok=[blok], batch_ids=["b-lama"], held_batch_ids=[]
    )
    assert agregat["temperature_observation"] != "observed", agregat
    assert agregat["evidence_sufficient"] is False, agregat


def test_tanpa_profil_mengaku_bukan_mengarang_rentang():
    blok = blok_bukti_profil_hilang(
        komoditas="kangkung", origin="seed", evaluation_time=AS_OF
    )
    agregat = blok_bukti_kandidat(
        batch_blok=[{"batch_id": "b-k", **blok}],
        batch_ids=["b-k"],
        held_batch_ids=[],
    )
    assert agregat["profile_source"] == "tidak ada", agregat
    assert agregat["temperature_observation"] != "observed", agregat
    assert agregat["evidence_state"] == "insufficient", agregat
