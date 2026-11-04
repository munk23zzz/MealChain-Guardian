# Keamanan — VPS demo MealChain Guardian

Dokumen ini menyangkut **stack demo** di `infra/vps/`. Baca sebelum membuka
domain ke publik. Untuk instalasi dengan data nyata, langkah di §4 wajib, bukan
opsional.

Status audit: **4 November 2026** — kode di `vps-deploy` + instance hidup
`http://43-129-50-209.sslip.io` (hanya 80/TCP). Setiap temuan punya rujukan
berkas:baris; temuan yang tidak bisa dibuktikan dari kode tidak dimuat di sini.

---

## 0. Ringkasan yang harus diingat

1. **Cabang `vps-deploy` = root di VPS.** Autopull menarik cabang itu tiap 3
   menit dan menjalankannya sebagai root. Repo ini **publik**, jadi kendali
   satu-satunya adalah siapa yang boleh *push* (§3 K-1).
2. **Repo publik memuat sandi demo.** Terverifikasi: `curl` ke
   `raw.githubusercontent.com/.../vps-deploy/backend/app/seed/demo_credentials.py`
   menjawab 200 dan mencetak ketiga sandi. Sandi itu *bukan* rahasia.
3. **Instance berjalan di HTTP polos.** Tanpa TLS, sandi dan token JWT lewat
   jaringan terbuka (§3 T-1).
4. **Tidak ada eskalasi peran lewat JWT.** Peran selalu dibaca dari DB, bukan
   dari klaim token (§5).

---

## 1. Fakta yang harus diterima lebih dulu

1. **Akun demo bersifat publik.** `sppg.head@demo.local`,
   `sppg.nutritionist@demo.local`, dan `bgn.monitor@demo.local` memakai sandi
   yang tertulis di repo (`backend/app/seed/demo_credentials.py:30-34`) dan
   repo-nya publik. Anggap ketiga akun ini **kredensial terbuka**.
2. **`bgn.monitor` adalah peran nasional dengan hak admin terbatas.** Endpoint
   `GET/PATCH /admin/users/{id}` dan `/admin/locations/{id}` hanya menerima
   peran `bgn_monitor` (`backend/app/api/admin.py:36,86-224`). Karena sandinya
   publik, siapa pun yang bisa membuka UI dapat mengubah nama/lokasi/peran
   pengguna demo — **dan setiap perubahan tercatat di ledger**. Ini disengaja
   untuk demo, bukan bug; artinya instance ini tidak boleh memuat data nyata.
3. **Tidak ada pendaftaran publik.** Tidak ada `POST /auth/register` atau
   pembuatan pengguna mandiri; akun hanya lahir dari seed. (Diperiksa ulang
   4 Nov 2026: satu-satunya rute tanpa `Depends(...)` adalah
   `GET /auth/demo-login`, lihat §5.)
4. **`DEMO_MODE=true` membuka jalur demo.** `GET /auth/demo-accounts`
   (butuh token `bgn_monitor`) mengembalikan email + sandi demo
   (`backend/app/api/auth.py:271-295`). Di mode non-demo jawabannya tetap
   `{enabled:false, accounts:[]}`.
5. **`DEMO_LOGIN_AUTOFILL` mengirim sandi ke browser.** Bila `true` (dan
   `DEMO_LOGIN_ALLOW_REMOTE=true`), layar login menerima sandi ketiga peran
   tanpa otentikasi. Bawaan stack ini **false**, dan instance hidup menjawab
   `{"enabled":false,"accounts":[]}` (terukur 4 Nov 2026, 31 byte).
6. **`ENABLE_DOCS=false`.** `/docs`, `/redoc`, dan `/openapi.json` menjawab 404
   (`backend/app/main.py:99-120`; terukur di instance hidup: `/api/docs` dan
   `/api/openapi.json` → 404).
7. **Backend hanya terjangkau lewat Caddy.** Postgres/backend/mock-sap tidak
   punya `ports:` (`infra/vps/docker-compose.vps.yml:24-25,50-52,102-103`).
   Jangan menambahkan `ports:` pada layanan itu "untuk debug" — itulah cara
   pembatas login per-IP dan isolasi DB hilang.

