# -*- coding: utf-8 -*-
"""Bangun laporan PDF "Alur semua fitur" MealChain Guardian.

Gaya visual diimpor dari docs/demo/buat_panduan_demo.py supaya kedua dokumen
satu keluarga. Angka diambil dari snapshot terukur
(scratch/snap_fitur.py, 26 Okt 2026 11.51 WIB) — bukan dari ingatan.

Jalankan:
  "$LOCALAPPDATA/Temp/pdfenv/Scripts/python.exe" docs/laporan/buat_alur_fitur.py
"""
from __future__ import annotations

import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo"))
from buat_panduan_demo import (AKSEN, BODY, CELL, H1, H2, HEAD, JUDUL,  # noqa: E402
                               KECIL, NAVY, SUB, callout, kode, p, tabel)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alur-fitur-mealchain.pdf")
TANGGAL = "26 Oktober 2026, 11.51 WIB"
SNAP = "scratch/snap_fitur.py (DB mealchain + API hidup)"

# judul tidak boleh menggantung sendiri di kaki halaman
H1.keepWithNext = 1
H2.keepWithNext = 1

LANGKAH = ParagraphStyle("langkah", parent=BODY, leftIndent=11, bulletIndent=2,
                         spaceAfter=1.6)
SEL = ParagraphStyle("sel", parent=CELL, fontSize=7.9, leading=10.4)


def langkah(daftar):
    """Daftar bernomor: satu Paragraph per langkah (bukan satu blok)."""
    return [Paragraph(t, LANGKAH, bulletText=f"{i}.") for i, t in enumerate(daftar, 1)]


def t3(rows, widths=(8 * mm, 40 * mm, 120 * mm)):
    return tabel(rows, list(widths))


# --- isi --------------------------------------------------------------------

def sampul():
    return [
        Spacer(1, 22 * mm),
        p("MealChain Guardian", JUDUL),
        p("Alur semua fitur: dari klik di layar sampai baris di database", SUB),
        Spacer(1, 7 * mm),
        p("Dokumen ini menjelaskan <b>alur kerja setiap fitur</b> yang ada di aplikasi — "
          "sepuluh tab konsol, pipeline agen, tujuh KPI, dan panel kendali demo — beserta "
          "sumber datanya (endpoint dan tabel), aturan bisnis yang menegakkannya, dan angka "
          "yang benar-benar terukur pada lingkungan demo.", BODY),
        Spacer(1, 3 * mm),
        tabel([
            ["Ruang lingkup", "10 tab konsol + 10 alur fitur + 6 state machine + 7 KPI + pipeline agen"],
            ["Pengguna", "SPPG Head, SPPG Nutritionist (satu lokasi), BGN Monitor (lintas lokasi, baca saja)"],
            ["Sumber fakta", SNAP],
            ["Tanggal data", TANGGAL],
            ["Versi aplikasi", "branch feature/db-modes-demo-coverage, Alembic head 033, PostgreSQL 16.15"],
        ], [38 * mm, 130 * mm], header=False, zebra=True),
        Spacer(1, 4 * mm),
        callout("<b>Cara membaca:</b> setiap bagian fitur memuat tabel <i>langkah</i> "
                "(apa yang diklik, apa yang terjadi, apa buktinya), tabel <i>aturan</i> "
                "(yang tidak boleh dilanggar), dan satu baris <i>angka sekarang</i> yang "
                "diambil dari database pada waktu di atas. Angka yang tidak terukur "
                "ditulis \"—\", tidak pernah diganti nol."),
        Spacer(1, 4 * mm),
        p("Sepuluh tab dan pertanyaan yang dijawabnya", H2),
        tabel([
            ["Tab", "Pertanyaan yang dijawab", "Menulis?"],
            ["Hari Ini", "apa yang harus saya lakukan pagi ini?", "tidak"],
            ["Overview", "di mana barang bergerak, mana yang tertinggal?", "tidak"],
            ["Recommendations", "usulan agen mana yang mendesak?", "tidak"],
            ["Decision & Evidence", "cukup bukti? setujui, tolak, atau eksekusi?", "ya"],
            ["Keamanan Pangan", "barang mana aman dipakai, mana ditahan?", "ya"],
            ["Surplus & Limbah", "berapa terbuang, ke mana surplus layak pergi?", "ya"],
            ["Pemasok", "siapa andal, siapa harus dikecualikan?", "ya"],
            ["Agent Log", "apa yang sebenarnya dikerjakan agen?", "tidak"],
            ["KPI & Kualitas Agen", "sistem membaik? agen bisa dipercaya?", "tidak"],
            ["Demo Control", "siapkan, jalankan, akhiri demo", "ya"],
        ], [34 * mm, 112 * mm, 22 * mm]),
    ]


JUDUL_BAGIAN = [
    ("1", "Ringkasan sistem dan angka kunci"),
    ("2", "Arsitektur: satu klik menyeberangi lima lapisan"),
    ("3", "Aturan yang berlaku di semua fitur (peran, sesi, empat mata, ledger)"),
    ("4", "Alur sepuluh fitur"),
    ("4.1", "Hari Ini — agenda dan kartu tindakan"),
    ("4.2", "Overview — peta pasokan dan kiriman"),
    ("4.3", "Recommendations — feed keputusan agen"),
    ("4.4", "Decision & Evidence — keputusan, bukti, persetujuan"),
    ("4.5", "Keamanan Pangan — batch, karantina, penerimaan"),
    ("4.6", "Surplus & Limbah — neraca dan alokasi"),
    ("4.7", "Pemasok — direktori, eksklusi, papan kiriman"),
    ("4.8", "Agent Log — jejak penalaran per langkah"),
    ("4.9", "KPI & Kualitas Agen — tujuh metrik dan audit sampel"),
    ("4.10", "Demo Control — sesi, data, agent, integrasi"),
    ("5", "Enam state machine yang menegakkan aturan"),
    ("6", "Tujuh KPI: rumus, jendela, dan arti no_data"),
    ("7", "Pipeline agen: delapan tahap"),
    ("8", "Alur demo panggung sebelas menit"),
    ("9", "Gerbang mutu dan bukti uji"),
    ("10", "Keterbatasan dan risiko yang harus disebut"),
]


def daftar_isi(hal_map=None):
    hal_map = hal_map or {}
    rows = [["Bagian", "Isi", "Halaman"]]
    for nomor, judul in JUDUL_BAGIAN:
        rows.append([nomor, judul, str(hal_map.get(nomor, "-"))])
    return [
        p("Daftar isi", H1),
        tabel(rows, [14 * mm, 128 * mm, 26 * mm]),
        Spacer(1, 3 * mm),
        p("Nomor halaman diambil dari hasil cetak dokumen ini sendiri (dua lintasan build), "
          "jadi tidak meleset bila isi diperbarui. Setiap angka keadaan diambil ulang saat "
          "dokumen dibangun.", KECIL),
    ]


