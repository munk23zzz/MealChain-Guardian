# Keamanan — VPS demo MealChain Guardian

Dokumen ini menyangkut **stack demo** di `infra/vps/`. Baca sebelum membuka
domain ke publik. Untuk instalasi dengan data nyata, langkah di §2 wajib, bukan
opsional.

---

## 1. Fakta yang harus diterima lebih dulu

1. **Akun demo bersifat publik.** `sppg.head@demo.local`,
   `sppg.nutritionist@demo.local`, dan `bgn.monitor@demo.local` memakai sandi
   yang tertulis di repo (`backend/app/seed/demo_credentials.py`,
   `DEMO_PASSWORDS_JURI`). Siapa pun yang bisa membaca repo — termasuk mirror
   publik — tahu sandi itu. Anggap ketiga akun ini **kredensial terbuka**.
2. **`bgn.monitor` adalah peran nasional dengan hak admin terbatas.** Endpoint
   `GET/PATCH /admin/users/{id}` dan `/admin/locations/{id}` hanya menerima
   peran `bgn_monitor`. Karena sandinya publik, siapa pun yang bisa membuka UI
   dapat mengubah nama/lokasi pengguna demo. Ini **disengaja untuk demo**, bukan
   bug — tetapi artinya instance ini tidak boleh memuat data nyata.
3. **Tidak ada pendaftaran publik.** Audit rute backend menunjukkan tidak ada
   endpoint `POST /auth/register` atau pembuatan pengguna mandiri; pembuatan
   akun hanya lewat seed. Jadi tidak ada tombol "daftar" yang perlu dimatikan —
   tetapi periksa ulang bila kode berubah.
4. **`DEMO_MODE=true` membuka jalur demo.** Endpoint `GET /auth/demo-accounts`
   (butuh token `bgn_monitor`) mengembalikan email + sandi demo. Di mode
   non-demo endpoint itu menjawab `{enabled:false, accounts:[]}`. Karena sandi
   demo memang publik, ini bukan kebocoran tambahan — tetapi tetap jangan
   nyalakan `DEMO_MODE` pada instance berisi data sungguhan.
5. **`DEMO_LOGIN_AUTOFILL` mengirim sandi ke browser.** Bila `true` (dan
   `DEMO_LOGIN_ALLOW_REMOTE=true`), layar login menerima sandi ketiga peran
   tanpa otentikasi. Bawaan stack ini **false**; biarkan begitu kecuali Anda
   memang ingin juri bisa masuk satu klik.
6. **`ENABLE_DOCS=false`.** `/docs`, `/redoc`, dan `/openapi.json` menjawab 404.
   Jangan dinyalakan di instance publik.
7. **Backend hanya terjangkau lewat Caddy.** Postgres/backend/mock-sap tidak
   punya port host. Jangan menambahkan `ports:` pada layanan itu "untuk debug" —
   itulah cara pembatas login per-IP dan isolasi DB hilang.

---

## 2. Sebelum instance ini dipakai di luar sesi juri

Pilih salah satu jalur:

### A. Tetap mode demo (paling umum untuk lomba)

- **Ganti sandi akun demo** sebelum dipublikasikan. `DEMO_PASSWORD_<ROLE>` di
  `.env` hanya dipakai saat akun **dibuat** oleh seed; akun yang sudah ada di
  database tidak ikut berubah. Untuk instance yang sudah hidup, ubah hash-nya
  langsung:

  ```bash
  COMPOSE="docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env"

  read -rsp "Sandi baru sppg.head@demo.local: " PW; echo
  HASH=$($COMPOSE exec -T backend python -c \
    "import bcrypt,sys;print(bcrypt.hashpw(sys.stdin.read().strip().encode(),bcrypt.gensalt()).decode())" <<<"$PW")
  $COMPOSE exec -T postgres psql -U mealchain -d mealchain -v ON_ERROR_STOP=1 \
    -c "UPDATE users SET password_hash = '$HASH' WHERE email = 'sppg.head@demo.local';"
  unset PW HASH
  ```

  Ulangi untuk `sppg.nutritionist@demo.local` dan `bgn.monitor@demo.local`
  (peran kota lain, `*.bandung@`/`*.surabaya@`, memakai sandi demo yang sama —
  ikut diganti bila instance benar-benar publik).

- **Matikan autofill sandi**: `DEMO_LOGIN_AUTOFILL=false` dan
  `DEMO_LOGIN_ALLOW_REMOTE=false` (bawaan).
- **Reset data sebelum/antar sesi**: `bash infra/vps/reset-demo.sh` — data
  yang diubah pengunjung (approval, PO, penerimaan) kembali ke template.
