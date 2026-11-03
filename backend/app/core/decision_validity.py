"""Validitas decision deterministik (Task 11 Sprint 2).

Kontrak plan:
- now < expires_at → valid; now >= expires_at → expired (exact = expired).
- Kedua timestamp wajib timezone-aware; naive/mixed ditolak ValueError.
- Expired tetap tersimpan untuk audit (persistence tidak menghapus),
  tidak dapat dipakai ulang sebagai kandidat/rekomendasi aktif.
"""

from datetime import datetime

__all__ = ["is_decision_valid"]


def is_decision_valid(now: datetime, expires_at: datetime) -> bool:
    if not isinstance(now, datetime) or not isinstance(expires_at, datetime):
        raise ValueError("now dan expires_at wajib datetime")
    if now.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError(
            "now dan expires_at wajib timezone-aware (naive ditolak)"
        )
    return now < expires_at