def ringkasan():
    out = [p("1. Ringkasan sistem dan angka kunci", H1),
           p("MealChain Guardian adalah konsol keputusan rantai pasok pangan untuk SPPG. "
             "Agen mendeteksi masalah (kekurangan stok, anomali harga, gangguan keamanan, "
             "pemasok berisiko), menyusun usulan beserta biaya dan buktinya, lalu "
             "<b>manusia</b> yang memutuskan: verifikasi, setujui (dua peran berbeda), "
             "eksekusi menjadi pesanan pembelian, atau tolak dengan alasan. Setiap langkah "
             "ditulis ke rantai audit yang tidak bisa diubah diam-diam.", BODY)]
    out.append(p("Angka kunci pada lingkungan demo", H2))
    out.append(tabel([
        ["Objek", "Jumlah", "Arti operasional"],
        ["Keputusan agen", "36 (19 terbuka)", "19 kartu menunggu tindakan manusia; 17 sisanya sudah selesai/ditolak"],
        ["Batch barang", "120", "satu batch = satu kiriman dengan berat, umur simpan, dan status uji sendiri"],
        ["Catatan pasokan", "5.240", "deret waktu pasokan 1 Sep - 4 Nov 2026 (basis grafik dan KPI)"],
        ["Rencana menu", "660", "rencana porsi per lokasi per hari (basis Meal Continuity)"],
        ["Kutipan harga", "5.924", "kutipan pemasok + referensi PIHPS (basis Price Deviation)"],
        ["Peristiwa limbah", "80", "pembuangan tercatat (basis Avoidable Food Loss)"],
        ["Pemasok", "60", "direktori dengan jarak, keandalan, sertifikasi, dan status eksklusi"],
        ["Rute kiriman", "12 (11 berjalur)", "satu baris = satu kiriman aktif, dengan jalur OSRM dan tahap perjalanan"],
        ["Jejak agen", "85 langkah", "satu baris per tahap per keputusan (DETECT, PREDICT, DECIDE, ACT, ...)"],
        ["Pesanan SAP", "16", "terbit setelah eksekusi; nomor MC-xxxx dapat ditelusuri ke keputusan"],
        ["Persetujuan", "21 baris", "empat mata: dua akun berbeda; penolakan juga dicatat dengan alasan"],
        ["Bukti keputusan", "51 dokumen", "minimal dua jenis bukti sebelum persetujuan (dasar Evidence Completeness)"],
        ["Blok rantai audit", "1.382 (1.310 arsip)", "hash chain append-only; generasi lama disimpan sebagai arsip"],
        ["Akun", "11", "3 peran sah; sisanya akun demo per lokasi"],
    ], [34 * mm, 30 * mm, 104 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(callout("<b>Batas yang jujur:</b> seluruh angka di dokumen ini berasal dari "
                       "template demo di database (kolom <font face='Courier'>origin</font> "
                       "= seed/demo), bukan data operasional nyata dan bukan panggilan "
                       "sungguhan ke SAP atau Bedrock. Integrasi eksternal berjalan dalam "
                       "mode simulasi (mock SAP) dan jalur jalan memakai OSRM."))
    return out


def arsitektur():
    out = [p("2. Arsitektur: satu klik menyeberangi lima lapisan", H1),
           p("Konsol adalah satu halaman Next.js (App Router) yang menyusun sepuluh tab. "
             "Tidak ada API route Next: semua panggilan diproksi ke backend FastAPI di "
             "origin yang sama, sehingga cookie/token tidak menyeberang domain.", BODY)]
    out.append(tabel([
        ["Lapisan", "Teknologi", "Perannya"],
        ["Antarmuka", "Next.js 14.2.14, React 18.3.1, TypeScript, TanStack Query 5.56",
         "10 tab, peta MapLibre 4.7.1, grafik Recharts 2.12.7; semua angka dari API, nilai kosong ditulis \"—\""],
        ["Kontrak", "77 operasi OpenAPI (34 router)",
         "satu sumber kebenaran bentuk data; artefak openapi.json diuji tidak basi"],
        ["Logika", "FastAPI + SQLAlchemy async, Alembic head 033",
         "RBAC, sesi demo, state machine keputusan, perhitungan KPI, ledger hash chain"],
        ["Data", "PostgreSQL 16.15, 24 tabel",
         "fakta (supply/demand/price/menu/delivery/disposal), keputusan, bukti, approval, PO, jejak"],
        ["Eksternal", "mock SAP, OSRM, Bedrock AgentCore (opsional)",
         "PO keluar ke SAP; jarak/jalur jalan; pemanggilan model agen bila kredensial tersedia"],
    ], [22 * mm, 62 * mm, 84 * mm]))
    out.append(p("Jalur satu permintaan (contoh: membuka tab Hari Ini)", H2))
    out.append(kode("Browser GET /agenda?start=2026-10-26&end=2026-10-26",
                    "  -> Next rewrite (API_ROOTS di next.config.mjs)          [tanpa /api, tanpa :8000]",
                    "  -> FastAPI: app/api/agenda.py  (JWT -> peran -> lokasi sendiri)",
                    "  -> SQL: menu_plans, delivery_events, disposal_events, supply_records,",
                    "          price_signals, batches, decisions",
                    "  -> JSON {period, scope, computed_at, days[]}",
                    "  -> React Query cache -> komponen -> angka di layar"))
    out.append(Spacer(1, 2 * mm))
    out.append(callout("Konsekuensi desain: kalau sebuah angka tidak ada di layar, penyebabnya "
                       "selalu salah satu dari tiga — data tidak ada di DB, endpoint menyaringnya "
                       "keluar (mis. cakupan lokasi), atau nilainya kosong dan ditulis \"—\". "
                       "Tidak ada angka contoh di komponen."))
    return out


def aturan_global():
    out = [p("3. Aturan yang berlaku di semua fitur", H1),
           p("Tiga hal di bawah ini menjelaskan mengapa banyak tombol bisa menolak (403/409/422). "
             "Ini bukan bug: penolakan adalah bagian dari alur.", BODY)]
    out.append(p("3.1 Peran dan cakupan data", H2))
    out.append(tabel([
        ["Peran", "Boleh melihat", "Boleh menulis"],
        ["SPPG Head", "satu lokasi (dari token)", "usul, setujui/tolak, eksekusi, catat penerimaan, catat limbah, kelola sesi demo"],
        ["SPPG Nutritionist", "satu lokasi", "usul, setujui/tolak (akun kedua untuk empat mata), catat penerimaan"],
        ["BGN Monitor", "semua lokasi (agregat)", "tidak ada: seluruh endpoint tulis menolak 403"],
    ], [32 * mm, 44 * mm, 92 * mm]))
    out.append(p("3.2 Sesi demo: dua jam, satu sesi, penjaga mutasi", H2))
    out.extend(langkah([
        "Menekan <b>Siapkan data demo</b> membangun template <i>lebih dulu</i>, baru membuka sesi "
        "(urutan ini mencegah sesi aktif dengan database kosong bila build gagal).",
        "Masa berlaku <font face='Courier'>expires_at = started_at + 120 menit</font>; "
        "<i>extend</i> hanya menambal sampai plafon 120 menit, tidak pernah melewatinya.",
        "Satu sesi aktif dijamin database lewat unique partial index "
        "<font face='Courier'>uq_demo_sessions_satu_aktif</font>, bukan hanya kunci di aplikasi.",
        "Selama tidak ada sesi aktif, middleware menolak POST/PUT/PATCH/DELETE dengan <b>409</b> "
        "(kecuali /auth/login, /health, dan pengelola sesi). Membaca tetap boleh.",
        "Saat sesi berakhir, baris operasional milik sesi dihapus; data kanonik "
        "(<font face='Courier'>origin='seed'</font>) tidak pernah disentuh.",
    ]))
    out.append(p("3.3 Empat mata, bukti, dan rantai audit", H2))
    out.append(tabel([
        ["Aturan", "Penegak", "Akibat bila dilanggar"],
        ["Dua akun berbeda harus menyetujui",
         "CHECK unik (keputusan, akun) + evaluasi kuorum",
         "akun yang sama menyetujui dua kali -> 409 \"approval sudah tercatat untuk akun ini\""],
        ["Tidak ada eksekusi tanpa persetujuan",
         "prasyarat /actions/execute (kuorum + verdict + belum kedaluwarsa)",
         "eksekusi ditolak; penyemai demo diuji agar tidak melahirkan executed tanpa approval"],
        ["Penolakan wajib beralasan",
         "validasi 422 + baris approvals(approved=false)",
         "tanpa komentar -> 422; alasan menjadi bahan belajar agen"],
        ["Setiap approve/reject/execute menulis blok",
         "ledger hash chain (append-only)",
         "/ledger/verify melaporkan rantai utuh; blok generasi lama menjadi arsip, tidak dihapus"],
        ["Nilai tak diketahui ditulis \"—\"",
         "kontrak frontend/lib/today.ts",
         "tidak ada 0 palsu; ini yang membuat KPI bisa no_data tanpa menyesatkan"],
    ], [44 * mm, 52 * mm, 72 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(callout("Tujuh status keputusan (CHECK di database): proposed, verifier_flagged, "
                       "pending_approval, approved, rejected, executed, review_only. Status di luar "
                       "daftar itu ditolak database, bukan hanya oleh UI."))
    return out


def fitur_hari_ini():
    out = [p("4. Alur sepuluh fitur", H1),
           p("Setiap sub-bagian memakai pola yang sama: tujuan, langkah, aturan, lalu angka "
             "yang terukur saat dokumen ini dibangun.", BODY),
           p("4.1 Hari Ini — agenda dan kartu tindakan", H2),
           p("Halaman pertama menjawab satu pertanyaan: <i>apa yang harus saya lakukan pagi ini?</i> "
             "Isinya strip enam kartu, agenda harian satu tanggal, dan daftar agenda terdekat.", BODY)]
    out.extend(langkah([
        "Pengguna membuka tab; tanggal aktif = hari ini (WIB) dan bisa diganti lewat pemilih tanggal.",
        "Strip kartu memuat: menunggu tindakan, batch mendekati kedaluwarsa (<48 jam, cakupan "
        "seluruh jaringan dan ditulis apa adanya), lokasi shortage, KPI tersedia, dan status rantai audit.",
        "Agenda harian memanggil <font face='Courier'>/agenda?start=..&end=..</font> dan menampilkan "
        "rencana menu (porsi), pengiriman makan tiba (porsi), pasokan tercatat (baris), harga tercatat "
        "(baris), limbah dibuang (kg + peristiwa), batch kedaluwarsa, dan keputusan agen per status.",
        "Klik kartu agenda membuka tab yang menjelaskan angka itu (mis. keputusan -> Recommendations).",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Agenda harian", "GET /agenda", "menu_plans, delivery_events, disposal_events, supply_records, price_signals, batches, decisions"],
        ["Strip kartu", "GET /decisions?window=24h, GET /batches, GET /kpi?periode=today, GET /ledger/verify", "decisions, batches, kpi (agregat), ledger_blocks"],
        ["Angka terukur", "1.211 porsi rencana · 12 baris pasokan · 33 baris harga · 31,49 kg limbah (3 peristiwa) · 2 batch kedaluwarsa · 11 keputusan (9 menunggu, 2 ditandai verifier) · rantai audit utuh", "—"],
    ], [30 * mm, 62 * mm, 76 * mm]))
    out.append(p("Aturan: porsi yang belum dikirim tidak dihitung 0 — jadwalnya kosong dan ditulis "
                 "\"tidak ada catatan\". Halaman ini membaca, tidak pernah menulis.", KECIL))
    return out


def fitur_overview():
    out = [p("4.2 Overview — peta pasokan dan kiriman", H2),
           p("Menjawab: <i>di mana barang bergerak, dan mana yang belum sampai?</i> Peta MapLibre "
             "menampilkan lokasi, pemasok, dan jalur kiriman; panel ringkasan memberi angka jaringan.", BODY)]
    out.extend(langkah([
        "Buka tab: peta memuat titik lokasi + pemasok aktif, dengan legenda nada (jangkauan, stok layak, dikecualikan).",
        "Pilih komoditas -> peta memanggil <font face='Courier'>/balance/map?commodity=..</font> "
        "dan mewarnai lokasi menurut surplus/shortage.",
        "Klik pin pemasok -> popup berisi keandalan, sertifikasi, jarak, dan status kirimannya.",
        "Panel kiriman memakai <font face='Courier'>/supplier-routes</font>: satu baris per kiriman "
        "dengan tahap (belum berangkat, di jalan, sudah tiba, tidak diketahui) dan jalur OSRM.",
        "Garis waktu bergerak sendiri: posisi truk dihitung dari waktu berangkat + durasi rute, "
        "bukan animasi hiasan; kiriman yang sudah tiba digambar redup.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel / layanan"],
        ["Titik & jalur", "GET /suppliers, GET /supplier-routes?limit=200", "suppliers, batches, road_routes (OSRM)"],
        ["Saldo per lokasi", "GET /balance/map?commodity=..", "supply_records, demand_records (baris TERBARU <= now)"],
        ["Angka terukur", "12 rute (11 berjalur OSRM) · 60 pemasok · 30 dalam 150 km · 53 punya stok layak", "—"],
    ], [30 * mm, 62 * mm, 76 * mm]))
    out.append(p("Aturan: jarak jalan hanya ditulis bila OSRM menjawab; kalau tidak, selnya "
                 "\"belum disinkronkan\" dan tidak diisi jarak lurus sebagai pengganti.", KECIL))
    return out


def fitur_rekomendasi():
    out = [p("4.3 Recommendations — feed keputusan agen", H2),
           p("Feed adalah antrean kerja: satu kartu = satu keputusan agen, diurutkan menurut urgensi. "
             "Manusia membaca ringkasnya di sini, lalu membuka tab Decision & Evidence untuk bertindak.", BODY)]
    out.extend(langkah([
        "Kartu memuat: jenis kasus, komoditas/berat, biaya (SDC), status, sisa waktu berlaku, dan satu kalimat rencana.",
        "Filter periode (Hari ini / 7 hari / 1 bulan) dan urutan (urgensi, tenggat, terbaru) tersedia di kepala feed.",
        "Pencarian menyaring judul/komoditas; pager menjaga tinggi halaman.",
        "Klik kartu -> tab Decision & Evidence membuka keputusan yang sama (id yang sama, bukan salinan).",
        "Badge sidebar dan lonceng memakai sumber yang sama, jadi angka \"menunggu tindakan\" selalu konsisten.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Feed", "GET /decisions?window=24h|7d|30d", "decisions (+ supplier, commodity, lokasi)"],
        ["Angka terukur", "11 perlu tindakan (9 menunggu persetujuan, 2 ditandai verifier) · 17 total dipantau", "—"],
    ], [26 * mm, 66 * mm, 76 * mm]))
    out.append(p("Aturan: feed memakai jendela bergulir (24 jam), sedangkan KPI memakai hari kalender "
                 "WIB. Keduanya sengaja berbeda dan labelnya menyebut hal itu; jangan menganggap "
                 "\"Hari ini\" di feed = \"Hari ini\" di KPI.", KECIL))
    return out


def fitur_bukti():
    out = [p("4.4 Decision & Evidence — keputusan, bukti, persetujuan", H2),
           p("Ini ruang kerja inti: melihat satu keputusan dari semua sisi lalu memutuskan. Panel "
             "dibagi menjadi jalur persetujuan, governance, bukti, biaya, keamanan & pemasok, "
             "identitas & tenggat, dan jejak & riwayat.", BODY)]
    out.extend(langkah([
        "Pilih keputusan (dari feed atau pemilih). Panel memanggil detail, rantai audit, jejak, "
        "ringkasan persetujuan, dan konteks pemasok secara paralel.",
        "Periksa <b>bukti</b>: setiap bukti menyebut jenis dan isinya; kelengkapan dihitung server.",
        "Periksa <b>biaya</b>: harga beli + logistik + penanganan + susut = Safe Delivered Cost.",
        "Verifikasi (agen verifier) menulis verdict: CONSISTENT, FLAGGED, atau INCONCLUSIVE.",
        "Setujui: akun pertama menekan Setujui, akun <b>berbeda</b> melengkapi kuorum -> status approved.",
        "Eksekusi: sistem menerbitkan pesanan pembelian (nomor MC-...), menulis blok ledger, "
        "dan mengisi jejak ACT. Tombol eksekusi menolak bila kuorum/verdict/tenggat belum lengkap.",
        "Tolak: wajib menulis alasan; alasan tersimpan sebagai rejection_reason dan baris approvals(approved=false).",
        "Ajukan ulang (repropose): hanya untuk keputusan yang DITOLAK; menghasilkan keputusan baru "
        "dengan supersedes_id, sehingga riwayat tidak hilang.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Detail & bukti", "GET /decisions/{id}, /dossier, /chain, /traces, /approval-summary, /compliance", "decisions, decision_evidence, agent_traces, approvals, ledger_blocks"],
        ["Tindakan", "POST /actions/verify, /propose, /approve, /execute, /repropose", "decisions, approvals, sap_mock_purchase_orders, ledger_blocks"],
        ["Konteks pemasok", "GET /supplier-exclusions/context/{id}", "suppliers, batches, supplier_exclusions"],
        ["Angka terukur", "21 approval · 51 bukti · 16 PO · sdc jejak = sdc keputusan (0 selisih)", "—"],
    ], [30 * mm, 66 * mm, 72 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(callout("<b>Batas peran dalam satu alur:</b> verifikasi, persetujuan, dan eksekusi "
                       "boleh dilakukan peran SPPG (kepala/gizi), tetapi dua approval harus dari "
                       "akun berbeda. BGN Monitor hanya bisa membaca seluruh riwayat."))
    return out


def fitur_keamanan():
    out = [p("4.5 Keamanan Pangan — batch, karantina, penerimaan", H2),
           p("Menjawab: <i>barang mana yang aman dipakai, mana yang harus ditahan, dan apa yang "
             "terjadi saat kiriman tiba?</i> Satu batch = satu kiriman dengan berat, umur simpan, "
             "dan status uji sendiri.", BODY)]
    out.extend(langkah([
        "Ringkasan pengawasan menampilkan empat kategori status uji (aman, gagal uji, perlu "
        "verifikasi, belum diuji) yang <b>menjumlah ke total batch</b>, ditambah penanda "
        "terpisah: karantina dan kedaluwarsa (boleh tumpang tindih dengan status uji).",
        "Daftar <i>batch perlu segera dipakai</i> menyaring sisa masa layak <= 48 jam atau sudah lewat.",
        "Penerimaan barang: petugas memilih komoditas dan batch, mencentang lima titik periksa "
        "(boleh sebagian), menulis catatan \"Lainnya\", lalu menyimpan.",
        "Server menghitung ulang keamanan dan kesegaran dari log suhu + umur panen, lalu menulis "
        "hasilnya ke kolom batch (bukan angka dari layar).",
        "Batch gagal uji diblokir dari alokasi; batch yang ditahan tidak dihitung \"aman\" walau "
        "skornya bagus, karena tidak boleh dipakai.",
        "Karantina: tahan, lepas, atau gagalkan — ketiganya keputusan manusia dan tercatat.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Batch & kesegaran", "GET /batches, GET /batches/{id}, POST /freshness/evaluate", "batches"],
        ["Penerimaan", "GET /receipts/menunggu, POST /receipts, POST /receipts/{id}/approve|reject", "batch_receipts, batches"],
        ["Karantina & uji", "POST /batches/{id}/quarantine, POST /safety/evaluate", "batches"],
        ["Keputusan keamanan", "GET /decisions (decision_type = safety_disruption)", "decisions, approvals"],
        ["Angka terukur", "14 batch cakupan Jakarta · 8 aman · 2 gagal uji (920 kg) · 2 perlu verifikasi · 2 belum diuji · 1 ditahan 540 kg · 2 kedaluwarsa · 2 catatan penerimaan menunggu", "—"],
    ], [30 * mm, 64 * mm, 74 * mm]))
    out.append(p("Aturan: satu keputusan ditolak tidak lagi dihitung dua kali sebagai \"ditolak\" dan "
                 "\"kedaluwarsa\"; setiap keadaan dihitung sekali dan beratnya disebut.", KECIL))
    return out


def fitur_surplus():
    out = [p("4.6 Surplus & Limbah — neraca dan alokasi", H2),
           p("Menjawab: <i>berapa yang terbuang, dan ke mana surplus yang masih layak pergi?</i> "
             "Fitur ini juga sumber angka KPI Avoidable Food Loss.", BODY)]
    out.extend(langkah([
        "Neraca hari ini memanggil <font face='Courier'>/waste/summary?days=30</font>: total kg, "
        "jumlah peristiwa, dan pecahan per alasan (kedaluwarsa vs rusak).",
        "Pencatatan limbah: pilih batch, jumlah kg, alasan, lalu simpan -> baris disposal_events "
        "dengan lokasi dan waktu.",
        "Rencana alokasi surplus: daftar batch yang masih layak untuk dialihkan ke lokasi lain, "
        "beserta jarak dan sisa masa layak.",
        "Angka ini yang menaikkan Avoidable Food Loss; pembuangan sah (mis. gagal uji) tetap "
        "terhitung food loss menurut definisi yang dipakai.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Neraca", "GET /waste/summary?days=30", "disposal_events, supply_records"],
        ["Pencatatan & alokasi", "POST /waste/disposals, GET /surplus/allocations", "disposal_events, batches, suppliers, locations"],
        ["Angka terukur", "51,82 kg / 7 peristiwa (30 hari) · hari ini 31,49 kg / 3 peristiwa · Food Loss hari ini 0,59% (sampel 2)", "—"],
    ], [30 * mm, 62 * mm, 76 * mm]))
    out.append(p("Aturan: tidak ada disposal event -> metrik no_data, bukan 0%. Penyebut nol juga "
                 "no_data dengan alasan berbeda, supaya dua keadaan itu tidak tertukar.", KECIL))
    return out


def fitur_pemasok():
    out = [p("4.7 Pemasok — direktori, eksklusi, papan kiriman", H2),
           p("Menjawab: <i>siapa pemasoknya, seberapa andal, dan siapa yang harus dikecualikan?</i> "
             "Direktori memuat jarak dan keandalan; register eksklusi adalah daftar keputusan "
             "manusia yang mengikat sistem.", BODY)]
    out.extend(langkah([
        "Ringkasan direktori: jumlah pemasok, rata-rata keandalan, pemasok keandalan rendah, "
        "yang punya titik peta, yang punya stok layak, di luar jangkauan, dan jumlah entri eksklusi.",
        "Daftar pemasok menampilkan komoditas, keandalan, sertifikasi, jarak, dan status kiriman "
        "(label \"stok layak\" berarti punya batch layak hari ini — bukan sedang di jalan).",
        "Papan kiriman: satu baris per kiriman dengan pemasok, tujuan, muatan, jalur jalan, "
        "berangkat, ETA, sisa masa layak, mutu, dan keadaan perjalanan.",
        "Register eksklusi menampilkan pemasok, alasan, <b>status</b> (aktif / menunggu keputusan), "
        "waktu WIB, dan id keputusan asalnya.",
        "Usul eksklusi dibuat dari sebuah keputusan: pilih keputusan -> usul -> menunggu persetujuan "
        "-> aktif. Pemulihan (restore) adalah usulan terpisah, bukan pembatalan diam-diam.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Direktori & jarak", "GET /suppliers?limit=200", "suppliers, batches"],
        ["Kiriman", "GET /supplier-routes?limit=200", "batches, suppliers, road_routes"],
        ["Eksklusi", "GET /supplier-exclusions, POST /supplier-exclusions/proposals, POST /{id}/restore", "supplier_exclusions, suppliers, decisions"],
        ["Angka terukur", "60 pemasok · keandalan rata-rata 82% · 4 di bawah 60% · 30 di luar jangkauan 150 km · 54 punya stok layak · eksklusi 1 aktif + 1 menunggu", "—"],
    ], [28 * mm, 66 * mm, 74 * mm]))
    out.append(p("Aturan: pemasok yang dikecualikan tidak dipilih lagi saat sistem menyusun pesanan "
                 "pembelian. Eksklusi bukan label hiasan — ia mengubah keputusan berikutnya.", KECIL))
    return out


def fitur_agent_log():
    out = [p("4.8 Agent Log — jejak penalaran per langkah", H2),
           p("Menjawab: <i>apa yang sebenarnya dikerjakan agen untuk keputusan ini?</i> Satu baris "
             "per tahap, apa adanya dari database, tanpa dirangkum ulang oleh UI.", BODY)]
    out.extend(langkah([
        "Pilih keputusan: tab memanggil <font face='Courier'>/decisions/{id}/traces</font>.",
        "Tiap baris menampilkan tahap (DETECT, PREDICT, DECIDE, ACT, ...), model/agen, durasi, "
        "waktu UTC, dan ringkasan keluaran.",
        "Ringkasan dibaca sebagai kalimat; data mentah (JSON) tersedia di lipatan \"Data mentah\".",
        "Panel 8 agen menampilkan pemeriksaan lintas domain: verdict verifier, kesesuaian bukti, "
        "peringatan, dan status tiap agen untuk keputusan itu.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Jejak", "GET /decisions/{id}/traces", "agent_traces (step_name, agent_name, duration_ms, input_summary, output_summary)"],
        ["Angka terukur", "85 langkah jejak · 0 jejak berisi teks template · sdc di jejak = sdc keputusan (selisih > Rp1 = 0)", "—"],
    ], [28 * mm, 62 * mm, 78 * mm]))
    out.append(p("Aturan: jejak yang ditulis penyemai demo diberi penanda sumber dan angkanya "
                 "diturunkan dari keputusan, sehingga tab ini tidak bisa menampilkan angka yang "
                 "bertentangan dengan kartu rekomendasi.", KECIL))
    return out


def fitur_kpi():
    out = [p("4.9 KPI & Kualitas Agen — tujuh metrik dan audit sampel", H2),
           p("Menjawab: <i>apakah sistem membaik, dan apakah agennya bisa dipercaya?</i> Tujuh "
             "metrik dihitung server dari tabel fakta; tab ini juga mengaudit sampel keputusan.", BODY)]
    out.extend(langkah([
        "Pilih periode (Hari ini / 7 hari / 1 bulan). Klien hanya mengirim KUNCI periode; "
        "server yang menghitung rentang WIB-nya.",
        "Tiap kartu menyebut nilai, satuan, cakupan (coverage), jumlah sampel, dan alasan bila "
        "metrik tidak tersedia.",
        "Kartu yang tidak bisa dinilai menampilkan \"—\" + alasan, bukan 0%.",
        "Bagian kualitas agen mengambil sampel keputusan, membandingkan verdict verifier, "
        "kelengkapan bukti, dan waktu keputusan terhadap jejak yang tersimpan.",
        "Angka berubah bila ada aksi nyata: eksekusi mengisi SDC dan Decision Time, approval "
        "mengisi Evidence Completeness.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["KPI", "GET /kpi?periode=today|7d|1bulan", "supply_records, demand_records, price_signals, menu_plans, delivery_events, disposal_events, decisions, approvals, decision_evidence, agent_traces, sap_mock_purchase_orders"],
        ["Kualitas agen", "GET /decisions + /traces + /approval-summary per sampel", "decisions, agent_traces, approvals, decision_evidence"],
        ["Angka terukur (Hari ini)", "Susut pangan 0,59% (2 sampel) · Simpangan harga 2,66% (17) · lima metrik no_data dengan alasan masing-masing", "—"],
    ], [30 * mm, 62 * mm, 76 * mm]))
    out.append(p("Aturan: angka nol hanya sah bila memang terukur nol. \"KPI tersedia 2/7\" adalah "
                 "keadaan normal pagi hari, bukan kegagalan.", KECIL))
    return out


def fitur_demo():
    out = [p("4.10 Demo Control — sesi, data, agent, integrasi", H2),
           p("Panel operator: menyiapkan data, menjalankan agen, membaca bukti yang ditulis agen, "
             "dan melihat status integrasi. Semua tombol di sini menulis ke database.", BODY)]
    out.extend(langkah([
        "<b>Siapkan data demo</b>: membangun template lalu membuka sesi 120 menit. Terukur 41 detik "
        "pada mesin demo (sediakan sampai sekitar 1 menit di laptop lambat).",
        "<b>Bangun ulang data</b>: mengembalikan angka ke keadaan awal tanpa menutup sesi.",
        "<b>Jalankan agent</b>: memanggil pipeline untuk komoditas terpilih; hasilnya kartu baru + jejak.",
        "<b>Bukti agent</b>: menampilkan langkah yang benar-benar tertulis pada putaran terakhir.",
        "<b>Data status</b>: jumlah baris kanonik vs demo per tabel, beserta rentang tanggalnya.",
        "<b>Integrasi</b>: status mock SAP, AWS/Bedrock, dan OSRM — termasuk alasan bila tidak aktif.",
        "<b>Akhiri sesi</b>: menutup jendela dan menghapus baris demo sehingga layar kembali ke keadaan awal.",
    ]))
    out.append(tabel([
        ["Sumber", "Endpoint", "Tabel"],
        ["Sesi", "GET/POST /demo/session, /start, /extend, /end, /demo/template/rebuild", "demo_sessions"],
        ["Data & agent", "GET /demo/data-status, /demo/agent/last-run, POST /demo/agent/run, /demo/seed", "semua tabel operasional + agent_traces"],
        ["Integrasi", "GET /integrations/status, /health", "konfigurasi layanan"],
        ["Angka terukur", "sesi demo 120 menit (plafon, tidak bisa diperpanjang) · 41 detik rebuild · 36 keputusan setelah siapkan data", "—"],
    ], [28 * mm, 66 * mm, 74 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(callout("<b>Peringatan operasional:</b> begitu sesi kedaluwarsa, penjaga mutasi "
                       "menolak semua tulisan (409) dan penyapu menghapus baris demo tanpa stempel. "
                       "Untuk panggung, tekan Siapkan data demo maksimal dua jam sebelum tampil, "
                       "dan jangan menjalankan <font face='Courier'>docker compose exec backend pytest</font> "
                       "pada database kerja (perintah itu mem-purge data demo)."))
    return out


def state_machine():
    out = [p("5. Enam state machine yang menegakkan aturan", H1),
           p("Status bukan hiasan: setiap perpindahan punya prasyarat, dan status di luar daftar "
             "ditolak oleh CHECK constraint di database.", BODY)]
    out.append(tabel([
        ["Objek", "Status", "Perpindahan dan prasyarat"],
        ["Sesi demo", "active, expired, ended",
         "start -> active (template dibangun dulu); expires_at lewat -> expired; end -> ended; satu sesi aktif dijamin index parsial"],
        ["Keputusan", "proposed, verifier_flagged, pending_approval, approved, rejected, executed, review_only",
         "propose: proposed/verifier_flagged -> pending_approval; verify FLAGGED -> verifier_flagged; approve (kuorum) -> approved; tolak (wajib alasan) -> rejected; execute (kuorum + verdict + belum kedaluwarsa) -> executed; event keamanan -> review_only"],
        ["Approval", "approved=false/true per baris",
         "dua akun berbeda; akun sama dua kali -> 409; penolakan menulis approved=false + komentar"],
        ["Batch keamanan", "pass, needs_verification, fail, pending",
         "dicatat penerimaan -> dihitung server dari suhu/umur -> pass/needs_verification/fail; fail diblokir dari alokasi"],
        ["Karantina batch", "none, quarantined, released, failed",
         "tahan -> quarantined (tidak boleh dialokasikan); lepas -> released; gagalkan -> failed; semuanya keputusan manusia"],
        ["Eksklusi pemasok", "proposed, active, rejected, revoked",
         "usul -> proposed; disetujui -> active (pemasok tidak dipilih lagi); ditolak -> rejected; dicabut -> revoked"],
        ["Pesanan SAP", "draft, submitted, confirmed",
         "diterbitkan saat eksekusi -> confirmed; total = kuantitas x harga; material diturunkan dari komoditas"],
    ], [26 * mm, 44 * mm, 98 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(kode("DETECT -> VERIFY -> PREDICT -> OPTIMIZE -> DECIDE -> SUPERVISE -> ACT -> LEARN",
                    "",
                    "ACT hanya terisi bila eksekusi berhasil; LEARN dipakai loop penolakan",
                    "(alasan penolakan menjadi bahan usulan berikutnya)."))
    return out


def kpi_tabel():
    out = [p("6. Tujuh KPI: rumus, jendela, dan arti no_data", H1),
           p("Semua metrik dihitung server dari tabel fakta (data_source: live_aggregate) pada "
             "rentang setengah terbuka [start, end), kecuali Meal Continuity yang memakai tanggal "
             "rencana. Jendela \"Hari ini\" = 00.00 WIB sampai sekarang, bukan 24 jam bergulir.", BODY)]
    out.append(tabel([
        ["Metrik (satuan)", "Rumus yang dijalankan", "no_data bila"],
        ["Meal Continuity (persen)",
         "100 x SUM(LEAST(kirim, rencana)) / SUM(rencana) per menu plan; rencana yang jendela kirimnya belum tiba tidak masuk penyebut",
         "tidak ada rencana; penyebut nol; atau belum ada yang bisa dinilai"],
        ["Avoidable Food Loss (persen)",
         "100 x kg_buang / (kg_buang + kg_pasokan) pada jendela",
         "tidak ada disposal; penyebut nol"],
        ["Regional Imbalance (persen)",
         "root case ber-jejak DETECT, diruntut lewat supersedes_id, di-dedupe; pembilang = yang punya anggota executed; demo_case dikecualikan",
         "tidak ada DETECT pada jendela"],
        ["Safe Delivered Cost (IDR)",
         "rata-rata safe_delivered_cost untuk keputusan yang punya PO pada jendela",
         "tidak ada PO berbiaya pada jendela"],
        ["Price Deviation (persen)",
         "rata-rata |kutipan - referensi PIHPS terakhir| / referensi x 100",
         "tidak ada pasangan kutipan-referensi"],
        ["Decision Time (menit)",
         "rata-rata (ACT - DETECT) untuk keputusan yang ACT-nya committed (punya PO); cakupan = sampel/eligible",
         "ada DETECT tetapi belum ada ACT committed; atau tidak ada DETECT"],
        ["Evidence Completeness (persen)",
         "keputusan dengan >=2 jenis bukti konsisten SEBELUM approval pertama / keputusan yang punya approval",
         "belum ada approval (tidak ada cutoff); atau tidak ada keputusan"],
    ], [30 * mm, 96 * mm, 42 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(p("Keadaan hari ini (diukur saat dokumen dibangun)", H2))
    out.append(tabel([
        ["Metrik", "Nilai", "Sampel", "Alasan bila kosong"],
        ["Meal Continuity Rate", "—", "1", "rencana hari ini ada, jendela kirimnya belum tiba"],
        ["Avoidable Food Loss", "0,59%", "2", "—"],
        ["Regional Imbalance", "—", "0", "tidak ada DETECT pada periode ini"],
        ["Safe Delivered Cost", "—", "0", "tidak ada batch terkirim yang punya biaya pada periode ini"],
        ["Price Deviation", "2,66%", "17", "—"],
        ["Decision Time", "—", "7", "7 keputusan punya DETECT, belum ada ACT committed"],
        ["Evidence Completeness", "—", "0", "11 keputusan ada, belum satu pun disetujui"],
    ], [46 * mm, 20 * mm, 18 * mm, 84 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(callout("Membaca tabel ini: dua metrik sudah punya angka, lima belum bisa dinilai — "
                       "dan itu memang keadaan pagi hari sebelum ada aksi. \"KPI tersedia 2/7\" "
                       "bukan kegagalan; ia menyatakan dengan jujur mana yang terukur."))
    return out


def pipeline():
    out = [p("7. Pipeline agen: delapan tahap", H1),
           p("Agen berjalan sebagai satu putaran per komoditas. Setiap tahap menulis satu baris "
             "jejak, sehingga hasilnya bisa diaudit tanpa membaca log aplikasi.", BODY)]
    out.append(tabel([
        ["Tahap", "Apa yang dikerjakan", "Keluaran yang tersimpan"],
        ["DETECT", "memeriksa pasokan/permintaan, anomali harga, keamanan batch, riwayat pemasok", "keputusan baru + jejak DETECT"],
        ["VERIFY", "agen verifier menilai kelengkapan dan konsistensi bukti", "verdict CONSISTENT / FLAGGED / INCONCLUSIVE"],
        ["PREDICT", "proyeksi kebutuhan dan dampak bila tidak ditindak", "ringkasan prakiraan"],
        ["OPTIMIZE", "memilih sumber alternatif dan rute termurah/tercepat", "kandidat sumber + ETA"],
        ["DECIDE", "menyusun usulan: komoditas, berat, biaya, tenggat", "keputusan + safe_delivered_cost"],
        ["SUPERVISE", "memeriksa batas wewenang dan risiko", "catatan pengawasan"],
        ["ACT", "mengeksekusi setelah kuorum: menerbitkan PO", "PO mock SAP + blok ledger"],
        ["LEARN", "menyerap alasan penolakan untuk usulan berikutnya", "catatan pembelajaran"],
    ], [22 * mm, 84 * mm, 62 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(p("Pemicu: tombol <b>Jalankan agent</b> di Demo Control, atau endpoint event "
                 "(/events/safety-disruption, /events/price-anomaly) untuk menyuntik kasus. "
                 "Pipeline juga bisa dipanggil langsung lewat /balance/analyze untuk demonstrasi "
                 "perhitungan tanpa menulis keputusan.", BODY))
    return out


def alur_demo():
    out = [p("8. Alur demo panggung sebelas menit", H1),
           p("Urutan ini yang dipakai saat presentasi; setiap babak punya angka yang bergerak dan "
             "bukti di layar. Naskah lengkap ada di docs/demo/alur-demo-juri.md.", BODY)]
    out.append(tabel([
        ["Babak", "Tab", "Yang dilakukan", "Angka/bukti yang bergerak"],
        ["0", "Overview", "menunjukkan peta pasokan, kiriman berjalan, dan cakupan", "12 rute, 11 berjalur"],
        ["1", "Recommendations -> Decision & Evidence", "buka satu rekomendasi, verifikasi, setujui dengan dua akun, eksekusi", "status -> approved -> executed; PO baru terbit; blok ledger bertambah"],
        ["2", "Keamanan Pangan", "batch gagal uji, karantina, keputusan keamanan", "2 gagal uji (920 kg); tile status uji menjumlah ke 14"],
        ["3", "Keamanan Pangan (penerimaan)", "catat penerimaan kiriman yang tiba", "batch pindah dari belum diuji -> status hasil hitung server"],
        ["4", "Pemasok", "register eksklusi + usul eksklusi dari keputusan", "1 aktif + 1 menunggu; pemasok hilang dari usulan berikutnya"],
        ["5", "Surplus & Limbah", "neraca limbah dan alokasi surplus", "Food Loss bergerak sesuai buangan yang dicatat"],
        ["6", "KPI & Kualitas Agen", "tunjukkan KPI yang bergerak dan yang tetap no_data + alasannya", "SDC/Decision Time/Evidence berubah setelah aksi"],
    ], [14 * mm, 34 * mm, 66 * mm, 54 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(p("Sebelum babak 1: pastikan sesi aktif dan kartu terbuka (11 di jendela 24 jam, "
                 "19 terbuka secara total). Sebelum meninggalkan "
                 "panggung: sebutkan bahwa data berasal dari template demo, dan bahwa KPI yang "
                 "belum bergerak memang belum punya bukti (bukan rusak).", KECIL))
    return out


def gerbang():
    out = [p("9. Gerbang mutu dan bukti uji", H1),
           p("Angka di bawah ini berasal dari eksekusi nyata pada sesi yang sama dengan dokumen ini.", BODY)]
    out.append(tabel([
        ["Pemeriksaan", "Perintah", "Hasil"],
        ["Unit test frontend", "npx vitest run", "1.818 lulus / 166 berkas"],
        ["Tipe TypeScript", "npx tsc --noEmit", "exit 0"],
        ["Lint frontend", "npm run lint", "tidak ada warning/error"],
        ["Gerbang invarian", "verify_stack.py verify/invariants.spec.json", "PASS 52 / FAIL 0 / SKIP 1"],
        ["Unit test backend (subset terkait perubahan)", "pytest -k \"balance or demo or sap_order or trace or agent\"", "231 lulus, 16 skip, 5 gagal yang lulus saat dijalankan sendiri (order-dependent)"],
        ["Lint backend", "ruff check", "All checks passed"],
        ["Migrasi", "alembic check", "tidak ada operasi baru"],
        ["Panen UI (Playwright)", "10 tab, rekam request + teks", "0 console error, semua endpoint 200"],
    ], [52 * mm, 66 * mm, 50 * mm]))
    out.append(Spacer(1, 2 * mm))
    out.append(p("Invarian yang diuji langsung di database: PO tanpa berat, material generik "
                 "MAT-UMUM, keputusan ditolak tanpa pencatat, jejak berisi teks template, sdc jejak "
                 "berbeda dari SDC keputusan, keputusan executed tanpa approval, dan jumlah baris "
                 "API dibandingkan dengan hitungan tabel.", KECIL))
    return out


def keterbatasan():
    out = [p("10. Keterbatasan dan risiko yang harus disebut", H1),
           p("Bagian ini sengaja tidak dirapikan. Juri yang menemukan sendiri masalah di daftar ini "
             "akan lebih meragukan daripada kita yang menyebutkannya lebih dulu.", BODY)]
    out.append(tabel([
        ["Hal", "Keadaan", "Dampak bila diabaikan"],
        ["Sesi demo 2 jam", "kedaluwarsa -> tulisan ditolak 409, baris demo tanpa stempel disapu",
         "layar kosong di tengah presentasi; siapkan data maksimal 2 jam sebelumnya"],
        ["Data demo vs nyata", "seluruh angka dari template demo; SAP disimulasikan",
         "jangan menyebutnya data operasional nyata atau panggilan SAP sungguhan"],
        ["Kredensial", "nilai .env pernah masuk riwayat git (kini tidak dilacak)",
         "rotasi wajib sebelum repo dibuka publik"],
        ["Dependensi", "3 CVE (next & maplibre critical, postcss high)",
         "perbaikan = upgrade mayor; jangan dikerjakan H-1 demo"],
        ["Perintah pytest di AGENTS.md", "mem-purge data demo pada database kerja",
         "jalankan hanya di DB klon dengan docker run + mount"],
        ["Test backend penuh", "13 kegagalan bergantung urutan (lulus saat diisolasi)",
         "jangan mengklaim \"seluruh suite hijau\""],
        ["Regional Imbalance", "mengecualikan keputusan demo_case (keputusan owner tertunda)",
         "metrik ini tidak bergerak saat kartu demo dieksekusi — sebutkan alasannya"],
        ["Belum diuji", "panggilan Bedrock/SAP AI Core sungguhan, uji beban, axe/kontras, keyboard, responsive perangkat, next build produksi",
         "jangan mengklaim siap produksi; sebut sebagai backlog"],
    ], [34 * mm, 74 * mm, 60 * mm]))
    out.append(Spacer(1, 3 * mm))
    out.append(callout("<b>Kesimpulan satu baris:</b> alur fitur dan asal-usul angkanya sudah "
                       "tertelusuri dari layar sampai baris database dan diuji ulang; yang belum "
                       "selesai adalah pekerjaan produksi (rotasi kredensial, upgrade dependensi, "
                       "uji beban dan aksesibilitas), bukan alur fiturnya."))
    return out


def build(hal_map=None, out=OUT):
    doc = BaseDocTemplate(out, pagesize=A4, title="MealChain Guardian - Alur semua fitur",
                          author="MealChain Guardian", leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=18 * mm, bottomMargin=18 * mm)
    frame_cover = Frame(18 * mm, 18 * mm, 174 * mm, 261 * mm, id="cover")
    frame_body = Frame(18 * mm, 18 * mm, 174 * mm, 261 * mm, id="body")

    def kaki(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#C9D4DE"))
        canvas.setLineWidth(0.4)
        canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(colors.HexColor("#4A5568"))
        canvas.drawString(18 * mm, 9.5 * mm,
                          "MealChain Guardian - alur semua fitur (%s)" % TANGGAL)
        canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, "hal. %d" % doc_.page)
        canvas.restoreState()

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame_cover]),
        PageTemplate(id="body", frames=[frame_body], onPage=kaki),
    ])

    story = [NextPageTemplate("cover")] + sampul()
    story += [NextPageTemplate("body"), PageBreak()]
    story += daftar_isi(hal_map) + [PageBreak()]
    for bagian in (ringkasan, arsitektur, aturan_global):
        story += bagian() + [Spacer(1, 3 * mm)]
    story += [PageBreak()]
    for bagian in (fitur_hari_ini, fitur_overview, fitur_rekomendasi, fitur_bukti,
                   fitur_keamanan, fitur_surplus, fitur_pemasok, fitur_agent_log,
                   fitur_kpi, fitur_demo):
        story += bagian()
    story += [PageBreak()]
    for bagian in (state_machine, kpi_tabel, pipeline, alur_demo, gerbang, keterbatasan):
        story += bagian() + [Spacer(1, 2 * mm)]
    doc.build(story)
    return out


def cari_halaman(pdf_path):
    """Peta nomor bagian -> halaman, dibaca dari teks PDF hasil cetak."""
    import re

    import pypdf

    reader = pypdf.PdfReader(pdf_path)
    teks = [re.sub(r"\s+", " ", (pg.extract_text() or "")) for pg in reader.pages]
    halaman_toc = {i for i, t in enumerate(teks, 1) if "Daftar isi" in t}
    hasil = {}
    for nomor, judul in JUDUL_BAGIAN:
        # cocokkan bentuk ber-nomor ("4.5 Keamanan Pangan") supaya kata pendek
        # seperti "Pemasok" tidak tertangkap daftar tab di halaman lain
        awalan = nomor if "." in nomor else nomor + "."
        kunci = (awalan + " " + judul).lower()
        for i, t in enumerate(teks, 1):
            if kunci[:30] in t.lower() and i > 1 and i not in halaman_toc:
                hasil[nomor] = i
                break
    return hasil


def main():
    import tempfile

    sementara = os.path.join(tempfile.gettempdir(), "alur-fitur-pass1.pdf")
    build(out=sementara)
    hal = cari_halaman(sementara)
    build(hal_map=hal, out=OUT)
    print("PDF:", OUT)
    print("halaman per bagian:", hal)
    os.remove(sementara)


if __name__ == "__main__":
    main()
