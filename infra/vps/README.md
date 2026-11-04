# Deploy MealChain Guardian di satu VPS

Panduan ini memasang **seluruh** stack MealChain Guardian di satu VPS Ubuntu
(2 vCPU / 2 GB RAM) memakai Docker Compose v2:

```
Internet
   │  80/443 (hanya ini yang terbuka)
   ▼
┌──────────────┐
│    caddy     │  TLS otomatis (Let's Encrypt), gzip/zstd, header keamanan
└──┬────────┬──┘
   │        │
   │        └──────────────► https://api.<DOMAIN>  →  backend:8000  (FastAPI)
   │
   └───────────────────────► https://<DOMAIN>      →  frontend:3000 (Next.js)

backend ──► postgres:5432        (jaringan internal compose, TIDAK dipublish)
backend ──► mock-sap:8001        (jaringan internal compose, TIDAK dipublish)
```

Yang dipublish ke host hanya **caddy (80/443)**. Postgres, backend, dan mock-sap
tidak punya port host sama sekali — tidak bisa dijangkau dari internet maupun
dari shell VPS kecuali lewat `docker compose exec`.

Berkas di direktori ini:

| Berkas | Isi |
|---|---|
| `docker-compose.vps.yml` | definisi 5 layanan (postgres, backend, mock-sap, frontend, caddy) |
| `Caddyfile` | reverse proxy + HTTPS otomatis |
| `.env.vps.example` | templat konfigurasi (semua variabel, nilai placeholder) |
| `deploy.sh` | pasang/perbarui (idempoten) + migrasi + seed demo |
| `reset-demo.sh` | segarkan data demo antar sesi juri + laporkan jumlah baris |
| `README.md` | berkas ini |
| `SECURITY.md` | hal yang WAJIB dibaca sebelum membuka ke publik |

---

## 1. Prasyarat

### 1.1 VPS

- Ubuntu 22.04 atau 24.04, **2 vCPU / 2 GB RAM** (1 GB terlalu kecil untuk
  `next build`).
- Disk 20 GB ke atas.

### 1.2 Swap 2 GB (WAJIB)

Build image frontend (`next build`) bisa memakai >1,5 GB. Tanpa swap, build
bisa mati dengan `Killed` / `exit 137`.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
# opsional: kurangi agresivitas swap
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p

free -h          # baris "Swap:" harus 2.0Gi
```

### 1.3 Firewall Tencent Lighthouse

Buka **hanya** port berikut di konsol Lighthouse
(*Instance → Firewall / Security Group*):

| Port | Protokol | Keterangan |
|---|---|---|
| 80 | TCP | verifikasi ACME + redirect ke HTTPS |
| 443 | TCP + UDP | HTTPS (TCP) dan HTTP/3 (UDP) |
| 22 | TCP | SSH (hanya bila perlu; batasi ke IP Anda) |

Jangan buka 3000, 8000, 8001, 5432 — aplikasi tidak memakainya dari luar.

Bila `ufw` aktif di dalam VPS, samakan:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
sudo ufw status
```

### 1.4 DNS

Buat dua **A record** ke IP publik VPS (TTL 300):

| Nama | Tipe | Nilai |
|---|---|---|
| `demo.mealchain.id` (atau domain Anda) | A | `<IP VPS>` |
| `api.demo.mealchain.id` | A | `<IP VPS>` |

Cek dari mesin lain sebelum deploy:

```bash
dig +short demo.mealchain.id
dig +short api.demo.mealchain.id
```

**DNS harus sudah benar sebelum `deploy.sh` dijalankan.** Caddy akan mencoba
ulang, tetapi percobaan gagal berulang bisa kena rate-limit Let's Encrypt
(5 kegagalan / jam).

### 1.5 Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker            # atau logout lalu login lagi
docker compose version   # harus "Docker Compose version v2.x"
```

`deploy.sh` memakai plugin `docker compose` (v2). Perintah lama
`docker-compose` tidak dipakai.

### 1.6 Repo di VPS

```bash
git clone <repo-url> ~/mealchain-guardian
cd ~/mealchain-guardian
```

Yang dibutuhkan saat runtime: `backend/`, `frontend/`, `data/`, dan
`infra/vps/`. Build context compose menunjuk `../../backend` dan
`../../frontend` relatif terhadap berkas compose, jadi **jangan** memindahkan
`infra/vps/` keluar dari repo.

---

## 2. Langkah pertama (sekali saja)

```bash
cd ~/mealchain-guardian

# 1) buat .env dari templat
cp infra/vps/.env.vps.example infra/vps/.env
chmod 600 infra/vps/.env

# 2) buat dua kunci acak
openssl rand -hex 32     # → JWT_SECRET
openssl rand -hex 24     # → POSTGRES_PASSWORD

# 3) isi .env (minimal: DOMAIN, ACME_EMAIL, JWT_SECRET, POSTGRES_PASSWORD)
nano infra/vps/.env

