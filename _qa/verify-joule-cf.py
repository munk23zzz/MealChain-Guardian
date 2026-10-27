"""Verifikasi silang: jawaban jembatan Joule (via CF) vs API backend pada saat yang sama.

Baca-saja. Untuk tiap pertanyaan, ambil angka dari artefak Joule lalu bandingkan dengan angka
yang baru saja dibaca dari API backend — supaya klaim "Joule membaca database" punya bukti,
bukan kesan. DB demo dipakai bersama, jadi setiap baris mencetak juga jam pembacaan.

Pakai: python _qa/verify-joule-cf.py [--bridge URL]
"""

from __future__ import annotations

import argparse
import re
import sys

import httpx

BRIDGE = "https://mealchain-joule-bridge-4sehat3trio.cfapps.ap10.hana.ondemand.com/"
BACKEND = "http://localhost:8000"
READ_USER = "bgn.monitor@demo.local"
READ_PASS = "Demo#BGN2026"  # akun demo publik dari backend/app/seed/seed_data.py


def tanya(client: httpx.Client, teks: str) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "kind": "message",
                "messageId": "1",
                "parts": [{"kind": "text", "text": teks}],
            }
        },
    }
    resp = client.post("", json=payload)
    resp.raise_for_status()
    hasil = resp.json()["result"]
    assert hasil["status"]["state"] == "completed", hasil.get("status")
    return hasil["artifacts"][0]["parts"][0]["text"]


def j2f(teks: str | None) -> float | None:
    """Angka gaya Indonesia -> float. `1.234,5` -> 1234.5 (titik ribuan, koma desimal)."""
    if teks is None:
        return None
    bersih = str(teks).strip().replace("Rp", "").replace("kg", "").strip()
    bersih = bersih.replace(".", "").replace(",", ".")
    try:
        return float(bersih)
    except ValueError:
        return None


def sama(kiri: float | None, kanan: float | None, toleransi: float = 0.051) -> bool:
    """Toleransi 0,051 = pembulatan satu desimal pada tampilan; bukan selisih data."""
    return kiri is not None and kanan is not None and abs(kiri - kanan) <= toleransi


