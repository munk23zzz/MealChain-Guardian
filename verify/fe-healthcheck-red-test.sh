#!/usr/bin/env bash
# Bukti gate menangkap "kontainer hidup tapi tidak melayani" (health=unhealthy), di stack uji.
set -u
cd "E:/hackathon/HackathonAWS/mealchain-guardian" || exit 1
LOG=verify/fe-healthcheck-red-test.log
: > "$LOG"
say() { echo "== $(date +%H:%M:%S) $*" | tee -a "$LOG"; }
C=mcg-mut-frontend-1

say "nyalakan stack uji"
docker compose -p mcg-mut -f verify/docker-compose.mutations.yml up -d --wait >> "$LOG" 2>&1
say "compose exit=$?"
for i in $(seq 1 24); do
  h=$(docker inspect "$C" --format '{{with .State.Health}}{{.Status}}{{end}}' 2>/dev/null)
  [ "$h" = "healthy" ] && break
  sleep 5
done
say "health awal=$h"; docker inspect "$C" --format 'status={{.State.Status}} health={{with .State.Health}}{{.Status}}{{end}}' | tee -a "$LOG"

PID_SERVER=$(docker exec "$C" ps -o pid,args 2>/dev/null | grep "next-server" | awk '{print $1}' | head -1)
say "next-server PID=$PID_SERVER -> SIGSTOP (server diam, kontainer tetap Up)"
docker exec "$C" sh -c "kill -STOP $PID_SERVER"
for i in $(seq 1 14); do
  h=$(docker inspect "$C" --format '{{with .State.Health}}{{.Status}}{{end}}')
  say "t+$((i*15))s health=$h page=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:13010/)"
  [ "$h" = "unhealthy" ] && break
  sleep 15
done

say "jalankan gate forensics (harus FAIL karena health=unhealthy)"
python "C:/Users/User/AppData/Local/hermes/skills/software-development/fullstack-verification/scripts/verify_stack.py" verify/stack.forensics.spec.json --ui-python "C:/Users/User/AppData/Local/hermes/venvs/webapp-testing/Scripts/python.exe" > verify/run-forensics-k3.log 2>&1
say "gate exit=$?"
grep -E "container|VERDICT|\[FAIL\]" verify/run-forensics-k3.log | tee -a "$LOG"

say "pulihkan: SIGCONT"
docker exec "$C" sh -c "kill -CONT $PID_SERVER"
for i in $(seq 1 12); do
  h=$(docker inspect "$C" --format '{{with .State.Health}}{{.Status}}{{end}}')
  say "t+$((i*10))s health=$h page=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:13010/)"
  [ "$h" = "healthy" ] && break
  sleep 10
done
say "gate ulang setelah pulih (harus PASS)"
python "C:/Users/User/AppData/Local/hermes/skills/software-development/fullstack-verification/scripts/verify_stack.py" verify/stack.forensics.spec.json --ui-python "C:/Users/User/AppData/Local/hermes/venvs/webapp-testing/Scripts/python.exe" > verify/run-forensics-k4.log 2>&1
say "gate exit=$?"
grep -E "VERDICT|\[FAIL\]" verify/run-forensics-k4.log | tee -a "$LOG"
