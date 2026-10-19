"""Profil pemasok kanonik DITURUNKAN dari batch kiriman (keputusan pemilik 2026-10-16).

Kenapa ada modul ini: `data/seed/sprint1_seed.json` mendefinisikan 60 pemasok
kanonik hanya dengan `name`/`location`/`reliability_score`, sehingga
`commodity_id`, `certification_status`, dan `capacity_kg_per_week` mereka NULL di
DB. Tab Pemasok karena itu menampilkan baris dengan Komoditas/Sertifikasi kosong,
dan pemasok kanonik tidak bisa tersaring per komoditas di peta.

Dua jalan keluar yang DITOLAK:

1. Mengarang nilai (mis. menebak kapasitas mingguan) - melanggar prinsip proyek
   "tidak ada angka karangan".
2. Menyalin dari pemasok demo Jabodetabek - mengubah identitas baris kanonik yang
   sudah dipakai mesin rekomendasi dan tes jangkar.

Yang dipakai: menurunkan HANYA apa yang bisa dibuktikan dari data yang sudah ada
(batch kiriman pemasok itu sendiri), dan membiarkan sisanya kosong.

Aturan (persis yang diuji di `tests/test_supplier_profile.py`):

- `commodity` = komoditas dengan total `quantity_kg` TERBESAR; seri ->
  komoditas batch paling BARU (`harvested_at_offset_hours` terbesar);
  masih seri -> `None`.
- `certification_status` = nilai sertifikasi batch bila seragam; beragam -> nilai
  TERBANYAK; seri -> `None`. Nilai kosong/`None` pada batch tidak dihitung.
- `capacity_kg_per_week` TIDAK ADA di keluaran: batch hanya memuat berat per
  kiriman, bukan kapasitas mingguan.
- Pemasok tanpa batch -> `{"commodity": None, "certification_status": None}`.
- Batch yang menyebut nama pemasok di luar daftar diabaikan (validasi referensi
  tetap milik seeder, bukan modul murni ini).

Deterministik: urutan batch pada masukan tidak boleh mengubah hasil, karena
pemecahan seri memakai nilai data (kuantitas, umur batch), bukan urutan baris.
"""

from collections import defaultdict
from typing import Iterable, Mapping, Optional


def _num(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dominant_commodity(batches: list[Mapping]) -> Optional[str]:
    """Komoditas dengan total kg terbesar; seri -> batch terbaru; seri -> None."""
    totals: dict[str, float] = defaultdict(float)
    newest: dict[str, float] = {}
    for batch in batches:
        commodity = batch.get("commodity")
        if not commodity:
            continue
        totals[commodity] += _num(batch.get("quantity_kg")) or 0.0
        age = _num(batch.get("harvested_at_offset_hours"))
        if age is not None:
            # Offset negatif = masa lalu; makin besar (mendekati 0) = makin baru.
            newest[commodity] = max(newest.get(commodity, float("-inf")), age)

    if not totals:
        return None

    best_total = max(totals.values())
    winners = [name for name, total in totals.items() if total == best_total]
    if len(winners) == 1:
        return winners[0]

    # Seri total: batch terbaru menang - hanya bila ada umur batch yang bisa dibandingkan.
    scored = [(newest.get(name, float("-inf")), name) for name in winners]
    if any(score == float("-inf") for score, _ in scored):
        return None
    best_score = max(score for score, _ in scored)
    freshest = [name for score, name in scored if score == best_score]
    return freshest[0] if len(freshest) == 1 else None


def _dominant_certification(batches: list[Mapping]) -> Optional[str]:
    """Nilai sertifikasi terbanyak; seragam -> nilai itu; seri -> None."""
    counts: dict[str, int] = defaultdict(int)
    for batch in batches:
        cert = batch.get("certification_status")
        if cert:
            counts[cert] += 1
    if not counts:
        return None
    top = max(counts.values())
    winners = [name for name, n in counts.items() if n == top]
    return winners[0] if len(winners) == 1 else None


def derive_supplier_profiles(
    batches: Iterable[Mapping], supplier_names: Iterable[str]
) -> dict[str, dict]:
    """Peta nama pemasok -> profil turunan (lihat docstring modul untuk aturannya)."""
    names = list(supplier_names)
    per_supplier: dict[str, list[Mapping]] = {name: [] for name in names}
    for batch in batches:
        owner = batch.get("supplier")
        if owner in per_supplier:
            per_supplier[owner].append(batch)

    return {
        name: {
            "commodity": _dominant_commodity(rows),
            "certification_status": _dominant_certification(rows),
        }
        for name, rows in per_supplier.items()
    }
