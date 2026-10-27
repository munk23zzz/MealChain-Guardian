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
    "fail": "gagal",
    "needs_verification": "perlu verifikasi",
    "pending": "menunggu pemeriksaan",
    # Nilai huruf besar dari backend versi lama tetap dikenali supaya laporan tidak
    # menampilkan istilah API mentah.
    "PASS": "lolos",
    "FAIL": "gagal",
    "NEEDS_VERIFICATION": "perlu verifikasi",
    "PENDING": "menunggu pemeriksaan",
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


def short_id(nilai: Any) -> str:
    """Rujukan pendek (8 karakter) untuk id panjang di tabel chat.

    Jembatan tetap menerima id utuh MAUPUN potongan ini saat pengguna menyebutnya
    (`server._resolve_id`), jadi kolom tidak perlu menampung 36 karakter per baris.
    """
    teks = str(nilai or "").strip()
    if not teks or teks == "None":
        return MISSING
    return teks[:8]


def _cap(
    rows: Sequence[Any], limit: int, *, konteks: str | None = None
) -> tuple[list[Any], str | None]:
    """Batasi jumlah baris dan sebutkan sisanya — supaya tidak ada yang disembunyikan.

    Catatan sisa memakai kalimat biasa ("menampilkan 12 dari 40 baris"), bukan jargon
    endpoint: pembacanya manajer SPPG, bukan pemanggil API.
    """
    if limit and limit > 0 and len(rows) > limit:
        awalan = f"{konteks}: " if konteks else ""
        return list(rows[:limit]), f"{awalan}Menampilkan {limit} dari {len(rows)} baris."
    return list(rows), None


# --- situasi pasokan ---------------------------------------------------------------------


