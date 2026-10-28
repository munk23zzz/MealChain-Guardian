"""Rehearsal Fase 12 — jalur demo replay / realtime / operasional lewat HTTP.

Dijalankan terhadap stack rehearsal (`verify/docker-compose.rehearsal.yml`,
backend 127.0.0.1:18100) yang menunjuk DB klon `mealchain_r12`, sehingga tidak
ada tulisan ke DB demo `mealchain`.

Bukti ditulis ke `_qa/f12/out/<mode>.json` + ringkasan tabel di stdout.
Tidak pernah mencetak kata sandi atau token.

Pemakaian:
  python _qa/f12/rehearsal_f12.py replay
  python _qa/f12/rehearsal_f12.py realtime
  python _qa/f12/rehearsal_f12.py operasional
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = os.environ.get("F12_BASE", "http://127.0.0.1:18100")
OUT_DIR = Path(__file__).resolve().parent / "out"
AKUN_HEAD = ("sppg.head@demo.local", "Demo#SPPG2026")
AKUN_NUT = ("sppg.nutritionist@demo.local", "Demo#Nut2026")
KANON = "2026-10-08T12:00:00"

hasil: list[dict] = []


def catat(step: str, ok: bool, detail=None) -> bool:
    hasil.append(
        {
            "step": step,
            "ok": bool(ok),
            "at": datetime.now(timezone.utc).isoformat(),
            "detail": detail,
        }
    )
    tanda = "OK   " if ok else "GAGAL"
    print(f"  [{tanda}] {step}")
    if detail is not None and not ok:
        print(f"          {json.dumps(detail, ensure_ascii=False)[:400]}")
    return ok


def panggil(path: str, *, token: str = "", method: str = "GET", body=None, timeout: float = 300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            mentah = resp.read().decode("utf-8", "replace")
            if mentah.strip().startswith(("{", "[")):
                return resp.status, json.loads(mentah)
            return resp.status, mentah
    except urllib.error.HTTPError as exc:
        mentah = exc.read().decode("utf-8", "replace")
        try:
            isi = json.loads(mentah)
        except Exception:  # noqa: BLE001
            isi = mentah[:300]
        return exc.code, isi
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def login(akun):
    kode, data = panggil("/auth/login", method="POST", body={"email": akun[0], "password": akun[1]})
    return kode, (data.get("access_token") if isinstance(data, dict) else None)


def jam(teks: str | None) -> datetime | None:
    if not teks:
        return None
    return datetime.fromisoformat(teks.replace("Z", "+00:00"))


def pilih_keputusan(items, demo_case, status="pending_approval"):
    for i in items:
        if i.get("demo_case") == demo_case and i.get("status") == status:
            return i
    return None


def muat_sesi(mode: str, token: str) -> dict:
    mulai = time.time()
    kode, data = panggil(
        "/demo/session/start", token=token, method="POST", body={"mode": mode, "replace": True}
    )
    durasi = round(time.time() - mulai, 1)
    catat(
        f"1. Muat Demo {mode} (POST /demo/session/start replace=true)",
        kode == 200 and isinstance(data, dict) and data.get("mode") == mode,
        {"http": kode, "sesi": (data or {}).get("session_id"), "mode": (data or {}).get("mode"),
         "anchor": (data or {}).get("evaluation_anchor"), "dataset_version": (data or {}).get("dataset_version"),
         "durasi_bangun_s": durasi},
    )
    return data


def alur(mode: str) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== rehearsal mode={mode} ({BASE}) ===")
    kode_h, tok_head = login(AKUN_HEAD)
    kode_n, tok_nut = login(AKUN_NUT)
    catat("0. login kepala SPPG + nutritionist", kode_h == 200 and kode_n == 200 and bool(tok_head) and bool(tok_nut),
          {"head_http": kode_h, "nut_http": kode_n})

    _kode_s, _sesi_awal = panggil("/demo/session", token=tok_head)
    _mode_aktif = (_sesi_awal or {}).get("mode") if isinstance(_sesi_awal, dict) else None
    sesi = muat_sesi(mode, tok_head)
    sid = sesi.get("session_id")
    anchor = sesi.get("evaluation_anchor")

    # Dataset bersih tiap putaran: kalau sesi sudah aktif dalam mode yang sama,
    # `start` tidak membangun ulang template (dan batch "usable" bisa sudah
    # diterima putaran sebelumnya). `template/rebuild` mem-purge baris
    # operasional lalu menyemai ulang tanpa menutup jendela sesi.
    if not sesi.get("created") and _mode_aktif is not None and _mode_aktif == mode:
        mulai = time.time()
        kode_rb, rb = panggil("/demo/template/rebuild", token=tok_head, method="POST")
        catat("1b. template dibangun ulang (dataset bersih untuk putaran ini)",
              kode_rb == 200 and isinstance(rb, dict),
              {"http": kode_rb, "durasi_detik": round(time.time() - mulai, 1),
               "hitung": (rb or {}).get("hitung", {}).get("decisions") if isinstance(rb, dict) else None})

    # anchor
    if mode == "replay":
        ok = bool(anchor) and anchor.startswith(KANON)
        catat("2. anchor replay = kanon 8 Okt 2026 12.00 UTC", ok, {"anchor": anchor})
    else:
        selisih = None
        if anchor:
            selisih = (datetime.now(timezone.utc) - jam(anchor)).total_seconds()
        ok = anchor is not None and not anchor.startswith(KANON) and selisih is not None and abs(selisih) < 600
        catat("2. anchor realtime = jam sesi (bukan kanon), selisih < 10 menit", ok,
              {"anchor": anchor, "selisih_detik": None if selisih is None else round(selisih, 1)})

    # refresh tidak menghilangkan sesi
    kode, lagi = panggil("/demo/session", token=tok_head)
    catat("3. GET /demo/session membaca sesi yang sama (tahan refresh)",
          kode == 200 and isinstance(lagi, dict) and lagi.get("session_id") == sid,
          {"http": kode, "session_id": (lagi or {}).get("session_id"), "mode": (lagi or {}).get("mode")})

    # analisis sebelum defisit terakhir ditutup
    kode, analisis = panggil("/balance/analyze", token=tok_head, method="POST", body={"demo_session": sid})
    ringkas = (analisis or {}).get("summary") if isinstance(analisis, dict) else None
    catat("4. POST /balance/analyze dijalankan pada keadaan awal sesi",
          kode == 200 and isinstance(ringkas, dict),
          {"http": kode, "summary": ringkas,
           "as_of": (analisis or {}).get("as_of") if isinstance(analisis, dict) else None,
           "held": len((analisis or {}).get("held") or []) if isinstance(analisis, dict) else None})

    # daftar keputusan
    kode, daftar = panggil("/decisions?limit=80", token=tok_head)
    items = daftar.get("items", []) if isinstance(daftar, dict) else []
    catat("5. daftar keputusan terbaca dari backend", kode == 200 and bool(items),
          {"http": kode, "total": (daftar or {}).get("total"), "items": len(items)})

    aman = pilih_keputusan(items, "wortel-coldchain-sah")
    tahan = pilih_keputusan(items, "wortel-coldchain-hold")
    catat("6. kasus replay/realtime tersedia: satu aman, satu bukti kurang",
          aman is not None and tahan is not None,
          {"aman": (aman or {}).get("decision_id"), "tahan": (tahan or {}).get("decision_id")})
    if not aman:
        raise SystemExit("kasus 'wortel-coldchain-sah' tidak ada — rehearsal tidak bisa lanjut")

    did = aman["decision_id"]
    kode, sum1 = panggil(f"/decisions/{did}/approval-summary", token=tok_head)
    catat("7. approval-summary: butuh dua peran, eksekusi belum boleh",
          kode == 200 and sum1.get("can_approve") and not sum1.get("can_execute")
          and sum1.get("approval_requirement", {}).get("min_approvals") == 2,
          {"http": kode, "can_approve": sum1.get("can_approve"), "can_execute": sum1.get("can_execute"),
           "requirement": sum1.get("approval_requirement"), "blocking": sum1.get("blocking_reasons")})

    # approval peran 1 lalu eksekusi ditolak
    kode_a1, _ = panggil("/actions/approve", token=tok_head, method="POST",
                         body={"decision_id": did, "approved": True, "comment": "rehearsal F12 — kepala SPPG"})
    kode_e1, isi_e1 = panggil("/actions/execute", token=tok_head, method="POST", body={"decision_id": did})
    catat("8. approval peran-1 lalu execute DITOLAK (butuh dua peran)",
          kode_a1 == 200 and kode_e1 == 409,
          {"approve_http": kode_a1, "execute_http": kode_e1,
           "detail": (isi_e1 or {}).get("detail") if isinstance(isi_e1, dict) else str(isi_e1)[:200]})

    kode_a2, _ = panggil("/actions/approve", token=tok_nut, method="POST",
                         body={"decision_id": did, "approved": True, "comment": "rehearsal F12 — nutritionist"})
    kode_s2, sum2 = panggil(f"/decisions/{did}/approval-summary", token=tok_head)
    catat("9. approval peran-2 → can_execute true",
          kode_a2 == 200 and kode_s2 == 200 and bool(sum2.get("can_execute")),
          {"approve_http": kode_a2, "can_execute": sum2.get("can_execute"),
           "blocking": sum2.get("blocking_reasons"), "approvals": len(sum2.get("approvals") or [])})

    kode_ex, isi_ex = panggil("/actions/execute", token=tok_head, method="POST", body={"decision_id": did})
    po_number = None
    if isinstance(isi_ex, dict):
        po_number = isi_ex.get("po_number") or (isi_ex.get("purchase_order") or {}).get("po_number")
    catat("10. execute → keputusan executed + PO terbit",
          kode_ex == 200 and bool(po_number),
          {"http": kode_ex, "po_number": po_number,
           "status": (isi_ex or {}).get("status") if isinstance(isi_ex, dict) else None,
           "kunci": sorted(isi_ex) if isinstance(isi_ex, dict) else None})

    # biaya: invoice vs SDC
    kode, det = panggil(f"/decisions/{did}", token=tok_head)
    cb = (det or {}).get("cost_breakdown") or {}
    kom = (det or {}).get("commercial_cost") or {}
    invoice = kom.get("invoice_total") or kom.get("total")
    sdc = (det or {}).get("safe_delivered_cost")
    penalti = [cb.get("expected_loss"), cb.get("freshness_risk"), cb.get("safety_penalty")]
    catat("11. invoice (purchase+transport+handling) terpisah dari SDC (+3 komponen risiko)",
          kode == 200 and invoice is not None and sdc is not None and all(p is not None for p in penalti),
          {"invoice_total": invoice, "sdc": sdc, "komponen_po": ["purchase", "transport", "handling"],
           "risiko": penalti, "commercial_cost": kom})

    # PO tersimpan
    kode, po = panggil("/sap/purchase-orders", token=tok_head)
    daftar_po = po if isinstance(po, list) else (po or {}).get("items", [])
    cocok = [p for p in daftar_po if p.get("po_number") == po_number]
    catat("12. PO ada di backend dan tertaut keputusan",
          kode == 200 and bool(cocok) and cocok[0].get("decision_id") == did,
          {"http": kode, "jumlah_po": len(daftar_po), "po": cocok[0] if cocok else None})

    # kiriman: batch di jalan + ETA dari server
    kode, rute = panggil("/supplier-routes", token=tok_head)
    baris = rute.get("routes") if isinstance(rute, dict) else rute
    baris = baris or []
    jalan = [r for r in baris if (r.get("journey") or {}).get("state") == "di_jalan"]
    catat("13. kiriman: ada batch 'di jalan' dengan ETA dihitung server",
          kode == 200 and bool(jalan),
          {"http": kode, "rute": len(baris), "di_jalan": len(jalan),
           "contoh": (jalan[0].get("journey") if jalan else None)})

    # ceklis + penerimaan batch usable
    gate = (sum1.get("receipt_gate") or {}).get("batches") or []
    usable = [b for b in gate if b.get("status") == "usable"]
    batch_id = usable[0]["batch_id"] if usable else None
    if batch_id:
        lokasi = aman.get("target_location_name") or "Jakarta"
        komoditas = aman.get("commodity") or "wortel"
        _k, pasokan_awal = panggil(f"/supply/{lokasi}/{komoditas}", token=tok_head)
        kode_c, ceklis = panggil("/receipts", token=tok_head, method="POST",
                                 body={"batch_id": batch_id,
                                       "checked": {"jumlah": True, "kemasan": True, "suhu": True},
                                       "other_note": "rehearsal Fase 12"})
        rid = (ceklis or {}).get("receipt_id") or (ceklis or {}).get("id")
        kode_r, terima = panggil(f"/receipts/{rid}/approve", token=tok_head, method="POST")
        _k2, pasokan_akhir = panggil(f"/supply/{lokasi}/{komoditas}", token=tok_head)
        awal = (pasokan_awal or {}).get("quantity_kg") if isinstance(pasokan_awal, dict) else None
        akhir = (pasokan_akhir or {}).get("quantity_kg") if isinstance(pasokan_akhir, dict) else None
        catat("14. ceklis + penerimaan batch usable diterima, pasokan lokasi bergerak",
              kode_c == 201 and kode_r == 200 and awal is not None and akhir is not None,
              {"batch_id": batch_id, "receipt_http": kode_c, "receipt_id": rid, "approve_http": kode_r,
               "status_penerimaan": (terima or {}).get("status") if isinstance(terima, dict) else None,
               "pasokan_sebelum_kg": awal, "pasokan_sesudah_kg": akhir,
               "selisih_kg": None if awal is None or akhir is None else round(float(akhir) - float(awal), 2)})
    else:
        catat("14. ceklis + penerimaan batch usable diterima, pasokan lokasi bergerak", False,
              {"alasan": "tidak ada batch berstatus usable di receipt_gate"})

    # KPI: provenance + baseline, dan cakupan sesi operator tidak mengarang angka
    kpi_bukti(sid, tok_head, mode)

    gerbang(tok_head, tok_nut, sid, po_number, aman, sum1, det)

    keluaran = {
        "mode": mode,
        "base": BASE,
        "session_id": sid,
        "anchor": anchor,
        "dataset_version": sesi.get("dataset_version"),
        "decision_id": did,
        "po_number": po_number,
        "steps": hasil,
    }
    (OUT_DIR / f"{mode}.json").write_text(json.dumps(keluaran, ensure_ascii=False, indent=1), encoding="utf-8")
    gagal = [s for s in hasil if not s["ok"]]
    print(f"\n  {len(hasil) - len(gagal)} lulus · {len(gagal)} gagal  →  out/{mode}.json")
    return keluaran


def gerbang(tok_head: str, tok_nut: str, sid: str, po_number: str | None, aman: dict, sum1: dict, det: dict) -> None:
    """Gerbang negatif (butir 6): yang TIDAK boleh lolos harus benar-benar ditolak."""
    # Kandidat: batch dengan status keamanan `needs_verification` yang BELUM
    # kedaluwarsa — inilah "bukti suhu kurang" yang harus ditahan tanpa
    # menyamarkannya sebagai kedaluwarsa.
    _k, daftar_batch = panggil("/batches?limit=200", token=tok_head)
    semua_batch = (daftar_batch or {}).get("batches") if isinstance(daftar_batch, dict) else daftar_batch
    semua_batch = semua_batch or []
    sekarang = datetime.now(timezone.utc)

    def belum_kedaluwarsa(b: dict) -> bool:
        batas = jam(b.get("usable_until"))
        return batas is not None and batas > sekarang

    nv_batch = next(
        (b for b in semua_batch
         if b.get("safety_status") == "needs_verification" and belum_kedaluwarsa(b)),
        None,
    )
    if nv_batch:
        bid = nv_batch["id"]
        kode_c, ceklis = panggil("/receipts", token=tok_head, method="POST",
                                 body={"batch_id": bid, "checked": {"jumlah": True},
                                       "other_note": "gerbang F12 — bukti suhu kurang"})
        rid = (ceklis or {}).get("receipt_id") or (ceklis or {}).get("id")
        kode_a, isi_a = panggil(f"/receipts/{rid}/approve", token=tok_head, method="POST") if rid else (0, {})
        # Dua bentuk penolakan yang sama-sama benar: ceklis tercatat lalu
        # penerimaan ditolak (409), ATAU ceklis sendiri sudah ditolak karena
        # batch tidak eligible. Yang tidak boleh: penerimaan lolos.
        ditolak = kode_a == 409 or (kode_c in (400, 409) and kode_a == 0)
        catat("N1. batch bukti kurang: PENERIMAAN tidak pernah lolos (ceklis tercatat atau ditolak lebih awal)",
              ditolak,
              {"batch_id": bid, "safety_status": nv_batch.get("safety_status"),
               "usable_until": nv_batch.get("usable_until"),
               "receipt_http": kode_c, "approve_http": kode_a,
               "detail": (isi_a or {}).get("detail") if isinstance(isi_a, dict) else str(isi_a)[:200]})

        kode_b, bd = panggil(f"/batches/{bid}", token=tok_head)
        batch = (bd or {}).get("batch") or {}
        ev = (bd or {}).get("evidence") or {}
        alasan_ev = ev.get("evidence_reasons") or []
        catat("N2. bukti suhu tidak lengkap → safety bukan 'pass'",
              kode_b == 200 and batch.get("safety_status") not in (None, "pass") and bool(alasan_ev),
              {"http": kode_b, "safety_status": batch.get("safety_status"),
               "freshness_score": batch.get("freshness_score"),
               "sample_count": ev.get("sample_count"),
               "evidence_sufficient": ev.get("evidence_sufficient"),
               "alasan": alasan_ev})

        # N2b — log yang benar-benar kosong/rusak tidak boleh dinilai cukup
        kosong = None
        for kandidat in semua_batch:
            if kandidat.get("safety_status") not in ("needs_verification", "fail"):
                continue
            _kx, bdx = panggil(f"/batches/{kandidat['id']}", token=tok_head)
            evx = (bdx or {}).get("evidence") or {}
            if evx.get("evidence_sufficient") is False:
                kosong = {
                    "batch_id": kandidat["id"],
                    "evidence_state": evx.get("evidence_state"),
                    "temperature_observation": evx.get("temperature_observation"),
                    "sample_count": evx.get("sample_count"),
                    "alasan": evx.get("evidence_reasons"),
                }
                break
        catat("N2b. log cold chain kosong/rusak → evidence_sufficient=false (tidak pernah 'pass')",
              kosong is not None, kosong or {"alasan": "tidak ada batch dengan bukti tidak cukup"})

    # N3 — batch kedaluwarsa tidak bisa diterima walau ceklis dicatat
    gate = (sum1.get("receipt_gate") or {}).get("batches") or []
    kedaluwarsa = [b for b in gate if "batch_expired" in (b.get("receive_reasons") or [])]
    if kedaluwarsa:
        bid_exp = kedaluwarsa[0]["batch_id"]
        kode_x, isi_x = panggil("/receipts", token=tok_head, method="POST",
                                body={"batch_id": bid_exp, "checked": {"jumlah": True},
                                      "other_note": "gerbang F12 — batch kedaluwarsa"})
        _kb, bd_exp = panggil(f"/batches/{bid_exp}", token=tok_head)
        alasan = ((bd_exp or {}).get("eligibility") or {}).get("blocking_reasons") or []
        catat("N3. batch kedaluwarsa ditolak (batch_expired)",
              kode_x in (400, 409) and "batch_expired" in alasan,
              {"batch_id": bid_exp, "http": kode_x, "blocking_reasons": alasan,
               "detail": (isi_x or {}).get("detail") if isinstance(isi_x, dict) else str(isi_x)[:200]})

    # N4 — keputusan yang masih butuh review tidak bisa dieksekusi walau dua peran setuju
    kode_h2, daftar = panggil("/decisions?limit=80", token=tok_head)
    items = (daftar or {}).get("items", []) if isinstance(daftar, dict) else []
    nv = pilih_keputusan(items, "wortel-coldchain-hold")
    if nv:
        nid = nv["decision_id"]
        panggil("/actions/approve", token=tok_head, method="POST",
                body={"decision_id": nid, "approved": True, "comment": "gerbang F12 — peran 1"})
        panggil("/actions/approve", token=tok_nut, method="POST",
                body={"decision_id": nid, "approved": True, "comment": "gerbang F12 — peran 2"})
        kode_e, isi_e = panggil("/actions/execute", token=tok_head, method="POST", body={"decision_id": nid})
        kode_s, sum_nv = panggil(f"/decisions/{nid}/approval-summary", token=tok_head)
        catat("N4. bukti kurang + dua approval → execute tetap ditolak",
              kode_e == 409 and not (sum_nv or {}).get("can_execute"),
              {"decision_id": nid, "execute_http": kode_e,
               "blocking_reasons": (sum_nv or {}).get("blocking_reasons"),
               "detail": (isi_e or {}).get("detail") if isinstance(isi_e, dict) else str(isi_e)[:200]})

    # N5 — penalti risiko TIDAK pernah masuk PO; invoice = purchase+transport+handling
    kom = (det or {}).get("commercial_cost") or {}
    cb = (det or {}).get("cost_breakdown") or {}
    kode, po = panggil("/sap/purchase-orders", token=tok_head)
    daftar_po = po if isinstance(po, list) else (po or {}).get("items", [])
    cocok = [p for p in daftar_po if p.get("po_number") == po_number]
    po_row = cocok[0] if cocok else {}
    teks = json.dumps(po_row, ensure_ascii=False).lower()
    ada_penalti = any(k in teks for k in ("expected_loss", "freshness_risk", "safety_penalty"))
    try:
        jumlah = round(float(cb.get("purchase", 0)) + float(cb.get("transport", 0)) + float(cb.get("handling", 0)), 2)
        invoice = round(float(kom.get("invoice_total") or 0), 2)
        cocok_angka = abs(jumlah - invoice) <= 1.0
    except (TypeError, ValueError):
        jumlah, invoice, cocok_angka = None, None, False
    catat("N5. PO tanpa penalti risiko; invoice = purchase+transport+handling",
          kode == 200 and bool(po_row) and not ada_penalti and cocok_angka,
          {"po_number": po_number, "ada_penalti_di_po": ada_penalti,
           "jumlah_komponen": jumlah, "invoice_total": invoice, "cocok_angka": cocok_angka,
           "kunci_po": sorted(po_row) if po_row else None})


def kpi_bukti(sid: str, token: str, mode: str) -> dict:
    """Tiga cakupan KPI: sesi operator, sesi sentinel template, dan operasional.

    Yang dibuktikan: setiap metrik membawa `state` eksplisit dan provenance;
    cakupan yang tidak punya bukti menjawab `no_data` (bukan nol karangan).
    """
    sentinel = "ce7a0000-0000-4000-8000-000000000001"
    ragam = {
        "sesi_operator": f"/kpi?periode=today&include_demo=true&demo_session_id={sid}",
        "sesi_sentinel_template": f"/kpi?periode=today&include_demo=true&demo_session_id={sentinel}",
        "operasional": "/kpi?periode=today",
    }
    keluaran: dict[str, dict] = {}
    for nama, path in ragam.items():
        kode, isi = panggil(path, token=token)
        metrik = (isi or {}).get("metrics") if isinstance(isi, dict) else None
        metrik = metrik or []
        ringkas = []
        for m in metrik:
            prov = m.get("provenance") or {}
            ringkas.append(
                {
                    "id": m.get("id") or m.get("key") or m.get("name"),
                    "state": m.get("state"),
                    "nilai": m.get("value"),
                    "evidence_kind": prov.get("evidence_kind") or m.get("evidence_kind"),
                    "baseline": m.get("baseline") or prov.get("baseline"),
                }
            )
        keluaran[nama] = {"http": kode, "n_metrik": len(metrik), "metrik": ringkas}
    operator = keluaran["sesi_operator"]
    sentinel_b = keluaran["sesi_sentinel_template"]
    operasional_b = keluaran["operasional"]
    ok = (
        operator["http"] == 200
        and bool(operator["n_metrik"])
        and all(m["state"] for m in operator["metrik"])
        and sentinel_b["http"] == 200
        and any(m["state"] in ("available", "simulated_estimate") for m in sentinel_b["metrik"])
        and operasional_b["http"] == 200
        and all(m["state"] for m in operasional_b["metrik"])
    )
    catat("15. KPI: state + provenance per metrik; cakupan tanpa bukti = no_data", ok, keluaran)
    (OUT_DIR / f"kpi-{mode}.json").write_text(json.dumps(keluaran, ensure_ascii=False, indent=1), encoding="utf-8")
    return keluaran


def operasional() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== rehearsal mode=operasional (DEMO_MODE=false) {BASE} ===")
    kode_h, tok_head = login(AKUN_HEAD)
    catat("0. login tetap jalan di mode operasional", kode_h == 200 and bool(tok_head), {"http": kode_h})

    for path, body in (("/demo/seed", {"force": False}), ("/demo/agent/run", {})):
        kode, isi = panggil(path, token=tok_head, method="POST", body=body)
        catat(f"1. {path} menjawab 404 di mode operasional", kode == 404,
              {"http": kode, "detail": (isi or {}).get("detail") if isinstance(isi, dict) else str(isi)[:120]})

    kode, sesi = panggil("/demo/session", token=tok_head)
    catat("2. router demo tertutup: GET /demo/session 404 (tidak ada fallback replay)",
          kode == 404,
          {"http": kode, "detail": (sesi or {}).get("detail") if isinstance(sesi, dict) else str(sesi)[:120]})

    kode_ds, data_status = panggil("/demo/data-status", token=tok_head)
    catat("3. GET /demo/data-status juga 404 — tidak ada jalur baca status demo",
          kode_ds == 404, {"http": kode_ds})

    kode_k, kpi = panggil("/kpi?periode=today", token=tok_head)
    metrik = (kpi or {}).get("metrics") or [] if isinstance(kpi, dict) else []
    klasifikasi = {}
    for m in metrik:
        prov = m.get("provenance") or {}
        kls = prov.get("classification") or {}
        if kls:
            klasifikasi[m.get("id") or m.get("name")] = kls
    seed_total = sum(int((k or {}).get("historical_seed") or 0) for k in klasifikasi.values())
    catat("4. data demo lama DITANDAI sebagai historical_seed, bukan disembunyikan",
          kode_k == 200 and seed_total > 0,
          {"http": kode_k, "n_metrik": len(metrik), "total_baris_historis": seed_total,
           "contoh": dict(list(klasifikasi.items())[:3]),
           "state": {m.get("id") or m.get("name"): m.get("state") for m in metrik[:7]}})

    keluaran = {"mode": "operasional", "base": BASE, "token_ok": bool(tok_head), "steps": hasil}
    (OUT_DIR / "operasional.json").write_text(json.dumps(keluaran, ensure_ascii=False, indent=1), encoding="utf-8")
    gagal = [s for s in hasil if not s["ok"]]
    print(f"\n  {len(hasil) - len(gagal)} lulus · {len(gagal)} gagal  →  out/operasional.json")
    return keluaran


if __name__ == "__main__":
    mode = (sys.argv[1] if len(sys.argv) > 1 else "replay").lower()
    if mode == "operasional":
        operasional()
    elif mode == "kpi":
        _kode, _tok = login(AKUN_HEAD)
        kpi_bukti(sys.argv[2], _tok, sys.argv[3] if len(sys.argv) > 3 else "manual")
        gagal = [s for s in hasil if not s["ok"]]
        print(f"\n  {len(hasil) - len(gagal)} lulus · {len(gagal)} gagal")
    else:
        alur(mode)