# 4) jalankan deploy (sekali pertama: build 5-15 menit di 2 vCPU)
bash infra/vps/deploy.sh
```

`deploy.sh` berhenti sendiri pada dua kondisi:

1. `.env` belum ada — berkas templat disalin lalu skrip keluar dengan instruksi.
2. `JWT_SECRET`/`POSTGRES_PASSWORD` masih `GANTI_...` atau DOMAIN masih
   `example.com` — skrip menolak menyalakan stack dengan kunci contoh.

Yang dilakukan skrip, berurutan: cek Docker → validasi `.env` → `pull` →
`build` → `up -d` → tunggu backend `healthy` (GET `/health`) →
`alembic upgrade head` → `app.seed.reference` → `app.seed.demo_template`
(sekali, dijaga penanda `infra/vps/.seed-done`) → cetak URL.

Seed demo memakan 60-90 detik. Aman dijalankan ulang: perintah yang sama
idempoten.

### 2.1 Nilai `.env` yang biasa diubah

| Variabel | Arti |
|---|---|
| `DOMAIN` | domain UI; `api.<DOMAIN>` dipakai otomatis |
| `ACME_EMAIL` | email pendaftaran sertifikat |
| `POSTGRES_PASSWORD` | sandi DB (acak) |
| `JWT_SECRET` | kunci tanda tangan token (acak, ≥32 karakter) |
| `JWT_EXPIRE_MINUTES` | umur sesi login (bawaan 480 menit = 8 jam) |
| `DEMO_MODE` | `true` untuk VPS demo/juri |
| `CORS_ORIGINS` | kosong = otomatis `https://<DOMAIN>` (disarankan) |
| `NEXT_PUBLIC_API_URL` | kosong = otomatis `https://api.<DOMAIN>` (disarankan) |
| `DATABASE_URL` | **tidak dibaca kontainer** — backend memakai DSN yang diturunkan dari `POSTGRES_*`, jadi sandi DB dan DSN tidak mungkin berbeda |
| `LOGIN_RATE_LIMIT`, `LOGIN_RATE_WINDOW` | batas percobaan login per IP |

`CORS_ORIGINS` dan `NEXT_PUBLIC_API_URL` **boleh dikosongkan**; compose
menurunkannya dari `DOMAIN`. Kurang satu origin di CORS = login gagal di
browser dengan pesan CORS di konsol.

---

## 3. Verifikasi

```bash
# API hidup (JSON: {"status":"healthy", ...})
curl -fsS https://api.demo.mealchain.id/health

# UI menjawab 200 dan HTTPS valid
curl -sI https://demo.mealchain.id | head -n 5

# sertifikat & masa berlaku
echo | openssl s_client -servername demo.mealchain.id \
  -connect demo.mealchain.id:443 2>/dev/null | openssl x509 -noout -subject -dates

# header keamanan
curl -sI https://api.demo.mealchain.id/health | grep -iE 'strict-transport|content-security|x-frame'
```

Cek status kontainer:

```bash
docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env ps
```

Semua layanan harus `running`; `postgres`, `backend`, dan `frontend` harus
`(healthy)` (caddy tidak punya healthcheck).

### 3.1 Login

Buka `https://<DOMAIN>` lalu masuk dengan akun demo:

| Email | Peran |
|---|---|
| `sppg.head@demo.local` | Kepala SPPG (Jakarta) |
| `sppg.nutritionist@demo.local` | Ahli Gizi (Jakarta) |
| `bgn.monitor@demo.local` | Pemantau BGN (nasional) |

Sandi demo ada di `backend/app/seed/demo_credentials.py`
(`DEMO_PASSWORDS_JURI`) — **kredensial publik**, lihat `SECURITY.md`.

Bila login berhasil tetapi panel kosong: data demo belum tersemai. Jalankan
`bash infra/vps/reset-demo.sh`.

---

## 4. Operasi harian

### 4.1 Lihat log

```bash
cd ~/mealchain-guardian
COMPOSE="docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env"

$COMPOSE logs -f --tail 100 caddy      # sertifikat, 4xx/5xx, error proxy
$COMPOSE logs -f --tail 100 backend    # galat aplikasi
$COMPOSE logs -f --tail 100 frontend
$COMPOSE logs --tail 200 backend | grep -i error
$COMPOSE logs -f                       # semua layanan
```

### 4.2 Reset data demo (antar sesi juri)

```bash
bash infra/vps/reset-demo.sh
```

Skrip ini menyemai ulang dataset demo, membuka sesi demo baru, lalu mencetak
jumlah baris per tabel + revisi skema + sesi aktif. Tidak menyentuh `.env`,
tidak me-restart kontainer, tidak menghapus volume. Durasi 60-90 detik; aman
dijalankan berulang.

Laporan lengkap seed disimpan di `infra/vps/.last-seed.json`.

