"""Gerbang endpoint bangun-ulang template demo (21 Okt 2026).

Yang dibuktikan, dari yang paling murah ke paling mahal:

1. Kunci proses: permintaan kedua saat bangun-ulang masih berjalan ditolak
   `SibukError` — tidak diantrikan sampai klien kehabisan waktu.
2. Argumen penyemai: `purge=True`, `freeze=True`, `bersihkan_sisa=False`.
   Tanpa `freeze` baris template ikut ber-stempel dan bisa terhapus; tanpa
   `purge` sisa aksi geladi sebelumnya menumpuk.
3. HTTP: hanya kepala SPPG (403 untuk peran lain) dan 409 saat sibuk.
   Kedua jalur ini TIDAK menyentuh data, jadi aman dijalankan di DB bersama.

Catatan gerbang: tes ini sengaja tidak pernah menjalankan build sungguhan —
bangun ulang mem-purge seluruh baris operasional, dan itu tugas yang hanya
boleh terjadi saat operator memang memintanya.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.services import demo_template_reset as reset
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL
from tests.test_actions import _login, _mk_user

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")


def _hapus_user(user_id: str) -> None:
    engine = create_engine(DB_URL, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id = :i"), {"i": user_id})
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_tolak_saat_kunci_dipegang():
    async def skenario() -> str:
        await reset._KUNCI.acquire()
        try:
            with pytest.raises(reset.SibukError):
                await reset.bangun_ulang(db=None)  # type: ignore[arg-type]
        finally:
            reset._KUNCI.release()
        return "ok"

    assert asyncio.run(skenario()) == "ok"


def test_memanggil_penyemai_dengan_opsi_yang_benar(monkeypatch):
    dipanggil: dict = {}

    async def build_palsu(db, *, purge, freeze, bersihkan_sisa, mode=None, anchor=None):
        # `mode`/`anchor` (Fase 7 MG) diteruskan pembangun template; palsu ini
        # mencatatnya supaya perubahan kontrak pemanggil tetap terlihat.
        dipanggil.update(
            {
                "purge": purge,
                "freeze": freeze,
                "bersihkan_sisa": bersihkan_sisa,
                "mode": mode,
                "anchor": anchor,
            }
        )
        return {"hitung": {"batches": 121, "decisions": 27}, "kasus": {}, "bukti": {}}

    class _HasilKosong:
        """Hasil query kosong: cukup untuk pembacaan "sesi aktif terakhir"."""

        def scalar_one_or_none(self):
            return None

        def scalars(self):
            return self

        def all(self):
            return []

        def first(self):
            return None

    class DbPalsu:
        # 27 Okt 2026: `_sesi_aktif_terakhir()` (dipakai saat menyemai template)
        # memanggil `db.execute(select(...))`. DB palsu tanpa `execute` membuat
        # tes ini gagal dengan AttributeError padahal alurnya benar — jadi
        # pembacaan dipenuhi dengan hasil kosong, bukan dengan menambal kode.
        async def execute(self, *args, **kwargs):
            return _HasilKosong()

        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def sesi_palsu(db):
        return None

    # 22 Okt 2026: sesudah template, bangun ulang juga mengisi deret waktu,
    # aktivitas, dan pelengkap cakupan — kalau tidak, tombol "Siapkan data demo"
    # meninggalkan grafik kosong (supply 5.200 -> 40). Ketiga langkah dipalsukan
    # di sini, dan tes memastikan ketiganya benar-benar dipanggil: tanpa asersi
    # ini, menghapus salah satunya tidak akan ketahuan.
    dilengkapi: dict = {}

    async def deret_palsu():
        dilengkapi["deret"] = True
        return {"counts": {"supply": 5200}}

    async def aktivitas_palsu(db, sekarang):
        dilengkapi["aktivitas"] = True
        return {"aktivitas": {}, "keputusan_selesai": {}, "harga_harian": {}}

    async def cakupan_palsu(db, sekarang):
        dilengkapi["pelengkap"] = True
        return {"decisions": 10}

    monkeypatch.setattr(reset, "pastikan_sesi", sesi_palsu)
    monkeypatch.setattr(reset, "build_into", build_palsu)
    monkeypatch.setattr(reset, "_bangun_deret", deret_palsu)
    monkeypatch.setattr(reset, "_lengkapi_aktivitas", aktivitas_palsu)
    monkeypatch.setattr(reset, "_lengkapi_cakupan", cakupan_palsu)

    # 26 Okt 2026 (F7): laporan dibaca ULANG sesudah semua langkah, jadi `hitung`
    # dipanggil dengan DB sungguhan. Tes unit ini memakai DB palsu yang tidak
    # punya `execute`, jadi hitung-nya ikut dipalsukan.
    async def hitung_palsu(db):
        return {"batches": 121, "decisions": 48}

    monkeypatch.setattr(reset, "hitung", hitung_palsu)

    async def skenario() -> dict:
        return await reset.bangun_ulang(DbPalsu())  # type: ignore[arg-type]

    hasil = asyncio.run(skenario())
    assert dipanggil == {
        "purge": True,
        "freeze": True,
        "bersihkan_sisa": False,
        # Tanpa sesi aktif, mode/jangkar memang tidak diisi.
        "mode": None,
        "anchor": None,
    }
    assert dilengkapi == {"deret": True, "aktivitas": True, "pelengkap": True}
    assert hasil["hitung"]["batches"] == 121
    assert hasil["hitung"]["decisions"] == 48  # dibaca sesudah langkah pelengkap
    assert hasil["pelengkap"] == {"decisions": 10}
    assert "durasi_detik" in hasil


def test_hanya_kepala_yang_boleh_dan_sibuk_ditolak_409(client):
    gizi = _mk_user("sppg_nutritionist", "Jakarta")
    kepala = _mk_user("sppg_head", "Jakarta")
    try:
        header_gizi = _login(client, gizi)
        header_kepala = _login(client, kepala)

        r = client.post("/demo/template/rebuild", headers=header_gizi)
        assert r.status_code == 403, r.text

        async def tahan_kunci() -> None:
            await reset._KUNCI.acquire()

        asyncio.run(tahan_kunci())
        try:
            r = client.post("/demo/template/rebuild", headers=header_kepala)
        finally:
            reset._KUNCI.release()
        assert r.status_code == 409, r.text
        assert "sedang berjalan" in r.json()["detail"]
    finally:
        _hapus_user(gizi["id"])
        _hapus_user(kepala["id"])

def test_pengguna_lokasi_mengabaikan_akun_uji():
    """Regresi 21 Okt 2026: 12 akun `sppg_head-*@test.local` sisa suite di Jakarta
    membuat `scalar_one_or_none()` melempar MultipleResultsFound dan MEMATIKAN
    seluruh bangun-ulang. Penyemai harus tahan terhadap akun uji.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.seed.demo_template import _pengguna_lokasi

    # Sengaja berawalan "a-" supaya URUTAN email menaruhnya di depan akun demo.
    # Tanpa filter @test.local, urutan itu yang membuat akun uji terpilih — jadi
    # tes ini benar-benar memaku filternya, bukan hanya "tidak melempar galat".
    email = f"a-{uuid.uuid4().hex[:8]}@test.local"

    async def skenario():
        eng = create_async_engine(settings.database_url)
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as db:
                lokasi = (
                    await db.execute(text("SELECT id FROM locations WHERE name = 'Jakarta'"))
                ).scalar_one()
                try:
                    await db.execute(
                        text(
                            "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                            "VALUES (:i, 'Uji', :e, 'x', 'sppg_head', :l)"
                        ),
                        {"i": str(uuid.uuid4()), "e": email, "l": str(lokasi)},
                    )
                    await db.commit()
                    hasil = await _pengguna_lokasi(db, lokasi, "sppg_head")
                finally:
                    await db.execute(
                        text("DELETE FROM users WHERE email = :e"), {"e": email}
                    )
                    await db.commit()
            return hasil
        finally:
            await eng.dispose()

    user = asyncio.run(skenario())
    assert user is not None
    assert not user.email.endswith("@test.local")

