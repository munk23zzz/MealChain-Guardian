#!/usr/bin/env bash
# Bagian 3 investigasi (c): reproduksi skenario insiden
# "teardown membunuh proses compose saat `up` berjalan" -> container ditinggal Exited(0)?
set -u
cd "E:/hackathon/HackathonAWS/mealchain-guardian" || exit 1
C=mcg-mut-frontend-1
LOG=verify/frontend-exit0-repro.log
EV=verify/frontend-exit0-repro-events.log
: > "$LOG"; : > "$EV"
say() { echo "== $*" | tee -a "$LOG"; }
st() { docker inspect "$C" --format 'status={{.State.Status}} exit={{.State.ExitCode}} restartCount={{.RestartCount}} finished={{.State.FinishedAt}}' 2>&1 | tee -a "$LOG"; }

docker start "$C" >/dev/null 2>&1
sleep 8
say "sebelum"; st
docker events --filter "container=$C" --format '{{.Time}} {{.Action}} exit={{.Actor.Attributes.exitCode}}' >> "$EV" 2>&1 &
EVPID=$!
sleep 1

attempt() {
  delay=$1
  say "percobaan: compose up --force-recreate frontend, lalu taskkill proses compose setelah ${delay}s"
  docker compose -p mcg-mut -f verify/docker-compose.mutations.yml up -d --force-recreate frontend > verify/repro-up.log 2>&1 &
  CPID=$!
  sleep "$delay"
  # cari proses docker compose (klien) lalu bunuh beserta anaknya, seperti teardown runner
  WINPID=$(ps -W 2>/dev/null | grep -i "docker-compose\|docker compose" | awk '{print $4}' | head -1)
  if [ -n "${WINPID:-}" ]; then
    taskkill //PID "$WINPID" //T //F >/dev/null 2>&1 && say "taskkill compose windows PID $WINPID"
  else
    kill -9 "$CPID" 2>/dev/null && say "kill -9 klien compose (bash PID $CPID)"
  fi
  wait "$CPID" 2>/dev/null
  say "exit klien compose=$?"
  sleep 4
  say "setelah dibunuh"; st
  docker ps -a --filter "name=mcg-mut-frontend" --format 'ps -a: {{.Names}} {{.Status}}' | tee -a "$LOG"
}

attempt 1
say "pulihkan"
docker compose -p mcg-mut -f verify/docker-compose.mutations.yml up -d frontend > /dev/null 2>&1
sleep 10
st
attempt 2
sleep 3
kill "$EVPID" 2>/dev/null
say "events"
cat "$EV" | tee -a "$LOG"
say "pulihkan akhir"
docker compose -p mcg-mut -f verify/docker-compose.mutations.yml up -d frontend > /dev/null 2>&1
sleep 12
st
echo "GET / => $(curl -s -o /dev/null -w '%{http_code}' --max-time 30 http://127.0.0.1:13010/)" | tee -a "$LOG"