- **Perketat laju login**: `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW` di `.env`
  (bawaan 10 percobaan / 60 detik per IP). Caddy di stack ini **tidak** punya
  modul rate-limit (image resmi tanpa plugin), jadi pembatas aplikasi +
  firewall adalah garis pertahanannya. Bila butuh pembatas di tepi, buat image
  Caddy kustom dengan `caddy-ratelimit` atau pasang `fail2ban` yang membaca log
  JSON Caddy (`docker compose logs caddy`).
- **Batasi ukuran body** (sudah aktif): 10 MB API, 2 MB UI (`MAX_BODY_*`).

### B. Instance dengan data nyata

1. `DEMO_MODE=false`, `DEMO_LOGIN_AUTOFILL=false`,
   `DEMO_LOGIN_ALLOW_REMOTE=false`.
2. Jangan jalankan seed demo (`deploy.sh` menjalankan
   `app.seed.demo_template` dan menanam akun demo). Pakai
   `python -m app.seed.db_mode init-default` untuk skema + referensi saja, lalu
   buat akun lewat jalur admin.
3. Ganti/hapus akun demo (`sppg.head@demo.local` dkk) — seed referensi menanam
   mereka beserta sandi demo.
4. `ENABLE_DOCS=false`, `DEBUG=false`.
5. Isi `SIGNING_KEY_HEX` bila dossier harus bertanda tangan; kosong = status
   `unsigned` yang jujur, bukan tanda tangan palsu.
6. Pasang backup otomatis (`pg_dump` harian) dan uji restore.

---

## 3. Yang TIDAK BOLEH pernah di-commit / ditaruh di VPS demo

| Jangan | Kenapa |
|---|---|
| **Kunci AWS asli** (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) | Bisa menagih akun Anda; VPS demo semi-publik. Pakai IAM role / Instance Profile dengan izin minimum. |
| `SAP_AI_CORE_CLIENT_SECRET`, `SAP_MCP_TOKEN` asli | Kredensial tenant SAP; memuat karakter `$` dan mudah rusak bila disalin ke compose. |
| `INFERHUB_API_KEY`, kunci model LLM | Tagihan pihak ketiga. |
| `JWT_SECRET` nilai nyata | Siapa pun yang memegangnya bisa membuat token sah untuk peran mana pun. |
| `SIGNING_KEY_HEX` nyata | Kunci tanda tangan dossier. |
| `infra/vps/.env`, `.env.local`, `*.env.bak*` | Berisi semua di atas. `.gitignore` sudah menutup `.env`, tetapi **periksa `git status` sebelum commit**. |
| Dump database (`*.dump`, `*.sql`) ke repo | Memuat data pengguna dan hash sandi. |
| Sertifikat/privat key TLS (`*.key`, `*.crt` pihak ketiga) | Sertifikat Let's Encrypt di stack ini dikelola volume Docker `caddy_data`, bukan berkas repo. |

Yang **harus** ada di repo dan boleh publik: `.env.vps.example` (placeholder
saja), `docker-compose.vps.yml`, `Caddyfile`, skrip, dan dokumen ini.

---

## 4. Perilaku yang sudah dikeraskan di stack ini

- TLS otomatis + HSTS (`max-age=31536000; includeSubDomains`), `-Server`.
- Header keamanan: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy`; CSP tetap milik aplikasi (Next.js & FastAPI), bukan Caddy —
  dua header CSP akan digabung lebih ketat oleh browser dan bisa mematikan UI.
- Body limit per situs (API 10 MB, UI 2 MB).
- Timeout baca/tulis; SSE di-flush segera (bukan buffered).
- `X-Forwarded-For` ditimpa Caddy dengan IP asli klien supaya pembatas login
  per-IP tidak bisa dilewati dengan header karangan.
- `.env` tidak masuk image dan tidak di-mount; dibaca sebagai `env_file`.
- Compose menolak start bila `JWT_SECRET`/`POSTGRES_PASSWORD`/`DOMAIN` kosong
  (fail-closed), dan `deploy.sh` menolak nilai placeholder.

---

## 5. Bila terjadi kebocoran

1. `JWT_SECRET` bocor → rotasi (README §4.3). Semua sesi lama otomatis gugur.
2. `POSTGRES_PASSWORD` bocor → ganti di `.env`, lalu
   `docker compose exec postgres psql -c "ALTER USER mealchain PASSWORD '...'"`,
   `docker compose up -d --force-recreate backend mock-sap`.
3. Kunci AWS/SAP bocor → **revoke di konsol cloud**, bukan sekadar mengganti
   berkas. Periksa CloudTrail pemakaian tak dikenal.
4. Data demo dikotori pengunjung → `bash infra/vps/reset-demo.sh`.