def test_boot_hanya_membersihkan_baris_berstempel(monkeypatch):
    """Regresi 21 Okt 2026: pembersihan saat boot memakai `bersihkan_warisan()`
    yang menghapus SELURUH baris operasional. Setiap restart backend tanpa sesi
    aktif memusnahkan template demo (terukur: 121 batch -> 0). Boot hanya boleh
    menyentuh baris ber-stempel; tampilan tetap kosong karena UI menyembunyikan
    data saat tidak ada sesi.
    """
    from app.api import dependencies as dep
    from app.core.config import settings
    from app.services import demo_session as ds

    monkeypatch.setattr(settings, "demo_session_enforce", True, raising=False)
    dipanggil: list[str] = []

    async def aktif_palsu(db):
        return None

    async def bertanda_palsu(db):
        dipanggil.append("bertanda")
        return 3

    async def warisan_palsu(db):
        dipanggil.append("warisan")
        return 999

    monkeypatch.setattr(ds, "aktif", aktif_palsu)
    monkeypatch.setattr(ds, "kosongkan_bertanda", bertanda_palsu)
    monkeypatch.setattr(ds, "bersihkan_warisan", warisan_palsu)

    class DbPalsu:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class MakerPalsu:
        def __call__(self):
            return DbPalsu()

    asyncio.run(dep._kosongkan_bila_tanpa_sesi(MakerPalsu()))
    assert dipanggil == ["bertanda"]