def f2id(x: float, digits: int = 1) -> str:
    """float -> tampilan Indonesia: 1234.5 -> `1.234,5`."""
    teks = f"{x:,.{digits}f}".replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    if digits and "," in teks:
        teks = teks.rstrip("0").rstrip(",")  # 50,00 -> 50 ; 3,20 -> 3,2 (sama seperti jembatan)
    return teks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", default=BRIDGE)
    args = parser.parse_args()

    hasil: list[tuple[str, str, str, str]] = []  # (cek, joule, api, status)

    with httpx.Client(base_url=args.bridge, timeout=120.0) as joule, httpx.Client(
        base_url=BACKEND, timeout=30.0
    ) as api:
        tok = api.post("/auth/login", json={"email": READ_USER, "password": READ_PASS}).json()[
            "access_token"
        ]
        api.headers["Authorization"] = f"Bearer {tok}"

        # 1. pasokan satu pasangan -------------------------------------------------------
        bal = api.get("/balance/map", params={"commodity": "telur"}).json()
        bd = next(r for r in bal["locations"] if r["location"] == "Bandung")
        teks = tanya(joule, "berapa stok telur di Bandung?")
        bal2 = api.get("/balance/map", params={"commodity": "telur"}).json()
        bd_sesudah = next(r for r in bal2["locations"] if r["location"] == "Bandung")
        cocok = re.search(r"pasokan ([\d.,]+) kg dari kebutuhan ([\d.,]+) kg: kurang ([\d.,]+) kg", teks)
        j = [j2f(x) for x in cocok.groups()] if cocok else [None, None, None]
        a = [float(bd_sesudah["supply_kg"]), float(bd_sesudah["demand_kg"]), float(bd_sesudah["shortage_kg"])]
        a_lama = [float(bd["supply_kg"]), float(bd["demand_kg"]), float(bd["shortage_kg"])]
        if [round(x, 1) for x in a] != [round(x, 1) for x in a_lama]:
            status = "DATA BERGERAK"
        elif all(sama(x, y) for x, y in zip(j, a)):
            status = "OK"
        else:
            status = "BEDA"
        hasil.append(
            (
                "pasokan Bandung/telur",
                "/".join(f2id(x) if x is not None else "?" for x in j),
                "/".join(f2id(x) for x in a),
                status,
            )
        )

        # 2. KPI ------------------------------------------------------------------------
        akhir = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        awal = akhir - __import__("datetime").timedelta(days=7)
        jendela = {
            "start": awal.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": akhir.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        kpi = api.get("/kpi", params=jendela).json()["metrics"]
        teks = tanya(joule, "bagaimana KPI agen minggu ini?")
        kpi_sesudah = api.get("/kpi", params=jendela).json()["metrics"]
        nilai_sebelum = {m.get("name"): (m.get("state"), m.get("value")) for m in kpi}
        bergerak = any(
            nilai_sebelum.get(m.get("name")) != (m.get("state"), m.get("value"))
            for m in kpi_sesudah
        )
        kpi = kpi_sesudah
        for m in kpi:
            nilai = m.get("value")
            if m.get("state") != "available" or nilai is None:
                continue
            unit = str(m.get("unit") or "")
            nilai_f = float(nilai)
            if unit in {"percent", "%"}:
                tampil = f"{f2id(nilai_f, 2)}%"
            elif unit in {"IDR", "idr"}:
                tampil = "Rp" + f"{nilai_f:,.0f}".replace(",", ".")
            elif unit in {"minutes", "minute", "menit"}:
                tampil = f"{f2id(nilai_f, 2)} menit"
            else:
                tampil = f2id(nilai_f, 2)
            if tampil in teks:
                status = "OK"
            elif bergerak:
                status = "DATA BERGERAK"
            else:
                status = "TIDAK ADA"
            hasil.append((f"KPI {m.get('name')}", tampil, tampil, status))

        # 3. antrean usulan --------------------------------------------------------------
        terbuka_status = {"proposed", "pending_approval", "verifier_flagged", "approved"}
        semua = api.get("/decisions", params={"limit": 200}).json()["items"]
        terbuka = sum(1 for r in semua if r["status"] in terbuka_status)
        teks = tanya(joule, "antrean keputusan yang menunggu persetujuan")
        cocok = re.search(r"\((\d+) usulan terbuka", teks) or re.search(r"\((\d+) baris\)", teks)
        hasil.append(
            (
                "antrean terbuka",
                cocok.group(1) if cocok else "?",
                str(terbuka),
                "OK" if cocok and int(cocok.group(1)) == terbuka else "BEDA",
            )
        )

        # 4. pemasok --------------------------------------------------------------------
        sup = api.get("/suppliers", params={"limit": 200}).json()
        teks = tanya(joule, "tampilkan direktori pemasok")
        cocok = re.search(r"Direktori pemasok \((\d+) pemasok", teks)
        hasil.append(
            (
                "jumlah pemasok",
                cocok.group(1) if cocok else "?",
                str(sup["total"]),
                "OK" if cocok and int(cocok.group(1)) == sup["total"] else "BEDA",
            )
        )

        # 5. penerimaan barang -----------------------------------------------------------
        rc = api.get("/receipts/menunggu").json().get("total")
        teks = tanya(joule, "antrean penerimaan barang yang menunggu")
        cocok = re.search(r"Ada (\d+) penerimaan barang", teks)
        if rc == 0:
            hasil.append(
                ("penerimaan menunggu", "Tidak ada" if "Tidak ada penerimaan" in teks else teks[:40], "0",
                 "OK" if "Tidak ada penerimaan" in teks else "BEDA")
            )
        else:
            hasil.append(
                (
                    "penerimaan menunggu",
                    cocok.group(1) if cocok else "?",
                    str(rc),
                    "OK" if cocok and int(cocok.group(1)) == rc else "BEDA",
                )
            )

        # 6. PO yang sudah dieksekusi ----------------------------------------------------
        po = api.get("/sap/purchase-orders", params={"limit": 200}).json()["items"]
        eksekusi = sum(1 for r in po if str(r.get("decision_status")) in {"approved", "executed"})
        teks = tanya(joule, "PO mana yang sudah disetujui?")
        cocok = re.search(r"dieksekusi \((\d+) PO\)", teks)
        hasil.append(
            (
                "PO disetujui/dieksekusi",
                cocok.group(1) if cocok else "?",
                str(eksekusi),
                "OK" if cocok and int(cocok.group(1)) == eksekusi else "BEDA",
            )
        )

        # 7. karantina -------------------------------------------------------------------
        batches = api.get("/batches", params={"limit": 500}).json()["batches"]
        karantina = [b for b in batches if str(b.get("quarantine_status")).lower() == "quarantined"]
        teks = tanya(joule, "status karantina batch")
        cocok = re.search(r"Ada (\d+) batch berstatus karantina", teks)
        hasil.append(
            (
                "batch karantina",
                cocok.group(1) if cocok else "?",
                str(len(karantina)),
                "OK" if cocok and int(cocok.group(1)) == len(karantina) else "BEDA",
            )
        )

        # 8. limbah (DB demo dipakai bersama: baca sebelum & sesudah tanya) ---------------
        w1 = api.get("/waste/summary").json()["recorded"]
        teks = tanya(joule, "kehilangan pangan minggu ini")
        w2 = api.get("/waste/summary").json()["recorded"]
        cocok = re.search(r"Limbah tercatat:\** ([\d.,]+) kg · (\d+) kejadian", teks)
        if (float(w1["kg"]), w1["events"]) != (float(w2["kg"]), w2["events"]):
            status = "DATA BERGERAK"
        elif cocok and sama(j2f(cocok.group(1)), float(w2["kg"])) and int(cocok.group(2)) == w2["events"]:
            status = "OK"
        else:
            status = "BEDA"
        hasil.append(
            (
                "limbah tercatat",
                f"{cocok.group(1)}/{cocok.group(2)}" if cocok else "?",
                f"{f2id(float(w2['kg']))}/{w2['events']}",
                status,
            )
        )

        # 9. harga satu pasangan ---------------------------------------------------------
        teks = tanya(joule, "berapa harga ayam di Surabaya?")
        lok = api.get("/admin/locations").json()["locations"]
        sid = next(item["id"] for item in lok if item["name"] == "Surabaya")
        harga = api.get(f"/price/{sid}/ayam").json()
        acuan = harga.get("price_per_kg")
        harga2 = api.get(f"/price/{sid}/ayam").json().get("price_per_kg")
        cocok = re.search(r"Rp([\d.]+)", teks)
        if acuan is not None and harga2 is not None and round(float(acuan)) != round(float(harga2)):
            status = "DATA BERGERAK"
        elif cocok and acuan is not None and round(j2f(cocok.group(1)) or -1) == round(float(harga2)):
            status = "OK"
        else:
            status = "BEDA"
        hasil.append(
            (
                "harga acuan Surabaya/ayam",
                cocok.group(0) if cocok else "?",
                f"Rp{float(harga2):,.0f}".replace(",", ".") if harga2 is not None else "—",
                status,
            )
        )

    print(f"{'CEK':32s} {'JOULE':28s} {'API/DB':28s} STATUS")
    for cek, j, a, st in hasil:
        print(f"{cek:32s} {j:28s} {a:28s} {st}")
    gagal = [h for h in hasil if h[3] != "OK"]
    print(f"\n{len(hasil) - len(gagal)}/{len(hasil)} cocok · {len(gagal)} beda")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
