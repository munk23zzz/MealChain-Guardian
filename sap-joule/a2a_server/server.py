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
import os
import re
from typing import Any, Callable, Mapping, Protocol, Sequence

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps.jsonrpc import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
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
    PAIR_LIMIT,
    MealchainClient,
    MealchainRejected,
    MealchainUnavailable,
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
SKILL_GAP = "unsupported_domain"
SKILL_EVIDENCE = "decision_evidence"
SKILL_SYSTEM = "system_status"
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
    SKILL_EVIDENCE,
    SKILL_SYSTEM,
)

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
    # Domain yang backend-nya BELUM punya endpoint baca. Dijawab jujur sebagai
    # "belum tersedia" — sebelumnya pertanyaan ini dijawab data pasokan, yang
    # tampak benar padahal menjawab hal lain (audit 21 Okt 2026).
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
        SKILL_QUEUE,
        ("approval", "approve", "persetujuan", "setuju", "usulan", "keputusan", "antrean", "queue"),
    ),
    # Risiko pemasok sebelum direktori: "pemasok yang dikecualikan" memuat `pemasok` milik direktori.
    (
        SKILL_SUPPLIER_RISK,
        ("eksklusi", "exclusion", "dikecualikan", "blacklist", "rute", "route", "jarak"),
    ),
    # Harga sebelum direktori: "harga dari pemasok" adalah pertanyaan harga.
    (SKILL_PRICE, ("harga", "price", "kuotasi", "quote", "tarif")),
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
            "health",
        ),
    ),
)