def supply_report(
    batches: Sequence[Mapping[str, Any]] | None,
    balance: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    limit: int = 12,
    note: str | None = None,
    pasangan: Mapping[str, Any] | None = None,
) -> str:
    """Situasi pasokan: keseimbangan per lokasi (`/balance/map`) + inventaris batch (`/batches`).

    Sengaja DUA tabel, bukan satu yang digabung: keseimbangan dihitung backend per
    (lokasi, komoditas), sedangkan keamanan & kesegaran melekat pada batch. Menggabungkannya
    berarti perender ini harus memilih satu nilai agregat — itu perhitungan, dan perhitungan
    bukan tugasnya.

    `pasangan` diisi pemanggil ketika pertanyaan menyebut tepat satu SPPG dan satu komoditas
    (mis. "berapa stok telur di Bandung?"). Kalimat pertama laporan lalu menjawab pasangan itu
    langsung, bukan menyodorkan 40 baris untuk dibaca sendiri.
    """
    batch_rows = list(batches or ())
    balance_by_commodity = balance or {}

    balance_rows: list[tuple[int, str, list[str]]] = []
    for commodity in sorted(balance_by_commodity):
        payload = balance_by_commodity[commodity] or {}
        commodity_name = payload.get("commodity") or commodity
        for row in payload.get("locations") or ():
            status = str(row.get("status") or "").lower()
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
            "Belum ada data pasokan yang tercatat di MealChain Guardian untuk saringan ini."
            "\n\n" + _footnote([note])
        )

    bagian: list[str] = []
    sisa: list[str] = []

    if balance_rows:
        kurang = sum(1 for rank, _, _ in balance_rows if rank == 0)
        lebih = sum(1 for rank, _, _ in balance_rows if rank == 2)
        seimbang = len(balance_rows) - kurang - lebih
        tampil, catatan_sisa = _cap(balance_rows, limit, konteks="Tabel pasokan")

        kalimat = ""
        if pasangan:
            dicari = (
                str(pasangan.get("location") or "").strip().lower(),
                str(pasangan.get("commodity") or "").strip().lower(),
            )
            for _, _, row in balance_rows:
                if (row[0].lower(), row[1].lower()) == dicari:
                    kalimat = (
                        f"\n\n**{row[0]} · {row[1]}** — pasokan {row[2]} dari kebutuhan "
                        f"{row[3]}: {row[4]} ({row[5]})."
                    )
                    break

        if pasangan and kalimat:
            judul = (
                f"Pasokan dan kebutuhan {_text(pasangan.get('commodity'))} "
                f"di {_text(pasangan.get('location'))}"
            )
        else:
            rincian = [f"{n} {label}" for n, label in
                       ((kurang, "kurang"), (lebih, "lebih"), (seimbang, "seimbang")) if n]
            judul = (
                f"Keseimbangan pasokan per SPPG ({len(balance_rows)} pasangan "
                f"SPPG–komoditas: {' · '.join(rincian)})"
            )

        bagian.append(
            judul
            + kalimat
            + "\n\n"
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
        tampil_batch, catatan_batch = _cap(tersortir, limit, konteks="Tabel batch")

        hitung: dict[str, int] = {}
        for row in batch_rows:
            kunci = str(row.get("safety_status") or "").strip().lower()
            hitung[kunci] = hitung.get(kunci, 0) + 1
        urutan = ("fail", "needs_verification", "pending", "pass")
        ringkas = " · ".join(
            f"{hitung[k]} {SAFETY_LABEL.get(k, k)}" for k in urutan if hitung.get(k)
        )
        lain = sum(n for k, n in hitung.items() if k not in urutan)

        bagian.append(
            f"Inventaris batch ({len(batch_rows)} batch"
            + (f": {ringkas}" if ringkas else "")
            + (f" · {lain} status lain" if lain else "")
            + "):\n\n"
            + (
                # Peringatan sebelum tabel: batch gagal keamanan tidak boleh dipakai,
                # label tanggal jangan sampai terbaca sebagai izin (audit 26 Okt 2026).
                f"Perhatian: {hitung['fail']} batch berstatus gagal keamanan — tidak boleh dipakai; "
                "lihat daftar kandidat pembuangan.\n\n"
                if hitung.get("fail")
                else ""
            )
            + _table(
                ["SPPG", "Komoditas", "Jumlah", "Keamanan", "Skor kesegaran", "Batas simpan"],
                [
                    [
                        _text(row.get("location")),
                        _text(row.get("commodity")),
                        kg(row.get("quantity_kg")),
                        SAFETY_LABEL.get(str(row.get("safety_status")), _text(row.get("safety_status"))),
                        num(row.get("freshness_score"), digits=2),
                        wib(row.get("usable_until")),
                    ]
                    for row in tampil_batch
                ],
            )
        )
        if catatan_batch:
            sisa.append(catatan_batch)

    catatan: list[str | None] = [note]
    if batch_rows:
        catatan.append("Skor kesegaran berskala 0–1 dari sistem MealChain: makin tinggi, makin segar.")
    if batch_rows and balance:
        # Dua tabel ini beda sumber; tanpa kalimat ini angka 900 kg vs 2.000 kg terbaca
        # seperti kontradiksi (jawaban nyata 26 Okt 2026).
        catatan.append(
            "Angka pasokan pada tabel keseimbangan dan jumlah kg pada tabel batch berasal dari "
            "sumber berbeda di MealChain (catatan pasokan vs inventaris batch), jadi keduanya "
            "tidak harus sama."
        )
    catatan.extend(sisa)
    return "\n\n".join(bagian) + "\n\n" + _footnote(catatan)


# --- batch bermasalah (kandidat tinjauan pembuangan) ---------------------------------------

QUARANTINE_LABEL = {
    "quarantined": "dikarantina",
    "failed": "gagal karantina",
    "released": "dilepas dari karantina",
    "none": "tidak dikarantina",
}


def batch_disposal_report(
    batches: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 12,
    note: str | None = None,
) -> str:
    """Batch yang perlu ditinjau manusia: keamanan GAGAL atau berstatus karantina/gagal karantina.

    Perender ini TIDAK menyimpulkan "buang" — itu keputusan manusia (Rules.md §1.2). Yang
    ditampilkan hanya baris yang statusnya dikirim backend, apa adanya, supaya pertanyaan
    "batch mana yang harus dibuang?" tidak dijawab dengan tabel pasokan.
    """
    semua = list(batches or ())
    kandidat = [
        row
        for row in semua
        if str(row.get("safety_status") or "").lower() == "fail"
        or str(row.get("quarantine_status") or "").lower() in {"quarantined", "failed"}
    ]
    if not kandidat:
        return (
            "Tidak ada batch yang berstatus gagal keamanan atau sedang dikarantina di "
            f"MealChain Guardian saat ini ({len(semua)} batch diperiksa)."
            "\n\n" + _footnote([note])
        )

    kandidat.sort(key=lambda row: (str(row.get("location") or ""), str(row.get("commodity") or "")))
    tampil, catatan_sisa = _cap(kandidat, limit, konteks="Tabel batch")
    rows = [
        [
            _text(row.get("location")),
            _text(row.get("commodity")),
            kg(row.get("quantity_kg")),
            SAFETY_LABEL.get(str(row.get("safety_status")), _text(row.get("safety_status"))),
            num(row.get("freshness_score"), digits=2),
            QUARANTINE_LABEL.get(str(row.get("quarantine_status") or "").lower(), _text(row.get("quarantine_status"))),
            wib(row.get("usable_until")),
        ]
        for row in tampil
    ]

    return (
        f"Batch yang perlu ditinjau untuk pembuangan ({len(kandidat)} dari {len(semua)} batch):\n\n"
        + _table(
            ["SPPG", "Komoditas", "Jumlah", "Keamanan", "Skor kesegaran", "Karantina", "Boleh dipakai sampai"],
            rows,
        )
        + "\n\n"
        + _footnote(
            [
                note,
                "Baris di atas kandidat tinjauan, bukan perintah buang: keputusan pembuangan "
                "dilakukan manusia di UI MealChain.",
                "Skor kesegaran berskala 0–1 dari sistem MealChain: makin tinggi, makin segar.",
                catatan_sisa,
            ]
        )
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
            "Belum ada data pemasok yang tercatat di MealChain Guardian.\n\n"
            + _footnote([note])
        )

    def urut(row: Mapping[str, Any]) -> tuple[int, str, str]:
        # 22 Okt 2026: tabel dipangkas 25 baris. Sebelumnya pemasok bertanda
        # "dikecualikan di hub" bisa jatuh di luar potongan, sehingga penanda
        # yang katanya "tidak disaring diam-diam" justru tidak pernah terlihat.
        # Yang bertanda selalu didahulukan.
        bertanda = 0 if row.get("excludedAtHub") else 1
        return (bertanda, str(row.get("location") or ""), str(row.get("name") or ""))

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
                "Daftar pemasok disalin dari data MealChain Guardian; Joule tidak menghitung ulang.",
                "Pemasok tanpa baris kiriman berarti terdaftar tetapi belum/tidak sedang mengirim — "
                "bukan nol karangan.",
                sisa,
            ]
        )
    )


