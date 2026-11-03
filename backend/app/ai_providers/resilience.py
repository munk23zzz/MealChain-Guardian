"""Shared resilience chain (S3-05).

SATU jalur fallback terbatas untuk semua external model call:
primary → fallback_1 → fallback_2 → fallback_3 → ProviderUnavailableError.

Kontrak (plan §S3-05):
- eksekusi sekuensial; provider sukses pertama menghentikan chain
- kategori error dipertahankan, tidak ada misclassifikasi massal
  (mis. HTTP 402 ≠ balance exhaustion)
- 429 = rate_limited = retryable, retry dibatasi per provider
- timeout per provider dibatasi (timeout_seconds, thread-based)
- setiap attempt tercatat eksplisit (name, outcome, category, error)
- circuit breaker opsional (protocol allow/record) dapat men-skip
  provider yang open tanpa memanggilnya
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Callable, Protocol

__all__ = [
    "ProviderAttempt",
    "ProviderResult",
    "ProviderUnavailableError",
    "classify_provider_error",
    "provider_slot_index",
    "with_fallback_chain",
]


class ProviderUnavailableError(RuntimeError):
    """Semua provider dalam chain gagal/tidak tersedia."""

    def __init__(self, attempts: list["ProviderAttempt"]) -> None:
        self.attempts = attempts
        names = ", ".join(f"{a.name}({a.category})" for a in attempts) or "no attempts"
        super().__init__(f"semua provider gagal: {names}")


class _CircuitBreaker(Protocol):
    """Protocol opsional: allow(name) -> bool, record(name, ok) -> None."""

    def allow(self, name: str) -> bool: ...

    def record(self, name: str, ok: bool) -> None: ...


def classify_provider_error(exc: BaseException) -> str:
    """Klasifikasi kategori error provider secara konservatif.

    402 tetap http_402 (bukan otomatis "balance"), 429 = rate_limited.
    """
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status == 402:
            return "http_402"
        if status == 429:
            return "rate_limited"
        if status == 401 or status == 403:
            return "auth"
        if status == 408 or status == 504:
            return "timeout"
        if 500 <= status < 600:
            return "server"
        return f"http_{status}"
    if isinstance(exc, TimeoutError):
        return "timeout"
    return "unknown"


_RETRYABLE_CATEGORIES = frozenset({"rate_limited", "timeout", "server"})

# Pemetaan nama pemenang posisional → indeks slot (dipakai client untuk
# translasi label jujur slot:kind; helper terpusat agar konsisten).
def provider_slot_index(name: str) -> int:
    """`primary` → 0, `fallback_N` → N; selain itu → 0 (aman)."""
    if name == "primary":
        return 0
    if name.startswith("fallback_"):
        try:
            return int(name.split("_", 1)[1])
        except ValueError:
            return 0
    return 0



def _attempt_call(
    fn: Callable[[str], str],
    prompt: str,
    timeout_seconds: float | None,
) -> tuple[str, str | None, str | None, str | None]:
    """Panggil satu provider. Return (outcome, text, category, error_message).

    outcome: "succeeded" | "failed". Exception ditangkap sekali di sini —
    provider TIDAK pernah dipanggil ulang hanya untuk pesan error.
    """
    if timeout_seconds is None:
        try:
            return "succeeded", fn(prompt), None, None
        except Exception as exc:  # noqa: BLE001 - batas chain yang menentukan
            return "failed", None, classify_provider_error(exc), str(exc)

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn, prompt)
    try:
        text = future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        return "failed", None, "timeout", "timeout"
    except Exception as exc:  # noqa: BLE001
        executor.shutdown(wait=False, cancel_futures=True)
        return "failed", None, classify_provider_error(exc), str(exc)
    else:
        executor.shutdown(wait=False)
        return "succeeded", text, None, None


@dataclass
class ProviderAttempt:
    """Satu attempt terhadap satu provider dalam chain."""

    name: str
    outcome: str  # "succeeded" | "failed" | "skipped_circuit_open"
    category: str | None = None
    error: str | None = None
    duration_seconds: float | None = None


@dataclass
class ProviderResult:
    """Hasil chain: teks + jejak provider eksplisit."""

    text: str
    provider: str
    fallback_used: bool
    attempts: list[ProviderAttempt] = field(default_factory=list)


def with_fallback_chain(
    primary: Callable[[str], str],
    prompt: str,
    *,
    fallback_1: Callable[[str], str] | None = None,
    fallback_2: Callable[[str], str] | None = None,
    fallback_3: Callable[[str], str] | None = None,
    fallbacks: list[Callable[[str], str]] | None = None,
    timeout_seconds: float | None = None,
    retry_policy: dict | None = None,
    circuit_breaker: _CircuitBreaker | None = None,
) -> ProviderResult:
    """Jalankan chain fallback atas callable provider sinkron.

    `fallbacks` (list) untuk chain panjang — label otomatis
    fallback_1..N; bila dipakai, kwargs fallback_1..3 diabaikan
    (kompatibilitas lama tetap hidup tanpa `fallbacks`).
    """
    if fallbacks is not None:
        labeled = [
            (f"fallback_{index}", fn)
            for index, fn in enumerate(fallbacks, start=1)
            if fn is not None
        ]
    else:
        labeled = [
            (label, fn)
            for label, fn in (
                ("fallback_1", fallback_1),
                ("fallback_2", fallback_2),
                ("fallback_3", fallback_3),
            )
            if fn is not None
        ]
    chain: list[tuple[str, Callable[[str], str]]] = [("primary", primary), *labeled]

    max_retries = 0
    if retry_policy:
        max_retries = int(retry_policy.get("max_retries", 0))

    attempts: list[ProviderAttempt] = []

    for index, (name, fn) in enumerate(chain):
        if circuit_breaker is not None and not circuit_breaker.allow(name):
            attempts.append(
                ProviderAttempt(
                    name=name,
                    outcome="skipped_circuit_open",
                    category="circuit_open",
                )
            )
            continue

        # attempt pertama + retry dibatasi per provider
        tries = 1 + max_retries
        for try_index in range(tries):
            start = time.monotonic()
            outcome, text, category, error_message = _attempt_call(
                fn, prompt, timeout_seconds
            )
            duration = time.monotonic() - start

            if outcome == "succeeded":
                attempts.append(
                    ProviderAttempt(
                        name=name,
                        outcome="succeeded",
                        duration_seconds=duration,
                    )
                )
                if circuit_breaker is not None:
                    circuit_breaker.record(name, True)
                is_fallback = index > 0
                return ProviderResult(
                    text=text,
                    provider=name,
                    fallback_used=is_fallback,
                    attempts=attempts,
                )

            attempts.append(
                ProviderAttempt(
                    name=name,
                    outcome="failed",
                    category=category,
                    error=error_message,
                    duration_seconds=duration,
                )
            )
            if circuit_breaker is not None:
                circuit_breaker.record(name, False)
            # retry hanya untuk kategori retryable
            if category not in _RETRYABLE_CATEGORIES:
                break

    raise ProviderUnavailableError(attempts)
