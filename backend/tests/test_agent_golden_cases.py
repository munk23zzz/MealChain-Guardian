"""Sepuluh golden case agent (P3, mock transport).

Kasus 10 menguji API/runtime tidak tersedia pada lapisan worker: tidak ada
kartu/temuan sukses yang dikarang. Kartu UI dan ARN AgentCore baru diuji di P4.
"""

from uuid import uuid4

from agent.api_client import AgentApiError
from agent.workers.base import WorkerContext
from agent.workers.freshness import FreshnessWorker
from agent.workers.logistics import LogisticsWorker
from agent.workers.price import PriceWorker
from agent.workers.safety import SafetyWorker
from agent.workers.supply import SupplyWorker


class FakeApi:
    def __init__(
        self,
        *,
        get: dict[str, object] | None = None,
        post: dict[str, object] | None = None,
    ) -> None:
        self.get_responses = get or {}
        self.post_responses = post or {}
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, path: str) -> dict:
        self.get_calls.append(path)
        response = self.get_responses.get(path)
        if response is None:
            raise AssertionError(f"GET tak terduga: {path}")
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, dict)
        return response

    def post_compute(self, path: str, body: dict) -> dict:
        self.post_calls.append((path, body))
        response = self.post_responses.get(path)
        if response is None:
            raise AssertionError(f"POST tak terduga: {path}")
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, dict)
        return response


def _context(
    api: object,
    *,
    location: str = "Jakarta",
    commodity: str = "telur",
    source_location: str | None = None,
    quantity_kg: float | None = None,
) -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id="decision-1",
        location=location,
        commodity=commodity,
        source_location=source_location,
        quantity_kg=quantity_kg,
        api=api,
    )


def _price_api(
    *,
    flagged: bool = False,
    valid: bool = True,
    supplier: dict | None = None,
) -> FakeApi:
    return FakeApi(
        get={
            "/price/quotes/Jakarta/telur": {
                "quotes": [
                    {
                        "price_per_kg": 30941.5,
                        "supplier_name": "Supplier A",
                    }
                ],
                "reference": {"price_per_kg": 30305.95},
            },
            "/decisions/decision-1/approval-summary": {
                "quantity_kg": 600.0,
                "safe_delivered_cost": 16206000.0,
                "can_execute": valid,
                "supplier": supplier if supplier is not None else {"name": "Koperasi Telur Cipanas Bersama"},
                "expiry": {"valid": valid},
            },
        },
        post={
            "/price/deviation": {
                "deviation_pct": "-40.0" if flagged else "2.0",
                "classification": "anomalous" if flagged else "normal",
                "flagged": flagged,
            }
        },
    )


def test_golden_01_shortage_jakarta() -> None:
    api = FakeApi(
        get={
            "/balance/Jakarta/telur": {
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

    assert finding.facts["supply_kg"] == 314.2
    assert finding.facts["demand_kg"] == 1080.0
    assert finding.facts["shortage_kg"] == 765.8
    assert finding.facts["status"] == "shortage"


def test_golden_02_surplus_cianjur_bukan_nol_palsu() -> None:
    api = FakeApi(
        get={
            "/balance/Cianjur/telur": {
                "supply_kg": 1457.37,
                "demand_kg": 0.0,
                "surplus_kg": 1457.37,
                "shortage_kg": 0.0,
                "status": "surplus",
                "supply_state": "terukur",
                "demand_state": "terukur",
                "data_state": "terukur",
            }
        }
    )

    finding = SupplyWorker().run(_context(api, location="Cianjur"))

    assert finding.status == "ok"
    assert finding.facts["demand_kg"] == 0.0
    assert finding.facts["surplus_kg"] == 1457.37
    assert finding.facts["status"] == "surplus"


def test_golden_03_rute_makassar_tidak_menyebut_malang() -> None:
    path = "/supplier-routes?commodity=telur&location=Makassar&limit=50"
    api = FakeApi(
        get={path: {"routes": []}},
        post={
            "/logistics/estimate": {
                "distance_km": 1400,
                "estimated_time_min": 1680.0,
                "feasible": True,
            }
        },
    )

    finding = LogisticsWorker().run(
        _context(api, location="Makassar", source_location="Cianjur", quantity_kg=600.0)
    )

    assert finding.facts["distance_km"] == 1400
    assert finding.facts["feasible"] is True
    assert "Malang" not in str(finding.model_dump())


def test_golden_04_safety_fail_blocking() -> None:
    api = FakeApi(
        get={
            "/batches": {
                "batches": [
                    {
                        "id": "b1",
                        "location": "Jakarta",
                        "commodity": "telur",
                        "safety_status": "fail",
                    }
                ]
            },
            "/supplier-exclusions": {"items": []},
        }
    )

    finding = SafetyWorker().run(_context(api))

    assert finding.facts["failed_count"] == 1
    assert finding.facts["worst_status"] == "fail"
    assert finding.blocking is True


def test_golden_05_freshness_rendah_memberi_warning() -> None:
    api = FakeApi(
        get={
            "/batches": {
                "batches": [
                    {
                        "id": "b1",
                        "location": "Jakarta",
                        "commodity": "telur",
                        "freshness_score": 0.8,
                        "usable_until": "2099-01-01T00:00:00+00:00",
                    }
                ]
            }
        }
    )

    finding = FreshnessWorker().run(_context(api))

    assert finding.facts["worst_freshness_score"] == 0.8
    assert any("0.8" in warning and "aman" in warning for warning in finding.warnings)
    assert finding.blocking is False


def test_golden_06_data_hilang_null_bukan_nol() -> None:
    api = FakeApi(
        get={
            "/balance/Jakarta/telur": {
                "supply_kg": 314.2,
                "demand_kg": 0.0,
                "surplus_kg": 0.0,
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
    assert finding.facts["demand_kg"] is None
    assert finding.facts["surplus_kg"] is None
    assert finding.facts["shortage_kg"] is None
    assert finding.facts["status"] is None
    assert finding.warnings


def test_golden_07_harga_janggal_tidak_aman() -> None:
    finding = PriceWorker().run(_context(_price_api(flagged=True)))

    assert finding.status == "degraded"
    assert finding.facts["flagged"] is True
    assert any("harga janggal" in warning for warning in finding.warnings)


def test_golden_08_supplier_unknown_tidak_ditebak() -> None:
    finding = PriceWorker().run(_context(_price_api(supplier={})))

    assert finding.status == "degraded"
    assert finding.facts["supplier_name"] is None
    assert any("supplier_unknown" in warning for warning in finding.warnings)


def test_golden_09_keputusan_expired_tidak_menyarankan_eksekusi() -> None:
    finding = PriceWorker().run(_context(_price_api(valid=False)))

    assert finding.facts["valid"] is False
    assert finding.facts["can_execute"] is False
    assert any("kedaluwarsa" in warning for warning in finding.warnings)


def test_golden_10_runtime_mati_tidak_mengarang_temuan() -> None:
    finding = PriceWorker().run(_context(None))

    assert finding.status == "error"
    assert finding.facts == {}
    assert finding.citations == []
    assert any("missing_config" in warning for warning in finding.warnings)


def test_golden_10b_client_tanpa_token_menolak() -> None:
    from agent.api_client import MealChainClient

    try:
        MealChainClient(token="")
    except AgentApiError as exc:
        assert "missing_config" in str(exc)
    else:
        raise AssertionError("client tanpa token seharusnya menolak")