---

## 2. Model ancaman autopull (baca sebelum menyalakan `--pasang`)

`autopull.sh` dipanggil systemd tiap 3 menit (`autopull.sh:93-105`) dan:

1. `git fetch --depth 1 origin vps-deploy` (`:128`),
2. `git checkout -B vps-deploy FETCH_HEAD` (`:140`),
3. `docker compose build` + `up -d --no-deps` untuk layanan yang berubah
   (`:167-179`),
4. probe `GET /api/health` (dan `/` bila Caddy/frontend dibangun ulang)
   (`:181-211`).

Unit systemd-nya **tidak** menetapkan `User=`, jadi semuanya berjalan sebagai
root; build juga menjalankan `RUN` di `infra/vps/backend.Dockerfile` sebagai
root di dalam builder. Konsekuensinya:

> Kemampuan push ke `vps-deploy` **setara dengan akses root ke host**. Pelaku
> tidak perlu menyentuh aplikasi: satu commit yang mengubah
> `docker-compose.vps.yml` (tambahkan `privileged: true` + bind-mount `/`) atau
> `backend.Dockerfile` sudah cukup.

Karena repo-nya publik, vektor yang perlu dijaga hanyalah jalur **tulis**:

| Vektor | Status | Tindakan |
|---|---|---|
| Kredensial GitHub pemilik repo dicuri | tidak bisa dicegah dari VPS | branch protection + review wajib; 2FA; audit security log GitHub |
| Deploy key dengan izin tulis ada di VPS | **tidak ada** — klon memakai HTTPS publik tanpa token (`bootstrap-vps.sh:25,157`) | jangan pernah menaruh PAT/deploy key di VPS ini |
| Kolaborator jahat / tidak sengaja | tidak bisa dicegah dari VPS | `git verify-commit` + wajib tanda tangan untuk `vps-deploy` |
| MITM saat fetch | HTTPS + DNS; risiko rendah | biarkan HTTPS, jangan ganti ke `git://`/HTTP |

Mitigasi minimum yang murah (tidak butuh ubah arsitektur):

```bash
# 1. Matikan autopull bila tidak sedang dipakai (paling aman):
sudo rm -f /opt/mealchain/.autopull-enabled

# 2. Bila harus aktif, batasi jendela berlakunya:
sudo systemctl stop mealchain-autopull.timer     # sementara
sudo systemctl start mealchain-autopull.timer

# 3. Wajib di GitHub: Settings → Branches → protect `vps-deploy`
#    (Require PR + 1 review, Include administrators, Restrict force-push).
```

---

## 3. Temuan berurut risiko

### KRITIS

**K-1 — Push ke `vps-deploy` = eksekusi kode sebagai root, tanpa verifikasi.**
Bukti: `autopull.sh:24-31` (batas keamanan yang dinyatakan), `:80-92` (unit
systemd tanpa `User=`/`NoNewPrivileges`), `:140-179` (checkout → build → up dari
commit apa pun), `bootstrap-vps.sh:12` (`curl ... | sudo bash` dari cabang yang
sama), `docker-compose.vps.yml:57-62` (build dari konteks akar repo).
Dampak: akun/token GitHub yang bocor atau kolaborator yang lalai menjalankan
perintah apa pun di host (baca `.env`, ambil `POSTGRES_PASSWORD`, pasang
container privileged, ubah `infra/vps/Caddyfile.http` yang di-mount Caddy
`:190`).
Perbaikan: (a) branch protection wajib PR+review pada `vps-deploy`;
(b) commit bertanda tangan + gerbang `git verify-commit` sebelum checkout —
satu `if ! git verify-commit "$SESUDAH"; then catat ...; exit 0; fi` setelah
`:132`; (c) bila tidak dipakai, matikan autopull (§2).

### TINGGI

