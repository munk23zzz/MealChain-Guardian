"""Membuat modul di `sap-joule/a2a_server/` bisa diimpor oleh pytest tanpa paket tambahan."""

from __future__ import annotations

import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
