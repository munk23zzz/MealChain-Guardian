"""Atribusi jejak agen — satu kamus nama agen untuk penulis jejak BACKEND.

Panel "Kualitas per agen" menghitung run per KUNCI TAMPILAN, bukan per nama
kelas agen: kontraknya ada di `frontend/lib/agent-swarm.ts` (SWARM_AGENTS) dan
`frontend/lib/agent-quality.ts` (`agentKeyOf`). Sembilan kuncinya:

    supply, demand, freshness, safety, price, logistics, evidence,
    supervisor, verifier

Selama penyemai demo menulis nama kelas (`detection_agent`, `sap_agent`,
`worker.detect`) atau `NULL`, `agentKeyOf` tidak menemukan kunci yang cocok dan
baris itu tidak dihitung: panel menampilkan 0 "tercatat" untuk semua agen
walaupun jejaknya ada (terukur 4 Nov 2026). Karena itu SETIAP baris jejak yang
mewakili kerja satu agen WAJIB menulis `agent_name` = salah satu dari
`AGENT_KEYS`.

Modul ini murni (tanpa DB/IO) supaya pemetaan bisa diuji sebagai unit dan
dipakai bersama oleh `api/demo.py` dan `seed/demo_template.py`. Frontend TIDAK
diubah: backend yang menyelaraskan diri ke kontrak tampilan.
"""

from __future__ import annotations

#: Kunci tampilan "Kualitas per agen" — urutan pipeline, sama dengan
#: `SWARM_AGENTS` di frontend/lib/agent-swarm.ts. Menambah kunci di sini tanpa
#: menambahkannya di frontend membuat barisnya tak pernah tampil.
AGENT_KEYS: tuple[str, ...] = (
    "supply",
    "demand",
    "freshness",
    "safety",
    "price",
    "logistics",
    "evidence",
    "supervisor",
    "verifier",
)

_AGENT_KEY_SET = frozenset(AGENT_KEYS)

#: Alat pipeline → agen yang benar-benar bekerja. Nama alat adalah bukti
#: PEMILIK baris, jadi ia menang atas tahap: `demand.snapshot` pada tahap
#: DETECT ditulis sebagai `demand`, bukan `supply`.
_TOOL_AGENT: dict[str, str] = {
    "demand.snapshot": "demand",
    "forecast.daily": "demand",
    "price.signal": "price",
    "price_deviation": "price",
    "logistics.status": "logistics",
    "logistics.reroute": "logistics",
    "evidence.crosscheck": "evidence",
    # Suhu adalah bukti KEAMANAN pangan (lihat worker safety), bukan bukti
    # administrasi; menilainya `evidence` membuat panel safety selalu 0.
    "evidence.temperature": "safety",
    "supply_balance.propose": "supply",
    # ACT = eksekusi yang meninggalkan bukti (PO terbit), bukan aksi SAP.
    "purchase_order.commit": "evidence",
    "rejection_loop.repropose": "supervisor",
    "supervisor.narration": "supervisor",
    "agent.review_summary": "supervisor",
}

#: Prefiks alat (`<agen>.<aksi>`) → agen. Dipakai bila nama alat lengkap tidak
#: terdaftar di `_TOOL_AGENT`.
_TOOL_PREFIX_AGENT: dict[str, str] = {
    "supply": "supply",
    "supply_balance": "supply",
    "demand": "demand",
    "forecast": "demand",
    "freshness": "freshness",
    "safety": "safety",
    "price": "price",
    "logistics": "logistics",
    "evidence": "evidence",
    "verifier": "verifier",
    "supervisor": "supervisor",
}

#: Akhiran alat perencanaan pasokan, mis. `telur.supply_gap` — prefiksnya nama
#: komoditas, jadi prefiks saja tidak cukup untuk mengenali supply.
_TOOL_SUFFIX_AGENT: tuple[tuple[str, str], ...] = (
    (".supply_gap", "supply"),
)