**T-1 — HTTP polos: sandi & JWT lewat jaringan terbuka.**
Bukti: `Caddyfile.http:1-16` (dokumen sendiri menyatakan konsekuensinya),
`docker-compose.vps.yml:176-181` (port 443 dipublish, tetapi firewall VPS
menutupnya), instance hidup menjawab `HTTP/1.1 200` di `:80` tanpa header HSTS.
Dampak: siapa pun di jaringan yang sama (Wi-Fi venue) bisa mencuri Bearer token
juri dan memakainya sampai 8 jam (`JWT_EXPIRE_MINUTES=480`,
`.env.vps.example:56`), atau membaca sandi saat login. Semua aksi demo jadi
milik penyerang.
Perbaikan: buka 443 lalu set `CADDY_CONFIG=Caddyfile` (TLS otomatis) — ini yang
seharusnya dipakai begitu firewall mengizinkan; atau Cloudflare Tunnel/frp
sebagai jalur TLS tanpa membuka port. Bila terpaksa HTTP: turunkan
`JWT_EXPIRE_MINUTES` ke 60-120, dan rotasi `JWT_SECRET` sesudah acara (semua
token lama gugur).

**T-2 — Autopull tidak menjalankan migrasi; `/health` tetap 200 saat skema
tertinggal.**
Bukti: `autopull.sh:167-211` hanya `build`/`up`/probe health — tidak ada
`alembic upgrade head`, padahal `deploy.sh:177-178` melakukannya (dan untuk
alasan yang sama). `health_check` hanya mengembalikan status statis
(`backend/app/main.py:298-320`) — tidak menyentuh tabel baru.
Dampak: commit yang menambah migrasi diterapkan, autopull mencatat `OK`, tetapi
endpoint yang menyentuh kolom baru menjawab 500 di tengah demo. Ini kegagalan
yang paling mungkin terjadi pada alur "push cepat sebelum presentasi".
Perbaikan: jalankan `alembic upgrade head` setelah `up` dan sebelum probe, dan
perlakukan gagal migrasi sebagai `gagal-migrasi` di `$STATUS`; atau tandai commit
yang menyentuh `backend/migrations/` sebagai "butuh deploy.sh manual". Sampai itu
ada, **jangan** push commit berisi migrasi lewat jalur autopull.

**T-3 — Tidak ada rollback otomatis; `:latest` tertimpa.**
Bukti: `autopull.sh:160-211`. Sebelum audit ini tidak ada image lama yang
disimpan: `docker compose build` menimpa `mealchain-vps-backend:latest`, jadi
commit yang lolos build tetapi crash-loop meninggalkan demo mati sampai ada
manusia yang bertindak.
Dampak: satu commit buruk = demo mati selama jeda antara push dan intervensi.
Perbaikan (sudah diterapkan sebagian): image yang sedang berjalan di-tag
`mealchain-vps-<layanan>:autopull-prev` sebelum build (`:160-165`), dan jalur
pemulihan dicatat ke log (`:207`). Rollback otomatis sengaja **tidak**
dilakukan: membalik image tanpa membalik skema bisa lebih buruk daripada
berhenti. Prosedur manual:

```bash
cd /opt/mealchain
docker tag mealchain-vps-backend:autopull-prev mealchain-vps-backend:latest
docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env \
  up -d --no-deps backend
```

**T-4 — Kredensial demo publik, termasuk satu akun ber-hak admin.**
Bukti: `backend/app/seed/demo_credentials.py:30-34`; repo publik (diverifikasi
lewat raw.githubusercontent, HTTP 200); `DEMO_MODE=true`
(`.env.vps.example:70`); `DEMO_SESSION_ENFORCE=false` (`.env.vps.example:84`)
mematikan gerbang sesi sehingga **setiap** mutasi diterima tanpa sesi aktif.
Dampak nyata (bukan teoretis): pengunjung mana pun dapat (a) login sebagai
`bgn_monitor` lalu `PATCH /admin/users/{id}` untuk mengubah peran/lokasi akun
demo, (b) membaca sandi ketiga peran lewat `GET /auth/demo-accounts`, (c) sebagai
`sppg_head` mengubah seluruh DB demo: menyetujui penerimaan, menerbitkan PO mock,
mengeksekusi keputusan, membersihkan deret waktu
(`POST /demo/timeseries/purge`, `backend/app/api/demo.py:1565-1571`). Tidak ada
data nyata yang tersentuh, tetapi **integritas demo di depan juri bisa dirusak
orang lain**, dan ledger berisi blok "kebenaran" yang ditulis penyerang.
Mitigasi minimum untuk demo juri (§4A): rotasi **hanya** sandi `bgn_monitor`
(juri tidak membutuhkannya), nyalakan `DEMO_SESSION_ENFORCE=true` sehingga
tulisan butuh sesi yang dibuka operator, dan jadwalkan `reset-demo.sh` tiap
30-60 menit. Jangan menghapus akun demo — itu yang dipakai juri.

