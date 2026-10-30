"""A2A server MealChain Guardian — jembatan BACA-SAJA ke SAP Joule (Bring Your Own Agent).

Alur (pola dari tutorial `joule_a2a/` repo hackathon SAP-AWS, Apache-2.0 — lihat `NOTICE`):

    Joule chat → scenario → function `agent-request` → BTP Destination
      → app ini (Cloud Foundry) → endpoint baca backend MealChain v0.2.0 → markdown → artefak A2A → Joule

Kenapa hanya BACA dan kenapa angka tidak dihitung di sini:

* `Rules.md` §1.1 — angka safety-critical keluar dari modul deterministik backend, bukan dari
  model bahasa. Karena itu modul ini tidak menjumlahkan apa pun; `report.py` hanya memformat.
* `Rules.md` §1.2 — tidak ada auto-execute. Joule boleh MELIHAT antrean usulan, tetapi
  persetujuan tetap di UI MealChain memakai token approver sendiri.
* Joule menunggu sinkron maksimum 60 detik (troubleshooting tutorial latihan 03). Karena itu
  setiap skill memanggil endpoint baca yang cepat, tanpa rantai model.

Pemilihan skill DETERMINISTIK (bukan LLM):

1. pesan berbentuk JSON dengan field `skill` — kontrak eksplisit, dipakai test & A2A Editor; atau
2. nomor PO di dalam teks (`MC-661695B2C685`) → skill purchase order, sekalian membawa nomornya;
3. kata kunci pada teks pesan, dalam urutan prioritas tetap (lihat `_KEYWORDS`):
   `kpi`/`indikator`/`kinerja` → KPI; `bukti`/`jejak`/`audit`/`dossier`/`tanda tangan` → bukti
   keputusan; `approval`/`persetujuan`/`usulan`/`antrean` → antrean usulan; `eksklusi`/`rute`/
   `jarak` → risiko pemasok; `harga`/`kuotasi` → harga; `kebutuhan`/`prakiraan` → kebutuhan &
   prakiraan; `limbah`/`kehilangan`/`susut` → kehilangan pangan; `pemasok`/`supplier`/`direktori`
   → direktori pemasok; `integrasi`/`ledger`/`status sistem` → status sistem; sisanya → situasi
   pasokan.

Urutan itu bukan hiasan: PO diperiksa SEBELUM antrean ("PO mana yang sudah disetujui?" memuat
`setuju` milik antrean), bukti SEBELUM antrean ("bukti keputusan X" memuat `keputusan`), dan
antrean SEBELUM risiko pemasok ("usulan eksklusi pemasok" adalah keputusan, bukan daftar eksklusi).

Batas yang jujur: routing kata kunci bisa salah tebak kalau kalimat pengguna ambigu. Perbaikan
yang lebih kuat (satu BTP Destination + satu agent card per skill) sengaja belum diambil supaya
tidak menambah permukaan konfigurasi sebelum dipakai di panggung.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol, Sequence

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps.jsonrpc import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore


# Logger uvicorn: satu-satunya yang sudah terkonfigurasi saat app dijalankan
# (`uvicorn server:app`), sehingga baris ini muncul di `cf logs` tanpa setup tambahan.
_log = logging.getLogger("uvicorn.error")
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import report
from mealchain_client import (
    EVIDENCE_LIMIT,
    KPI_DEFAULT_DAYS,
    PAIR_LIMIT,
    MealchainClient,
    MealchainRejected,
    MealchainUnavailable,
)

_BULAN = (
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

ARTIFACT_ID = "mealchain_report"
ARTIFACT_NAME = "mealchain_report"
DEFAULT_PORT = "8080"

SKILL_SUPPLY = "supply_situation"
SKILL_KPI = "kpi_snapshot"
SKILL_QUEUE = "approval_queue"
SKILL_PO = "purchase_order"
SKILL_DIRECTORY = "supplier_directory"
SKILL_PRICE = "price_intelligence"
SKILL_DEMAND = "demand_forecast"
SKILL_LOSS = "food_loss"
SKILL_SUPPLIER_RISK = "supplier_risk"
SKILL_RECEIPTS = "receipts_queue"
SKILL_QUARANTINE = "quarantine_status"
SKILL_BATCH = "batch_detail"
SKILL_GAP = "unsupported_domain"
SKILL_EVIDENCE = "decision_evidence"
SKILL_SYSTEM = "system_status"
SKILL_SURPLUS = "surplus_region"
SKILLS = (
    SKILL_SUPPLY,
    SKILL_KPI,
    SKILL_QUEUE,
    SKILL_PO,
    SKILL_DIRECTORY,
    SKILL_PRICE,
    SKILL_DEMAND,
    SKILL_LOSS,
    SKILL_SUPPLIER_RISK,
    SKILL_RECEIPTS,
    SKILL_QUARANTINE,
    SKILL_BATCH,
    SKILL_EVIDENCE,
    SKILL_SYSTEM,
    SKILL_SURPLUS,
)

#: Berapa komoditas yang rencana alihnya diperiksa per jawaban. Satu komoditas = satu
#: panggilan HTTP; Joule menunggu sinkron maksimal 60 detik, jadi sisanya disebut di laporan.
SURPLUS_COMMODITY_LIMIT = 4

#: Urutan di tuple ini = urutan pemeriksaan (prioritas), kecuali PO yang punya pemeriksa sendiri
#: dan selalu diperiksa setelah KPI. Alasannya tertulis di docstring modul; ringkasnya:
#: kata kunci yang bertumpang-tindih HARUS diperiksa lebih dulu atau ia tidak pernah menang.
_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (SKILL_KPI, ("kpi", "indikator", "kinerja", "metrik", "performance")),
    # Bukti sebelum antrean: "bukti keputusan X" memuat `keputusan` milik antrean.
    (
        SKILL_EVIDENCE,
        (
            "bukti",
            "evidence",
            "jejak",
            "trace",
            "audit",
            "dossier",
            "kepatuhan",
            "compliance",
            "tanda tangan",
            "signature",
            "sidik",
            "rantai keputusan",
            # "siapa yang menyetujui" → bukti (punya daftar approval + nama), bukan antrean.
            "menyetujui",
            "disetujui oleh",
            "penyetuju",
            "approver",
        ),
    ),
    # Penerimaan barang SEBELUM antrean keputusan: "penerimaan barang menunggu
    # persetujuan" memuat kata `persetujuan` milik antrean, padahal domainnya
    # `batch_receipts` (audit 21 Okt 2026: jawabannya dulu salah domain).
    (
        SKILL_RECEIPTS,
        (
            "penerimaan",
            "receipt",
            "receiving",
            "barang datang",
            "goods receipt",
            "belum diperiksa",
            "pemeriksaan barang",
        ),
    ),
    # Karantina punya kolom sendiri (`quarantine_status`), bukan status pasokan.
    (SKILL_QUARANTINE, ("karantina", "quarantine", "dikarantina")),
    # Rincian SATU batch: keamanan tersimpan vs hasil evaluasi, kebijakan suhu komoditas,
    # dan kecukupan bukti (`GET /batches/{id}`). Ditaruh sesudah karantina dan penerimaan
    # karena pertanyaan "penerimaan barang batch X" adalah antrean penerimaan, bukan rincian
    # keamanan. Kata `batch`/`bacth` saja tidak cukup: bentuk pertanyaannya bisa "batch mana
    # yang suhunya menyimpang", dan itu memang domain ini.
    (
        SKILL_BATCH,
        (
            "batch",
            "bacth",
            "batches",
            "suhu",
            "temperature",
            "kedaluwarsa",
            "expired",
            "expiry",
            "masa layak",
            "layak pakai",
            "excursion",
            "penyimpangan suhu",
        ),
    ),
    (
        SKILL_QUEUE,
        ("approval", "approve", "persetujuan", "setuju", "usulan", "keputusan", "antrean", "queue"),
    ),
    # Risiko pemasok sebelum direktori: "pemasok yang dikecualikan" memuat `pemasok` milik direktori.
    (
        SKILL_SUPPLIER_RISK,
        (
            "eksklusi",
            "exclusion",
            "dikecualikan",
            "blacklist",
            "rute",
            "route",
            "jarak",
            # "pemasok mana yang berisiko?" dulu jatuh ke direktori karena hanya kata
            # `pemasok` yang dikenali — jawabannya daftar 61 pemasok, bukan risiko.
            "berisiko",
            "risiko",
            "risk",
            "rawan",
        ),
    ),
    # Harga sebelum direktori: "harga dari pemasok" adalah pertanyaan harga.
    (SKILL_PRICE, ("harga", "price", "kuotasi", "quote", "tarif")),
    # Surplus ANTAR WILAYAH (bukan saldo per SPPG). Semua katanya berfrasa: kata `surplus`
    # sendirian SENGAJA tidak dipakai, sebab "pasokan beras masih surplus?" adalah laporan
    # pasokan (default) dan sudah benar — menambah `surplus` telanjang akan merebutnya.
    # Ditaruh sebelum blok domain-tak-tersedia: "surplus antar wilayah" tidak memuat
    # kata domain lain, tetapi blok itu memuat `pengiriman`/`stok`.
    (
        SKILL_SURPLUS,
        (
            "surplus wilayah",
            "surplus daerah",
            "surplus antar",
            "surplus lintas",
            "surplus per wilayah",
            "surplus per daerah",
            "sebaran surplus",
            "peta surplus",
            "alih surplus",
            "alokasi surplus",
            "rencana alih",
            "realokasi",
            "redistribusi",
        ),
    ),
    # Domain yang backend-nya BELUM punya endpoint baca. Dijawab jujur sebagai
    # "belum tersedia" — sebelumnya pertanyaan ini dijawab data pasokan, yang
    # tampak benar padahal menjawab hal lain (audit 21 Okt 2026).
    # Ditaruh SESUDAH risiko pemasok: "pemasok berisiko karena jarak pengiriman"
    # memuat `pengiriman` dan dulu dicuri blok ini (audit 26 Okt 2026).
    (
        SKILL_GAP,
        (
            "pengiriman",
            "delivery",
            "surat jalan",
            "stok material",
            "material stock",
            "stok sap",
            "inventaris sap",
        ),
    ),
    (
        SKILL_DEMAND,
        ("kebutuhan", "demand", "prakiraan", "forecast", "proyeksi", "ramalan", "perlu dipenuhi"),
    ),
    (SKILL_LOSS, ("limbah", "waste", "kehilangan", "susut", "terbuang", "disposal", "pemborosan")),
    (SKILL_DIRECTORY, ("pemasok", "supplier", "direktori", "vendor")),
    (
        SKILL_SYSTEM,
        (
            "integrasi",
            "integration",
            "ledger",
            "status sistem",
            "status koneksi",
            "kesehatan sistem",
            "kesiapan sistem",
            "semua data",
            "terakhir diperbarui",
            "diperbarui",
            "sumber data",
            "sumbernya",
            "kesegaran data",
            "data terbaru",
            "health",
        ),
    ),
)

#: Pertanyaan bantuan/sapaan: dijawab daftar kemampuan, bukan tabel 40 baris.
_HELP_WORDS: tuple[str, ...] = (
    "halo",
    "hallo",
    "hai",
    "hello",
    "selamat pagi",
    "selamat siang",
    "selamat malam",
    "bisa bantu",
    "bisa apa",
    "bisa melakukan apa",
    "siapa kamu",
    "kamu siapa",
    "apa yang bisa",
    "apa saja yang bisa",
    "bantuan",
    "help",
)

#: Frasa yang tetap dijawab daftar kemampuan walau ada kata domain — pengguna memang
#: bertanya soal kemampuan Joule, bukan soal datanya.
_HELP_TEGAS: tuple[str, ...] = (
    "bisa bantu apa",
    "bisa membantu apa",
    "bisa melakukan apa",
    "siapa kamu",
    "kamu siapa",
    "kemampuan anda",
    "kemampuanmu",
    "fitur apa",
    "menu bantuan",
)

#: Kata/frasa yang menandakan pesan benar-benar menanyakan DATA. Sapaan di depan pesan
#: tidak boleh membatalkan pertanyaan data: "Halo, kondisi pasokan beras?" tetap pasokan.
_KATA_DOMAIN: tuple[str, ...] = tuple(
    sorted({kata for _, kata_kunci in _KEYWORDS for kata in kata_kunci})
) + (
    "pasokan",
    "stok",
    "persediaan",
    "komoditas",
    "sppg",
    "batch",
    "dapur",
)


def _ada_kata_domain(teks_kecil: str) -> bool:
    return any(kata in teks_kecil for kata in _KATA_DOMAIN)

#: Pertanyaan tentang batch yang harus dibuang/kedaluwarsa. Backend tidak punya endpoint
#: "pembuangan", jadi yang disajikan kandidat tinjauan (keamanan GAGAL / dikarantina) dan
#: keputusannya tetap milik manusia.
_BUANG_WORDS: tuple[str, ...] = (
    "dibuang",
    "buang",
    "kedaluwarsa",
    "kadaluarsa",
    "expired",
    "basi",
    "tidak layak",
    "rusak",
)

#: Nomor PO kanonik: `MC-<12 hex>` (satu pembentuk, `backend/app/core/po_number`). Dibaca
#: lebih dulu daripada kata kunci mana pun karena bentuknya tidak ambigu.
_PO_NUMBER = re.compile(r"\b(MC-[0-9A-Fa-f]{6,})\b")

# Perintah TULIS (Fase 12): jembatan ini hanya baca, jadi permintaan menyetujui/
# menolak/mengeksekusi harus dijawab dengan penolakan + arah ke cockpit — bukan
# dijawab tabel PO (yang membuat penanya mengira permintaannya diproses).
# Dianker di AWAL pesan supaya pertanyaan seperti "PO mana yang sudah disetujui?"
# atau "status eksekusi PO …" tetap jatuh ke skill baca yang benar.
_WRITE_INTENT = re.compile(
    r"^\s*(tolong\s+|mohon\s+|please\s+|silakan\s+|bisa\s+)?"
    r"(setujui|menyetujui|approve|tolak|menolak|reject|"
    r"eksekusi|mengeksekusi|execute|batalkan|cancel|sahkan)\b",
    re.IGNORECASE,
)

#: Nomor PO gaya SAP (hanya angka, mis. `4500000001`). Hanya diakui kalau menempel pada kata
#: `PO`, supaya nominal rupiah 10 digit tidak diperlakukan sebagai nomor dokumen.
_PO_ANGKA = re.compile(
    r"(?<![A-Za-z])(?:po|purchase[\s-]?orders?|pesanan[\s-]+pembelian)"
    r"\s*(?:nomor|no\.?|#|:)?\s*([0-9]{8,12})(?![0-9])",
    re.IGNORECASE,
)

#: Sebutan PO tanpa nomor. Batas kata dipakai supaya `po` di dalam "produk"/"pasokan" tidak
#: ikut tertangkap — routing yang salah tebak lebih mahal daripada tidak menangkap.
_PO_WORD = re.compile(
    r"(?<![A-Za-z])(po|purchase[\s-]?orders?|pesanan[\s-]+pembelian)(?![A-Za-z])", re.IGNORECASE
)

#: Id keputusan / batch berbentuk UUID. Dipakai untuk membuka bukti satu keputusan
#: (`/decisions/{id}/compliance`) atau penerimaan satu batch (`/receipts?batch_id=`).
_UUID = re.compile(
    r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b"
)
#: Rujukan pendek yang tampil di tabel chat (8 karakter pertama sebuah id). Tanpa ini,
#: pengguna harus menyalin 36 karakter dari layar untuk membuka satu keputusan/batch.
_ID_PENDEK = re.compile(r"\b([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){0,4}|[0-9a-fA-F]{9,36})\b")


def _nomor_rujukan(pesan: str) -> re.Match[str] | None:
    """Id utuh kalau ada, kalau tidak potongan 8+ karakter yang tampil di tabel."""
    return _UUID.search(pesan) or _ID_PENDEK.search(pesan)

#: Kata yang menandakan permintaan PEMBUANGAN/pengalihan limbah. Pertanyaan "batch mana yang
#: harus dibuang?" memuat kata `batch` milik skill rincian batch, padahal domainnya
#: kehilangan pangan (`batch_disposal_report`). Tanpa penjaga ini, rincian satu batch
#: mencuri pertanyaan pembuangan (tes lama `test_batch_harus_dibuang_…` menangkapnya).
_DISPOSAL_WORDS = ("dibuang", "pembuangan", "buang", "disposal", "limbah", "waste")

#: Kata yang menandakan permintaan PENERIMAAN BARANG untuk satu batch, bukan bukti keputusan.
_RECEIPT_WORDS = (
    "penerimaan barang",
    "penerimaan batch",
    "goods receipt",
    "receipt",
    "terima barang",
)


class ReadOnlyBackend(Protocol):
    """Kontrak yang dipakai jembatan ini — SENGAJA hanya baca.

    `MealchainClient` memenuhinya; test memakai klien palsu yang memenuhi kontrak sama.
    Tidak ada metode tulis di sini: jembatan ini tidak boleh mengusulkan/menyetujui apa pun
    (`Rules.md` §1.2).
    """

    def __enter__(self) -> "ReadOnlyBackend": ...
    def __exit__(self, *_: object) -> None: ...
    def close(self) -> None: ...
    def health(self) -> dict[str, Any]: ...
    def demo_session(self) -> dict[str, Any]: ...
    def batches(self) -> list[dict[str, Any]]: ...
    def batch_detail(self, batch_id: str) -> dict[str, Any]: ...
    def suppliers(self) -> list[dict[str, Any]]: ...
    def locations(self) -> list[dict[str, Any]]: ...
    def balance_map(self, commodity: str) -> dict[str, Any]: ...
    def kpi(
        self,
        days: int = ...,
        *,
        scope: str = ...,
        demo_session_id: str | None = ...,
    ) -> dict[str, Any]: ...
    def pending_decisions(self) -> list[dict[str, Any]]: ...
    def purchase_orders(self) -> list[dict[str, Any]]: ...
    def po_detail(self, po_number: str) -> dict[str, Any]: ...
    def supply_point(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def demand(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def demand_forecast(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def price(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def price_quotes(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def waste_summary(self) -> dict[str, Any]: ...
    def surplus_regions(self) -> dict[str, Any]: ...
    def surplus_allocations(self, commodity: str, limit: int = ...) -> dict[str, Any]: ...
    def supplier_exclusions(self) -> list[dict[str, Any]]: ...
    def supplier_routes(self) -> dict[str, Any]: ...
    def decision_compliance(self, decision_id: str) -> dict[str, Any]: ...
    def decision_packet(self, decision_id: str) -> dict[str, Any]: ...
    def decision_chain(self, decision_id: str) -> dict[str, Any]: ...
    def decision_traces(self, decision_id: str) -> dict[str, Any]: ...
    def decisions(self) -> list[dict[str, Any]]: ...
    def integrations_status(self) -> dict[str, Any]: ...
    def ledger_verify(self) -> dict[str, Any]: ...
    def po_summary(self) -> dict[str, Any]: ...
    def receipts(self, batch_id: str) -> list[dict[str, Any]]: ...
    def receipts_menunggu(self) -> dict[str, Any]: ...


def _po_request(teks: str) -> Mapping[str, Any] | None:
    """Permintaan PO bila pesan menyebut nomor PO atau kata `po`/`purchase order`."""
    nomor = _PO_NUMBER.search(teks)
    if nomor:
        return {"po_number": nomor.group(1).upper()}
    angka = _PO_ANGKA.search(teks)
    if angka:
        return {"po_number": angka.group(1)}
    if _PO_WORD.search(teks):
        return {}
    return None


def resolve_skill(user_input: str) -> tuple[str, Mapping[str, Any]]:
    """Tentukan skill dari pesan masuk — deterministik, tidak memanggil model bahasa."""
    pesan = (user_input or "").strip()
    if pesan.startswith("{"):
        try:
            data = json.loads(pesan)
        except ValueError:
            data = None
        if isinstance(data, dict):
            # Pesan JSON = kontrak eksplisit. Skill tak dikenal TIDAK dipindai kata kuncinya:
            # seluruh isi JSON akan terbaca sebagai kata kunci dan menebak salah.
            diminta = str(data.get("skill") or "").strip()
            return (diminta if diminta in SKILLS else SKILL_SUPPLY), data
    teks = pesan.lower()
    # "keseimbangan pasokan dan kebutuhan" = tampilan saldo (pasokan vs kebutuhan),
    # bukan prakiraan. Kata `kebutuhan` saja milik SKILL_DEMAND, jadi diperiksa lebih dulu.
    if "keseimbangan" in teks or "saldo pasokan" in teks:
        return SKILL_SUPPLY, {}
    if any(keyword in teks for keyword in dict(_KEYWORDS)[SKILL_KPI]):
        return SKILL_KPI, {}
    # PO sebelum antrean: "PO mana yang sudah disetujui?" memuat `setuju` milik antrean.
    po = _po_request(pesan)
    if po is not None:
        return SKILL_PO, po
    # Kontrak lama yang harus tetap jalan: "penerimaan barang batch <uuid>" membaca
    # catatan SATU batch lewat `GET /receipts?batch_id=…`, bukan antrean. Diperiksa
    # sebelum kata kunci supaya skill antrean penerimaan tidak mencurinya.
    nomor_batch = _nomor_rujukan(pesan)
    if nomor_batch and any(k in teks for k in _RECEIPT_WORDS):
        return SKILL_SUPPLY, {"batch_id": nomor_batch.group(1)}
    # Batch yang disebut eksplisit + kata keamanan/suhu = rincian batch, walaupun pesannya
    # memuat `bukti` (milik SKILL_EVIDENCE, diperiksa lebih dulu di dalam loop). Contoh nyata:
    # "bukti suhu batch 068edb8a cukup?" dulu dijawab bukti keputusan, bukan rincian batch.
    if (
        nomor_batch
        and any(k in teks for k in dict(_KEYWORDS)[SKILL_BATCH])
        and not any(k in teks for k in _DISPOSAL_WORDS)
    ):
        return SKILL_BATCH, {"batch_id": nomor_batch.group(1)}
    for skill, kata_kunci in _KEYWORDS:
        if skill == SKILL_KPI:  # sudah diperiksa di atas, sebelum PO
            continue
        if not any(keyword in teks for keyword in kata_kunci):
            continue
        if skill == SKILL_BATCH and any(k in teks for k in _DISPOSAL_WORDS):
            # "batch mana yang harus dibuang" = kehilangan pangan, bukan rincian keamanan.
            continue
        payload: dict[str, Any] = {}
        if skill == SKILL_BATCH:
            nomor = _nomor_rujukan(pesan)
            if nomor:
                payload["batch_id"] = nomor.group(1)
        if skill == SKILL_EVIDENCE:
            nomor = _nomor_rujukan(pesan)
            if nomor:
                payload["decision_id"] = nomor.group(1)
        return skill, payload
    # Default = situasi pasokan. Penerimaan barang tetap mungkin diminta tanpa kata kunci
    # skill lain, jadi id batch diambil di sini.
    nomor = _nomor_rujukan(pesan)
    if nomor and any(k in teks for k in _RECEIPT_WORDS):
        return SKILL_SUPPLY, {"batch_id": nomor.group(1)}
    return SKILL_SUPPLY, {}


def _kalimat_sesi(sesi: Mapping[str, Any]) -> str:
    """Konteks sesi demo untuk jawaban KPI: mode, jangkar, dan id sesi.

    Fase 12 MG. Tanpa kalimat ini pembaca Joule tidak bisa membedakan "hari ini"
    pada tabel (catatan operasional) dari jangkar simulasi yang sedang dimuat
    operator, dan tidak bisa mencocokkan sesinya dengan `GET /demo/session`.
    """
    mode = str(sesi.get("mode") or "").strip().lower()
    ident = str(sesi.get("session_id") or sesi.get("id") or "").strip()
    jangkar = str(sesi.get("evaluation_anchor") or "").strip()
    tanggal = ""
    if jangkar:
        try:
            saat = datetime.fromisoformat(jangkar.replace("Z", "+00:00"))
        except ValueError:
            saat = None
        if saat is not None:
            if saat.tzinfo is not None:
                saat = saat.astimezone(timezone(timedelta(hours=7)))
            tanggal = f"{saat.day} {_BULAN[saat.month - 1]} {saat.year} {saat:%H:%M} WIB"
    potongan = [f"mode {mode}" if mode else None]
    if tanggal:
        potongan.append(f"jangkar {tanggal}")
    if ident:
        potongan.append(f"sesi {ident[:8]}")
    rinci = ", ".join([p for p in potongan if p])
    if not rinci:
        return ""
    return (
        f"Sesi demo aktif: {rinci} — angka KPI di atas tetap catatan operasional, "
        "bukan hasil simulasi."
    )


def _jendela_kpi(sesi: Mapping[str, Any] | None) -> int:
    """Jendela KPI yang cukup lebar untuk memuat JANGKAR sesi demo.

    Mode replay berjangkar 8 Okt 2026; jendela bawaan 7 hari pada 27 Okt tidak
    memuat satu baris pun, sehingga seluruh indikator berbunyi "belum bisa
    dihitung" padahal datanya ada di sesi. Jendela diperlebar sampai jangkar,
    tidak lebih: memperlebar tanpa batas akan mencampur periode lain.
    """
    dasar = KPI_DEFAULT_DAYS
    if not isinstance(sesi, Mapping):
        return dasar
    jangkar = str(sesi.get("evaluation_anchor") or "").strip()
    if not jangkar:
        return dasar
    try:
        saat = datetime.fromisoformat(jangkar.replace("Z", "+00:00"))
    except ValueError:
        return dasar
    if saat.tzinfo is None:
        saat = saat.replace(tzinfo=timezone.utc)
    selisih = (datetime.now(timezone.utc) - saat).days + 1
    return max(dasar, selisih + 1)


def _data_source_note(client: ReadOnlyBackend) -> str | None:
    """Penanda sumber data dari `/health` — `Rules.md` §1.4: yang mock harus terlihat mock.

    Gagal membaca `/health` bukan alasan menggagalkan laporan: catatan ini hanya konteks,
    dan laporan tetap menyebut asal angkanya.
    """
    try:
        sap = (client.health() or {}).get("sap") or {}
    except MealchainUnavailable:
        return None
    sumber = sap.get("data_source")
    if not sumber:
        return None
    tambahan = " (campuran beberapa sumber)" if sap.get("is_mixed") else ""
    return f"Sumber data SAP pada backend: {sumber}{tambahan} — data mock ditandai mock, bukan klaim SAP nyata."


def _disebut(teks_kecil: str, nama: str) -> bool:
    """Nama disebut sebagai kata utuh — `ayam` tidak boleh cocok di dalam `bayam`."""
    if not nama:
        return False
    pola = rf"(?<![a-z0-9]){re.escape(nama.lower())}(?![a-z0-9])"
    return re.search(pola, teks_kecil) is not None


def _permintaan_bantuan(teks: str) -> bool:
    """Sapaan / permintaan bantuan: dijawab daftar kemampuan, bukan tabel data.

    Dua tingkat (26 Okt 2026): frasa yang jelas menanyakan KEMAMPUAN selalu dijawab daftar
    kemampuan; sapaan/kata samar (`halo`, `bantuan`, `help`) hanya menang bila pesan tidak
    memuat kata domain — supaya "Halo, kondisi pasokan beras?" tidak berubah jadi menu.
    """
    kecil = (teks or "").lower()
    if not re.search(r"[a-z0-9]", kecil):
        # Pesan kosong / emoji saja tidak punya maksud: daftar kemampuan lebih jujur
        # daripada menebak tabel pasokan 40 baris (audit 26 Okt 2026).
        return True
    if any(frasa in kecil for frasa in _HELP_TEGAS):
        return True
    if not any(kata in kecil for kata in _HELP_WORDS):
        return False
    return not _ada_kata_domain(kecil)


def _permintaan_buang(teks: str) -> bool:
    """Pertanyaan tentang batch yang harus dibuang / sudah kedaluwarsa."""
    kecil = (teks or "").lower()
    return any(kata in kecil for kata in _BUANG_WORDS)


def teks_bantuan() -> str:
    """Daftar kemampuan Joule untuk MealChain Guardian (tanpa satu pun angka)."""
    return (
        "Saya Joule untuk MealChain Guardian: saya membaca data operasional SPPG yang tersimpan "
        "di sistem, lalu menyajikannya dalam tabel. Saya tidak menghitung ulang angka dan tidak "
        "menyetujui apa pun.\n\n"
        "Contoh yang bisa Anda tanyakan:\n"
        "- **Pasokan**: \"bagaimana kondisi pasokan?\" · \"berapa stok telur di Bandung?\"\n"
        "- **Kebutuhan & prakiraan**: \"prakiraan kebutuhan beras di Jakarta\"\n"
        "- **Harga**: \"harga telur di Bandung\"\n"
        "- **Antrean keputusan**: \"usulan yang menunggu persetujuan\"\n"
        "- **Penerimaan barang**: \"antrean penerimaan barang\"\n"
        "- **Karantina & batch bermasalah**: \"batch yang dikarantina\" · \"batch mana yang harus dibuang?\"\n"
        "- **Purchase order**: \"PO MC-661695B2C685\" · \"PO mana yang sudah disetujui?\"\n"
        "- **Pemasok**: \"direktori pemasok\" · \"pemasok yang dikecualikan\"\n"
        "- **Kehilangan pangan**: \"limbah minggu ini\"\n"
        "- **KPI**, **bukti keputusan** (sebut nomor keputusan), dan **status integrasi**.\n\n"
        "Persetujuan, eksekusi, dan pembuangan tetap dilakukan manusia di UI MealChain."
    )


def _pairs(client: ReadOnlyBackend, teks: str = "") -> tuple[list[dict[str, str]], int, int]:
    """Pasangan (SPPG, komoditas) yang benar-benar ada di inventaris.

    Sumber pasangan = `/batches`, bukan daftar di kode. Bila pengguna menyebut nama SPPG atau
    komoditas, pasangan itu yang diperiksa (panggilan HTTP ikut menyusut); tanpa penyebutan,
    `PAIR_LIMIT` pasangan pertama diperiksa dan sisanya DISEBUT di catatan laporan.

    Kembalian: (pasangan yang diperiksa, jumlah pasangan di inventaris, jumlah pasangan yang
    cocok dengan penyebutan pengguna).
    """
    unik: dict[tuple[str, str], dict[str, str]] = {}
    for row in client.batches():
        nama_lokasi = str(row.get("location") or "")
        komoditas = str(row.get("commodity") or "")
        lokasi_id = str(row.get("location_id") or "")
        if not (nama_lokasi and komoditas and lokasi_id):
            continue
        unik.setdefault(
            (nama_lokasi, komoditas),
            {"location": nama_lokasi, "location_id": lokasi_id, "commodity": komoditas},
        )
    semua = sorted(unik.values(), key=lambda p: (p["location"], p["commodity"]))
    teks_kecil = (teks or "").lower()
    lokasi = {p["location"] for p in semua if _disebut(teks_kecil, p["location"])}
    komoditas = {p["commodity"] for p in semua if _disebut(teks_kecil, p["commodity"])}
    dipilih = [
        p
        for p in semua
        if (not lokasi or p["location"] in lokasi) and (not komoditas or p["commodity"] in komoditas)
    ] or semua
    return dipilih[:PAIR_LIMIT], len(semua), len(dipilih)


def _satu_pasangan(batches: Sequence[Mapping[str, Any]], teks: str) -> dict[str, str] | None:
    """Pasangan (SPPG, komoditas) TUNGGAL yang disebut pengguna, kalau ada.

    Dipakai untuk menampilkan baris sumber pasokan terakhir (`GET /supply/…`) hanya saat
    pertanyaannya spesifik — supaya tidak menambah satu panggilan HTTP per pasangan.
    """
    unik: dict[tuple[str, str], dict[str, str]] = {}
    for row in batches:
        nama_lokasi = str(row.get("location") or "")
        komoditas = str(row.get("commodity") or "")
        lokasi_id = str(row.get("location_id") or "")
        if not (nama_lokasi and komoditas and lokasi_id):
            continue
        unik.setdefault(
            (nama_lokasi, komoditas),
            {"location": nama_lokasi, "location_id": lokasi_id, "commodity": komoditas},
        )
    teks_kecil = (teks or "").lower()
    lokasi = {p["location"] for p in unik.values() if _disebut(teks_kecil, p["location"])}
    komoditas = {p["commodity"] for p in unik.values() if _disebut(teks_kecil, p["commodity"])}
    if len(lokasi) != 1 or len(komoditas) != 1:
        return None
    return unik.get((next(iter(lokasi)), next(iter(komoditas))))


def _gabung(*bagian: str | None) -> str | None:
    """Sambung catatan laporan; `None` kalau tidak ada isinya."""
    isi = [b for b in bagian if b]
    return "\n\n".join(isi) if isi else None


def _coverage_note(total: int, tersedia: int, diperiksa: int, gagal: Sequence[str]) -> str | None:
    """Catatan cakupan: berapa pasangan ada, berapa diperiksa, apa yang gagal dibaca."""
    bagian: list[str] = []
    if tersedia < total:
        bagian.append(
            f"Dari {total} pasangan (SPPG, komoditas) di inventaris, {diperiksa} diperiksa karena "
            "pertanyaan menyebut SPPG/komoditas tertentu."
        )
    elif diperiksa < tersedia:
        bagian.append(
            f"{tersedia} pasangan (SPPG, komoditas) ada di inventaris; {diperiksa} diperiksa dalam "
            f"satu jawaban (batas {PAIR_LIMIT}). Sebut nama SPPG atau komoditas untuk mempersempit."
        )
    if gagal:
        bagian.append("Tidak terbaca: " + "; ".join(gagal) + " — bukan berarti nol.")
    return "\n\n".join(bagian) if bagian else None


def render_skill(
    client: ReadOnlyBackend,
    skill: str,
    payload: Mapping[str, Any] | None = None,
    teks: str | None = None,
) -> str:
    """Jalankan satu skill: ambil dari backend, render markdown. Tidak ada aritmetika di sini.

    Skill pasokan membaca dua read model: `/batches` (keamanan & kesegaran melekat pada batch)
    dan `/balance/map` (pasokan/kebutuhan per lokasi) — satu panggilan per komoditas yang
    benar-benar ada di inventaris. Komoditasnya DIBACA dari data, bukan didaftar tetap di kode.

    Skill berpasangan (harga, kebutuhan) mengiterasi pasangan yang ada di inventaris; skill
    bukti & sistem membaca endpoint keputusan/ledger/integrasi. Semua angka tetap milik backend.
    """
    # Sapaan / "bisa bantu apa?" tidak boleh dijawab tabel 40 baris: itu terasa seperti
    # jawaban asal-asalan. Dijawab daftar kemampuan, tanpa memanggil backend sama sekali.
    if skill == SKILL_SUPPLY and teks is not None and _permintaan_bantuan(teks):
        return teks_bantuan()

    # Perintah tulis ditolak SEBELUM skill mana pun: tanpa ini "Setujui PO MC-…"
    # dijawab tabel PO (terlihat seperti sudah diproses) padahal tidak ada apa pun
    # yang diubah. Otorisasi tetap milik cockpit MealChain + token approver.
    if teks is not None and _WRITE_INTENT.search(teks):
        return (
            "Saya tidak bisa menyetujui, menolak, atau mengeksekusi apa pun — jembatan "
            "ini hanya membaca data MealChain Guardian.\n\n"
            "Persetujuan tetap dilakukan manusia di cockpit MealChain: buka tab "
            "**Keputusan** → pilih keputusan → **Setujui** (kepala SPPG) dan satu peran "
            "kedua, lalu **Eksekusi**. Setiap token approver hanya berlaku untuk perannya "
            "sendiri, dan bukti yang kurang akan menahan keputusan sebagai `on_hold`.\n\n"
            "Yang bisa saya bantu: membaca pasokan, KPI, antrean persetujuan, status PO, "
            "kiriman, dan bukti keputusan."
        )

    note = _data_source_note(client)
    if skill == SKILL_KPI:
        # Cakupan KPI (Fase 8): bawaan = fakta operasional. Pemanggil yang minta
        # cakupan simulasi WAJIB menyebut sesinya; tanpa itu jawabannya menolak
        # dengan kalimat, bukan menebak sesi terakhir (angka milik sesi lain
        # adalah cacat yang justru ditutup Fase 8).
        opsi = payload if isinstance(payload, Mapping) else {}
        scope = str(opsi.get("scope") or "").strip().lower()
        sesi = opsi.get("demo_session_id") or opsi.get("session_id")
        # Fase 12 MG: konteks sesi WAJIB disebut, tetapi angka KPI tetap
        # cakupan operasional kecuali pemanggil meminta cakupan demo secara
        # eksplisit. Alasannya terukur (27 Okt 2026): baris dataset template
        # dimiliki sesi "cetakan" (sentinel), sedangkan sesi yang dimuat
        # operator adalah sesi lain — cakupan demo untuk sesi operator
        # mengembalikan 7 indikator `no_data` padahal datanya ada. Menyebut
        # sesi + menyatakan angkanya operasional lebih jujur daripada tabel
        # kosong, dan tetap memenuhi syarat "jelaskan konteks sesi".
        aktif: Mapping[str, Any] = {}
        pembaca_sesi = getattr(client, "demo_session", None)
        if callable(pembaca_sesi):
            hasil_sesi = pembaca_sesi()
            if isinstance(hasil_sesi, Mapping):
                aktif = hasil_sesi
        if not scope:
            scope = "operational"
        sesi_aktif = aktif.get("session_id") or aktif.get("id")
        if aktif.get("active") is not False and sesi_aktif and scope == "operational":
            kalimat = _kalimat_sesi(aktif)
            note = f"{note} {kalimat}".strip() if note else kalimat
        try:
            envelope = client.kpi(
                scope=scope, demo_session_id=str(sesi) if sesi else None
            )
        except ValueError as exc:
            return report.kpi_scope_problem(str(exc), note=note)
        return report.kpi_report(envelope, note=note)
    if skill == SKILL_QUEUE:
        # `pending_decisions()` hanya melengkapi DETAIL_LIMIT baris teratas; jumlah terbuka
        # yang sebenarnya dihitung dari daftar keputusan mentah supaya judul tidak berbohong.
        terbuka = sum(
            1
            for row in client.decisions()
            if str(row.get("status")) in report.UNFINISHED_STATUS
        )
        return report.approval_queue_report(
            client.pending_decisions(), note=note, total_belum=terbuka
        )
    if skill == SKILL_RECEIPTS:
        return report.receipts_queue_report(client.receipts_menunggu(), note=note)
    if skill == SKILL_QUARANTINE:
        return report.quarantine_report(client.batches(), note=note)
    if skill == SKILL_BATCH:
        batch_id = str((payload or {}).get("batch_id") or "").strip() or None
        if batch_id:
            # Operator menyalin id pendek (8 karakter) dari laporan karantina/daftar batch.
            # Petakan ke id lengkap dulu, supaya pertanyaan yang wajar tidak berakhir "tidak
            # ditemukan" hanya karena id dipotong.
            daftar = client.batches()
            if len(batch_id) < 36:
                cocok = [
                    str(row.get("id") or row.get("batch_id") or "")
                    for row in daftar
                    if isinstance(row, Mapping)
                    and str(row.get("id") or row.get("batch_id") or "")
                    .lower()
                    .startswith(batch_id.lower())
                ]
                if len(cocok) == 1:
                    batch_id = cocok[0]
            try:
                detail = client.batch_detail(batch_id)
            except MealchainRejected:
                # Batch tidak ada / bukan milik peran ini: tampilkan kandidat, bukan rincian
                # karangan dan bukan pesan error mentah.
                return report.batch_detail_report(
                    None, candidates=daftar, batch_id=batch_id, note=note
                )
            return report.batch_detail_report(detail, batch_id=batch_id, note=note)
        return report.batch_detail_report(None, candidates=client.batches(), note=note)
    if skill == SKILL_GAP:
        return report.unsupported_report(
            "pengiriman barang, surat jalan, atau stok material SAP",
            "datanya belum tersedia di MealChain Guardian — belum ada sumber data untuk pengiriman, surat jalan, atau stok material SAP.",
        )
    if skill == SKILL_PO:
        nomor = str((payload or {}).get("po_number") or "").strip() or None
        kecil = (teks or "").lower()
        hanya_disetujui = any(
            kata in kecil for kata in ("disetujui", "dieksekusi", "approved", "sudah disetujui")
        )
        # Nomor PO disebut → baca DOKUMEN-nya (29 Okt 2026), bukan sekadar baris
        # daftar: rincian biaya, persetujuan bernama, syarat, keputusan asal.
        # Backend lama tanpa rute `/detail` ditangani dengan jatuh ke tampilan
        # daftar — jangan menjawab "tidak ditemukan" hanya karena rutenya belum ada.
        if nomor:
            baca = getattr(client, "po_detail", None)
            if callable(baca):
                try:
                    dokumen = baca(nomor)
                except MealchainRejected:
                    dokumen = None
                except MealchainUnavailable as exc:
                    return report.unavailable_report("purchase_order", str(exc))
                if isinstance(dokumen, dict):
                    return report.po_document_report(dokumen, note=note)
        return report.purchase_order_report(
            client.purchase_orders(),
            po_number=nomor,
            note=note,
            hanya_disetujui=hanya_disetujui,
        )
    if skill == SKILL_DIRECTORY:
        return report.supplier_directory_report(client.suppliers(), note=note)

    if skill == SKILL_PRICE:
        pairs, total, tersedia = _pairs(client, teks or "")
        prices: list[Mapping[str, Any]] = []
        quotes: list[Mapping[str, Any]] = []
        gagal: list[str] = []
        for pair in pairs:
            label = f"{pair['location']}/{pair['commodity']}"
            try:
                prices.append(client.price(pair["location_id"], pair["commodity"]))
            except MealchainRejected as exc:
                gagal.append(f"harga {label} ({exc})")
            try:
                quotes.append(client.price_quotes(pair["location_id"], pair["commodity"]))
            except MealchainRejected as exc:
                gagal.append(f"kuotasi {label} ({exc})")
        return report.price_report(
            prices,
            quotes,
            note=_gabung(note, _coverage_note(total, tersedia, len(pairs), gagal)),
        )

    if skill == SKILL_DEMAND:
        pairs, total, tersedia = _pairs(client, teks or "")
        rows: list[dict[str, Any]] = []
        gagal = []
        for pair in pairs:
            label = f"{pair['location']}/{pair['commodity']}"
            try:
                kebutuhan = client.demand(pair["location_id"], pair["commodity"])
            except MealchainRejected as exc:
                gagal.append(f"kebutuhan {label} ({exc})")
                continue
            prakiraan: Mapping[str, Any] = {}
            try:
                prakiraan = client.demand_forecast(pair["location_id"], pair["commodity"])
            except MealchainRejected as exc:
                gagal.append(f"prakiraan {label} ({exc})")
            rows.append(
                {
                    "location": pair["location"],
                    "commodity": pair["commodity"],
                    "quantityKg": kebutuhan.get("quantity_kg"),
                    "neededBy": kebutuhan.get("needed_by"),
                    "forecastKg": prakiraan.get("forecast_qty_kg"),
                    "forecastMethod": prakiraan.get("method"),
                    "confidence": prakiraan.get("confidence"),
                }
            )
        return report.demand_report(
            rows, note=_gabung(note, _coverage_note(total, tersedia, len(pairs), gagal))
        )

    if skill == SKILL_LOSS:
        return report.food_loss_report(client.waste_summary(), note=note)

    if skill == SKILL_SUPPLIER_RISK:
        # Hanya id yang dikirim `/supplier-exclusions`; nama diambil dari direktori & daftar
        # lokasi backend yang sama — bukan tabel nama yang ditanam di jembatan.
        nama_pemasok = {str(row.get("id")): row.get("name") for row in client.suppliers()}
        nama_lokasi = {str(row.get("id")): row.get("name") for row in client.locations()}
        exclusions = [
            {
                **row,
                "supplierName": nama_pemasok.get(str(row.get("supplier_id"))),
                "scopeLocationName": nama_lokasi.get(str(row.get("scope_location_id"))),
            }
            for row in client.supplier_exclusions()
        ]
        return report.supplier_risk_report(exclusions, client.supplier_routes(), note=note)

    if skill == SKILL_SURPLUS:
        # Satu panggilan `/surplus/regions`, lalu satu panggilan alokasi per komoditas.
        # Komoditasnya DIBACA dari kiriman backend (bukan daftar tetap), dan kalau pengguna
        # menyebut satu komoditas, itu yang diperiksa lebih dulu — memotong urutan acak akan
        # menjawab komoditas yang tidak ditanyakan.
        wilayah = client.surplus_regions()
        semua_komoditas = [str(k) for k in (wilayah.get("commodities") or ()) if str(k).strip()]
        kecil = (teks or "").lower()
        disebut = [k for k in semua_komoditas if _disebut(kecil, k)]
        urutan = disebut + [k for k in semua_komoditas if k not in disebut]
        dipilih = urutan[:SURPLUS_COMMODITY_LIMIT]
        alokasi: list[Mapping[str, Any]] = []
        gagal: list[str] = []
        for komoditas in dipilih:
            try:
                alokasi.append(client.surplus_allocations(komoditas))
            except MealchainRejected as exc:
                gagal.append(f"rencana alih {komoditas} ({exc})")
        catatan_gagal = f"Tidak terbaca: {'; '.join(gagal)} — bukan berarti nol." if gagal else None
        return report.surplus_region_report(
            wilayah,
            alokasi,
            note=_gabung(note, catatan_gagal),
            dilewati=max(0, len(semua_komoditas) - len(dipilih)),
        )

    if skill == SKILL_EVIDENCE:
        diminta = str((payload or {}).get("decision_id") or "").strip()
        if diminta:
            utuh, galat = _resolve_id(
                diminta,
                [str(row.get("decision_id")) for row in client.decisions() if row.get("decision_id")],
                sebutan="keputusan",
            )
            if galat:
                return galat
            ids = [utuh]
        else:
            ids = [
                str(row.get("decision_id"))
                for row in client.decisions()
                if row.get("decision_id")
            ][:EVIDENCE_LIMIT]
        cases: list[dict[str, Any]] = []
        gagal_ev: list[str] = []
        for satu in ids:
            try:
                compliance = client.decision_compliance(satu)
            except MealchainRejected:
                gagal_ev.append(report.short_id(satu))
                continue
            rantai: Mapping[str, Any] = {}
            jejak: Mapping[str, Any] = {}
            try:
                rantai = client.decision_chain(satu)
            except MealchainRejected as exc:
                gagal_ev.append(f"rantai {satu} ({exc})")
            try:
                jejak = client.decision_traces(satu)
            except MealchainRejected as exc:
                gagal_ev.append(f"jejak {satu} ({exc})")
            # Fase 6 butir 4: state bukti batch dibaca dari PAKET keputusan (read model
            # yang sama dengan layar), bukan dihitung ulang di jembatan.
            paket: dict[str, Any] = {}
            try:
                paket = client.decision_packet(satu)
            except MealchainRejected as exc:
                gagal_ev.append(f"paket {satu} ({exc})")
            cases.append(
                {
                    "id": satu,
                    "compliance": compliance,
                    "chain": rantai,
                    "traces": jejak,
                    "packet": paket,
                }
            )
        return report.decision_evidence_report(
            cases,
            note=_gabung(
                note,
                (
                    "Keputusan "
                    + ", ".join(gagal_ev)
                    + " tidak ditemukan di data yang aktif sekarang — salin ulang 8 karakter"
                    " pertama ID dari tabel antrean. Tidak ada angka pengganti yang dikarang."
                )
                if gagal_ev
                else None,
            ),
        )

    if skill == SKILL_SYSTEM:
        return report.system_status_report(
            client.integrations_status(),
            client.ledger_verify(),
            client.po_summary(),
            client.locations(),
            note=note,
        )

    batches_semua = client.batches()

    # Pertanyaan "batch mana yang harus dibuang?" tidak dijawab tabel pasokan: tampilkan
    # kandidat tinjauan (keamanan GAGAL / dikarantina) dan tegaskan keputusan ada di manusia.
    if _permintaan_buang(teks or ""):
        return report.batch_disposal_report(batches_semua, note=note)

    # Kalau pertanyaan menyebut SPPG dan/atau komoditas, saring ke pasangan itu saja: jawaban
    # "berapa stok telur di Bandung?" tidak boleh berupa 40 baris yang harus dibaca sendiri.
    kecil = (teks or "").lower()
    lokasi_disebut = {
        str(row.get("location"))
        for row in batches_semua
        if _disebut(kecil, str(row.get("location") or ""))
    }
    komoditas_disebut = {
        str(row.get("commodity"))
        for row in batches_semua
        if _disebut(kecil, str(row.get("commodity") or ""))
    }
    batches = [
        row
        for row in batches_semua
        if (not lokasi_disebut or str(row.get("location")) in lokasi_disebut)
        and (not komoditas_disebut or str(row.get("commodity")) in komoditas_disebut)
    ]
    if not batches:  # nama disebut tetapi tidak ada di inventaris: jangan tampilkan laporan kosong
        batches = batches_semua
        lokasi_disebut, komoditas_disebut = set(), set()

    komoditas = sorted(
        {str(row.get("commodity")) for row in batches if row.get("commodity")}
    )
    balance: dict[str, Mapping[str, Any]] = {}
    gagal: list[str] = []
    for nama in komoditas:
        try:
            payload_balance = client.balance_map(nama)
        except MealchainRejected as exc:
            # Satu komoditas yang tidak punya data keseimbangan tidak boleh mematikan seluruh
            # laporan: tabel batch (keamanan/kesegaran) tetap berguna. Kekosongannya disebut
            # apa adanya — bukan diisi nol, karena nol terbaca "tidak ada masalah".
            gagal.append(f"{nama} ({exc})")
            continue
        if lokasi_disebut and isinstance(payload_balance, Mapping):
            baris_lokasi = payload_balance.get("locations") or ()
            payload_balance = {
                **payload_balance,
                "locations": [
                    row
                    for row in baris_lokasi
                    if str(row.get("location")) in lokasi_disebut
                ],
            }
        balance[nama] = payload_balance
    if gagal:
        tambahan = (
            "Keseimbangan tidak terbaca untuk: "
            + "; ".join(gagal)
            + " — komoditas itu tidak muncul di tabel keseimbangan, bukan berarti nol."
        )
        note = f"{note}\n\n{tambahan}" if note else tambahan

    satu = _satu_pasangan(batches_semua, teks or "")
    laporan = report.supply_report(batches, balance, note=note, pasangan=satu)

    # Kalau pertanyaannya menyebut SATU SPPG dan SATU komoditas, sebutkan baris sumbernya:
    # `/balance/map` memberi `supply_kg` hasil hitungan backend, `/supply/…` memberi catatan
    # pasokan terakhir apa adanya (kg, waktu catat, sumber) — satu panggilan, tanpa agregasi.
    if satu:
        try:
            titik = client.supply_point(satu["location_id"], satu["commodity"])
        except MealchainRejected:
            titik = {}
        if titik:
            dicatat = report.wib(titik.get("recorded_at"))
            masa_depan = ""
            try:
                waktu = datetime.fromisoformat(str(titik.get("recorded_at")).replace("Z", "+00:00"))
                if waktu > datetime.now(timezone.utc):
                    masa_depan = (
                        " — tanggal ini melewati hari ini, jadi baris ini catatan terjadwal "
                        "dalam data, bukan pencatatan yang sudah terjadi"
                    )
            except (TypeError, ValueError):
                masa_depan = ""
            laporan += (
                f"\n\nCatatan pasokan terakhir yang dilaporkan SAP untuk {satu['location']} / "
                f"{satu['commodity']}: {report.kg(titik.get('quantity_kg'))}, dicatat "
                f"{dicatat}{masa_depan} (sumber "
                f"{report._label(report.PRICE_SOURCE_LABEL, titik.get('source') or report.MISSING)}). "
                "Angka ini catatan pengiriman pemasok, "
                "bukan stok batch yang bisa dipakai."
            )

    # Penerimaan barang (goods receipt) selalu per batch: `/receipts` mewajibkan `batch_id`.
    # Kalau pengguna menyebut SATU batch, jawabannya adalah catatan penerimaan batch itu saja —
    # bukan seluruh tabel pasokan dengan catatan batch ditempel di ujung.
    batch_id = str((payload or {}).get("batch_id") or "").strip()
    if not batch_id:
        return laporan
    batch_id, galat_batch = _resolve_id(
        batch_id,
        [str(row.get("id")) for row in batches_semua if row.get("id")],
        sebutan="batch",
    )
    if galat_batch:
        return galat_batch
    try:
        receipts = client.receipts(batch_id)
    except MealchainRejected as exc:
        return (
            f"Penerimaan barang batch {batch_id} tidak terbaca: {exc}.\n\n"
            "Batch yang tidak terdaftar atau di luar cakupan akun baca tidak akan muncul — "
            "bukan berarti catatannya tidak ada."
        )
    return report.receipt_report(receipts, batch_id=batch_id, note=note)


def _resolve_id(
    diminta: str,
    kandidat: Sequence[str],
    *,
    sebutan: str = "data",
) -> tuple[str, str | None]:
    """Cocokkan id yang disebut pengguna (boleh 8 karakter pertama) ke id utuh.

    Urutan: cocok PERSIS → awalan unik → selain itu tidak ditebak. Hasil `(id, pesan_galat)`;
    `pesan_galat` sudah berbahasa pengguna dan siap dikirim sebagai artefak chat.

    Id panjang (≥32 karakter) yang tidak ada di daftar tetap diteruskan apa adanya supaya
    record di luar cakupan daftar masih bisa dibuka lewat endpoint-nya sendiri — backend yang
    memutuskan, bukan tebakan pencocokan di jembatan.
    """
    kunci = (diminta or "").strip()
    if not kunci:
        return diminta, None

    def sama(nilai: str) -> bool:
        return nilai.lower() == kunci.lower()

    def awalan(nilai: str) -> bool:
        return nilai.lower().startswith(kunci.lower())

    persis = [nilai for nilai in kandidat if sama(nilai)]
    if persis:
        return persis[0], None

    mirip = [nilai for nilai in kandidat if awalan(nilai)]
    if len(mirip) == 1:
        return mirip[0], None
    if len(mirip) > 1:
        contoh = ", ".join(report.short_id(nilai) for nilai in mirip[:5])
        return diminta, (
            f"Ada {len(mirip)} {sebutan} yang cocok dengan awalan `{kunci}` ({contoh}). "
            "Sebutkan lebih banyak karakter supaya saya membuka yang tepat — saya tidak memilih "
            "salah satu atas nama Anda."
        )
    if len(kunci) >= 32:
        return kunci, None
    return diminta, (
        f"Tidak ada {sebutan} dengan awalan `{kunci}` di data yang bisa saya baca sekarang. "
        "Coba salin ulang id dari tabel sebelumnya."
    )


def default_client_factory() -> MealchainClient:
    """Klien dari environment (`MEALCHAIN_API_URL`, `MEALCHAIN_READ_USERNAME/PASSWORD`)."""
    return MealchainClient()


class MealchainExecutor(AgentExecutor):
    """Menjembatani siklus hidup tugas A2A ke pembacaan backend MealChain.

    Pekerjaan backend bersifat sinkron (httpx), jadi dijalankan di thread pool dengan
    `run_in_executor` supaya event loop server tidak beku — sama seperti pola tutorial.
    """

    def __init__(
        self, client_factory: Callable[[], ReadOnlyBackend] = default_client_factory
    ) -> None:
        self._client_factory = client_factory

    def _render(
        self, skill: str, payload: Mapping[str, Any] | None = None, teks: str | None = None
    ) -> str:
        with self._client_factory() as client:
            return render_skill(client, skill, payload, teks)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        teks = context.get_user_input()
        skill, payload = resolve_skill(teks)
        try:
            loop = asyncio.get_running_loop()
            body = await loop.run_in_executor(None, self._render, skill, payload, teks)
        except MealchainUnavailable as exc:
            # Diterbitkan sebagai ARTEFAK teks, bukan tugas `failed`: function Joule membaca
            # `artifacts[0].parts[0].text`, jadi hanya begini pengguna melihat penyebabnya.
            body = report.unavailable_report(skill, str(exc))
        except Exception as exc:  # jaring pengaman: pengguna harus tetap dapat penjelasan
            body = report.unavailable_report(skill, f"galat tak terduga: {exc!r}")

        # Satu baris bukti per pesan, terlihat di `cf logs`: tanpa ini tidak ada cara
        # membedakan "chat kosong karena artefak kosong" dari "chat kosong karena
        # Joule tidak memanggil jembatan" saat demo. Ukuran art di access log router
        # BUKAN panjang jawaban, jadi jangan dipakai menebak.
        _log.info(
            "pesan A2A: skill=%s teks=%d char artefak=%d char",
            skill,
            len(teks or ""),
            len(body),
        )

        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                artifact=Artifact(
                    artifactId=ARTIFACT_ID,
                    name=ARTIFACT_NAME,
                    parts=[TextPart(text=body)],
                ),
            )
        )
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


def public_url() -> str:
    """URL publik aplikasi: dari `VCAP_APPLICATION` saat di Cloud Foundry, else localhost."""
    vcap = json.loads(os.environ.get("VCAP_APPLICATION", "{}") or "{}")
    uris = vcap.get("application_uris") or []
    if uris:
        return f"https://{uris[0]}"
    return f"http://localhost:{os.environ.get('PORT', DEFAULT_PORT)}"


def agent_card(app_url: str) -> AgentCard:
    """Identitas agen — dibaca Joule (via BTP Destination) di `/.well-known/agent-card.json`."""
    modalitas = ["text/plain", "application/json"]
    return AgentCard(
        name="MealChain Guardian — jembatan Joule",
        description=(
            "Membaca SELURUH data MealChain Guardian (SPPG/BGN) yang dimiliki akun baca ini: "
            "situasi pasokan, kebutuhan & prakiraan, harga & kuotasi pemasok, kehilangan pangan, "
            "direktori & risiko pemasok, antrean usulan keputusan, bukti/jejak keputusan, "
            "purchase order (PO), serta status integrasi & ledger. Baca-saja: persetujuan tetap "
            "dilakukan manusia."
        ),
        url=app_url,
        # Disamakan dengan `metadata.version` di capability.sapdas.yaml: agent
        # card yang lebih tua dari capability membuat operator mengira Joule
        # memakai definisi lama padahal scenario-nya sudah 1.4.0.
        version="1.4.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id=SKILL_SUPPLY,
                name="Situasi pasokan SPPG",
                description=(
                    "Stok terpakai, kebutuhan, selisih surplus/kurang, kesegaran, dan status "
                    "keamanan pangan per SPPG dan komoditas."
                ),
                tags=["pangan", "pasokan", "sppg", "mbg", "surplus", "kekurangan"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_KPI,
                name="Indikator kinerja",
                description=(
                    "KPI MealChain Guardian: keberlanjutan porsi, kehilangan pangan yang bisa "
                    "dihindari, penyelesaian ketimpangan wilayah, biaya aman terkirim, "
                    "simpangan harga, waktu keputusan, kelengkapan bukti."
                ),
                tags=["kpi", "indikator", "kinerja", "metrik"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_QUEUE,
                name="Antrean usulan keputusan",
                description=(
                    "Daftar usulan rebalancing/anomali harga/gangguan keamanan/eksklusi pemasok "
                    "beserta statusnya. Hanya untuk dilihat; persetujuan di UI MealChain."
                ),
                tags=["usulan", "approval", "persetujuan", "keputusan"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_RECEIPTS,
                name="Antrean penerimaan barang",
                description=(
                    "Catatan penerimaan barang (goods receipt) yang sudah diperiksa tetapi belum "
                    "diputuskan: komoditas, jumlah, lokasi, status keamanan, pencatat, dan "
                    "kelengkapan pemeriksaan. Persetujuan di UI MealChain."
                ),
                tags=["penerimaan", "receipt", "receiving", "barang datang", "sppg"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_QUARANTINE,
                name="Status karantina batch",
                description=(
                    "Batch yang sedang dikarantina beserta komoditas, jumlah, lokasi, dan status "
                    "keamanannya — dibaca dari kolom `quarantine_status`."
                ),
                tags=["karantina", "quarantine", "keamanan pangan", "batch"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_BATCH,
                name="Rincian keamanan satu batch",
                description=(
                    "Rincian satu batch menurut ID: jumlah, status keamanan tersimpan dan hasil "
                    "evaluasi terbaru, kelayakan pakai beserta penghalang dan langkah berikutnya, "
                    "skor kesegaran, masa layak, status karantina, kebijakan suhu komoditas yang "
                    "dipakai menilai (rentang suhu, sampel minimum, versi kebijakan, jenisnya), "
                    "serta kecukupan bukti observasi suhu. Baca-saja."
                ),
                tags=["batch", "suhu", "keamanan pangan", "kedaluwarsa", "kesegaran"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_PO,
                name="Purchase order (PO) mock SAP",
                description=(
                    "Purchase order yang terbit dari keputusan MealChain atau diimpor dari SAP: "
                    "nomor PO, status, lokasi tujuan, pemasok, bahan, jumlah kg, harga per kg, "
                    "total nilai, dan keputusan asalnya. Baca-saja; dokumen PDF-nya diunduh di "
                    "UI MealChain, bukan dari chat."
                ),
                tags=["po", "purchase order", "pesanan pembelian", "pemasok", "sap"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_DIRECTORY,
                name="Direktori pemasok SPPG",
                description=(
                    "Daftar pemasok yang melayani tiap SPPG: komoditas, keandalan, "
                    "kapasitas mingguan, dan status kiriman aktif. Termasuk penanda "
                    "pemasok yang dikecualikan di hub-nya. Baca-saja."
                ),
                tags=["pemasok", "supplier", "direktori", "vendor", "sppg"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_PRICE,
                name="Harga dan kuotasi pemasok",
                description=(
                    "Harga acuan per kilogram per SPPG dan komoditas beserta sumber dan waktu "
                    "pencatatannya, ditambah kuotasi harga terbaru dari pemasok. Baca-saja; "
                    "jembatan tidak menghitung termurah atau rata-rata."
                ),
                tags=["harga", "price", "kuotasi", "quote", "tarif", "pemasok"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_DEMAND,
                name="Kebutuhan dan prakiraan",
                description=(
                    "Kebutuhan (kg) per SPPG dan komoditas, batas waktu pemenuhannya, serta "
                    "prakiraan kebutuhan dari model backend lengkap dengan metode dan tingkat "
                    "keyakinannya."
                ),
                tags=["kebutuhan", "demand", "prakiraan", "forecast", "proyeksi"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_LOSS,
                name="Kehilangan pangan dan pengalihan limbah",
                description=(
                    "Limbah pangan yang tercatat, yang sudah dialihkan ke mitra pengolahan, dan "
                    "yang belum punya mitra — beserta daftar mitra dan periodenya."
                ),
                tags=["limbah", "waste", "kehilangan", "susut", "pemborosan"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_SUPPLIER_RISK,
                name="Risiko pemasok dan rute kiriman",
                description=(
                    "Eksklusi pemasok di hub (aktif maupun dicabut) beserta alasannya, dan "
                    "kiriman aktif dengan jarak jalan, durasi, serta keadaan perjalanannya."
                ),
                tags=["eksklusi", "exclusion", "rute", "route", "jarak", "pemasok"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_EVIDENCE,
                name="Bukti dan jejak keputusan",
                description=(
                    "Berkas bukti satu keputusan: tanda tangan kriptografis dan hasil "
                    "verifikasinya, alamat isi (content address), rantai iterasi termasuk "
                    "penolakan, dan jejak langkah agen beserta tool yang dipanggil."
                ),
                tags=["bukti", "evidence", "jejak", "audit", "dossier", "tanda tangan"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_SYSTEM,
                name="Status integrasi, ledger, dan jaringan",
                description=(
                    "Status komponen integrasi (SAP AI Core, mock SAP, AgentCore, observability) "
                    "apa adanya, verifikasi rantai blok ledger bukti, ringkasan purchase order, "
                    "dan daftar SPPG yang terdaftar."
                ),
                tags=["integrasi", "integration", "ledger", "status sistem", "kesiapan"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
        ],
        defaultInputModes=modalitas,
        defaultOutputModes=["text/markdown"],
    )


def cors_origins() -> list[str]:
    """Origin CORS: `MEALCHAIN_BRIDGE_CORS_ORIGINS` (dipisah koma), default `*` untuk demo."""
    mentah = os.environ.get("MEALCHAIN_BRIDGE_CORS_ORIGINS", "*")
    return [origin.strip() for origin in mentah.split(",") if origin.strip()]


def build_app(
    client_factory: Callable[[], ReadOnlyBackend] = default_client_factory,
    app_url: str | None = None,
) -> FastAPI:
    """Bangun aplikasi A2A + `/health`. `client_factory` disuntik test (`FakeClient`)."""
    handler = DefaultRequestHandler(
        agent_executor=MealchainExecutor(client_factory),
        task_store=InMemoryTaskStore(),
    )
    fastapi_app = A2AFastAPIApplication(
        agent_card=agent_card(app_url or public_url()), http_handler=handler
    ).build()

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @fastapi_app.get("/health")
    def health() -> dict[str, Any]:
        """Selalu 200 selama aplikasi hidup (Cloud Foundry memakainya untuk health check).

        Keterjangkauan backend MealChain dilaporkan sebagai DATA, bukan sebagai status HTTP:
        kalau endpoint ini ikut gagal saat backend mati, Cloud Foundry akan me-restart aplikasi
        berulang kali padahal yang bermasalah bukan aplikasi ini.
        """
        hasil: dict[str, Any] = {"status": "ok", "service": "mealchain-joule-bridge"}
        try:
            with client_factory() as client:
                hasil["backend"] = {"reachable": True, **(client.health() or {})}
        except MealchainUnavailable as exc:
            hasil["backend"] = {"reachable": False, "detail": str(exc)}
        return hasil

    return fastapi_app


app = build_app()


if __name__ == "__main__":  # jalur lokal; di Cloud Foundry dipakai `command:` di manifest.yml
    uvicorn = __import__("uvicorn")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", DEFAULT_PORT)))
