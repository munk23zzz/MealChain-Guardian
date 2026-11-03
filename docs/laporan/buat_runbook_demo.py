# -*- coding: utf-8 -*-
"""Runbook demo juri MealChain Guardian -> PDF (reportlab platypus).

Gaya visual sengaja sama dengan dua laporan sebelumnya (docs/laporan/buat_laporan.py)
supaya tiga dokumen terbaca sebagai satu keluarga. Isi angka diambil dari database
yang berjalan 21 Oktober 2026 dan dari aksi yang benar-benar dieksekusi saat uji.

Jalankan:  pdfenv/Scripts/python.exe buat_runbook_demo.py <keluaran.pdf>
"""
import os
import sys

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from buat_laporan import (  # noqa: E402  (gaya bersama)
    AMBER, BLUE, BODY, BORDER, CAP, CELL, CELLB, GREEN, INK,
    LEAD, LIGHT, M_B, M_L, M_R, M_T, MUTED, NAVY, PAGE_H, PAGE_W, SLATE,
    callout, h1, p, rows_table,
)

KUNING = colors.HexColor("#B45309")
KUNING_BG = colors.HexColor("#FFFBEB")
MERAH_BG = colors.HexColor("#FEF2F2")
HIJAU_BG = colors.HexColor("#F0FDF4")
UNGU_BG = colors.HexColor("#F5F3FF")

BIG = ParagraphStyle("big", parent=BODY, fontName="Helvetica-Bold", fontSize=17, leading=19,
                     textColor=NAVY, alignment=1)
BIGLBL = ParagraphStyle("biglbl", parent=BODY, fontSize=7.6, leading=9.6, textColor=MUTED,
                        alignment=1)
# Warna teks TERANG: paragraf membawa warnanya sendiri, jadi TEXTCOLOR pada
# TableStyle tidak berlaku untuk isi blok kode berlatar navy.
MONO = ParagraphStyle("mono", parent=BODY, fontName="Courier", fontSize=8, leading=11,
                      textColor=colors.HexColor("#E2E8F0"))
STEP = ParagraphStyle("step", parent=BODY, fontSize=9.6, leading=14, textColor=INK,
                      leftIndent=13, bulletIndent=2, spaceAfter=3)
NOTE = ParagraphStyle("note", parent=CELL, fontSize=8.4, leading=11.6, textColor=INK)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(M_L, M_B - 6 * mm, PAGE_W - M_R, M_B - 6 * mm)
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(M_L, M_B - 10.5 * mm, "MealChain Guardian - runbook demo juri (21 Oktober 2026)")
    canvas.drawRightString(PAGE_W - M_R, M_B - 10.5 * mm, "%d" % doc.page)
    canvas.restoreState()


def angka_band(items):
    """Enam angka besar: dibaca juri dari jauh, jadi tipografinya tebal dan lapang."""
    sel = [[Paragraph(v, BIG) for v, _ in items], [Paragraph(label, BIGLBL) for _, label in items]]
    w = (PAGE_W - M_L - M_R) / len(items)
    t = Table(sel, colWidths=[w] * len(items), hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    return t


def langkah(nomor, teks):
    return Paragraph(f"<b>{nomor}</b>&nbsp;&nbsp;{teks}", STEP, bulletText="")


def peringatan(teks):
    return callout(teks, color=AMBER, bg=KUNING_BG)


def sukses(teks):
    return callout(teks, color=GREEN, bg=HIJAU_BG)


def kode(baris):
    # Satu sel berisi semua baris dipisah <br/>: tabel satu-baris-dengan-N-sel
    # (colWidths hanya satu nilai) memotong semua baris kecuali yang pertama.
    isi = "<br/>".join(b.replace(" ", "&nbsp;") for b in baris)
    t = Table([[Paragraph(isi, MONO)]], colWidths=[PAGE_W - M_L - M_R], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0B1220")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
    ]))
    return t


# ------------------------------------------------------------------ COVER

