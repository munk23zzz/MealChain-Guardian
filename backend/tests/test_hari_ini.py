"""Satu hari operasional Jakarta: seed + endpoint + apa yang tampil di layar.

Permintaan pemilik (24 Okt 2026): dalam jendela 1 hari harus ada keputusan yang
MENUNGGU PERSETUJUAN (kartu teratas = pengiriman dari pemasok, supaya bisa
didemokan), ada yang SEDANG DIKIRIM (truk bergerak di peta), ada yang SELESAI,
plus jalur gagal (ditolak / lewat tenggat / ditandai verifikator). Angka KPI
harus lahir dari baris-baris itu, bukan ditulis tangan.

Tes ini menulis ke DB demo lewat endpoint — memang begitu kontraknya: seed
idempoten dan Jakarta-sentris, dan "muat ulang hari ini" adalah fitur, bukan
efek samping. Setiap tes memanggil seed lebih dulu supaya tidak bergantung pada
urutan eksekusi.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

try:  # seed/test helpers: tes ini juga berjalan di image backend tanpa paket agent
    from sqlalchemy import text as _text

    from app.core.config import settings as _settings
    from app.db import create_engine as _create_engine
    from app.db import create_session_maker as _maker
except Exception:  # pragma: no cover
    _text = None

JAKARTA = "Jakarta"
STATUS_WAJIB = {"pending_approval", "approved", "executed", "rejected", "verifier_flagged"}


def _muat(client: TestClient, headers: dict) -> dict:
    resp = client.post("/demo/hari-ini", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _jakarta_24_jam(client: TestClient, headers: dict) -> list[dict]:
    resp = client.get("/decisions", params={"window": "24h", "limit": 200}, headers=headers)
    assert resp.status_code == 200, resp.text
    return [r for r in resp.json()["items"] if r.get("target_location_name") == JAKARTA]


def test_endpoint_menolak_peran_monitor(monitor_headers):
    """Monitor hanya membaca; seed mengubah data → harus 403, bukan diam-diam jalan."""
    with TestClient(app) as c:
        resp = c.post("/demo/hari-ini", headers=monitor_headers)
    assert resp.status_code == 403


def test_seed_menulis_sembilan_keputusan(auth_headers):
    with TestClient(app) as c:
        hasil = _muat(c, auth_headers)
    assert hasil["kota"] == JAKARTA
    assert hasil["keputusan"] == 9
    assert hasil["kartu_teratas"]["jenis"] == "supplier_procurement"
    assert hasil["kartu_teratas"]["pemasok"], "kartu teratas wajib punya nama pemasok"


def test_kartu_teratas_adalah_persetujuan_kirim_pemasok(auth_headers):
    """Kartu paling atas = pengadaan dari pemasok yang menunggu persetujuan.

    Urutan feed di layar memakai urgensi, bukan waktu; yang diuji di sini adalah
    data: keputusan terbaru Jakarta adalah pengadaan pemasok yang belum disetujui
    dan nama pemasoknya terisi (baris "Rencana kirim dari pemasok …").
    """
    with TestClient(app) as c:
        hasil = _muat(c, auth_headers)
        baris = _jakarta_24_jam(c, auth_headers)
    # Tes ini berjalan di DB bersama, jadi yang diuji adalah KARTU SEED ITU
    # SENDIRI (id deterministik), bukan "yang paling baru di seluruh tabel" —
    # tes lain boleh menulis keputusan lebih baru tanpa membuat ini merah.
    kartu = [r for r in baris if str(r["decision_id"]) == hasil["kartu_teratas"]["id"]]
    assert kartu, "kartu seed tidak muncul di feed 24 jam"
    kartu = kartu[0]
    assert kartu["decision_type"] == "supplier_procurement"
    assert kartu["status"] == "pending_approval"
    assert kartu["supplier_name"]
    assert kartu["pengirim"] == "pemasok"
    # Tenggatnya paling dekat di antara kartu seed: itulah yang menaruhnya di
    # puncak feed (urutan layar memakai urgensi, bukan waktu dibuat).
    # Yang dibandingkan hanya yang MASIH bisa ditindak (belum lewat tenggat):
    # keputusan kedaluwarsa punya chip sendiri dan tidak ikut urutan urgensi.
    sekarang = datetime.now(timezone.utc)
    tenggat_seed = [
        datetime.fromisoformat(r["expires_at"])
        for r in baris
        if str(r["decision_id"]) in set(hasil["ids"])
        and r["status"] in {"proposed", "pending_approval"}
        and datetime.fromisoformat(r["expires_at"]) > sekarang
    ]
    assert datetime.fromisoformat(kartu["expires_at"]) == min(tenggat_seed)


def test_komposisi_status_untuk_demo(auth_headers):
    """Satu hari harus memuat jalur bahagia DAN jalur gagal."""
    with TestClient(app) as c:
        _muat(c, auth_headers)
        baris = _jakarta_24_jam(c, auth_headers)
    status = {r["status"] for r in baris}
    assert STATUS_WAJIB.issubset(status), f"status yang ada: {sorted(status)}"


def test_ada_yang_lewat_tenggat(auth_headers):
    """Kedaluwarsa bukan status, melainkan `expires_at` yang sudah lewat."""
    with TestClient(app) as c:
        _muat(c, auth_headers)
        baris = _jakarta_24_jam(c, auth_headers)
    sekarang = datetime.now(timezone.utc)
    lewat = [
        r
        for r in baris
        if r["status"] in {"proposed", "pending_approval"}
        and datetime.fromisoformat(r["expires_at"]) < sekarang
    ]
    assert lewat, "butuh satu keputusan yang sudah lewat tenggat untuk chip merah"


def test_kpi_24_jam_tujuh_metrik_tersedia(auth_headers):
    """Angka KPI harus lahir dari baris seed (penerimaan, PO, limbah, bukti)."""
    with TestClient(app) as c:
        _muat(c, auth_headers)
        sekarang = datetime.now(timezone.utc)
        resp = c.get(
            "/kpi",
            params={
                "start": (sekarang - timedelta(hours=24)).isoformat(),
                "end": sekarang.isoformat(),
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200, resp.text
    metrik = resp.json()["metrics"]
    assert len(metrik) == 7
    gelap = [m["name"] for m in metrik if m["state"] != "available"]
    assert not gelap, f"metrik tanpa data: {gelap}"


def test_dua_kiriman_berjalan_dengan_geometri(auth_headers):
    """Truk di peta butuh state `di_jalan` DAN geometri rute — dua-duanya diuji."""
    with TestClient(app) as c:
        _muat(c, auth_headers)
        resp = c.get("/supplier-routes", params={"limit": 200}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    jalan = [r for r in resp.json()["routes"] if r["journey"]["state"] == "di_jalan"]
    assert len(jalan) >= 2, f"hanya {len(jalan)} kiriman berjalan"
    assert all(r["road"] is not None for r in jalan), "kiriman berjalan wajib punya jalur jalan"


def test_seed_idempoten(auth_headers):
    """Menjalankan dua kali tidak boleh menumpuk baris."""
    with TestClient(app) as c:
        _muat(c, auth_headers)
        pertama = len(_jakarta_24_jam(c, auth_headers))
        hasil_kedua = _muat(c, auth_headers)
        kedua = len(_jakarta_24_jam(c, auth_headers))
    assert kedua == pertama
    assert not hasil_kedua["kpi_tertulis"], "putaran kedua tidak boleh menulis kejadian KPI baru"


def test_tombol_siapkan_data_demo_menghasilkan_hari_yang_sama(auth_headers):
    """"Siapkan data demo" (`POST /demo/refresh`) tidak boleh menyisakan 1 kartu.

    Tanpa sambungan ke seed hari-ini, tombol itu menghapus kasus skrip dan
    menggeser baris aksi keluar jendela 24 jam: feed kembali berisi satu kartu
    dan KPI kosong. Kontraknya sekarang: sekali klik = satu hari utuh.
    """
    with TestClient(app) as c:
        resp = c.post("/demo/refresh", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["hari_ini"]["keputusan"] == 9

        baris = _jakarta_24_jam(c, auth_headers)
        assert len(baris) >= 9, f"feed 24 jam hanya {len(baris)} kartu"
        assert STATUS_WAJIB.issubset({r["status"] for r in baris})

        sekarang = datetime.now(timezone.utc)
        kpi = c.get(
            "/kpi",
            params={
                "start": (sekarang - timedelta(hours=24)).isoformat(),
                "end": sekarang.isoformat(),
            },
            headers=auth_headers,
        ).json()["metrics"]
    assert all(m["state"] == "available" for m in kpi), [
        m["name"] for m in kpi if m["state"] != "available"
    ]


def test_data_masuk_akal_jarak_dan_jenis_pemasok():
    """Data demo harus masuk akal secara operasional, bukan sekadar terisi.

    Dua kesalahan nyata yang pernah muncul di layar:
      * "Ganti pasokan 300 kg ayam: Surabaya → Jakarta" (663 km, lintas pulau
        untuk ayam segar);
      * "Pengadaan beras dari CV Barokah Telur Cianjur" (pemasok telur memasok
        beras).
    Tes ini mengunci keduanya.
    """
    import asyncio

    async def skenario():
        engine = _create_engine(_settings.database_url)
        maker = _maker(engine)
        try:
            async with maker() as s:
                jauh = (
                    (
                        await s.execute(
                            _text(
                            """
                            SELECT c.name, sl.name, tl.name,
                                   round((6371 * acos(least(1, greatest(-1,
                                     sin(radians(sl.latitude)) * sin(radians(tl.latitude))
                                     + cos(radians(sl.latitude)) * cos(radians(tl.latitude))
                                       * cos(radians(sl.longitude - tl.longitude))))))::numeric)
                            FROM decisions d
                            JOIN commodities c ON c.id = d.commodity_id
                            JOIN locations sl ON sl.id = d.source_location_id
                            JOIN locations tl ON tl.id = d.target_location_id
                            WHERE d.source_location_id IS NOT NULL
                              AND d.source_location_id <> d.target_location_id
                            """
                        )
                        )
                    ).all()
                )
                salah_komoditas = (
                    (
                        await s.execute(
                            _text(
                            """
                            SELECT b.id, c.name, s.name, sc.name
                            FROM batches b
                            JOIN commodities c ON c.id = b.commodity_id
                            JOIN suppliers s ON s.id = b.supplier_id
                            JOIN commodities sc ON sc.id = s.commodity_id
                            WHERE s.commodity_id <> b.commodity_id
                            """
                        )
                        )
                    ).all()
                )
        finally:
            await engine.dispose()

        terlalu_jauh = [(k, a, t, float(km)) for k, a, t, km in jauh if float(km) > 400]
        assert not terlalu_jauh, f"rute lintas pulau untuk pasokan: {terlalu_jauh}"
        assert not salah_komoditas, f"pemasok salah komoditas: {salah_komoditas}"

    asyncio.run(skenario())
