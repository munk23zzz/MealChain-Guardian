"""Generator kasus replay/realtime (Fase 7 MG butir 1, 2, 4, 6).

Kenapa berkas ini ada: sebelum Fase 7 tidak ada satu pun modul yang menjawab
"ID apa dan jam berapa baris kasus ini" — seeder memakai `datetime.now()` dan
`gen_random_uuid`, sehingga dua pembuatan dataset yang sama menghasilkan baris
berbeda dan replay tidak dapat direproduksi.

Yang dipaku di sini (tanpa database; modul generator murni):

1. identitas replay STABIL (dua pembuatan = ID sama), realtime BERBEDA per
   jangkar, dan keduanya tidak pernah bertabrakan;
2. waktu peristiwa simulasi selalu offset dari jangkar dan TIDAK PERNAH di masa
   depan relatif jangkar (`event_at` menolak offset positif);
3. log suhu berlabel simulasi (`simulated_replay`/`simulated_realtime`), bukan
   `sensor`, dan entri rusak benar-benar tidak terbaca;
4. skor kesegaran + masa layak DIHITUNG dari profil komoditas, dan kasus
   `usable` konsisten (tiba sebelum tenggat, layak saat tiba, tenggat belum
   lewat);
5. kasus `on_hold` menyatakan bukti yang tidak cukup, bukan kegagalan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.commodity_policy import policy_for
from app.services import scenario_generator as gen
from app.services.scenario_specs import (
    SCENARIO_VERSION,
    BatchSpec,
    ScenarioCaseSpec,
    kasus_komoditas,
    spec_untuk,
)

JANGKAR_REPLAY = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
JANGKAR_REALTIME = datetime(2026, 10, 27, 3, 15, tzinfo=timezone.utc)
VERSI_REPLAY = "kanon-2026-10-08T12:00:00Z"
VERSI_REALTIME = "realtime-20261027T031500Z"


def _spec(key: str) -> ScenarioCaseSpec:
    return spec_untuk(key)


# --- butir 1: replay identik -------------------------------------------------


def test_identitas_replay_stabil_walau_dibangun_lagi():
    spec = _spec("wortel-coldchain-sah")
    a = gen.identitas_kasus(
        spec, mode="replay", anchor=JANGKAR_REPLAY, dataset_version=VERSI_REPLAY,
        target="Jakarta",
    )
    # Pembangunan kedua di hari lain, tetapi dataset kanon yang sama: identitas
    # harus sama, supaya rerun tidak menggandakan baris.
    b = gen.identitas_kasus(
        spec,
        mode="replay",
        anchor=datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc),
        dataset_version=VERSI_REPLAY,
        target="Jakarta",
    )
    assert a == b
    assert gen.id_decision(a, iteration=3) == gen.id_decision(b, iteration=3)
    batch = spec.batches[0]
    assert gen.id_batch(a, batch) == gen.id_batch(b, batch)


def test_identitas_memuat_kota_dan_versi_skenario():
    spec = _spec("wortel-coldchain-sah")
    jakarta = gen.identitas_kasus(
        spec, mode="replay", anchor=JANGKAR_REPLAY, dataset_version=VERSI_REPLAY,
        target="Jakarta",
    )
    bandung = gen.identitas_kasus(
        spec, mode="replay", anchor=JANGKAR_REPLAY, dataset_version=VERSI_REPLAY,
        target="Bandung",
    )
    assert jakarta != bandung, "kasus dua kota tidak boleh berbagi ID"
    assert SCENARIO_VERSION in jakarta
    assert "Jakarta" in jakarta


def test_identitas_realtime_berbeda_per_jangkar_dan_dari_replay():
    spec = _spec("wortel-coldchain-sah")
    replay = gen.identitas_kasus(
        spec, mode="replay", anchor=JANGKAR_REPLAY, dataset_version=VERSI_REPLAY,
        target="Jakarta",
    )
    sesi1 = gen.identitas_kasus(
        spec, mode="realtime", anchor=JANGKAR_REALTIME,
        dataset_version=VERSI_REALTIME, target="Jakarta",
    )
    sesi2 = gen.identitas_kasus(
        spec, mode="realtime", anchor=JANGKAR_REALTIME + timedelta(minutes=7),
        dataset_version="realtime-20261027T032200Z", target="Jakarta",
    )
    assert sesi1 != sesi2, "dua sesi realtime harus punya identitas berbeda"
    assert replay not in (sesi1, sesi2)
    assert gen.id_decision(replay, iteration=1) != gen.id_decision(sesi1, iteration=1)


def test_mode_asing_ditolak():
    spec = _spec("wortel-coldchain-sah")
    with pytest.raises(ValueError):
        gen.identitas_kasus(
            spec, mode="live", anchor=JANGKAR_REPLAY, dataset_version=VERSI_REPLAY,
            target="Jakarta",
        )


# --- butir 2: waktu relatif jangkar, tidak di masa depan ---------------------


def test_peristiwa_tidak_boleh_di_masa_depan_relatif_jangkar():
    spec = _spec("wortel-coldchain-sah")
    with pytest.raises(gen.FutureEventError):
        gen.event_at(JANGKAR_REPLAY, 5, label="panen")
    # Nol dan negatif sah: "saat dataset dievaluasi" dan "sebelumnya".
    assert gen.event_at(JANGKAR_REPLAY, 0) == JANGKAR_REPLAY
    assert gen.event_at(JANGKAR_REPLAY, -30) == JANGKAR_REPLAY - timedelta(minutes=30)
    # Setiap batch spec yang dikirim ke generator juga dijaga di tingkat spec.
    with pytest.raises(ValueError):
        BatchSpec(
            label="x", quantity_kg=1.0, harvest_offset_min=15, dispatched_offset_min=None
        )
    assert spec.batches, "kasus contoh harus punya batch"


def test_semua_peristiwa_batch_relatif_jangkar():
    spec = _spec("wortel-coldchain-sah")
    policy = policy_for(spec.commodity)
    baris = gen.rencana_batch(
        spec, spec.batches[0], anchor=JANGKAR_REPLAY, mode="replay", policy=policy
    )
    assert baris["harvested_at"] < JANGKAR_REPLAY
    assert baris["dispatched_at"] < JANGKAR_REPLAY
    assert baris["usable_until"] > JANGKAR_REPLAY
    for entri in baris["temperature_log"]:
        stempel = datetime.fromisoformat(entri["timestamp"])
        assert stempel <= JANGKAR_REPLAY
        assert JANGKAR_REPLAY - stempel <= timedelta(hours=6)


def test_jangkar_naif_ditolak():
    with pytest.raises(ValueError):
        gen.event_at(datetime(2026, 10, 8, 12, 0), -10)


# --- butir 2 & 4: label simulasi, bukan sensor ------------------------------


def test_log_suhu_berlabel_simulasi_per_mode():
    spec = _spec("wortel-coldchain-sah")
    replay = gen.log_suhu(spec.batches[0], anchor=JANGKAR_REPLAY, mode="replay")
    realtime = gen.log_suhu(spec.batches[0], anchor=JANGKAR_REALTIME, mode="realtime")
    assert {e["source"] for e in replay} == {"simulated_replay"}
    assert {e["source"] for e in realtime} == {"simulated_realtime"}
    teks = " ".join(str(e) for e in replay)
    assert "sensor" not in teks


def test_kasus_hold_punya_entri_rusak_yang_tidak_terbaca():
    spec = _spec("wortel-coldchain-hold")
    log = gen.log_suhu(spec.batches[0], anchor=JANGKAR_REPLAY, mode="replay")
    sah = [e for e in log if e.get("timestamp") and isinstance(e["temperature_c"], float)]
    rusak = [e for e in log if not isinstance(e["temperature_c"], float)]
    assert len(sah) == 1, "kasus on_hold sengaja hanya punya satu sampel sah"
    assert len(rusak) == 2
    assert all(e["timestamp"] is None for e in rusak)


# --- butir 4 & 6: angka dihitung, kasus usable konsisten --------------------


def test_skor_dan_masa_layak_dihitung_dari_profil():
    spec = _spec("wortel-coldchain-sah")
    policy = policy_for(spec.commodity)
    baris = gen.rencana_batch(
        spec, spec.batches[0], anchor=JANGKAR_REPLAY, mode="replay", policy=policy
    )
    skor = float(baris["freshness_score"])
    assert 0.0 <= skor <= 1.0
    # Masa layak = panen + shelf_life * skor (rumus core, bukan angka tangan).
    harap = baris["harvested_at"] + timedelta(days=policy.shelf_life_days * skor)
    assert abs((baris["usable_until"] - harap).total_seconds()) < 1


def test_kasus_usable_konsisten_dengan_tenggat_dan_logistik():
    spec = _spec("wortel-coldchain-sah")
    policy = policy_for(spec.commodity)
    baris = gen.rencana_batch(
        spec, spec.batches[0], anchor=JANGKAR_REPLAY, mode="replay", policy=policy
    )
    masalah = gen.pemeriksaan_konsistensi(
        spec, [baris], anchor=JANGKAR_REPLAY, travel_minutes=150
    )
    assert masalah == (), f"kasus usable tidak konsisten: {masalah}"


def test_pemeriksaan_menangkap_tenggat_yang_sudah_lewat():
    """Kasus `usable` dengan tenggat lampau HARUS ditolak, bukan diloloskan."""
    spec = ScenarioCaseSpec(
        key="uji-tenggat-lewat",
        kind="commodity",
        commodity="wortel",
        target_location="Jakarta",
        source_candidates=("Bogor",),
        quantity_kg=100.0,
        intended_outcome="usable",
        demand_needed_by_offset_min=-120,
        batches=(
            BatchSpec(
                label="b",
                quantity_kg=100.0,
                harvest_offset_min=-300,
                dispatched_offset_min=-200,
                temperature_offsets_min=(-150, -90),
                temperatures_c=(3.0, 3.5),
            ),
        ),
    )
    baris = gen.rencana_batch(
        spec, spec.batches[0], anchor=JANGKAR_REPLAY, mode="replay",
        policy=policy_for("wortel"),
    )
    masalah = gen.pemeriksaan_konsistensi(
        spec, [baris], anchor=JANGKAR_REPLAY, travel_minutes=150
    )
    assert "kasus_usable:tenggat_sudah_lewat" in masalah


def test_pemeriksaan_menangkap_layak_sebelum_tiba():
    spec = ScenarioCaseSpec(
        key="uji-layak-sebelum-tiba",
        kind="commodity",
        commodity="wortel",
        target_location="Jakarta",
        source_candidates=("Bogor",),
        quantity_kg=100.0,
        intended_outcome="usable",
        demand_needed_by_offset_min=600,
        batches=(
            BatchSpec(
                label="b",
                quantity_kg=100.0,
                # Panen 20 hari sebelum jangkar pada wortel (masa layak 21 hari):
                # masih layak saat dievaluasi, tetapi bisa saja habis sebelum
                # tiba kalau perjalanan panjang.
                harvest_offset_min=-20 * 24 * 60,
                dispatched_offset_min=-10,
                temperature_offsets_min=(-600, -60),
                temperatures_c=(3.0, 3.5),
            ),
        ),
    )
    baris = gen.rencana_batch(
        spec, spec.batches[0], anchor=JANGKAR_REPLAY, mode="replay",
        policy=policy_for("wortel"),
    )
    masalah = gen.pemeriksaan_konsistensi(
        spec, [baris], anchor=JANGKAR_REPLAY, travel_minutes=10 * 24 * 60
    )
    assert any(kode.endswith("layak_sebelum_tiba") for kode in masalah)


# --- provenance -------------------------------------------------------------


def test_provenance_menyatakan_simulasi_tanpa_klaim_produksi():
    spec = _spec("beras-ambient")
    blok = gen.provenance(
        spec, mode="realtime", anchor=JANGKAR_REALTIME, dataset_version=VERSI_REALTIME
    )
    assert blok["simulated"] is True
    assert blok["temperature_source"] == "simulated_realtime"
    assert blok["mode"] == "realtime"
    assert blok["evaluation_anchor"] == JANGKAR_REALTIME.isoformat()
    teks = str(blok).lower()
    assert "sap production" not in teks
    assert "sensor aktif" not in teks


# --- kelengkapan daftar kasus ----------------------------------------------


def test_kasus_komoditas_lengkap_dan_unik():
    kunci = [spec.key for spec in kasus_komoditas()]
    # 30 Okt 2026: telur + ayam ikut, karena tanpa keduanya panel demo tidak
    # punya kasus untuk dua dari empat komoditas yang bisa dipilih.
    assert kunci == [
        "wortel-coldchain-sah",
        "wortel-coldchain-hold",
        "beras-ambient",
        "telur-rantai-dingin-sah",
        "ayam-rantai-dingin-hold",
    ]
    assert len(set(kunci)) == len(kunci)
    for spec in kasus_komoditas():
        assert spec.batches, f"{spec.key} tanpa batch"
        assert spec.price_per_kg and spec.price_per_kg > 0
        assert spec.demand_needed_by_offset_min is not None
        assert spec.decision_status == "pending_approval"


def test_waktu_catat_kebutuhan_tidak_bertabrakan_antar_kasus():
    """Dua kasus dengan komoditas+kota sama wajib berbeda `recorded_at`.

    Kunci unik `demand_records` adalah (lokasi, komoditas, recorded_at). Kalau
    dua kasus wortel menulis jam yang sama, penyemai meng-update baris pertama
    dan kebutuhan 420 kg/8 jam HILANG — hanya 380 kg/6 jam yang tersisa, padahal
    kedua kasus diklaim lengkap. Diuji di generator (bukan di DB) supaya
    kegagalannya menunjuk spesifikasi, bukan efek samping unik constraint.
    """
    kunci: dict[tuple[str, str], set[datetime]] = {}
    for spec in kasus_komoditas():
        demand = gen.rencana_demand(spec, anchor=JANGKAR_REPLAY, mode="replay")
        assert demand is not None
        pasangan = (spec.commodity, spec.target_location)
        kunci.setdefault(pasangan, set()).add(demand["recorded_at"])
    for pasangan, jam in kunci.items():
        jumlah_kasus = sum(
            1
            for spec in kasus_komoditas()
            if (spec.commodity, spec.target_location) == pasangan
        )
        assert len(jam) == jumlah_kasus, (
            f"{pasangan}: {jumlah_kasus} kasus tetapi hanya {len(jam)} slot waktu "
            "kebutuhan — baris akan saling menimpa"
        )
        assert all(stempel <= JANGKAR_REPLAY for stempel in jam)
