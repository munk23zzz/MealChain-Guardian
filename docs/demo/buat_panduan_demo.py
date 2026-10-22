# -*- coding: utf-8 -*-
"""Bangun panduan demo MealChain Guardian (PDF, 5 halaman).

Angka yang dicetak di sini DIUKUR dari DB `mealchain` dan `/supplier-routes`
pada 22 Oktober 2026 (lihat docs/demo/panduan-demo-singkat.md). Kalau data
demo berubah, perbarui konstanta di bawah, bukan ingatan.

Jalankan:
  "$LOCALAPPDATA/Temp/pdfenv/Scripts/python.exe" docs/demo/buat_panduan_demo.py
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panduan-demo-mealchain.pdf")

# --- Angka terukur (22 Okt 2026, DB mealchain) -------------------------------
ANGKA = [
    ("Batch aktif", "125"),
    ("Keputusan", "47 (16 menunggu)"),
    ("Pemasok", "61"),
    ("Pesanan SAP", "20"),
    ("Penerimaan menunggu", "5"),
    ("Rute kiriman", "105 (80 berjalur)"),
]

NAVY = colors.HexColor("#12263A")
AKSEN = colors.HexColor("#0F6E8C")
ABU = colors.HexColor("#4A5568")
ZEBRA = colors.HexColor("#F2F6F9")
KUNING = colors.HexColor("#FFF6DC")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.2,
                      leading=13.2, alignment=TA_LEFT, textColor=colors.HexColor("#1A202C"),
                      spaceAfter=3)
KECIL = ParagraphStyle("kecil", parent=BODY, fontSize=8.2, leading=11.4, textColor=ABU)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.2, leading=11.0, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
# Header tabel: Paragraph membawa warnanya sendiri, jadi TEXTCOLOR di TableStyle
# tidak berlaku untuk sel ber-Paragraph -> tanpa gaya ini judul kolom tak terlihat
# di atas latar navy.
HEAD = ParagraphStyle("head", parent=CELL, fontName="Helvetica-Bold",
                      textColor=colors.white)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=14.5,
                    leading=18, textColor=NAVY, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=10.6,
                    leading=13.5, textColor=AKSEN, spaceBefore=6, spaceAfter=3)
JUDUL = ParagraphStyle("judul", parent=H1, fontSize=22, leading=26, spaceAfter=6)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=11, leading=15, textColor=ABU)


def p(t, s=BODY):
    return Paragraph(t, s)


def tabel(rows, widths, header=True, zebra=True):
    data = []
    for i, r in enumerate(rows):
        gaya_sel = HEAD if (i == 0 and header) else CELL
        data.append([c if isinstance(c, Paragraph) else Paragraph(str(c), gaya_sel) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    gaya = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D4DE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        gaya += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    if zebra:
        for i in range(2 if header else 1, len(data), 2):
            gaya.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(gaya))
    return t


def callout(teks, latar=KUNING):
    t = Table([[p(teks)]], colWidths=[168 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), latar),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, AKSEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def kode(*baris):
    teks = "<br/>".join(b.replace("\n", "<br/>") for b in baris)
    t = Table([[Paragraph(teks, ParagraphStyle(
        "kode", fontName="Courier", fontSize=7.8, leading=10.6,
        textColor=colors.HexColor("#E6EDF3")))]], colWidths=[168 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F1620")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#C9D4DE"))
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(ABU)
    canvas.drawString(18 * mm, 9.5 * mm, "MealChain Guardian — panduan demo (22 Okt 2026)")
    canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, "hal. %d" % doc.page)
    canvas.restoreState()


def halaman1():
    out = [Spacer(1, 26 * mm), p("MealChain Guardian", JUDUL),
           p("Panduan demo — langkah singkat untuk operator", SUB),
           Spacer(1, 6 * mm),
           p("Dokumen ini dipakai sambil berdiri: satu halaman persiapan, satu lembar contekan, "
             "enam babak berisi langkah klik, lalu pemulihan bila ada yang gagal di tengah jalan."),
           Spacer(1, 5 * mm), p("Durasi", H2),
           p("Persiapan 15 menit sebelum juri masuk, tampil 12 menit, tanya-jawab 5 menit."),
           p("Prasyarat", H2),
           p("1) Docker Desktop hidup dan stack sudah jalan (backend, frontend, Postgres, mock-SAP). "
             "2) Data demo sudah disemai ulang. 3) Jembatan Joule melaporkan <b>reachable:true</b>. "
             "Ketiganya diperiksa di halaman 3."),
           Spacer(1, 4 * mm), p("Keadaan awal yang harus terlihat", H2),
           tabel([["Ukuran", "Nilai terukur 22 Okt 2026"]] + [[k, v] for k, v in ANGKA],
                 [70 * mm, 90 * mm]),
           Spacer(1, 4 * mm),
           callout("Halaman 2 boleh dicetak terpisah dan ditaruh di samping laptop: isinya ringkasan "
                   "babak, angka yang bergerak, dan tanya-jawab yang sering muncul."),
           Spacer(1, 5 * mm), p("Isi dokumen", H2),
           tabel([["Hal.", "Isi", "Dipakai kapan"],
                  ["2", "Lembar contekan: babak, angka, tanya-jawab", "dipegang saat tampil"],
                  ["3", "Persiapan 15 menit + layanan dan port", "sebelum juri masuk"],
                  ["4", "Enam babak berisi langkah klik", "selama demo"],
                  ["5", "Joule, pemulihan cepat, hal yang tidak boleh diklaim", "saat tanya-jawab"]],
                 [12 * mm, 96 * mm, 60 * mm]),
           ]
    return out


def halaman2():
    besar = ParagraphStyle("besar", parent=BODY, fontName="Helvetica-Bold", fontSize=15,
                           leading=17, textColor=NAVY, alignment=1)
    label = ParagraphStyle("label", parent=BODY, fontSize=7.4, leading=9, textColor=ABU, alignment=1)
    sel = [[Paragraph(v, besar), Paragraph(k, label)] for k, v in ANGKA]
    band = Table([[sel[0][0], sel[1][0], sel[2][0]], [sel[0][1], sel[1][1], sel[2][1]],
                  [sel[3][0], sel[4][0], sel[5][0]], [sel[3][1], sel[4][1], sel[5][1]]],
                 colWidths=[56 * mm] * 3)
    band.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                              ("TOPPADDING", (0, 0), (-1, -1), 2),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    out = [p("Lembar contekan", H1),
           p("Angka keadaan awal (terukur 22 Okt 2026):", KECIL), band, Spacer(1, 3 * mm),
           p("Satu baris per babak. Kolom terakhir adalah angka yang berubah di layar — itu yang "
             "disebut saat menjelaskan.", KECIL),
           Spacer(1, 3 * mm)]
    baris = [
        ["Waktu", "Tab", "Aksi", "Angka yang bergerak"],
        ["0:00-1:30", "Overview", "Tunjuk peta + KPI, sebut angka batch & keputusan", "125 batch, 47 keputusan"],
        ["1:30-4:30", "Recommendations -> Decision & Evidence", "Buka satu usulan, lihat bukti, Kelola persetujuan -> Setuju", "persetujuan 0/2 -> 1/2"],
        ["4:30-6:30", "Keamanan Pangan", "Tunjuk batch gagal uji & karantina; setujui satu penerimaan (5 kotak centang)", "penerimaan menunggu 5 -> 4"],
        ["6:30-8:00", "Pemasok", "Cari pemasok, tunjuk tanda eksklusi, buka papan kiriman", "105 kiriman, 8 di jalan"],
        ["8:00-9:30", "Demo Control", "Jalankan agent, tunggu status selesai", "jejak agent bertambah"],
        ["9:30-12:00", "Joule (webclient)", "Ajukan 3 pertanyaan, biarkan tabel muncul", "angka sama dengan layar"],
    ]
    out += [tabel(baris, [19 * mm, 40 * mm, 60 * mm, 49 * mm]), Spacer(1, 5 * mm),
            p("Tiga bukti terukur yang bisa disebut", H2),
            tabel([["Bukti", "Angka", "Cara menunjukkannya"],
                   ["Persetujuan dua peran", "0/2 -> 1/2",
                    "Decision & Evidence -> Kelola persetujuan, status tetap menunggu"],
                   ["Eksekusi tanpa kuorum ditolak", "HTTP 409",
                    "coba Eksekusi sebelum peran kedua menyetujui"],
                   ["Joule membaca DB yang sama", "40 baris pasokan",
                    "bandingkan satu id keputusan di jawaban dengan tab Decision & Evidence"]],
                  [52 * mm, 26 * mm, 90 * mm]),
            Spacer(1, 5 * mm),
            p("Tanya-jawab yang sering muncul", H2)]
    out += [tabel([
        ["Pertanyaan juri", "Jawaban singkat"],
        ["Ini data asli atau mockup?", "Data asli di PostgreSQL 16.15 lokal; SAP dan Joule memakai endpoint tiruan yang kontraknya sama."],
        ["Siapa yang memutuskan?", "Agen mengusulkan, manusia menyetujui. Eksekusi ditolak sistem bila kuorum belum terpenuhi (terbukti 409)."],
        ["Kenapa angka di Joule sama?", "Joule membaca backend yang sama lewat jembatan A2A, bukan salinan data."],
        ["Kalau jaringan mati?", "Tunjukkan mode DEFAULT: layar kosong dengan pesan, bukan angka palsu."],
    ], [58 * mm, 110 * mm]), Spacer(1, 5 * mm),
        p("Ruang catatan", H2)]
    for _ in range(4):
        out.append(Table([[""]], colWidths=[168 * mm], rowHeights=[9 * mm],
                         style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D4DE"))])))
    return out


def halaman3():
    out = [p("Persiapan (15 menit sebelum juri)", H1),
           p("Urutannya penting: database dulu, baru jembatan Joule, terakhir browser. "
             "Kalau dibalik, layar akan menampilkan keadaan lama.", KECIL), Spacer(1, 2 * mm),
           p("1. Nyalakan stack", H2),
           kode("cd E:/hackathon/HackathonAWS/mealchain-guardian\n"
                "docker compose up -d"),
           Spacer(1, 2 * mm), p("2. Semai ulang data demo (deterministik, +/- 90 detik)", H2),
           kode("DB_MODE=demo bash scripts/db-mode.sh init-demo"),
           p("Ini juga menyegarkan rute OSRM dan memberangkatkan 8 kiriman, sehingga peta punya truk "
             "berjalan. Tanpa langkah ini, kiriman akan tampak 'sudah tiba' semua.", KECIL),
           Spacer(1, 2 * mm), p("3. Pastikan backend sehat", H2),
           kode("curl -s http://localhost:8000/health\n# {\"status\":\"healthy\",\"service\":\"mealchain-backend\"}"),
           Spacer(1, 2 * mm), p("4. Pastikan jembatan Joule sampai ke backend", H2),
           kode("bash scripts/joule-perbaiki.sh\n# ... {\"backend\":{\"reachable\":true, ...}}"),
           p("Skrip ini menyalakan tunel baru, mengarahkan aplikasi CF ke URL itu, lalu memverifikasi "
             "lewat route Cloud Foundry. Kalau sesi cf kedaluwarsa, skrip meminta login SSO lebih dulu.", KECIL),
           Spacer(1, 2 * mm), p("5. Buka tiga akun demo", H2),
           tabel([["Peran", "Email", "Dipakai untuk"],
                  ["Kepala SPPG", "sppg.head@demo.local", "setujui keputusan, setujui penerimaan, Demo Control"],
                  ["Ahli Gizi", "sppg.nutritionist@demo.local", "keamanan pangan (tanpa hak setuju keputusan)"],
                  ["BGN Monitor", "bgn.monitor@demo.local", "peta nasional, direktori pemasok, Pengaturan"]],
                 [30 * mm, 62 * mm, 76 * mm]),
           p("Kata sandi ada di berkas .env lokal (tidak dicetak di dokumen ini).", KECIL),
           Spacer(1, 2 * mm),
           Spacer(1, 2 * mm), p("6. Layanan yang harus hidup", H2),
           tabel([["Layanan", "Alamat", "Tanda hidup"],
                  ["Frontend konsol", "http://localhost:3010", "halaman login tampil"],
                  ["Backend API", "http://localhost:8000", "/health -> healthy"],
                  ["Jembatan Joule lokal", "http://127.0.0.1:8099", "agent card 1.4.0, 13 skill"],
                  ["PostgreSQL", "localhost:15432 -> 5432", "psql select 1 berhasil"],
                  ["Mock SAP", "http://localhost:8001", "daftar pesanan tampil di tab keputusan"]],
                 [42 * mm, 60 * mm, 66 * mm]),
           Spacer(1, 3 * mm),
           callout("Tiga hal yang paling sering menggagalkan demo: (a) data demo belum disemai sehingga "
                   "peta kosong, (b) tunel Cloudflare mati sehingga Joule menjawab 'backend tidak bisa "
                   "dihubungi', (c) halaman dibuka sebelum backend selesai start sehingga muncul pesan galat."),
           ]
    return out


def halaman4():
    out = [p("Enam babak — langkah klik", H1),
           p("Setiap babak: tujuan, langkah, dan bukti di layar. Jangan lompat babak; angka di babak "
             "berikut mengacu pada keadaan sesudah babak sebelumnya.", KECIL), Spacer(1, 3 * mm)]
    babak = [
        ("Babak 0 — Pembuka (Overview, 1,5 menit)",
         ["Buka tab <b>Overview</b>. Peta nasional tampil dengan pin pemasok dan garis jalur.",
          "Sebut: 125 batch, 47 keputusan, 61 pemasok, 20 pesanan SAP.",
          "Klik chip komoditas (telur / ayam / beras / wortel) untuk menunjukkan peta menyaring per komoditas.",
          "Tunjuk panel kiriman: <i>8 di jalan</i> — kalau semua 'sudah tiba', ulangi langkah 2 persiapan."]),
        ("Babak 1 — Agen mengusulkan, manusia memutuskan (3 menit)",
         ["Tab <b>Recommendations</b> -> buka satu kartu usulan.",
          "Baca ringkasan bukti: biaya, keamanan, pemasok. Sebut bahwa angka berasal dari tabel, bukan teks agen.",
          "Pindah ke <b>Decision & Evidence</b> -> tombol <b>Kelola persetujuan…</b>.",
          "Tekan <b>Setuju</b>. Persetujuan menjadi 1 dari 2 peran; status tetap menunggu karena butuh peran kedua.",
          "Tunjukkan percobaan eksekusi sebelum kuorum -> sistem menolak (409 'approval belum memenuhi requirement')."]),
        ("Babak 2 — Keamanan pangan (2 menit)",
         ["Tab <b>Keamanan Pangan</b>: tunjuk batch <i>gagal uji</i> dan batch <i>karantina</i>.",
          "Sebut aturan: batch gagal tidak pernah masuk alokasi, karantina menahan sampai dilepas.",
          "Tunjuk antrean penerimaan: 5 menunggu."]),
        ("Babak 3 — Penerimaan barang (1,5 menit)",
         ["Masih di <b>Keamanan Pangan</b> -> buka satu penerimaan.",
          "Centang lima butir pemeriksaan (kemasan, suhu, kesegaran, timbangan, lot).",
          "Tekan <b>Setujui & masukkan stok</b>. Penerimaan menunggu 5 -> 4 dan stok bertambah."]),
        ("Babak 4 — Pemasok & jalur kiriman (1,5 menit)",
         ["Tab <b>Pemasok</b>: tunjuk ringkasan (61 pemasok, 6 eksklusi), lalu <b>Cari pemasok</b>.",
          "Tunjuk penanda 'Dikecualikan di &lt;lokasi&gt;' — eksklusi berlaku per hub, bukan global.",
          "Gulir ke papan kiriman: 105 kiriman, urutkan 'Paling mendesak', tunjuk kolom jalur & estimasi tiba."]),
        ("Babak 5 — Agen berjalan (1,5 menit)",
         ["Tab <b>Demo Control</b> -> pilih komoditas -> tekan <b>Jalankan agent</b>.",
          "Tunggu sampai status <b>selesai · primary:agentcore</b>.",
          "Buka <b>Agent Log</b>: tunjuk jejak yang baru bertambah; sebut bahwa jejak disimpan di DB, bukan di memori UI."]),
        ("Babak 6 — Joule (3 menit)",
         ["Buka webclient Joule (URL di halaman 5).",
          "Ajukan tiga pertanyaan berurutan: kondisi pasokan -> antrean penerimaan -> direktori pemasok.",
          "Tunjuk bahwa angka di jawaban sama dengan angka di layar — satu backend, dua antarmuka."]),
    ]
    for judul, langkah in babak:
        blok = [p(judul, H2)]
        for i, l in enumerate(langkah, 1):
            blok.append(p("%d. %s" % (i, l)))
        out.append(KeepTogether(blok))
    return out


def halaman5():
    out = [p("Joule: pertanyaan yang sudah terbukti", H1),
           p("Diuji 14 pertanyaan, 14 lulus (mode DEMO). Tiga di antaranya paling aman untuk panggung:", KECIL),
           Spacer(1, 2 * mm)]
    out += [tabel([["Ucapan", "Yang muncul"],
                   ["kondisi pasokan", "tabel keseimbangan per lokasi (40 baris), kekurangan lebih dulu"],
                   ["antrean penerimaan", "antrean usulan keputusan (12 baris) beserta id"],
                   ["direktori pemasok", "daftar pemasok + penanda eksklusi di hub"],
                   ["status sistem", "kesehatan backend dan versi kemampuan (1.4.0, 13 skill)"]],
                  [45 * mm, 123 * mm]),
            Spacer(1, 4 * mm),
            p("URL webclient", H2),
            kode("https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap/webclient/standalone/",
                 "    mealchain_assistant_4sehat3trio"),
            Spacer(1, 3 * mm),
            p("Kalau ada yang gagal di panggung", H2)]
    out += [tabel([["Gejala", "Satu perintah / tindakan"],
                   ["Joule: 'backend tidak bisa dihubungi'", "bash scripts/joule-perbaiki.sh (tunel + set-env + restage)"],
                   ["Peta kosong / tanpa truk", "DB_MODE=demo bash scripts/db-mode.sh init-demo (90 detik)"],
                   ["Layar kosong di Overview (peran BGN)", "muat ulang halaman; bila berulang, laporkan — sudah diperbaiki 22 Okt"],
                   ["Ingin keadaan bersih tanpa data", "DB_MODE=default bash scripts/db-mode.sh init-default"]],
                  [60 * mm, 108 * mm]),
            Spacer(1, 4 * mm),
            p("Mengembalikan keadaan sesudah tampil", H2),
            tabel([["Cara", "Perintah", "Waktu"],
                   ["Data demo segar", "DB_MODE=demo bash scripts/db-mode.sh init-demo", "~90 detik"],
                   ["Mode kosong (referensi saja)", "DB_MODE=default bash scripts/db-mode.sh init-default", "~15 detik"],
                   ["Hapus baris demo", "DB_MODE=demo bash scripts/db-mode.sh reset-demo --yes", "~20 detik"],
                   ["Cek mode aktif", "bash scripts/db-mode.sh status", "seketika"]],
                  [40 * mm, 96 * mm, 32 * mm]),
            Spacer(1, 4 * mm),
            p("Jangan diklaim saat demo", H2),
            p("- Jumlah pengguna serentak atau hasil uji beban: belum diukur.<br/>"
              "- SAP S/4HANA dan tenant Joule produksi: masih endpoint tiruan dengan kontrak sama.<br/>"
              "- Model Bedrock produksi: kuota TPM masih 0; pipeline agen berjalan lewat jalur yang tersedia.<br/>"
              "- Peta menampilkan satu komoditas per tampilan, tidak ada mode semua komoditas sekaligus."),
            Spacer(1, 4 * mm),
            callout("Sesudah demo: kembalikan keadaan dengan <b>bash scripts/db-mode.sh reset-demo --yes</b> "
                    "lalu <b>init-demo</b> bila akan tampil lagi. Jangan tinggalkan data hasil klik panggung "
                    "karena angka awal dokumen ini menjadi tidak cocok."),
            ]
    return out


def build():
    doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=16 * mm, bottomMargin=18 * mm,
                          title="MealChain Guardian — panduan demo",
                          author="MealChain Guardian", subject="Langkah demo 12 menit")
    frame = Frame(18 * mm, 18 * mm, A4[0] - 36 * mm, A4[1] - 34 * mm, id="body",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame]),
        PageTemplate(id="body", frames=[frame], onPage=footer),
    ])
    story = [NextPageTemplate("cover")] + halaman1() + [NextPageTemplate("body"), PageBreak()]
    for fungsi in (halaman2, halaman3, halaman4, halaman5):
        story += fungsi()
        if fungsi is not halaman5:
            story.append(PageBreak())
    doc.build(story)
    print("OK ->", OUT)


if __name__ == "__main__":
    build()
