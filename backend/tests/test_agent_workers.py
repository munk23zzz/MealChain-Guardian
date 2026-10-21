"""P2 — empat worker baca pertama (Supply, Demand, Safety, Freshness).

Transport API di-mock. Tidak ada model, tidak ada DB, tidak ada tulisan.
"""

from uuid import uuid4

import pytest
from agent.api_client import AgentApiError, MealChainClient
from agent.contracts import AgentFinding
from agent.workers.base import WorkerContext
from agent.workers.demand import DemandWorker
from agent.workers.freshness import FreshnessWorker
from agent.workers.safety import SafetyWorker
from agent.workers.supply import SupplyWorker


class FakeApi:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        self.calls.append(path)
        response = self.responses.get(path)
        if response is None:
            raise AssertionError(f"path tak terduga: {path}")
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, dict)
        return response

    def semua_batch(self, page_size: int = 500, max_rows: int = 5000) -> list[dict]:
        """Tiruan paginasi `/batches`: satu halaman, seperti respons nyata tanpa `offset`."""
        respons = self.get("/batches")
        return list(respons.get("batches") or [])


def _context(api: object, location: str = "Jakarta", commodity: str = "telur") -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id="decision-1",
        location=location,
        commodity=commodity,
        api=api,
    )


def _citations(finding: AgentFinding) -> dict[str, object]:
    return {citation.claim: citation.source_value for citation in finding.citations}


def test_supply_membaca_balance_dan_memberi_sitasi_angka() -> None:
    api = FakeApi(
        {
            "/balance/Jakarta/telur": {
                "location": "Jakarta",
                "commodity": "telur",
                "supply_kg": 314.2,
                "demand_kg": 1080.0,
                "surplus_kg": 0.0,
                "shortage_kg": 765.8,
                "status": "shortage",
                "supply_state": "terukur",
                "demand_state": "terukur",
                "data_state": "terukur",
            }
        }
    )

    finding = SupplyWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.blocking is False
    assert finding.facts["supply_kg"] == 314.2
    assert finding.facts["demand_kg"] == 1080.0
    assert finding.facts["shortage_kg"] == 765.8
    assert finding.facts["status"] == "shortage"
    assert _citations(finding) == {
        "supply_kg": 314.2,
        "demand_kg": 1080.0,
        "surplus_kg": 0.0,
        "shortage_kg": 765.8,
    }
    assert api.calls == ["/balance/Jakarta/telur"]


def test_supply_tidak_mengubah_nol_menjadi_data_terukur() -> None:
    api = FakeApi(
        {
            "/balance/Jakarta/telur": {
                "location": "Jakarta",
                "commodity": "telur",
                "supply_kg": 314.2,
                "demand_kg": 0.0,
                "surplus_kg": 314.2,
                "shortage_kg": 0.0,
                "status": "surplus",
                "supply_state": "terukur",
                "demand_state": "tidak_ada_baris",
                "data_state": "sebagian",
            }
        }
    )

    finding = SupplyWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["supply_kg"] == 314.2
    assert finding.facts["demand_kg"] is None
    assert finding.facts["surplus_kg"] is None
    assert finding.facts["shortage_kg"] is None
    assert finding.facts["status"] is None
    assert finding.warnings
    assert _citations(finding) == {"supply_kg": 314.2}


def test_supply_404_menjadi_degraded_tanpa_angka_palsu() -> None:
    api = FakeApi(
        {"/balance/Jakarta/telur": AgentApiError("data tidak ditemukan", status_code=404)}
    )

    finding = SupplyWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["supply_kg"] is None
    assert finding.facts["demand_kg"] is None
    assert finding.citations == []
    assert finding.warnings


def test_demand_membaca_demand_dan_forecast() -> None:
    api = FakeApi(
        {
            "/demand/Jakarta/telur": {
                "quantity_kg": 1080.0,
                "needed_by": "2026-10-20T00:00:00+00:00",
            },
            "/demand/forecast/Jakarta/telur?horizon_days=7": {
                "forecast_qty_kg": 1104.5,
                "method": "statistical",
                "confidence": 0.62,
            },
        }
    )

    finding = DemandWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.blocking is False
    assert finding.facts["quantity_kg"] == 1080.0
    assert finding.facts["forecast_qty_kg"] == 1104.5
    assert finding.facts["forecast_method"] == "statistical"
    assert _citations(finding) == {
        "quantity_kg": 1080.0,
        "forecast_qty_kg": 1104.5,
        "forecast_confidence": 0.62,
    }


def test_demand_forecast_404_tetap_memakai_demand_yang_ada() -> None:
    api = FakeApi(
        {
            "/demand/Jakarta/telur": {
                "quantity_kg": 1080.0,
                "needed_by": "2026-10-20T00:00:00+00:00",
            },
            "/demand/forecast/Jakarta/telur?horizon_days=7": AgentApiError(
                "demand history tidak ditemukan", status_code=404
            ),
        }
    )

    finding = DemandWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["quantity_kg"] == 1080.0
    assert finding.facts["forecast_qty_kg"] is None
    assert finding.facts["forecast_method"] is None
    assert _citations(finding) == {"quantity_kg": 1080.0}
    assert finding.warnings


