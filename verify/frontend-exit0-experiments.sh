#!/usr/bin/env bash
# Investigasi (c): kenapa container frontend pernah "Exited (0)".
# Semua eksperimen hanya pada container stack uji mcg-mut-frontend-1.
set -u
cd "E:/hackathon/HackathonAWS/mealchain-guardian" || exit 1
C=mcg-mut-frontend-1
LOG=verify/frontend-exit0-experiments.log
EV=verify/frontend-exit0-events.log
: > "$LOG"; : > "$EV"

say() { echo "== $*" | tee -a "$LOG"; }
state() {
  docker inspect "$C" --format 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} restartCount={{.RestartCount}} started={{.State.StartedAt}} finished={{.State.FinishedAt}}' 2>&1 | tee -a "$LOG"
}

say "tunggu stack uji siap"
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:13010/ || true)
  [ "$code" = "200" ] && break
  sleep 5
done
say "frontend uji http=$code"

docker events --filter "container=$C" --format '{{.Time}} {{.Action}} exit={{.Actor.Attributes.exitCode}}' >> "$EV" 2>&1 &
EVPID=$!
sleep 2
say "baseline"; state

# ---------- E5: SIGTERM langsung ke PID 1 (paling bersih: tidak lewat docker stop) ----------
say "E5: docker exec kill -TERM 1"
docker exec "$C" sh -c 'kill -TERM 1' 2>&1 | tee -a "$LOG"
sleep 6
say "E5 hasil"; state
say "E5 30 detik kemudian (apakah unless-stopped menghidupkan lagi?)"
sleep 30
state

# ---------- E1: docker stop (graceful) ----------
say "E1: docker start lalu docker stop"
docker start "$C" >/dev/null 2>&1
for i in $(seq 1 20); do
  docker inspect "$C" --format '{{.State.Status}}' | grep -q running && break
  sleep 3
done
sleep 10
state
docker stop "$C" 2>&1 | tee -a "$LOG"
sleep 5
say "E1 hasil"; state
sleep 20
say "E1 +20s"; state

# ---------- E2: SIGKILL ----------
say "E2: docker start lalu docker kill -s KILL (kontrol: harus 137)"
docker start "$C" >/dev/null 2>&1
for i in $(seq 1 20); do
  docker inspect "$C" --format '{{.State.Status}}' | grep -q running && break
  sleep 3
done
sleep 10
docker kill -s KILL "$C" 2>&1 | tee -a "$LOG"
sleep 8
say "E2 hasil (137 = SIGKILL)"; state
sleep 25
say "E2 +25s (unless-stopped seharusnya menghidupkan ulang)"; state

kill "$EVPID" 2>/dev/null
say "events (docker daemon)"
cat "$EV" | tee -a "$LOG"

say "ringkasan exit code per aksi"
grep -E "^(E5|E1|E2) hasil" -A 1 "$LOG" | tee -a "$LOG"