### SEDANG

**S-1 — Build gagal = commit tertinggal, tidak ada percobaan ulang.**
Bukti: `autopull.sh:134-136` membandingkan `HEAD` dengan `FETCH_HEAD`, jadi
setelah build/up gagal (`:170-178`) HEAD sudah berada di commit yang gagal dan
putaran berikutnya tidak melakukan apa pun sampai ada commit baru. `$STATUS`
(`:171,176,190,195`) tidak dibaca kode mana pun (grep seluruh repo: tanpa
konsumen).
Dampak: kegagalan transien (OOM build di 2 GB RAM, jaringan putus) membuat
perbaikan tidak pernah terpasang, tanpa alarm; operator hanya melihat "tidak ada
yang berubah".
Perbaikan: periksa `$STATUS` di awal — bila `gagal-build <sha>` dan SHA itu
masih `FETCH_HEAD`, coba ulang paling banyak sekali per jam (tulis stempel
waktu), bukan tiap 3 menit; tampilkan `$STATUS` di panel Demo Control.

**S-2 — `.env` berada di dalam working tree yang di-checkout sebagai root.**
Bukti: `autopull.sh:46` (`ENV_FILE="$APP_DIR/infra/vps/.env"`),
`docker-compose.vps.yml:69-70` (`env_file: .env`), `bootstrap-vps.sh:164-188`.
Dampak: bila suatu commit (sengaja atau tidak) menambahkan `infra/vps/.env`, dua
kemungkinan buruk: (a) berkas untracked → `git checkout` gagal dan autopull
berhenti diam-diam (`:140-143`); (b) bila berkas itu pernah dilacak → checkout
**menimpa** `JWT_SECRET`/`POSTGRES_PASSWORD` server dengan nilai dari commit.
Perbaikan: pindahkan `.env` ke luar repo, mis. `/etc/mealchain/mealchain.env`
(chmod 600, root), dan rujuk jalur itu di `--env-file` serta `env_file:` compose.

**S-3 — Tidak ada gerbang path: perubahan compose/Caddy langsung diterapkan.**
Bukti: `autopull.sh:145-158` hanya memilih *layanan* yang dibangun; isi
perubahan tidak diperiksa.
Dampak: commit yang mengubah `infra/vps/docker-compose.vps.yml` (mis. menambah
`ports:` atau `privileged:`) diterapkan tanpa mata manusia.
Perbaikan: bila `git diff --name-only` memuat pola
`^infra/vps/(docker-compose|Caddyfile|backend\.Dockerfile|autopull\.sh)`,
tulis `perlu-review <sha>` ke `$STATUS` dan **berhenti** (jangan checkout/build);
perubahan itu diterapkan manual lewat `deploy.sh` setelah ditinjau.

**S-4 — Gerbang sesi demo dimatikan pada templat VPS.**
Bukti: `.env.vps.example:84` (`DEMO_SESSION_ENFORCE=false`), sementara default
kode `True` (`backend/app/core/config.py:38`). Akibatnya pagar di
`backend/app/main.py:182-219` (tolak 409 bila tidak ada sesi) tidak aktif, dan
`POST /demo/agent/run` (`backend/app/api/demo.py:1899-1902`) bahkan tidak
memakai `butuh_sesi_aktif`.
Dampak: tidak ada "jendela waktu" untuk membatasi kerusakan data demo — melekat
pada T-4. Untuk juri, sesi yang kedaluwarsa tidak boleh membuat demo buntu, jadi
pilihannya: nyalakan enforcement + tombol "Siapkan data demo" yang jelas, atau
biarkan mati dan andalkan reset berkala.

