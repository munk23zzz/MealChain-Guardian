"""Pemasok yang SEDANG MENGIRIM barang (keputusan pemilik 2026-10-16).

Definisi yang disetujui pemilik: kiriman dianggap "sedang berjalan" bila batch-nya
MASIH LAYAK dipakai hari ini (`usable_until >= sekarang`). Batch yang masa
layaknya sudah lewat tidak dihitung - mengirim barang yang sudah tidak layak
bukan kiriman aktif, itu temuan mutu.

Modul murni ini sengaja tidak menyentuh DB: ia hanya meringkas baris batch yang
sudah dibaca endpoint, supaya aturan "layak" bisa diuji tanpa fixture DB dan
angka di peta selalu berasal dari DB (bukan dihitung ulang di frontend).

Kontrak keluaran per pemasok:
- `count`             jumlah kiriman layak
- `total_kg`          total berat kiriman layak (float)
- `until`             batas layak TERJAUH (datetime)
- `commodities`       nama komoditas unik, terurut, tanpa nilai kosong
- `safety_fail_count` kiriman layak yang status keamanannya `fail` (bukan
                      disembunyikan: kalau ada, UI wajib bisa menyebutnya)

Pemasok tanpa baris layak TIDAK muncul di peta hasil (bukan entri 0 kg).
"""

from datetime import datetime
from typing import Iterable, Mapping, Optional


def shipping_summary(
    rows: Iterable[Mapping], now: datetime
) -> dict[str, dict]:
    """Ringkas baris batch -> peta `supplier_id` -> ringkasan kiriman aktif.

    `rows` memuat kunci: `supplier_id`, `commodity`, `quantity_kg`,
    `usable_until`, `safety_status`. Baris tanpa `supplier_id` atau tanpa
    `usable_until` diabaikan (tidak bisa dibuktikan sedang berjalan).
    """
    summary: dict[str, dict] = {}
    for row in rows:
        supplier_id = row.get("supplier_id")
        usable_until = row.get("usable_until")
        if supplier_id is None or usable_until is None:
            continue
        if usable_until < now:
            continue

        entry = summary.setdefault(
            str(supplier_id),
            {
                "count": 0,
                "total_kg": 0.0,
                "until": usable_until,
                "commodities": set(),
                "safety_fail_count": 0,
            },
        )
        entry["count"] += 1
        entry["total_kg"] += float(row.get("quantity_kg") or 0.0)
        if usable_until > entry["until"]:
            entry["until"] = usable_until
        commodity = row.get("commodity")
        if commodity:
            entry["commodities"].add(commodity)
        if row.get("safety_status") == "fail":
            entry["safety_fail_count"] += 1

    return {
        supplier_id: {
            "count": entry["count"],
            "total_kg": round(entry["total_kg"], 3),
            "until": entry["until"],
            "commodities": sorted(entry["commodities"]),
            "safety_fail_count": entry["safety_fail_count"],
        }
        for supplier_id, entry in summary.items()
    }


def shipping_for(summary: Mapping[str, dict], supplier_id) -> Optional[dict]:
    """Ringkasan satu pemasok, atau None bila tidak ada kiriman layak."""
    if supplier_id is None:
        return None
    return summary.get(str(supplier_id))
