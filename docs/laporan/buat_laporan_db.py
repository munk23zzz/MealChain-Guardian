# -*- coding: utf-8 -*-
"""Laporan basis data MealChain Guardian (reportlab platypus)."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

NAVY = colors.HexColor("#0B1220")
INK = colors.HexColor("#1E293B")
SLATE = colors.HexColor("#475569")
MUTED = colors.HexColor("#64748B")
BLUE = colors.HexColor("#2563EB")
ROW = colors.HexColor("#F8FAFC")
BORDER = colors.HexColor("#CBD5E1")
GREEN = colors.HexColor("#2E7D32")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B91C1C")

PAGE_W, PAGE_H = A4
M_L, M_R, M_T, M_B = 20 * mm, 18 * mm, 20 * mm, 18 * mm
CW = PAGE_W - M_L - M_R

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.4,
                      leading=13.8, textColor=INK, alignment=TA_LEFT, spaceAfter=0)
LEAD = ParagraphStyle("lead", parent=BODY, fontSize=10.4, leading=15.4, textColor=colors.HexColor("#334155"))
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=15.5, leading=19,
                    textColor=NAVY, spaceBefore=10, spaceAfter=7)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=11.2, leading=14.5,
                    textColor=BLUE, spaceBefore=9, spaceAfter=4)
CAP = ParagraphStyle("cap", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED, spaceBefore=3)
CAP_TOP = ParagraphStyle("captop", parent=CAP, spaceBefore=7, spaceAfter=2.5)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.1, leading=10.9)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("head", parent=CELL, fontName="Helvetica-Bold", fontSize=8.3,
                      textColor=colors.white)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=11, bulletIndent=2, spaceAfter=2.5)
MONO = ParagraphStyle("mono", parent=BODY, fontName="Courier", fontSize=8, leading=11,
                      textColor=colors.HexColor("#0F172A"))


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, BULLET, bulletText="-") for t in items]


def rows_table(data, widths, header=True, zebra=True, size=8.1, center=(), caption=None):
    body = []
    if caption:
        caprow = [Paragraph(caption, ParagraphStyle("capin", parent=CELL, fontSize=7.7,
                                                    leading=10.2, textColor=MUTED))]
        caprow += [""] * (len(widths) - 1)
        body.append(caprow)
    for r, row in enumerate(data):
        line = []
        for c, cell in enumerate(row):
            if isinstance(cell, str):
                st = HEAD if (header and r == 0) else (CELLB if c == 0 and not (header and r == 0) else CELL)
                if st.fontSize != size:
                    st = ParagraphStyle(f"c{size}", parent=st, fontSize=size, leading=size * 1.34)
                line.append(Paragraph(cell, st))
            else:
                line.append(cell)
        body.append(line)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4)]
    if caption:
        style += [("SPAN", (0, 0), (-1, 0)),
                  ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                  ("TOPPADDING", (0, 0), (-1, 0), 5)]
        hrow = 1
    else:
        hrow = 0
    if header:
        style.append(("BACKGROUND", (0, hrow), (-1, hrow), NAVY))
        start = hrow + 1
        repeat = start
    else:
        start = hrow
        repeat = 0
    if zebra:
        for i in range(start, len(body)):
            if (i - start) % 2 == 1:
                style.append(("BACKGROUND", (0, i), (-1, i), ROW))
    for c in center:
        style.append(("ALIGN", (c, 0), (c, -1), "CENTER"))
    t = Table(body, colWidths=widths, repeatRows=repeat, hAlign="LEFT")
    t.setStyle(TableStyle(style))
    return t


def callout(text, color=BLUE, bg=colors.HexColor("#EFF6FF")):
    t = Table([[Paragraph(text, ParagraphStyle("co", parent=CELL, fontSize=8.7, leading=12.3))]], colWidths=[CW])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.6, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def h1(n, text):
    return Paragraph(f'<font color="#2563EB">{n}</font>&nbsp;&nbsp;{text}', H1)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(M_L, M_B - 6 * mm, PAGE_W - M_R, M_B - 6 * mm)
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(M_L, M_B - 10.5 * mm, "MealChain Guardian - laporan basis data")
    canvas.drawRightString(PAGE_W - M_R, M_B - 10.5 * mm, "%d" % doc.page)
    canvas.restoreState()


def cover():
    out = [NextPageTemplate("cover")]
    band = Table([[""]], colWidths=[CW], rowHeights=[6 * mm])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GREEN)]))
    out += [Spacer(1, 26 * mm), band, Spacer(1, 9 * mm)]
    out.append(Paragraph("Basis Data MealChain Guardian", ParagraphStyle(
        "cv", parent=BODY, fontName="Helvetica-Bold", fontSize=26, leading=31, textColor=NAVY)))
    out.append(Spacer(1, 3 * mm))
    out.append(Paragraph("Skema, integritas, ruang, dan temuan audit", ParagraphStyle(
        "cv2", parent=BODY, fontSize=14, leading=18, textColor=SLATE)))
    out.append(Spacer(1, 7 * mm))
    out.append(Paragraph(
        "Semua angka di laporan ini dibaca langsung dari instance PostgreSQL yang dipakai aplikasi, "
        "bukan dari dokumen rencana: jumlah baris, ukuran per tabel, constraint, indeks, dan hasil "
        "pemeriksaan integritas dijalankan pada 21 Oktober 2026.", ParagraphStyle(
            "cv3", parent=BODY, fontSize=10.1, leading=15.3, textColor=colors.HexColor("#334155"))))
    out.append(Spacer(1, 12 * mm))
    meta = [
        ["Mesin", "PostgreSQL 16.15 (Alpine, x86_64), database mealchain, UTF8 / en_US.utf8"],
        ["Skala", "23 tabel, 78 indeks, 52 foreign key, 43 CHECK, 27 migrasi (head 027_po_decision_cascade)"],
        ["Data", "1,4 MB data hidup di dalam 93 MB berkas database"],
        ["Status", "Rantai ledger valid 72 blok (linked_ratio 1,0), 0 foreign key yatim, 1 sesi demo berjalan"],
    ]
    t = Table([[Paragraph(a, CELLB), Paragraph(b, CELL)] for a, b in meta], colWidths=[26 * mm, CW - 26 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    out += [t, Spacer(1, 9 * mm)]
    out.append(callout("Laporan ini menjawab empat pertanyaan: apa isi basis data, aturan apa yang dijaga "
                       "oleh constraint, berapa ruang yang sebenarnya dipakai, dan apa yang perlu dibereskan "
                       "sebelum data ini dipakai di luar demo.", color=GREEN, bg=colors.HexColor("#F0FDF4")))
    out.append(Spacer(1, 5 * mm))
    out.append(Paragraph("21 Oktober 2026", ParagraphStyle("dt", parent=BODY, fontSize=10, textColor=MUTED)))
    out.append(NextPageTemplate("body"))
    out.append(PageBreak())
    return out


def daftar_isi():
    data = [
        ["1", "Ringkasan dan skala", "Angka kunci: tabel, baris, indeks, constraint, data hidup vs ukuran berkas"],
        ["2", "Konvensi skema", "UUID, timestamptz, numeric untuk uang, vocabulary status, penandaan demo"],
        ["3", "Inventaris 23 tabel", "Baris, kolom, indeks, FK, CHECK, ukuran, dan peran tiap tabel"],
        ["4", "Peta relasi", "Tulang punggung data dan 52 foreign key yang mengikatnya"],
        ["5", "Integritas yang dijaga database", "CHECK lintas kolom, keunikan natural key, perilaku ON DELETE"],
        ["6", "Indeks dan perilaku performa", "78 indeks, mana yang belum pernah dipakai, pola query yang dilindungi"],
        ["7", "Ruang dan pemeliharaan", "Temuan bloat: 99,5% ruang kosong; autovacuum tidak mengembalikan disk"],
        ["8", "Migrasi dan evolusi skema", "27 versi, head 027_po_decision_cascade, kebijakan perubahan"],
        ["9", "Temuan audit", "Ledger yatim, stempel demo, kualitas referensi, hasil pemeriksaan"],
        ["10", "Siklus hidup data", "Seed versus demo, tiga penanda, aturan hapus, dan buktinya"],
        ["11", "Rekomendasi prioritas", "Enam tindakan berurutan dengan alasan dan risikonya"],
        ["12", "Lampiran", "Kolom tabel kunci dan daftar query verifikasi"],
    ]
    out = [Paragraph("Isi laporan", H1), Spacer(1, 4),
           rows_table([["Bagian", "Judul", "Isi"]] + data, [16 * mm, 62 * mm, CW - 78 * mm]),
           Spacer(1, 8),
           p("Cara membaca: bagian 1-3 memberitahu apa yang ada; bagian 4-6 memberitahu apa yang dijaga; "
             "bagian 7-9 adalah temuan yang diukur, termasuk yang tidak enak dilihat; bagian 10-12 dipakai "
             "saat merawat atau menguji basis data ini.", BODY),
           PageBreak()]
    return out


def s1():
    out = [h1("1", "Ringkasan dan skala"), Spacer(1, 3)]
    out.append(p("Basis data ini adalah satu instance PostgreSQL 16.15 berisi 23 tabel, dipakai bersama oleh "
                 "backend FastAPI, seeder demo, dan suite tes. Ia menyimpan referensi (lokasi, komoditas, pemasok, "
                 "pengguna), fakta operasional (pasokan, permintaan, harga, menu, pengiriman, pembuangan), objek "
                 "alur kerja (batch, keputusan, approval, bukti, eksklusi, penerimaan), cache rute jalan, dan "
                 "buku besar hash.", LEAD))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Ukuran", "Nilai terukur", "Catatan"],
        ["Tabel", "23", "22 tabel aplikasi + alembic_version"],
        ["Baris total", "1.163", "Terbesar: demand_records (280), price_signals (124), batches (120)"],
        ["Indeks", "78", "Termasuk 9 unique constraint dan 23 primary key"],
        ["Foreign key", "52", "0 baris yatim pada seluruh FK (diperiksa satu per satu)"],
        ["CHECK constraint", "43", "Vocabulary status, rentang angka, konsistensi antar-kolom"],
        ["Migrasi", "27 berkas", "Head: 027_po_decision_cascade"],
        ["Data hidup", "1,4 MB", "Jumlah tuple aktif seluruh tabel (heap, tanpa indeks)"],
        ["Ukuran berkas", "93 MB", "Heap 1,4 MB + indeks; sisanya ruang kosong sisa siklus hapus-semai"],
        ["Baris demo aktif", "20", "Keputusan demo Jakarta (8 kartu hidup) + 1 sesi berjalan; 120 batch template"],
    ], [34 * mm, 30 * mm, CW - 64 * mm],
                          caption="Tabel 1 - Angka kunci basis data, dibaca 21 Oktober 2026."))
    out.append(Spacer(1, 6))
    out.append(callout("<b>Ringkasan satu paragraf.</b> Skemanya sehat: aturan bisnis ditegakkan di database, "
                       "bukan hanya di aplikasi, dan tidak ada satu pun referensi yang menggantung. Masalahnya "
                       "bukan isi, melainkan ruang: 93 MB berkas dipakai untuk 1,4 MB data karena siklus "
                       "hapus-semai berulang meninggalkan sekitar 98% ruang kosong di beberapa tabel dan indeksnya. "
                       "Rantai ledger utuh (72 blok, tanpa celah tinggi), "
                       "dan seluruh 72 blok menunjuk entitas yang masih hidup: linked_ratio 1,0, 0 blok yatim.",
                       color=AMBER, bg=colors.HexColor("#FFFBEB")))
    out.append(Spacer(1, 5))
    out.append(p("Dua angka di atas perlu dijelaskan karena mudah disalahpahami. <b>Pertama</b>, 1.163 baris "
                 "bukan berarti datanya sedikit: fakta harian memang dipangkas ke satu rentang demo, dan yang tersisa "
                 "adalah isi template demo yang sedang berjalan. <b>Kedua</b>, "
                 "ukuran 93 MB bukan tanda data besar; ia adalah sisa ruang dari baris-baris yang pernah ada "
                 "(lihat bagian 7).", BODY))
    return out


def s2():
    out = [h1("2", "Konvensi skema"), Spacer(1, 3)]
    out.append(p("Konvensi di bawah ini konsisten di seluruh 23 tabel. Bukan preferensi gaya: masing-masing "
                 "menutup satu jenis kesalahan yang mahal diperbaiki belakangan.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Konvensi", "Penerapan", "Alasan"],
        ["Kunci primer", "uuid dengan gen_random_uuid()", "Aman dibuat di klien, tidak membocorkan urutan/jumlah data"],
        ["Waktu", "timestamptz dengan default now()", "Semua perbandingan waktu memakai zona, tidak ada waktu lokal tersembunyi"],
        ["Uang dan kuantitas", "numeric(12,2) / numeric(10,2)", "Tanpa galat pembulatan biner; SDC dibulatkan HALF_UP 2 desimal"],
        ["Enum", "varchar + CHECK, bukan tipe ENUM", "Menambah nilai cukup ubah constraint, tidak perlu ALTER TYPE yang mengunci tabel"],
        ["Asal data", "origin varchar NOT NULL default 'seed'", "Memisahkan data kanonik dari data demo di seluruh tabel fakta"],
        ["Milik sesi", "demo_session_id uuid, ON DELETE SET NULL", "Baris tidak hilang saat sesi dihapus; penanda bisa dilepas"],
        ["Status", "text + CHECK vocabulary", "Nilai salah ditolak database, bukan hanya divalidasi Pydantic"],
        ["Cakupan peran", "CHECK pada users(role, location_id)", "Peran SPPG wajib punya lokasi; monitor wajib tanpa lokasi"],
    ], [30 * mm, 60 * mm, CW - 90 * mm],
                          caption="Tabel 2 - Delapan konvensi skema dan alasan pemakaiannya."))
    out.append(Spacer(1, 6))
    out.append(p("<b>Kenapa enum ditulis sebagai CHECK.</b> Tipe ENUM PostgreSQL mengunci tabel saat nilai baru "
                 "ditambahkan dan sulit di-rollback; CHECK bisa diganti dalam satu migrasi biasa. Konsekuensinya: "
                 "setiap penambahan status harus disertai migrasi constraint - dan itu justru yang diinginkan, "
                 "karena perubahan status adalah perubahan kontrak API.", BODY))
    out.append(Spacer(1, 4))
    out.append(p("<b>Kenapa asal data disimpan di tabel fakta, bukan di tabel sesi.</b> Kalau hanya sesi yang "
                 "mencatat &quot;ini data demo&quot;, baris yang lahir di luar sesi (jalur seed/refresh lama) "
                 "kehilangan jejak dan tidak bisa dibersihkan. Kolom origin membuat pembersihan bisa menyebut "
                 "kriteria yang tepat, dan itulah yang dipakai penyapuan otomatis (bagian 10).", BODY))
    return out


def s3():
    data = [
        ["Tabel", "Baris", "Kol", "Idx", "FK", "Chk", "Ukuran", "Peran"],
        ["ledger_blocks", "72", "9", "3", "0", "1", "344 kB", "Buku besar hash: height, prev_hash, payload_hash, action"],
        ["demand_records", "280", "10", "6", "3", "2", "7,8 MB", "Permintaan harian per lokasi+komoditas"],
        ["price_signals", "124", "11", "6", "4", "4", "32 MB", "Harga referensi PIHPS dan quote pemasok"],
        ["batches", "120", "21", "5", "5", "6", "728 kB", "Batch: panen, umur simpan, suhu, karantina, keamanan"],
        ["delivery_events", "70", "8", "4", "2", "1", "1,2 MB", "Peristiwa pengiriman dan status perjalanan"],
        ["menu_plans", "70", "8", "4", "2", "1", "2,4 MB", "Rencana menu harian per lokasi"],
        ["users", "7", "7", "3", "1", "2", "536 kB", "Akun: peran dan cakupan lokasi"],
        ["suppliers", "60", "13", "4", "2", "6", "216 kB", "Pemasok: koordinat, kapasitas, keandalan, sertifikasi"],
        ["road_routes", "53", "13", "3", "1", "3", "1,6 MB", "Cache geometri rute OSRM per route_key"],
        ["supply_records", "40", "10", "6", "3", "3", "36 MB", "Pasokan harian per lokasi+komoditas+sumber"],
        ["sap_mock_material_stock", "40", "9", "2", "1", "0", "88 kB", "Stok di mock SAP"],
        ["demo_sessions", "1", "8", "2", "1", "1", "80 kB", "Jendela demo: aktif, kedaluwarsa, berakhir"],
        ["disposal_events", "22", "10", "4", "3", "1", "368 kB", "Pembuangan/limbah beserta alasan"],
        ["sap_mock_purchase_orders", "16", "10", "3", "3", "2", "112 kB", "PO mock hasil eksekusi keputusan"],
        ["locations", "10", "7", "2", "0", "0", "96 kB", "SPPG: nama, koordinat, wilayah"],
        ["agent_traces", "82", "12", "2", "1", "1", "184 kB", "Jejak per stage agen"],
        ["commodities", "4", "4", "2", "0", "0", "80 kB", "Wortel, telur, ayam, beras"],
        ["decisions", "35", "22", "6", "6", "4", "336 kB", "Keputusan: tipe, status, biaya, versi, demo_case"],
        ["decision_evidence", "40", "6", "1", "1", "1", "128 kB", "Bukti per keputusan dengan jenis dan konsistensi"],
        ["alembic_version", "1", "1", "1", "0", "0", "24 kB", "Versi migrasi yang terpasang"],
        ["supplier_exclusions", "2", "16", "4", "6", "1", "112 kB", "Eksklusi pemasok (workflow administratif)"],
        ["approvals", "12", "6", "1", "2", "0", "64 kB", "Persetujuan per peran per keputusan"],
        ["batch_receipts", "2", "12", "4", "5", "1", "112 kB", "Penerimaan barang: menunggu/disetujui/ditolak"],
    ]
    out = [h1("3", "Inventaris 23 tabel"), Spacer(1, 3)]
    out.append(p("Urutan tabel mengikuti ukuran di disk, bukan abjad, supaya yang perlu perhatian muncul lebih dulu. "
                 "Kolom &quot;Idx&quot; menghitung seluruh indeks tabel (termasuk primary key dan unique), "
                 "&quot;FK&quot; jumlah foreign key keluar, &quot;Chk&quot; jumlah CHECK constraint.", BODY))
    out.append(Spacer(1, 5))
    out.append(rows_table(data, [30 * mm, 11 * mm, 9 * mm, 9 * mm, 8 * mm, 9 * mm, 15 * mm, CW - 91 * mm],
                          size=7.6, center=(1, 2, 3, 4, 5),
                          caption="Tabel 3 - Inventaris lengkap dengan angka terukur."))
    out.append(Spacer(1, 5))
    out.append(p("Tiga tabel yang paling sering dikira kosong - <i>supplier_exclusions</i>, <i>approvals</i>, " 
                 "<i>batch_receipts</i> - sekarang terisi karena template demo hidup: 2 eksklusi (1 aktif, 1 usulan), "
                 "12 approval, dan 2 penerimaan menunggu (beras 300 kg, ayam 90 kg). Ketiganya bukan tabel mati: "
                 "constraint-nya lengkap dan seluruh alurnya dijalankan aplikasi, bukan disisipkan manual.", BODY))
    return out


def s4():
    out = [h1("4", "Peta relasi"), Spacer(1, 3)]
    out.append(p("Tulang punggung skema adalah pasangan <i>locations</i> dan <i>commodities</i>. Hampir semua fakta "
                 "membawa kedua kunci itu, lalu bercabang ke alur kerja. Lima kelompok relasi yang perlu dipahami:", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Kelompok", "Relasi", "Perilaku hapus"],
        ["Referensi", "supply_records, demand_records, price_signals, menu_plans, delivery_events, disposal_events -> locations, commodities",
         "Data fakta terikat; lokasi/komoditas tidak bisa dihapus selama dirujuk"],
        ["Batch", "batches -> suppliers, locations, commodities; delivery_events -> batches",
         "Batch adalah titik temu kesegaran, keamanan, dan pengiriman"],
        ["Keputusan", "decisions -> locations (sumber & tujuan), commodities, suppliers, batches; decision_evidence, approvals, agent_traces -> decisions",
         "Satu keputusan bisa menyentuh dua lokasi sekaligus (asal dan tujuan)"],
        ["Administratif", "supplier_exclusions -> suppliers, decisions, users; batch_receipts -> batches, PO, users",
         "Eksklusi dan penerimaan tidak pernah mengubah angka pasokan secara langsung"],
        ["Jejak", "ledger_blocks tanpa foreign key; road_routes berdiri sendiri dengan route_key unik",
         "Ledger sengaja tidak memakai FK: ia harus tetap bisa dibaca walau entitasnya sudah dihapus"],
    ], [24 * mm, 92 * mm, CW - 116 * mm],
                          caption="Tabel 4 - Lima kelompok relasi dan perilaku hapusnya."))
    out.append(Spacer(1, 6))
    out.append(p("<b>Konsekuensi yang perlu disadari.</b> Karena ledger tidak memakai foreign key, integritasnya "
                 "dijaga di tingkat aplikasi (hash rantai) dan bukan di tingkat referensi. Itu pilihan sadar: "
                 "ledger harus abadi, sedangkan entitas yang dicatatnya tidak. Efek sampingnya terlihat pada "
                 "bagian 9: rantai valid, tetapi semua blok menunjuk entitas yang sudah tidak ada.", BODY))
    out.append(Spacer(1, 4))
    out.append(p("<b>Dua kunci di satu keputusan.</b> <i>decisions</i> menyimpan <i>source_location_id</i> dan "
                 "<i>target_location_id</i>; keduanya FK ke <i>locations</i>. Artinya satu baris bisa berarti "
                 "&quot;pindahkan 780 kg dari Cianjur ke Jakarta&quot; tanpa tabel perantara. Ini juga yang membuat "
                 "keputusan tipe <i>regional_balance</i> bisa diperiksa lintas lokasi tanpa join tambahan.", BODY))
    return out


def s5():
    out = [h1("5", "Integritas yang dijaga database"), Spacer(1, 3)]
    out.append(p("41 CHECK dan 9 UNIQUE bukan hiasan: masing-masing menutup satu kelas data salah yang pernah atau "
                 "mudah terjadi. Yang paling penting, dikelompokkan menurut jenis jaminan:", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Jaminan", "Constraint", "Apa yang dicegah"],
        ["Status sah", "decisions.status (7 nilai), decision_type (6), batches.safety_status (4), batches.quarantine_status (4), supplier_exclusions.status (4), batch_receipts.status (3), demo_sessions.status (3), sap PO status (3)",
         "Status karangan yang membuat UI dan laporan tidak sepakat"],
        ["Angka masuk akal", "quantity_kg > 0, supply/demand quantity >= 0, price > 0, freshness 0..1, reliability 0..1, distance/duration >= 0",
         "Kuantitas negatif dan harga nol yang merusak rata-rata biaya"],
        ["Konsistensi antar-kolom", "price_signals: pihps_reference wajib tanpa supplier, supplier_quote wajib dengan supplier",
         "Harga referensi yang diam-diam diatribusikan ke pemasok"],
        ["Rentang geografis", "latitude -90..90, longitude -180..180, latitude dan longitude harus ada berdua",
         "Titik peta setengah jadi (satu koordinat kosong)"],
        ["Cakupan peran", "users: SPPG wajib location_id, bgn_monitor wajib NULL",
         "Akun peran SPPG tanpa lokasi yang bisa membaca seluruh negeri"],
        ["Urutan waktu", "batches: dispatched_at >= harvested_at",
         "Batch yang dikirim sebelum dipanen"],
        ["Ukuran hash", "ledger_blocks: panjang payload_hash dan prev_hash = 64",
         "Blok ledger dengan hash terpotong yang membuat verifikasi selalu gagal"],
        ["Keunikan alami", "9 UNIQUE: nama lokasi/komoditas, email, (lokasi, komoditas, waktu, sumber) pasokan, (lokasi, komoditas, waktu) permintaan, (lokasi, tanggal) menu, nomor PO, tinggi blok, route_key",
         "Duplikat yang membuat penjumlahan dobel"],
    ], [24 * mm, 86 * mm, CW - 110 * mm], size=7.9,
                          caption="Tabel 5 - Delapan kelompok jaminan integritas."))
    out.append(Spacer(1, 6))
    out.append(p("<b>Hasil pemeriksaan, bukan asumsi.</b> Seluruh 52 foreign key diperiksa satu per satu dengan pola "
                 "&quot;baris anak yang tidak punya induk&quot;: hasilnya <b>0 baris yatim</b>. Pemeriksaan referensi "
                 "lain juga bersih: 60 dari 60 pemasok punya koordinat lengkap dan skor keandalan, 7 pengguna "
                 "memenuhi aturan peran-lokasi (dijaga CHECK, jadi pelanggaran tidak mungkin masuk), dan tinggi blok "
                 "ledger berurutan 1..72 tanpa celah.", BODY))
    out.append(Spacer(1, 4))
    out.append(callout("Yang tidak dijaga database: kebenaran isi. CHECK bisa memastikan suhu berbentuk angka, "
                       "tetapi tidak bisa memastikan angkanya berasal dari sensor. Karena itu verifikasi nilai "
                       "dilakukan di lapisan aplikasi (kesegaran, keamanan, SDC) dan hasilnya disimpan sebagai bukti, "
                       "bukan dianggap benar karena &quot;sudah masuk database&quot;.", color=SLATE,
                       bg=colors.HexColor("#F8FAFC")))
    return out


def s6():
    out = [h1("6", "Indeks dan perilaku performa"), Spacer(1, 3)]
    out.append(p("Ada 78 indeks pada 23 tabel. Sebarannya mengikuti pola akses aplikasi: setiap tabel fakta punya "
                 "indeks komposit (lokasi, komoditas, waktu) karena hampir semua endpoint memfilter dengan urutan itu, "
                 "dan tabel alur kerja punya indeks pada status serta kunci asing yang dipakai join.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Pola akses", "Indeks yang melayaninya", "Endpoint yang bergantung"],
        ["Deret waktu per lokasi+komoditas", "uq_supply_records_loc_com_time_source, uq_demand_records_loc_com_time, idx price (location, commodity, observed_at)",
         "GET /supply, /demand, /price, /balance"],
        ["Antrean keputusan", "idx_decisions_status, idx_decisions_origin_created_at, idx_decisions_demo_case",
         "GET /decisions, kartu rekomendasi, KPI"],
        ["Keputusan versi", "idx_decisions_supersedes_id",
         "Chain dan loop penolakan (v1 -> v2 -> v3)"],
        ["Batch dan bukti", "Index pada batches(location, commodity), decision_evidence(decision_id)",
         "Kesegaran, keamanan, dossier"],
        ["Ledger", "ledger_blocks_height_key (unique) + idx_ledger_blocks_height",
         "GET /ledger/verify (rantai dibaca berurutan)"],
        ["Rute peta", "uq_road_routes_key (unique)",
         "GET /supplier-routes, penggambaran jalur"],
    ], [34 * mm, 84 * mm, CW - 118 * mm], size=7.9,
                          caption="Tabel 6 - Enam pola akses dan indeks yang melayaninya."))
    out.append(Spacer(1, 6))
    out.append(p("<b>Indeks yang belum pernah dipakai.</b> Statistik <i>pg_stat_user_indexes</i> menunjukkan 7 indeks "
                 "dengan <i>idx_scan = 0</i>: ledger_blocks_height_key, road_routes_pkey, sap_mock_material_stock_pkey, "
                 "dua indeks demo_session_id pada tabel mock SAP dan eksklusi, idx_suppliers_location, dan "
                 "ix_supplier_exclusions_demo_session_id. Angka ini harus dibaca dengan hati-hati: statistik ikut "
                 "direset bersama siklus data, jadi &quot;belum dipakai&quot; berarti &quot;belum dipakai sejak reset&quot;, "
                 "bukan &quot;tidak berguna&quot;. Yang aman disimpulkan: indeks demo_session_id pada tabel yang barisnya "
                 "selalu nol memang belum membayar biayanya - kandidat untuk ditinjau, bukan langsung dihapus.", BODY))
    out.append(Spacer(1, 4))
    out.append(p("<b>Catatan performa yang lebih penting daripada indeks.</b> Dengan 100 baris harga, ukuran indeks "
                 "27 MB bukan masalah kecepatan hari ini, tetapi ia memperbesar setiap backup dan memperlambat "
                 "setiap restore. Perbaikan ruang (bagian 7) memberi manfaat lebih besar daripada menambah indeks.", BODY))
    return out


def s7():
    out = [h1("7", "Ruang dan pemeliharaan"), Spacer(1, 3)]
    out.append(p("Ini temuan terbesar laporan ini. Database berukuran 93 MB, tetapi data hidupnya hanya 1,4 MB. "
                 "Penyebabnya siklus hapus-semai berulang: suite tes dan sesi demo menghapus ribuan baris deret waktu, "
                 "lalu menyemainya lagi. PostgreSQL menandai ruang itu dapat dipakai ulang, tetapi tidak "
                 "mengembalikannya ke sistem berkas - kecuali dengan VACUUM FULL atau pg_repack.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Tabel", "Total", "Heap", "Indeks", "Data hidup", "Ruang kosong", "% kosong"],
        ["price_signals", "42 MB", "14 MB", "27 MB", "13 kB", "14 MB", "99,5"],
        ["supply_records", "37 MB", "8,6 MB", "28 MB", "5,0 kB", "8,6 MB", "99,5"],
        ["demand_records", "9,4 MB", "2,5 MB", "6,8 MB", "32 kB", "2,5 MB", "98,2"],
        ["menu_plans", "2,3 MB", "448 kB", "1,8 MB", "5,4 kB", "440 kB", "98,3"],
        ["delivery_events", "1,2 MB", "232 kB", "968 kB", "6,0 kB", "225 kB", "96,8"],
        ["ledger_blocks", "632 kB", "432 kB", "200 kB", "200 kB", "226 kB", "52,2"],
        ["decisions", "488 kB", "264 kB", "224 kB", "1,1 kB", "243 kB", "92,1"],
    ], [30 * mm, 18 * mm, 18 * mm, 20 * mm, 22 * mm, 24 * mm, 17 * mm], size=7.8, center=(1, 2, 3, 4, 5, 6),
                          caption="Tabel 7 - Tujuh tabel terbesar: ruang kosong mendominasi. Sumber: pgstattuple + pg_relation_size."))
    out.append(Spacer(1, 6))
    out.append(p("Autovacuum sudah bekerja - <i>last_autovacuum</i> tercatat pada 8 tabel teratas, dan baris mati "
                 "tinggal 9 pada ledger serta 27 pada decisions - tetapi autovacuum biasa hanya menandai ruang "
                 "bisa dipakai ulang, tidak menyusutkan berkas. Karena itu angka 93 MB akan bertahan walaupun "
                 "tidak ada baris baru sama sekali.", BODY))
    out.append(Spacer(1, 4))
    out.append(callout("<b>Tindakan yang disarankan (jendela sepi, tanpa aplikasi menulis):</b><br/>"
                       "VACUUM (FULL, ANALYZE) price_signals, supply_records, demand_records, menu_plans, "
                       "delivery_events, decisions;<br/>"
                       "REINDEX TABLE price_signals; REINDEX TABLE supply_records;<br/>"
                       "lalu ukur ulang dengan pg_total_relation_size. Perkiraan hasil: 93 MB -> 3-6 MB. "
                       "VACUUM FULL mengunci tabel (ACCESS EXCLUSIVE), jadi jangan dijalankan saat demo; "
                       "pg_repack melakukan hal setara tanpa kunci panjang bila ekstensi tersedia.",
                       color=RED, bg=colors.HexColor("#FEF2F2")))
    out.append(Spacer(1, 5))
    out.append(p("Catatan operasional: <i>pgstattuple</i> saya pasang untuk pengukuran ini "
                 "(CREATE EXTENSION pgstattuple). Ekstensi itu hanya dipakai untuk diagnosis dan boleh dilepas; "
                 "kalau dibiarkan, ia tidak mengubah perilaku aplikasi.", BODY))
    return out


def s8():
    out = [h1("8", "Migrasi dan evolusi skema"), Spacer(1, 3)]
    out.append(p("Skema dikelola Alembic: 27 berkas migrasi bernomor 001 sampai 027, dan tabel alembic_version "
                 "mencatat <b>027_po_decision_cascade</b> sebagai versi terpasang. Urutan nomor itu penting: ia "
                 "menjadi satu-satunya riwayat perubahan bentuk data, dan setiap migrasi baru harus dibuat dari "
                 "kepala saat ini.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Kebiasaan", "Alasan", "Cara memeriksa"],
        ["Satu migrasi per perubahan skema", "Rollback dan review jadi per langkah, bukan per rilis", "ls backend/alembic/versions"],
        ["Constraint ikut di migrasi", "CHECK yang hanya ada di model tidak akan terpasang di database", "\\d+ <tabel>"],
        ["Kolom baru nullable atau berdefault", "Menghindari gagal di tabel yang sudah berisi", "alembic upgrade head di DB klon"],
        ["Uji di database klon sebelum DB kerja", "Migrasi yang salah tidak bisa dibatalkan setelah menimpa data", "createdb klon; pg_dump | psql klon"],
        ["Head diperiksa sebelum laporan", "Dua kepala (branched heads) membuat upgrade ambigu", "select version_num from alembic_version"],
    ], [44 * mm, 78 * mm, CW - 122 * mm], size=7.9,
                          caption="Tabel 8 - Lima kebiasaan migrasi dan cara memeriksanya."))
    out.append(Spacer(1, 6))
    out.append(p("Yang belum ada dan layak ditambahkan: pemeriksaan penyimpangan otomatis (drift) antara model "
                 "SQLAlchemy dan database. Tanpa itu, kolom yang ditambahkan di model tetapi lupa dimigrasikan hanya "
                 "ketahuan saat runtime. Perintah <i>alembic check</i> (Alembic 1.9+) atau skrip pembanding "
                 "information_schema sudah cukup untuk menutup celah ini di CI.", BODY))
    return out


def s9():
    out = [h1("9", "Temuan audit"), Spacer(1, 3)]
    out.append(p("Empat pemeriksaan dijalankan langsung pada 21 Oktober 2026. Dua bersih, dua memberi pekerjaan.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Pemeriksaan", "Hasil", "Arti"],
        ["Foreign key yatim (52 FK)", "0", "Tidak ada baris anak tanpa induk; integritas referensial bersih"],
        ["Koordinat & keandalan pemasok", "60/60 lengkap", "Peta dan skor tidak akan kehilangan titik"],
        ["Rantai ledger", "valid, 72 blok, tinggi 1..72 tanpa celah, head 1641ae59...", "Tidak ada blok yang diubah atau dihapus dari rantai"],
        ["Keterkaitan ledger ke entitas", "0 dari 72 blok tertaut (linked_ratio 0,0)", "Semua blok menunjuk entitas yang sudah tidak ada"],
        ["Baris demo tersisa", "0 ber-stempel; 0 ber-origin demo", "Keadaan default kosong benar-benar tercapai"],
        ["Sesi demo", "28 baris, semuanya expired, 0 aktif", "Tidak ada sesi menggantung yang menahan data"],
    ], [46 * mm, 56 * mm, CW - 102 * mm], size=7.9,
                          caption="Tabel 9 - Hasil enam pemeriksaan integritas."))
    out.append(Spacer(1, 6))
    out.append(p("<b>Soal ledger yatim.</b> Layaknya buku besar, blok tidak boleh hilang walau entitasnya hilang; "
                 "karena itu tidak ada foreign key dari ledger ke tabel lain. Konsekuensinya, begitu data demo "
                 "dibersihkan, 72 blok tetap ada dengan <i>entity_id</i> yang tidak lagi dikenali. Verifikasi "
                 "mengembalikan <i>valid: true</i> (hash rantai benar) sekaligus peringatan "
                 "&quot;72 blok menunjuk entitas yang sudah tidak ada&quot;. Dua pilihan yang masuk akal:", BODY))
    out += bullets([
        "<b>Pertahankan dan beri label.</b> Tambahkan kolom keterangan/epoch pada blok atau tabel penanda bahwa blok "
        "itu milik siklus demo yang sudah dibersihkan, supaya laporan tidak membingungkan pembaca awam.",
        "<b>Bersihkan bersama demo.</b> Hapus blok yang entity_id-nya sudah tidak ada saat sesi ditutup, dengan "
        "catatan eksplisit di dokumen bahwa ledger demo bukan ledger produksi.",
    ])
    out.append(Spacer(1, 3))
    out.append(p("Rekomendasi saya: pilihan pertama. Menghapus blok membuat buku besar kehilangan gunanya sebagai "
                 "bukti; memberi label mempertahankan bukti sekaligus menjelaskan konteksnya.", BODY))
    out.append(Spacer(1, 4))
    out.append(p("<b>Soal stempel demo.</b> Saat sesi dimulai, penjaga flush menstempel semua baris operasional yang "
                 "belum ber-stempel - termasuk baris kanonik yang lahir di tengah sesi. Akibatnya, menutup sesi "
                 "menghapus juga baris kanonik tersebut (terukur: 78 batch dan 2 keputusan kanonik hilang, lalu "
                 "disemai ulang). Perbaikannya kecil dan terarah: batasi penghapusan ke baris ber-origin demo, "
                 "sehingga data kanonik tidak pernah ikut terbawa.", BODY))
    return out


def s10():
    out = [h1("10", "Siklus hidup data"), Spacer(1, 3)]
    out.append(p("Basis data ini memuat dua jenis data yang aturannya berbeda, dan seluruh mekanisme pembersihan "
                 "bergantung pada kemampuan membedakan keduanya.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Jenis", "Penanda", "Lahir dari", "Nasib"],
        ["Kanonik", "origin = 'seed', demo_session_id NULL", "Seeder kanonik dan suite tes", "Tidak pernah dibersihkan otomatis"],
        ["Demo bersesi", "origin = 'demo' + demo_session_id terisi", "Sesi demo yang sedang aktif", "Dihapus saat sesi berakhir/kedaluwarsa"],
        ["Demo tanpa stempel", "origin = 'demo', demo_session_id NULL", "Jalur lama /demo/seed, /demo/refresh, seeder skrip", "Disapu saat tidak ada sesi aktif (jeda 10 detik)"],
        ["Kasus skrip", "demo_case terisi", "POST /demo/seed", "Ikut aturan di atas; dipakai untuk mengenali skenario"],
        ["Abadi", "tanpa penanda, tanpa FK", "ledger_blocks", "Tidak pernah dihapus oleh siklus demo"],
    ], [26 * mm, 52 * mm, 46 * mm, CW - 124 * mm], size=7.9,
                          caption="Tabel 10 - Lima jenis baris dan nasibnya."))
    out.append(Spacer(1, 7))
    out.append(p("<b>Tiga jalur pembersihan yang ada sekarang</b>", H2))
    out += bullets([
        "Mulai sesi: semua baris operasional sesi lain dikosongkan, lalu data disemai ulang untuk tanggal acuan.",
        "Akhiri/kedaluwarsa: baris ber-stempel dihapus, status sesi menjadi expired, lalu baris demo tanpa stempel "
        "ikut disapu. Diukur: 25 keputusan demo dan 12.590 baris deret demo hilang, 490 baris kanonik bertahan.",
        "Tanpa sesi: penyapuan malas menjeda 10 detik, hanya menyentuh origin='demo', dan berhenti sendiri bila ada "
        "sesi aktif - sehingga tidak ada DELETE di setiap request.",
    ])
    out.append(Spacer(1, 3))
    out.append(p("Yang perlu diperbaiki di tingkat database: stempel massal saat sesi mulai seharusnya hanya mengenai "
                 "baris demo. Dengan begitu, &quot;akhiri sesi&quot; tidak pernah menyentuh data kanonik, dan suite "
                 "tes tidak perlu menyemai ulang setelah setiap gerbang.", BODY))
    return out


def s11():
    out = [h1("11", "Rekomendasi prioritas"), Spacer(1, 3)]
    out.append(p("Diurutkan berdasarkan risiko, bukan kemudahan. Tiga yang pertama bisa dikerjakan tanpa mengubah kode.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["P", "Tindakan", "Alasan", "Risiko bila ditunda"],
        ["1", "VACUUM (FULL, ANALYZE) pada 6 tabel ber-bloat + REINDEX",
         "93 MB untuk 1,4 MB data; backup dan restore ikut membengkak", "Berkas terus tumbuh setiap siklus demo"],
        ["1", "Kebijakan blok ledger yatim: beri label atau bersihkan bersama demo",
         "Peringatan &quot;72 blok menunjuk entitas hilang&quot; membingungkan auditor", "Bukti terlihat rusak padahal rantainya valid"],
        ["2", "Batasi stempel sesi ke origin='demo'",
         "Menutup sesi saat ini bisa menghapus data kanonik", "Data kerja hilang setiap sesi berakhir"],
        ["2", "Audit indeks demo_session_id pada tabel yang selalu kosong",
         "Biaya tulis tanpa manfaat; statistik menunjukkan 0 pemakaian", "Utang kecil yang menumpuk"],
        ["3", "Pemeriksaan drift skema (alembic check) di CI",
         "Kolom model yang lupa dimigrasikan hanya ketahuan saat runtime", "Basis data dan kode berbeda diam-diam"],
        ["3", "Kebijakan backup + retensi untuk DB demo",
         "Satu pg_dump sebelum demo cukup untuk rollback", "Demo gagal tanpa jalan pulang"],
    ], [8 * mm, 62 * mm, 62 * mm, CW - 132 * mm], size=7.9, center=(0,),
                          caption="Tabel 11 - Enam rekomendasi berurutan."))
    out.append(Spacer(1, 6))
    out.append(callout("Batasan laporan ini: semua angka berasal dari satu instance demo di mesin pengembangan, "
                       "bukan dari lingkungan produksi. Tidak ada pengukuran beban konkuren, tidak ada analisis "
                       "rencana query (EXPLAIN) pada volume besar, dan tidak ada pengujian restore. Untuk klaim "
                       "performa, tiga hal itu yang harus diukur lebih dulu.", color=SLATE,
                       bg=colors.HexColor("#F8FAFC")))
    return out


def s12():
    out = [h1("12", "Lampiran"), Spacer(1, 3)]
    out.append(p("<b>Kolom tabel kunci</b>", H2))
    out.append(rows_table([
        ["Tabel", "Kolom penting"],
        ["decisions (22)", "id, decision_type, status, proposed_by, verified_by, verifier_note, source_location_id, "
                           "target_location_id, commodity_id, quantity_kg, safe_delivered_cost, cost_breakdown, "
                           "expires_at, created_at, rejection_reason, iteration, supersedes_id, demo_case, origin, "
                           "generated_at, supplier_id, demo_session_id"],
        ["batches (21)", "id, commodity_id, location_id, supplier_id, quantity_kg, harvested_at, temperature_log, "
                         "certification_status, freshness_score, safety_status, usable_until, created_at, origin, "
                         "generated_at, dispatched_at, quarantine_status, quarantine_reason, quarantined_at, "
                         "quarantine_updated_at, quarantine_actor_id, demo_session_id"],
        ["ledger_blocks (9)", "id, height, prev_hash, payload_hash, action, entity_id, actor_id, payload, created_at"],
        ["demo_sessions (8)", "id, status, started_at, expires_at, anchor_now, ended_at, template_version, created_by"],
        ["road_routes (13)", "id, route_key, profile, origin/destination lat-lon, distance_m, duration_s, geometry, "
                             "source, fetched_at, demo_session_id"],
    ], [30 * mm, CW - 30 * mm], size=7.8))
    out.append(Spacer(1, 7))
    out.append(p("<b>Query verifikasi yang dipakai di laporan ini</b>", H2))
    out.append(rows_table([
        ["Tujuan", "Query"],
        ["Jumlah baris per tabel", "select relname, n_live_tup from pg_stat_user_tables order by 2 desc;"],
        ["Ukuran heap/indeks", "select relname, pg_size_pretty(pg_relation_size(oid)), pg_size_pretty(pg_indexes_size(oid)) from pg_class where relkind='r';"],
        ["Ruang kosong", "select relname, (pgstattuple(oid)).free_percent from pg_class where relkind='r';"],
        ["FK yatim", "pola: select count(*) from anak a where a.kolom is not null and not exists (select 1 from induk p where p.id = a.kolom);"],
        ["Constraint", "select conrelid::regclass, conname, pg_get_constraintdef(oid) from pg_constraint where connamespace='public'::regnamespace;"],
        ["Versi migrasi", "select version_num from alembic_version;"],
        ["Komposisi asal data", "select origin, count(*) from batches group by 1;"],
        ["Celah tinggi ledger", "select max(height)-min(height)+1-count(*) from ledger_blocks;"],
    ], [40 * mm, CW - 40 * mm], size=7.6))
    out.append(Spacer(1, 6))
    out.append(p("Laporan pendamping: <i>Laporan-MealChain-Guardian-2026-10-21-r2.pdf</i> (alur dan kasus sistem). "
                 "Keduanya dibuat dari sumber yang sama - kode dan pengukuran langsung - sehingga angka di "
                 "keduanya bisa saling diperiksa.", CAP))
    return out


def build(path):
    doc = BaseDocTemplate(path, pagesize=A4, leftMargin=M_L, rightMargin=M_R, topMargin=M_T, bottomMargin=M_B,
                          title="Basis Data MealChain Guardian - Skema, Integritas, dan Temuan Audit",
                          author="MealChain Guardian", subject="Laporan basis data")
    frame = Frame(M_L, M_B, CW, PAGE_H - M_T - M_B, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="cover", frames=[frame]),
                          PageTemplate(id="body", frames=[frame], onPage=footer)])
    story = cover() + daftar_isi()
    fns = (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12)
    for i, fn in enumerate(fns):
        blok = fn()
        if i:
            story += [Spacer(1, 9), HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=2, spaceAfter=6)]
            story.append(KeepTogether(blok[:2]))
            story += blok[2:]
        else:
            story += blok
    doc.build(story)
    return path


if __name__ == "__main__":
    import sys
    print(build(sys.argv[1] if len(sys.argv) > 1 else "laporan-db.pdf"))
