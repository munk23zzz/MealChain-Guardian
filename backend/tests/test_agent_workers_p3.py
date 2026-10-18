"""P3 — Price, Logistics, Evidence: mock transport dan aturan sitasi."""

from uuid import uuid4

from agent.api_client import AgentApiError
from agent.contracts import AgentFinding
from agent.workers.base import WorkerContext, as_number
from agent.workers.evidence import EvidenceWorker
from agent.workers.logistics import LogisticsWorker
from agent.workers.price import PriceWorker


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
    decision_id: str = "decision-1",
    source_location: str | None = None,
    quantity_kg: float | None = None,
) -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id=decision_id,
        location=location,
        commodity=commodity,
        source_location=source_location,
        quantity_kg=quantity_kg,
        api=api,
    )


def _citations(finding: AgentFinding) -> dict[str, object]:
    return {citation.claim: citation.source_value for citation in finding.citations}


def _price_get() -> dict[str, object]:
    return {
        "/price/quotes/Jakarta/telur": {
            "location": "Jakarta",
            "commodity": "telur",
            "quotes": [
                {
                    "id": "q1",
                    "supplier_id": "s1",
                    "supplier_name": "Supplier A",
                    "price_per_kg": 30941.5,
                    "recorded_at": "2026-10-17T10:00:00+00:00",
                }
            ],
            "reference": {
                "id": "r1",
                "price_per_kg": 30305.95,
                "recorded_at": "2026-10-17T00:00:00+00:00",
            },
        },
        "/decisions/decision-1/approval-summary": {
            "decision_id": "decision-1",
            "quantity_kg": 600.0,
            "safe_delivered_cost": 16206000.0,
            "can_execute": False,
            "supplier": {"id": "s1", "name": "Supplier A Cianjur", "reliability_score": 0.92},
            "expiry": {"valid": True, "seconds_remaining": 1000},
        },
    }


def test_price_membaca_quote_deviasi_dan_sdc() -> None:
    api = FakeApi(
        get=_price_get(),
        post={
            "/price/deviation": {
                "deviation_pct": "2.097145939988682090480582196",
                "reference_price": 30305.95,
                "classification": "normal",
                "flagged": False,
            }
        },
    )

    finding = PriceWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.blocking is False
    assert finding.facts["quote_count"] == 1
    assert finding.facts["latest_quote_price"] == 30941.5
    assert finding.facts["reference_price"] == 30305.95
    assert finding.facts["safe_delivered_cost"] == 16206000.0
    assert finding.facts["quantity_kg"] == 600.0
    assert finding.facts["classification"] == "normal"
    assert finding.facts["flagged"] is False
    assert _citations(finding) == {
        "quote_count": 1,
        "latest_quote_price": 30941.5,
        "reference_price": 30305.95,
        "safe_delivered_cost": 16206000.0,
        "quantity_kg": 600.0,
    }
    assert api.post_calls == [
        (
            "/price/deviation",
            {"location": "Jakarta", "commodity": "telur", "supplier_price": 30941.5},
        )
    ]


def test_price_anomali_tidak_menyimpulkan_aman() -> None:
    api = FakeApi(
        get=_price_get(),
        post={
            "/price/deviation": {
                "deviation_pct": "-40.0",
                "reference_price": 30305.95,
                "classification": "anomalous",
                "flagged": True,
            }
        },
    )

    finding = PriceWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["flagged"] is True
    assert finding.facts["classification"] == "anomalous"
    assert any("harga janggal" in warning for warning in finding.warnings)
    assert finding.blocking is False


def test_price_tanpa_referensi_tidak_mengarang_deviasi() -> None:
    get = _price_get()
    get["/price/quotes/Jakarta/telur"] = {
        "quotes": [],
        "reference": None,
    }
    get["/price/Jakarta/telur"] = AgentApiError("HTTP 404", status_code=404)
    api = FakeApi(get=get)

    finding = PriceWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["quote_count"] == 0
    assert finding.facts["reference_price"] is None
    assert finding.facts["deviation_pct"] is None
    assert _citations(finding)["quote_count"] == 0
    assert "latest_quote_price" not in _citations(finding)
    assert api.post_calls == []


def test_price_403_deviasi_tetap_jujur() -> None:
    api = FakeApi(
        get=_price_get(),
        post={"/price/deviation": AgentApiError("HTTP 403", status_code=403)},
    )

    finding = PriceWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["deviation_pct"] is None
    assert finding.facts["safe_delivered_cost"] == 16206000.0
    assert any("deviasi harga" in warning for warning in finding.warnings)


