"""Regression: later-visible batches must not enter an earlier freshness evaluation."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Batch, Commodity, Location, Supplier
from app.services import recommendation_service as rs
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

AS_OF = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def _log_suhu(harvested_at: datetime) -> list[dict]:
    """Bukti suhu LENGKAP (dua sampel) untuk satu batch.

    Dipakai DUA kali: sebagai isi baris `batches` dan sebagai argumen saat
    menghitung nilai harapan. Sebelum ini baris DB diberi log lengkap sementara
    nilai harapan dihitung dengan log KOSONG, sehingga tes gagal (0,964286 vs
    0,664286) bukan karena produk salah melainkan karena tes membandingkan dua
    input berbeda. Sejak F-02 (25 Okt 2026) log kosong memang dihukum penuh
    (`outside_fraction = 1.0`, −0,30), jadi yang harus diperbaiki adalah
    ekspektasinya — bukan aturan keselamatannya.
    """
    return [
        {"timestamp": harvested_at.isoformat(), "temperature_c": 4.0},
        {
            "timestamp": (harvested_at - timedelta(minutes=10)).isoformat(),
            "temperature_c": 4.2,
        },
    ]


@pytest.mark.parametrize("explicit_as_of", [False, True], ids=["live-race", "historical"])
def test_fetch_excludes_later_harvests_without_advancing_as_of(monkeypatch, explicit_as_of):
    engine = create_engine(
        DSN_SYNC
    )

    # Pipeline kini mengambil jam dari `evaluation_clock()` (refactor jam sesi
    # lain), bukan `datetime.now()`. Membekukan `rs.datetime` tidak lagi
    # berpengaruh; yang dibekukan adalah jam evaluasinya.
    beku = AS_OF + timedelta(days=1) if explicit_as_of else AS_OF

    def _jam(as_of=None):
        return as_of if as_of is not None else beku

    # Hanya varian historis yang membekukan jam. Varian "live-race" justru
    # menguji `as_of=None`: membekukannya ke 8 Okt membuat SEMUA baris uji
    # (28 Okt) terbaca "panen di masa depan" dan fungsi melempar ValueError —
    # itu menguji jam palsu, bukan perlombaan yang dimaksud.
    if explicit_as_of:
        monkeypatch.setattr(rs, "evaluation_clock", _jam)
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            with Session(bind=connection) as session:
                location = session.scalar(select(Location).where(Location.name == "Cianjur"))
                commodity = session.scalar(select(Commodity).where(Commodity.name == "telur"))
                supplier = session.scalar(select(Supplier).limit(1))
                ids = {name: uuid.uuid4() for name in ("old", "boundary", "later")}
                if explicit_as_of:
                    acuan = AS_OF
                    harvested = {
                        "old": AS_OF - timedelta(days=1),
                        "boundary": AS_OF,
                        "later": AS_OF + timedelta(milliseconds=600),
                    }
                else:
                    # Varian jam dinding: `fetch_operational_facts(as_of=None)`
                    # memakai `datetime.now()`, BUKAN `evaluation_clock` — jadi
                    # patokan harus jam nyata, dan "later" harus jelas di masa
                    # depan. Dengan +600 ms, batch itu sudah "masa lalu" saat
                    # fungsi membaca jamnya, sehingga tes gagal bukan karena
                    # produk bocor melainkan karena asumsi jamnya salah
                    # (terukur 28 Okt 2026: [live-race] merah di setiap run).
                    # Baris disisipkan saat fungsi mengirim query PERTAMA,
                    # yaitu sesudah ia mengambil jamnya. Karena itu "later"
                    # cukup 2 detik di depan: pasti sesudah jam yang dipakai,
                    # dan tidak memicu ValueError "panen di masa depan" yang
                    # muncul bila jaraknya berjam-jam.
                    mulai = datetime.now(timezone.utc)
                    # Nilai harapan HARUS dihitung pada jam yang sama dengan
                    # yang dipakai fungsi (jam dinding di varian ini).
                    acuan = mulai
                    harvested = {
                        "old": mulai - timedelta(days=1),
                        "boundary": mulai,
                        "later": mulai + timedelta(seconds=2),
                    }

                class LaterVisibleSession:
                    inserted = False

                    async def execute(self, statement):
                        if not self.inserted:
                            self.inserted = True
                            # Deterministic interleaving: these rows become visible only
                            # after fetch_operational_facts has captured its clock.
                            session.add_all([
                                Batch(
                                    id=ids[name], location_id=location.id,
                                    commodity_id=commodity.id, supplier_id=supplier.id,
                                    quantity_kg=Decimal("10"), harvested_at=timestamp,
                                    # Bukti suhu lengkap: sejak F-02 (25 Okt 2026) log
                                    # kosong tidak lagi berbuah skor `pass` (0,7), dan
                                    # tes ini menguji pemotongan `as_of`, bukan freshness.
                                    temperature_log=_log_suhu(timestamp),
                                    safety_status="pass",
                                )
                                for name, timestamp in harvested.items()
                            ])
                            session.flush()
                        return session.execute(statement)

                facts = asyncio.run(rs.fetch_operational_facts(
                    LaterVisibleSession(), AS_OF if explicit_as_of else None
                ))
                batches = {b["batch_id"]: b for b in facts[4]}
                assert str(ids["later"]) not in batches
                # Varian jam dinding: `boundary` dibuat 1 menit sebelum jam
                # nyata, jadi skornya menyusut sepersekian (0,999975) — itu
                # decay yang benar, bukan kebocoran data. Yang diuji tetap:
                # batch pada batas IKUT, batch setelah jam evaluasi TIDAK.
                if explicit_as_of:
                    assert batches[str(ids["boundary"])]["freshness_score"] == Decimal("1.000000")
                else:
                    assert batches[str(ids["boundary"])]["freshness_score"] >= Decimal("0.9999")
                # `policy` WAJIB sama dengan yang dipakai jalur produksi
                # (`fetch_operational_facts` memanggil dengan policy=...).
                # Tanpa policy, penalti bukti suhu kosong dihitung berbeda dan
                # selisihnya tepat 0,30 (0,964286 vs 0,664286) — itu cacat
                # kontrak tes, bukan bug skor (terukur 28 Okt 2026).
                from app.core.commodity_policy import policy_for

                expected = rs.compute_freshness_score(
                    harvested["old"], acuan, rs.settings.shelf_life_days_telur,
                    _log_suhu(harvested["old"]),
                    rs.settings.safe_temp_min_c, rs.settings.safe_temp_max_c,
                    policy=policy_for("telur"),
                )
                assert batches[str(ids["old"])]["freshness_score"] == rs._score(
                    Decimal(str(expected))
                )
                assert batches[str(ids["old"])]["safety_status"] == "pass"
            transaction.rollback()
    finally:
        engine.dispose()
