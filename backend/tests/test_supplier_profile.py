"""Profil pemasok kanonik DITURUNKAN dari batch kiriman (keputusan pemilik 2026-10-16).

Latar: 14 pemasok kanonik di `data/seed/sprint1_seed.json` hanya punya
nama/lokasi/skor keandalan, sehingga `commodity_id`, `certification_status`, dan
`capacity_kg_per_week` mereka NULL di DB. Akibatnya tab Pemasok menampilkan baris
dengan Komoditas/Sertifikasi kosong dan pemasok itu tidak bisa tersaring per
komoditas di peta.

Aturan penurunan (disetujui pemilik, hanya dari data yang SUDAH ada):

- `commodity` = komoditas dengan TOTAL `quantity_kg` terbesar di antara batch
  pemasok itu; bila seri -> komoditas batch TERBARU (`harvested_at_offset_hours`
  terbesar); bila masih seri -> `None` (TIDAK ditebak).
- `certification_status` = nilai sertifikasi batch pemasok itu bila seragam;
  bila beragam -> nilai terbanyak; bila seri -> `None` (TIDAK ditebak).
- `capacity_kg_per_week` TIDAK diturunkan: tidak ada satu pun sumber datanya
  (batch hanya memuat berat per kiriman, bukan kapasitas mingguan).
- Pemasok tanpa batch -> `(None, None)`; nama pemasok pada batch yang tidak ada
  di daftar pemasok diabaikan (bukan galat di sini - validasi ada di seed).

Kontrak ini yang mengisi profil kanonik di DB, jadi tes ini adalah pengunci
kejujurannya: nilai kosong tetap kosong.
"""

from datetime import UTC, datetime

from app.seed.seed_data import build_seed_rows
from app.seed.supplier_profile import derive_supplier_profiles

SUPPLIERS = [
    "Koperasi Telur Cipanas Bersama",
    "UD H. Asep Cianjur",
    "UD Cipanas Telur Sejahtera",
    "CV Barokah Telur Cianjur",
    "Supplier Medan-1",
]


def test_pemasok_tanpa_batch_tidak_dikarang() -> None:
    """Tanpa batch, tidak ada dasar apa pun -> kedua nilai None (bukan default)."""
    profiles = derive_supplier_profiles([], SUPPLIERS)

    assert profiles["CV Barokah Telur Cianjur"] == {
        "commodity": None,
        "certification_status": None,
    }
    assert profiles["Supplier Medan-1"]["commodity"] is None


def test_komoditas_dari_total_kuantitas_terbesar() -> None:
    """A Cianjur: 3 batch telur -> telur, sertifikasi seragam haccp."""
    batches = [
        {"supplier": "Koperasi Telur Cipanas Bersama", "commodity": "telur", "quantity_kg": 500,
         "harvested_at_offset_hours": -18, "certification_status": "haccp"},
        {"supplier": "Koperasi Telur Cipanas Bersama", "commodity": "telur", "quantity_kg": 500,
         "harvested_at_offset_hours": -60, "certification_status": "haccp"},
        {"supplier": "Koperasi Telur Cipanas Bersama", "commodity": "telur", "quantity_kg": 400,
         "harvested_at_offset_hours": -100, "certification_status": "haccp"},
    ]
    profile = derive_supplier_profiles(batches, SUPPLIERS)["Koperasi Telur Cipanas Bersama"]

    assert profile == {"commodity": "telur", "certification_status": "haccp"}


def test_kuantitas_menang_atas_jumlah_batch() -> None:
    """B Cianjur: 1 batch telur 600 kg mengalahkan 1 batch ayam 200 kg."""
    batches = [
        {"supplier": "UD H. Asep Cianjur", "commodity": "telur", "quantity_kg": 600,
         "harvested_at_offset_hours": -18, "certification_status": "haccp"},
        {"supplier": "UD H. Asep Cianjur", "commodity": "ayam", "quantity_kg": 200,
         "harvested_at_offset_hours": -40, "certification_status": "haccp"},
    ]
    profile = derive_supplier_profiles(batches, SUPPLIERS)["UD H. Asep Cianjur"]

    assert profile["commodity"] == "telur"


def test_seri_kuantitas_dimenangkan_batch_terbaru() -> None:
    """Seri 300 vs 300 kg -> komoditas batch yang paling baru dipanen."""
    batches = [
        {"supplier": "CV Barokah Telur Cianjur", "commodity": "ayam", "quantity_kg": 300,
         "harvested_at_offset_hours": -90, "certification_status": "haccp"},
        {"supplier": "CV Barokah Telur Cianjur", "commodity": "telur", "quantity_kg": 300,
         "harvested_at_offset_hours": -5, "certification_status": "haccp"},
    ]
    profile = derive_supplier_profiles(batches, SUPPLIERS)["CV Barokah Telur Cianjur"]

    assert profile["commodity"] == "telur"


def test_seri_penuh_tidak_ditebak() -> None:
    """Seri kuantitas dan umur batch sama -> None, bukan pilihan sepihak."""
    batches = [
        {"supplier": "CV Barokah Telur Cianjur", "commodity": "ayam", "quantity_kg": 300,
         "harvested_at_offset_hours": -10, "certification_status": None},
        {"supplier": "CV Barokah Telur Cianjur", "commodity": "telur", "quantity_kg": 300,
         "harvested_at_offset_hours": -10, "certification_status": None},
    ]
    profile = derive_supplier_profiles(batches, SUPPLIERS)["CV Barokah Telur Cianjur"]

    assert profile["commodity"] is None