def cover():
    out = [NextPageTemplate("cover")]
    band = Table([[""]], colWidths=[PAGE_W - M_L - M_R], rowHeights=[6 * mm])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE)]))
    out += [Spacer(1, 24 * mm), band, Spacer(1, 9 * mm)]
    out.append(Paragraph("MealChain Guardian", ParagraphStyle(
        "cover", parent=BODY, fontName="Helvetica-Bold", fontSize=30, leading=34, textColor=NAVY)))
    out.append(Spacer(1, 2 * mm))
    out.append(Paragraph("Runbook demo untuk juri", ParagraphStyle(
        "cover2", parent=BODY, fontSize=17, leading=21, textColor=SLATE)))
    out.append(Spacer(1, 6 * mm))
    out.append(Paragraph(
        "Sebelas menit, enam babak, tiga bukti bahwa angka benar-benar bergerak. Setiap angka di dokumen ini "
        "dibaca dari basis data yang berjalan pada 21 Oktober 2026 dan sudah diuji dengan aksi nyata: "
        "persetujuan, eksekusi, penerimaan barang, dan karantina.", 
        ParagraphStyle("cover3", parent=BODY, fontSize=10.4, leading=15.6,
                       textColor=colors.HexColor("#334155"))))
    out.append(Spacer(1, 10 * mm))

    meta = [
        ["Durasi", "11 menit isi + 3 menit tanya jawab (bisa dipangkas ke 7 menit: babak 0, 1, 6)"],
        ["Prasyarat", "Sesi demo aktif. Tombol Siapkan data demo butuh +-68 detik; jalankan sebelum juri masuk"],
        ["Sumber angka", "PostgreSQL 16.15, database mealchain; KPI 30 hari terakhir; ledger SHA-256"],
        ["Status", "Angka dan delta di sini hasil eksekusi nyata, bukan perkiraan; risiko ditulis di bagian 6"],
    ]
    t = Table([[Paragraph(a, CELLB), Paragraph(b, CELL)] for a, b in meta],
              colWidths=[30 * mm, PAGE_W - M_L - M_R - 30 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    out += [t, Spacer(1, 8 * mm)]
    out.append(Paragraph("Dokumen kerja - cetak dua sisi, halaman 2 dibawa ke panggung.", CAP))
    out.append(NextPageTemplate("body"))
    out.append(PageBreak())
    return out


# ------------------------------------------------------------------ 1. CONTEKAN

def contekan():
    out = [h1("1", "Lembar contekan (bawa halaman ini ke panggung)"), Spacer(1, 4)]
    out.append(angka_band([
        ("120", "batch aktif"),
        ("31", "keputusan"),
        ("5", "notifikasi"),
        ("16", "pesanan SAP"),
        ("72", "blok ledger"),
        ("7/7", "KPI berangka"),
    ]))
    out.append(Spacer(1, 6))
    out.append(p("Semua angka di atas adalah keadaan awal setelah <b>Siapkan data demo</b>. Kalau salah satu "
                 "berbeda, jangan mulai: jalankan reset (bagian 5) lebih dulu.", BODY))
    out.append(Spacer(1, 8))
    out.append(rows_table([
        ["#", "Babak", "Menit", "Tab", "Angka yang bergerak"],
        ["0", "Pembuka", "1,5", "Overview", "-780 kg; pasokan 300/1.080 kg (28%); notifikasi 5"],
        ["1", "Agent mengusulkan, manusia memutuskan", "3", "Recommendations, Decision &amp; Evidence", "status pending -&gt; executed; PO 16 -&gt; 17; ledger 72 -&gt; 75"],
        ["2", "Keamanan pangan", "2", "Keamanan Pangan", "karantina 540 kg dilepas; batch gagal 800 kg tetap diblokir"],
        ["3", "Penerimaan barang", "1,5", "Keamanan Pangan", "ayam 90 kg disetujui; pasokan Jakarta 200 -&gt; 290 kg; selisih -15 -&gt; +75 kg"],
        ["4", "Pemasok berisiko", "1,5", "Pemasok", "1 eksklusi aktif, 1 usulan; status proposed -&gt; active"],
        ["5", "Surplus lintas lokasi", "1,5", "Surplus &amp; Limbah", "Cianjur -&gt; Bogor 208 kg; biaya angkut 3,4%"],
        ["6", "Bukti &amp; KPI", "1", "Agent Log, KPI, Ledger", "82 trace; 72 blok; linked_ratio 1,0; 7 metrik"],
    ], [10 * mm, 44 * mm, 13 * mm, 40 * mm, PAGE_W - M_L - M_R - 107 * mm]))
    out.append(p("Tabel 1 - Peta babak. Kolom terakhir adalah satu-satunya yang perlu diingat di panggung.", CAP))
    out.append(Spacer(1, 8))
    out.append(p("<b>Kalimat pembuka yang mengikat seluruh demo:</b> &quot;Angka ini berubah selama demo. "
                 "Saya akan buktikan tiga kali: saat keputusan dieksekusi, saat barang diterima, dan saat "
                 "bukti diaudit.&quot;", LEAD))
    out.append(Spacer(1, 6))
    out.append(sukses("Tiga bukti bergerak yang sudah diukur ulang: (1) PO 16 -&gt; 17 dan ledger 72 -&gt; 75 "
                      "setelah approve dua peran + eksekusi; (2) supply_records +1 dan pasokan ayam Jakarta "
                      "290 kg setelah penerimaan 90 kg disetujui; (3) linked_ratio tetap 1,0 dengan 0 blok "
                      "yatim setelah semua aksi."))
    out.append(Spacer(1, 9))
    out.append(rows_table([
        ["Kalau juri bertanya", "Jawaban singkat yang jujur"],
        ["&quot;Apakah angkanya dibuat-buat?&quot;",
         "Tidak. Angka dibaca dari PostgreSQL; tiga delta di atas diukur setelah aksi nyata, dan query pembuktiannya ada di bagian 10."],
        ["&quot;Apakah agent bisa eksekusi sendiri?&quot;",
         "Tidak. Verifier mengaudit, matriks approval meminta dua peran berbeda, eksekusi tetap klik manusia."],
        ["&quot;Kalau data kurang?&quot;",
         "Metrik berstate no_data, bukan angka nol. Tujuh KPI di sini semuanya available karena datanya ada."],
        ["&quot;Bagaimana kalau salah?&quot;",
         "Setiap penolakan dan pelepasan karantina wajib beralasan, dan alasannya masuk evidence ledger."],
    ], [46 * mm, PAGE_W - M_L - M_R - 46 * mm]))
    out.append(p("Tabel 2 - Tanya jawab yang paling sering muncul; sisanya boleh dijawab dari tab yang sedang terbuka.", CAP))
    out.append(Spacer(1, 10))
    out.append(p("Ruang catatan:"))
    out.append(Spacer(1, 14 * mm))
    out.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    out.append(Spacer(1, 14 * mm))
    out.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    out.append(Spacer(1, 14 * mm))
    out.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    return out


# ------------------------------------------------------------------ 2. PRA-PERANGKAT

def pra():
    out = [h1("2", "Lima menit sebelum juri masuk"), Spacer(1, 4)]
    out.append(p("Urutannya penting: data dulu, login belakangan. Membalik urutan membuat layar sempat "
                 "menampilkan keadaan kosong dan itu terlihat seperti sistem rusak.", BODY))
    out += [Spacer(1, 6)]
    out += [langkah("1.", "Pastikan frontend (port 3010) dan backend (port 8000) hidup: "
                          "<font face='Courier'>curl -s localhost:8000/health</font> harus "
                          "<font face='Courier'>healthy</font>.")]
    out += [langkah("2.", "Demo Control -&gt; <b>Siapkan data demo</b>. Tunggu +-70 detik (menyemai 120 batch "
                          "dan mengambil 53 rute OSRM). Jangan klik dua kali.")]
    out += [langkah("3.", "Cek enam angka di halaman 1. Kalau berbeda, reset dulu (bagian 5).")]
    out += [langkah("4.", "Buka tab Overview sekali, pilih komoditas <b>wortel</b>, pastikan garis kiriman dan "
                          "ikon truk muncul di peta. Kembali ke Overview.")]
    out += [langkah("5.", "Siapkan dua browser profil: Kepala SPPG (layar utama) dan Ahli Gizi (layar kedua) - "
                          "babak 1 butuh dua peran.")]
    out.append(Spacer(1, 8))
    out.append(rows_table([
        ["Akun demo", "Peran", "Dipakai untuk"],
        ["sppg.head@demo.local", "Kepala SPPG Jakarta", "Semua persetujuan pertama, eksekusi, penerimaan, karantina"],
        ["sppg.nutritionist@demo.local", "Ahli Gizi Jakarta", "Persetujuan kedua (matriks dua peran)"],
        ["bgn.monitor@demo.local", "BGN Monitor", "Tampilan pengawas: read-only, tanpa tombol aksi"],
    ], [58 * mm, 42 * mm, PAGE_W - M_L - M_R - 100 * mm]))
    out.append(p("Tabel 3 - Akun demo. Password ada di Demo Control pada mesin demo, tidak dicetak di sini.", CAP))
    out.append(Spacer(1, 8))
    out.append(peringatan("Jangan membuat usulan eksklusi <b>baru</b> di panggung. Verifier untuk keputusan yang "
                          "lahir saat runtime bisa mengembalikan <font face='Courier'>unavailable</font> bila "
                          "runtime agent tidak terjangkau, dan persetujuan akan ditolak (409). Pakai usulan yang "
                          "sudah ada - semuanya sudah <font face='Courier'>consistent</font>."))
    return out


# ------------------------------------------------------------------ 3. BABAK

def babak_0():
    out = [h1("3", "Babak 0 - Pembuka: angka pagi ini (1,5 menit)"), Spacer(1, 4)]
    out.append(p("<b>Tab:</b> Overview. <b>Tujuan:</b> juri melihat sistem yang sudah berisi, bukan formulir kosong.", BODY))
    out.append(Spacer(1, 5))
    out += [langkah("1.", "Login Kepala SPPG. Biarkan 5 detik sampai label <i>Live Sync (5s)</i> berhenti berputar.")]
    out += [langkah("2.", "Tunjuk kartu <b>Selisih pasokan Jakarta</b>: <b>-780 kg</b>, kurang 72% dari kebutuhan, "
                          "0 lokasi surplus, 1 shortage.")]
    out += [langkah("3.", "Tunjuk <b>Pasokan terpantau</b>: 300 kg dari 1.080 kg kebutuhan jaringan (28%), "
                          "bertanggal 21 Oktober 2026.")]
    out += [langkah("4.", "Tunjuk notifikasi <b>5</b> dan daftar <b>Perlu keputusan</b> (2 menunggu persetujuan, "
                          "1 ditandai verifier, 2 menunggu).")]
    out += [langkah("5.", "Pilih komoditas <b>wortel</b> di peta: hanya wortel yang punya kiriman berjalan hari ini, "
                          "jadi hanya di situ garis + ikon truk muncul. Pemasok aktif berdenyut violet #8B5CF6.")]
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Yang ditunjuk", "Nilai", "Cara membacanya"],
        ["Selisih pasokan Jakarta", "-780 kg", "Kekurangan 72% dari kebutuhan; 1 lokasi shortage"],
        ["Pasokan terpantau", "300 / 1.080 kg", "Hanya 28% kebutuhan jaringan yang terukur"],
        ["Notifikasi", "5", "4 menunggu tindakan + 1 ditandai verifier"],
        ["Kecukupan pasokan", "2/4 komoditas", "Beras -3.010 kg; ayam -156 kg; telur +150 kg; wortel +702 kg"],
    ], [46 * mm, 30 * mm, PAGE_W - M_L - M_R - 76 * mm]))
    out.append(p("Tabel 4 - Angka pembuka, dibaca langsung dari layar pada 21 Oktober 2026 03.07 WIB.", CAP))
    out.append(Spacer(1, 6))
    out.append(p("<b>Kalimat:</b> &quot;Ini bukan mockup. Setiap angka di layar ini punya baris di database, "
                 "dan tiga di antaranya akan berubah selama sebelas menit ke depan.&quot;", BODY))
    return out


