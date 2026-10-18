"""Penjaga jalur agent: memiliki Quick Tunnel dan menyinkronkan URL ke AgentCore.

Masalah yang dijaga (T1 di `_qa/uji-ketat-2026-10-18.md`): runtime AgentCore
memanggil backend lewat URL publik. Quick Tunnel memberi URL acak yang berubah
setiap proses cloudflared restart; kalau URL berubah tanpa sinkronisasi, worker
berhenti diam-diam (`agent_review: unavailable`) dan itu baru terlihat di depan
juri.

Cara kerja:
  1. jalankan cloudflared sebagai anak proses, baca URL dari keluarannya
  2. bila URL berbeda dari yang tercatat, panggil `agent/set_runtime_env.py`
     (menunggu runtime READY, bukan sekadar "update dikirim")
  3. verifikasi `/health` pada URL itu benar-benar 200 dari luar
  4. bila cloudflared mati, ulangi — URL baru otomatis disinkronkan lagi

Jalankan:  python agent/tunnel_watchdog.py            (loop, untuk service/task)
           python agent/tunnel_watchdog.py --self-test (uji logika murni)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "agent" / ".tunnel_state.json"
CLOUDFLARED = Path(r"C:/Program Files (x86)/cloudflared/cloudflared.exe")
BACKEND = "http://localhost:8000"
URL_RE = re.compile(r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com")


def parse_url(teks: str) -> str | None:
    """Ambil URL tunnel pertama dari keluaran cloudflared (None bila belum ada)."""
    cocok = URL_RE.search(teks or "")
    return cocok.group(0) if cocok else None


def perlu_sinkron(url_baru: str | None, url_tercatat: str | None) -> bool:
    """Sinkron hanya bila ada URL baru yang berbeda dari yang tercatat."""
    if not url_baru:
        return False
    return url_baru != url_tercatat


def baca_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def tulis_state(data: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def backend_hidup(url: str, coba: int = 20, jeda: float = 3.0) -> bool:
    """Tunggu `/health` pada URL publik sampai 200 (DNS tunnel butuh beberapa detik)."""
    for _ in range(coba):
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=10) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(jeda)
    return False


def panaskan_runtime(coba: int = 8, jeda: float = 8.0) -> bool:
    """Paksa satu review nyata sampai worker benar-benar jalan.

    Setelah runtime READY, container masih sempat "dingin": satu-dua panggilan
    pertama bisa `unavailable` walau URL sudah benar. Pemanasan ini memakai jalur
    yang sama dengan aplikasi (bukan /health), jadi bila lulus berarti agent
    benar-benar bisa memanggil backend lewat URL baru.
    """
    skrip = (
        "from app.services.agent_review_client import review_decision;"
        "from sqlalchemy import create_engine, text;"
        "e=create_engine('postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain');"
        "d=e.connect().execute(text('select id from decisions order by created_at desc limit 1')).scalar_one();"
        "r=review_decision(str(d));print('HASIL', r.status, r.error)"
    )
    for i in range(coba):
        hasil = subprocess.run(
            ["docker", "exec", "-w", "/app", "mealchain-backend", "python", "-c", skrip],
            capture_output=True, text=True, timeout=180,
        )
        keluaran = (hasil.stdout or "") + (hasil.stderr or "")
        if "HASIL completed" in keluaran or "HASIL partial" in keluaran:
            print(f"[watchdog] pemanasan OK (percobaan {i + 1})", flush=True)
            return True
        print(f"[watchdog] pemanasan belum siap (percobaan {i + 1})", flush=True)
        time.sleep(jeda)
    return False


def sinkron(url: str, timeout_runtime: int = 300) -> bool:
    """Arahkan runtime AgentCore ke URL ini dan tunggu sampai READY."""
    perintah = [
        "uv", "run", "--no-project", "--with", "boto3",
        "python", str(ROOT / "agent" / "set_runtime_env.py"),
        "--api-url", url, "--tunggu-detik", str(timeout_runtime),
    ]
    hasil = subprocess.run(perintah, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout_runtime + 120)
    keluaran = (hasil.stdout or "") + (hasil.stderr or "")
    ok = hasil.returncode == 0 and "runtime READY" in keluaran
    print(f"[watchdog] sinkron {'OK' if ok else 'GAGAL'} untuk {url}", flush=True)
    for baris in keluaran.strip().splitlines()[-4:]:
        print(f"[watchdog]   {baris}", flush=True)
    return ok


def jalankan_tunnel() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", BACKEND],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def main_loop() -> int:
    state = baca_state()
    while True:
        print("[watchdog] menjalankan cloudflared…", flush=True)
        anak = jalankan_tunnel()
        url = None
        try:
            assert anak.stdout is not None
            for baris in anak.stdout:
                if not url:
                    url = parse_url(baris)
                if url and perlu_sinkron(url, state.get("url")):
                    if not backend_hidup(url):
                        print(f"[watchdog] {url} tidak menjawab /health, tunggu tunnel berikutnya", flush=True)
                        continue
                    if sinkron(url):
                        state = {"url": url, "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                        tulis_state(state)
                        if not panaskan_runtime():
                            print("[watchdog] pemanasan gagal: agent belum bisa memanggil backend", flush=True)
                    else:
                        print("[watchdog] sinkron gagal, akan dicoba lagi di iterasi berikutnya", flush=True)
        except KeyboardInterrupt:
            anak.terminate()
            return 0
        finally:
            try:
                anak.wait(timeout=5)
            except subprocess.TimeoutExpired:
                anak.kill()
        print("[watchdog] cloudflared berhenti; mulai ulang dalam 5 detik", flush=True)
        time.sleep(5)


def self_test() -> int:
    kasus = [
        ("2026-10-18 INF |  https://suggest-venue-mortgage-able.trycloudflare.com  |", "https://suggest-venue-mortgage-able.trycloudflare.com"),
        ("no url here", None),
        ("https://abc.trycloudflare.com dan https://def.trycloudflare.com", "https://abc.trycloudflare.com"),
    ]
    for teks, harap in kasus:
        dapat = parse_url(teks)
        assert dapat == harap, f"parse_url({teks!r}) = {dapat!r}, harusnya {harap!r}"
    assert perlu_sinkron("https://a.trycloudflare.com", None) is True
    assert perlu_sinkron("https://a.trycloudflare.com", "https://a.trycloudflare.com") is False
    assert perlu_sinkron("https://b.trycloudflare.com", "https://a.trycloudflare.com") is True
    assert perlu_sinkron(None, "https://a.trycloudflare.com") is False
    print("self-test: 7 pemeriksaan lulus")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    sys.exit(self_test() if args.self_test else main_loop())