def test_safety_menandai_fail_dan_exclusion_aktif() -> None:
    api = FakeApi(
        {
            "/batches": {
                "batches": [
                    {
                        "id": "b1",
                        "location": "Jakarta",
                        "commodity": "telur",
                        "safety_status": "fail",
                        "freshness_score": 0.7,
                        "usable_until": "2026-10-20T00:00:00+00:00",
                    },
                    {
                        "id": "b2",
                        "location": "Jakarta",
                        "commodity": "telur",
                        "safety_status": "pass",
                        "freshness_score": 0.9,
                        "usable_until": "2026-10-22T00:00:00+00:00",
                    },
                    {
                        "id": "b3",
                        "location": "Bandung",
                        "commodity": "telur",
                        "safety_status": "fail",
                        "freshness_score": 0.1,
                        "usable_until": "2026-10-19T00:00:00+00:00",
                    },
                ]
            },
            "/supplier-exclusions": {
                "items": [{"id": "e1", "status": "active"}],
                "count": 1,
            },
        }
    )

    finding = SafetyWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.blocking is True
    assert finding.facts["batch_count"] == 2
    assert finding.facts["failed_count"] == 1
    assert finding.facts["failed_batch_ids"] == ["b1"]
    assert finding.facts["active_exclusion_count"] == 1
    assert finding.facts["worst_status"] == "fail"
    assert _citations(finding) == {
        "batch_count": 2,
        "pass_count": 1,
        "pending_count": 0,
        "failed_count": 1,
        "active_exclusion_count": 1,
    }


def test_safety_batches_404_tidak_mengarang_nol() -> None:
    api = FakeApi({"/batches": AgentApiError("gagal", status_code=404)})

    finding = SafetyWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["batch_count"] is None
    assert finding.facts["failed_count"] is None
    assert finding.blocking is False
    assert finding.citations == []
    assert finding.warnings


def test_freshness_menandai_batch_kedaluwarsa() -> None:
    api = FakeApi(
        {
            "/batches": {
                "batches": [
                    {
                        "id": "b1",
                        "location": "Jakarta",
                        "commodity": "telur",
                        "safety_status": "pass",
                        "freshness_score": 0.35,
                        "usable_until": "2020-01-01T00:00:00+00:00",
                    },
                    {
                        "id": "b2",
                        "location": "Jakarta",
                        "commodity": "telur",
                        "safety_status": "pass",
                        "freshness_score": 0.9,
                        "usable_until": "2099-01-01T00:00:00+00:00",
                    },
                ]
            }
        }
    )

    finding = FreshnessWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.blocking is True
    assert finding.facts["batch_count"] == 2
    assert finding.facts["expired_count"] == 1
    assert finding.facts["expired_batch_ids"] == ["b1"]
    assert finding.facts["worst_freshness_score"] == 0.35
    assert _citations(finding) == {
        "batch_count": 2,
        "expired_count": 1,
        "worst_freshness_score": 0.35,
    }


def test_freshness_daftar_kosong_adalah_nol_nyata() -> None:
    api = FakeApi({"/batches": {"batches": []}})

    finding = FreshnessWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["batch_count"] == 0
    assert finding.facts["expired_count"] == 0
    assert finding.facts["worst_freshness_score"] is None
    assert finding.blocking is False
    assert _citations(finding) == {"batch_count": 0, "expired_count": 0}


def test_klien_semua_batch_membaca_semua_halaman(monkeypatch) -> None:
    """`/batches` berplafon 500 (bawaan 50): halaman kedua harus ikut terbaca.

    Regresi nyata: worker kesegaran/keamanan memanggil `/batches` sekali lalu
    menyaring di memori, sehingga batch Jakarta/telur (3 baris) tidak terlihat
    dan laporan menjadi "0 batch" padahal datanya ada.
    """
    from agent.api_client import MealChainClient

    klien = MealChainClient(base_url="http://backend:8000", token="token-uji")
    diminta: list[dict] = []

    def fake_get(path: str, params: dict | None = None) -> dict:
        assert path == "/batches"
        assert params is not None
        diminta.append(params)
        if params["offset"] == 0:
            return {
                "batches": [{"id": "lain", "location": "Medan"}],
                "total": 2,
            }
        return {
            "batches": [{"id": "jkt", "location": "Jakarta"}],
            "total": 2,
        }

    monkeypatch.setattr(klien, "get", fake_get)
    hasil = klien.semua_batch()
    assert [b["id"] for b in hasil] == ["lain", "jkt"]
    assert [p["offset"] for p in diminta] == [0, 1]
    assert all(p["limit"] == 500 for p in diminta)


def test_worker_tanpa_api_tidak_mengarang() -> None:
    finding = SupplyWorker().run(_context(None))

    assert finding.status == "error"
    assert finding.facts == {}
    assert finding.citations == []
    assert finding.warnings


def test_endpoint_p2_semua_read_only() -> None:
    from agent.registry import get_spec

    for name in ("supply", "demand", "safety", "freshness"):
        assert all(
            endpoint.startswith("GET ") for endpoint in get_spec(name).endpoints
        ), name


def test_klien_tanpa_token_menolak() -> None:
    with pytest.raises(AgentApiError, match="missing_config"):
        MealChainClient(token="")


def test_klien_hanya_punya_get() -> None:
    assert not hasattr(MealChainClient, "post")
    assert not hasattr(MealChainClient, "put")
    assert not hasattr(MealChainClient, "delete")