def babak_1():
    out = [h1("4", "Babak 1 - Agent mengusulkan, manusia memutuskan (3 menit)"), Spacer(1, 4)]
    out.append(p("<b>Tab:</b> Recommendations -&gt; Decision &amp; Evidence. <b>Tujuan:</b> memperlihatkan batas "
                 "otonomi: agent menyusun, verifier mengaudit, dua manusia menyetujui, baru SAP menerima pesanan.", BODY))
    out.append(Spacer(1, 5))
    out += [langkah("1.", "Recommendations: buka kartu <b>Alokasi regional</b> (regional_balance) untuk Jakarta.")]
    out += [langkah("2.", "Masuk <b>Decision &amp; Evidence</b>. Tunjuk verdict verifier: <b>consistent</b>, "
                          "beserta bukti yang dipakai (pesanan SAP + inspeksi manusia).")]
    out += [langkah("3.", "Sebagai Kepala SPPG: <b>Setujui</b> (komentar: &quot;Bukti cocok&quot;).")]
    out += [langkah("4.", "Pindah ke layar Ahli Gizi: <b>Setujui</b> keputusan yang sama. Matriks dua peran menolak "
                          "satu persetujuan saja.")]
    out += [langkah("5.", "Kembali ke Kepala SPPG: <b>Eksekusi</b>. Pesanan SAP lahir, blok ledger bertambah.")]
    out.append(Spacer(1, 7))
    out.append(rows_table([
        ["Momen", "Sebelum", "Sesudah", "Bukti"],
        ["Status keputusan", "pending_approval", "executed", "Decision &amp; Evidence"],
        ["Pesanan SAP", "16", "17", "SAP -&gt; Pesanan (14 confirmed, 2 submitted)"],
        ["Blok ledger", "72", "75", "approve kepala + approve gizi + eksekusi"],
        ["Trace agent", "82", "+1 per aksi", "Agent Log"],
        ["Decision Time (KPI)", "20 menit", "berubah sesuai waktu aksi", "KPI &amp; Kualitas Agen"],
    ], [38 * mm, 30 * mm, 34 * mm, PAGE_W - M_L - M_R - 102 * mm]))
    out.append(p("Tabel 5 - Delta babak 1. Angka PO dan ledger diukur setelah eksekusi nyata, bukan simulasi.", CAP))
    out.append(Spacer(1, 7))
    out.append(p("<b>Kalimat:</b> &quot;Agent tidak boleh mengeksekusi sendiri. Dua peran berbeda harus setuju, dan "
                 "setiap persetujuan meninggalkan blok hash yang tidak bisa diubah belakangan.&quot;", BODY))
    out.append(Spacer(1, 6))
    out.append(peringatan("Cadangan: kalau tombol eksekusi menolak karena bukti kurang, jangan berdebat dengan "
                          "sistem di panggung. Pindah ke kartu regional_balance Bandung atau Surabaya - keduanya "
                          "juga sudah <font face='Courier'>consistent</font> dan siap dieksekusi."))
    return out