def test_price_supplier_unknown_tidak_ditebak() -> None:
    get = _price_get()
    get["/decisions/decision-1/approval-summary"] = {
        "quantity_kg": 600.0,
        "safe_delivered_cost": 16206000.0,
        "can_execute": False,
        "supplier": None,
        "expiry": {"valid": True},
    }
    api = FakeApi(
        get=get,
        post={
            "/price/deviation": {
                "deviation_pct": "2.0",
                "classification": "normal",
                "flagged": False,
            }
        },
    )

    finding = PriceWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["supplier_name"] is None
    assert any("supplier_unknown" in warning for warning in finding.warnings)


def test_price_tanpa_api_error_bukan_fakta() -> None:
    finding = PriceWorker().run(_context(None))

    assert finding.status == "error"
    assert finding.facts == {}
    assert finding.citations == []


def test_logistics_membaca_rute_dan_jarak() -> None:
    path = "/supplier-routes?commodity=telur&location=Jakarta&limit=50"
    api = FakeApi(
        get={
            path: {
                "routes": [
                    {
                        "supplier_name": "Supplier A Cianjur",
                        "destination_name": "Jakarta",
                        "commodity": "telur",
                        "road": {
                            "distance_km": 110.4,
                            "duration_min": 84.3,
                            "source": "osrm",
                        },
                    },
                    {
                        "supplier_name": "Supplier Bogor-1",
                        "destination_name": "Jakarta",
                        "commodity": "telur",
                        "road": None,
                    },
                ]
            }
        }
    )

    finding = LogisticsWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.facts["route_count"] == 2
    assert finding.facts["with_road_count"] == 1
    assert finding.facts["without_road_count"] == 1
    assert finding.facts["min_distance_km"] == 110.4
    assert finding.facts["max_distance_km"] == 110.4
    assert finding.facts["road_source"] == "osrm"
    assert _citations(finding)["route_count"] == 2
    assert "rute ada tetapi geometri jalan belum tersinkron" in finding.warnings


def test_logistics_estimasi_makassar_dari_server() -> None:
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

    assert finding.status == "ok"
    assert finding.facts["route_count"] == 0
    assert finding.facts["distance_km"] == 1400
    assert finding.facts["estimated_time_min"] == 1680.0
    assert finding.facts["feasible"] is True
    assert "Malang" not in str(finding.model_dump())
    assert api.post_calls == [
        (
            "/logistics/estimate",
            {"source": "Cianjur", "target": "Makassar", "quantity_kg": 600.0},
        )
    ]


def test_logistics_tanpa_rute_dan_sumber_tidak_mengarang() -> None:
    path = "/supplier-routes?commodity=telur&location=Makassar&limit=50"
    api = FakeApi(get={path: {"routes": []}})

    finding = LogisticsWorker().run(_context(api, location="Makassar"))

    assert finding.status == "degraded"
    assert finding.facts["route_count"] == 0
    assert finding.facts["distance_km"] is None if "distance_km" in finding.facts else True
    assert api.post_calls == []


def _evidence_get() -> dict[str, object]:
    return {
        "/decisions/decision-1/dossier": {
            "decision_id": "decision-1",
            "content_address": "mc1-abc",
            "signature": {"state": "signed"},
            "verify": True,
        },
        "/decisions/decision-1/compliance": {
            "decision": {
                "status": "pending_approval",
                "quantity_kg": "600.00",
                "safe_delivered_cost": "16206000.00",
            },
            "evidence": [
                {"evidence_type": "human_inspection", "is_consistent": True},
            ],
            "approvals": [{"role": "sppg_head", "approved": True}],
            "traces": [{"step_name": "DETECT"}, {"step_name": "DECIDE"}],
            "signature": {"state": "signed"},
            "verify": True,
        },
        "/decisions/decision-1/chain": {
            "chain": [
                {"decision_id": "d0", "iteration": 1},
                {"decision_id": "decision-1", "iteration": 2},
            ]
        },
        "/decisions/decision-1/approval-summary": {
            "expiry": {"valid": True},
            "can_execute": False,
        },
        "/ledger/verify": {"valid": True, "blocks": 6637},
    }


