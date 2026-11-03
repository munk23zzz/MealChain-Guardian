"""Seed Jakarta harus bisa memperagakan TIGA keadaan perjalanan sekaligus.

Temuan riset 7b-3 (17 Okt 2026): satu-satunya kiriman Jakarta berangkat -1 jam
pada rute 84 menit. Akibatnya (a) jendela "di jalan" hanya ~24 menit setelah
"Segarkan ke hari ini", dan (b) di tujuan yang dilihat peran SPPG Head tidak ada
kiriman "belum berangkat" maupun "sudah tiba". Demo jadi bergantung pada jam
dinding, bukan pada data.

Tes ini mengunci struktur yang dibutuhkan, bukan angka tampilan:
- ketiga keadaan ada di Jakarta pada saat seed,
- kiriman "di jalan" punya progres yang terbaca (bukan 0% atau 90%) dan
  jendela sisa ≥ 45 menit,
- ketiga kiriman datang dari pemasok berbeda supaya garisnya tidak menumpuk
  persis (garis identik = satu garis di layar, bukan tiga).
"""

from datetime import UTC, datetime

from app.core.journey import (
    STATE_BELUM_BERANGKAT,
    STATE_DI_JALAN,
    STATE_SUDAH_TIBA,
    eta_at,
    journey_state,
    progress_ratio,
)
from app.seed.seed_data import build_seed_rows

REF = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
#: Durasi OSRM Cianjur → Jakarta yang dipakai koridor demo (road_routes).
TRAVEL_CIANJUR_JAKARTA_S = 5060


def _jakarta(rows: dict) -> list[dict]:
    return [b for b in rows["batches"] if b["location"] == "Jakarta"]


def _keadaan(batch: dict, now: datetime = REF) -> str:
    eta = eta_at(batch["dispatched_at"], TRAVEL_CIANJUR_JAKARTA_S)
    return journey_state(now, batch["dispatched_at"], eta)


def test_jakarta_punya_tiga_keadaan_perjalanan_saat_seed() -> None:
    rows = build_seed_rows(REF)
    keadaan = {_keadaan(b) for b in _jakarta(rows)}

    assert STATE_DI_JALAN in keadaan, "tidak ada kiriman Jakarta yang sedang di jalan"
    assert STATE_SUDAH_TIBA in keadaan, "tidak ada kiriman Jakarta yang sudah tiba"
    assert (
        STATE_BELUM_BERANGKAT in keadaan
    ), "tidak ada kiriman Jakarta yang belum berangkat"


def test_kiriman_di_jalan_punya_progres_terbaca_dan_jendela_cukup() -> None:
    rows = build_seed_rows(REF)
    berjalan = [b for b in _jakarta(rows) if _keadaan(b) == STATE_DI_JALAN]

    assert len(berjalan) == 1, f"harus tepat satu kiriman 'di jalan', dapat {len(berjalan)}"
    batch = berjalan[0]
    eta = eta_at(batch["dispatched_at"], TRAVEL_CIANJUR_JAKARTA_S)
    assert eta is not None, "kiriman 'di jalan' wajib punya estimasi tiba"
    progres = progress_ratio(REF, batch["dispatched_at"], eta)
    assert progres is not None, "progres wajib terhitung untuk kiriman 'di jalan'"
    sisa_menit = (eta - REF).total_seconds() / 60

    assert 0.15 <= progres <= 0.50, f"progres {progres:.2f} harus terbaca, bukan 0 atau 90%"
    assert sisa_menit >= 45, (
        f"jendela 'di jalan' hanya {sisa_menit:.0f} menit — demo bisa selesai sebelum "
        "juri melihatnya"
    )


def test_kiriman_jakarta_dari_pemasok_berbeda_agar_garis_tidak_menumpuk() -> None:
    rows = build_seed_rows(REF)
    pemasok = [b["supplier"] for b in _jakarta(rows)]

    assert len(pemasok) == len(set(pemasok)), f"pemasok kembar: {pemasok}"
    assert len(pemasok) >= 3, f"butuh ≥3 kiriman Jakarta, dapat {len(pemasok)}"


def test_semua_kiriman_jakarta_masih_layak_dipakai_saat_seed() -> None:
    rows = build_seed_rows(REF)
    kedaluwarsa = [b["code"] for b in _jakarta(rows) if b["usable_until"] < REF]

    assert kedaluwarsa == [], f"kiriman kedaluwarsa tidak akan tampil di peta: {kedaluwarsa}"
