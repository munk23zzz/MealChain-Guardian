"""Monitor harga pasar (PIHPS Bank Indonesia) — logika MURNI + pembacaan snapshot.

Kenapa berkas, bukan tabel DB: data ini adalah SALINAN pakan eksternal
(referensi pasar harian), bukan keadaan operasional MealChain. Snapshot membuat
panel tetap terbaca saat internet venue mati dan menyimpan jejak sumbernya
(`source_url` + `fetched_at`) apa adanya. Tabel `price_signals` yang dipakai
mesin keputusan (acuan semai + kutipan pemasok) TIDAK disentuh, supaya metrik
deviasi 5%/15% tidak berubah diam-diam.

Dipisah dari `app/api/price.py` supaya bisa diuji tanpa DB dan tanpa HTTP.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Akar repo: `backend/app/core/…` → parents[3]. Di kontainer backend mount
#: `./data:/data:ro`, jadi jalur yang dihitung tetap `/data/harga_pihps/…`.
AKAR_REPO = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = AKAR_REPO / "data" / "harga_pihps" / "pihps_latest.json"

#: Komoditas MealChain → kode PIHPS. Wortel SENGAJA tidak ada: PIHPS tidak
#: menerbitkan wortel, jadi panel tidak boleh menampilkannya sebagai acuan.
KOMODITAS_PROYEK: dict[str, str] = {
    "telur": "com_10",
    "ayam": "com_7",
    "beras": "com_3",
}
KODE_KE_PROYEK: dict[str, str] = {kode: nama for nama, kode in KOMODITAS_PROYEK.items()}

#: Cache sederhana {jalur: (mtime, isi)} — penarikan ulang langsung terlihat.
_cache: dict[str, tuple[float, dict]] = {}


def baca_snapshot(path: Path | None = None) -> dict | None:
    """Snapshot terakhir, atau None bila berkas hilang/rusak (bukan galat 500)."""
    berkas = path or SNAPSHOT_PATH
    try:
        mtime = berkas.stat().st_mtime
    except OSError:
        return None
    kunci = str(berkas)
    tersimpan = _cache.get(kunci)
    if tersimpan and tersimpan[0] == mtime:
        return tersimpan[1]
    try:
        isi = json.loads(berkas.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(isi, dict):
        return None
    _cache[kunci] = (mtime, isi)
    return isi


def kode_diminta(commodity: str | None) -> list[str] | None:
    """'telur,com_3' → ['com_10', 'com_3']; None = tanpa filter.

    Nama tak dikenal diabaikan dengan sengaja: filter yang salah ketik tidak
    boleh berubah menjadi "tampilkan semua".
    """
    if not commodity:
        return None
    kode: list[str] = []
    for bagian in commodity.split(","):
        bagian = bagian.strip()
        if not bagian:
            continue
        if bagian in KOMODITAS_PROYEK:
            kode.append(KOMODITAS_PROYEK[bagian])
        elif bagian.startswith("com_"):
            kode.append(bagian)
    return kode or None


def jawaban_kosong(alasan: str) -> dict:
    return {
        "status": "kosong",
        "alasan": alasan,
        "source": None,
        "source_url": None,
        "market": None,
        "unit": None,
        "fetched_at": None,
        "window": None,
        "days": 0,
        "commodities": [],
        "movers": [],
        "regions": [],
        "coverage": {"tanggal_terisi": 0, "tanggal_pertama": None, "tanggal_terakhir": None},
        "rows": [],
    }


def pergerakan_teratas(
    rows: list[dict], kode: str, batas: int = 3
) -> list[dict]:
    """Wilayah dengan perubahan terbesar untuk satu komoditas.

    Dihitung di server dari SELURUH baris snapshot (bukan dari jendela satu
    wilayah), supaya panel bisa menunjukkan "di mana harga bergerak" tanpa
    mengirim ribuan baris ke peramban. Wilayah dengan satu titik dilewati:
    satu titik tidak punya arah, dan menuliskan 0% berarti mengarang.
    """
    per_wilayah: dict[str, list[dict]] = {}
    for baris in rows:
        if baris.get("commodity_code") != kode:
            continue
        harga = baris.get("price_per_kg")
        if not isinstance(harga, (int, float)) or harga <= 0:
            continue
        per_wilayah.setdefault(baris.get("region_name", ""), []).append(baris)

    hasil: list[dict] = []
    for wilayah, daftar in per_wilayah.items():
        if len(daftar) < 2:
            continue
        urut = sorted(daftar, key=lambda b: b.get("observed_on", ""))
        awal = float(urut[0]["price_per_kg"])
        akhir = float(urut[-1]["price_per_kg"])
        if awal <= 0:
            continue
        hasil.append(
            {
                "region_name": wilayah,
                "awal": awal,
                "akhir": akhir,
                "delta_pct": (akhir - awal) / awal * 100,
            }
        )
    hasil.sort(key=lambda h: abs(h["delta_pct"]), reverse=True)
    return hasil[:batas]


def susun_monitor(
    snap: dict,
    *,
    days: int = 30,
    commodity: str | None = None,
    region: str | None = None,
) -> dict:
    """Potong snapshot jadi deret siap-render untuk satu jendela hari.

    `days` dihitung dari TANGGAL BERISI DATA, bukan hari kalender: PIHPS tidak
    terbit Sabtu/Minggu, jadi "30 hari" berarti 30 tanggal publikasi terakhir.
    """
    jendela = max(1, min(int(days), 120))
    tanggal = sorted(snap.get("tanggal_terisi") or [])
    batas = tanggal[-jendela:] if tanggal else []
    batas_awal = batas[0] if batas else "9999-12-31"
    # Jendela punya DUA ujung: tanpa batas akhir, baris bertanggal masa depan
    # (mis. sisa penarikan lama) ikut terkirim dan sumbu X melompat.
    batas_akhir = batas[-1] if batas else "0000-00-00"

    kode = kode_diminta(commodity)
    rows = [
        {
            "commodity_code": baris["commodity_code"],
            "commodity_label": baris["commodity_label"],
            "region_name": baris["region_name"],
            "region_level": baris["region_level"],
            "observed_on": baris["observed_on"],
            "price_per_kg": baris["price_per_kg"],
        }
        for baris in snap.get("rows", [])
        if batas_awal <= baris.get("observed_on", "") <= batas_akhir
        and (not kode or baris.get("commodity_code") in kode)
        and (not region or baris.get("region_name") == region)
    ]

    komoditas = [
        {
            "code": item["code"],
            "label": item["label"],
            # Nama komoditas MealChain yang memakai seri ini; None = seri PIHPS
            # yang tidak dipakai modul (mis. cabai).
            "project_key": KODE_KE_PROYEK.get(item["code"]),
        }
        for item in snap.get("komoditas", [])
        if not kode or item["code"] in kode
    ]

    # Pergerakan hanya bermakna kalau ada satu komoditas acuan; dengan filter
    # kosong (semua komoditas) daftar ini tidak diisi.
    pergerakan = pergerakan_teratas(snap.get("rows", []), kode[0], 3) if kode else []

    return {
        "status": "ok" if rows else "kosong",
        "alasan": None
        if rows
        else (
            "Snapshot ada, tetapi tidak ada baris untuk filter ini "
            f"(wilayah={region or 'semua'}, komoditas={commodity or 'semua'})."
        ),
        "source": snap.get("sumber"),
        "source_url": snap.get("source_url"),
        "market": snap.get("jenis_pasar"),
        "unit": snap.get("satuan"),
        "fetched_at": snap.get("fetched_at"),
        "window": snap.get("window"),
        "days": jendela,
        "commodities": komoditas,
        "movers": pergerakan,
        "regions": snap.get("wilayah", []),
        "coverage": {
            "tanggal_terisi": len(batas),
            "tanggal_pertama": batas[0] if batas else None,
            "tanggal_terakhir": batas[-1] if batas else None,
        },
        "rows": rows,
    }