**S-5 — Endpoint agent tidak dibatasi laju; bisa memicu biaya pihak ketiga.**
Bukti: `backend/app/api/agent.py:90` (`POST /supervisor/ask`, hanya
`get_current_user`), `demo.py:1899` (`/demo/agent/run`, `sppg_head`); pembatas
laju hanya dipasang di login (`auth.py:306-313` → `core/rate_limit.py`).
Dampak: bila kredensial model diisi di `.env`, pengunjung dengan sandi publik
bisa memicu panggilan LLM berulang (biaya) atau minimal membebani 2 vCPU sampai
UI lambat saat presentasi.
Perbaikan: pada instance publik biarkan `WORKER_AGENT_MODE=off`,
`MULTI_AGENT_REVIEW=false`, dan jangan isi kunci model; kalau agen perlu hidup,
batasi rute `/api/supervisor/ask` di Caddy/firewall.

### RENDAH

**R-1 — Versi framework terekspos.** `X-Powered-By: Next.js` muncul di respons
UI (terukur 4 Nov 2026). Dampak: memudahkan pemetaan versi. Perbaikan: tambah
`-X-Powered-By` pada blok `header` `Caddyfile.http:62-67` (satu baris, aman).

**R-2 — Umur token panjang untuk instance HTTP.** `JWT_EXPIRE_MINUTES=480`
(`.env.vps.example:56`), dijepit maksimum 1440 menit di `auth.py:107-125`. Pada
instance ber-TLS 8 jam wajar; pada HTTP (T-1) token yang disadap berlaku
sepanjang hari. Perbaikan: 120 menit bila tetap HTTP.

**R-3 — `JWT_ALGORITHM` dari env tanpa allowlist.** `auth.py:103-104` dipakai
baik untuk `encode` (`:142`) maupun `decode` (`:164-168`). Karena decode memakai
daftar algoritme yang sama persis, ini **bukan** celah alg-confusion
(`none`/RS256 hanya akan membuat login gagal, bukan menerima token palsu).
Perbaikan opsional: tolak nilai selain `HS256`/`HS384`/`HS512` saat start agar
salah ketik tidak berujung 500 di tengah demo.

**R-4 — Pembatas login in-process, per (IP,email).** `core/rate_limit.py:33-58`
(dikunci `login:{ip}:{email}` di `auth.py:234-237`). Dampak: penyemprotan lintas
banyak email tidak dibatasi, dan penghitung hilang saat kontainer restart (satu
proses uvicorn, jadi tidak ada masalah multi-worker saat ini). Perbaikan: tidak
perlu untuk demo (sandi sudah publik); bila ingin rapat, pindah penghitung ke
Postgres atau pasang `fail2ban` pada log Caddy.

**R-5 — Token JWT disimpan di `localStorage`.** `frontend/app/page.tsx:288`.
Dampak: XSS apa pun = token dicuri. Risiko XSS rendah (React meng-escape, tidak
ada HTML dari pengguna; CSP UI memakai `'unsafe-inline'` karena kebutuhan
Next.js — terukur di header `/`). Perbaikan: tidak mendesak; cookie `HttpOnly` +
CSRF adalah perubahan besar, bukan untuk menjelang demo.

---

## 4. Sebelum instance ini dipakai di luar sesi juri

### A. Tetap mode demo (paling umum untuk lomba)

1. **Rotasi sandi `bgn_monitor` saja** (akun ini tidak dipakai juri, tetapi
   memegang `/admin/*`). `DEMO_PASSWORD_<ROLE>` hanya dipakai saat akun
   **dibuat** oleh seed; akun yang sudah ada tidak ikut berubah. Untuk instance
   hidup, ubah hash-nya langsung:

   ```bash
   COMPOSE="docker compose -f infra/vps/docker-compose.vps.yml --env-file infra/vps/.env"

   read -rsp "Sandi baru bgn.monitor@demo.local: " PW; echo
   HASH=$($COMPOSE exec -T backend python -c \
     "import bcrypt,sys;print(bcrypt.hashpw(sys.stdin.read().strip().encode(),bcrypt.gensalt()).decode())" <<<"$PW")
   $COMPOSE exec -T postgres psql -U mealchain -d mealchain -v ON_ERROR_STOP=1 \
     -c "UPDATE users SET password_hash = '$HASH' WHERE email = 'bgn.monitor@demo.local';"
   unset PW HASH
   ```

   Sandi `sppg.head@` / `sppg.nutritionist@` sengaja dibiarkan publik — itu yang
   dipakai juri. (Peran kota `*.bandung@`/`*.surabaya@` memakai sandi demo yang
   sama dengan peran induknya.)