def test_sertifikasi_campuran_pakai_yang_terbanyak() -> None:
    """haccp 1 batch, hygiene 2 batch -> hygiene; sertifikasi kosong diabaikan."""
    batches = [
        {"supplier": "UD Cipanas Telur Sejahtera", "commodity": "telur", "quantity_kg": 100,
         "harvested_at_offset_hours": -1, "certification_status": "haccp"},
        {"supplier": "UD Cipanas Telur Sejahtera", "commodity": "telur", "quantity_kg": 100,
         "harvested_at_offset_hours": -2, "certification_status": "hygiene"},
        {"supplier": "UD Cipanas Telur Sejahtera", "commodity": "telur", "quantity_kg": 100,
         "harvested_at_offset_hours": -3, "certification_status": "hygiene"},
        {"supplier": "UD Cipanas Telur Sejahtera", "commodity": "telur", "quantity_kg": 100,
         "harvested_at_offset_hours": -4, "certification_status": None},
    ]
    profile = derive_supplier_profiles(batches, SUPPLIERS)["UD Cipanas Telur Sejahtera"]

    assert profile["certification_status"] == "hygiene"


def test_sertifikasi_seri_tidak_ditebak() -> None:
    """haccp 1 vs hygiene 1 -> None."""
    batches = [
        {"supplier": "UD Cipanas Telur Sejahtera", "commodity": "telur", "quantity_kg": 100,
         "harvested_at_offset_hours": -1, "certification_status": "haccp"},
        {"supplier": "UD Cipanas Telur Sejahtera", "commodity": "telur", "quantity_kg": 100,
         "harvested_at_offset_hours": -2, "certification_status": "hygiene"},
    ]
    profile = derive_supplier_profiles(batches, SUPPLIERS)["UD Cipanas Telur Sejahtera"]

    assert profile["certification_status"] is None


def test_kapasitas_tidak_diturunkan() -> None:
    """Kapasitas mingguan tidak punya sumber data -> kuncinya tidak ada sama sekali."""
    batches = [
        {"supplier": "Koperasi Telur Cipanas Bersama", "commodity": "telur", "quantity_kg": 500,
         "harvested_at_offset_hours": -18, "certification_status": "haccp"},
    ]
    profile = derive_supplier_profiles(batches, SUPPLIERS)["Koperasi Telur Cipanas Bersama"]

    assert "capacity_kg_per_week" not in profile
    assert set(profile) == {"commodity", "certification_status"}


def test_nama_pemasok_asing_diabaikan() -> None:
    """Batch yang menyebut pemasok di luar daftar tidak menambah/mengganggu baris."""
    batches = [
        {"supplier": "Supplier Tidak Dikenal", "commodity": "telur", "quantity_kg": 900,
         "harvested_at_offset_hours": -1, "certification_status": "haccp"},
    ]
    profiles = derive_supplier_profiles(batches, SUPPLIERS)

    assert set(profiles) == set(SUPPLIERS)
    assert profiles["Koperasi Telur Cipanas Bersama"]["commodity"] is None


# ---------------------------------------------------------------------------
# Sambungan ke seed kanonik: baris yang dibangun seeder wajib memuat hasil
# turunan, dan pemasok yang tidak punya batch wajib TETAP kosong (bukan default).
# ---------------------------------------------------------------------------

CANONICAL_REF = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)


def _canonical_suppliers() -> dict[str, dict]:
    return {row["name"]: row for row in build_seed_rows(CANONICAL_REF)["suppliers"]}


def test_seed_kanonik_mengisi_profil_dari_batch() -> None:
    """A/B/C Cianjur punya batch -> komoditas & sertifikasi terisi dari kiriman."""
    rows = _canonical_suppliers()

    assert rows["Koperasi Telur Cipanas Bersama"]["commodity"] == "telur"
    assert rows["Koperasi Telur Cipanas Bersama"]["certification_status"] == "haccp"
    assert rows["UD H. Asep Cianjur"]["commodity"] == "telur"
    # Pemasok yang kirimannya hanya telur juga terisi; yang TIDAK punya batch
    # tetap kosong (diuji tes berikutnya), jadi nama di sini harus yang ber-batch.
    assert rows["UD Blitar Telur Makmur"]["commodity"] == "telur"


def test_seed_pemasok_tanpa_batch_tetap_kosong() -> None:
    """Pemasok kanonik tanpa batch tidak boleh mendapat nilai tebakan.

    Daftarnya DITURUNKAN dari data kanonik, bukan dipaku: sejak Fase 10 Supplier
    D Cianjur punya batch telur → Jakarta, jadi menyebutnya "tanpa batch" membuat
    tes merah padahal seed-nya benar. Yang diuji adalah aturannya: bila sebuah
    pemasok tidak punya batch, profilnya tidak diisi tebakan.
    """
    rows = _canonical_suppliers()
    punya_batch = {
        batch["supplier"] for batch in build_seed_rows(CANONICAL_REF)["batches"]
    }
    tanpa_batch = [name for name in rows if name not in punya_batch]
    assert tanpa_batch, "seed harus punya pemasok tanpa batch untuk menguji aturan ini"

    for name in tanpa_batch:
        assert rows[name]["commodity"] is None, name
        assert rows[name]["certification_status"] is None, name


def test_seed_tidak_menambah_kapasitas_karangan() -> None:
    """Kapasitas mingguan tidak punya sumber -> tidak boleh muncul di baris seed."""
    rows = _canonical_suppliers()

    for name, row in rows.items():
        assert "capacity_kg_per_week" not in row, name