def babak_2():
    out = [h1("5", "Babak 2 - Keamanan pangan: blokir yang nyata (2 menit)"), Spacer(1, 4)]
    out.append(p("<b>Tab:</b> Keamanan Pangan. <b>Tujuan:</b> memperlihatkan bahwa angka kepatuhan bukan hiasan - "
                 "batch yang gagal benar-benar keluar dari kandidat alokasi.", BODY))
    out.append(Spacer(1, 5))
    out += [langkah("1.", "Tunjuk tile <b>batch gagal uji</b>: beras Jakarta <b>800 kg</b>, suhu puncak "
                          "<b>9,5 C</b>, 8 titik log, durasi di atas ambang 30 menit. Status: diblokir dari alokasi.")]
    out += [langkah("2.", "Tunjuk <b>karantina</b>: beras Jakarta <b>540 kg</b>, alasan &quot;kemasan penyok pada "
                          "3 dus; menunggu pemeriksaan gudang&quot;.")]
    out += [langkah("3.", "Klik <b>Lepas</b>, isi alasan (&quot;Sudah diperiksa gudang, kemasan diganti&quot;), kirim.")]
    out.append(Spacer(1, 7))
    out.append(rows_table([
        ["Momen", "Sebelum", "Sesudah"],
        ["Status batch", "quarantined", "released (tidak boleh dialokasikan -&gt; kandidat lagi)"],
        ["Batch karantina", "1", "0"],
        ["Kg tertahan", "540 kg", "0 kg"],
        ["Batch gagal uji", "1 (800 kg)", "tetap 1 - kegagalan tidak bisa dilepas manual"],
    ], [40 * mm, 34 * mm, PAGE_W - M_L - M_R - 74 * mm]))
    out.append(p("Tabel 6 - Delta babak 2. Pelepasan karantina butuh alasan tertulis dan tercatat di evidence.", CAP))
    out.append(Spacer(1, 7))
    out.append(p("<b>Kalimat:</b> &quot;Karantina bukan label kosmetik: selama batch ditahan, ia tidak pernah muncul "
                 "sebagai kandidat alokasi. Kegagalan uji tidak bisa dilepas manual - hanya bisa dinyatakan gagal "
                 "atau diverifikasi ulang dengan log baru.&quot;", BODY))
    return out


