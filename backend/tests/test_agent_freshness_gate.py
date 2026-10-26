"""Gerbang kesegaran CERTIFIED pada worker Freshness (regresi AUD-9A-05).

Sebelum perbaikan: worker hanya membandingkan skor dengan sempurna 1.0 lalu
tetap `ok` untuk skor 0,82 — padahal `backend/app/core/freshness.py` menyebut
0,82 `needs_verification` (PASS >= 0,85, VERIFY >= 0,60). Dua hal yang dikunci
di sini:

1. ambang yang dipakai worker SAMA dengan ambang certified di core (bukan
   angka kembar yang bisa melenceng);
2. skor di bawah PASS dilaporkan sebagai fakta berstatus
   `needs_verification`/`fail`, dan tidak ada warning yang menyimpulkan aman.

`blocking` sengaja tidak diubah di sini: menaikkannya untuk
`needs_verification` akan memveto hampir seluruh putaran demo, jadi itu
keputusan owner (lihat docs/audit/9_AGENT_REPAIR_LOG.md).
"""

from uuid import uuid4  # noqa: I001

import pytest

pytest.importorskip("agent")

from agent.workers.base import WorkerContext  # noqa: E402
from agent.workers.freshness import (  # noqa: E402
    PASS_THRESHOLD,
    VERIFY_THRESHOLD,
    FreshnessWorker,
    classify_freshness,
)

from app.core import freshness as core_freshness  # noqa: E402


class FakeApi:
    def __init__(self, batches: list[dict]) -> None:
        self.batches = batches

    def get(self, path: str) -> dict:  # pragma: no cover - hanya /batches dipakai
        return {"batches": self.batches}

    def semua_batch(self, page_size: int = 500, max_rows: int = 5000) -> list[dict]:
        return list(self.batches)


def _context(api: object) -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id="decision-1",
        location="Jakarta",
        commodity="telur",
        api=api,
    )


def _batch(batch_id: str, score: float, usable_until: str = "2099-01-01T00:00:00+00:00") -> dict:
    return {
        "id": batch_id,
        "location": "Jakarta",
        "commodity": "telur",
        "freshness_score": score,
        "usable_until": usable_until,
    }


def test_ambang_kesegaran_worker_sama_dengan_core() -> None:
    """Angka worker harus identik dengan gerbang certified di backend."""
    assert PASS_THRESHOLD == core_freshness.PASS_THRESHOLD
    assert VERIFY_THRESHOLD == core_freshness.VERIFY_THRESHOLD
    for skor in (0.0, 0.59, 0.6, 0.82, 0.849, 0.85, 1.0):
        assert classify_freshness(skor) == core_freshness.classify_freshness(skor), skor


def test_skor_082_dilaporkan_needs_verification_bukan_aman() -> None:
    """Kasus runtime audit: 3 batch, skor terburuk 0,82."""
    api = FakeApi([_batch("b1", 0.82), _batch("b2", 0.93), _batch("b3", 0.96)])

    finding = FreshnessWorker().run(_context(api))

    assert finding.facts["worst_freshness_score"] == 0.82
    assert finding.facts["freshness_status"] == "needs_verification"
    assert "needs_verification" in finding.summary
    # Fakta certified wajib muncul sebagai warning yang menyebut verifikasi.
    assert any(
        "needs_verification" in w and "verifikasi" in w for w in finding.warnings
    )
    # Tidak boleh ada lagi warning yang hanya bilang "belum sempurna".
    assert not any("belum sempurna" in w for w in finding.warnings)


def test_skor_di_bawah_verify_threshold_berstatus_fail() -> None:
    api = FakeApi([_batch("b1", 0.35), _batch("b2", 0.9)])

    finding = FreshnessWorker().run(_context(api))

    assert finding.facts["freshness_status"] == "fail"
    # Batch b1 belum lewat `usable_until`, jadi `blocking` tetap False:
    # ambang fail saja BUKAN veto (lihat catatan modul).
    assert finding.blocking is False
    assert any("fail" in w and "verifikasi" in w for w in finding.warnings)


def test_skor_pass_tetap_pass_dan_tidak_memblokir() -> None:
    api = FakeApi([_batch("b1", 0.95), _batch("b2", 0.9)])

    finding = FreshnessWorker().run(_context(api))

    assert finding.facts["freshness_status"] == "pass"
    assert finding.status == "ok"
    assert finding.blocking is False


def test_batch_kedaluwarsa_tetap_memblokir() -> None:
    api = FakeApi([_batch("b1", 0.3, usable_until="2020-01-01T00:00:00+00:00")])

    finding = FreshnessWorker().run(_context(api))

    assert finding.facts["expired_count"] == 1
    assert finding.blocking is True
