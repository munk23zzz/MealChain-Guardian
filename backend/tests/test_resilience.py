"""Test shared resilience chain (S3-05, TDD).

Satu jalur fallback terbatas untuk SEMUA external model call:
primary → fallback_1 → fallback_2 → fallback_3 → ProviderUnavailableError.

Kontrak deterministik:
- provider sukses pertama menghentikan chain (eksekusi sekuensial)
- kategori error dipertahankan; HTTP 402 TIDAK otomatis dilabeli
  "balance exhaustion"
- 429 = rate_limited = retryable; retry dibatasi per provider
- timeout per provider dibatasi (timeout_seconds)
- status provider eksplisit: attempted/succeeded per attempt
- circuit breaker (opsional) bisa men-skip provider yang open

Plan: .hermes/plans/2026-10-06-sprint3-agent-layer.md §S3-05.
"""

import time

import pytest

from app.ai_providers.resilience import (
    ProviderUnavailableError,
    classify_provider_error,
    with_fallback_chain,
)


class HTTPishError(Exception):
    """Exception dengan status_code ala HTTP untuk klasifikasi."""

    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(message or f"http {status_code}")
        self.status_code = status_code


def test_primary_success_no_fallback():
    calls = []

    def primary(prompt):
        calls.append("primary")
        return "P"

    def fallback_1(prompt):  # pragma: no cover - tidak boleh dipanggil
        calls.append("fallback_1")
        return "F1"

    result = with_fallback_chain(primary=primary, fallback_1=fallback_1, prompt="x")

    assert result.text == "P"
    assert result.provider == "primary"
    assert result.fallback_used is False
    assert [(a.name, a.outcome) for a in result.attempts] == [("primary", "succeeded")]
    assert calls == ["primary"]


def test_primary_failure_falls_back_to_fallback_1():
    def primary(prompt):
        raise RuntimeError("primary down")

    def fallback_1(prompt):
        return "F1"

    result = with_fallback_chain(primary=primary, fallback_1=fallback_1, prompt="x")

    assert result.text == "F1"
    assert result.provider == "fallback_1"
    assert result.fallback_used is True
    assert [(a.name, a.outcome) for a in result.attempts] == [
        ("primary", "failed"),
        ("fallback_1", "succeeded"),
    ]


def test_chain_reaches_fallback_2():
    def primary(prompt):
        raise RuntimeError("down-1")

    def fallback_1(prompt):
        raise RuntimeError("down-2")

    def fallback_2(prompt):
        return "F2"

    result = with_fallback_chain(
        primary=primary, fallback_1=fallback_1, fallback_2=fallback_2, prompt="x"
    )

    assert result.text == "F2"
    assert result.provider == "fallback_2"
    assert [a.outcome for a in result.attempts] == ["failed", "failed", "succeeded"]


def test_all_unavailable_raises_with_attempt_record():
    def boom(msg):
        def _p(prompt):
            raise RuntimeError(msg)

        return _p

    with pytest.raises(ProviderUnavailableError) as excinfo:
        with_fallback_chain(
            primary=boom("a"),
            fallback_1=boom("b"),
            fallback_2=boom("c"),
            prompt="x",
        )

    err = excinfo.value
    assert [a.name for a in err.attempts] == ["primary", "fallback_1", "fallback_2"]
    assert all(a.outcome == "failed" for a in err.attempts)
    # kategori + pesan error asli tersimpan, tidak dihilangkan
    assert err.attempts[0].error is not None
    assert "a" in err.attempts[0].error


def test_error_category_preserved_402_not_balance():
    # HTTP 402 TIDAK boleh otomatis dilabeli balance exhaustion
    assert classify_provider_error(HTTPishError(402, "payment required")) == "http_402"
    assert classify_provider_error(HTTPishError(429, "capacity_saturated")) == "rate_limited"
    assert classify_provider_error(HTTPishError(401)) == "auth"
    assert classify_provider_error(HTTPishError(503)) == "server"
    assert classify_provider_error(TimeoutError("late")) == "timeout"
    assert classify_provider_error(RuntimeError("misterius")) == "unknown"


def test_429_retryable_bounded_retries():
    calls = {"primary": 0, "fallback_1": 0}

    def primary(prompt):
        calls["primary"] += 1
        raise HTTPishError(429, "capacity_saturated")

    def fallback_1(prompt):
        calls["fallback_1"] += 1
        return "F1"

    result = with_fallback_chain(
        primary=primary,
        fallback_1=fallback_1,
        prompt="x",
        retry_policy={"max_retries": 1},
    )

    # 1 panggilan awal + 1 retry (dibatasi), lalu pindah provider
    assert calls["primary"] == 2
    assert calls["fallback_1"] == 1
    assert result.text == "F1"
    assert [a.name for a in result.attempts] == ["primary", "primary", "fallback_1"]


def test_bounded_timeout_moves_to_fallback():
    def slow(prompt):
        time.sleep(0.3)
        return "slow"  # pragma: no cover - tidak akan sempat

    def fast(prompt):
        return "fast"

    result = with_fallback_chain(
        primary=slow, fallback_1=fast, prompt="x", timeout_seconds=0.05
    )

    assert result.text == "fast"
    assert result.attempts[0].outcome == "failed"
    assert result.attempts[0].category == "timeout"


def test_circuit_breaker_open_skips_provider():
    class OpenCB:
        def allow(self, name):
            return name != "primary"

        def record(self, name, ok):
            pass

    def primary(prompt):  # pragma: no cover - harus di-skip
        raise AssertionError("primary open, tidak boleh dipanggil")

    def fallback_1(prompt):
        return "F1"

    result = with_fallback_chain(
        primary=primary, fallback_1=fallback_1, prompt="x", circuit_breaker=OpenCB()
    )

    assert result.text == "F1"
    assert result.attempts[0].outcome == "skipped_circuit_open"