def babak_3():
    out = [h1("6", "Babak 3 - Penerimaan barang menggerakkan pasokan (1,5 menit)"), Spacer(1, 4)]
    out.append(p("<b>Tab:</b> Keamanan Pangan (panel penerimaan) -&gt; Overview. <b>Tujuan:</b> membuktikan angka "
                 "pasokan berasal dari stok yang benar-benar masuk, bukan dari animasi.", BODY))
    out.append(Spacer(1, 5))
    out += [langkah("1.", "Panel <b>Penerimaan menunggu</b> berisi 2 baris: ayam 90 kg dan beras 300 kg (Jakarta).")]
    out += [langkah("2.", "Setujui penerimaan <b>ayam 90 kg</b>.")]
    out += [langkah("3.", "Overview -&gt; komoditas <b>ayam</b> -&gt; Jakarta. Bandingkan sebelum/sesudah.")]
    out += [langkah("4.", "Sebutkan bahwa penerimaan beras 300 kg <b>sengaja dibiarkan</b> untuk tanya jawab.")]
    out.append(Spacer(1, 7))
    out.append(rows_table([
        ["Momen", "Sebelum", "Sesudah"],
        ["Status penerimaan", "menunggu", "disetujui"],
        ["Baris supply_records", "-", "+1 (90 kg ayam)"],
        ["Pasokan ayam Jakarta", "200 kg", "290 kg"],
        ["Selisih ayam Jakarta", "-15 kg (shortage)", "+75 kg (surplus)"],
        ["Status tile Jakarta", "Shortage", "Surplus"],
    ], [44 * mm, 40 * mm, PAGE_W - M_L - M_R - 84 * mm]))
    out.append(p("Tabel 7 - Delta babak 3, diukur dari /balance/map setelah persetujuan.", CAP))
    out.append(Spacer(1, 7))
    out.append(p("<b>Kalimat:</b> &quot;Persetujuan ini menulis satu baris stok. Overview membaca stok terbaru, jadi "
                 "angka pasokan berubah karena datanya berubah - bukan karena grafiknya di-refresh.&quot;", BODY))
    out.append(Spacer(1, 6))
    out.append(peringatan("Kalau juri meminta bukti tambahan: klik penerimaan beras 300 kg dan tolak dengan alasan "
                          "&quot;beras tidak sesuai spesifikasi&quot;. Stok tidak bertambah, dan angka tetap konsisten "
                          "- sistem menolak menambah pasokan dari barang yang ditolak."))
    return out


