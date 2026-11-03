"""Mesin skor ceklis penerimaan barang (Dok 05 §3–§4, §6).

Kenapa ada modul ini: sampai 29 Okt 2026 ceklis penerimaan hanya berisi lima
kotak centang boolean. Itu bisa menjawab "diperiksa atau tidak", tetapi tidak
bisa menjawab **seberapa layak** kiriman itu, dan tidak ada angka yang bisa
dibandingkan antar-kiriman atau dipakai memutuskan. Dok 05 §3 menetapkan tujuh
butir berbobot yang jumlah bobotnya 100, dan §4 menetapkan urutan aturan
putusan. Modul ini menegakkan keduanya di SERVER: layar tidak pernah menghitung
skor sendiri (kalau dihitung di layar, dua peramban bisa menampilkan putusan
berbeda untuk jawaban yang sama).

Aturan yang dipegang, satu per satu:

1. **Bobot total 100.** Jumlah poin = nilai akhir, tanpa pembagian tambahan.
2. **`poin = bobot × faktor / 100`, dibulatkan HALF_UP** ke bilangan bulat
   (12,5 → 13, bukan 12). Pembulatan bank tidak dipakai.
3. **Urutan aturan putusan tidak boleh ditukar** (§4): kritis/nol dulu, lalu
   ambang nilai, lalu butir "perlu cek", lalu syarat 95% berat. Aturan yang
   lebih awal menang, jadi nilai tinggi tidak bisa menutupi barang kritis.
4. **Butir "kesesuaian jumlah" TIDAK dijawab manual.** Ia diturunkan dari berat
   yang benar-benar ditimbang (§5.1) — kalau petugas boleh menjawabnya sendiri,
   timbangan dan jawaban bisa bercerita berbeda dan nilai rupiahnya jadi kabur.
5. **Versi ceklis disimpan** (`CHECKLIST_VERSION`) supaya jawaban lama tetap
   terbaca dengan rumus yang berlaku saat itu (§4 paragraf terakhir).

Yang sengaja TIDAK ada di sini: foto bukti (§8.4) dan `acceptance_advice` yang
dihitung dari riwayat pemasok. Keduanya butuh kolom/tabel baru; §7 hanya menuntut
kalimat alasan untuk rentang 65–85, dan itu dibuat di `saran()` dari angka yang
memang sudah ada.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.commodity_limits import cold_chain_required, safe_temp_for

__all__ = [
    "BUTIR",
    "NAMA_PUTUSAN",
    "CHECKLIST_VERSION",
    "AMBANG",
    "HasilSkor",
    "butir_by_kunci",
    "checklist_untuk",
    "opsi_jumlah",
    "putusan",
    "saran",
    "skor",
    "validasi_berat",
]

#: Versi daftar butir & bobot. Disimpan di setiap baris penerimaan (§4).
CHECKLIST_VERSION = "2026-10-29.v1"

#: Ambang putusan (§4). Disimpan juga di kode supaya satu sumber.
AMBANG = {
    "fail_max_score": 65,  # nilai < 65 → fail
    "ambiguous_max_score": 85,  # nilai ≤ 85 → needs_verification
    "accepted_ratio_min": 95,  # < 95% berat pesanan → turun ke needs_verification
    "berat_lebih_maks_persen": 110,  # toleransi timbangan lebih
}


@dataclass(frozen=True)
class Opsi:
    """Satu pilihan jawaban untuk satu butir."""

    kunci: str
    label: str
    #: Persentase mutu: 100 = sesuai sepenuhnya, 0 = tidak boleh dipakai.
    faktor: int
    #: Faktor 0 → putusan langsung `fail`, apa pun butir lainnya (§4 aturan 1).
    kritis: bool = False
    #: Menandai butir yang wajib diverifikasi manusia (§4 aturan 3).
    perlu_cek: bool = False


@dataclass(frozen=True)
class Butir:
    kunci: str
    label: str
    bobot: int
    opsi: tuple[Opsi, ...]
    #: Butir ini dijawab dari timbangan, bukan dari pilihan petugas.
    dari_timbangan: bool = False

    def opsi_by_kunci(self, kunci: str) -> Opsi:
        for item in self.opsi:
            if item.kunci == kunci:
                return item
        raise KeyError(f"pilihan '{kunci}' tidak ada untuk butir '{self.kunci}'")


#: Tujuh butir, bobot total 100 — persis tabel Dok 05 §3.
BUTIR: tuple[Butir, ...] = (
    Butir(
        "suhu",
        "Suhu barang saat tiba",
        25,
        (
            Opsi("sesuai", "Sesuai batas suhu komoditas", 100),
            Opsi("sedikit", "Sedikit di atas batas", 55),
            Opsi("jauh", "Jauh di atas batas", 0, kritis=True),
        ),
    ),
    Butir(
        "kesegaran",
        "Kesegaran bahan",
        25,
        (
            Opsi("segar", "Segar", 100),
            Opsi("kurang", "Kurang segar", 55),
            Opsi("busuk", "Busuk", 0, kritis=True),
        ),
    ),
    Butir(
        "kemasan",
        "Kondisi kemasan",
        15,
        (
            Opsi("utuh", "Utuh", 100),
            Opsi("penyok", "Penyok / lecet ringan", 60),
            Opsi("bocor", "Bocor / pecah", 0, kritis=True),
        ),
    ),
    Butir(
        "kebersihan",
        "Kebersihan dan hama",
        15,
        (
            Opsi("bersih", "Bersih, tidak ada hama", 100),
            Opsi("kotoran", "Kotoran ringan", 55),
            Opsi("kontaminasi", "Kontaminasi / ada hama", 0, kritis=True),
        ),
    ),
    Butir(
        "label",
        "Label dan dokumen asal",
        8,
        (
            Opsi("lengkap", "Lengkap", 100),
            Opsi("sebagian", "Sebagian", 50, perlu_cek=True),
            Opsi("tidak_ada", "Tidak ada", 10, perlu_cek=True),
        ),
    ),
    Butir(
        "jumlah",
        "Kesesuaian jumlah",
        7,
        (
            Opsi("sesuai", "Sesuai timbangan (≥95% pesanan)", 100),
            Opsi("kurang", "Kurang dari 95% pesanan", 50),
            Opsi("lebih", "Lebih dari pesanan", 70),
        ),
        dari_timbangan=True,
    ),
    Butir(
        "waktu",
        "Ketepatan waktu tiba",
        5,
        (
            Opsi("tepat", "Tepat waktu", 100),
            Opsi("telat_ringan", "Telat kurang dari 2 jam", 55),
            Opsi("telat_berat", "Telat 2 jam atau lebih", 20),
        ),
    ),
)

BIT_URUT = tuple(butir.kunci for butir in BUTIR)


def butir_by_kunci(kunci: str) -> Butir:
    for butir in BUTIR:
        if butir.kunci == kunci:
            return butir
    raise KeyError(f"butir '{kunci}' tidak dikenal")


@dataclass(frozen=True)
class HasilSkor:
    #: Nilai akhir 0–100 (jumlah poin, karena bobot total = 100).
    score: int
    #: Rincian per butir: kunci, label, opsi, poin, max_points, faktor.
    per_butir: tuple[dict, ...]
    #: Ada jawaban kritis (faktor 0) → putusan `fail` tanpa melihat nilai.
    kritis: bool
    #: Ada butir bertanda perlu cek ulang → `needs_verification`.
    perlu_cek: bool


def _poin(bobot: int, faktor: int) -> int:
    """`bobot × faktor / 100`, HALF_UP ke bilangan bulat (Dok 05 §3)."""
    nilai = Decimal(bobot) * Decimal(faktor) / Decimal(100)
    return int(nilai.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def skor(jawaban: dict[str, str]) -> HasilSkor:
    """Hitung nilai 0–100 dari tujuh jawaban.

    `jawaban` wajib memuat SEMUA kunci butir — ceklis setengah jadi tidak
    dinilai, karena butir yang belum dijawab bukan "0 poin" melainkan "belum
    diperiksa". `KeyError` dengan nama butir yang kurang.
    """
    kurang = [k for k in BIT_URUT if k not in jawaban]
    if kurang:
        raise KeyError(", ".join(kurang))

    total = 0
    rincian: list[dict] = []
    kritis = False
    perlu_cek = False
    for butir in BUTIR:
        opsi = butir.opsi_by_kunci(str(jawaban[butir.kunci]))
        poin = _poin(butir.bobot, opsi.faktor)
        total += poin
        kritis = kritis or opsi.kritis
        perlu_cek = perlu_cek or opsi.perlu_cek
        rincian.append(
            {
                "kunci": butir.kunci,
                "label": butir.label,
                "opsi": opsi.kunci,
                "opsi_label": opsi.label,
                "bobot": butir.bobot,
                "faktor": opsi.faktor,
                "poin": poin,
                "max_points": butir.bobot,
                "kritis": opsi.kritis,
                "perlu_cek": opsi.perlu_cek,
            }
        )
    return HasilSkor(
        score=total, per_butir=tuple(rincian), kritis=kritis, perlu_cek=perlu_cek
    )


def opsi_jumlah(pesan_kg: float, diterima_kg: float) -> str:
    """Jawaban butir `jumlah` DITURUNKAN dari timbangan, bukan dipilih.

    Ambangnya mengikuti §4 aturan 5 (95% pesanan) dan arah selisihnya:
    ≥95% s/d 100% → `sesuai`, <95% → `kurang`, >100% → `lebih`.
    """
    if pesan_kg <= 0:
        return "kurang"
    rasio = diterima_kg / pesan_kg * 100
    if rasio < AMBANG["accepted_ratio_min"]:
        return "kurang"
    if rasio > 100:
        return "lebih"
    return "sesuai"


def validasi_berat(pesan_kg: float, diterima_kg: float) -> str | None:
    """Kode kesalahan berat, atau `None` bila wajar.

    Kode (bukan kalimat) supaya UI menerjemahkan sekali:
    `berat_nol` (< 1 kg), `berat_minus`, `berat_lebih`. Batas atas 110% pesanan
    ada di sini, bukan di UI: timbangan yang mencatat 3× pesanan lebih sering
    salah ketik daripada kiriman sungguhan.
    """
    if diterima_kg < 0:
        return "berat_minus"
    if diterima_kg < 1:
        return "berat_nol"
    if pesan_kg > 0 and diterima_kg > pesan_kg * AMBANG["berat_lebih_maks_persen"] / 100:
        return "berat_lebih"
    return None


def putusan(
    hasil: HasilSkor,
    pesan_kg: float,
    diterima_kg: float,
) -> str:
    """Putusan `fail` / `needs_verification` / `pass` — urutan §4.

    Urutan ini kontrak, bukan selera: aturan pertama yang cocok menang, sehingga
    nilai 98 tidak bisa menyelamatkan kemasan bocor.
    """
    if hasil.kritis or diterima_kg <= 0:
        return "fail"
    if hasil.score < AMBANG["fail_max_score"]:
        return "fail"
    if hasil.perlu_cek or hasil.score <= AMBANG["ambiguous_max_score"]:
        return "needs_verification"
    if pesan_kg > 0 and (
        diterima_kg / pesan_kg * 100 < AMBANG["accepted_ratio_min"]
    ):
        # §4 aturan 5: nilai bagus tidak boleh menutupi barang yang datang jauh
        # lebih sedikit.
        return "needs_verification"
    return "pass"


#: Satu-satunya sumber label putusan. API mengimpornya (bukan menyalin) supaya
#: endpoint ceklis dan balasan baris tidak bisa memberi dua nama untuk putusan
#: yang sama.
NAMA_PUTUSAN = {
    "pass": "Layak diterima",
    "needs_verification": "Perlu keputusan manual",
    "fail": "Tidak boleh diterima",
}


def saran(
    hasil: HasilSkor,
    keputusan: str,
    pesan_kg: float,
    diterima_kg: float,
) -> str:
    """Kalimat alasan untuk layar (§7: rentang 65–85 wajib punya alasannya).

    Tidak pernah menyebut "aman" untuk rentang 65–85, dan tidak menyembunyikan
    penyebabnya: setiap kalimat menyebut angka atau butir yang menurunkannya.
    """
    temuan = [b for b in hasil.per_butir if b["faktor"] < 100]
    sebab = "; ".join(f"{b['label'].lower()} {b['opsi_label'].lower()}" for b in temuan)
    selisih = pesan_kg - diterima_kg
    berat = (
        f" Berat datang {diterima_kg:.0f} kg dari {pesan_kg:.0f} kg pesanan "
        f"({'kurang' if selisih > 0 else 'lebih'} {abs(selisih):.0f} kg)."
        if pesan_kg > 0
        else ""
    )
    kritis = [b["label"].lower() for b in hasil.per_butir if b["kritis"]]
    if keputusan == "fail":
        if kritis:
            return (
                f"Nilai {hasil.score} dari 100, tetapi ada butir kritis: "
                f"{', '.join(kritis)}. Barang tidak boleh masuk dapur.{berat}"
            )
        if diterima_kg <= 0:
            return (
                f"Nilai {hasil.score} dari 100, tetapi tidak ada barang yang "
                f"diterima. Barang tidak boleh masuk dapur.{berat}"
            )
        return (
            f"Nilai {hasil.score} dari 100, di bawah ambang "
            f"{AMBANG['fail_max_score']} — {sebab}. Barang tidak boleh masuk dapur.{berat}"
        )
    if keputusan == "needs_verification":
        alasan = sebab or "tidak ada butir yang penuh"
        if hasil.score <= AMBANG["ambiguous_max_score"] and hasil.score >= AMBANG["fail_max_score"]:
            alasan = (
                f"nilai {hasil.score} ada di rentang "
                f"{AMBANG['fail_max_score']}–{AMBANG['ambiguous_max_score']}: {alasan}"
            )
        return (
            f"Perlu keputusan manual: {alasan}. Kedua tombol tersedia — "
            f"terima atau tolak sama-sama sah, dan alasannya tersimpan.{berat}"
        )
    return (
        f"Layak diterima: nilai {hasil.score} dari 100"
        + (f", {sebab}" if sebab else ", semua butir penuh")
        + f".{berat}"
    )


def checklist_untuk(komoditas: str | None) -> dict:
    """Daftar butir + bobot + pilihan untuk SATU komoditas.

    Petunjuk suhu diambil dari profil komoditas (`commodity_limits`), bukan
    dikarang di UI: telur/ayam/wortel punya rentang rantai dingin, beras tidak.
    Itu sebabnya butir "suhu" bisa berbunyi berbeda antar-komoditas walau bobot
    dan faktornya sama.
    """
    band = safe_temp_for(komoditas) if komoditas else None
    dingin = cold_chain_required(komoditas) if komoditas else False
    if band is not None:
        bawah, atas = band
        petunjuk_suhu = (
            f"Rentang aman {bawah:g}–{atas:g} °C untuk {komoditas}. "
            "Di atas batas → pilih 'sedikit' atau 'jauh di atas batas'."
        )
    elif komoditas and not dingin:
        petunjuk_suhu = (
            f"{komoditas} tidak diukur rantai dingin (suhu ruang) — nilai "
            "keadaan barangnya, bukan angkanya."
        )
    else:
        petunjuk_suhu = "Rentang suhu komoditas ini belum punya profil."

    butir_keluar = []
    for butir in BUTIR:
        butir_keluar.append(
            {
                "kunci": butir.kunci,
                "label": butir.label,
                "bobot": butir.bobot,
                "dari_timbangan": butir.dari_timbangan,
                "petunjuk": petunjuk_suhu if butir.kunci == "suhu" else None,
                "opsi": [
                    {
                        "kunci": o.kunci,
                        "label": o.label,
                        "faktor": o.faktor,
                        "kritis": o.kritis,
                        "perlu_cek": o.perlu_cek,
                    }
                    for o in butir.opsi
                ],
            }
        )
    return {
        "version": CHECKLIST_VERSION,
        "komoditas": komoditas,
        "total_bobot": sum(b.bobot for b in BUTIR),
        "ambang": dict(AMBANG),
        "butir": butir_keluar,
        "nama_putusan": dict(NAMA_PUTUSAN),
    }
