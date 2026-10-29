"""Dokumen purchase order (PDF) — satu PO, seluruh angkanya dari basis data.

Latar (20 Okt 2026, permintaan pemilik): panel "Purchase order" pada tab
Decision & Evidence hanya menampilkan baris di layar. Kepala SPPG tidak punya
berkas yang bisa diunduh, dicetak, atau diserahkan ke bagian keuangan — padahal
justru PO itu bukti bahwa dua persetujuan manusia benar-benar menghasilkan
dokumen pembelian.

Tata letak memakai template PO korporat (permintaan pemilik, 29 Okt 2026):
kepala dokumen berisi merek + meta PO, blok "Kepada (vendor)" / "Kirim ke
(tujuan)" / "Bahan", tabel rincian pesanan bernomor dengan kolom
jumlah–satuan–harga satuan–nilai, baris total, lalu blok pengesahan
(disiapkan/didisetujui). Tiga bagian lama DIHAPUS atas permintaan yang sama:
blok "Safe Delivered Cost (analitis, bukan tagihan)", blok "Dasar persetujuan",
serta seluruh keterangan di bawah tabel (catatan kaki `*` harga satuan turunan /
lumpsum / selisih pembulatan, kalimat arti status, "Syarat & ketentuan", dan
kalimat "Sumber angka"). Konsekuensinya rincian pesanan memuat SENDIRI komponen
bahan, transportasi, dan penanganan — bukan hanya bahan dan total.

Lima aturan yang dipegang modul ini:

1. **Hanya PO yang sudah disetujui.** PDF terbit untuk PO yang lahir dari
   keputusan berstatus `approved` atau `executed`. PO impor tanpa keputusan
   (`4500000001`) dan PO dari keputusan yang masih menunggu TIDAK punya PDF:
   dokumen pembelian untuk sesuatu yang belum disetujui adalah klaim palsu.
   Penolakan disampaikan route sebagai 409 + alasan, bukan dokumen kosong.
2. **Tidak ada angka baru.** Kuantitas & harga dibaca dari kolom apa adanya;
   nilai baris bahan = komponen `purchase_total` (atau harga × kuantitas bila
   rincian komersial tidak ada), nilai transportasi/penanganan = komponennya
   sendiri, total = harga × kuantitas. Harga satuan bahan diturunkan
   (nilai ÷ jumlah) dan tampil di kolomnya sendiri tanpa catatan kaki — kolom
   Nilai tetap angka yang tercatat. Tanggal ditampilkan dalam WIB (UTC+7) dan
   diberi label zona, bukan waktu server yang tidak diketahui pembaca.
3. **Asal data disebut di setiap halaman.** "SAP simulasi" wajib (Rules.md §4):
   data mock tidak boleh tampil seolah SAP S/4HANA produksi.
4. **Yang tidak diketahui ditulis "—".** Pemasok/lokasi/bahan yang NULL tidak
   diganti tebakan; komponen biaya yang tidak tercatat tidak dicetak sebagai
   Rp 0. Status asing ditampilkan apa adanya, bukan diterjemahkan dengan menebak.
5. **Estimasi risiko internal tidak pernah masuk tagihan.** Penalti (perkiraan
   kerugian, risiko kesegaran, penalti keamanan) tidak dicetak sama sekali dan
   tidak dijumlahkan ke nilai PO.
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from xml.sax.saxutils import escape

import jwt as pyjwt
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


def kuantitas(nilai: float | None) -> str:
    """Kuantitas tanpa satuan (kolom "Jumlah" terpisah): ",0" tidak dikarang."""
    if nilai is None:
        return "—"
    teks = _angka_id(float(nilai), 1)
    return teks[:-2] if teks.endswith(",0") else teks


def kg(nilai: float | None) -> str:
    """Kuantitas kg: satu desimal, tanpa ",0" yang mengarang presisi."""
    if nilai is None:
        return "—"
    return f"{kuantitas(nilai)} kg"


def waktu_wib(saat: datetime | None) -> str:
    """Timestamp → "19 Okt 2026 14.05 WIB" (tanggal dari DB, zona disebut)."""
    if saat is None:
        return "—"
    if saat.tzinfo is None:
        saat = saat.replace(tzinfo=timezone.utc)
    lokal = saat.astimezone(WIB)
    return f"{lokal.day} {BULAN[lokal.month - 1]} {lokal.year} {lokal:%H.%M} WIB"


def tanggal_wib(saat: datetime | None) -> str:
    """Tanggal saja — meta PO tidak perlu jam yang tidak dibaca siapa pun."""
    if saat is None:
        return "—"
    if saat.tzinfo is None:
        saat = saat.replace(tzinfo=timezone.utc)
    lokal = saat.astimezone(WIB)
    return f"{lokal.day} {BULAN[lokal.month - 1]} {lokal.year}"


def nama_berkas(po_number: str) -> str:
    """Nama unduhan: hanya karakter aman, prefix `PO-` sekali."""
    bersih = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in po_number)
    return f"PO-{bersih}.pdf"


# ── Tautan PDF publik untuk Joule ───────────────────────────────────────────
#
# Joule hanya mengirim teks: ia tidak bisa melampirkan berkas dan tidak punya
# token Bearer pengguna. Supaya juri tetap bisa membuka dokumen yang sedang
# dibacanya, jembatan mengirim SATU tautan bertanda tangan yang berlaku singkat.
# Tautan itu tidak memberi wewenang lain: isinya hanya nomor PO, umurnya
# dibatasi, dan rute publiknya tetap menolak PO yang keputusannya belum
# disetujui — sama seperti rute ber-token.

#: Umur tautan. Cukup untuk satu sesi demo, terlalu pendek untuk dibagikan.
UMUR_TAUTAN_PDF_MENIT = 15


def _kunci_tautan() -> str:
    kunci = os.environ.get("JWT_SECRET") or ""
    if not kunci:
        raise RuntimeError(
            "JWT_SECRET belum diset — tautan PDF publik tidak bisa ditandatangani"
        )
    return kunci


def token_pdf(
    po_number: str, *, menit: int = UMUR_TAUTAN_PDF_MENIT, sekarang: datetime | None = None
) -> str:
    """Token pendek untuk satu nomor PO (`typ: po_pdf`)."""
    saat = sekarang or datetime.now(timezone.utc)
    klaim = {
        "sub": po_number,
        "typ": "po_pdf",
        "iat": int(saat.timestamp()),
        "exp": int((saat + timedelta(minutes=menit)).timestamp()),
    }
    return pyjwt.encode(klaim, _kunci_tautan(), algorithm="HS256")


def nomor_dari_token_pdf(token: str) -> str | None:
    """Nomor PO dari token tautan, atau `None` bila tidak sah/kedaluwarsa."""
    try:
        klaim = pyjwt.decode(
            token,
            _kunci_tautan(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except pyjwt.PyJWTError:
        return None
    if klaim.get("typ") != "po_pdf":
        return None
    nomor = str(klaim.get("sub") or "").strip()
    return nomor or None


def link_pdf_publik(
    po_number: str, basis: str, *, menit: int = UMUR_TAUTAN_PDF_MENIT
) -> str:
    """URL absolut yang bisa dibuka tanpa token login (berlaku `menit` menit)."""
    nomor = quote(po_number, safe="")
    return f"{basis.rstrip('/')}/public/purchase-orders/{nomor}/pdf?t={token_pdf(po_number, menit=menit)}"


# ── Tata letak PDF ──────────────────────────────────────────────────────────

_INK = colors.HexColor("#0F172A")
_MUTED = colors.HexColor("#64748B")
_LINE = colors.HexColor("#CBD5E1")
_ACCENT = colors.HexColor("#0F766E")
_TINT = colors.HexColor("#F1F5F9")
_TOTAL = colors.HexColor("#FAFAF9")


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
        "label": ParagraphStyle(
            "label", parent=dasar, fontSize=7.5, leading=10, textColor=_MUTED,
            spaceBefore=1,
        ),
        "meta_nilai": ParagraphStyle(
            "meta_nilai", parent=dasar, fontName="Helvetica-Bold", fontSize=9,
            leading=12, alignment=2,
        ),
        "meta_ref": ParagraphStyle(
            "meta_ref", parent=dasar, fontSize=7, leading=9, alignment=2,
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
        "kepala_sel": ParagraphStyle(
            "kepala_sel", parent=dasar, fontName="Helvetica-Bold", fontSize=7.5,
            leading=10, textColor=_MUTED,
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


def _komponen_biaya(biaya: object) -> list[tuple[str, float]]:
    """Komponen yang benar-benar tercatat, urut: bahan, transportasi, penanganan.

    Komponen yang `None` tidak dikembalikan — mencetaknya sebagai Rp 0 berarti
    mengarang biaya yang tidak ada di data.
    """
    if not isinstance(biaya, dict):
        return []
    hasil: list[tuple[str, float]] = []
    for label, kunci in (
        ("Bahan", "purchase_total"),
        ("Transportasi", "transport_total"),
        ("Penanganan", "handling_total"),
    ):
        nilai = biaya.get(kunci)
        if nilai is None:
            continue
        try:
            hasil.append((label, float(nilai)))
        except (TypeError, ValueError):
            continue
    return hasil


def bangun_pdf(dokumen: dict) -> bytes:
    """Susun PDF satu PO dari dict yang sudah dibaca route (tanpa query DB).

    `dokumen` berisi: po_number, status, created_at, ordered_quantity, price,
    total, material_number, commodity_name, location_name, supplier_name,
    commercial_cost, cost_legacy, keputusan (dict), persetujuan (list),
    dibuat_pada (datetime).
    """
    g = _gaya()
    buf = io.BytesIO()
    po_number = str(dokumen.get("po_number") or "—")
    keputusan = dokumen.get("keputusan") or {}
    persetujuan = dokumen.get("persetujuan") or []

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

    # ── Kepala dokumen: merek + identitas PO ────────────────────────────────
    meta = Table(
        [
            [_p("Nomor PO", g["label"]), _p(po_number, g["meta_nilai"])],
            [
                _p("Tanggal", g["label"]),
                _p(tanggal_wib(dokumen.get("created_at")), g["meta_nilai"]),
            ],
            [
                _p("Status", g["label"]),
                _p(status_po_label(dokumen.get("status")), g["meta_nilai"]),
            ],
            [_p("Mata uang", g["label"]), _p("IDR (Rupiah)", g["meta_nilai"])],
            [
                _p("Ref. keputusan", g["label"]),
                _p(keputusan.get("id") or "—", g["meta_ref"]),
            ],
        ],
        colWidths=[lebar * 0.15, lebar * 0.33],
        hAlign="LEFT",
    )
    meta.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, _LINE),
            ]
        )
    )
    kepala = Table(
        [
            [
                [
                    _p("MEALCHAIN GUARDIAN", g["merek"]),
                    _p("PURCHASE ORDER", g["judul"]),
                    _p("Dokumen pembelian · SAP simulasi", g["kecil"]),
                ],
                meta,
            ]
        ],
        colWidths=[lebar * 0.52, lebar * 0.48],
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

    # ── Pihak & bahan: tiga blok khas PO korporat ───────────────────────────
    bahan_teks = dokumen.get("commodity_name") or "bahan tidak tercatat"
    if dokumen.get("material_number"):
        bahan_teks = f"{bahan_teks} · {dokumen['material_number']}"
    pihak = Table(
        [
            [
                _p("KEPADA (VENDOR)", g["kepala_sel"]),
                _p("KIRIM KE (TUJUAN)", g["kepala_sel"]),
                _p("BAHAN", g["kepala_sel"]),
            ],
            [
                _p(dokumen.get("supplier_name") or "—", g["sel_tebal"]),
                _p(dokumen.get("location_name") or "—", g["sel_tebal"]),
                _p(bahan_teks, g["sel"]),
            ],
        ],
        colWidths=[lebar * 0.36, lebar * 0.28, lebar * 0.36],
        hAlign="LEFT",
    )
    pihak.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 0), (-1, 0), _TINT),
                ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, _LINE),
                ("LINEAFTER", (0, 0), (1, -1), 0.4, _LINE),
            ]
        )
    )
    story.append(pihak)

    # ── Rincian pesanan: bahan, transportasi, penanganan, lalu total ────────
    # Tabel inilah yang memuat komponen tagihan. Sejak 29 Okt 2026 komponen
    # transportasi/penanganan pindah ke sini (blok "Rincian biaya komersial"
    # dan blok Safe Delivered Cost dihapus atas permintaan pemilik).
    story.append(_p("Rincian pesanan", g["bagian"]))
    qty = dokumen.get("ordered_quantity")
    harga = dokumen.get("price")
    total = dokumen.get("total")
    biaya = dokumen.get("commercial_cost")
    komponen = _komponen_biaya(biaya)

    kolom = [
        lebar * 0.06,
        lebar * 0.36,
        lebar * 0.10,
        lebar * 0.11,
        lebar * 0.18,
        lebar * 0.19,
    ]
    rincian: list[list] = [
        [
            _p("No", g["sel_tebal"]),
            _p("Uraian", g["sel_tebal"]),
            _p("Jumlah", g["sel_tebal"]),
            _p("Satuan", g["sel_tebal"]),
            _p("Harga satuan", g["sel_tebal"]),
            _p("Nilai", g["sel_tebal"]),
        ]
    ]

    bahan_nilai = next((n for label, n in komponen if label == "Bahan"), None)
    if bahan_nilai is None:
        bahan_nilai = float(total) if total is not None else None
    harga_bahan = None
    if bahan_nilai is not None and qty:
        harga_bahan = round(bahan_nilai / float(qty), 2)
    if harga_bahan is None and harga is not None:
        harga_bahan = float(harga)

    uraian_bahan = "Bahan"
    if dokumen.get("commodity_name"):
        uraian_bahan += f" — {dokumen['commodity_name']}"

    rincian.append(
        [
            _p("1", g["sel"]),
            _p(uraian_bahan, g["sel"]),
            _p(kuantitas(qty), g["sel"]),
            _p("kg", g["sel"]),
            _p(rupiah(harga_bahan), g["sel"]),
            _p(rupiah(bahan_nilai), g["sel"]),
        ]
    )

    nomor = 2
    for label in ("Transportasi", "Penanganan"):
        nilai = next((n for nama, n in komponen if nama == label), None)
        if nilai is None:
            continue
        rincian.append(
            [
                _p(str(nomor), g["sel"]),
                _p(label, g["sel"]),
                _p("1", g["sel"]),
                _p("ls", g["sel"]),
                _p(rupiah(nilai), g["sel"]),
                _p(rupiah(nilai), g["sel"]),
            ]
        )
        nomor += 1

    invoice_total = None
    if isinstance(biaya, dict) and biaya.get("invoice_total") is not None:
        invoice_total = float(biaya["invoice_total"])
    total_nilai = float(total) if total is not None else None
    selisih = 0.0
    if invoice_total is not None and total_nilai is not None:
        selisih = round(invoice_total - total_nilai, 2)

    label_total = "Total PO"
    if komponen:
        label_total = "Total PO (bahan + transportasi + penanganan)"

    awal_total = len(rincian)
    if invoice_total is not None and abs(selisih) >= 0.01:
        rincian.append(
            [
                _p("Subtotal (jumlah baris di atas)", g["sel"]),
                "",
                "",
                "",
                "",
                _p(rupiah(invoice_total), g["sel"]),
            ]
        )
        rincian.append(
            [
                _p("Total PO (harga satuan × jumlah)", g["sel_tebal"]),
                "",
                "",
                "",
                "",
                _p(rupiah(total_nilai), g["sel_tebal"]),
            ]
        )
    else:
        rincian.append(
            [
                _p(label_total, g["sel_tebal"]),
                "",
                "",
                "",
                "",
                _p(rupiah(total_nilai), g["sel_tebal"]),
            ]
        )

    gaya_rincian = [
        ("BACKGROUND", (0, 0), (-1, 0), _TINT),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("LINEABOVE", (0, awal_total), (-1, awal_total), 0.8, _INK),
        ("BACKGROUND", (0, awal_total), (-1, -1), _TOTAL),
    ]
    for baris in range(awal_total, len(rincian)):
        gaya_rincian.append(("SPAN", (0, baris), (4, baris)))
    story.append(_tabel(rincian, kolom, gaya_rincian))

    # Catatan kaki bertanda `*` (harga satuan turunan, lumpsum transportasi,
    # selisih pembulatan) beserta kalimat arti status DIHAPUS 29 Okt 2026 atas
    # permintaan pemilik: di bawah tabel rincian hanya boleh ada blok pengesahan,
    # tanpa keterangan tambahan. Angka yang sama tetap tampil di kolom Nilai.

    if dokumen.get("cost_legacy") == "legacy_unmigrated":
        story.append(
            _p(
                "Biaya: legacy_unmigrated — PO ini memakai format biaya lama "
                "(sebelum kontrak invoice), jadi komponen transportasi dan "
                "penanganan tidak tercatat pada rincian biaya keputusan dan tidak "
                "tercetak sebagai baris. Angka historis tidak diubah; migrasi "
                "butuh keputusan pemilik.",
                g["catatan"],
            )
        )

    # Blok "Syarat & ketentuan" (nilai IDR dua desimal, sumber angka mock,
    # komponen dibebankan terpisah, estimasi risiko tidak ditagihkan, persetujuan
    # digital) DIHAPUS 29 Okt 2026 atas permintaan pemilik. Asal data tetap
    # disebut di footer setiap halaman ("SAP simulasi", Rules.md §4).

    # ── Pengesahan: disiapkan vs disetujui (blok tanda tangan PO korporat) ──
    # Menggantikan blok "Dasar persetujuan" yang dihapus 29 Okt 2026: yang
    # dibutuhkan pembaca dokumen pembelian adalah siapa yang mengesahkan dan
    # kapan, bukan rincian versi/jendela keputusan.
    story.append(_p("Pengesahan", g["bagian"]))
    if persetujuan:
        disetujui: list = []
        for baris in persetujuan:
            disetujui.append(
                _p(
                    f"{peran_label(baris.get('role'))} · {baris.get('name') or '—'}",
                    g["sel_tebal"],
                )
            )
            disetujui.append(
                _p(
                    f"{'Setuju' if baris.get('approved') else 'Menolak'} · "
                    f"{waktu_wib(baris.get('approved_at'))}",
                    g["sel_kecil"],
                )
            )
            if baris.get("comment"):
                disetujui.append(_p(f"Catatan: {baris['comment']}", g["sel_kecil"]))
            disetujui.append(Spacer(1, 12))
    else:
        disetujui = [
            _p("Belum ada baris persetujuan tercatat untuk keputusan ini.", g["sel"])
        ]

    disiapkan = [
        _p("MealChain Guardian", g["sel_tebal"]),
        _p("dokumen dibangkitkan otomatis oleh sistem", g["sel_kecil"]),
        _p(waktu_wib(dokumen.get("dibuat_pada")), g["sel_kecil"]),
    ]
    pengesahan = Table(
        [
            [
                _p("DISIAPKAN OLEH", g["kepala_sel"]),
                _p("DISETUJUI OLEH", g["kepala_sel"]),
            ],
            [disiapkan, disetujui],
        ],
        colWidths=[lebar * 0.38, lebar * 0.62],
        hAlign="LEFT",
    )
    pengesahan.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 0), (-1, 0), _TINT),
                ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, _LINE),
                ("LINEAFTER", (0, 0), (0, -1), 0.4, _LINE),
            ]
        )
    )
    story.append(pengesahan)

    # ── Kaki dokumen ────────────────────────────────────────────────────────
    # Kalimat "Sumber angka: tabel purchase order SAP simulasi (mock_sap_table)
    # …" dihapus 29 Okt 2026 bersama Syarat & ketentuan; footer setiap halaman
    # tetap menulis "SAP simulasi" (Rules.md §4).
    story.append(Spacer(1, 14))
    story.append(
        _p(
            "Dokumen ini dibuat otomatis oleh MealChain Guardian pada "
            f"{waktu_wib(dokumen.get('dibuat_pada'))}.",
            g["catatan"],
        )
    )

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
