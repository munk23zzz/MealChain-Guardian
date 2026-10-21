"""Perender markdown untuk jawaban Joule — fungsi murni: tanpa I/O, tanpa database, tanpa LLM.

Bentuk data yang dirender di sini adalah bentuk backend klon (a) `mealchain-guardian` v0.2.0
(ganti garis 2026-10-11 dari `/ui/*` v0.1.0):

* `/batches`     — inventaris batch: lokasi, komoditas, kg, keamanan, kesegaran, masa pakai.
* `/balance/map` — pasokan/kebutuhan/surplus/kurang per lokasi untuk satu komoditas.
* `/kpi`         — `metrics[{name, unit, state, value, reason}]`.
* `/decisions` + `/decisions/{id}/approval-summary` — antrean usulan lengkap asal→tujuan.

Aturan modul ini:

* **Tidak ada aritmetika.** Semua angka datang dari respons backend apa adanya (`Rules.md` §1.1).
  Yang dilakukan di sini hanya memformat, menyusun tabel, dan mengurutkan.
* **Tidak ada angka karangan.** Nilai yang tidak dikirim backend ditampilkan sebagai `—`.
  Khusus kesegaran, modul ini TIDAK mengubah `freshness_score` menjadi pita
  fresh/mendekati/kedaluwarsa — ambang pita itu milik backend, bukan milik perender.
* **Format angka Indonesia**: pemisah ribuan titik, desimal koma.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Callable, Mapping, Sequence

MISSING = "—"

#: Nama bulan Indonesia pendek — dipakai `wib()` untuk tanggal PO.
BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

#: WIB = UTC+7 tanpa DST (Indonesia tidak memakai DST). Offset tetap, bukan hitungan.
WIB = _dt.timezone(_dt.timedelta(hours=7), "WIB")

#: Label Indonesia untuk status yang dikirim backend (Inggris di API).
SUPPLY_STATUS_LABEL = {
    "shortage": "KURANG",
    "deficit": "KURANG",
    "surplus": "LEBIH",
    "balanced": "SEIMBANG",
}
SAFETY_LABEL = {
    "pass": "lolos",
    "fail": "GAGAL",
    "needs_verification": "perlu verifikasi",
    # Nilai huruf besar dari backend versi lama tetap dikenali supaya laporan tidak
    # menampilkan istilah API mentah.
    "PASS": "lolos",
    "FAIL": "GAGAL",
    "NEEDS_VERIFICATION": "perlu verifikasi",
}
DECISION_TYPE_LABEL = {
    "regional_balance": "penyeimbangan wilayah",
    "price_anomaly": "anomali harga",
    "safety_disruption": "gangguan keamanan pangan",
    "supplier_exclusion": "eksklusi supplier",
}
#: Urutan prioritas: yang kurang tampil lebih dulu (paling butuh perhatian).
_STATUS_RANK = {"shortage": 0, "deficit": 0, "balanced": 1, "surplus": 2}
#: Status keputusan yang belum tuntas.
UNFINISHED_STATUS = frozenset(
    {"proposed", "pending_approval", "verified", "approved", "verifier_flagged"}
)


# --- pemformat angka ---------------------------------------------------------------------


def num(value: Any, digits: int = 1) -> str:
    """Angka gaya Indonesia: `1234.5` -> `1.234,5`. Nilai bukan angka -> `—`."""
    if value is None or isinstance(value, bool):
        return MISSING
    try:
        number = float(value)
    except (TypeError, ValueError):
        return MISSING
    text = (
        f"{number:,.{digits}f}"
        .replace(",", "\u0000")
        .replace(".", ",")
        .replace("\u0000", ".")
    )
    if digits > 0 and text.endswith(",0"):
        text = text[: -len(",0")]
    return text


def kg(value: Any) -> str:
    return f"{num(value)} kg" if num(value) != MISSING else MISSING


def rupiah(value: Any) -> str:
    """Rupiah tanpa desimal (angka besar tidak perlu koma di layar chat)."""
    if value is None:
        return MISSING
    return f"Rp{num(value, digits=0)}"


def percent(value: Any) -> str:
    """Persen dua desimal tanpa nol berekor: `74.95` -> `74,95%`, `96.4` -> `96,4%`."""
    teks = num(value, digits=2)
    return MISSING if teks == MISSING else f"{_trim(teks)}%"


def minutes(value: Any) -> str:
    teks = num(value, digits=2)
    return MISSING if teks == MISSING else f"{_trim(teks)} menit"


def _trim(teks: str) -> str:
    """Buang nol tak bermakna di belakang koma: `96,40` -> `96,4`, `12,00` -> `12`."""
    if "," in teks:
        teks = teks.rstrip("0").rstrip(",")
    return teks


#: Pemformat per satuan dari `/kpi` (backend: percent, IDR, minutes, …).
UNIT_FORMATTER: dict[str, Callable[[Any], str]] = {
    "percent": percent,
    "%": percent,
    "kg": kg,
    "idr": rupiah,
    "rp": rupiah,
    "minutes": minutes,
    "minute": minutes,
    "menit": minutes,
}


def format_metric(value: Any, unit: Any) -> str:
    """Format nilai metrik sesuai satuan yang dikirim backend.

    Satuan yang tidak dikenal ditampilkan sebagai angka apa adanya, TIDAK dipaksa menjadi
    satuan yang kita kenal — satuan salah lebih berbahaya daripada satuan yang jujur mentah.
    """
    formatter = UNIT_FORMATTER.get(str(unit or "").strip().lower())
    if formatter is None:
        teks = num(value, digits=2)
        return MISSING if teks == MISSING else _trim(teks)
    return formatter(value)


def _text(value: Any) -> str:
    if value is None or value == "":
        return MISSING
    return str(value)


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _footnote(lines: Sequence[str | None]) -> str:
    return "\n".join(f"_{line}_" for line in lines if line)


def _cap(rows: Sequence[Any], limit: int) -> tuple[list[Any], str | None]:
    """Batasi jumlah baris dan kembalikan catatan sisa — supaya tidak ada yang disembunyikan."""
    if limit and limit > 0 and len(rows) > limit:
        return list(rows[:limit]), f"{len(rows) - limit} baris lain tidak ditampilkan."
    return list(rows), None


# --- situasi pasokan ---------------------------------------------------------------------


def supply_report(
    batches: Sequence[Mapping[str, Any]] | None,
    balance: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    limit: int = 12,
    note: str | None = None,
) -> str:
    """Situasi pasokan: keseimbangan per lokasi (`/balance/map`) + inventaris batch (`/batches`).

    Sengaja DUA tabel, bukan satu yang digabung: keseimbangan dihitung backend per
    (lokasi, komoditas), sedangkan keamanan & kesegaran melekat pada batch. Menggabungkannya
    berarti perender ini harus memilih satu nilai agregat — itu perhitungan, dan perhitungan
    bukan tugasnya.
    """
    batch_rows = list(batches or ())
    balance_by_commodity = balance or {}

    balance_rows: list[tuple[int, str, list[str]]] = []
    for commodity in sorted(balance_by_commodity):
        payload = balance_by_commodity[commodity] or {}
        commodity_name = payload.get("commodity") or commodity
        for row in payload.get("locations") or ():
            status = str(row.get("status") or "")
            location = _text(row.get("location"))
            shortage = row.get("shortage_kg")
            surplus = row.get("surplus_kg")
            if isinstance(shortage, (int, float)) and shortage > 0:
                selisih = f"kurang {kg(shortage)}"
            elif isinstance(surplus, (int, float)) and surplus > 0:
                selisih = f"lebih {kg(surplus)}"
            elif shortage is None and surplus is None:
                selisih = MISSING
            else:
                selisih = "seimbang"
            balance_rows.append(
                (
                    _STATUS_RANK.get(status, 3),
                    f"{location} {commodity_name}",
                    [
                        location,
                        _text(commodity_name),
                        kg(row.get("supply_kg")),
                        kg(row.get("demand_kg")),
                        selisih,
                        SUPPLY_STATUS_LABEL.get(status, _text(status)),
                    ],
                )
            )
    balance_rows.sort(key=lambda item: (item[0], item[1]))

    if not balance_rows and not batch_rows:
        return (
            "Belum ada data pasokan yang dikirim backend MealChain.\n\n"
            + _footnote([note or "sumber: GET /batches + GET /balance/map"])
        )

    bagian: list[str] = []
    sisa: list[str] = []

    if balance_rows:
        tampil, catatan_sisa = _cap(balance_rows, limit)
        bagian.append(
            f"Keseimbangan pasokan per lokasi ({len(balance_rows)} baris), "
            "yang kurang ditampilkan lebih dulu:\n\n"
            + _table(
                ["SPPG", "Komoditas", "Pasokan", "Kebutuhan", "Selisih", "Status"],
                [row for _, _, row in tampil],
            )
        )
        if catatan_sisa:
            sisa.append(catatan_sisa)

    if batch_rows:
        def urut_batch(row: Mapping[str, Any]) -> tuple[int, str, str]:
            keamanan = str(row.get("safety_status") or "").lower()
            return (
                0 if keamanan == "fail" else 1,
                str(row.get("usable_until") or "~"),
                str(row.get("location") or ""),
            )

        tersortir = sorted(batch_rows, key=urut_batch)
        tampil_batch, catatan_batch = _cap(tersortir, limit)
        bagian.append(
            f"Inventaris batch ({len(batch_rows)} batch):\n\n"
            + _table(
                ["SPPG", "Komoditas", "Jumlah", "Keamanan", "Skor kesegaran", "Boleh dipakai sampai"],
                [
                    [
                        _text(row.get("location")),
                        _text(row.get("commodity")),
                        kg(row.get("quantity_kg")),
                        SAFETY_LABEL.get(str(row.get("safety_status")), _text(row.get("safety_status"))),
                        num(row.get("freshness_score"), digits=2),
                        _text(row.get("usable_until")),
                    ]
                    for row in tampil_batch
                ],
            )
        )
        if catatan_batch:
            sisa.append(catatan_batch)

    return "\n\n".join(bagian) + "\n\n" + _footnote(
        [
            note,
            "Sumber angka: backend MealChain `GET /batches` + `GET /balance/map` "
            "(dihitung modul deterministik backend, bukan oleh model bahasa).",
            "Kesegaran ditampilkan sebagai skor mentah dari backend; ambang pita kesegaran "
            "milik backend dan tidak ditaksir ulang di sini.",
            *sisa,
        ]
    )


# --- direktori pemasok -------------------------------------------------------------------


def supplier_directory_report(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 25,
    note: str | None = None,
) -> str:
    """Direktori pemasok per SPPG: hub, komoditas, keandalan, kapasitas, kiriman aktif.

    Satu baris = satu pemasok seperti dikirim `GET /suppliers`. Jarak, kelayakan, dan
    skor TIDAK ditaksir di sini — nilainya datang dari backend. `excluded_at_hub`
    ditampilkan sebagai penanda, bukan disaring diam-diam: direktori memang daftar
    sumber, dan konteks eksklusi berguna bagi manusia yang membacanya.
    """
    pemasok = list(rows or ())
    if not pemasok:
        return (
            "Belum ada data pemasok yang dikirim backend MealChain.\n\n"
            + _footnote([note or "sumber: GET /suppliers"])
        )

    def urut(row: Mapping[str, Any]) -> tuple[str, str]:
        return (str(row.get("location") or ""), str(row.get("name") or ""))

    tampil, sisa = _cap(sorted(pemasok, key=urut), limit)
    baris: list[list[str]] = []
    for row in tampil:
        jumlah = row.get("shippingCount")
        if jumlah is None:
            kiriman = "belum mengirim"
        else:
            kiriman = f"{jumlah} batch"
            if row.get("shippingKg") is not None:
                kiriman += f" · {kg(row.get('shippingKg'))}"
        if row.get("excludedAtHub"):
            kiriman += " · dikecualikan di hub"
        baris.append(
            [
                _text(row.get("name")),
                _text(row.get("location")),
                _text(row.get("commodity")),
                num(row.get("reliability"), digits=2),
                kg(row.get("capacityKgPerWeek")),
                kiriman,
            ]
        )

    return (
        f"Direktori pemasok ({len(pemasok)} pemasok, dikelompokkan per SPPG):\n\n"
        + _table(
            ["Pemasok", "SPPG", "Komoditas", "Keandalan", "Kapasitas/minggu", "Kiriman aktif"],
            baris,
        )
        + "\n\n"
        + _footnote(
            [
                note,
                "Sumber: backend MealChain `GET /suppliers` (baca-saja; Joule tidak menghitung ulang).",
                "Pemasok tanpa baris kiriman berarti terdaftar tetapi belum/tidak sedang mengirim — "
                "bukan nol karangan.",
                sisa,
            ]
        )
    )


# --- KPI ----------------------------------------------------------------------------------


def kpi_report(envelope: Mapping[str, Any] | None, *, note: str | None = None) -> str:
    """Daftar KPI dari `/kpi`. Metrik yang tidak bisa dihitung ditampilkan `—` + alasannya."""
    metrics = list((envelope or {}).get("metrics") or ())
    if not metrics:
        return (
            "Belum ada metrik KPI yang dikirim backend MealChain.\n\n"
            + _footnote([note or "sumber: GET /kpi"])
        )

    rows: list[list[str]] = []
    belum = 0
    for metric in metrics:
        name = _text(metric.get("name"))
        state = str(metric.get("state") or "").strip().lower()
        if state == "available" and metric.get("value") is not None:
            rows.append([name, format_metric(metric.get("value"), metric.get("unit"))])
        else:
            alasan = _text(metric.get("reason")) if metric.get("reason") else MISSING
            rows.append([name, f"{MISSING} ({alasan})"])
            belum += 1

    return (
        f"Indikator kinerja MealChain Guardian ({len(metrics)} metrik, angka dari backend):\n\n"
        + _table(["Indikator", "Nilai"], rows)
        + "\n\n"
        + _footnote(
            [
                note,
                f"{belum} indikator belum bisa dihitung dan ditandai alasannya, bukan diisi nol.",
                "Sumber: GET /kpi (jendela waktu diminta oleh jembatan).",
            ]
        )
    )


# --- antrean usulan ----------------------------------------------------------------------


def approval_queue_report(
    decisions: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 12,
    note: str | None = None,
) -> str:
    """Antrean usulan keputusan — untuk dilihat manusia, bukan disetujui agen.

    Baris datang dari `/decisions` yang sudah dilengkapi `/decisions/{id}/approval-summary`
    oleh klien; karena itu asal→tujuan dan komoditas sudah berupa NAMA, bukan id.
    """
    items = list(decisions or ())
    if not items:
        return (
            "Belum ada usulan keputusan di MealChain Guardian.\n\n"
            + _footnote([note or "sumber: GET /decisions"])
        )

    items.sort(
        key=lambda row: (
            0 if str(row.get("status")) in UNFINISHED_STATUS else 1,
            str(row.get("id")),
        )
    )
    tampil, catatan_sisa = _cap(items, limit)

    rows = [
        [
            _text(row.get("id")),
            DECISION_TYPE_LABEL.get(str(row.get("decisionType")), _text(row.get("decisionType"))),
            f"{_text(row.get('sourceLocation'))} → {_text(row.get('targetLocation'))}",
            _text(row.get("commodity")),
            kg(row.get("quantityKg")),
            _text(row.get("status")),
        ]
        for row in tampil
    ]
    body = _table(["ID", "Jenis", "Asal → tujuan", "Komoditas", "Jumlah", "Status"], rows)

    return (
        f"Antrean usulan keputusan MealChain Guardian ({len(items)} baris):\n\n"
        f"{body}\n\n"
        + _footnote(
            [
                note,
                "Persetujuan TIDAK bisa dilakukan dari Joule: approver menekan Setuju di UI "
                "MealChain dengan tokennya sendiri (Rules.md §1.2 — tidak ada auto-execute).",
                "Sumber: GET /decisions + GET /decisions/{id}/approval-summary.",
                catatan_sisa,
            ]
        )
    )


# --- purchase order (tabel mock SAP) ------------------------------------------------------

PO_STATUS_LABEL = {
    "draft": "rancangan",
    "submitted": "terkirim",
    "confirmed": "dikonfirmasi",
}
DECISION_STATUS_LABEL = {
    "proposed": "usulan",
    "verifier_flagged": "ditandai verifikator",
    "pending_approval": "menunggu persetujuan",
    "approved": "disetujui",
    "rejected": "ditolak",
    "executed": "dieksekusi",
    "review_only": "tinjauan saja",
}
ORIGIN_LABEL = {
    "execution": "lahir dari eksekusi keputusan",
    "demo": "baris impor SAP (tanpa keputusan)",
}


def wib(timestamp: Any) -> str:
    """ISO-8601 dari backend → `20 Okt 2026 09.20 WIB`.

    WIB = UTC+7 tanpa DST (Indonesia tidak memakai DST), jadi offset tetap ini hanya
    penandaan zona — bukan perhitungan atas data. Nilai yang tidak terbaca dikembalikan
    apa adanya supaya waktu karangan tidak pernah muncul.
    """
    teks = str(timestamp or "").strip()
    if not teks:
        return MISSING
    try:
        saat = _dt.datetime.fromisoformat(teks.replace("Z", "+00:00"))
    except ValueError:
        return teks
    if saat.tzinfo is None:  # backend selalu mengirim offset; kalau tidak, jangan menebak zona
        return teks
    lokal = saat.astimezone(WIB)
    return (
        f"{lokal.day} {BULAN[lokal.month - 1]} {lokal.year} "
        f"{lokal.hour:02d}.{lokal.minute:02d} WIB"
    )


def _label(peta: Mapping[str, str], value: Any) -> str:
    """Label Indonesia bila dikenal; nilai mentah bila tidak — istilah API tidak disembunyikan."""
    teks = str(value or "").strip()
    if not teks:
        return MISSING
    return peta.get(teks, teks)


def _po_detail(po: Mapping[str, Any], *, jumlah_terbaca: int, note: str | None) -> str:
    """Satu PO sebagai daftar kolom→nilai (bukan tabel selebar layar chat)."""
    keputusan = _text(po.get("decisionId"))
    if keputusan != MISSING:
        keputusan = f"{keputusan} — {_label(DECISION_STATUS_LABEL, po.get('decisionStatus'))}"
    baris = [
        ("Status PO", _label(PO_STATUS_LABEL, po.get("status"))),
        ("Dibuat", wib(po.get("createdAt"))),
        ("Lokasi tujuan", _text(po.get("locationName"))),
        ("Pemasok", _text(po.get("supplierName"))),
        ("Bahan", _text(po.get("commodityName"))),
        ("Nomor material SAP", _text(po.get("materialNumber"))),
        ("Jumlah", kg(po.get("quantityKg"))),
        ("Harga per kg", rupiah(po.get("pricePerKg"))),
        ("Total nilai", rupiah(po.get("totalValue"))),
        ("Keputusan", keputusan),
        ("Asal baris", _label(ORIGIN_LABEL, po.get("origin"))),
    ]
    isi = "\n".join(f"- **{judul}:** {nilai}" for judul, nilai in baris)
    return (
        f"Purchase order {_text(po.get('poNumber'))}\n\n"
        f"{isi}\n\n"
        + _footnote(
            [
                note,
                f"Sumber: GET /sap/purchase-orders (tabel mock SAP di backend) — 1 dari "
                f"{jumlah_terbaca} PO yang terbaca akun baca ini.",
                "Angka ditampilkan apa adanya; total nilai dihitung backend, bukan oleh jembatan.",
                "Dokumen PDF PO diunduh dari UI MealChain (tab Decision & Evidence) setelah "
                "keputusan disetujui — Joule hanya mengirim teks, tidak melampirkan berkas.",
            ]
        )
    )


def purchase_order_report(
    orders: Sequence[Mapping[str, Any]] | None,
    *,
    po_number: str | None = None,
    limit: int = 10,
    note: str | None = None,
) -> str:
    """Daftar purchase order mock SAP, atau satu PO bila nomornya disebut.

    Baris datang dari `/sap/purchase-orders` (read-only, cakupan akun `bgn_monitor` =
    nasional). Nomor PO dicocokkan PERSIS — tidak ada pencarian samar yang bisa menampilkan
    PO lain seolah-olah yang diminta.
    """
    items = list(orders or ())
    dicari = (po_number or "").strip().upper()
    if dicari:
        cocok = [row for row in items if str(row.get("poNumber") or "").upper() == dicari]
        if not cocok:
            return (
                f"Purchase order {dicari} tidak ditemukan di antara {len(items)} PO yang "
                "terbaca akun baca ini.\n\n"
                + _footnote(
                    [
                        note,
                        "Sumber: GET /sap/purchase-orders (tabel mock SAP di backend).",
                        "Nomor yang tidak terdaftar, atau PO di luar cakupan akun baca, tidak "
                        "akan muncul di sini — bukan berarti PO-nya fiktif.",
                    ]
                )
            )
        return _po_detail(cocok[0], jumlah_terbaca=len(items), note=note)

    if not items:
        return (
            "Belum ada purchase order yang terbaca di MealChain Guardian.\n\n"
            + _footnote([note or "sumber: GET /sap/purchase-orders"])
        )

    tampil, catatan_sisa = _cap(items, limit)
    rows = [
        [
            _text(row.get("poNumber")),
            _label(PO_STATUS_LABEL, row.get("status")),
            _text(row.get("locationName")),
            _text(row.get("commodityName")),
            kg(row.get("quantityKg")),
            rupiah(row.get("totalValue")),
            _label(DECISION_STATUS_LABEL, row.get("decisionStatus"))
            if row.get("decisionId")
            else "impor SAP",
        ]
        for row in tampil
    ]
    body = _table(
        ["Nomor PO", "Status", "Lokasi tujuan", "Bahan", "Jumlah", "Total", "Keputusan"],
        rows,
    )
    return (
        f"Purchase order MealChain Guardian ({len(items)} PO terbaca):\n\n"
        f"{body}\n\n"
        + _footnote(
            [
                note,
                "Sumber: GET /sap/purchase-orders (tabel mock SAP di backend), urutan "
                "terbaru lebih dulu — angka apa adanya, tanpa hitung ulang di jembatan.",
                "Sebut satu nomor PO (mis. `PO MC-661695B2C685`) untuk melihat rinciannya.",
                catatan_sisa,
            ]
        )
    )


# --- harga & kuotasi ---------------------------------------------------------------------

PRICE_SOURCE_LABEL = {
    "pihps_reference": "acuan PIHPS",
    "price_signal": "sinyal harga",
    "mock_sap": "mock SAP",
    "mock": "mock",
}
#: Metode prakiraan kebutuhan: label Indonesia; nilai tak dikenal tampil apa adanya.
FORECAST_METHOD_LABEL = {
    "statistical_fallback": "fallback statistik (model peramal tidak dipakai)",
    "sap_rpt": "SAP-RPT-1.6",
    "sap_rpt_1_6": "SAP-RPT-1.6",
    "moving_average": "rata-rata bergerak",
}
EXCLUSION_STATUS_LABEL = {"active": "AKTIF", "revoked": "dicabut", "proposed": "diusulkan"}
#: Kuotasi yang ditampilkan per pasangan (SPPG, komoditas) sebelum dipotong `_cap`.
QUOTE_ROWS_PER_PAIR = 3


def _kg_events(blok: Any) -> str:
    """`{available, kg, events}` → `631,5 kg · 86 kejadian`; tidak tersedia disebut alasannya."""
    if not isinstance(blok, Mapping):
        return MISSING
    if blok.get("available") is False:
        alasan = blok.get("reason")
        return f"{MISSING} ({_text(alasan) if alasan else 'tidak tersedia'})"
    teks = kg(blok.get("kg"))
    jumlah = blok.get("events")
    if jumlah is None:
        return teks
    return f"{teks} · {_text(jumlah)} kejadian"


def price_report(
    prices: Sequence[Mapping[str, Any]] | None,
    quote_payloads: Sequence[Mapping[str, Any]] | None = None,
    *,
    limit: int = 12,
    note: str | None = None,
) -> str:
    """Harga acuan + kuotasi pemasok per SPPG & komoditas.

    Dua tabel: harga acuan (`/price/…`, satu baris per pasangan) dan kuotasi pemasok
    (`/price/quotes/…`). Jembatan tidak menghitung termurah, rata-rata, atau simpangan —
    angka turunan seperti itu milik modul deterministik backend.
    """
    baris_harga = list(prices or ())
    bagian: list[str] = []
    sisa: list[str] = []

    if baris_harga:
        urut = sorted(
            baris_harga,
            key=lambda r: (str(r.get("location") or ""), str(r.get("commodity") or "")),
        )
        tampil, catatan = _cap(urut, limit)
        bagian.append(
            f"Harga acuan per SPPG dan komoditas ({len(baris_harga)} pasangan terbaca):\n\n"
            + _table(
                ["SPPG", "Komoditas", "Harga per kg", "Sumber", "Dicatat"],
                [
                    [
                        _text(r.get("location")),
                        _text(r.get("commodity")),
                        rupiah(r.get("price_per_kg")),
                        _label(PRICE_SOURCE_LABEL, r.get("source")),
                        wib(r.get("recorded_at")),
                    ]
                    for r in tampil
                ],
            )
        )
        if catatan:
            sisa.append(catatan)

    kuotasi: list[list[str]] = []
    for payload in quote_payloads or ():
        for quote in list(payload.get("quotes") or ())[:QUOTE_ROWS_PER_PAIR]:
            kuotasi.append(
                [
                    _text(quote.get("supplier_name")),
                    _text(payload.get("location")),
                    _text(payload.get("commodity")),
                    rupiah(quote.get("price_per_kg")),
                    wib(quote.get("recorded_at")),
                ]
            )
    if kuotasi:
        tampil_kuotasi, catatan_kuotasi = _cap(kuotasi, limit)
        bagian.append(
            f"Kuotasi pemasok terbaru ({len(kuotasi)} kuotasi, yang terbaru lebih dulu):\n\n"
            + _table(
                ["Pemasok", "SPPG", "Komoditas", "Harga per kg", "Dicatat"],
                tampil_kuotasi,
            )
        )
        if catatan_kuotasi:
            sisa.append(catatan_kuotasi)

    if not bagian:
        return "Belum ada data harga yang dikirim backend MealChain.\n\n" + _footnote(
            [note or "sumber: GET /price/{lokasi}/{komoditas}"]
        )

    return "\n\n".join(bagian) + "\n\n" + _footnote(
        [
            note,
            "Sumber: `GET /price/…` + `GET /price/quotes/…` — harga apa adanya dari backend; "
            "jembatan tidak menghitung termurah atau rata-rata.",
            "Komoditas tanpa baris harga tidak diisi nol: kekosongan berarti backend belum "
            "punya sinyal harga untuk pasangan itu.",
            *sisa,
        ]
    )


# --- kebutuhan & prakiraan ---------------------------------------------------------------


def demand_report(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 12,
    note: str | None = None,
) -> str:
    """Kebutuhan per SPPG & komoditas beserta prakiraan dari model backend.

    `method` ditampilkan apa adanya: `statistical_fallback` berarti model peramal tidak
    dipakai, dan pembaca harus tahu itu — bukan disamarkan sebagai angka pasti.
    """
    data = list(rows or ())
    if not data:
        return "Belum ada data kebutuhan yang dikirim backend MealChain.\n\n" + _footnote(
            [note or "sumber: GET /demand/{lokasi}/{komoditas}"]
        )

    urut = sorted(
        data, key=lambda r: (str(r.get("location") or ""), str(r.get("commodity") or ""))
    )
    tampil, sisa = _cap(urut, limit)
    baris = [
        [
            _text(r.get("location")),
            _text(r.get("commodity")),
            kg(r.get("quantityKg")),
            wib(r.get("neededBy")),
            kg(r.get("forecastKg")),
            _label(FORECAST_METHOD_LABEL, r.get("forecastMethod")),
            num(r.get("confidence"), digits=2),
        ]
        for r in tampil
    ]
    return (
        f"Kebutuhan dan prakiraan per SPPG ({len(data)} pasangan terbaca):\n\n"
        + _table(
            [
                "SPPG",
                "Komoditas",
                "Kebutuhan",
                "Diperlukan sampai",
                "Prakiraan",
                "Metode prakiraan",
                "Keyakinan (0–1)",
            ],
            baris,
        )
        + "\n\n"
        + _footnote(
            [
                note,
                "Sumber: `GET /demand/…` + `GET /demand/forecast/…` (angka dari backend; "
                "jembatan tidak meramal dan tidak menghitung ulang).",
                "`fallback statistik` berarti model peramal SAP tidak dipakai untuk pasangan "
                "itu — prakiraannya tetap angka backend, bukan tebakan jembatan.",
                sisa,
            ]
        )
    )


# --- kehilangan pangan -------------------------------------------------------------------


def food_loss_report(summary: Mapping[str, Any] | None, *, note: str | None = None) -> str:
    """Limbah pangan: tercatat, dialihkan ke mitra, dan yang belum punya mitra.

    Tiga angka dipisah karena artinya berbeda: `recorded` = seluruh limbah tercatat,
    `diverted` = punya mitra pengolahan, `unassigned` = tercatat tanpa mitra. Jembatan
    menampilkan ketiganya apa adanya dan tidak menjumlah ulang.
    """
    data = summary or {}
    if not data:
        return "Belum ada ringkasan limbah yang dikirim backend MealChain.\n\n" + _footnote(
            [note or "sumber: GET /waste/summary"]
        )

    periode = data.get("period") or {}
    scope = data.get("scope") or {}
    lokasi = scope.get("locations") or []
    ringkas = [
        ("Limbah tercatat", _kg_events(data.get("recorded"))),
        ("Dialihkan ke mitra", _kg_events(data.get("diverted"))),
        ("Tercatat tanpa mitra", _kg_events(data.get("unassigned"))),
        ("Periode", f"{wib(periode.get('start'))} – {wib(periode.get('end'))} ({_text(periode.get('days'))} hari)"),
        ("Cakupan", f"{_text(scope.get('role'))} · {len(lokasi)} SPPG"),
        ("Dihitung pada", wib(data.get("computed_at"))),
    ]
    isi = "\n".join(f"- **{judul}:** {nilai}" for judul, nilai in ringkas)

    mitra = list(data.get("partners") or ())
    bagian_mitra = ""
    if mitra:
        bagian_mitra = "\n\nMitra pengalihan limbah:\n\n" + _table(
            ["Mitra", "Jumlah", "Kejadian"],
            [
                [_text(m.get("name")), kg(m.get("kg")), _text(m.get("events"))]
                for m in mitra
            ],
        )

    return (
        "Kehilangan pangan dan pengalihannya (MealChain Guardian)\n\n"
        f"{isi}{bagian_mitra}\n\n"
        + _footnote(
            [
                note,
                "Sumber: `GET /waste/summary` (tabel `disposal_events`) — angka dihitung "
                "backend, jembatan hanya memformat.",
                "Tanpa mitra artinya limbah tercatat tetapi belum dialihkan ke pengolahan — "
                "bukan berarti dibuang; backend tidak menyimpulkan hal itu.",
            ]
        )
    )


# --- risiko pemasok & rute kiriman -------------------------------------------------------


def supplier_risk_report(
    exclusions: Sequence[Mapping[str, Any]] | None,
    routes: Mapping[str, Any] | None = None,
    *,
    limit: int = 12,
    note: str | None = None,
) -> str:
    """Eksklusi pemasok di hub + kiriman aktif beserta rute jalannya.

    Baris eksklusi datang dari `/supplier-exclusions`; nama pemasok & SPPG diisi `server.py`
    dari direktori backend (bukan tabel nama yang ditanam di jembatan). Rute berasal dari
    `/supplier-routes`: jarak jalan, durasi, dan keadaan perjalanan semuanya angka backend.
    """
    bagian: list[str] = []
    sisa: list[str] = []

    daftar = list(exclusions or ())
    if daftar:
        urut = sorted(
            daftar,
            key=lambda r: (0 if str(r.get("status")) == "active" else 1, str(r.get("supplierName") or "")),
        )
        tampil, catatan = _cap(urut, limit)
        bagian.append(
            f"Eksklusi pemasok di hub ({len(daftar)} baris):\n\n"
            + _table(
                ["Pemasok", "SPPG", "Status", "Alasan", "Aktif sejak", "Dicabut"],
                [
                    [
                        _text(r.get("supplierName") or r.get("supplier_id")),
                        _text(r.get("scopeLocationName") or r.get("scope_location_id")),
                        _label(EXCLUSION_STATUS_LABEL, r.get("status")),
                        _text(r.get("reason")),
                        wib(r.get("activated_at")),
                        wib(r.get("revoked_at")),
                    ]
                    for r in tampil
                ],
            )
        )
        if catatan:
            sisa.append(catatan)

    payload_rute = routes or {}
    daftar_rute = list(payload_rute.get("routes") or ())
    if daftar_rute:
        tampil_rute, catatan_rute = _cap(daftar_rute, limit)
        bagian.append(
            f"Kiriman aktif dan rutenya ({len(daftar_rute)} kiriman):\n\n"
            + _table(
                [
                    "Pemasok",
                    "Tujuan",
                    "Komoditas",
                    "Jumlah",
                    "Jarak jalan",
                    "Durasi",
                    "Perjalanan",
                ],
                [
                    [
                        _text(r.get("supplierName")),
                        _text(r.get("destinationName")),
                        _text(r.get("commodity")),
                        kg(r.get("quantityKg")),
                        f"{num(r.get('roadKm'))} km" if r.get("roadKm") is not None else MISSING,
                        f"{num(r.get('roadMinutes'))} menit"
                        if r.get("roadMinutes") is not None
                        else MISSING,
                        _text(r.get("journeyState")),
                    ]
                    for r in tampil_rute
                ],
            )
        )
        if catatan_rute:
            sisa.append(catatan_rute)

        ringkasan = payload_rute.get("summary") or {}
        if ringkasan:
            keadaan = ringkasan.get("journey_states") or {}
            sisa.append(
                "Rute dengan geometri jalan: "
                f"{_text(ringkasan.get('with_road'))} · tanpa geometri: "
                f"{_text(ringkasan.get('without_road'))} · cakupan: "
                f"{_text(ringkasan.get('scope'))}"
                + (
                    " · keadaan perjalanan: "
                    + ", ".join(f"{k}={v}" for k, v in keadaan.items() if v)
                    if any(keadaan.values())
                    else ""
                )
            )

    if not bagian:
        return (
            "Belum ada data eksklusi pemasok maupun kiriman aktif dari backend MealChain.\n\n"
            + _footnote([note or "sumber: GET /supplier-exclusions + GET /supplier-routes"])
        )

    return "\n\n".join(bagian) + "\n\n" + _footnote(
        [
            note,
            "Sumber: `GET /supplier-exclusions` + `GET /supplier-routes` (jarak jalan & durasi "
            "dari layanan rute backend, bukan taksiran jembatan).",
            "Eksklusi berstatus AKTIF tetap ditampilkan beserta alasannya — Joule tidak "
            "menyembunyikan pemasok yang dikecualikan.",
            *sisa,
        ]
    )


# --- bukti & jejak keputusan -------------------------------------------------------------


def _signature_line(compliance: Mapping[str, Any]) -> str:
    """Satu baris ringkas keadaan tanda tangan + hasil verifikasi materi."""
    tanda = compliance.get("signature") or {}
    state = _label({"signed": "bertanda tangan", "unsigned": "belum ditandatangani"}, tanda.get("state"))
    algoritma = _text(tanda.get("algorithm"))
    verifikasi = compliance.get("verify")
    if verifikasi is True:
        hasil = "cocok"
    elif verifikasi is False:
        hasil = "TIDAK cocok"
    else:
        hasil = MISSING
    return f"{state} · {algoritma} · verifikasi materi: {hasil}"


def decision_evidence_report(
    cases: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 3,
    note: str | None = None,
) -> str:
    """Berkas bukti keputusan: tanda tangan kriptografis, rantai iterasi, jejak agen.

    Satu blok per keputusan. Angka bukti/approval/jejak diambil dari panjang daftar yang
    dikirim backend (bukan hasil pencocokan ulang di jembatan); tanda tangan dipotong untuk
    muat di chat — materi lengkapnya ada di UI MealChain.
    """
    data = list(cases or ())
    if not data:
        return (
            "Belum ada keputusan yang bisa dibuka bukti dan jejaknya.\n\n"
            + _footnote([note or "sumber: GET /decisions + /decisions/{id}/compliance"])
        )

    tampil, sisa = _cap(data, limit)
    blok: list[str] = []
    for case in tampil:
        compliance = case.get("compliance") or {}
        decision = compliance.get("decision") or {}
        chain = list((case.get("chain") or {}).get("chain") or ())
        traces = list((case.get("traces") or {}).get("steps") or ())
        bukti = compliance.get("evidence") or []
        approval = compliance.get("approvals") or []
        tanda = compliance.get("signature") or {}
        sidik = str(tanda.get("signature") or "")
        isi = [
            ("Jenis", _label(DECISION_TYPE_LABEL, decision.get("decision_type") or case.get("decisionType"))),
            ("Status", _label(DECISION_STATUS_LABEL, decision.get("status") or case.get("status"))),
            ("Diusulkan oleh", _text(decision.get("proposed_by") or case.get("proposedBy"))),
            ("Tanda tangan", _signature_line(compliance)),
            ("Sidik tanda tangan", f"{sidik[:24]}…" if sidik else MISSING),
            ("Alamat isi (content address)", _text(compliance.get("content_address"))),
            ("Bukti / approval / jejak", f"{len(bukti)} / {len(approval)} / {len(traces)}"),
            (
                "Penyetuju",
                # Nama manusia, bukan hanya peran (aditif 21 Okt 2026): pertanyaan
                # "siapa yang menyetujui" tidak bisa dijawab dengan "sppg_head".
                ", ".join(
                    f"{_text(a.get('approved_by_name'))} ({_text(a.get('role'))})"
                    for a in approval
                    if isinstance(a, Mapping) and a.get("approved")
                )
                or MISSING,
            ),
            ("Iterasi dalam rantai", _text(len(chain)) if chain else MISSING),
        ]
        teks_kasus = "\n".join(f"- **{judul}:** {nilai}" for judul, nilai in isi)
        blok.append(
            f"**Keputusan {_text(case.get('id') or compliance.get('decision_id'))}**\n\n{teks_kasus}"
        )
        if chain:
            blok.append(
                "Rantai iterasi:\n\n"
                + _table(
                    ["Iterasi", "Status", "Jumlah", "Alasan penolakan", "Dibuat"],
                    [
                        [
                            _text(row.get("iteration")),
                            _label(DECISION_STATUS_LABEL, row.get("status")),
                            kg(row.get("quantity_kg")),
                            _text(row.get("rejection_reason")),
                            wib(row.get("created_at")),
                        ]
                        for row in chain
                    ],
                )
            )
        if traces:
            blok.append(
                "Jejak agen:\n\n"
                + _table(
                    ["Langkah", "Tool", "Ringkasan keluaran", "Waktu"],
                    [
                        [
                            _text(step.get("step_name")),
                            _text(step.get("tool_called")),
                            _text((step.get("output_summary") or {}).get("learning_note"))
                            if isinstance(step.get("output_summary"), Mapping)
                            else _text(step.get("output_summary")),
                            wib(step.get("step_at")),
                        ]
                        for step in traces
                    ],
                )
            )

    return (
        f"Bukti & jejak keputusan MealChain Guardian ({len(data)} keputusan):\n\n"
        + "\n\n".join(blok)
        + "\n\n"
        + _footnote(
            [
                note,
                "Sumber: `/decisions/{id}/compliance` + `/decisions/{id}/chain` + "
                "`/decisions/{id}/traces` (tanda tangan dan verifikasi dihitung backend).",
                "Tanda tangan kriptografis hanya ditampilkan sebagian supaya muat di chat; "
                "materi lengkap + berkas bukti ada di UI MealChain.",
                sisa,
            ]
        )
    )


# --- status sistem & integrasi -----------------------------------------------------------


def system_status_report(
    integrations: Mapping[str, Any] | None,
    ledger: Mapping[str, Any] | None,
    po_summary: Mapping[str, Any] | None,
    locations: Sequence[Mapping[str, Any]] | None = None,
    *,
    limit: int = 15,
    note: str | None = None,
) -> str:
    """Kesiapan sistem: komponen integrasi, ledger, ringkasan PO, dan jaringan SPPG.

    Semua status datang dari backend apa adanya — termasuk yang `belum dimulai` atau
    `fail-closed`. Jembatan tidak menaikkan status apa pun menjadi hijau.
    """
    integrasi = integrations or {}
    ledger_data = ledger or {}
    ringkasan_po = po_summary or {}
    bagian: list[str] = []
    sisa: list[str] = []

    komponen = list(integrasi.get("components") or ())
    if komponen:
        tampil, catatan = _cap(
            sorted(komponen, key=lambda r: str(r.get("category") or "")), limit
        )
        bagian.append(
            f"Komponen integrasi ({len(komponen)} komponen, diperiksa {wib(integrasi.get('checked_at'))}):\n\n"
            + _table(
                ["Komponen", "Status", "Bukti"],
                [
                    [
                        _text(komponen_row.get("name") or komponen_row.get("id")),
                        _text(komponen_row.get("category_label") or komponen_row.get("category")),
                        _text(komponen_row.get("evidence")),
                    ]
                    for komponen_row in tampil
                ],
            )
        )
        if catatan:
            sisa.append(catatan)

    if ledger_data:
        warning = ledger_data.get("coverage_warning")
        bagian.append(
            "Ledger bukti (rantai blok):\n\n"
            + "\n".join(
                [
                    f"- **Status verifikasi:** {'SAH' if ledger_data.get('valid') else 'TIDAK SAH'}",
                    f"- **Blok:** {_text(ledger_data.get('blocks'))} "
                    f"(terhubung {_text(ledger_data.get('linked_blocks'))}, "
                    f"yatim {_text(ledger_data.get('orphan_blocks'))})",
                    f"- **Rasio blok terhubung (0–1):** {num(ledger_data.get('linked_ratio'), digits=2)}",
                    f"- **Kepala rantai:** {_text(ledger_data.get('head'))}",
                    f"- **Peringatan cakupan:** {_text(warning) if warning else 'tidak ada'}",
                ]
            )
        )

    if ringkasan_po:
        per_status = ringkasan_po.get("by_status") or {}
        rincian = ", ".join(
            f"{_label(PO_STATUS_LABEL, status)}={_text(jumlah)}"
            for status, jumlah in per_status.items()
        )
        bagian.append(
            "Purchase order (mock SAP):\n\n"
            + "\n".join(
                [
                    f"- **Jumlah PO:** {_text(ringkasan_po.get('count'))}",
                    f"- **Total nilai:** {rupiah(ringkasan_po.get('total_value'))}",
                    f"- **Per status:** {rincian or MISSING}",
                    f"- **Cakupan:** {_text(ringkasan_po.get('scope'))} · sumber "
                    f"{_text(ringkasan_po.get('source'))}",
                ]
            )
        )

    jaringan = list(locations or ())
    if jaringan:
        daftar = ", ".join(
            f"{_text(row.get('name'))} ({_text(row.get('region'))})" for row in jaringan
        )
        bagian.append(f"Jaringan SPPG ({len(jaringan)} lokasi):\n\n{daftar}")

    if not bagian:
        return (
            "Belum ada status sistem yang dikirim backend MealChain.\n\n"
            + _footnote([note or "sumber: GET /integrations/status + GET /ledger/verify"])
        )

    return "\n\n".join(bagian) + "\n\n" + _footnote(
        [
            note,
            "Sumber: `GET /integrations/status` + `GET /ledger/verify` + "
            "`GET /sap/purchase-orders/summary` + `GET /admin/locations`.",
            "Status ditampilkan apa adanya, termasuk yang belum dimulai; Joule tidak "
            "menaikkan status komponen mana pun.",
            "Direktori pengguna (`/admin/users`) sengaja TIDAK dibuka lewat chat: baca-saja "
            "bukan alasan membocorkan data pribadi ke antarmuka percakapan.",
            *sisa,
        ]
    )


# --- penerimaan barang satu batch --------------------------------------------------------


RECEIPT_CHECK_LABEL = {
    "suhu": "suhu",
    "kemasan": "kemasan",
    "berat_kg": "berat",
    "catatan": "catatan",
}


def _pemeriksaan(checked: Any) -> str:
    """Checklist penerimaan apa adanya: `ya`/`belum` per butir, bukan angka ringkasan."""
    if not isinstance(checked, Mapping):
        return MISSING
    butir = [
        f"{RECEIPT_CHECK_LABEL.get(str(nama), str(nama))}: {'ya' if nilai else 'belum'}"
        for nama, nilai in checked.items()
        if isinstance(nilai, bool)
    ]
    return ", ".join(butir) if butir else MISSING


def receipt_report(
    receipts: Sequence[Mapping[str, Any]] | None,
    batch_id: str | None = None,
    *,
    note: str | None = None,
) -> str:
    """Penerimaan barang (goods receipt) untuk satu batch yang disebut pengguna."""
    data = list(receipts or ())
    if not data:
        return (
            f"Belum ada penerimaan barang tercatat untuk batch {_text(batch_id)}.\n\n"
            + _footnote(
                [
                    note,
                    "Sumber: GET /receipts?batch_id=… — backend mewajibkan satu batch per "
                    "permintaan, jadi Joule tidak menarik seluruh tabel penerimaan.",
                ]
            )
        )
    baris = [
        [
            wib(row.get("recorded_at")),
            _text(row.get("recorded_by_name")),
            _pemeriksaan(row.get("checked")),
            _text(row.get("other_note")),
        ]
        for row in data
    ]
    return (
        f"Penerimaan barang untuk batch {_text(batch_id)} ({len(data)} catatan):\n\n"
        + _table(["Dicatat", "Oleh", "Pemeriksaan", "Catatan lain"], baris)
        + "\n\n"
        + _footnote(
            [
                note,
                "Sumber: `GET /receipts?batch_id=…` — checklist dan catatan apa adanya dari "
                "backend, tanpa hitung ulang.",
            ]
        )
    )


def receipts_queue_report(
    payload: Mapping[str, Any] | None,
    *,
    note: str | None = None,
) -> str:
    """Antrean penerimaan barang: sudah dicatat, BELUM diputuskan kepala SPPG.

    Domain ini berbeda dari antrean keputusan: `batch_receipts` mencatat pemeriksaan
    fisik barang, dan persetujuannya yang menulis `supply_records`. Sebelum skill ini
    ada, pertanyaan "penerimaan barang mana yang menunggu persetujuan" dijawab
    "Antrean keputusan" — domain yang salah, meski `/receipts/menunggu` tersedia.
    """
    data = payload if isinstance(payload, Mapping) else {}
    items = [row for row in (data.get("items") or ()) if isinstance(row, Mapping)]
    total = data.get("total")
    jumlah = total if isinstance(total, int) else len(items)

    if not items:
        return (
            "Tidak ada penerimaan barang yang menunggu keputusan.\n\n"
            + _footnote(
                [
                    note,
                    "Sumber: `GET /receipts/menunggu` — daftar kosong berarti setiap "
                    "catatan penerimaan sudah diputuskan (disetujui/ditolak).",
                ]
            )
        )

    baris = [
        [
            _text(row.get("commodity")),
            kg(row.get("quantity_kg")),
            _text(row.get("location")),
            _text(row.get("safety_status")),
            _text(row.get("recorded_by_name")),
            f"{num(row.get('checked_count'), 0)}/3",
            wib(row.get("recorded_at")),
        ]
        for row in items
    ]
    return (
        f"Ada {jumlah} penerimaan barang yang menunggu keputusan:\n\n"
        + _table(
            ["Komoditas", "Jumlah", "Lokasi", "Keamanan", "Dicatat oleh", "Diperiksa", "Waktu"],
            baris,
        )
        + "\n\n"
        + _footnote(
            [
                note,
                "Sumber: `GET /receipts/menunggu` (satu baris per batch, catatan terbaru), "
                "sudah di-scope ke lokasi pengguna.",
                "Persetujuan ditulis lewat `POST /receipts/{id}/approve`; barulah stok bertambah.",
            ]
        )
    )


def quarantine_report(
    batches: Sequence[Mapping[str, Any]] | None,
    *,
    note: str | None = None,
) -> str:
    """Batch yang sedang dikarantina — disaring dari `/batches`, bukan tabel karangan."""
    data = [
        row
        for row in (batches or ())
        if isinstance(row, Mapping)
        and str(row.get("quarantine_status") or "").lower() in {"quarantined", "karantina"}
    ]
    if not data:
        return (
            "Tidak ada batch berstatus karantina saat ini.\n\n"
            + _footnote(
                [
                    note,
                    "Sumber: `GET /batches` — kolom `quarantine_status` disaring di jembatan, "
                    "tanpa menambah endpoint baru.",
                ]
            )
        )
    baris = [
        [
            _text(row.get("code") or row.get("batch_code")),
            _text(row.get("commodity")),
            kg(row.get("quantity_kg")),
            _text(row.get("location")),
            _text(row.get("safety_status")),
        ]
        for row in data
    ]
    return (
        f"Ada {len(data)} batch berstatus karantina:\n\n"
        + _table(["Batch", "Komoditas", "Jumlah", "Lokasi", "Keamanan"], baris)
        + "\n\n"
        + _footnote(
            [
                note,
                "Sumber: `GET /batches` (kolom `quarantine_status`), angka apa adanya dari backend.",
            ]
        )
    )


def unsupported_report(domain: str, reason: str) -> str:
    """Domain yang backend-nya belum punya endpoint baca.

    Sebelum ini, pertanyaan seperti "pengiriman hari ini" dijawab tabel pasokan —
    terlihat seperti jawaban padahal menjawab hal lain. Menyatakan belum tersedia
    lebih jujur daripada menampilkan angka dari domain yang berdekatan.
    """
    return (
        f"Joule belum bisa menjawab pertanyaan tentang {domain}.\n\n"
        f"Alasan: {reason}\n\n"
        + _footnote(
            [
                "Tidak ada angka pengganti dari domain lain — jawaban kosong lebih baik "
                "daripada angka yang bukan menjawab pertanyaan.",
                "Yang tersedia sekarang: situasi pasokan, antrean keputusan, penerimaan "
                "barang, karantina, PO, harga, kebutuhan, limbah, eksklusi pemasok, bukti "
                "keputusan, dan status sistem.",
            ]
        )
    )


def unavailable_report(skill: str, reason: str) -> str:
    """Dipakai saat backend tidak bisa dibaca — jujur, bukan tabel kosong yang tampak aman."""
    return (
        f"Data MealChain Guardian untuk permintaan `{skill}` belum bisa diambil.\n\n"
        f"Penyebab: {reason}\n\n"
        + _footnote(
            [
                "Tidak ada angka yang ditampilkan karena tidak ada angka yang terbaca — "
                "bukan berarti kondisinya aman.",
                "Periksa backend MealChain (`/health`) lalu coba lagi.",
            ]
        )
    )
