"""Probe rantai model agent: slot mana yang benar-benar menjawab (read-only).

Kenapa ada: `GET /agent/supervisor/health` hanya melaporkan `configured` — ia tidak
memanggil provider, jadi rantai bisa tampak 11 slot padahal sebagian besar mati. Skrip ini
memanggil SETIAP slot lewat `build_default_callers()` (kode yang sama dengan produksi) dan
melaporkan OK/GAGAL per slot, sehingga "cadangan" yang tidak berfungsi kelihatan sebelum
demo, bukan saat juri bertanya.

Jalankan di container (env backend lengkap):

    docker exec mealchain-backend python /app/scripts/probe_rantai_model_agent.py

Tidak menulis data aplikasi dan tidak mencetak kredensial. Prompt sengaja satu kata
(`Jawab satu kata: ok`) supaya biayanya kecil.
"""

from __future__ import annotations

import time

from app.ai_providers.ai_provider_chain import build_default_callers
from app.ai_providers.model_registry import get_agent_chain

PROMPT = "Jawab satu kata: ok"
AGENTS = ("verifier", "supervisor", "forecast")


def uji(agent: str) -> None:
    print(f"\n== agent: {agent} ==")
    try:
        chain = get_agent_chain(agent)
    except Exception as exc:  # noqa: BLE001 - diagnostik: laporkan apa adanya
        print("chain ERROR:", type(exc).__name__, str(exc)[:160])
        return
    daftar = [
        f"{getattr(r, 'kind', '?')}:{str(getattr(r, 'model_id', ''))[:36]}" for r in chain
    ]
    print("slot:", daftar)

    callers = build_default_callers(agent)
    hidup = 0
    for label, fn, _kind in callers:
        t0 = time.time()
        try:
            out = fn(PROMPT)
        except Exception as exc:  # noqa: BLE001 - diagnostik: satu slot mati tidak menghentikan
            pesan = f"{type(exc).__name__}: {str(exc)[:100]}"
            print(f"  {label}: GAGAL {time.time() - t0:.1f}s | {pesan}")
            continue
        hidup += 1
        print(f"  {label}: OK {time.time() - t0:.1f}s | {str(out)[:50]!r}")
    print(f"ringkas: {hidup}/{len(callers)} slot menjawab")


def main() -> None:
    for agent in AGENTS:
        uji(agent)


if __name__ == "__main__":
    main()
