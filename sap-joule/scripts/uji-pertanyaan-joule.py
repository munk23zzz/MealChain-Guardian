"""Uji nyata 14 pertanyaan Joule terhadap jembatan A2A yang sedang berjalan.

Meniru apa yang dikirim Joule (JSON-RPC `message/send` ke bridge A2A), bukan
memanggil backend langsung. Dipakai untuk dua mode database:

    python scripts/uji-pertanyaan-joule.py --mode demo
    python scripts/uji-pertanyaan-joule.py --mode default

Mode `demo` menuntut jawaban berisi DATA (angka/nama/entitas nyata).
Mode `default` menuntut jawaban jujur bahwa belum ada data — bukan tabel kosong
yang terbaca seolah semuanya nol, dan bukan error 500.

Hasil ditulis ke `_qa/joule-pertanyaan-<mode>.json`; exit code 1 bila ada yang
gagal, supaya bisa dipakai sebagai gerbang.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import urllib.error
import urllib.request

PERTANYAAN = [
    {
        "id": "supply-beras-jakarta",
        "skill": "supply_situation",
        "tanya": "Bagaimana situasi pasokan beras di SPPG Jakarta hari ini?",
        "endpoint": "GET /balance/map?commodity=beras, /supply/{loc}/{com}",
        "demo": ["beras", "kg"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "risiko-pemasok-bandung",
        "skill": "supplier_risk",
        "tanya": "Pemasok mana yang berisiko dikeluarkan di Bandung dan mengapa?",
        "endpoint": "GET /supplier-exclusions, /supplier-routes",
        "demo": ["eksklusi", "pemasok"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "antrean-usulan",
        "skill": "approval_queue",
        "tanya": "Tampilkan antrean usulan keputusan yang menunggu persetujuan saya.",
        "endpoint": "GET /decisions, /decisions/{id}/approval-summary",
        "demo": ["usulan", "keputusan"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "kpi-mingguan",
        "skill": "kpi_snapshot",
        "tanya": "Berapa indikator kinerja KPI program dalam 7 hari terakhir?",
        "endpoint": "GET /kpi?start&end",
        "demo": ["kpi", "indikator"],
        "default": ["belum", "tidak ada", "tidak tersedia"],
    },
    {
        "id": "po-dari-keputusan",
        "skill": "purchase_order",
        "tanya": "Tunjukkan PO MC-EXTRA000 dan dari keputusan mana PO itu lahir.",
        "endpoint": "GET /sap/purchase-orders?limit",
        "demo": ["mc-extra000", "keputusan"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "harga-wortel",
        "skill": "price_intelligence",
        "tanya": "Berapa harga acuan dan kuotasi pemasok untuk wortel di Jakarta?",
        "endpoint": "GET /price/{loc}/{com}, /price/quotes/{loc}/{com}",
        "demo": ["wortel", "rp"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "prakiraan-kebutuhan",
        "skill": "demand_forecast",
        "tanya": "Bagaimana prakiraan kebutuhan telur untuk SPPG Jakarta?",
        "endpoint": "GET /demand/forecast/{loc}/{com}",
        "demo": ["telur", "prakiraan"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "kehilangan-pangan",
        "skill": "food_loss",
        "tanya": "Berapa kehilangan pangan 30 hari terakhir dan mana yang sudah dialihkan?",
        "endpoint": "GET /waste/summary?days=30",
        "demo": ["limbah", "kg"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "penerimaan-menunggu",
        "skill": "receipts_queue",
        "tanya": "Penerimaan barang mana yang masih menunggu pemeriksaan?",
        "endpoint": "GET /receipts/menunggu, /receipts?batch_id",
        "demo": ["terima", "menunggu"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "batch-karantina",
        "skill": "quarantine_status",
        "tanya": "Apakah ada batch yang sedang dikarantina atau gagal keamanan pangan?",
        "endpoint": "GET /batches",
        "demo": ["karantina", "batch"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "bukti-keputusan",
        "skill": "decision_evidence",
        "tanya": "Perlihatkan bukti keputusan terbaru: apakah tanda tangannya masih sah?",
        "endpoint": "GET /decisions/{id}/compliance, /chain, /traces",
        "demo": ["bukti", "keputusan"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "status-sistem",
        "skill": "system_status",
        "tanya": "Bagaimana status integrasi sistem dan verifikasi ledger?",
        "endpoint": "GET /integrations/status, /ledger/verify, /sap/purchase-orders/summary",
        "demo": ["integrasi", "ledger"],
        "default": ["integrasi", "ledger"],
    },
    {
        "id": "direktori-pemasok",
        "skill": "supplier_directory",
        "tanya": "Daftar pemasok yang terdaftar beserta komoditasnya.",
        "endpoint": "GET /suppliers?limit",
        "demo": ["pemasok"],
        "default": ["belum", "tidak ada", "kosong"],
    },
    {
        "id": "po-inggris",
        "skill": "purchase_order",
        "tanya": "Show me the latest purchase orders and their suppliers, please.",
        "endpoint": "GET /sap/purchase-orders?limit",
        "demo": ["po", "pemasok"],
        "default": ["belum", "tidak ada", "kosong"],
    },
]


def kirim(url: str, teks: str, timeout: float = 60.0) -> dict:
    """Kirim satu pesan A2A (JSON-RPC message/send) dan kembalikan payload hasil."""
    pesan = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": teks}],
            }
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(pesan).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as f:
        return json.load(f)


def teks_jawaban(payload: dict) -> str:
    """Ambil teks artefak pertama (jalur SpEL yang dipakai Joule)."""
    hasil = payload.get("result") or {}
    for artefak in hasil.get("artifacts") or []:
        for bagian in artefak.get("parts") or []:
            if isinstance(bagian.get("text"), str):
                return bagian["text"]
    for status in hasil.get("status", {}).get("message", {}).get("parts", []) or []:
        if isinstance(status.get("text"), str):
            return status["text"]
    return json.dumps(payload)[:800]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "default"], required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8099/")
    parser.add_argument("--keluar", default=None)
    args = parser.parse_args()

    hasil_uji = []
    gagal = 0
    for item in PERTANYAAN:
        mulai = time.time()
        try:
            payload = kirim(args.url, item["tanya"])
            jawaban = teks_jawaban(payload)
            galat = None
        except urllib.error.HTTPError as exc:
            jawaban = exc.read()[:500].decode(errors="replace")
            galat = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 - dilaporkan apa adanya
            jawaban = ""
            galat = f"{type(exc).__name__}: {exc}"

        kunci = [k.lower() for k in item[args.mode]]
        rendah = jawaban.lower()
        cocok = [k for k in kunci if k in rendah]
        # Mode DEMO: wajib ada penanda data. Mode DEFAULT: wajib jujur kosong.
        lulus = galat is None and bool(rendah.strip()) and bool(cocok)
        if not lulus:
            gagal += 1
        hasil_uji.append(
            {
                "id": item["id"],
                "skill": item["skill"],
                "tanya": item["tanya"],
                "endpoint": item["endpoint"],
                "detik": round(time.time() - mulai, 2),
                "lulus": lulus,
                "cocok": cocok,
                "galat": galat,
                "jawaban": jawaban[:1200],
            }
        )
        tanda = "LULUS" if lulus else "GAGAL"
        print(f"[{tanda}] {item['id']:26s} skill={item['skill']:22s} {round(time.time()-mulai,2)}s")
        if not lulus:
            print(f"         kunci={kunci} galat={galat} jawaban={jawaban[:300]!r}")

    keluar = Path(args.keluar or f"_qa/joule-pertanyaan-{args.mode}.json")
    keluar.parent.mkdir(parents=True, exist_ok=True)
    keluar.write_text(
        json.dumps(
            {
                "mode": args.mode,
                "url": args.url,
                "total": len(hasil_uji),
                "lulus": len(hasil_uji) - gagal,
                "gagal": gagal,
                "hasil": hasil_uji,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\n{len(hasil_uji) - gagal}/{len(hasil_uji)} lulus -> {keluar}")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