def babak_4():
    out = [h1("7", "Babak 4 - Pemasok berisiko dan jalur pemulihan (1,5 menit)"), Spacer(1, 4)]
    out.append(p("<b>Tab:</b> Pemasok. <b>Tujuan:</b> memperlihatkan tata kelola mitra: eksklusi ber-scope, "
                 "beralasan, dan bisa dicabut.", BODY))
    out.append(Spacer(1, 5))
    out += [langkah("1.", "Tunjuk <b>1 aktif</b>: CV Ambarawa Telur Utama - dua kiriman telur di atas ambang suhu, "
                          "sertifikasi HACCP belum diperbarui.")]
    out += [langkah("2.", "Tunjuk <b>1 usulan</b>: CV Ayam Kampung Cugenang - kemasan retak, menunggu klarifikasi. "
                          "Status <font face='Courier'>proposed</font>.")]
    out += [langkah("3.", "Setujui usulan itu lewat alur yang sama dengan babak 1 (verifier sudah "
                          "<font face='Courier'>consistent</font>, lalu approve dua peran, lalu eksekusi): status "
                          "menjadi <font face='Courier'>active</font>, dan pemasok berhenti muncul di kandidat "
                          "pengadaan lokasi tersebut.")]
    out += [langkah("4.", "Sebutkan tombol <b>Pulihkan</b>: eksklusi bisa dicabut dengan alasan, dan pemasok kembali "
                          "ke kandidat. Ini yang membedakan tata kelola dari daftar hitam permanen.")]
    out.append(Spacer(1, 7))
    out.append(rows_table([
        ["Keadaan", "Jumlah", "Arti"],
        ["Eksklusi aktif", "1", "CV Ambarawa Telur Utama (telur, Jakarta)"],
        ["Eksklusi usulan", "1", "CV Ayam Kampung Cugenang (ayam, Jakarta)"],
        ["Pemasok terdaftar", "60", "35 hygiene, 17 HACCP, 8 tanpa sertifikat"],
        ["Setelah eksekusi", "2 aktif", "Pemasok yang dieksklusi tidak masuk kandidat pengadaan"],
    ], [40 * mm, 24 * mm, PAGE_W - M_L - M_R - 64 * mm]))
    out.append(p("Tabel 8 - Keadaan tab Pemasok pada data demo.", CAP))
    out.append(Spacer(1, 6))
    out.append(peringatan("Jangan membuat usulan baru di panggung (lihat bagian 2). Verifier untuk usulan yang lahir "
                          "saat runtime belum punya verdict, dan persetujuan akan ditolak."))
    return out


def babak_5():
    out = [h1("8", "Babak 5 - Surplus lintas lokasi: keputusan berbasis biaya (1,5 menit)"), Spacer(1, 4)]
    out.append(p("<b>Tab:</b> Surplus &amp; Limbah -&gt; komoditas <b>wortel</b>. <b>Tujuan:</b> memperlihatkan bahwa "
                 "alokasi dipilih karena biaya dan ketersediaan, bukan karena urutan abjad.", BODY))
    out.append(Spacer(1, 5))
    out.append(rows_table([
        ["Metrik", "Nilai", "Arti"],
        ["Lokasi surplus", "2 (667 kg)", "Stok melebihi kebutuhan + ambang lot minimum 150 kg"],
        ["Lokasi kekurangan", "8 (286 kg)", "Kekurangan terukur, bukan proyeksi"],
        ["Dapat dialokasikan", "208 kg", "Batas alokasi setelah aturan lot"],
        ["Pasangan teratas", "Cianjur -&gt; Bogor", "208 kg, 44 km"],
        ["Harga acuan", "Rp2.150/kg", "Nilai Rp4.472.000"],
        ["Biaya angkut", "Rp152.746", "3,4% dari nilai - di bawah ambang 10%"],
    ], [40 * mm, 34 * mm, PAGE_W - M_L - M_R - 74 * mm]))
    out.append(p("Tabel 9 - Alokasi wortel, dibaca dari /surplus/allocations?commodity=wortel.", CAP))
    out.append(Spacer(1, 7))
    out.append(p("<b>Kalimat:</b> &quot;Sistem memilih pasangan ini karena biaya angkutnya 3,4% dan stoknya ada hari "
                 "ini. Kalau biayanya di atas ambang, ia akan menolak mengalokasikan dan menyarankan beli lokal - "
                 "itu keputusan yang bisa dipertanggungjawabkan ke auditor.&quot;", BODY))
    out.append(Spacer(1, 6))
    out.append(p("Komoditas lain juga punya angka, tetapi hanya wortel yang punya kiriman <i>di_jalan</i> hari ini. "
                 "Jangan menjanjikan truk di komoditas yang tidak punya perjalanan aktif.", CAP))
    return out