### 4.3 Rotasi `JWT_SECRET`

Efeknya: semua token lama tidak berlaku, semua pengguna harus login ulang.
Lakukan di luar jam demo.

```bash
cd ~/mealchain-guardian

# 1) kunci baru
NEW=$(openssl rand -hex 32)

# 2) ganti baris JWT_SECRET di .env (tanpa mencetak kunci ke riwayat shell)
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${NEW}|" infra/vps/.env
unset NEW

# 3) hanya backend perlu dibuat ulang
docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env \
  up -d --no-deps --force-recreate backend

# 4) verifikasi: token lama ditolak (401), login baru berhasil
curl -s -o /dev/null -w '%{http_code}\n' https://api.demo.mealchain.id/auth/me
```

Cabut juga sesi lama di sisi data bila perlu: `reset-demo.sh` membuka sesi baru.

### 4.4 Perbarui kode

```bash
cd ~/mealchain-guardian
git pull
bash infra/vps/deploy.sh          # build ulang + migrasi; seed dilewati
```

Seed dilewati karena penanda `.seed-done` sudah ada. Untuk memaksa:
`bash infra/vps/deploy.sh --reseed`.

**Catatan:** perubahan `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_USE_MOCK`, atau
`NEXT_PUBLIC_BASE_PATH` hanya berlaku setelah **build ulang** image frontend
(variabel ini masuk ke bundel klien saat `next build`). `deploy.sh` selalu
menjalankan `build`, jadi cukup jalankan ulang skrip itu.

### 4.5 Backup / restore database

```bash
COMPOSE="docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env"

# backup
$COMPOSE exec -T postgres pg_dump -U mealchain -d mealchain -Fc > ~/mealchain-$(date +%F).dump

# restore (DB tujuan kosong!)
$COMPOSE exec -T postgres pg_restore -U mealchain -d mealchain --clean --if-exists < ~/mealchain-2026-11-04.dump
```

### 4.6 Hentikan / hapus

```bash
COMPOSE="docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env"
$COMPOSE stop              # hentikan, data tetap
$COMPOSE down              # hapus kontainer + jaringan, volume TETAP
$COMPOSE down -v           # HAPUS JUGA DATABASE & sertifikat (hati-hati)
```

---

## 5. Pemecahan masalah

| Gejala | Penyebab lazim | Tindakan |
|---|---|---|
| Caddy log: `no such host` / `could not get certificate` | DNS belum menunjuk ke VPS, atau port 80 tertutup | cek `dig`, buka 80/443 di Lighthouse, lalu `$COMPOSE restart caddy` |
| `502 Bad Gateway` di UI | frontend/backend belum sehat | `$COMPOSE ps`, `$COMPOSE logs backend` |
| UI terbuka tetapi login gagal (konsol: CORS) | `CORS_ORIGINS` salah/terisi manual | kosongkan `CORS_ORIGINS` di `.env`, jalankan `deploy.sh` |
| Halaman kosong, konsol: CSP menolak `https://api...` | image frontend lama (dibangun sebelum `NEXT_PUBLIC_API_URL` benar) | `deploy.sh` (build ulang) |
| `Killed` / `exit 137` saat build frontend | RAM habis, swap belum aktif | pasang swap 2 GB (§1.2), build ulang |
| Backend `unhealthy` | kredensial DB beda, migrasi belum jalan | `$COMPOSE logs backend`; `$COMPOSE exec -T backend alembic upgrade head` |
| Panel kosong padahal login berhasil | data demo belum tersemai / sesi kedaluwarsa | `bash infra/vps/reset-demo.sh` |
| Reset Let's Encrypt rate limit | terlalu banyak percobaan saat DNS salah | tunggu (bisa 1 minggu) atau uji dengan `staging` CA |

Debug cepat dari dalam VPS (tanpa membuka port):

```bash
docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env \
  exec -T backend python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/health').read()[:200])"
```

---

## 6. Peringatan keamanan

> **JANGAN TARUH KUNCI AWS ASLI DI SINI.**
>
> Jangan menaruh `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
> `SAP_AI_CORE_CLIENT_SECRET` asli, atau kredensial akun cloud mana pun di
> `infra/vps/.env` pada VPS demo ini. VPS demo bersifat semi-publik: siapa pun
> yang memegang akses shell (atau menemukan berkas `.env` di backup/snapshot)
> memegang kunci itu, dan kunci AWS bisa dipakai menagih akun Anda.
>
> Integrasi AWS/SAP pada stack demo memakai **mock** (`SAP_PROVIDER=mock`).
> Untuk demo dengan layanan asli, pakai IAM role/Instance Profile dengan izin
> minimum — bukan kunci statis di `.env`.

Sebelum membuka instance ke publik, baca **`SECURITY.md`** di direktori ini:
akun demo bersifat publik, dan ada langkah wajib sebelum dipakai di luar sesi
juri.
