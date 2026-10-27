"""Guardian (Safety/Freshness) menilai batch SUMBER + exclusion ber-cakupan.

Bug yang direproduksi (AUD-9B-29, P0):

1. `SafetyWorker`/`FreshnessWorker` menyaring batch dengan `context.location`,
   yaitu lokasi **tujuan** keputusan. Batch yang benar-benar dikirim untuk
   keputusan itu ada di lokasi **sumber** (`approval-summary.source_location`,
   atau himpunan `batch_ids` yang terikat di bukti keputusan). Akibatnya batch
   sumber berstatus `fail`/kedaluwarsa/dikarantina tidak terlihat sama sekali,
   sementara batch tujuan yang aman dilaporkan "pass".
2. Hitungan exclusion tidak melihat cakupan: SELAMA ada satu baris exclusion
   `active` di DB, setiap review mendapat `blocking=True` — termasuk review
   keputusan yang pemasok/lokasinya sama sekali lain (probe e7150da4 dan
   3e2e3cc7: `active_exclusion_ids=['55bb6ed8…']` padahal exclusion itu milik
   CV Ambarawa Telur Utama untuk SPPG Jakarta).

Kontrak yang dikunci di sini:

- batch sumber teridentifikasi → dipakai; batch tujuan TIDAK pernah dipakai
  sebagai pengganti;
- sumber tak dapat diidentifikasi (tanpa id batch terikat, tanpa lokasi
  sumber, batch terikat hilang dari `/batches`) → **fail-closed**: `degraded`
  + `blocking=True`, bukan "aman";
- exclusion hanya memveto bila cakupannya cocok: `supplier_id` sama dengan
  pemasok keputusan DAN `scope_location_id` sama dengan lokasi tujuan;
- exclusion yang cakupannya tidak dapat dibuktikan (baris tanpa kolom cakupan,
  atau konteks tanpa identitas) tetap memveto — sikap konservatif, bukan
  pelonggaran;
- ambang bisnis tidak berubah: freshness tetap 0,85/0,60, safety tetap
  `pass`/`pending`/`needs_verification`/`fail`.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("agent")

from agent.orchestrator import context_from_approval  # noqa: E402
from agent.workers.base import WorkerContext  # noqa: E402
from agent.workers.freshness import FreshnessWorker  # noqa: E402
from agent.workers.safety import SafetyWorker  # noqa: E402

LOKASI = {
    "Jakarta": "loc-jakarta",
    "Bandung": "loc-bandung",
    "Cianjur": "loc-cianjur",
}
SUP_TELUR_CIANJUR = "sup-telur-cianjur"
SUP_TELUR_AMBARAWA = "sup-telur-ambarawa"
SUP_AYAM_JAKARTA = "sup-ayam-jakarta"
EXCLUSION_JAKARTA_TELUR = "exc-jakarta-telur"


class FakeApi:
    """Transport tiruan: hanya `semua_batch()` dan `get()` seperti klien nyata."""

    def __init__(self, batches: list[dict], exclusions: list[dict] | None = None) -> None:
        self.batches = batches
        self.exclusions = exclusions if exclusions is not None else []
        self.calls: list[str] = []

    def semua_batch(self, page_size: int = 500, max_rows: int = 5000) -> list[dict]:
        self.calls.append("/batches")
        return list(self.batches)

    def get(self, path: str) -> dict:
        self.calls.append(path)
        if path == "/supplier-exclusions":
            return {"items": list(self.exclusions), "count": len(self.exclusions)}
        raise AssertionError(f"GET tak terduga: {path}")


def _batch(
    batch_id: str,
    location: str,
    commodity: str,
    *,
    safety_status: str = "pass",
    quarantine_status: str = "none",
    freshness_score: float = 0.95,
    usable_until: str = "2099-01-01T00:00:00+00:00",
    supplier_id: str | None = None,
) -> dict:
    baris = {
        "id": batch_id,
        "location": location,
        "location_id": LOKASI[location],
        "commodity": commodity,
        "safety_status": safety_status,
        "quarantine_status": quarantine_status,
        "freshness_score": freshness_score,
        "usable_until": usable_until,
    }
    if supplier_id is not None:
        baris["supplier_id"] = supplier_id
    return baris


def _exclusion(
    exclusion_id: str = EXCLUSION_JAKARTA_TELUR,
    *,
    supplier_id: str | None = SUP_TELUR_AMBARAWA,
    scope_location_id: str | None = None,
    status: str = "active",
) -> dict:
    item = {"id": exclusion_id, "status": status}
    if supplier_id is not None:
        item["supplier_id"] = supplier_id
    if scope_location_id is not None:
        item["scope_location_id"] = scope_location_id
    return item


def _context(
    api: FakeApi,
    *,
    location: str = "Bandung",
    commodity: str = "telur",
    source_location: str | None = "Cianjur",
    supplier_id: str | None = SUP_TELUR_CIANJUR,
    target_location_id: str | None = None,
    source_batch_ids: tuple[str, ...] = (),
) -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id="decision-1",
        location=location,
        commodity=commodity,
        source_location=source_location,
        supplier_id=supplier_id,
        target_location_id=target_location_id or LOKASI[location],
        source_batch_ids=source_batch_ids,
        api=api,
    )


# --------------------------------------------------------------------------
# (a) batch sumber `fail` harus dinilai, bukan batch tujuan
# --------------------------------------------------------------------------


def test_safety_menilai_batch_sumber_bukan_lokasi_tujuan() -> None:
    api = FakeApi(
        [
            # Tujuan: tiga batch aman (dipakai versi lama → "pass").
            _batch("bdg-1", "Bandung", "telur"),
            _batch("bdg-2", "Bandung", "telur"),
            _batch("bdg-3", "Bandung", "telur"),
            # Sumber: satu batch FAIL, satu kedaluwarsa, satu dikarantina.
            _batch("cjr-fail", "Cianjur", "telur", safety_status="fail"),
            _batch(
                "cjr-quarantine",
                "Cianjur",
                "telur",
                quarantine_status="quarantined",
            ),
            _batch("cjr-pass", "Cianjur", "telur"),
        ]
    )

    finding = SafetyWorker().run(_context(api))

    assert finding.facts["location"] == "Bandung"  # tujuan tetap disebut
    assert finding.facts["source_location"] == "Cianjur"
    assert finding.facts["batch_count"] == 3  # tiga batch SUMBER
    assert finding.facts["failed_count"] == 1
    assert finding.facts["failed_batch_ids"] == ["cjr-fail"]
    assert finding.facts["quarantined_count"] == 1
    assert finding.facts["quarantined_batch_ids"] == ["cjr-quarantine"]
    assert finding.blocking is True


def test_freshness_menilai_batch_sumber_bukan_lokasi_tujuan() -> None:
    api = FakeApi(
        [
            _batch("bdg-1", "Bandung", "telur", freshness_score=0.95),
            _batch(
                "cjr-expired",
                "Cianjur",
                "telur",
                freshness_score=0.20,
                usable_until="2020-01-01T00:00:00+00:00",
            ),
            _batch("cjr-segar", "Cianjur", "telur", freshness_score=0.93),
        ]
    )

    finding = FreshnessWorker().run(_context(api))

    assert finding.facts["location"] == "Bandung"
    assert finding.facts["source_location"] == "Cianjur"
    assert finding.facts["batch_count"] == 2
    assert finding.facts["expired_batch_ids"] == ["cjr-expired"]
    assert finding.facts["worst_freshness_score"] == 0.20
    assert finding.blocking is True


def test_batch_terikat_menentukan_himpunan_sumber() -> None:
    """Binding eksplisit menang: batch fail di lokasi sumber yang TIDAK dikirim
    tidak boleh memveto pengiriman batch lain (paritas `batch_sumber_transfer`)."""
    api = FakeApi(
        [
            _batch("cjr-fail", "Cianjur", "telur", safety_status="fail"),
            _batch("cjr-dikirim", "Cianjur", "telur"),
        ]
    )

    finding = SafetyWorker().run(_context(api, source_batch_ids=("cjr-dikirim",)))

    assert finding.facts["batch_count"] == 1
    assert finding.facts["failed_count"] == 0
    assert finding.blocking is False


# --------------------------------------------------------------------------
# (b) batch sumber dikarantina / hilang
# --------------------------------------------------------------------------


def test_safety_batch_sumber_dikarantina_memblokir() -> None:
    api = FakeApi(
        [_batch("cjr-q", "Cianjur", "telur", quarantine_status="quarantined")]
    )

    finding = SafetyWorker().run(_context(api))

    assert finding.facts["quarantined_count"] == 1
    assert finding.facts["quarantined_batch_ids"] == ["cjr-q"]
    assert finding.blocking is True


def test_safety_batch_terikat_hilang_fail_closed() -> None:
    """Binding menunjuk batch yang tidak ada di `/batches` → tidak boleh lolos."""
    api = FakeApi([_batch("cjr-lain", "Cianjur", "telur")])

    finding = SafetyWorker().run(_context(api, source_batch_ids=("cjr-hantu",)))

    assert finding.status == "degraded"
    assert finding.blocking is True
    assert finding.facts["batch_count"] is None
    assert any("terikat" in w for w in finding.warnings)


# --------------------------------------------------------------------------
# (c) exclusion lokasi/pemasok lain TIDAK memveto
# --------------------------------------------------------------------------


def test_exclusion_lokasi_lain_tidak_memveto() -> None:
    api = FakeApi(
        [
            _batch("cjr-1", "Cianjur", "telur"),
            _batch("cjr-2", "Cianjur", "telur"),
        ],
        [_exclusion(scope_location_id=LOKASI["Jakarta"])],
    )

    finding = SafetyWorker().run(_context(api))

    assert finding.blocking is False
    assert finding.facts["active_exclusion_count"] == 0
    assert finding.facts["active_exclusion_ids"] == []
    assert finding.facts["ignored_exclusion_ids"] == [EXCLUSION_JAKARTA_TELUR]


def test_exclusion_pemasok_lain_lokasi_sama_tidak_memveto() -> None:
    """Exclusion Jakarta/telur tidak boleh memveto review Jakarta/ayam."""
    api = FakeApi(
        [_batch("jkt-ayam", "Jakarta", "ayam")],
        [
            _exclusion(
                "exc-jakarta-ayam",
                supplier_id=SUP_AYAM_JAKARTA,
                scope_location_id=LOKASI["Jakarta"],
            )
        ],
    )

    finding = SafetyWorker().run(
        _context(
            api,
            location="Jakarta",
            commodity="ayam",
            source_location="Jakarta",
            supplier_id=SUP_TELUR_CIANJUR,
        )
    )

    assert finding.blocking is False
    assert finding.facts["active_exclusion_count"] == 0


# --------------------------------------------------------------------------
# (d) exclusion yang memang berlaku tetap memveto
# --------------------------------------------------------------------------


def test_exclusion_cakupan_cocok_tetap_memveto() -> None:
    api = FakeApi(
        [_batch("cjr-1", "Cianjur", "telur")],
        [
            _exclusion(
                "exc-bandung-telur",
                supplier_id=SUP_TELUR_CIANJUR,
                scope_location_id=LOKASI["Bandung"],
            )
        ],
    )

    finding = SafetyWorker().run(_context(api))

    assert finding.blocking is True
    assert finding.facts["active_exclusion_count"] == 1
    assert finding.facts["active_exclusion_ids"] == ["exc-bandung-telur"]
    assert finding.facts["ignored_exclusion_ids"] == []


def test_exclusion_tanpa_kolom_cakupan_tidak_lolos_diam_diam() -> None:
    """Baris exclusion tanpa `supplier_id`/`scope_location_id` tidak dapat
    dibuktikan tidak berlaku → tetap memveto (konservatif)."""
    api = FakeApi([_batch("cjr-1", "Cianjur", "telur")], [_exclusion(supplier_id=None)])

    finding = SafetyWorker().run(_context(api))

    assert finding.blocking is True
    assert finding.facts["active_exclusion_count"] == 1
    assert any("cakupan" in w for w in finding.warnings)


# --------------------------------------------------------------------------
# (e) batch sumber tak teridentifikasi → fail-closed
# --------------------------------------------------------------------------


def test_safety_tanpa_identitas_sumber_fail_closed() -> None:
    api = FakeApi([_batch("bdg-1", "Bandung", "telur")])

    finding = SafetyWorker().run(
        _context(api, source_location=None, supplier_id=None, source_batch_ids=())
    )

    assert finding.status == "degraded"
    assert finding.blocking is True
    assert finding.facts["batch_count"] is None
    assert any("sumber" in w for w in finding.warnings)


def test_freshness_tanpa_identitas_sumber_fail_closed() -> None:
    api = FakeApi([_batch("bdg-1", "Bandung", "telur")])

    finding = FreshnessWorker().run(
        _context(api, source_location=None, supplier_id=None, source_batch_ids=())
    )

    assert finding.status == "degraded"
    assert finding.blocking is True
    assert finding.facts["batch_count"] is None
    assert any("sumber" in w for w in finding.warnings)


def test_konteks_tidak_memakai_lokasi_tujuan_sebagai_sumber() -> None:
    """Tanpa lokasi sumber, batch tujuan tidak boleh dipakai sebagai pengganti."""
    api = FakeApi(
        [_batch("bdg-1", "Bandung", "telur", safety_status="fail")]
    )

    finding = SafetyWorker().run(
        _context(api, source_location=None, source_batch_ids=())
    )

    assert finding.facts["batch_count"] is None
    assert finding.facts["failed_count"] is None
    assert finding.blocking is True


# --------------------------------------------------------------------------
# Konteks dari approval-summary: identitas sumber masuk ke worker
# --------------------------------------------------------------------------


def test_context_dari_approval_summary_membawa_identitas_sumber() -> None:
    summary = {
        "target_location": "Bandung",
        "source_location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": 600.0,
        "target_location_id": LOKASI["Bandung"],
        "source_location_id": LOKASI["Cianjur"],
        "supplier": {"id": SUP_TELUR_CIANJUR, "name": "UD H. Asep Cianjur"},
        "safety": {"batch_ids": ["cjr-1", "cjr-2"]},
    }

    context = context_from_approval("decision-1", summary)

    assert context.location == "Bandung"
    assert context.source_location == "Cianjur"
    assert context.target_location_id == LOKASI["Bandung"]
    assert context.source_location_id == LOKASI["Cianjur"]
    assert context.supplier_id == SUP_TELUR_CIANJUR
    assert context.source_batch_ids == ("cjr-1", "cjr-2")
