"""Tarik harga pangan harian PIHPS Bank Indonesia → snapshot JSON.

Sumber (bukan API resmi ber-SLA, terverifikasi 28 Okt 2026):
    https://www.bi.go.id/hargapangan  →  /hargapangan/WebSite/TabelHarga/GetGridDataKomoditas

Kenapa snapshot, bukan tabel DB: data ini adalah SALINAN pakan eksternal
(referensi pasar), bukan keadaan operasional. Snapshot membuat panel harga tetap
bisa dibaca saat internet venue mati, dan jejak sumbernya (`source_url` +
`fetched_at`) ikut tersimpan apa adanya. Tabel `price_signals` yang dipakai
mesin keputusan TIDAK disentuh sama sekali.

Pemakaian:
    python -m scripts.tarik_harga_pihps --days 30                 # 8 provinsi demo
    python -m scripts.tarik_harga_pihps --provinsi all --komoditas all
    python -m scripts.tarik_harga_pihps --dry-run                 # cetak ringkasan saja

Keluaran (default):
    data/harga_pihps/pihps_latest.json          ← dibaca backend (`GET /price/monitor`)
    data/harga_pihps/pihps_<tanggal>.json       ← arsip per tanggal tarik
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASIS = "https://www.bi.go.id"
HALAMAN = f"{BASIS}/hargapangan/TabelHarga/PasarTradisionalKomoditas"
REF_KOMODITAS = f"{BASIS}/hargapangan/WebSite/TabelHarga/GetRefCommodityAndCategory"
REF_PROVINSI = f"{BASIS}/hargapangan/WebSite/TabelHarga/GetRefProvince"
DATA_GRID = f"{BASIS}/hargapangan/WebSite/TabelHarga/GetGridDataKomoditas"
SUMBER = "PIHPS Bank Indonesia"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

#: Provinsi yang memuat 10 kota demo MealChain Guardian.
PROVINSI_DEMO = [13, 12, 14, 15, 16, 26, 8, 2]

#: Wilayah yang disimpan. `None` = semua baris tingkat nasional + provinsi.
KOTA_DEMO = [
    "Kota Jakarta Pusat",
    "Kota Bogor",
    "Kota Bandung",
    "Kota Semarang",
    "Kota Yogyakarta",
    "Kota Surabaya",
    "Kota Makassar",
    "Kota Palembang",
    "Kota Medan",
]

#: Komoditas yang dipakai modul MealChain (kode PIHPS). Wortel TIDAK ada di PIHPS.
KOMODITAS_PROYEK = ["com_10", "com_7", "com_3"]

AKAR_REPO = Path(__file__).resolve().parents[2]
KELUARAN_DEFAULT = AKAR_REPO / "data" / "harga_pihps"

JEDA_DETIK = 0.35


class Transport:
    """HTTP ke bi.go.id.

    `curl` dipakai lebih dulu bila ada: permintaan dari TLS stack Python
    direset server (WinError 10054 / ConnectionReset) walau header sudah sama
    dengan peramban — terukur 28 Okt 2026. curl berhasil, jadi transport curl
    adalah jalur utama dan urllib hanya cadangan untuk mesin tanpa curl.
    """

    def __init__(self) -> None:
        self.pakai_curl = shutil.which("curl") is not None
        self._jar_berkas: str | None = None
        self._opener: urllib.request.OpenerDirector | None = None
        if self.pakai_curl:
            berkas = tempfile.NamedTemporaryFile(
                prefix="pihps-cookie-", suffix=".txt", delete=False
            )
            berkas.close()
            self._jar_berkas = berkas.name
        else:
            jar = http.cookiejar.CookieJar()
            self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            self._opener.addheaders = [
                ("User-Agent", UA),
                ("Accept", "application/json, text/plain, */*"),
                ("X-Requested-With", "XMLHttpRequest"),
                ("Referer", HALAMAN),
            ]

    # -- transport ---------------------------------------------------------
    def _ambil(self, url: str) -> bytes:
        if self.pakai_curl:
            perintah = [
                "curl",
                "-sS",
                "--compressed",
                "-m",
                "45",
                "-A",
                UA,
                "-H",
                "Accept: application/json, text/plain, */*",
                "-H",
                "X-Requested-With: XMLHttpRequest",
                "-H",
                f"Referer: {HALAMAN}",
                "-b",
                str(self._jar_berkas),
                "-c",
                str(self._jar_berkas),
                url,
            ]
            hasil = subprocess.run(perintah, capture_output=True, timeout=60)
            if hasil.returncode != 0:
                raise urllib.error.URLError(
                    f"curl keluar {hasil.returncode}: "
                    f"{hasil.stderr.decode('utf-8', 'replace')[:200]}"
                )
            return hasil.stdout
        assert self._opener is not None
        with self._opener.open(url, timeout=45) as jawab:
            return jawab.read()

    def buka_sesi(self) -> None:
        """Ambil cookie sesi dari halaman tabel; endpoint grid menolaknya tanpa itu."""
        self._ambil(HALAMAN)

    def get_json(self, url: str, ulang: int = 2) -> dict:
        for percobaan in range(ulang + 1):
            try:
                return json.loads(self._ambil(url).decode("utf-8", "replace"))
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as galat:
                if percobaan >= ulang:
                    raise RuntimeError(f"gagal menarik {url}: {galat}") from galat
                time.sleep(1.5 * (percobaan + 1))
        raise RuntimeError("tidak tercapai")


def ambil_referensi(transport: Transport) -> tuple[list[dict], list[dict]]:
    komoditas = [
        baris
        for baris in transport.get_json(REF_KOMODITAS).get("data", [])
        if baris.get("cat_id")
    ]
    provinsi = transport.get_json(REF_PROVINSI).get("data", [])
    return komoditas, provinsi


def _angka(teks: object) -> float | None:
    """'25,700' → 25700.0 ; '' / None / '-' → None (bukan 0)."""
    if not isinstance(teks, str):
        return None
    bersih = teks.strip().replace(",", "").replace(".", "")
    if not bersih or not bersih.isdigit():
        return None
    nilai = float(bersih)
    return nilai if nilai > 0 else None


def tarik_komoditas(
    transport: Transport,
    kode: str,
    label: str,
    provinsi_id: int,
    mulai: date,
    selesai: date,
    simpan_kota: set[str],
) -> list[dict]:
    """Satu request = satu komoditas × satu provinsi × rentang tanggal."""
    kueri = urllib.parse.urlencode(
        {
            "price_type_id": 1,
            "comcat_id": kode,
            "province_id": provinsi_id,
            "regency_id": "",
            "showKota": "true",
            "showPasar": "false",
            "tipe_laporan": 1,
            "start_date": mulai.isoformat(),
            "end_date": selesai.isoformat(),
        }
    )
    isi = transport.get_json(f"{DATA_GRID}?{kueri}")
    baris_keluar: list[dict] = []
    for baris in isi.get("data", []):
        level = baris.get("level")
        nama = (baris.get("name") or "").strip()
        # level 0 = nasional, 1 = provinsi, 2 = kota/kabupaten
        if level not in (0, 1, 2):
            continue
        if level == 2 and nama not in simpan_kota:
            continue
        for kunci, nilai in baris.items():
            if kunci in {"no", "name", "level"}:
                continue
            try:
                tanggal = datetime.strptime(kunci, "%d/%m/%Y").date()
            except ValueError:
                continue
            harga = _angka(nilai)
            if harga is None:
                continue  # hari libur / tidak dipublikasikan → sel kosong, bukan 0
            baris_keluar.append(
                {
                    "commodity_code": kode,
                    "commodity_label": label,
                    "region_name": nama,
                    "region_level": {0: "nasional", 1: "provinsi", 2: "kota"}[level],
                    "observed_on": tanggal.isoformat(),
                    "price_per_kg": harga,
                    "source": "pihps_bi",
                }
            )
    return baris_keluar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, default=30, help="rentang hari ke belakang (default 30)"
    )
    parser.add_argument(
        "--provinsi",
        default="demo",
        help="'demo' (8 provinsi kota demo), 'all', atau daftar id dipisah koma",
    )
    parser.add_argument(
        "--komoditas",
        default="all",
        help="'all' (21 komoditas PIHPS), 'proyek' (telur/ayam/beras), atau kode dipisah koma",
    )
    parser.add_argument("--out", default=str(KELUARAN_DEFAULT), help="folder keluaran")
    parser.add_argument("--dry-run", action="store_true", help="jangan tulis berkas")
    args = parser.parse_args(argv)

    selesai = date.today()
    mulai = selesai - timedelta(days=max(args.days, 1))

    opener = Transport()
    opener.buka_sesi()
    komoditas_semua, provinsi_semua = ambil_referensi(opener)
    peta_komoditas = {baris["id"]: baris["name"] for baris in komoditas_semua}
    peta_provinsi = {baris["id"]: baris["name"] for baris in provinsi_semua}

    # ---- pilih komoditas
    if args.komoditas == "all":
        kode_komoditas = [b["id"] for b in komoditas_semua]
    elif args.komoditas == "proyek":
        kode_komoditas = list(KOMODITAS_PROYEK)
    else:
        kode_komoditas = [k.strip() for k in args.komoditas.split(",") if k.strip()]
    tak_dikenal = [k for k in kode_komoditas if k not in peta_komoditas]
    if tak_dikenal:
        print(f"komoditas tidak dikenal: {tak_dikenal}", file=sys.stderr)
        return 2

    # ---- pilih provinsi
    if args.provinsi == "demo":
        id_provinsi = list(PROVINSI_DEMO)
    elif args.provinsi == "all":
        id_provinsi = [b["id"] for b in provinsi_semua]
    else:
        id_provinsi = [int(x) for x in args.provinsi.split(",") if x.strip()]
    tak_dikenal = [p for p in id_provinsi if p not in peta_provinsi]
    if tak_dikenal:
        print(f"provinsi tidak dikenal: {tak_dikenal}", file=sys.stderr)
        return 2

    simpan_kota = set(KOTA_DEMO)
    baris: list[dict] = []
    permintaan = 0
    for provinsi_id in id_provinsi:
        for kode in kode_komoditas:
            permintaan += 1
            baris.extend(
                tarik_komoditas(
                    opener,
                    kode,
                    peta_komoditas[kode],
                    provinsi_id,
                    mulai,
                    selesai,
                    simpan_kota,
                )
            )
            time.sleep(JEDA_DETIK)

    # ---- buang duplikat (baris nasional muncul di setiap provinsi)
    unik: dict[tuple, dict] = {}
    for item in baris:
        kunci = (item["commodity_code"], item["region_name"], item["observed_on"])
        unik[kunci] = item
    baris = sorted(
        unik.values(),
        key=lambda r: (r["commodity_code"], r["region_name"], r["observed_on"]),
    )

    wilayah = sorted({(r["region_level"], r["region_name"]) for r in baris})
    tanggal_terisi = sorted({r["observed_on"] for r in baris})
    per_komoditas: dict[str, int] = {}
    for r in baris:
        per_komoditas[r["commodity_code"]] = per_komoditas.get(r["commodity_code"], 0) + 1

    snap = {
        "sumber": SUMBER,
        "source_url": HALAMAN,
        "endpoint": DATA_GRID,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": mulai.isoformat(), "end": selesai.isoformat()},
        "jenis_pasar": "Pasar Tradisional",
        "satuan": "Rp/kg",
        "komoditas": [
            {"code": k, "label": peta_komoditas[k]} for k in kode_komoditas
        ],
        "provinsi_diminta": [peta_provinsi[p] for p in id_provinsi],
        "wilayah": [{"level": lv, "name": nm} for lv, nm in wilayah],
        "tanggal_terisi": tanggal_terisi,
        "rows": baris,
    }

    print(f"permintaan: {permintaan} | baris: {len(baris)} | wilayah: {len(wilayah)}")
    print(f"rentang: {mulai} → {selesai} | tanggal berisi data: {len(tanggal_terisi)}")
    rincian = ", ".join(f"{peta_komoditas[k]}={v}" for k, v in sorted(per_komoditas.items()))
    print(f"per komoditas: {rincian}")
    contoh = [r for r in baris if r["region_level"] == "kota"][:3]
    for c in contoh:
        print(
            f"  {c['observed_on']} {c['region_name']:<22} "
            f"{c['commodity_label']:<26} Rp {c['price_per_kg']:,.0f}"
        )

    if args.dry_run:
        print("(--dry-run) tidak ada berkas ditulis")
        return 0

    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    terbaru = folder / "pihps_latest.json"
    arsip = folder / f"pihps_{selesai.isoformat()}.json"
    teks = json.dumps(snap, ensure_ascii=False, indent=1)
    terbaru.write_text(teks, encoding="utf-8")
    arsip.write_text(teks, encoding="utf-8")
    print(f"ditulis: {terbaru} ({terbaru.stat().st_size // 1024} KB)")
    print(f"arsip  : {arsip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