# --- KPI ----------------------------------------------------------------------------------


#: Nama indikator datang dari backend dalam bahasa Inggris; chat memakai bahasa Indonesia yang
#: sama dengan label di UI MealChain. Nama yang belum dikenal lolos apa adanya.
KPI_NAME_LABEL = {
    "Meal Continuity Rate": "Keberlanjutan menu",
    "Avoidable Food Loss": "Kehilangan pangan yang bisa dicegah",
    "Regional Imbalance Resolution Rate": "Penyelesaian ketimpangan wilayah",
    "Safe Delivered Cost": "Biaya pengiriman aman",
    "Procurement Price Deviation": "Simpangan harga pengadaan",
    "Decision Time": "Waktu keputusan",
    "Evidence Completeness": "Kelengkapan bukti",
}

#: Jenis keputusan yang belum masuk `DECISION_TYPE_LABEL` di bawah. Kode mentah (snake_case)
#: terbaca seperti kebocoran di chat, jadi tiap kode yang pernah muncul diberi nama manusiawi.
JENIS_TAMBAHAN = {
    "supplier_procurement": "pengadaan pemasok",
    "food_safety_incident": "gangguan keamanan pangan",
    "price_anomaly": "anomali harga",
}


def _decision_type(nilai: Any) -> str:
    """Jenis keputusan dalam bahasa Indonesia; kode tak dikenal dirapikan, tidak dikarang."""
    kunci = str(nilai or "").strip()
    if kunci in JENIS_TAMBAHAN:
        return JENIS_TAMBAHAN[kunci]
    if kunci in DECISION_TYPE_LABEL:
        return DECISION_TYPE_LABEL[kunci]
    return kunci.replace("_", " ").strip() or MISSING


