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


# --- read model baru: bukti bahwa jembatan benar-benar bisa membaca SEMUA domain ----------


def _pasangan(klien) -> tuple[str, str, str, str]:
    """Satu (location_id, location, commodity) nyata dari inventaris — bukan hardcode."""
    baris = klien.batches()
    contoh = next(
        b for b in baris if b.get("location_id") and b.get("commodity")
    )
    return (
        str(contoh["location_id"]),
        str(contoh["location"]),
        str(contoh["commodity"]),
        str(contoh.get("id") or ""),
    )


def test_batches_memuat_seluruh_inventaris(klien):
    """Batas 50 di backend dulu memotong inventaris; sekarang plafon 500 = semua baris."""
    baris = klien.batches()
    assert len(baris) > 50, (
        "kurang dari 51 batch terbaca — batas 50 di /batches mungkin kembali tertanam di kode"
    )


def test_harga_dan_kuotasi_per_pasangan(klien):
    lokasi_id, lokasi, komoditas, _ = _pasangan(klien)
    harga = klien.price(lokasi_id, komoditas)
    assert harga.get("price_per_kg") is not None, f"harga {lokasi}/{komoditas} kosong: {harga}"
    assert harga.get("location") == lokasi
    kuotasi = klien.price_quotes(lokasi_id, komoditas)
    assert kuotasi.get("quotes"), f"kuotasi {lokasi}/{komoditas} kosong"
    assert "supplier_name" in kuotasi["quotes"][0]


def test_kebutuhan_dan_prakiraan_per_pasangan(klien):
    lokasi_id, _, komoditas, _ = _pasangan(klien)
    kebutuhan = klien.demand(lokasi_id, komoditas)
    assert kebutuhan.get("quantity_kg") is not None
    prakiraan = klien.demand_forecast(lokasi_id, komoditas)
    assert prakiraan.get("forecast_qty_kg") is not None
    assert prakiraan.get("method"), "metode prakiraan harus disebut backend"


def test_pasokan_baris_terakhir_per_pasangan(klien):
    lokasi_id, _, komoditas, _ = _pasangan(klien)
    titik = klien.supply_point(lokasi_id, komoditas)
    assert titik.get("quantity_kg") is not None
    assert titik.get("source"), "sumber baris pasokan harus disebut (mock vs nyata)"


def test_limbah_menyebut_tiga_angka_terpisah(klien):
    ringkas = klien.waste_summary()
    for kunci in ("recorded", "diverted", "unassigned"):
        assert kunci in ringkas, f"/waste/summary tidak memuat {kunci}: {sorted(ringkas)}"


def test_eksklusi_dan_rute_pemasok_terbaca(klien):
    eksklusi = klien.supplier_exclusions()
    assert isinstance(eksklusi, list)
    rute = klien.supplier_routes(limit=50)
    assert rute["routes"], "tidak ada kiriman aktif — seed belum dijalankan?"
    contoh = rute["routes"][0]
    assert contoh.get("supplierName") and contoh.get("destinationName")
    assert "geometry" not in str(rute), "polylines tidak boleh ikut ke teks chat"


def test_bukti_dan_jejak_keputusan_terbaca(klien):
    baris = klien.decisions()
    if not baris:
        pytest.skip("belum ada keputusan di DB demo")
    decision_id = str(baris[0]["decision_id"])
    compliance = klien.decision_compliance(decision_id)
    assert compliance.get("signature"), f"keputusan {decision_id} tanpa tanda tangan"
    assert (compliance.get("signature") or {}).get("state")
    assert "verify" in compliance
    rantai = klien.decision_chain(decision_id)
    assert rantai.get("chain"), "rantai iterasi kosong"
    jejak = klien.decision_traces(decision_id)
    assert "steps" in jejak


def test_integrasi_ledger_dan_ringkasan_po_terbaca(klien):
    integrasi = klien.integrations_status()
    assert integrasi.get("components"), "/integrations/status tanpa komponen"
    ledger = klien.ledger_verify()
    assert ledger.get("valid") is not None and ledger.get("blocks") is not None
    ringkas = klien.po_summary()
    assert ringkas.get("count") is not None
    assert ringkas.get("total_value") is not None


def test_receipts_terbaca_untuk_satu_batch(klien):
    """`/receipts` mewajibkan batch_id; jembatan hanya bisa mencari per batch."""
    baris = klien.batches()
    for batch in baris[:20]:
        try:
            catatan = klien.receipts(str(batch["id"]))
        except Exception:  # batch tanpa penerimaan dijawab 404 oleh backend
            continue
        assert isinstance(catatan, list)
        return
    pytest.skip("tidak ada batch dengan penerimaan barang di DB demo")