2. **Nyalakan gerbang sesi** `DEMO_SESSION_ENFORCE=true` dan pastikan tombol
   "Siapkan data demo" terlihat; atau terima S-4 dan andalkan langkah 3.
3. **Reset berkala**: jadwalkan `infra/vps/reset-demo.sh` (60-90 detik) tiap
   30-60 menit selama acara, plus sekali tepat sebelum presentasi:

   ```ini
   # /etc/systemd/system/mealchain-reset.service  (Type=oneshot,
   # ExecStart=/bin/bash /opt/mealchain/infra/vps/reset-demo.sh)
   # /etc/systemd/system/mealchain-reset.timer    (OnCalendar=*:0/45)
   ```
4. **Matikan autofill sandi**: `DEMO_LOGIN_AUTOFILL=false` dan
   `DEMO_LOGIN_ALLOW_REMOTE=false` (bawaan; instance sekarang sudah
   `enabled:false`).
5. **Perketat laju login**: `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW` (bawaan
   kode 20/60; `.env.vps.example:93` menyetel 10/60). Caddy di stack ini
   **tidak** punya modul rate-limit (image resmi tanpa plugin), jadi pembatas
   aplikasi + firewall adalah garis pertahanannya. Bila butuh pembatas di tepi,
   buat image Caddy kustom dengan `caddy-ratelimit` atau pasang `fail2ban` yang
   membaca log JSON Caddy (`docker compose logs caddy`).
6. **Batasi ukuran body** (sudah aktif): 10 MB API, 2 MB UI
   (`Caddyfile.http:34-38,55-58`, `MAX_BODY_*`).
7. **Matikan autopull di luar jam perubahan** (§2), dan pastikan branch
   protection menyala sebelum acara.

### B. Instance dengan data nyata

1. `DEMO_MODE=false`, `DEMO_LOGIN_AUTOFILL=false`,
   `DEMO_LOGIN_ALLOW_REMOTE=false`, `DEMO_SESSION_ENFORCE=true`,
   `ENABLE_DOCS=false`, `DEBUG=false`.
2. Jangan jalankan seed demo (`deploy.sh` menjalankan `app.seed.demo_template`
   dan menanam akun demo). Pakai `python -m app.seed.db_mode init-default` untuk
   skema + referensi saja, lalu buat akun lewat jalur admin.
3. Ganti/hapus akun demo (`sppg.head@demo.local` dkk) — seed referensi menanam
   mereka beserta sandi demo.
4. Wajib TLS (`Caddyfile` + port 443) — jangan pernah jalankan data nyata di
   HTTP.
5. Isi `SIGNING_KEY_HEX` bila dossier harus bertanda tangan; kosong = status
   `unsigned` yang jujur, bukan tanda tangan palsu.
6. Pasang backup otomatis (`pg_dump` harian) dan uji restore.

---

## 5. Yang sudah aman (jangan "diperbaiki" tanpa alasan)

Diperiksa 4 November 2026 — ini yang **tidak** perlu disentuh:

- **Tidak ada eskalasi peran lewat klaim JWT.** `_issue_token` menulis klaim
  `role` (`auth.py:128-142`) tetapi `get_current_user` **mengabaikan** klaim itu
  dan memuat pengguna dari DB (`auth.py:156-184`). Klaim hanya dipakai UI untuk
  menampilkan menu (`frontend/lib/auth.ts:3-21`). Mengubah payload token tidak
  menaikkan peran; token yang ditandatangani pihak lain ditolak (401).
- **Tidak ada jalur `mock:<peran>` di backend.** Grep seluruh `backend/` +
  `agent/`: tidak ada. `mock:<peran>` hanya hidup di build statis frontend
  (`frontend/lib/auth.ts:6-9`, `frontend/lib/mock-api.ts:75-77`), dan image
  produksi dibangun dengan `NEXT_PUBLIC_USE_MOCK=false`
  (`docker-compose.vps.yml:138,150`) sehingga cabang itu tidak pernah aktif.
