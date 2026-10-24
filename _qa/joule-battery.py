"""Baterai uji chat Joule: kirim pertanyaan gaya juri ke jembatan A2A dan simpan artefaknya.

Baca-saja: hanya `message/send` (GET di sisi jembatan ke backend), tidak menyentuh endpoint
mutasi. Hasil ditulis ke _qa/ agar bisa diperiksa satu per satu.

Pakai:  python _qa/joule-battery.py [--bridge URL] [--out BERKAS]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import httpx

BRIDGE = "https://mealchain-joule-bridge-4sehat3trio.cfapps.ap10.hana.ondemand.com/"

PERTANYAAN: list[tuple[str, str]] = [
    ("supply-umum", "bagaimana kondisi pasokan?"),
    ("supply-spesifik", "berapa stok telur di Bandung?"),
    ("supply-spesifik-2", "apakah ayam di Jakarta kurang?"),
    ("supply-spesifik-3", "kebutuhan wortel di Bogor berapa?"),
    ("kpi", "bagaimana KPI agen minggu ini?"),
    ("antrean", "antrean keputusan yang menunggu persetujuan"),
    ("po-daftar", "PO mana yang sudah disetujui?"),
    ("direktori", "tampilkan direktori pemasok"),
    ("risiko-pemasok", "pemasok mana yang berisiko?"),
    ("harga", "harga beras di Jakarta"),
    ("harga-spesifik", "berapa harga telur di Bandung?"),
    ("kebutuhan", "prakiraan kebutuhan telur di Bandung"),
    ("limbah", "kehilangan pangan minggu ini"),
    ("karantina", "status karantina batch"),
    ("penerimaan", "antrean penerimaan barang yang menunggu"),
    ("sistem", "status integrasi SAP dan ledger"),
    ("tak-didukung", "pengiriman barang ke Surabaya pakai surat jalan siapa?"),
    ("ambigu", "bagaimana kondisi gudang sekarang?"),
    ("sapaan", "halo, kamu bisa bantu apa?"),
    ("batch-opname", "batch mana yang harus dibuang?"),
    ("batch-kedaluwarsa", "batch telur yang sudah kedaluwarsa"),
    ("po-detail", "tampilkan PO MC-661695B2C685"),
    ("bukti-satu", "bukti keputusan 94d13057-70ae-401c-ae35-aab399bde3ed"),
    ("siapa-menyetujui", "siapa yang menyetujui keputusan 94d13057-70ae-401c-ae35-aab399bde3ed?"),
    ("penerimaan-batch", "penerimaan barang batch 3627c1d1-85d4-53a2-b841-1f75693a9888"),
    ("eksklusi", "pemasok yang dikecualikan di hub"),
    ("harga-lokasi-lain", "berapa harga ayam di Surabaya?"),
    ("supply-komoditas", "stok beras di Makassar berapa?"),
    ("supply-tidak-ada", "berapa stok gandum di Bandung?"),
]


def tanya(client: httpx.Client, teks: str, nomor: int) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": str(nomor),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "kind": "message",
                "messageId": str(nomor),
                "parts": [{"kind": "text", "text": teks}],
            }
        },
    }
    mulai = time.time()
    try:
        resp = client.post("", json=payload)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - hasil apa pun dicatat, bukan dilempar
        return {"teks": teks, "galat": f"{type(exc).__name__}: {exc}", "detik": round(time.time() - mulai, 2)}
    hasil = data.get("result") or {}
    artefacts = hasil.get("artifacts") or []
    isi = artefacts[0].get("parts", [{}])[0].get("text", "") if artefacts else ""
    return {
        "teks": teks,
        "state": (hasil.get("status") or {}).get("state"),
        "detik": round(time.time() - mulai, 2),
        "artefak": isi,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", default=BRIDGE)
    parser.add_argument("--out", default="_qa/joule-battery.json")
    args = parser.parse_args()

    hasil: list[dict] = []
    with httpx.Client(base_url=args.bridge, timeout=120.0) as client:
        for i, (label, teks) in enumerate(PERTANYAAN, start=1):
            satu = tanya(client, teks, i)
            satu["label"] = label
            hasil.append(satu)
            print(
                f"[{i:02d}] {label:18s} state={satu.get('state')!s:10s} "
                f"{satu.get('detik')}s  {len(satu.get('artefak') or '')} char",
                flush=True,
            )
            if satu.get("galat"):
                print("     GALAT:", satu["galat"], flush=True)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(hasil, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTersimpan: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