def babak_6():
    out = [h1("9", "Babak 6 - Bukti dan KPI: penutup (1 menit)"), Spacer(1, 4)]
    out.append(p("<b>Tab:</b> Agent Log, KPI &amp; Kualitas Agen, Ledger. <b>Tujuan:</b> menutup dengan bukti, bukan "
                 "dengan janji.", BODY))
    out.append(Spacer(1, 5))
    out += [langkah("1.", "Agent Log: 82 trace; filter per keputusan untuk menunjukkan rantai penalaran.")]
    out += [langkah("2.", "KPI &amp; Kualitas Agen: 7 metrik berangka - kontinuitas 100%, food loss 1,70%, "
                          "imbalance 100%, Safe Delivered Cost Rp18.062.477,91, deviasi harga 2,66%, decision "
                          "time 20 menit, kelengkapan bukti 100%.")]
    out += [langkah("3.", "Ledger: <font face='Courier'>valid: true</font>, 72 blok (75 setelah babak 1), "
                          "<font face='Courier'>linked_ratio 1,0</font>, 0 blok yatim. Tunjuk head hash.")]
    out.append(Spacer(1, 7))
    out.append(rows_table([
        ["Metrik KPI (30 hari)", "Nilai"],
        ["Meal Continuity Rate", "100,00"],
        ["Avoidable Food Loss", "1,70%"],
        ["Regional Imbalance Resolution", "100,00"],
        ["Safe Delivered Cost", "Rp18.062.477,91"],
        ["Procurement Price Deviation", "2,66%"],
        ["Decision Time", "20,00 menit"],
        ["Evidence Completeness", "100,00"],
    ], [70 * mm, PAGE_W - M_L - M_R - 70 * mm]))
    out.append(p("Tabel 10 - Tujuh metrik KPI, semuanya state available (tidak ada angka palsu untuk metrik tanpa data).", CAP))
    out.append(Spacer(1, 6))
    out.append(sukses("Penutup: &quot;Yang kami bangun bukan dashboard. Ini jejak keputusan: angka yang punya asal, "
                      "persetujuan yang punya nama, dan bukti yang punya hash.&quot;"))
    return out


# ------------------------------------------------------------------ 4. RESET

def reset():
    out = [h1("10", "Reset setelah demo"), Spacer(1, 4)]
    out.append(p("Data demo <b>tidak</b> dihapus oleh <i>Akhiri sesi</i>: baris template sengaja tidak distempel, "
                 "supaya tidak ada satu klik pun yang bisa menghapus data kanonik. Sesi berikutnya membangun ulang "
                 "dari nol, jadi angka awalnya selalu sama.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Cara", "Klik / perintah", "Waktu", "Kapan dipakai"],
        ["A. Sesi masih jalan", "Demo Control -&gt; Bangun ulang data -&gt; Ya, bangun ulang", "+-70 dtk", "Geladi berulang tanpa menutup sesi"],
        ["B. Sesi ditutup", "Demo Control -&gt; Siapkan data demo", "+-68 dtk", "Mulai sesi baru dari nol"],
        ["C. Tanpa UI", "docker exec mealchain-backend python -m app.seed.demo_template", "+-70 dtk", "Mesin demo tanpa operator"],
        ["Rollback", "pg_restore --clean --if-exists &lt; backup", "+-20 dtk", "Kalau data referensi ikut rusak"],
    ], [26 * mm, 88 * mm, 18 * mm, PAGE_W - M_L - M_R - 132 * mm]))
    out.append(p("Tabel 11 - Tiga jalur pemulihan, dari yang paling ringan ke yang paling menyeluruh.", CAP))
    out.append(Spacer(1, 7))
    out.append(p("Verifikasi setelah reset (harus sama persis dengan halaman 1):", BODY))
    out.append(Spacer(1, 4))
    out.append(kode([
        "select (select count(*) from batches)          as batch,",
        "       (select count(*) from decisions)        as keputusan,",
        "       (select count(*) from ledger_blocks)    as ledger,",
        "       (select count(*) from sap_mock_purchase_orders) as po;",
        "-- harapan: 120 | 35 | 72 | 16",
    ]))
    out.append(Spacer(1, 5))
    out.append(p("Tombol A hanya muncul saat sesi aktif, hanya untuk kepala SPPG, dan permintaan kedua saat "
                 "proses berjalan dijawab 409 — tidak diantrikan sampai klien kehabisan waktu. Isinya sama "
                 "dengan perintah C: baris operasional di-purge lalu template disemai ulang, jendela sesi "
                 "tidak disentuh.", BODY))
    out.append(Spacer(1, 5))
    out.append(p("Backup yang dipakai untuk rollback: <font face='Courier'>data/backups/"
                 "mealchain-pra-demo-2026-10-21.dump</font> (521 KB, dibuat sebelum penggantian data).", BODY))
    return out


# ------------------------------------------------------------------ 5. PETA DATA