- **Semua rute butuh auth kecuali satu.** Pemeriksaan terprogram atas seluruh
  `@router.get/post/put/patch/delete` di `backend/app/api/*.py`: hanya
  `GET /auth/demo-login` tanpa `Depends(...)`, dan itu dijaga tiga kunci
  (`DEMO_MODE` + `DEMO_LOGIN_AUTOFILL` + pemanggil lokal,
  `auth.py:56-84,240-268`).
- **`/admin` tidak bisa dipakai token layanan.** Endpoint admin menuntut klaim
  `typ="user"` (`admin.py:31-37`, `auth.py:198-214`), sehingga token agen (akun
  `bgn_monitor`) tidak bisa mengelola pengguna; dan `bgn_monitor` tidak boleh
  mengubah perannya sendiri (`admin.py:109-113`).
- **Otorisasi tulis per-cakupan sudah ditegakkan** pada jalur berisiko:
  keputusan (`decisions.py:73-95,192`), seluruh siklus aksi
  (`actions.py:90-104`, dipakai di `:507,565,686,1021,1255,1398,1558`),
  penerimaan barang (`receipts.py:274,426,594`), karantina
  (`services/quarantine_service.py:39-46`), event (`events.py:54,117`), limbah
  (`waste.py:150-165`), eksklusi pemasok
  (`services/supplier_exclusion_service.py:102`). IDOR yang dicari — endpoint
  tulis menerima id tanpa cek kepemilikan/cakupan — **tidak ditemukan**.
- **PDF PO publik bertanda tangan.** `GET /public/purchase-orders/{po}/pdf`
  tanpa token login, tetapi menuntut JWT `typ=po_pdf` berumur 15 menit yang
  mengikat nomor PO dan ditandatangani `JWT_SECRET`
  (`services/po_document.py:210-251`); tanpa `JWT_SECRET` ia menolak bekerja
  (`:214-220`).
- **CORS allow-list, bukan wildcard** (`main.py:65-97`); mode satu-port memakai
  origin sama sehingga CORS praktis tidak terlibat.
- **Dokumentasi API tertutup** dan menjawab 404, bukan 403 (`main.py:99-120`;
  diverifikasi hidup).
- **Header keamanan** dari backend (`main.py:127-147`: nosniff, DENY,
  Referrer-Policy, Permissions-Policy, COOP, CSP ketat, HSTS hanya di HTTPS) dan
  dari Caddy (`Caddyfile.http:62-67`) — terverifikasi pada respons hidup.
- **Batas ukuran body** 10 MB API / 2 MB UI di tepi (`Caddyfile.http:34-38`).
- **DB/backend/mock-sap tidak punya port host** (`docker-compose.vps.yml:24-25,
  50-52,102-103`); `data/` di-mount read-only ke backend (`:98-101`), dan kode
  tidak di-mount sehingga image yang berjalan = image yang dibangun.
- **Rahasia dibuat di server, bukan di repo:** `bootstrap-vps.sh:169-188`
  membuat `POSTGRES_PASSWORD` (24 byte hex) dan `JWT_SECRET` (32 byte hex) acak,
  `chmod 600`; compose menolak start bila kosong (`:38-40,78`) dan `deploy.sh`
  menolak placeholder serta `JWT_SECRET` < 32 karakter (`:119-123`).
- **Tidak ada kredensial di remote git** (klon HTTPS publik), jadi log fetch
  tidak bisa membocorkan token; `.gitignore:52` menutup `.env`.
- **Login:** bcrypt + hash dummy untuk email tak dikenal (timing), pembatas laju
  per IP+email (`auth.py:298-332`, `core/rate_limit.py`).
- **Autopull punya pagar dasar:** penanda `.autopull-enabled`, kunci `flock`
  (satu build sekaligus), cabang dipatok, hanya layanan yang berubah dibangun,
  probe health sungguhan, dan (sejak audit ini) batas waktu per tahap, log
  0600, tag `autopull-prev`, serta fallback diff yang tidak lagi melewatkan
  build.

---

## 6. Autopull: apa yang diubah audit ini

