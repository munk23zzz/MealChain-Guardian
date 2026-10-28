import os, re, subprocess, sys
u = os.environ["DATABASE_URL"]
clone = re.sub(r"/[A-Za-z0-9_]+(\?|$)", lambda m: "/" + os.environ["F6_DB"] + m.group(1), u, count=1)
print("DB =", clone.rsplit("@", 1)[-1], flush=True)
env = dict(os.environ, DATABASE_URL=clone, DEMO_SESSION_ENFORCE="false")
args = [sys.executable, "-m", "pytest", *os.environ["F6_TESTS"].split(), "-q", "--tb=short", "-p", "no:cacheprovider"]
rc = subprocess.call(args, env=env)
print("EXIT =", rc, flush=True)
sys.exit(rc)
