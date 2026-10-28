"""Jalankan pytest Fase 6 di KLON DB (DB demo hanya SELECT).

Pemakaian di dalam kontainer backend:
    python _qa/f6/run_f6.py <nama_db_kulon> <berkas_tes> [berkas_tes ...]

DSN diturunkan dari os.environ['DATABASE_URL'] (env kontainer), nama DB diganti
lewat lambda (bukan backreference) supaya tidak ada nama DB rusak.
"""
import os
import re
import subprocess
import sys

if len(sys.argv) < 3:
    print("pakai: run_f6.py <db> <tes...>")
    sys.exit(2)

db = sys.argv[1]
tests = sys.argv[2:]
url = os.environ["DATABASE_URL"]
clone = re.sub(r"/[A-Za-z0-9_]+(\?|$)", lambda m: "/" + db + m.group(1), url, count=1)
print("DB =", clone.rsplit("@", 1)[-1], flush=True)

env = dict(os.environ, DATABASE_URL=clone, DEMO_SESSION_ENFORCE="false")
args = [sys.executable, "-m", "pytest", *tests, "-q", "--tb=short", "-p", "no:cacheprovider"]
rc = subprocess.call(args, env=env)
print("PYTEST_EXIT =", rc, flush=True)
sys.exit(rc)
