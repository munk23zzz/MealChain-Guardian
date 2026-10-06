"""Paket AI provider layer Sprint 3 (S3-05+).

Semua panggilan model eksternal (verifier, forecast, supervisor) lewat
shared resilience chain di `resilience` — dilarang membuat logika
fallback paralel di call site lain.
"""