def test_evidence_membaca_dossier_chain_dan_ledger() -> None:
    api = FakeApi(get=_evidence_get())

    finding = EvidenceWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.facts["chain_length"] == 2
    assert finding.facts["evidence_count"] == 1
    assert finding.facts["approval_count"] == 1
    assert finding.facts["trace_count"] == 2
    assert finding.facts["inconsistent_evidence_count"] == 0
    assert finding.facts["ledger_blocks"] == 6637
    assert finding.facts["ledger_valid"] is True
    assert finding.facts["signature_verified"] is True
    assert finding.facts["can_execute"] is False
    assert finding.facts["decision_quantity_kg"] == 600.0
    assert finding.facts["decision_safe_delivered_cost"] == 16206000.0
    assert finding.blocking is False
    assert _citations(finding) == {
        "chain_length": 2,
        "evidence_count": 1,
        "approval_count": 1,
        "trace_count": 2,
        "inconsistent_evidence_count": 0,
        "ledger_blocks": 6637,
        "decision_quantity_kg": 600.0,
        "decision_safe_delivered_cost": 16206000.0,
    }


def test_evidence_ledger_rusak_menjadi_blocking() -> None:
    get = _evidence_get()
    get["/ledger/verify"] = {"valid": False, "blocks": 10}
    api = FakeApi(get=get)

    finding = EvidenceWorker().run(_context(api))

    assert finding.status == "ok"
    assert finding.blocking is True
    assert finding.facts["ledger_valid"] is False
    assert any("ledger tidak valid" in warning for warning in finding.warnings)


def test_evidence_tidak_konsisten_menjadi_blocking() -> None:
    get = _evidence_get()
    get["/decisions/decision-1/compliance"] = {
        **get["/decisions/decision-1/compliance"],
        "evidence": [{"evidence_type": "human_inspection", "is_consistent": False}],
    }
    api = FakeApi(get=get)

    finding = EvidenceWorker().run(_context(api))

    assert finding.blocking is True
    assert finding.facts["inconsistent_evidence_count"] == 1


def test_evidence_ledger_hilang_degraded_bukan_nol() -> None:
    get = _evidence_get()
    get["/ledger/verify"] = AgentApiError("HTTP 503", status_code=503)
    api = FakeApi(get=get)

    finding = EvidenceWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["ledger_valid"] is None
    assert finding.facts["ledger_blocks"] is None
    assert "ledger_blocks" not in _citations(finding)
    assert any("validitas ledger tidak tersedia" in warning for warning in finding.warnings)


def test_evidence_decision_404_error() -> None:
    get = _evidence_get()
    get["/decisions/decision-1/dossier"] = AgentApiError("HTTP 404", status_code=404)
    api = FakeApi(get=get)

    finding = EvidenceWorker().run(_context(api))

    assert finding.status == "error"
    assert finding.facts == {}
    assert finding.citations == []


def test_post_compute_hanya_allowlist() -> None:
    from agent.api_client import COMPUTE_ALLOWLIST, MealChainClient

    assert "/price/deviation" in COMPUTE_ALLOWLIST
    assert "/logistics/estimate" in COMPUTE_ALLOWLIST
    assert "/actions/execute" not in COMPUTE_ALLOWLIST
    assert "/evidence/fuse" not in COMPUTE_ALLOWLIST

    client = MealChainClient(base_url="http://invalid", token="dummy")
    try:
        client.post_compute("/actions/execute", {})
    except AgentApiError as exc:
        assert "tidak diizinkan" in str(exc)
    else:
        raise AssertionError("endpoint mutasi tidak boleh lolos")


def test_tujuh_worker_nyata_terdaftar() -> None:
    from agent.contracts import AgentName
    from agent.workers import build_workers

    workers = build_workers()

    assert len(workers) == 7
    assert {worker.name for worker in workers} == set(AgentName)


def test_as_number_tidak_menebak_string_umum() -> None:
    assert as_number("600.00") is None
    assert as_number("600.00", allow_numeric_string=True) == 600.0
    assert as_number("tidak tersedia", allow_numeric_string=True) is None
    assert as_number(True, allow_numeric_string=True) is None


def test_price_403_peran_read_only_dijelaskan_di_fakta() -> None:
    """Token agen read-only ditolak 403 — fakta harus MENYEBUT sebabnya.

    Tanpa ini, `degraded` tercampur antara "data harga tidak ada" dan
    "peran tidak boleh menghitung"; pembaca log tidak bisa membedakannya.
    """
    api = FakeApi(
        get=_price_get(),
        post={
            "/price/deviation": AgentApiError(
                "HTTP 403 pada /price/deviation: role tidak diizinkan",
                status_code=403,
                path="/price/deviation",
            )
        },
    )

    finding = PriceWorker().run(_context(api))

    assert finding.status == "degraded"
    assert finding.facts["deviation_pct"] is None
    assert finding.facts["deviation_unavailable_reason"] == "role_read_only"
    assert any("hanya boleh membaca" in w for w in finding.warnings), finding.warnings