MODE_SOURCE_SENTENCE = {
    "operational": "Sumber: catatan operasional MealChain Guardian.",
    "demo": "Sumber: catatan satu sesi demo — angka simulasi, bukan hasil lapangan.",
}


def _periode_kpi(envelope: Mapping[str, Any]) -> str | None:
    """`Periode: 24 Okt 2026 – 27 Okt 2026 (Asia/Jakarta)` dari amplop `/kpi`.

    Tanggal saja (bukan jam): KPI dihitung atas hari kalender, dan menampilkan jam
    akan membuatnya terbaca seperti jendela 24 jam bergulir.
    """
    blok = envelope.get("period")
    if not isinstance(blok, Mapping):
        return None
    label = str(blok.get("label") or "").strip()
    zona = str(blok.get("timezone") or "Asia/Jakarta").strip()

    def _tanggal(nilai: Any) -> str:
        teks = str(nilai or "").strip()
        if not teks:
            return MISSING
        try:
            saat = _dt.datetime.fromisoformat(teks.replace("Z", "+00:00"))
        except ValueError:
            return teks
        if saat.tzinfo is not None:
            saat = saat.astimezone(WIB)
        return f"{saat.day} {BULAN[saat.month - 1]} {saat.year}"

    mulai, selesai = _tanggal(blok.get("start")), _tanggal(blok.get("end"))
    rentang = f"{mulai} – {selesai}"
    if label:
        return f"Periode: {label} ({rentang}, {zona})."
    return f"Periode: {rentang} ({zona})."


def _estimasi_teks(metric: Mapping[str, Any]) -> str | None:
    """Anotasi proyeksi untuk satu metrik — selalu berawalan `estimasi`."""
    est = metric.get("estimate")
    if not isinstance(est, Mapping):
        return None
    state = str(est.get("state") or "").strip().lower()
    if state != "available" or est.get("value") is None:
        return None
    return f"estimasi {format_metric(est.get('value'), est.get('unit'))}"


def kpi_report(envelope: Mapping[str, Any] | None, *, note: str | None = None) -> str:
    """Daftar KPI dari `/kpi`. Metrik yang tidak bisa dihitung ditampilkan `—` + alasannya.

    Fase 8: laporan menyebut periode, asal angka (operasional vs sesi demo), dan
    menandai metrik yang membawa estimasi. Tanpa itu pembaca tidak bisa tahu apakah
    persen yang ia lihat adalah catatan lapangan atau proyeksi model.
    """
    metrics = list((envelope or {}).get("metrics") or ())
    if not metrics:
        return (
            "Belum ada metrik KPI yang tercatat di MealChain Guardian.\n\n"
            + _footnote([note])
        )

    rows: list[list[str]] = []
    belum = 0
    ada_estimasi = False
    for metric in metrics:
        name = _label(KPI_NAME_LABEL, metric.get("name"))
        state = str(metric.get("state") or "").strip().lower()
        estimasi = _estimasi_teks(metric)
        if state == "available" and metric.get("value") is not None:
            sel = format_metric(metric.get("value"), metric.get("unit"))
            if estimasi:
                sel = f"{sel} ({estimasi})"
                ada_estimasi = True
            rows.append([name, sel])
        else:
            alasan = _text(metric.get("reason")) if metric.get("reason") else MISSING
            rows.append([name, f"{MISSING} ({alasan})"])
            belum += 1

    mode = str((envelope or {}).get("data_mode") or "operational").strip().lower()
    catatan = _footnote(
        [
            _periode_kpi(envelope or {}),
            MODE_SOURCE_SENTENCE.get(mode, MODE_SOURCE_SENTENCE["operational"]),
            (
                "Angka berlabel estimasi adalah proyeksi model, bukan kejadian tercatat."
                if ada_estimasi
                else None
            ),
            (
                f"{belum} indikator belum bisa dihitung; alasannya ikut ditulis supaya "
                "tidak terbaca nol."
            )
            if belum
            else None,
            note,
        ]
    )
    teks = (
        f"Indikator kinerja MealChain Guardian ({len(metrics)} indikator):\n\n"
        + _table(["Indikator", "Nilai"], rows)
    )
    return f"{teks}\n\n{catatan}" if catatan else teks


