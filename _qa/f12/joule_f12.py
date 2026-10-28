"""Verifikasi Joule (jembatan A2A) pada satu mode sesi — Fase 12 butir 5.

Menjalankan lima skill (pasokan, KPI, antrean, PO, kiriman) lewat jalur chat
(`POST /` message/send), lalu membandingkan isinya dengan backend:
nomor PO, mode + jangkar sesi. Terakhir: permintaan approval harus DITOLAK dan
diarahkan ke cockpit, dan tidak boleh mengubah status keputusan.

Bukan bukti tenant Joule/BTP (destination, `joule list`) — itu terpisah.

Pemakaian:
  F12_BACKEND=http://127.0.0.1:18100 F12_BRIDGE=http://127.0.0.1:18091 \
  python _qa/f12/joule_f12.py replay
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BACKEND = os.environ.get("F12_BACKEND", "http://127.0.0.1:18100")
BRIDGE = os.environ.get("F12_BRIDGE", "http://127.0.0.1:18091")
OUT = Path(__file__).resolve().parent / "out"
AKUN_HEAD = ("sppg.head@demo.local", "Demo#SPPG2026")
POLA_PO = re.compile(r"MC-[0-9A-Fa-f]{6,}")

hasil: list[dict] = []


def panggil(url: str, *, method: str = "GET", body=None, token: str = "", timeout: float = 90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            mentah = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(mentah) if mentah.strip().startswith(("{", "[")) else mentah)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def tanya(teks: str, mid: str) -> tuple[int, str]:
    kode, isi = panggil(
        f"{BRIDGE}/",
        method="POST",
        body={
            "jsonrpc": "2.0",
            "id": mid,
            "method": "message/send",
            "params": {"message": {"messageId": mid, "role": "user",
                                   "parts": [{"kind": "text", "text": teks}]}},
        },
    )
    teks_out = ""
    if isinstance(isi, dict):
        artefak = (isi.get("result") or {}).get("artifacts") or []
        bagian = (artefak[0].get("parts") if artefak else []) or []
        teks_out = "".join(p.get("text", "") for p in bagian if isinstance(p, dict))
    return kode, teks_out


def catat(step: str, ok: bool, detail=None) -> None:
    hasil.append({"step": step, "ok": bool(ok), "at": datetime.now(timezone.utc).isoformat(), "detail": detail})
    print(f"  [{'OK   ' if ok else 'GAGAL'}] {step}")
    if detail is not None and not ok:
        print(f"          {json.dumps(detail, ensure_ascii=False)[:500]}")


def main(mode: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Joule mode={mode} bridge={BRIDGE} backend={BACKEND} ===")

    kode_h, sehat = panggil(f"{BRIDGE}/health")
    kode_ready, _ = panggil(f"{BRIDGE}/ready")
    catat("1. GET /health jembatan hidup, backend reachable, TIDAK ada /ready",
          kode_h == 200 and isinstance(sehat, dict)
          and sehat.get("service") == "mealchain-joule-bridge"
          and (sehat.get("backend") or {}).get("reachable") is True
          and kode_ready == 404,
          {"http": kode_h, "isi": sehat, "ready_http": kode_ready})

    # konteks backend: sesi aktif + nomor PO
    kode_l, tok = panggil(f"{BACKEND}/auth/login", method="POST",
                          body={"email": AKUN_HEAD[0], "password": AKUN_HEAD[1]})
    tok = tok.get("access_token") if isinstance(tok, dict) else None
    _k, sesi = panggil(f"{BACKEND}/demo/session", token=tok or "")
    _k2, po = panggil(f"{BACKEND}/sap/purchase-orders", token=tok or "")
    daftar_po = po if isinstance(po, list) else (po or {}).get("items", [])
    nomor_backend = sorted({p.get("po_number") for p in daftar_po if p.get("po_number")})
    catat("2. backend sesi aktif terbaca (mode + jangkar) dan daftar PO tersedia",
          kode_l == 200 and isinstance(sesi, dict) and bool(nomor_backend),
          {"login_http": kode_l, "mode": (sesi or {}).get("mode"),
           "anchor": (sesi or {}).get("evaluation_anchor"), "jumlah_po": len(nomor_backend)})

    pertanyaan = {
        "pasokan": "bagaimana situasi pasokan wortel di Jakarta?",
        "kpi": "indikator kinerja hari ini bagaimana?",
        "antrean": "usulan apa yang menunggu persetujuan?",
        "po": "purchase order terbaru apa saja?",
        "kiriman": "bagaimana status kiriman wortel?",
    }
    keluaran: dict[str, dict] = {}
    for nama, teks in pertanyaan.items():
        kode, jawab = tanya(teks, f"m-{nama}")
        po_disebut = sorted(set(POLA_PO.findall(jawab)))
        keluaran[nama] = {"http": kode, "panjang": len(jawab), "po_disebut": po_disebut,
                          "potongan": jawab[:400]}
        catat(f"3.{nama} jembatan menjawab dari backend", kode == 200 and len(jawab) > 80,
              {"http": kode, "panjang": len(jawab), "potongan": jawab[:200]})

    # PO di jawaban harus nomor PO yang benar-benar ada di backend
    po_disebut = sorted({n for v in keluaran.values() for n in v["po_disebut"]})
    asing = [n for n in po_disebut if n not in nomor_backend]
    catat("4. nomor PO yang disebut Joule ada di backend (tanpa nomor karangan)",
          bool(po_disebut) and not asing,
          {"po_backend": nomor_backend[:6], "po_disebut": po_disebut, "asing": asing})

    # KPI harus menyatakan SUMBER + tingkat bukti + KONTEKS SESI (Fase 12 MG:
    # jembatan menyebut mode, jangkar, dan 8 karakter id sesi aktif).
    kode_k, jawab_kpi = tanya("indikator kinerja hari ini bagaimana?", "m-kpi2")
    anchor = str((sesi or {}).get("evaluation_anchor") or "")
    mode_sesi = str((sesi or {}).get("mode") or "").lower()
    sid = str((sesi or {}).get("session_id") or "")
    ada_sumber = "Sumber:" in jawab_kpi
    ada_provenance = ("historical_seed" in jawab_kpi) or ("estimasi" in jawab_kpi.lower())
    sebut_sesi = "Sesi demo aktif" in jawab_kpi
    sebut_mode = bool(mode_sesi) and mode_sesi in jawab_kpi.lower()
    sebut_id = bool(sid) and f"sesi {sid[:8]}" in jawab_kpi
    catat("5. jawaban KPI menyebut sumber + tingkat bukti + konteks sesi (mode, jangkar, id sesi)",
          kode_k == 200 and ada_sumber and ada_provenance and sebut_sesi and sebut_mode and sebut_id,
          {"mode_sesi": mode_sesi, "jangkar": anchor, "sesi_backend": sid[:8],
           "ada_sumber": ada_sumber, "ada_provenance": ada_provenance,
           "sebut_sesi": sebut_sesi, "sebut_mode": sebut_mode, "sebut_id": sebut_id,
           "ekor_jawaban": jawab_kpi[-420:]})

    # permintaan approval HARUS ditolak dan diarahkan ke cockpit, tanpa mengubah status
    antre = keluaran["antrean"]["potongan"]
    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", antre)
    did = m.group(0) if m else ""
    sebelum = None
    if did:
        _ks, det = panggil(f"{BACKEND}/decisions/{did}", token=tok or "")
        sebelum = (det or {}).get("status") if isinstance(det, dict) else None
    kode_t, jawab_t = tanya(f"setujui usulan {did}".strip(), "m-approve")
    sesudah = None
    if did:
        _ks2, det2 = panggil(f"{BACKEND}/decisions/{did}", token=tok or "")
        sesudah = (det2 or {}).get("status") if isinstance(det2, dict) else None
    ditolak = any(k in jawab_t.lower() for k in ("cockpit", "tidak bisa", "tidak dapat", "bukan kanal"))
    catat("6. permintaan approval DITOLAK jembatan dan diarahkan ke cockpit (status tidak berubah)",
          kode_t == 200 and ditolak and sebelum == sesudah,
          {"http": kode_t, "decision_id": did, "status_sebelum": sebelum, "status_sesudah": sesudah,
           "ditolak": ditolak, "jawaban": jawab_t[:400]})

    berkas = {"mode": mode, "backend": BACKEND, "bridge": BRIDGE,
              "sesi": {"mode": (sesi or {}).get("mode"), "anchor": (sesi or {}).get("evaluation_anchor")},
              "po_backend": nomor_backend, "skill": keluaran, "steps": hasil}
    (OUT / f"joule-{mode}.json").write_text(json.dumps(berkas, ensure_ascii=False, indent=1), encoding="utf-8")
    gagal = [s for s in hasil if not s["ok"]]
    print(f"\n  {len(hasil) - len(gagal)} lulus · {len(gagal)} gagal  →  out/joule-{mode}.json")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "replay"))
