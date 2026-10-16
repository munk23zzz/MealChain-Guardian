"""Perjalanan kiriman (pemasok → tujuan): jam berangkat, estimasi tiba, keadaan.

Kontrak yang dikunci tes ini (permintaan pemilik 2026-10-16: "tampilkan waktu
estimasi sampai … pastikan sinkron dengan database"):

- estimasi tiba **tidak pernah** dihitung tanpa jam berangkat dari DB dan tanpa
  waktu tempuh nyata dari cache OSRM — tidak ada angka perjalanan yang dikarang;
- keadaan perjalanan dibaca dari WAKTU (sekarang vs berangkat vs tiba), bukan
  dari tebakan: `belum_berangkat`, `di_jalan`, `sudah_tiba`, dan
  `tidak_diketahui` (sudah berangkat tetapi waktu tempuhnya belum ada — tidak
  boleh diklaim tiba maupun di jalan);
- jam berangkat tidak boleh mendahului panen (`dispatched_at >= harvested_at`),
  dijaga di sini DAN oleh CHECK constraint di DB;
- perbandingan dengan `usable_until` dilaporkan sebagai PERBANDINGAN dua angka
  (estimasi tiba vs batas layak), bukan sebagai klaim keamanan.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.journey import (
    STATE_BELUM_BERANGKAT,
    STATE_DI_JALAN,
    STATE_SUDAH_TIBA,
    STATE_TIDAK_DIKETAHUI,
    dispatch_time,
    elapsed_min,
    eta_at,
    journey_payload,
    journey_state,
    progress_ratio,
    remaining_min,
    validate_dispatch,
)

NOW = datetime(2026, 10, 16, 22, 30, tzinfo=UTC)
REF = datetime(2026, 10, 16, 22, 30, tzinfo=UTC)
HARVEST = datetime(2026, 10, 16, 6, 0, tzinfo=UTC)
#: 84,3 menit = waktu tempuh OSRM Cianjur → Jakarta (dari cache `road_routes`).
TRAVEL_S = 5058.0


def test_jam_berangkat_dihitung_dari_referensi_seeder():
    assert dispatch_time(REF, -1.0) == REF - timedelta(hours=1)
    assert dispatch_time(REF, -1.5) == REF - timedelta(hours=1, minutes=30)
    # Belum berangkat: TIDAK ada jam berangkat (NULL di DB), bukan jam karangan.
    assert dispatch_time(REF, None) is None
    with pytest.raises(ValueError):
        dispatch_time(REF.replace(tzinfo=None), -1.0)
    with pytest.raises(ValueError):
        dispatch_time(REF, float("nan"))


def test_jam_berangkat_tidak_boleh_mendahului_panen():
    panen = HARVEST
    assert validate_dispatch(panen, panen + timedelta(hours=1)) is None
    # Berangkat bersamaan dengan panen masih masuk akal (tidak ada staging).
    assert validate_dispatch(panen, panen) is None
    # Tanpa jam berangkat: tidak ada yang dilanggar.
    assert validate_dispatch(panen, None) is None
    with pytest.raises(ValueError):
        # berangkat 2 jam SEBELUM panen = tidak mungkin
        validate_dispatch(panen, panen - timedelta(hours=2))


def test_estimasi_tiba_hanya_dari_jam_berangkat_plus_waktu_tempuh():
    berangkat = dispatch_time(REF, -1.0)
    assert eta_at(berangkat, TRAVEL_S) == berangkat + timedelta(seconds=TRAVEL_S)
    # Tanpa jam berangkat atau tanpa waktu tempuh: TIDAK ada estimasi.
    assert eta_at(None, TRAVEL_S) is None
    assert eta_at(berangkat, None) is None
    assert eta_at(berangkat, 0) is None


def test_keadaan_perjalanan_dibaca_dari_waktu():
    berangkat = NOW - timedelta(minutes=60)
    tiba = berangkat + timedelta(minutes=84.3)
    assert journey_state(NOW, berangkat, tiba) == STATE_DI_JALAN
    # Tepat saat berangkat = di jalan (0 menit berjalan), bukan "belum berangkat".
    assert journey_state(berangkat, berangkat, tiba) == STATE_DI_JALAN
    # Tepat pada estimasi tiba = sudah tiba.
    assert journey_state(tiba, berangkat, tiba) == STATE_SUDAH_TIBA
    assert journey_state(tiba + timedelta(minutes=1), berangkat, tiba) == STATE_SUDAH_TIBA
    # Belum berangkat: jam berangkat kosong ATAU masih di depan.
    assert journey_state(NOW, None, None) == STATE_BELUM_BERANGKAT
    assert journey_state(NOW, NOW + timedelta(hours=2), None) == STATE_BELUM_BERANGKAT
    # Sudah berangkat tetapi waktu tempuh belum ada: TIDAK diklaim tiba/di jalan.
    assert journey_state(NOW, berangkat, None) == STATE_TIDAK_DIKETAHUI


def test_sisa_dan_progres_perjalanan():
    berangkat = NOW - timedelta(minutes=60)
    tiba = berangkat + timedelta(minutes=84.3)
    assert remaining_min(NOW, tiba) == pytest.approx(24.3, abs=0.01)
    assert elapsed_min(NOW, berangkat) == pytest.approx(60.0, abs=0.01)
    assert progress_ratio(NOW, berangkat, tiba) == pytest.approx(0.71, abs=0.01)
    # Dijaga di rentang 0..1 — tidak pernah "150% perjalanan".
    assert progress_ratio(tiba + timedelta(hours=5), berangkat, tiba) == 1.0
    assert progress_ratio(berangkat - timedelta(hours=5), berangkat, tiba) == 0.0
    # Tanpa dua ujung waktu, tidak ada progres yang bisa dilaporkan.
    assert progress_ratio(NOW, None, tiba) is None
    assert remaining_min(NOW, None) is None
    assert elapsed_min(NOW, None) is None


def test_payload_perjalanan_menyebut_asal_angka_dan_batas_layak():
    berangkat = NOW - timedelta(minutes=60)
    usable_until = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    payload = journey_payload(
        now=NOW,
        dispatched_at=berangkat,
        travel_s=TRAVEL_S,
        travel_source="osrm",
        usable_until=usable_until,
    )
    assert payload["state"] == STATE_DI_JALAN
    assert payload["eta_at"] == (berangkat + timedelta(seconds=TRAVEL_S)).isoformat()
    assert payload["travel_min"] == pytest.approx(84.3, abs=0.01)
    assert payload["travel_source"] == "osrm"
    assert payload["remaining_min"] == pytest.approx(24.3, abs=0.01)
    assert payload["arrives_before_usable_until"] is True

    # Estimasi yang melewati batas layak dilaporkan apa adanya (False), bukan disembunyikan.
    payload_lambat = journey_payload(
        now=NOW,
        dispatched_at=berangkat,
        travel_s=30 * 24 * 3600,  # 30 hari perjalanan
        travel_source="osrm",
        usable_until=usable_until,
    )
    assert payload_lambat["arrives_before_usable_until"] is False

    # Tanpa jam berangkat: keadaan jujur "belum berangkat", tanpa estimasi.
    belum = journey_payload(
        now=NOW,
        dispatched_at=None,
        travel_s=TRAVEL_S,
        travel_source="osrm",
        usable_until=usable_until,
    )
    assert belum["state"] == STATE_BELUM_BERANGKAT
    assert belum["eta_at"] is None
    assert belum["remaining_min"] is None
    assert belum["progress"] is None
    assert belum["arrives_before_usable_until"] is None
    # Waktu tempuh tetap dilaporkan: itu sifat JALUR, bukan sifat barang.
    assert belum["travel_min"] == pytest.approx(84.3, abs=0.01)

    # Belum ada jalur jalan: keadaan tidak diklaim, estimasi tidak ada.
    tanpa_jalur = journey_payload(
        now=NOW,
        dispatched_at=berangkat,
        travel_s=None,
        travel_source=None,
        usable_until=usable_until,
    )
    assert tanpa_jalur["state"] == STATE_TIDAK_DIKETAHUI
    assert tanpa_jalur["eta_at"] is None
    assert tanpa_jalur["travel_min"] is None
    assert tanpa_jalur["arrives_before_usable_until"] is None