def peta_data():
    out = [h1("11", "Di mana setiap kasus tinggal"), Spacer(1, 4)]
    out.append(p("Tabel ini yang dipakai kalau juri bertanya &quot;boleh lihat yang lain?&quot; - setiap tab punya "
                 "isi yang dijamin ada, bukan hasil kebetulan.", BODY))
    out.append(Spacer(1, 6))
    out.append(rows_table([
        ["Tab", "Isi yang dijamin ada"],
        ["Overview", "10 lokasi, 4 komoditas, gap per lokasi, notifikasi 5, peta + truk (wortel)"],
        ["Recommendations", "10 keputusan siap approve: 3 kota x regional_balance, 2 safety_disruption per kota, supplier_exclusion Jakarta"],
        ["Decision &amp; Evidence", "29 baris bukti (pesanan SAP + inspeksi manusia), 8 approval, verdict verifier konsisten"],
        ["Keamanan Pangan", "1 gagal uji, 1 karantina, 2 penerimaan menunggu, 14 needs_verification"],
        ["Surplus &amp; Limbah", "2 surplus / 8 shortage wortel; 1 pasangan 208 kg; 22 disposal event"],
        ["Pemasok", "60 pemasok; 1 eksklusi aktif, 1 usulan; 35 hygiene, 17 HACCP, 8 tanpa sertifikat"],
        ["Agent Log", "82 trace"],
        ["KPI &amp; Kualitas Agen", "7 metrik tersedia untuk 30 hari terakhir"],
        ["Demo Control", "Siapkan data, Akhiri sesi, Segarkan ke hari ini, purge"],
    ], [40 * mm, PAGE_W - M_L - M_R - 40 * mm]))
    out.append(p("Tabel 12 - Peta tab ke isi data demo.", CAP))
    return out


# ------------------------------------------------------------------ 6. RISIKO

def risiko():
    out = [h1("12", "Risiko yang diketahui - sebutkan, jangan sembunyikan"), Spacer(1, 4)]
    out.append(rows_table([
        ["Risiko", "Dampak", "Mitigasi"],
        ["Verifier lambat / satu percobaan gagal",
         "Verifikasi usulan baru bisa puluhan detik, atau 409 bila belum ada verdict",
         "Pakai 10 keputusan yang sudah consistent; verifikasi usulan baru sebelum tampil, bukan di panggung"],
        ["Siapkan data demo 68 detik",
         "Juri menunggu tanpa isi",
         "Jalankan sebelum masuk; kalau terpaksa, isi dengan narasi arsitektur"],
        ["Rute OSRM butuh internet",
         "Garis dan ikon truk tidak muncul",
         "Batch dan angka tetap benar; sebutkan peta butuh jaringan"],
        ["Tunnel Cloudflare ephemeral",
         "Koneksi AgentCore mati saat mesin tidur",
         "Named tunnel, atau MULTI_AGENT_REVIEW=false"],
        ["Ledger lama pernah yatim (570 blok)",
         "Audit terlihat tidak konsisten",
         "Template membangun ulang rantai (72 blok, 0 yatim); jangan hapus manual"],
    ], [52 * mm, 46 * mm, PAGE_W - M_L - M_R - 98 * mm]))
    out.append(p("Tabel 13 - Risiko demo dan mitigasinya.", CAP))
    out.append(Spacer(1, 7))
    out.append(p("<b>Yang belum dikerjakan dan sebaiknya tidak diklaim:</b> verifikasi offline untuk keputusan baru, "
                 "sinkronisasi dua arah ke SAP asli (mock yang dipakai sekarang), dan tombol bangun-ulang template "
                 "di dalam UI (masih lewat shell).", BODY))
    return out


# ------------------------------------------------------------------ DOKUMEN

def build(path):
    doc = BaseDocTemplate(path, pagesize=(PAGE_W, PAGE_H), leftMargin=M_L, rightMargin=M_R,
                          topMargin=M_T, bottomMargin=M_B,
                          title="MealChain Guardian - Runbook demo juri",
                          author="MealChain Guardian", subject="Alur demo, angka yang bergerak, dan reset data")
    frame = Frame(M_L, M_B, PAGE_W - M_L - M_R, PAGE_H - M_T - M_B, id="f",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame]),
        PageTemplate(id="body", frames=[frame], onPage=footer),
    ])

    def rapatkan(daftar):
        """Tempel caption &quot;Tabel N ...&quot; ke tabelnya supaya tidak terpisah halaman."""
        hasil = []
        i = 0
        while i < len(daftar):
            kini = daftar[i]
            nxt = daftar[i + 1] if i + 1 < len(daftar) else None
            teks = getattr(nxt, "text", "") if nxt is not None else ""
            if isinstance(kini, Table) and teks.startswith("Tabel"):
                hasil.append(KeepTogether([kini, nxt]))
                i += 2
                continue
            hasil.append(kini)
            i += 1
        return hasil

    story = []
    story += cover()
    story += contekan()
    story.append(Spacer(1, 9))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=2, spaceAfter=6))
    story.append(PageBreak())
    for fn in (pra, babak_0, babak_1, babak_2, babak_3, babak_4, babak_5, babak_6, reset, peta_data, risiko):
        blok = fn()
        story.append(KeepTogether(blok[:2]))
        story += blok[2:]
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=1, spaceAfter=6))
    doc.build(rapatkan(story))
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "runbook.pdf"
    print(build(out))
