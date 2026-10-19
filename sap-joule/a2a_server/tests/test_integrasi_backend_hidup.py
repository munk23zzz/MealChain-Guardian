"""Bukti nyata: klien jembatan vs backend MealChain yang HIDUP (bukan FakeClient).

Tes unit memakai `FakeClient`, jadi kontrak HTTP bisa rusak tanpa satu tes pun gagal
(pelajaran yang sudah tercatat di skill: "tes klien palsu tidak melindungi protokol").
Tes ini menembak backend sungguhan dan **skip** bila backend/kredensial tidak tersedia,
supaya `pytest` tetap hijau di mesin tanpa stack demo.

Cara menjalankan (stack demo hidup):

    MEALCHAIN_API_URL=http://localhost:8000 \
    MEALCHAIN_READ_USERNAME=bgn.monitor@demo.local \
    MEALCHAIN_READ_PASSWORD='<password demo>' \
    .venv/Scripts/python.exe -m pytest a2a_server/tests/test_integrasi_backend_hidup.py -q
"""

from __future__ import annotations

import os

import pytest

from mealchain_client import MealchainClient, MealchainUnavailable

API_URL = os.environ.get("MEALCHAIN_API_URL", "http://localhost:8000")
USERNAME = os.environ.get("MEALCHAIN_READ_USERNAME", "")
PASSWORD = os.environ.get("MEALCHAIN_READ_PASSWORD", "")


@pytest.fixture(scope="module")
def klien():
    if not (USERNAME and PASSWORD):
        pytest.skip("MEALCHAIN_READ_USERNAME/PASSWORD tidak diisi — tes integrasi dilewati")
    with MealchainClient(API_URL, USERNAME, PASSWORD, timeout=20.0) as c:
        try:
            sehat = c.health()
        except MealchainUnavailable as galat:  # backend mati / URL salah
            pytest.skip(f"backend {API_URL} tidak terjangkau: {galat}")
        if sehat.get("status") != "healthy":
            pytest.skip(f"backend {API_URL} tidak sehat: {sehat}")
        yield c


def test_batches_terbaca_dan_berbentuk_kontrak(klien):
    baris = klien.batches()
    assert baris, "backend sehat tetapi /batches kosong — seed belum dijalankan?"
    contoh = baris[0]
    for kunci in ("location", "commodity"):
        assert kunci in contoh, f"/batches tidak lagi memuat '{kunci}': {sorted(contoh)}"


def test_balance_map_memuat_supply_dan_demand(klien):
    # Komoditas TIDAK di-hardcode: DB demo memakai telur/ayam/wortel, dan daftarnya bisa
    # berubah saat seed diperbarui. Ambil dari /batches supaya tes mengikuti kenyataan.
    baris = klien.batches()
    komoditas = next(
        (str(b["commodity"]) for b in baris if b.get("commodity")),
        "telur",
    )
    peta = klien.balance_map(komoditas)
    assert peta, f"/balance/map kosong untuk {komoditas}"
    lokasi = peta.get("locations") or []
    assert lokasi, f"/balance/map tidak memuat 'locations' untuk {komoditas}"
    contoh = lokasi[0]
    assert "demand_kg" in contoh, sorted(contoh)
    assert [k for k in contoh if k.startswith("supply")], sorted(contoh)


def test_kpi_mengembalikan_metrik_beralasan(klien):
    amplop = klien.kpi()
    metrik = amplop.get("metrics") or []
    assert metrik, "/kpi tidak mengembalikan metrik"
    for m in metrik:
        assert "name" in m and "state" in m
        if m["state"] not in ("available", "ok"):
            assert m.get("reason"), f"metrik {m['name']} tidak menyebut alasan saat {m['state']}"


def test_antrean_keputusan_dan_ringkasannya_terbaca(klien):
    antrean = klien.pending_decisions()
    if not antrean:
        pytest.skip("antrean kosong — tidak ada keputusan tertunda untuk diperiksa")
    pertama = antrean[0]
    # Bentuk ternormalisasi jembatan: id/status selalu ada; asal-tujuan boleh None
    # (klien sengaja tidak mengarangnya saat ringkasan gagal).
    assert pertama.get("id") and pertama.get("status")
    ringkas = klien.approval_summary(pertama["id"])
    assert "commodity" in ringkas or "blocking_reasons" in ringkas, sorted(ringkas)[:8]


def test_tidak_ada_jalan_tulis_di_klien():
    """Akun baca-saja + klien tanpa metode tulis = dua lapis penjagaan."""
    metode = {nama for nama in dir(MealchainClient) if not nama.startswith("_")}
    terlarang = {"approve", "execute", "propose", "post", "put", "patch", "delete", "create"}
    assert not (metode & terlarang), f"klien punya jalan tulis: {sorted(metode & terlarang)}"


def test_purchase_orders_terbaca_dari_backend_hidup(klien):
    """PO nyata dari tabel mock SAP: nomor ada, jumlah > 0, dan total konsisten.

    Konsistensi `total = harga x jumlah` diperiksa DI TES (bukan di jembatan): jembatan hanya
    menampilkan `totalValue` dari backend, jadi kalau backend suatu saat mengirim total yang
    tidak cocok dengan kolomnya, tes inilah yang menangkapnya.
    """
    rows = klien.purchase_orders(limit=50)

    assert rows, "tabel mock SAP kosong — seeder demo belum dijalankan?"
    for row in rows[:5]:
        assert str(row.get("poNumber") or "").strip(), "PO tanpa nomor tidak boleh tampil"
        assert float(row["quantityKg"]) > 0
        assert abs(float(row["totalValue"]) - float(row["pricePerKg"]) * float(row["quantityKg"])) < 0.01
    assert any(row.get("decisionId") for row in rows), (
        "PO demo harus punya asal keputusan; kalau tidak, klaim 'PO terbit dari eksekusi' kosong"
    )
    # Asal baris disebut eksplisit — PO impor SAP tidak boleh tampil seolah dari eksekusi.
    assert {row.get("origin") for row in rows} <= {"execution", "demo"}
