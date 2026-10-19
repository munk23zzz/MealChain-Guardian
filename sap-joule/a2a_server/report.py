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