# --- antrean usulan ----------------------------------------------------------------------


def kpi_scope_problem(reason: str, *, note: str | None = None) -> str:
    """Cakupan KPI yang diminta tidak bisa dihitung — sebut sebabnya, jangan menebak sesi."""
    return _footnote(
        [
            f"KPI untuk cakupan itu tidak bisa ditampilkan: {reason}.",
            MODE_SOURCE_SENTENCE["operational"],
            note,
        ]
    )


def approval_queue_report(
    decisions: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 12,
    note: str | None = None,
    total_belum: int | None = None,
) -> str:
    """Antrean usulan keputusan — untuk dilihat manusia, bukan disetujui agen.

    Baris datang dari `/decisions` yang sudah dilengkapi `/decisions/{id}/approval-summary`
    oleh klien; karena itu asal→tujuan dan komoditas sudah berupa NAMA, bukan id.

    `total_belum` = jumlah usulan terbuka yang SEBENARNYA. Klien hanya melengkapi
    `DETAIL_LIMIT` baris teratas (satu panggilan HTTP per keputusan), jadi tanpa angka ini
    judul "12 baris" membuat 10 usulan lain seolah tidak ada.
    """
    items = list(decisions or ())
    if not items:
        return (
            "Belum ada usulan keputusan di MealChain Guardian.\n\n" + _footnote([note])
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
            short_id(row.get("id")),
            _decision_type(row.get("decisionType")),
            f"{_text(row.get('sourceLocation'))} → {_text(row.get('targetLocation'))}",
            _text(row.get("commodity")),
            kg(row.get("quantityKg")),
            _label(DECISION_STATUS_LABEL, row.get("status")),
        ]
        for row in tampil
    ]
    body = _table(["ID", "Jenis", "Asal → tujuan", "Komoditas", "Jumlah", "Status"], rows)

    jumlah_belum = total_belum if isinstance(total_belum, int) and total_belum > 0 else len(items)
    if jumlah_belum > len(items):
        judul = (
            f"Antrean usulan keputusan MealChain Guardian ({jumlah_belum} usulan terbuka, "
            f"{len(items)} teratas ditampilkan):"
        )
    else:
        judul = f"Antrean usulan keputusan MealChain Guardian ({len(items)} baris):"

    return (
        f"{judul}\n\n"
        f"{body}\n\n"
        + _footnote(
            [
                note,
                "Sebut 8 karakter pertama ID untuk membuka bukti keputusannya.",
                "Persetujuan tidak bisa dilakukan dari Joule: approver menekan Setuju di UI "
                "MealChain dengan tokennya sendiri — tidak ada persetujuan otomatis.",
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
    "execution": "dibuat dari eksekusi keputusan",
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
    keputusan = short_id(po.get("decisionId"))
    if keputusan != MISSING:
        keputusan = f"{keputusan} — {_label(DECISION_STATUS_LABEL, po.get('decisionStatus'))}"
    baris = [
        ("Status PO", _label(PO_STATUS_LABEL, po.get("status"))),
        ("Dibuat", wib(po.get("createdAt"))),
        ("Lokasi tujuan", _text(po.get("locationName"))),
        ("Pemasok", _text(po.get("supplierName"))),
        ("Bahan", _text(po.get("commodityName"))),
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
                f"Diambil dari tabel purchase order SAP simulasi di MealChain Guardian — 1 dari "
                f"{jumlah_terbaca} PO yang terbaca.",
                "Angka ditampilkan apa adanya, tanpa hitung ulang.",
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
    hanya_disetujui: bool = False,
) -> str:
    """Daftar purchase order mock SAP, atau satu PO bila nomornya disebut.

    `hanya_disetujui` dipakai saat pertanyaannya "PO mana yang sudah disetujui?": yang
    ditampilkan hanya PO yang keputusannya sudah disetujui/dieksekusi, bukan seluruh 20 baris
    termasuk rancangan yang tidak menjawab pertanyaan.

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
                        "Purchase order dibaca dari tabel SAP simulasi di MealChain Guardian.",
                        "Nomor yang tidak terdaftar, atau PO di luar cakupan akun baca, tidak "
                        "akan muncul di sini — bukan berarti PO-nya fiktif.",
                    ]
                )
            )
        return _po_detail(cocok[0], jumlah_terbaca=len(items), note=note)

    if hanya_disetujui:
        items = [
            row
            for row in items
            if str(row.get("decisionStatus") or "").lower() in {"approved", "executed"}
        ]
        if not items:
            return (
                "Belum ada purchase order yang keputusannya sudah disetujui atau dieksekusi.\n\n"
                + _footnote([note])
            )

    if not items:
        return (
            "Belum ada purchase order yang terbaca di MealChain Guardian.\n\n"
            + _footnote([note])
        )

    tampil, catatan_sisa = _cap(items, limit, konteks="Tabel PO")
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
    judul = (
        f"Purchase order yang sudah disetujui atau dieksekusi ({len(items)} PO):\n\n"
        if hanya_disetujui
        else f"Purchase order MealChain Guardian ({len(items)} PO terbaca):\n\n"
    )
    return (
        judul
        + f"{body}\n\n"
        + _footnote(
            [
                note,
                "Tabel SAP simulasi di MealChain Guardian, terbaru lebih dulu; angka apa adanya.",
                (
                    f"Sebut satu nomor PO (mis. `PO {_text(tampil[0].get('poNumber'))}`)"
                    " untuk melihat rinciannya."
                    if tampil
                    else "Sebut satu nomor PO untuk melihat rinciannya."
                ),
                catatan_sisa,
            ]
        )
    )


# --- harga & kuotasi ---------------------------------------------------------------------

PRICE_SOURCE_LABEL = {
    "pihps_reference": "acuan PIHPS",
    "price_signal": "sinyal harga",
    "mock_sap": "integrasi SAP simulasi",
    "mock_sap_table": "integrasi SAP simulasi",
    "mock": "mock",
}
#: Metode prakiraan kebutuhan: label Indonesia; nilai tak dikenal tampil apa adanya.
FORECAST_METHOD_LABEL = {
    "statistical_fallback": "cadangan statistik",
    "sap_rpt": "SAP-RPT-1.6",
    "sap_rpt_1_6": "SAP-RPT-1.6",
    "moving_average": "rata-rata bergerak",
}
EXCLUSION_STATUS_LABEL = {
    "active": "aktif",
    "revoked": "dicabut",
    "proposed": "diusulkan",
    "rejected": "ditolak",
}
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
            [note]
        )

    return "\n\n".join(bagian) + "\n\n" + _footnote(
        [
            note,
            "Harga disalin apa adanya; Joule tidak menghitung termurah atau rata-rata.",
            "Pasangan tanpa baris harga dibiarkan kosong, bukan diisi nol.",
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
            [note]
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
                "Angka kebutuhan dan prakiraan datang dari sistem MealChain Guardian; Joule "
                "tidak meramal dan tidak menghitung ulang.",
                "Cadangan statistik berarti model peramal SAP tidak dipakai untuk pasangan "
                "itu — prakiraannya tetap angka sistem, bukan tebakan Joule.",
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
            [note]
        )

    periode = data.get("period") or {}
    scope = data.get("scope") or {}
    lokasi = scope.get("locations") or []
    ringkas = [
        ("Limbah tercatat", _kg_events(data.get("recorded"))),
        ("Dialihkan ke mitra", _kg_events(data.get("diverted"))),
        ("Tercatat tanpa mitra", _kg_events(data.get("unassigned"))),
        ("Periode", f"{wib(periode.get('start'))} – {wib(periode.get('end'))} ({_text(periode.get('days'))} hari)"),
        ("Cakupan", f"{len(lokasi)} SPPG · cakupan akun Anda"),
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
                "Angka kehilangan pangan dihitung sistem MealChain Guardian; Joule hanya menyajikan.",
                "Tanpa mitra artinya limbah tercatat tetapi belum dialihkan ke pengolahan — "
                "bukan berarti dibuang; sistem tidak menyimpulkan hal itu.",
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
                        _text(str(r.get("journeyState") or "").replace("_", " ").capitalize())
                        if r.get("journeyState")
                        else MISSING,
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
            rincian_keadaan = ", ".join(
                f"{v} {str(k).replace('_', ' ')}" for k, v in keadaan.items() if v
            )
            sisa.append(
                f"{_text(ringkasan.get('with_road'))} kiriman punya rute jalan, "
                f"{_text(ringkasan.get('without_road'))} tanpa rute jalan"
                + (f"; perjalanan: {rincian_keadaan}" if rincian_keadaan else "")
                + "."
            )

    if not bagian:
        return (
            "Belum ada data eksklusi pemasok maupun kiriman aktif di MealChain Guardian.\n\n"
            + _footnote([note])
        )

    return "\n\n".join(bagian) + "\n\n" + _footnote(
        [
            note,
            "Jarak jalan dan durasi dari layanan rute MealChain Guardian, bukan taksiran Joule.",
            "Eksklusi yang berstatus aktif tetap ditampilkan beserta alasannya — Joule tidak "
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
            "Permintaan bukti keputusan ini tidak bisa dilayani.\n\n"
            + _footnote([note])
        )

    tampil, sisa = _cap(data, limit)
    # Ringkasan status di judul: pembaca tahu isinya apa sebelum menggulir (audit 26 Okt 2026).
    hitung: dict[str, int] = {}
    for kasus in data:
        status = ((kasus.get("compliance") or {}).get("decision") or {}).get("status")
        label = _label(DECISION_STATUS_LABEL, status)
        hitung[label] = hitung.get(label, 0) + 1
    ringkas = " · ".join(f"{jumlah} {label}" for label, jumlah in hitung.items())
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
                # "siapa yang menyetujui" tidak bisa dijawab dengan "sppg_head". Kalau belum
                # ada persetujuan, itu DINYATAKAN — tanda hubung terbaca seperti data hilang.
                ", ".join(
                    f"{_text(a.get('approved_by_name'))} ({_text(a.get('role'))})"
                    for a in approval
                    if isinstance(a, Mapping) and a.get("approved")
                )
                or "belum ada persetujuan tercatat",
            ),
            ("Iterasi dalam rantai", _text(len(chain)) if chain else MISSING),
        ]
        teks_kasus = "\n".join(f"- **{judul}:** {nilai}" for judul, nilai in isi)
        blok.append(
            f"**Keputusan {short_id(case.get('id') or compliance.get('decision_id'))}**\n\n{teks_kasus}"
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
            baris = [
                [
                    _text(step.get("step_name")),
                    _text(step.get("tool_called")),
                    _text((step.get("output_summary") or {}).get("learning_note"))
                    if isinstance(step.get("output_summary"), Mapping)
                    else _text(step.get("output_summary")),
                    wib(step.get("step_at")),
                ]
                for step in traces
            ]
            # Kolom ringkasan yang kosong untuk SEMUA baris tidak menambah informasi;
            # dihapus supaya tabel jejak tetap terbaca di chat (audit 26 Okt 2026).
            if all(sel in ("", MISSING, None) for sel in (r[2] for r in baris)):
                blok.append(
                    "Jejak agen:\n\n"
                    + _table(["Langkah", "Tool", "Waktu"], [[r[0], r[1], r[3]] for r in baris])
                )
            else:
                blok.append(
                    "Jejak agen:\n\n"
                    + _table(["Langkah", "Tool", "Ringkasan keluaran", "Waktu"], baris)
                )

    return (
        f"Bukti & jejak keputusan MealChain Guardian ({len(data)} keputusan: {ringkas}):\n\n"
        + "\n\n".join(blok)
        + "\n\n"
        + _footnote(
            [
                note,
                "Tanda tangan dan verifikasi dihitung sistem MealChain Guardian.",
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
            "Purchase order (SAP simulasi):\n\n"
            + "\n".join(
                [
                    f"- **Jumlah PO:** {_text(ringkasan_po.get('count'))}",
                    f"- **Total nilai:** {rupiah(ringkasan_po.get('total_value'))}",
                    f"- **Per status:** {rincian or MISSING}",
                    f"- **Cakupan:** {_text(ringkasan_po.get('scope'))} · sumber "
                    f"{_label(PRICE_SOURCE_LABEL, ringkasan_po.get('source'))}",
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
            "Belum ada status sistem yang tercatat di MealChain Guardian.\n\n" + _footnote([note])
        )

    return "\n\n".join(bagian) + "\n\n" + _footnote(
        [
            note,
            "Status komponen, ledger, dan PO dibaca dari sistem MealChain Guardian.",
            "Status ditampilkan apa adanya, termasuk yang belum dimulai; Joule tidak "
            "menaikkan status komponen mana pun.",
            "Direktori pengguna sengaja tidak dibuka lewat chat: baca-saja "
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
            f"Belum ada penerimaan barang tercatat untuk batch {short_id(batch_id)}.\n\n"
            + _footnote(
                [
                    note,
                    "Backend mewajibkan satu batch per permintaan, jadi Joule tidak menarik "
                    "seluruh tabel penerimaan.",
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
        f"Penerimaan barang untuk batch {short_id(batch_id)} ({len(data)} catatan):\n\n"
        + _table(["Dicatat", "Oleh", "Pemeriksaan", "Catatan lain"], baris)
        + "\n\n"
        + _footnote(
            [
                note,
                "Checklist dan catatan ditampilkan apa adanya, tanpa hitung ulang.",
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
                    "Daftar kosong berarti setiap catatan penerimaan sudah diputuskan "
                    "(disetujui/ditolak).",
                ]
            )
        )

    baris = [
        [
            _text(row.get("commodity")),
            kg(row.get("quantity_kg")),
            _text(row.get("location")),
            SAFETY_LABEL.get(str(row.get("safety_status")), _text(row.get("safety_status"))),
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
                "Satu baris per batch, catatan terbaru; sudah dibatasi ke lokasi pengguna.",
                "Persetujuan dilakukan di UI MealChain; setelah itu barulah stok bertambah.",
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
                    "Status karantina dibaca dari catatan batch MealChain Guardian.",
                ]
            )
        )
    baris = [
        [
            # 22 Okt 2026: `/batches` tidak mengirim `code`/`batch_code`, jadi
            # kolom Batch selalu "—" pada jawaban Joule. Pakai potongan id supaya
            # batch karantina tetap bisa dirujuk operator.
            _text(
                row.get("code")
                or row.get("batch_code")
                or short_id(row.get("id"))
            ),
            _text(row.get("commodity")),
            kg(row.get("quantity_kg")),
            _text(row.get("location")),
            SAFETY_LABEL.get(str(row.get("safety_status")), _text(row.get("safety_status"))),
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
                "Sebut 8 karakter pertama ID batch untuk melihat penerimaannya.",
                "Angka apa adanya dari catatan batch MealChain Guardian.",
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