`infra/vps/autopull.sh` (perubahan kecil, alur tetap):

| Perubahan | Alasan |
|---|---|
| `umask 077` + `chmod 600` log | log memuat perintah build, URL remote, nama variabel; dulu 0644 (dibaca semua user host) |
| `terbatas <detik>` untuk fetch/build/up + `TimeoutStartSec=2400` | proses menggantung dulu memegang `flock` selamanya → semua autopull berikutnya `exit 0` tanpa pesan |
| fallback diff membangun **semua** layanan | dulu fallback `"semua"` tidak cocok dengan grep berjangkar `^` → commit dicatat "baru" tanpa satu pun build |
| tag `<image>:autopull-prev` sebelum build + perintah rollback di log | sebelumnya tidak ada image lama untuk dibalikkan |
| probe `/` bila caddy/frontend dibangun | caddy rusak dulu dilaporkan `OK` karena hanya backend yang diuji |

Yang **belum** diperbaiki dan tetap pekerjaan manusia: verifikasi tanda tangan
commit (K-1), migrasi otomatis (T-2), gerbang path (S-3), retry build gagal
(S-1), relokasi `.env` (S-2).

---

## 7. Yang TIDAK BOLEH pernah di-commit / ditaruh di VPS demo

| Jangan | Kenapa |
|---|---|
| **Kunci AWS asli** (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) | Bisa menagih akun Anda; VPS demo semi-publik. Pakai IAM role / Instance Profile dengan izin minimum. |
| `SAP_AI_CORE_CLIENT_SECRET`, `SAP_MCP_TOKEN` asli | Kredensial tenant SAP; memuat karakter `$` dan mudah rusak bila disalin ke compose. |
| `INFERHUB_API_KEY`, kunci model LLM | Tagihan pihak ketiga — dan endpoint agent publik (S-5) bisa memakainya. |
| `JWT_SECRET` nilai nyata | Siapa pun yang memegangnya bisa membuat token sah untuk peran mana pun **dan** tautan PDF PO. |
| `SIGNING_KEY_HEX` nyata | Kunci tanda tangan dossier. |
| `infra/vps/.env`, `.env.local`, `*.env.bak*` | Berisi semua di atas. `.gitignore` sudah menutup `.env`, tetapi **periksa `git status` sebelum commit**. |
| Dump database (`*.dump`, `*.sql`) ke repo | Memuat data pengguna dan hash sandi. |
| Sertifikat/privat key TLS (`*.key`, `*.crt` pihak ketiga) | Sertifikat Let's Encrypt di stack ini dikelola volume Docker `caddy_data`, bukan berkas repo. |
| **Token/deploy key GitHub dengan izin tulis** | Autopull berjalan sebagai root; kredensial tulis di VPS = kunci kerajaan (K-1). |

Yang **harus** ada di repo dan boleh publik: `.env.vps.example` (placeholder
saja), `docker-compose.vps.yml`, `Caddyfile*`, skrip, dan dokumen ini.

---

## 8. Bila terjadi kebocoran

1. `JWT_SECRET` bocor → rotasi (README §4.3). Semua sesi lama **dan seluruh
   tautan PDF PO** otomatis gugur.
2. `POSTGRES_PASSWORD` bocor → ganti di `.env`, lalu
   `docker compose exec postgres psql -c "ALTER USER mealchain PASSWORD '...'"`,
   `docker compose up -d --force-recreate backend mock-sap`.
3. Akun GitHub pemilik repo dicuri → cabut token/deploy key di GitHub, aktifkan
   2FA, periksa commit tak dikenal di `vps-deploy`, **matikan autopull**
   (`sudo rm -f /opt/mealchain/.autopull-enabled`), lalu audit host (proses,
   kontainer, `authorized_keys`, cron) — push setara root.
4. Data demo dikotori pengunjung → `bash infra/vps/reset-demo.sh`; bila
   `bgn_monitor` disalahgunakan, periksa blok `admin.user.update` di ledger dan
   rotasi sandi akun itu.
5. Kunci AWS/SAP bocor → **revoke di konsol cloud**, bukan sekadar mengganti
   berkas. Periksa CloudTrail pemakaian tak dikenal.
