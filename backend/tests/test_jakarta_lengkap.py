"""Penjaga kontrak seeder `jakarta_lengkap` (data demo Jakarta lengkap).

Fokus tes ini BUKAN menghitung baris (itu tugas probe di laporan), tetapi
mengunci dua hal yang mudah rusak tanpa suara:

1. `agent_name` yang ditulis seeder harus SAMA dengan kunci yang dicocokkan
   `frontend/lib/agent-swarm.ts`. Sebelum ini nilainya "supply_agent" sehingga
   panel Agent Log berkata "Belum ada review 7 agen" walau barisnya ada.
2. Id harus deterministik: menjalankan seeder dua kali tidak boleh menggandakan
   kiriman/keputusan/PO.
"""

import uuid

from app.seed.jakarta_lengkap import PEKERJA, _id


def test_nama_agen_cocok_dengan_kontrak_frontend():
    """Tujuh worker = kunci `SWARM_AGENTS` di frontend, tanpa akhiran _agent."""
    kunci = [k for k, _tahap, _agen in PEKERJA]
    assert kunci == [
        "supply",
        "demand",
        "freshness",
        "safety",
        "price",
        "logistics",
        "evidence",
    ]
    # Tahap tiap worker juga dipakai UI (kartu menampilkan tahapnya).
    tahap = {k: t for k, t, _a in PEKERJA}
    assert tahap["supply"] == "DETECT"
    assert tahap["demand"] == "PREDICT"
    assert tahap["freshness"] == "VERIFY"
    assert tahap["safety"] == "VERIFY"
    assert tahap["price"] == "OPTIMIZE"
    assert tahap["logistics"] == "OPTIMIZE"
    assert tahap["evidence"] == "TRACE"


def test_id_deterministik_dan_berbeda_per_kunci():
    a = _id("batch", "7")
    b = _id("batch", "7")
    c = _id("batch", "8")
    assert a == b, "id yang sama harus menghasilkan UUID yang sama (idempoten)"
    assert a != c
    assert isinstance(a, uuid.UUID)
    # Namespace terpisah dari seeder lain supaya tidak bentrok.
    assert a.version == 5
