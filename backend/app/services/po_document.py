"""Dokumen purchase order (PDF) — satu PO, seluruh angkanya dari basis data.

Latar (20 Okt 2026, permintaan pemilik): panel "Purchase order" pada tab
Decision & Evidence hanya menampilkan baris di layar. Kepala SPPG tidak punya
berkas yang bisa diunduh, dicetak, atau diserahkan ke bagian keuangan — padahal
justru PO itu bukti bahwa dua persetujuan manusia benar-benar menghasilkan
dokumen pembelian.

Empat aturan yang dipegang modul ini:

1. **Hanya PO yang sudah disetujui.** PDF terbit untuk PO yang lahir dari
   keputusan berstatus `approved` atau `executed`. PO impor tanpa keputusan
   (`4500000001`) dan PO dari keputusan yang masih menunggu TIDAK punya PDF:
   dokumen pembelian untuk sesuatu yang belum disetujui adalah klaim palsu.
   Penolakan disampaikan route sebagai 409 + alasan, bukan dokumen kosong.
2. **Tidak ada angka baru.** Kuantitas & harga dibaca dari kolom apa adanya;
   total = harga × kuantitas (aturan yang sama dengan endpoint daftar, lihat
   `api/sap_orders._baris`). Tanggal ditampilkan dalam WIB (UTC+7) dan diberi
   label zona, bukan waktu server yang tidak diketahui pembaca.
3. **Asal data disebut di setiap halaman.** "SAP simulasi" wajib (Rules.md §4):
   data mock tidak boleh tampil seolah SAP S/4HANA produksi.
4. **Yang tidak diketahui ditulis "—".** Pemasok/lokasi/bahan yang NULL tidak
   diganti tebakan; status asing ditampilkan apa adanya, bukan diterjemahkan
   dengan menebak.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Kosakata tampilan ────────────────────────────────────────────────────────
# Semua label di sini adalah terjemahan 1:1 dari nilai yang tersimpan. Status
# atau jenis yang tidak dikenal dikembalikan apa adanya (tidak dikarang).

STATUS_PO = {"draft": "Draf", "submitted": "Terkirim", "confirmed": "Terkonfirmasi"}

STATUS_KEPUTUSAN = {
    "proposed": "Diusulkan",
    "verifier_flagged": "Ditandai verifikator",
    "pending_approval": "Menunggu persetujuan",
    "approved": "Disetujui",
    "executed": "Dieksekusi",
    "rejected": "Ditolak",
    "review_only": "Tinjauan (review-only)",
}

JENIS_KEPUTUSAN = {
    "regional_balance": "Penyeimbangan antarwilayah",
    "price_anomaly": "Anomali harga",
    "safety_disruption": "Gangguan keamanan pangan",
    "supplier_exclusion": "Eksklusi pemasok",
    "supplier_exclusion_restoration": "Pemulihan pemasok",
}

PERAN = {
    "sppg_head": "Kepala SPPG",
    "sppg_nutritionist": "Ahli Gizi SPPG",
    "bgn_monitor": "Monitor BGN",
}

#: Status keputusan yang boleh punya dokumen PO. Satu sumber untuk route dan
#: tes — menambah status di sini berarti mengubah pagar, bukan kosmetik.
STATUS_BOLEH_PDF = frozenset({"approved", "executed"})

BULAN = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Mei",
    "Jun",
    "Jul",
    "Agu",
    "Sep",
    "Okt",
    "Nov",
    "Des",
)

WIB = timezone(timedelta(hours=7))


def status_po_label(status: str | None) -> str:
    if not status:
        return "—"
    return STATUS_PO.get(status, status)


def status_keputusan_label(status: str | None) -> str:
    if not status:
        return "—"
    return STATUS_KEPUTUSAN.get(status, status)


def jenis_keputusan_label(jenis: str | None) -> str:
    if not jenis:
        return "—"
    return JENIS_KEPUTUSAN.get(jenis, jenis)


def peran_label(peran: str | None) -> str:
    if not peran:
        return "—"
    return PERAN.get(peran, peran)


def boleh_pdf(status_keputusan: str | None) -> bool:
    """Apakah keputusan ini sudah cukup matang untuk menerbitkan dokumen PO."""
    return (status_keputusan or "").lower() in STATUS_BOLEH_PDF


def _angka_id(nilai: float, desimal: int) -> str:
    """Angka gaya Indonesia: ribuan "." dan desimal "," (tanpa pembulatan liar)."""
    teks = f"{nilai:,.{desimal}f}"
    return teks.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def rupiah(nilai: float | None) -> str:
    """Rupiah penuh dua desimal — sama dengan format panel, jadi tidak ada dua
    bacaan untuk angka yang sama."""
    if nilai is None:
        return "—"
    return f"Rp {_angka_id(float(nilai), 2)}"


def kg(nilai: float | None) -> str:
    """Kuantitas kg: satu desimal, tanpa ",0" yang mengarang presisi."""
    if nilai is None:
        return "—"
    angka = float(nilai)
    teks = _angka_id(angka, 1)
    if teks.endswith(",0"):
        teks = teks[:-2]
    return f"{teks} kg"


def waktu_wib(saat: datetime | None) -> str:
    """Timestamp → "19 Okt 2026 14.05 WIB" (tanggal dari DB, zona disebut)."""
    if saat is None:
        return "—"
    if saat.tzinfo is None:
        saat = saat.replace(tzinfo=timezone.utc)
    lokal = saat.astimezone(WIB)
    return f"{lokal.day} {BULAN[lokal.month - 1]} {lokal.year} {lokal:%H.%M} WIB"


def nama_berkas(po_number: str) -> str:
    """Nama unduhan: hanya karakter aman, prefix `PO-` sekali."""
    bersih = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in po_number)
    return f"PO-{bersih}.pdf"


def catatan_status(status: str | None) -> str:
    """Arti status PO yang benar-benar terjadi di sistem ini (bukan klaim SAP).

    Backend hanya menulis `submitted` saat mengeksekusi keputusan; `confirmed`
    hanya ada pada baris yang diimpor dari SAP. Menuliskan ini mencegah
    pembaca menyimpulkan aplikasi sudah mengonfirmasi ke SAP.
    """
    if status == "confirmed":
        return (
            "Status Terkonfirmasi berarti baris ini sudah ada di data SAP dan "
            "diimpor ke aplikasi — bukan hasil konfirmasi yang dikirim aplikasi."
        )
    if status == "submitted":
        return (
            "Status Terkirim berarti PO diterbitkan aplikasi setelah keputusan "
            "dieksekusi; konfirmasi dari SAP untuk PO ini belum tercatat."
        )
    if status == "draft":
        return "Status Draf berarti PO belum dikirim ke SAP."
    return ""


# ── Tata letak PDF ──────────────────────────────────────────────────────────

_INK = colors.HexColor("#0F172A")
_MUTED = colors.HexColor("#64748B")
_LINE = colors.HexColor("#CBD5E1")
_ACCENT = colors.HexColor("#0F766E")
_TINT = colors.HexColor("#F1F5F9")


def _gaya() -> dict[str, ParagraphStyle]:
    dasar = ParagraphStyle(
        "dasar", fontName="Helvetica", fontSize=9.5, leading=13, textColor=_INK
    )
    return {
        "dasar": dasar,
        "merek": ParagraphStyle(
            "merek", parent=dasar, fontName="Helvetica-Bold", fontSize=8.5,
            leading=11, textColor=_ACCENT, spaceAfter=2,
        ),
        "judul": ParagraphStyle(
            "judul", parent=dasar, fontName="Helvetica-Bold", fontSize=21,
            leading=24, textColor=_INK,
        ),
        "nomor": ParagraphStyle(
            "nomor", parent=dasar, fontName="Helvetica-Bold", fontSize=12,
            leading=15, alignment=2,
        ),
        "kecil": ParagraphStyle(
            "kecil", parent=dasar, fontSize=8, leading=11, textColor=_MUTED
        ),
        "kecil_kanan": ParagraphStyle(
            "kecil_kanan", parent=dasar, fontSize=8, leading=11, textColor=_MUTED,
            alignment=2,
        ),
        "bagian": ParagraphStyle(
            "bagian", parent=dasar, fontName="Helvetica-Bold", fontSize=10.5,
            leading=14, textColor=_INK, spaceBefore=12, spaceAfter=5,
        ),
        "sel": ParagraphStyle("sel", parent=dasar, fontSize=9, leading=12),
        "sel_tebal": ParagraphStyle(
            "sel_tebal", parent=dasar, fontName="Helvetica-Bold", fontSize=9,
            leading=12,
        ),
        "sel_kecil": ParagraphStyle(
            "sel_kecil", parent=dasar, fontSize=8.5, leading=11, textColor=_MUTED
        ),
        "catatan": ParagraphStyle(
            "catatan", parent=dasar, fontSize=8, leading=11, textColor=_MUTED,
            spaceBefore=4,
        ),
    }


def _p(teks: object, gaya: ParagraphStyle) -> Paragraph:
    return Paragraph(escape("—" if teks is None else str(teks)), gaya)


def _tabel(data, lebar, gaya_tambahan=None) -> Table:
    tabel = Table(data, colWidths=lebar, hAlign="LEFT")
    perintah = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _LINE),
        ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
    ]
    if gaya_tambahan:
        perintah.extend(gaya_tambahan)
    tabel.setStyle(TableStyle(perintah))
    return tabel


def bangun_pdf(dokumen: dict) -> bytes:
    """Susun PDF satu PO dari dict yang sudah dibaca route (tanpa query DB).

    `dokumen` berisi: po_number, status, created_at, ordered_quantity, price,
    total, material_number, commodity_name, location_name, supplier_name,
    keputusan (dict), persetujuan (list), syarat (dict), dibuat_pada (datetime).
    """
    g = _gaya()
    buf = io.BytesIO()
    po_number = str(dokumen.get("po_number") or "—")

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MUTED)
        tinggi = 14 * mm
        canvas.setStrokeColor(_LINE)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, tinggi + 6, A4[0] - 20 * mm, tinggi + 6)
        canvas.drawString(20 * mm, tinggi, f"MealChain Guardian · SAP simulasi · {po_number}")
        canvas.drawRightString(A4[0] - 20 * mm, tinggi, f"halaman {_doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=24 * mm,
        title=f"Purchase Order {po_number}",
        author="MealChain Guardian",
        subject="Purchase order (SAP simulasi) beserta dasar persetujuannya",
        creator="MealChain Guardian",
    )
    lebar = A4[0] - 40 * mm
    story: list = []

    # ── Kepala dokumen ──────────────────────────────────────────────────────
    kepala = Table(
        [
            [
                [
                    _p("MEALCHAIN GUARDIAN", g["merek"]),
                    _p("PURCHASE ORDER", g["judul"]),
                    _p("Dokumen dari data aplikasi · SAP simulasi", g["kecil"]),
                ],
                [
                    _p(po_number, g["nomor"]),
                    _p(f"Status: {status_po_label(dokumen.get('status'))}", g["kecil_kanan"]),
                    _p(f"Terbit: {waktu_wib(dokumen.get('created_at'))}", g["kecil_kanan"]),
                ],
            ]
        ],
        colWidths=[lebar * 0.58, lebar * 0.42],
        hAlign="LEFT",
    )
    kepala.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, _ACCENT),
            ]
        )
    )
    story.append(kepala)
    story.append(Spacer(1, 10))

    # ── Pihak & bahan ───────────────────────────────────────────────────────
    story.append(_p("Pihak & bahan", g["bagian"]))
    baris_pihak = [
        [
            _p("Dikirim ke", g["sel_kecil"]),
            _p(dokumen.get("location_name") or "—", g["sel_tebal"]),
            _p("Pemasok", g["sel_kecil"]),
            _p(dokumen.get("supplier_name") or "—", g["sel_tebal"]),
        ],
        [
            _p("Bahan", g["sel_kecil"]),
            _p(dokumen.get("commodity_name") or "bahan tidak tercatat", g["sel"]),
            _p("Nomor bahan", g["sel_kecil"]),
            _p(dokumen.get("material_number") or "—", g["sel"]),
        ],
    ]
    story.append(
        _tabel(
            baris_pihak,
            [lebar * 0.16, lebar * 0.34, lebar * 0.16, lebar * 0.34],
            [("BACKGROUND", (0, 0), (0, -1), _TINT), ("BACKGROUND", (2, 0), (2, -1), _TINT)],
        )
    )

    # ── Rincian pesanan ─────────────────────────────────────────────────────
    story.append(_p("Rincian pesanan", g["bagian"]))
    qty = dokumen.get("ordered_quantity")
    harga = dokumen.get("price")
    total = dokumen.get("total")
    rincian = [
        [
            _p("Bahan", g["sel_tebal"]),
            _p("Jumlah", g["sel_tebal"]),
            _p("Harga satuan", g["sel_tebal"]),
            _p("Nilai", g["sel_tebal"]),
        ],
        [
            _p(dokumen.get("commodity_name") or dokumen.get("material_number") or "—", g["sel"]),
            _p(kg(qty), g["sel"]),
            _p(f"{rupiah(harga)} / kg" if harga is not None else "—", g["sel"]),
            _p(rupiah(total), g["sel"]),
        ],
        [
            _p("Total nilai pesanan", g["sel_tebal"]),
            "",
            "",
            _p(rupiah(total), g["sel_tebal"]),
        ],
    ]
    story.append(
        _tabel(
            rincian,
            [lebar * 0.40, lebar * 0.16, lebar * 0.22, lebar * 0.22],
            [
                ("BACKGROUND", (0, 0), (-1, 0), _TINT),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("SPAN", (0, 2), (2, 2)),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FAFAF9")),
            ],
        )
    )
    cerita_status = catatan_status(dokumen.get("status"))
    if cerita_status:
        story.append(_p(cerita_status, g["catatan"]))

    # ── Dasar persetujuan ───────────────────────────────────────────────────
    keputusan = dokumen.get("keputusan") or {}
    story.append(_p("Dasar persetujuan", g["bagian"]))
    identitas = [
        [
            _p("ID keputusan", g["sel_kecil"]),
            _p(keputusan.get("id") or "—", g["sel"]),
            _p("Status keputusan", g["sel_kecil"]),
            _p(status_keputusan_label(keputusan.get("status")), g["sel_tebal"]),
        ],
        [
            _p("Jenis", g["sel_kecil"]),
            _p(jenis_keputusan_label(keputusan.get("jenis")), g["sel"]),
            _p("Versi", g["sel_kecil"]),
            _p(f"v{keputusan.get('iteration') or 1}", g["sel"]),
        ],
        [
            _p("Diajukan", g["sel_kecil"]),
            _p(
                f"{keputusan.get('proposed_by') or '—'} · {waktu_wib(keputusan.get('created_at'))}",
                g["sel"],
            ),
            _p("Berlaku sampai", g["sel_kecil"]),
            _p(waktu_wib(keputusan.get("expires_at")), g["sel"]),
        ],
    ]
    story.append(
        _tabel(
            identitas,
            [lebar * 0.18, lebar * 0.42, lebar * 0.16, lebar * 0.24],
            [("BACKGROUND", (0, 0), (0, -1), _TINT), ("BACKGROUND", (2, 0), (2, -1), _TINT)],
        )
    )

    # Jejak persetujuan: hanya baris yang benar-benar ada di DB.
    persetujuan = dokumen.get("persetujuan") or []
    story.append(Spacer(1, 8))
    if persetujuan:
        jejak = [
            [
                _p("Peran", g["sel_tebal"]),
                _p("Nama", g["sel_tebal"]),
                _p("Keputusan", g["sel_tebal"]),
                _p("Waktu", g["sel_tebal"]),
                _p("Catatan", g["sel_tebal"]),
            ]
        ]
        for baris in persetujuan:
            jejak.append(
                [
                    _p(peran_label(baris.get("role")), g["sel"]),
                    _p(baris.get("name") or "—", g["sel"]),
                    _p(
                        "Setuju" if baris.get("approved") else "Menolak",
                        g["sel_tebal"] if baris.get("approved") else g["sel"],
                    ),
                    _p(waktu_wib(baris.get("approved_at")), g["sel"]),
                    _p(baris.get("comment") or "—", g["sel_kecil"]),
                ]
            )
        story.append(
            _tabel(
                jejak,
                [
                    lebar * 0.16,
                    lebar * 0.19,
                    lebar * 0.14,
                    lebar * 0.20,
                    lebar * 0.31,
                ],
                [("BACKGROUND", (0, 0), (-1, 0), _TINT)],
            )
        )
    else:
        story.append(_p("Belum ada baris persetujuan tercatat untuk keputusan ini.", g["dasar"]))

    syarat = dokumen.get("syarat") or {}
    if syarat:
        tercatat = len([b for b in persetujuan if b.get("approved")])
        minimal = syarat.get("min_approvals")
        kalimat = f"{tercatat} persetujuan tercatat"
        if isinstance(minimal, int):
            kalimat += f" dari {minimal} yang disyaratkan matriks persetujuan"
        kalimat += (
            " — syarat terpenuhi." if syarat.get("satisfied") else " — syarat belum terpenuhi."
        )
        story.append(_p(kalimat, g["catatan"]))

    # ── Kaki dokumen ────────────────────────────────────────────────────────
    penutup = [
        _p(
            "Dokumen ini dibuat otomatis oleh MealChain Guardian pada "
            f"{waktu_wib(dokumen.get('dibuat_pada'))}.",
            g["catatan"],
        ),
        _p(
            "Sumber angka: tabel purchase order SAP simulasi (mock_sap_table) di "
            "basis data aplikasi — bukan SAP S/4HANA produksi. Nomor PO, jumlah, "
            "harga, status, dan jejak persetujuan dibaca apa adanya dari basis "
            "data; total nilai = harga × jumlah.",
            g["catatan"],
        ),
    ]
    story.append(Spacer(1, 14))
    story.extend(penutup)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