#: Nomor PO kanonik: `MC-<12 hex>` (satu pembentuk, `backend/app/core/po_number`). Dibaca
#: lebih dulu daripada kata kunci mana pun karena bentuknya tidak ambigu.
_PO_NUMBER = re.compile(r"\b(MC-[0-9A-Fa-f]{6,})\b")

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
    def batches(self) -> list[dict[str, Any]]: ...
    def suppliers(self) -> list[dict[str, Any]]: ...
    def locations(self) -> list[dict[str, Any]]: ...
    def balance_map(self, commodity: str) -> dict[str, Any]: ...
    def kpi(self, days: int = ...) -> dict[str, Any]: ...
    def pending_decisions(self) -> list[dict[str, Any]]: ...
    def purchase_orders(self) -> list[dict[str, Any]]: ...
    def supply_point(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def demand(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def demand_forecast(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def price(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def price_quotes(self, location_id: str, commodity: str) -> dict[str, Any]: ...
    def waste_summary(self) -> dict[str, Any]: ...
    def supplier_exclusions(self) -> list[dict[str, Any]]: ...
    def supplier_routes(self) -> dict[str, Any]: ...
    def decision_compliance(self, decision_id: str) -> dict[str, Any]: ...
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
    if any(keyword in teks for keyword in dict(_KEYWORDS)[SKILL_KPI]):
        return SKILL_KPI, {}
    # PO sebelum antrean: "PO mana yang sudah disetujui?" memuat `setuju` milik antrean.
    po = _po_request(pesan)
    if po is not None:
        return SKILL_PO, po
    # Kontrak lama yang harus tetap jalan: "penerimaan barang batch <uuid>" membaca
    # catatan SATU batch lewat `GET /receipts?batch_id=…`, bukan antrean. Diperiksa
    # sebelum kata kunci supaya skill antrean penerimaan tidak mencurinya.
    nomor_batch = _UUID.search(pesan)
    if nomor_batch and any(k in teks for k in _RECEIPT_WORDS):
        return SKILL_SUPPLY, {"batch_id": nomor_batch.group(1)}
    for skill, kata_kunci in _KEYWORDS:
        if skill == SKILL_KPI:  # sudah diperiksa di atas, sebelum PO
            continue
        if not any(keyword in teks for keyword in kata_kunci):
            continue
        payload: dict[str, Any] = {}
        if skill == SKILL_EVIDENCE:
            nomor = _UUID.search(pesan)
            if nomor:
                payload["decision_id"] = nomor.group(1)
        return skill, payload
    # Default = situasi pasokan. Penerimaan barang tetap mungkin diminta tanpa kata kunci
    # skill lain, jadi id batch diambil di sini.
    nomor = _UUID.search(pesan)
    if nomor and any(k in teks for k in _RECEIPT_WORDS):
        return SKILL_SUPPLY, {"batch_id": nomor.group(1)}
    return SKILL_SUPPLY, {}


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
    note = _data_source_note(client)
    if skill == SKILL_KPI:
        return report.kpi_report(client.kpi(), note=note)
    if skill == SKILL_QUEUE:
        return report.approval_queue_report(client.pending_decisions(), note=note)
    if skill == SKILL_RECEIPTS:
        return report.receipts_queue_report(client.receipts_menunggu(), note=note)
    if skill == SKILL_QUARANTINE:
        return report.quarantine_report(client.batches(), note=note)
    if skill == SKILL_GAP:
        return report.unsupported_report(
            "pengiriman barang, surat jalan, atau stok material SAP",
            "backend MealChain belum menyediakan endpoint baca untuk domain ini.",
        )
    if skill == SKILL_PO:
        nomor = str((payload or {}).get("po_number") or "").strip() or None
        return report.purchase_order_report(client.purchase_orders(), po_number=nomor, note=note)
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

    if skill == SKILL_EVIDENCE:
        diminta = str((payload or {}).get("decision_id") or "").strip()
        if diminta:
            ids = [diminta]
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
            except MealchainRejected as exc:
                gagal_ev.append(f"kepatuhan {satu} ({exc})")
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
            cases.append({"id": satu, "compliance": compliance, "chain": rantai, "traces": jejak})
        return report.decision_evidence_report(
            cases,
            note=_gabung(note, ("Tidak terbaca: " + "; ".join(gagal_ev)) if gagal_ev else None),
        )

    if skill == SKILL_SYSTEM:
        return report.system_status_report(
            client.integrations_status(),
            client.ledger_verify(),
            client.po_summary(),
            client.locations(),
            note=note,
        )

    batches = client.batches()
    komoditas = sorted(
        {str(row.get("commodity")) for row in batches if row.get("commodity")}
    )
    balance: dict[str, Mapping[str, Any]] = {}
    gagal: list[str] = []
    for nama in komoditas:
        try:
            balance[nama] = client.balance_map(nama)
        except MealchainRejected as exc:
            # Satu komoditas yang tidak punya data keseimbangan tidak boleh mematikan seluruh
            # laporan: tabel batch (keamanan/kesegaran) tetap berguna. Kekosongannya disebut
            # apa adanya — bukan diisi nol, karena nol terbaca "tidak ada masalah".
            gagal.append(f"{nama} ({exc})")
    if gagal:
        tambahan = (
            "Keseimbangan tidak terbaca untuk: "
            + "; ".join(gagal)
            + " — komoditas itu tidak muncul di tabel keseimbangan, bukan berarti nol."
        )
        note = f"{note}\n\n{tambahan}" if note else tambahan
    laporan = report.supply_report(batches, balance, note=note)

    # Kalau pertanyaannya menyebut SATU SPPG dan SATU komoditas, sebutkan baris sumbernya:
    # `/balance/map` memberi `supply_kg` hasil hitungan backend, `/supply/…` memberi baris
    # pasokan terakhir apa adanya (kg, waktu catat, sumber) — satu panggilan, tanpa agregasi.
    satu = _satu_pasangan(batches, teks or "")
    if satu:
        try:
            titik = client.supply_point(satu["location_id"], satu["commodity"])
        except MealchainRejected:
            titik = {}
        if titik:
            laporan += (
                f"\n\nBaris pasokan terakhir {satu['location']} / {satu['commodity']}: "
                f"{report.kg(titik.get('quantity_kg'))} dicatat "
                f"{report.wib(titik.get('recorded_at'))}, sumber "
                f"{titik.get('source') or report.MISSING}."
            )

    # Penerimaan barang (goods receipt) selalu per batch: `/receipts` mewajibkan `batch_id`.
    # Jalur ini hanya aktif kalau pengguna menyebut satu batch, supaya jembatan tidak
    # memanggil 158 kali untuk seluruh inventaris.
    batch_id = str((payload or {}).get("batch_id") or "").strip()
    if not batch_id:
        return laporan
    try:
        receipts = client.receipts(batch_id)
    except MealchainRejected as exc:
        return f"{laporan}\n\n---\n\n_Penerimaan barang batch {batch_id} tidak terbaca: {exc}_"
    return (
        f"{laporan}\n\n---\n\n"
        + report.receipt_report(receipts, batch_id=batch_id, note=note)
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
