#!/usr/bin/env python3
"""cek-agen.py - pemeriksa mandiri SELURUH permukaan agen MealChain Guardian.

Skrip ini hanya bicara lewat HTTP: tidak mengimpor kode backend, tidak membaca
database. Karena itu ia bisa dijalankan di host (menguji API publik/VPS) maupun
DI DALAM kontainer backend (menguji 127.0.0.1:8000), dengan Python 3 stdlib
saja - tanpa dependensi baru.

Yang diperiksa berurutan (semuanya endpoint yang benar-benar ada di kode):

  1. GET  /health                              - backend hidup?
  2. POST /auth/login                          - token + peran
  3. GET  /agent/supervisor/health             - rantai model supervisor
  4. GET  /agent/feedback/rejections           - bahan langkah LEARN
  5. POST /agent/supervisor/ask                - jawaban baca-saja
  6. GET  /demo/agent/commodities              - pilihan komoditas demo
  7. POST /demo/agent/run                      - putaran pipeline penuh
  8. GET  /demo/agent/stream?run_token=...     - langkah yang disiarkan (SSE)
  9. GET  /decisions/{id}/traces               - jejak agen yang dibaca FE
 10. GET  /decisions?limit=200                 - keputusan per status

Setiap cek mencetak PASS/FAIL/SKIP + status HTTP + 1-2 angka bukti. Kegagalan
dilaporkan APA ADANYA (404 ditulis 404, bukan "tidak tersedia"), dan alasan
penolakan 4xx ditampilkan dari field `detail` server.

Arti status:
  PASS = perilaku yang dijanjikan terbukti pada pemeriksaan ini.
  FAIL = endpoint menjawab galat, atau janji datanya tidak terpenuhi (keras:
         skrip keluar dengan kode 1).
  SKIP = tidak bisa diuji karena gerbang lingkungan yang NYATA (mis. sesi demo
         belum aktif sehingga POST ditolak 409, atau tidak ada id keputusan
         karena putaran dilewati). Alasannya selalu dicetak.

Contoh:
  python infra/vps/cek-agen.py --base http://localhost:8000
  python infra/vps/cek-agen.py --base https://.../api --email ... --password ...
  MEALCHAIN_BASE=http://backend:8000 python cek-agen.py   # di dalam kontainer

Keluar: 0 = tidak ada FAIL keras, 1 = ada FAIL keras, 2 = argumen salah.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

#: Batas detik bawaan untuk operasi BERAT (POST /demo/agent/run + SSE).
#: Terukur pada stack lokal: satu putaran beras ~82 detik (verifier + forecast
#: + review), jadi batas kecil seperti 30 detik akan menuduh "timeout" padahal
#: pipeline memang sedang bekerja.
TIMEOUT_BAWAAN = 240.0

#: Endpoint cepat (health, login, daftar) tidak perlu menunggu selama itu.
TIMEOUT_RINGAN = 15.0

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


# ---------------------------------------------------------------------------
# HTTP tipis (stdlib)
# ---------------------------------------------------------------------------


class Http:
    """Pemanggil HTTP dengan base yang bisa memuat awalan seperti `/api`."""

    def __init__(self, base: str, timeout: float, insecure: bool = False):
        self.base = (base or "").strip().rstrip("/")
        self.timeout = timeout
        self.ctx = None
        if insecure and self.base.startswith("https"):
            import ssl

            self.ctx = ssl._create_unverified_context()  # noqa: S323 - diminta eksplisit

    def panggil(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        token: str | None = None,
        timeout: float | None = None,
        terima: str = "application/json",
    ) -> tuple[int, bytes, dict]:
        """Kembalikan (status, badan mentah, header). Galat jaringan dilempar."""
        data = None
        headers = {"Accept": terima}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        batas = self.timeout if timeout is None else timeout
        try:
            with urllib.request.urlopen(req, timeout=batas, context=self.ctx) as r:
                return int(r.status), r.read(), dict(r.headers)
        except urllib.error.HTTPError as exc:
            # 4xx/5xx tetap "jawaban server" - dibaca apa adanya, bukan dilempar.
            return int(exc.code), exc.read() or b"", dict(exc.headers or {})


def baca_json(mentah: bytes):
    """JSON atau None; badan non-JSON (mis. HTML 502) tidak membuat skrip mati."""
    try:
        return json.loads(mentah.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return None


def teks_galat(obj, mentah: bytes, maks: int = 240) -> str:
    """Alasan penolakan dari server, dipotong supaya satu baris tetap terbaca."""
    if isinstance(obj, dict) and "detail" in obj:
        detail = obj["detail"]
        teks = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    else:
        teks = mentah.decode("utf-8", "replace")
    teks = " ".join(teks.split())
    return teks[:maks] + ("..." if len(teks) > maks else "")


def potong(nilai, maks: int = 120) -> str:
    teks = " ".join(str(nilai).split())
    return teks[:maks] + ("..." if len(teks) > maks else "")


# ---------------------------------------------------------------------------
# Pencatat hasil
# ---------------------------------------------------------------------------


def catat(hasil: list[dict], nama: str, status: str, http, bukti: str) -> None:
    baris = {"nama": nama, "status": status, "http": http, "bukti": bukti}
    hasil.append(baris)
    print(f"[{nama:<16}] {status:<4} http={str(http):<4} | {bukti}", flush=True)


def cari(hasil: list[dict], nama: str) -> dict:
    for baris in hasil:
        if baris["nama"] == nama:
            return baris
    return {"status": SKIP, "bukti": "tidak dijalankan"}


# ---------------------------------------------------------------------------
# Pendengar SSE
# ---------------------------------------------------------------------------


class PendengarSSE(threading.Thread):
    """Membaca `/demo/agent/stream` di utas terpisah.

    Kanal kemajuan HARUS dibuka SEBELUM `POST /demo/agent/run`: server hanya
    menyiarkan langkah ke kanal yang sudah ada (`agent_progress.buka`), dan
    mengirim komentar `: siap` begitu kanal terbuka. Karena itu utas ini
    dijalankan lebih dulu, lalu pemanggil menunggu `siap`.

    Kenapa memakai `select` + `http.client`, bukan `urlopen().readline()`:
    jeda antar langkah nyata bisa >10 detik (VERIFY sampai 16 detik), dan satu
    kali socket timeout membuat objek respons mati ("cannot read from timed out
    object") sehingga langkah sesudahnya hilang. Dengan `select` utas ini hanya
    membaca saat data benar-benar siap, dan berhenti dalam <=0,4 detik setelah
    `berhenti` di-set.
    """

    def __init__(self, http: Http, token_auth: str, run_token: str, batas_detik: float):
        super().__init__(daemon=True)
        self.http = http
        self.token_auth = token_auth
        self.run_token = run_token
        self.batas = time.monotonic() + batas_detik
        self.langkah: list[dict] = []
        self.status: int | None = None
        self.galat: str | None = None
        self.siap = threading.Event()
        self.berhenti = threading.Event()
        self.selesai = threading.Event()

    def _jalur(self) -> str:
        u = urllib.parse.urlsplit(self.http.base)
        awalan = u.path.rstrip("/")
        return awalan + "/demo/agent/stream?run_token=" + urllib.parse.quote(self.run_token)

    def run(self) -> None:  # noqa: D401 - utas
        import http.client
        import select

        u = urllib.parse.urlsplit(self.http.base)
        host = u.hostname or "localhost"
        port = u.port or (443 if u.scheme == "https" else 80)
        koneksi = None
        try:
            if u.scheme == "https":
                koneksi = http.client.HTTPSConnection(
                    host, port, timeout=15, context=self.http.ctx
                )
            else:
                koneksi = http.client.HTTPConnection(host, port, timeout=15)
            koneksi.putrequest("GET", self._jalur())
            # Jangan menambah header `Host` sendiri: `putrequest` sudah
            # mengirimnya. Header ganda ditolak 400 oleh Caddy (terukur pada
            # VPS), padahal uvicorn lokal memaafkannya.
            koneksi.putheader("Authorization", "Bearer " + self.token_auth)
            koneksi.putheader("Accept", "text/event-stream")
            koneksi.putheader("Cache-Control", "no-cache")
            koneksi.endheaders()
            resp = koneksi.getresponse()
            self.status = int(resp.status)
            # Header sudah tiba = handler server sudah membuka kanal; aman
            # mengirim POST sekarang (langkah tidak akan terlewat).
            self.siap.set()
            if self.status != 200:
                badan = resp.read(2000)
                self.galat = f"HTTP {self.status}: {teks_galat(baca_json(badan), badan)}"
                return
            # Jangan kirim `Connection: close`: http.client lalu menutup koneksi
            # dan mengosongkan `conn.sock` tepat sesudah header dibaca, sehingga
            # `select` tidak punya objek untuk ditunggu. Koneksi diputus oleh
            # skrip ini sendiri di blok `finally`.
            sock = koneksi.sock
            if sock is None:  # server tetap memutus (mis. proxy): pakai soket fp
                sock = getattr(getattr(resp.fp, "raw", None), "_sock", None)
            if sock is None:
                self.galat = "koneksi SSE ditutup server sebelum langkah pertama"
                return
            while time.monotonic() < self.batas:
                if self.berhenti.is_set():
                    break
                siap, _, _ = select.select([sock], [], [], 0.4)
                if not siap:
                    continue
                baris = resp.readline()
                if not baris:
                    break
                teks = baris.decode("utf-8", "replace").strip()
                if not teks or teks.startswith(":"):
                    continue
                if teks.startswith("data:"):
                    muatan = teks[5:].strip()
                    try:
                        self.langkah.append(json.loads(muatan))
                    except ValueError:
                        continue
        except Exception as exc:  # noqa: BLE001 - dilaporkan, bukan ditelan
            self.galat = f"{type(exc).__name__}: {exc}"
        finally:
            self.siap.set()
            try:
                if koneksi is not None:
                    koneksi.close()
            except Exception:  # noqa: BLE001 - best effort
                pass
            self.selesai.set()


# ---------------------------------------------------------------------------
# Cek satu per satu
# ---------------------------------------------------------------------------


def cek_health(http: Http, hasil: list[dict]) -> bool:
    try:
        st, mentah, _ = http.panggil("GET", "/health", timeout=TIMEOUT_RINGAN)
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "health", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return False
    obj = baca_json(mentah)
    if st != 200:
        catat(hasil, "health", FAIL, st, f"harus 200: {teks_galat(obj, mentah)}")
        return False
    ringkas = obj if isinstance(obj, dict) else {}
    review = (ringkas.get("agent_review") or {}).get("mode")
    catat(
        hasil,
        "health",
        PASS,
        st,
        f"service={ringkas.get('service')} status={ringkas.get('status')} "
        f"agent_review={review}",
    )
    return True


def cek_login(http: Http, hasil: list[dict], email: str, password: str) -> str | None:
    try:
        st, mentah, _ = http.panggil(
            "POST",
            "/auth/login",
            body={"email": email, "password": password},
            timeout=TIMEOUT_RINGAN,
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "login", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return None
    obj = baca_json(mentah)
    token = (obj or {}).get("access_token") if isinstance(obj, dict) else None
    if st != 200 or not token:
        catat(hasil, "login", FAIL, st, f"tanpa access_token: {teks_galat(obj, mentah)}")
        return None
    peran = "-"
    if isinstance(obj, dict):
        peran = obj.get("role") or (obj.get("user") or {}).get("role") or "-"
    catat(hasil, "login", PASS, st, f"peran={peran} token={len(token)} karakter")
    return token


def cek_sesi_demo(http: Http, hasil: list[dict], token: str) -> dict:
    """Status sesi demo: penjelas utama bila POST ditolak 409.

    Bukan sekadar hiasan: `DEMO_SESSION_ENFORCE=true` menolak SEMUA POST saat
    tidak ada sesi aktif, termasuk langkah yang sebenarnya baca-saja seperti
    `/agent/supervisor/ask`.
    """
    try:
        st, mentah, _ = http.panggil(
            "GET", "/demo/session", token=token, timeout=TIMEOUT_RINGAN
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "sesi-demo", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return {}
    obj = baca_json(mentah) or {}
    if st != 200:
        catat(hasil, "sesi-demo", FAIL, st, f"harus 200: {teks_galat(obj, mentah)}")
        return {}
    aktif = bool(obj.get("active"))
    catat(
        hasil,
        "sesi-demo",
        PASS,
        st,
        f"aktif={'ya' if aktif else 'tidak'} enforced={obj.get('enforced')} "
        f"mode={obj.get('mode')} sisa={obj.get('remaining_seconds')}s",
    )
    return obj


def cek_supervisor(http: Http, hasil: list[dict], token: str) -> None:
    try:
        st, mentah, _ = http.panggil(
            "GET", "/agent/supervisor/health", token=token, timeout=TIMEOUT_RINGAN
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "supervisor", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return
    obj = baca_json(mentah)
    if st != 200:
        catat(hasil, "supervisor", FAIL, st, f"harus 200: {teks_galat(obj, mentah)}")
        return
    data = obj if isinstance(obj, dict) else {}
    # `live: null` adalah janji desain (tidak ada probe provider di jalur ini),
    # jadi PASS di sini berarti "konfigurasi terbaca", bukan "model hidup".
    catat(
        hasil,
        "supervisor",
        PASS,
        st,
        f"status={data.get('status')} model={potong(data.get('model'), 64)} "
        f"slots={data.get('slots')} live={data.get('live')}",
    )


def cek_feedback(http: Http, hasil: list[dict], token: str) -> None:
    try:
        st, mentah, _ = http.panggil(
            "GET", "/agent/feedback/rejections?limit=20", token=token, timeout=TIMEOUT_RINGAN
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "feedback", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return
    obj = baca_json(mentah)
    if st != 200:
        catat(hasil, "feedback", FAIL, st, f"harus 200: {teks_galat(obj, mentah)}")
        return
    data = obj if isinstance(obj, dict) else {}
    jumlah = data.get("jumlah") or {}
    catat(
        hasil,
        "feedback",
        PASS,
        st,
        f"keputusan_ditolak={jumlah.get('keputusan')} penerimaan_ditolak={jumlah.get('penerimaan')} "
        f"cakupan={data.get('cakupan')} writes={data.get('writes')}",
    )


def cek_ask(http: Http, hasil: list[dict], token: str) -> None:
    """POST baca-saja; 200 dibuktikan, 4xx dijelaskan, TIDAK disembunyikan."""
    pertanyaan = "Berapa keputusan yang menunggu persetujuan?"
    try:
        st, mentah, _ = http.panggil(
            "POST",
            "/agent/supervisor/ask",
            body={"question": pertanyaan},
            token=token,
            timeout=TIMEOUT_RINGAN,
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "supervisor-ask", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return
    obj = baca_json(mentah)
    if st == 200:
        data = obj if isinstance(obj, dict) else {}
        catat(
            hasil,
            "supervisor-ask",
            PASS,
            st,
            f"mode={data.get('mode')} tool={potong(data.get('tool'), 48)} "
            f"writes={data.get('writes')} jawab={potong(data.get('answer'), 110)}",
        )
        return
    alasan = teks_galat(obj, mentah)
    if st == 404:
        # Rute tidak ada (mis. bug prefiks Caddy) = permukaan keras, bukan SKIP.
        catat(hasil, "supervisor-ask", FAIL, st, f"rute tidak ditemukan: {alasan}")
    elif 400 <= st < 500:
        # Gerbang lingkungan / di luar cakupan bukan bukti endpoint rusak, tetapi
        # juga BUKAN PASS: jawaban supervisor tidak terbukti pada pemeriksaan ini.
        catat(hasil, "supervisor-ask", SKIP, st, f"ditolak server: {alasan}")
    else:
        catat(hasil, "supervisor-ask", FAIL, st, f"galat server: {alasan}")


def cek_commodities(http: Http, hasil: list[dict], token: str, komoditas: str) -> None:
    try:
        st, mentah, _ = http.panggil(
            "GET", "/demo/agent/commodities", token=token, timeout=TIMEOUT_RINGAN
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "commodities", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return
    obj = baca_json(mentah)
    if st != 200:
        catat(hasil, "commodities", FAIL, st, f"harus 200: {teks_galat(obj, mentah)}")
        return
    data = obj if isinstance(obj, dict) else {}
    daftar = data.get("commodities") or []
    kasus = {k.get("commodity"): k for k in (data.get("kasus") or [])}
    pilihan = kasus.get(komoditas) or {}
    catat(
        hasil,
        "commodities",
        PASS,
        st,
        f"n={len(daftar)} lokasi={data.get('location')} "
        f"{komoditas}:status={pilihan.get('status')} bisa_dijalankan={pilihan.get('bisa_dijalankan')}",
    )


def cek_run(
    http: Http, hasil: list[dict], token: str, komoditas: str, timeout: float
) -> dict:
    """POST /demo/agent/run + SSE paralel. Kembalikan info putaran."""
    # Pembaca SSE dulu: kanal harus ada sebelum pipeline mengirim langkah.
    run_token = uuid.uuid4().hex[:16]
    pendengar = PendengarSSE(http, token, run_token, timeout + 30)
    pendengar.start()
    pendengar.siap.wait(10)

    try:
        st, mentah, _ = http.panggil(
            "POST",
            "/demo/agent/run",
            body={"commodity": komoditas, "run_token": run_token},
            token=token,
            timeout=timeout,
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        pendengar.berhenti.set()
        pendengar.join(12)
        catat(hasil, "demo-run", FAIL, "-", f"tidak bisa dihubungi/di luar batas waktu: {exc}")
        return {"pendengar": pendengar, "dilewati": True}
    finally:
        # Jeda serap: langkah terakhir (SUPERVISE) bisa tiba beberapa milidetik
        # sesudah respons POST; tanpa jeda ini jumlah langkah tampak kurang.
        time.sleep(1.5)
        pendengar.berhenti.set()
        pendengar.join(12)

    obj = baca_json(mentah)
    data = obj if isinstance(obj, dict) else {}
    if st == 201:
        dibuat = data.get("created") or []
        ids = [d.get("decision_id") for d in dibuat if isinstance(d, dict)]
        if not ids and data.get("decision_id"):
            ids = [data.get("decision_id")]
        dilewati = data.get("skipped") or []
        snap = data.get("decision_snapshot") or {}
        review = data.get("agent_review") or {}
        catat(
            hasil,
            "demo-run",
            PASS,
            st,
            f"keputusan={len(ids)} status={snap.get('status')} "
            f"komoditas={','.join(d.get('commodity', '?') for d in dibuat) or '-'} "
            f"dilewati={len(dilewati)} review={review.get('status')}",
        )
        return {
            "pendengar": pendengar,
            "dilewati": False,
            "decision_ids": [i for i in ids if i],
            "status": snap.get("status"),
        }

    alasan = teks_galat(obj, mentah)
    if st == 409:
        catat(
            hasil,
            "demo-run",
            SKIP,
            st,
            f"pipeline tidak berjalan: {alasan}",
        )
        return {"pendengar": pendengar, "dilewati": True}
    if 400 <= st < 500:
        catat(hasil, "demo-run", FAIL, st, f"ditolak: {alasan}")
    else:
        catat(hasil, "demo-run", FAIL, st, f"galat server: {alasan}")
    return {"pendengar": pendengar, "dilewati": True}


def cek_stream(hasil: list[dict], pendengar: PendengarSSE, dijalankan: bool) -> None:
    if not dijalankan:
        catat(hasil, "demo-stream", SKIP, "-", "tidak ada putaran: SSE tidak membaca apa pun")
        return
    langkah = [l.get("step") for l in pendengar.langkah if isinstance(l, dict)]
    if pendengar.galat:
        catat(hasil, "demo-stream", FAIL, pendengar.status, f"galat kanal: {pendengar.galat}")
        return
    if pendengar.status != 200:
        catat(
            hasil,
            "demo-stream",
            FAIL,
            pendengar.status,
            f"kanal SSE menjawab {pendengar.status}; langkah diterima={len(langkah)}",
        )
        return
    if not langkah:
        catat(
            hasil,
            "demo-stream",
            FAIL,
            pendengar.status,
            "kanal terbuka tetapi tidak ada satu langkah pun yang disiarkan",
        )
        return
    unik = list(dict.fromkeys(langkah))
    tuntas = "DECIDE" in langkah
    catat(
        hasil,
        "demo-stream",
        PASS if tuntas else FAIL,
        pendengar.status,
        f"langkah={len(langkah)} urutan={' > '.join(unik)}",
    )


def cek_traces(
    http: Http, hasil: list[dict], token: str, decision_ids: list[str]
) -> None:
    if not decision_ids:
        catat(hasil, "traces", SKIP, "-", "tidak ada id keputusan dari putaran")
        return
    did = decision_ids[0]
    jalur = f"/decisions/{urllib.parse.quote(did)}/traces"
    try:
        st, mentah, _ = http.panggil("GET", jalur, token=token, timeout=TIMEOUT_RINGAN)
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "traces", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return
    obj = baca_json(mentah)
    if st != 200:
        catat(hasil, "traces", FAIL, st, f"harus 200: {teks_galat(obj, mentah)}")
        return
    data = obj if isinstance(obj, dict) else {}
    steps = data.get("steps") or []
    nama_agen = sorted({s.get("agent_name") for s in steps if s.get("agent_name")})
    langkah = [s.get("step_name") for s in steps]
    if not steps:
        catat(
            hasil,
            "traces",
            FAIL,
            st,
            f"0 langkah untuk keputusan {did[:8]} - jejak agen tidak terbaca FE",
        )
        return
    # Jejak review 7 worker hanya ada bila MULTI_AGENT_REVIEW menyala; di
    # pipeline deterministik `agent_name` memang kosong. Itu dilaporkan apa
    # adanya, bukan dihitung sebagai PASS palsu maupun FAIL palsu.
    ket = (
        f"agent_name_unik={len(nama_agen)}: " + ", ".join(nama_agen)
        if nama_agen
        else "agent_name_unik=0 (review 7 worker tidak menulis baris; agent_name null)"
    )
    catat(
        hasil,
        "traces",
        PASS,
        st,
        f"langkah={len(steps)} {' > '.join(str(x) for x in dict.fromkeys(langkah) if x)} | {ket}",
    )


def cek_keputusan(http: Http, hasil: list[dict], token: str) -> None:
    try:
        st, mentah, _ = http.panggil(
            "GET", "/decisions?limit=200", token=token, timeout=TIMEOUT_RINGAN
        )
    except (urllib.error.URLError, OSError, socket.timeout) as exc:
        catat(hasil, "keputusan", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        return
    obj = baca_json(mentah)
    if st != 200:
        catat(hasil, "keputusan", FAIL, st, f"harus 200: {teks_galat(obj, mentah)}")
        return
    data = obj if isinstance(obj, dict) else {}
    items = data.get("items") or []
    per_status: dict[str, int] = {}
    for baris in items:
        kunci = (baris or {}).get("status") or "tanpa_status"
        per_status[kunci] = per_status.get(kunci, 0) + 1
    total = data.get("total")
    rinci = ", ".join(
        f"{k}={v}" for k, v in sorted(per_status.items(), key=lambda p: (-p[1], p[0]))
    )
    # `total` adalah tegas dari server: bila ia tidak sama dengan jumlah baris
    # yang dikirim (dan total <= limit), itu inkonsistensi yang harus terlihat.
    konsisten = total is None or (isinstance(total, int) and total > 200) or total == len(items)
    catat(
        hasil,
        "keputusan",
        PASS if konsisten and items else FAIL,
        st,
        f"total={total} items={len(items)} | {rinci or 'kosong'}",
    )


# ---------------------------------------------------------------------------
# Ringkasan
# ---------------------------------------------------------------------------


def cetak_ringkasan(hasil: list[dict]) -> int:
    urutan = [
        ("health", "health"),
        ("login", "login"),
        ("sesi-demo", "sesi-demo"),
        ("supervisor", "supervisor"),
        ("supervisor-ask", "supervisor-ask"),
        ("feedback", "feedback"),
        ("commodities", "commodities"),
        ("demo-run", "demo-run"),
        ("demo-stream", "demo-stream"),
        ("traces", "traces"),
        ("keputusan", "keputusan"),
    ]
    if any(b["nama"] == "mulai-sesi" for b in hasil):
        urutan.insert(3, ("mulai-sesi", "mulai-sesi"))
    print("\n== RINGKASAN ==")
    print(f"{'AGEN':<16} {'HASIL':<5} BUKTI")
    print("-" * 78)
    for kunci, label in urutan:
        baris = cari(hasil, kunci)
        print(f"{label:<16} {baris['status']:<5} {potong(baris['bukti'], 60)}")

    gagal = [b for b in hasil if b["status"] == FAIL]
    lewat = [b for b in hasil if b["status"] == SKIP]
    print("-" * 78)
    print(f"PASS={sum(1 for b in hasil if b['status'] == PASS)} "
          f"FAIL={len(gagal)} SKIP={len(lewat)}")
    if lewat:
        print("\nTidak teruji (SKIP) - alasan apa adanya:")
        for b in lewat:
            print(f"  - {b['nama']}: {b['bukti']}")
    if gagal:
        print("\nGagal keras (FAIL):")
        for b in gagal:
            print(f"  - {b['nama']} (http={b['http']}): {b['bukti']}")
    print("\nHASIL AKHIR:", "GAGAL" if gagal else "LULUS (dengan catatan)" if lewat else "LULUS")
    return 1 if gagal else 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Periksa seluruh permukaan agen MealChain Guardian lewat HTTP."
    )
    p.add_argument(
        "--base",
        default=os.environ.get("MEALCHAIN_BASE") or "http://localhost:8000",
        help="URL dasar API, boleh memuat /api (bawaan: env MEALCHAIN_BASE atau "
        "http://localhost:8000)",
    )
    p.add_argument(
        "--email", default=os.environ.get("MEALCHAIN_EMAIL") or "sppg.head@demo.local",
        help="akun yang dipakai (bawaan: kepala SPPG demo)",
    )
    p.add_argument(
        "--password", default=os.environ.get("MEALCHAIN_PASSWORD") or "Demo#SPPG2026",
        help="kata sandi akun (bawaan: kata sandi akun demo)",
    )
    p.add_argument("--commodity", default="beras", help="komoditas untuk putaran demo")
    p.add_argument(
        "--timeout",
        type=float,
        default=TIMEOUT_BAWAAN,
        help=f"batas detik operasi berat: run + SSE (bawaan {TIMEOUT_BAWAAN:.0f})",
    )
    p.add_argument(
        "--mulai-sesi",
        action="store_true",
        help="buka sesi demo dulu bila belum aktif (menyemai template; ubah data demo)",
    )
    p.add_argument(
        "--insecure", action="store_true", help="lewati verifikasi TLS (sertifikat sendiri)"
    )
    args = p.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - konsol aneh tidak boleh menggagalkan cek
            pass

    http = Http(args.base, args.timeout, insecure=args.insecure)
    hasil: list[dict] = []
    print("== MealChain Guardian | cek permukaan agen ==")
    print(f"base={http.base} komoditas={args.commodity} akun={args.email} "
          f"timeout_berat={args.timeout:.0f}s\n")

    if not cek_health(http, hasil):
        return cetak_ringkasan(hasil)
    token = cek_login(http, hasil, args.email, args.password)
    if token is None:
        for nama in ("sesi-demo", "supervisor", "feedback", "supervisor-ask",
                     "commodities", "demo-run", "demo-stream", "traces", "keputusan"):
            catat(hasil, nama, SKIP, "-", "tidak dijalankan: login gagal")
        return cetak_ringkasan(hasil)

    sesi = cek_sesi_demo(http, hasil, token)
    if args.mulai_sesi and not sesi.get("active"):
        # Opt-in eksplisit: hanya geladi yang boleh membuka sesi (menyemai
        # template ~40 detik dan mengubah isi database demo).
        try:
            st, mentah, _ = http.panggil(
                "POST", "/demo/session/start",
                body={"mode": "replay", "menit": 120},
                token=token, timeout=max(args.timeout, 180),
            )
        except (urllib.error.URLError, OSError, socket.timeout) as exc:
            catat(hasil, "mulai-sesi", FAIL, "-", f"tidak bisa dihubungi: {exc}")
        else:
            obj = baca_json(mentah) or {}
            catat(
                hasil,
                "mulai-sesi",
                PASS if st == 200 else FAIL,
                st,
                f"created={obj.get('created')} mode={obj.get('mode')} "
                f"status={obj.get('status')}"
                if st == 200
                else f"gagal membuka sesi: {teks_galat(obj, mentah)}",
            )
            sesi = cek_sesi_demo(http, hasil, token)

    cek_supervisor(http, hasil, token)
    cek_feedback(http, hasil, token)
    cek_ask(http, hasil, token)
    cek_commodities(http, hasil, token, args.commodity)

    putaran = cek_run(http, hasil, token, args.commodity, args.timeout)
    cek_stream(hasil, putaran["pendengar"], not putaran["dilewati"])
    cek_traces(http, hasil, token, putaran.get("decision_ids") or [])
    cek_keputusan(http, hasil, token)

    return cetak_ringkasan(hasil)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ndihentikan pengguna", file=sys.stderr)
        sys.exit(130)
