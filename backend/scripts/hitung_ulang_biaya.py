"""Hitung ulang biaya seluruh keputusan dari data (revisi rumus 2026-10-29b).

Kenapa ada
----------
Rumus SDC berubah: laju susut per komoditas, penalti kesegaran linear, dan
angkut per trip. Angka yang TERSIMPAN di `decisions.cost_breakdown` masih
dihitung dengan rumus lama. Membiarkannya berarti panel bukti menampilkan
angka lama dengan label versi baru — tepat jenis kebohongan yang dilarang
`Rules.md`.

Cara kerja
----------
Biaya tiap keputusan dihitung ulang dari data nyata (harga, batch, jarak) oleh
`services.demo_cost.hitung_biaya_demo` — mesin yang sama dengan tombol
"Hitung ulang biaya", bukan angka tulis tangan. Skrip TIDAK menyentuh
keputusan administratif (tanpa rincian biaya transfer) dan tidak mengarang
angka bila bahan hitung tidak ada; keputusan seperti itu dilaporkan apa adanya.

Dua hal WAJIB terjadi bersamaan (temuan audit 26 Okt 2026): kolom keputusan
DAN `agent_traces.output_summary["sdc"]`. Kalau hanya yang pertama, tab Agent
Log memperlihatkan angka berbeda dari kartu rekomendasi untuk keputusan yang
sama.

Pemakaian (di kontainer)
------------------------
    docker compose exec -T backend python scripts/hitung_ulang_biaya.py
    docker compose exec -T backend python scripts/hitung_ulang_biaya.py --terapkan

Tanpa `--terapkan` skrip hanya membaca (pratinjau). Dengan `--terapkan` ia
menulis cadangan nilai lama ke `_qa/hitung-ulang-biaya-<tanggal>.json` lebih
dulu, baru menyimpan perubahan.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.decisions import AgentTrace, Decision
from app.services.decision_time import evaluation_clock
from app.services.demo_cost import hitung_biaya_demo

URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain",
)

#: Kunci breakdown yang angkanya ikut berubah bila rumus berubah.
_KUNCI_PANTAU = ("transport", "transport_supplier_leg", "loss_in_storage", "freshness_risk")


def _num(nilai) -> Decimal | None:
    if nilai is None or nilai == "":
        return None
    try:
        return Decimal(str(nilai))
    except (ArithmeticError, TypeError, ValueError):
        return None


def _ringkas(bd: dict | None, kunci: str) -> Decimal | None:
    if not isinstance(bd, dict):
        return None
    return _num(bd.get(kunci))


async def _sinkron_jejak(db, keputusan: Decision) -> int:
    """Samakan `sdc` di jejak DECIDE dengan SDC final. Kembalikan jumlah baris."""
    if keputusan.safe_delivered_cost is None:
        return 0
    jejak = (
        await db.execute(
            select(AgentTrace).where(
                AgentTrace.decision_id == keputusan.id,
                AgentTrace.output_summary.isnot(None),
            )
        )
    ).scalars().all()
    n = 0
    for langkah in jejak:
        ringkasan = langkah.output_summary
        if isinstance(ringkasan, dict) and "sdc" in ringkasan:
            langkah.output_summary = {
                **ringkasan,
                "sdc": float(keputusan.safe_delivered_cost),
            }
            n += 1
    return n


async def jalankan(terapkan: bool, as_of: datetime | None) -> int:
    engine = create_async_engine(URL)
    sesi_pabrik = async_sessionmaker(engine, expire_on_commit=False)
    sekarang = evaluation_clock(as_of)
    baris: list[dict] = []
    cadangan: list[dict] = []

    async with sesi_pabrik() as db:
        keputusan = (
            await db.execute(
                select(Decision)
                .where(Decision.quantity_kg.isnot(None))
                .order_by(Decision.created_at, Decision.id)
            )
        ).scalars().all()

        for d in keputusan:
            bd_lama = d.cost_breakdown if isinstance(d.cost_breakdown, dict) else None
            dasar = {
                "id": str(d.id),
                "judul": f"{d.demo_case or d.decision_type} {str(d.id)[:8]}",
                "status": d.status,
                "qty": str(d.quantity_kg),
                "sdc_lama": str(d.safe_delivered_cost),
                "sdc_baru": None,
                "delta": None,
                "delta_komponen": {},
                "versi_lama": (bd_lama or {}).get("formula_version"),
                "versi_baru": None,
                "hasil": "",
            }

            if not bd_lama or "purchase" not in bd_lama:
                dasar["hasil"] = "dilewati: tidak punya rincian biaya transfer"
                baris.append(dasar)
                continue

            cadangan.append(
                {
                    "id": str(d.id),
                    "safe_delivered_cost": str(d.safe_delivered_cost),
                    "cost_breakdown": bd_lama,
                }
            )

            berhasil = await hitung_biaya_demo(db, d, sekarang)
            if not berhasil:
                dasar["hasil"] = "gagal: bahan hitung tidak tersedia (dibiarkan apa adanya)"
                baris.append(dasar)
                continue

            bd_baru = d.cost_breakdown if isinstance(d.cost_breakdown, dict) else {}
            dasar["sdc_baru"] = str(d.safe_delivered_cost)
            lama, baru = _num(dasar["sdc_lama"]), _num(dasar["sdc_baru"])
            if lama is not None and baru is not None:
                dasar["delta"] = str((baru - lama).quantize(Decimal("0.01")))
            dasar["versi_baru"] = bd_baru.get("formula_version")
            for kunci in _KUNCI_PANTAU:
                a, b = _ringkas(bd_lama, kunci), _ringkas(bd_baru, kunci)
                if a is None or b is None:
                    continue
                selisih = (b - a).quantize(Decimal("0.01"))
                if selisih:
                    dasar["delta_komponen"][kunci] = str(selisih)
            dasar["hasil"] = "dihitung ulang"
            baris.append(dasar)

        dihitung = sum(1 for b in baris if b["hasil"] == "dihitung ulang")
        gagal = sum(1 for b in baris if b["hasil"].startswith("gagal"))
        dilewati = len(baris) - dihitung - gagal

        print(f"as-of evaluasi : {sekarang.isoformat()}")
        print(
            f"keputusan      : {len(baris)} "
            f"(dihitung ulang {dihitung}, gagal {gagal}, dilewati {dilewati})"
        )
        print()
        urut = sorted(baris, key=lambda x: abs(Decimal(x["delta"] or "0")), reverse=True)
        for b in urut[:15]:
            delta = b["delta"] or "-"
            print(
                f"  {b['id'][:8]}  {str(b['judul'])[:30]:30s}  "
                f"SDC {b['sdc_lama'] or '-':>14s} → {b['sdc_baru'] or '-':>14s}  Δ {delta:>14s}  "
                f"[{b['hasil']}]"
            )
            for kunci, selisih in b["delta_komponen"].items():
                print(f"        · {kunci:24s} Δ {selisih}")
        sisa = [b for b in baris if b["hasil"] != "dihitung ulang"]
        if sisa:
            print()
            print("  tidak dihitung ulang:")
            for b in sisa:
                print(f"    {b['id'][:8]}  {str(b['judul'])[:44]:44s}  {b['hasil']}")

        if not terapkan:
            print()
            print("PRATINJAU — tidak ada yang ditulis. Ulangi dengan --terapkan untuk menyimpan.")
            await db.rollback()
            await engine.dispose()
            return 0

        # Cadangan ditulis SEBELUM commit supaya perubahan selalu bisa dibandingkan.
        # `/app` = backend (mount compose); repo root tidak ikut di-mount, jadi
        # cadangan ditulis ke `backend/_qa` dan bisa dipindah ke `_qa` repo.
        folder = Path(os.environ.get("QA_DIR", "/app/_qa"))
        folder.mkdir(parents=True, exist_ok=True)
        cap = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        berkas = folder / f"hitung-ulang-biaya-{cap}.json"
        berkas.write_text(
            json.dumps(
                {"dibuat": cap, "as_of": sekarang.isoformat(), "keputusan": cadangan},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        sinkron = 0
        for d in keputusan:
            if isinstance(d.cost_breakdown, dict) and "purchase" in d.cost_breakdown:
                sinkron += await _sinkron_jejak(db, d)

        await db.commit()
        print()
        print(f"cadangan nilai lama : {berkas}")
        print(f"jejak DECIDE disinkronkan: {sinkron} baris")
        print("TERSIMPAN.")

    await engine.dispose()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--terapkan", action="store_true", help="tulis hasil + sinkron jejak")
    p.add_argument(
        "--as-of", default=None, help="jam evaluasi ISO-8601 (default: jam evaluasi dataset)"
    )
    a = p.parse_args()
    as_of = datetime.fromisoformat(a.as_of.replace("Z", "+00:00")) if a.as_of else None
    return asyncio.run(jalankan(a.terapkan, as_of))


if __name__ == "__main__":
    raise SystemExit(main())