#: Tahap → agen bawaan bila alat tidak memberi petunjuk. Selaras dengan
#: `stage` pada SWARM_AGENTS (DETECT=supply, PREDICT=demand, OPTIMIZE=price,
#: TRACE=evidence, SUPERVISE=supervisor) ditambah satu agen per tahap
#: selebihnya supaya tidak ada tahap yang jatuh ke `NULL` lagi.
_STAGE_AGENT: dict[str, str] = {
    "DETECT": "supply",
    "PREDICT": "demand",
    "OPTIMIZE": "price",
    "TRACE": "evidence",
    "SUPERVISE": "supervisor",
    # Keputusan diambil supervisor (satu agen yang menarasikan pilihan).
    "DECIDE": "supervisor",
    # Audit/verifikasi: baris VERIFY tanpa nama adalah audit verifikator.
    "VERIFY": "verifier",
    "ACT": "evidence",
    "LEARN": "evidence",
    "ANALYZE": "evidence",
}

#: Nama lama/kelas agen → kunci kontrak. Dipakai untuk membaca jejak yang sudah
#: tersimpan sebelum perbaikan ini, dan sebagai jaring saat penulis baru lupa
#: memakai kunci kontrak.
_ALIASES: dict[str, str] = {
    "detection": "supply",
    "detection_agent": "supply",
    "screening": "supply",
    "worker.detect": "supply",
    "forecaster": "demand",
    "agent:demand-forecaster": "demand",
    "optimizer": "price",
    "agent:allocation-optimizer": "logistics",
    "agent:safety-supervisor": "safety",
    "orchestrator": "supervisor",
    "sap": "evidence",
    "sap_agent": "evidence",
    "worker.act": "evidence",
    "auditor": "verifier",
    "verifier_agent": "verifier",
    "supervisor_agent": "supervisor",
}


def normalize_agent_name(nama: object) -> str | None:
    """Nama agen apa pun → kunci kontrak, atau `None` bila tak dikenali.

    Menerima kunci kontrak ("supply"), nama kelas berakhiran `_agent`
    ("supervisor_agent"), dan alias lama ("detection_agent", "worker.detect").
    """
    teks = str(nama or "").strip().lower()
    if not teks:
        return None
    if teks in _AGENT_KEY_SET:
        return teks
    if teks in _ALIASES:
        return _ALIASES[teks]
    if teks.endswith("_agent"):
        inti = teks[: -len("_agent")]
        if inti in _AGENT_KEY_SET:
            return inti
        if inti in _ALIASES:
            return _ALIASES[inti]
    return None


def agent_key(step_name: object, tool_called: object = None) -> str:
    """`agent_key_for` yang WAJIB menghasilkan kunci kontrak.

    Dipakai penulis jejak: baris yang tahapnya tidak dikenal harus gagal dengan
    pesan jelas, bukan tersimpan dengan `agent_name` kosong lalu menghitung 0 di
    panel "Kualitas per agen".
    """
    kunci = agent_key_for(step_name, tool_called)
    if kunci is None:
        raise ValueError(
            "tahap jejak tidak punya agen kontrak: "
            f"step_name={step_name!r} tool_called={tool_called!r}"
        )
    return kunci


def agent_key_for(step_name: object, tool_called: object = None) -> str | None:
    """Agen pemilik satu langkah pipeline, menurut kunci tampilan.

    Urutan keputusan: alat (paling spesifik) → prefiks/akhiran alat → tahap.
    `None` hanya bila tahapnya tidak dikenal; tahap yang dikenal SELALU
    menghasilkan kunci kontrak supaya tidak ada baris `agent_name` kosong lagi.
    """
    alat = str(tool_called or "").strip().lower()
    tahap = str(step_name or "").strip().upper()
    # Tahap KEPUTUSAN selalu milik supervisor: alat `supply_balance.propose`
    # hanya menghitung neraca, yang memutuskan dan menarasikan tetap supervisor.
    if tahap in ("DECIDE", "SUPERVISE"):
        return "supervisor"
    if alat:
        if alat in _TOOL_AGENT:
            return _TOOL_AGENT[alat]
        for akhiran, agen in _TOOL_SUFFIX_AGENT:
            if alat.endswith(akhiran):
                return agen
        prefiks = alat.split(".", 1)[0]
        if prefiks in _TOOL_PREFIX_AGENT:
            return _TOOL_PREFIX_AGENT[prefiks]
        # `agent.<kunci>` (jejak runtime) juga memberi tahu pemiliknya.
        if prefiks == "agent":
            sisa = alat.split(".", 1)[1] if "." in alat else ""
            kunci = normalize_agent_name(sisa)
            if kunci is not None:
                return kunci
    return _STAGE_AGENT.get(tahap)