def test_pastikan_sesi_membuat_sesi_bila_tidak_ada(monkeypatch):
    """Regresi 21 Okt 2026: build berakhir 0 batch karena penyapu di proses
    aplikasi menghapus baris `origin='demo'` yang belum dibekukan. Penjagaannya
    adalah sesi aktif, jadi `pastikan_sesi` wajib memulai sesi bila belum ada —
    dan TIDAK memulai sesi kedua bila sudah ada.
    """
    from app.seed import demo_template as dt

    dipanggil: list[str] = []

    class SesiPalsu:
        id = "sesi-uji"

    async def aktif_ada(db):
        dipanggil.append("aktif")
        return SesiPalsu()

    async def mulai(db, created_by=None):
        dipanggil.append("mulai")
        return SesiPalsu()

    monkeypatch.setattr(dt.sesi, "aktif", aktif_ada)
    monkeypatch.setattr(dt.sesi, "mulai", mulai)

    hasil = asyncio.run(dt.pastikan_sesi(db=None))
    assert hasil.id == "sesi-uji"
    assert dipanggil == ["aktif"]

    dipanggil.clear()

    async def aktif_tidak_ada(db):
        dipanggil.append("aktif")
        return None

    async def lokasi_palsu(db, nama):
        return None

    monkeypatch.setattr(dt.sesi, "aktif", aktif_tidak_ada)
    monkeypatch.setattr(dt, "_lokasi", lokasi_palsu)

    hasil = asyncio.run(dt.pastikan_sesi(db=None))
    assert hasil.id == "sesi-uji"
    assert dipanggil == ["aktif", "mulai"]

def test_boot_mode_dev_tidak_menyentuh_data(monkeypatch):
    """Pelajaran 21 Okt 2026: saat `DEMO_SESSION_ENFORCE` mati, boot TIDAK boleh
    membersihkan apa pun. Versi yang memanggil `bersihkan_warisan` di jalur ini
    menghapus seluruh data kanonik pada boot TestClient pertama, dan 47 tes gagal
    karena kehabisan baris (bukan karena logika produk).
    """
    from app.api import dependencies as dep
    from app.core.config import settings
    from app.services import demo_session as ds

    monkeypatch.setattr(settings, "demo_session_enforce", False, raising=False)
    dipanggil: list[str] = []

    async def bertanda_palsu(db):
        dipanggil.append("bertanda")
        return 1

    async def warisan_palsu(db):
        dipanggil.append("warisan")
        return 999

    monkeypatch.setattr(ds, "kosongkan_bertanda", bertanda_palsu)
    monkeypatch.setattr(ds, "bersihkan_warisan", warisan_palsu)

    class MakerPalsu:
        def __call__(self):  # pragma: no cover - tidak boleh dipanggil
            raise AssertionError("maker tidak boleh dipakai saat flag mati")

    asyncio.run(dep._kosongkan_bila_tanpa_sesi(MakerPalsu()))
    assert dipanggil == []
