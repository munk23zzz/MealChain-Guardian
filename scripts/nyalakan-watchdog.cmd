@echo off
REM Penjaga tunnel MealChain Guardian — dipanggil Windows Task Scheduler saat logon.
REM Satu-satunya pemilik cloudflared: URL baru langsung disinkronkan ke
REM environment runtime AgentCore, .env, dan aplikasi Joule di Cloud Foundry.
cd /d "E:\hackathon\HackathonAWS\mealchain-guardian"
"C:\Python314\python.exe" -u agent\tunnel_watchdog.py >> .tunnel-watchdog.log 2>&1
