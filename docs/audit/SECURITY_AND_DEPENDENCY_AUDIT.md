# SECURITY & DEPENDENCY AUDIT — MealChain Guardian

Diukur 26 Oktober 2026, 21:37–21:50 WIB pada repo `E:\hackathon\HackathonAWS\mealchain-guardian`
(git `5885810`, branch `feature/db-modes-demo-coverage`) dengan stack Compose hidup
(backend :8000, frontend :3010, postgres :15432).

Dokumen ini hanya memuat temuan dan bukti. **Tidak ada sandi, token, kunci, atau isi `.env` yang
ditulis di sini** — bila sebuah temuan menyangkut rahasia, yang dicatat adalah lokasi dan sifat
kebocorannya, bukan nilainya.

## 1. Ringkasan

| Area | Hasil | Status |
|---|---|---|
| `npm audit` (frontend) | **15 kerentanan**: 4 critical, 5 high, 6 moderate, 0 low — 628 dependensi (101 prod, 519 dev) | OPEN |
| Kebocoran kredensial di bundel | Sandi demo **tidak** ada di sumber; **ada** di artefak build lama (`.next`, `.next-build`, `.next-dev2`) | OPEN (Medium) |
| Kebocoran kredensial di sumber (`app/`, `components/`, `lib/`) | 0 kecocokan literal sandi | PASS |
| AuthN (401 tanpa/ token palsu) | Terverifikasi langsung | PASS |
| AuthZ (scope lokasi, role) | Terverifikasi langsung (403) | PASS |
| CORS | Allow-list eksplisit, tanpa wildcard | PASS |
| Header keamanan backend | Terverifikasi pada 3 endpoint | PASS |
| Dokumentasi API (`/docs`, `/openapi.json`) | 404 (tertutup) | PASS |
| Sesi demo (guard mutasi) | Kode + status sesi terverifikasi; **tidak** diekskusi sebagai POST (DB demo) | PARTIAL |
| Dependensi backend (`pip-audit`, `bandit`) | Alat tidak terpasang di image | **NOT TESTED** |
| Rate limit login | Kode ada (`app/core/rate_limit.py`), perilaku tidak diuji | **NOT TESTED** |

## 2. `npm audit` — hasil mentah dan rincian

Perintah (read-only, tanpa `npm install`, tanpa menyentuh lockfile):

```
cd frontend && npm audit --json
```

- Exit code **1** (artinya ada kerentanan, bukan alat gagal).
- `metadata.vulnerabilities`: `{critical: 4, high: 5, moderate: 6, low: 0, info: 0, total: 15}`
- `metadata.dependencies`: `{prod: 101, dev: 519, optional: 87, total: 628}`

| Paket | Severity | Direct | Lingkungan | Rentang terdampak | Perbaikan yang ditawarkan |
|---|---|---|---|---|---|
| `maplibre-gl` **4.7.1** | critical | ya | **produksi** | `<=6.4.0` | `maplibre-gl@6.16.0` (major) |
| `next` **14.2.14** | critical | ya | **produksi** | `>=14.0.0 <14.2.21` | `next@16.4.3` (major) |
| `vitest` 2.1.9 | critical | ya | dev | `<=4.1.10` | `vitest@4.1.12` (major) |
| `tinypool` 1.1.1 | critical | tidak | dev | `<=2.1.1` | `vitest@4.1.12` (major) |
| `postcss` 8.4.47 | high | ya | dev | `<=8.5.22` | `next@16.4.3` (major) |
| `eslint-config-next` 14.2.14 | high | ya | dev | `14.0.5-canary.0 – 15.0.0-rc.1` | `eslint-config-next@16.4.3` (major) |
| `@next/eslint-plugin-next` 14.2.14 | high | tidak | dev | idem | `eslint-config-next@16.4.3` (major) |
| `glob` 10.3.10 | high | tidak | dev | `10.2.0 – 10.4.5` | `eslint-config-next@16.4.3` (major) |
| `vite` 5.4.21 | high | tidak | dev | `<=6.4.3` | `vitest@4.1.12` (major) |
| `tailwindcss` 3.4.13 | moderate | ya | dev | `0.5.0 – 3.4.19` | `tailwindcss@4.3.3` (major) |
| `postcss-selector-parser` 6.1.5 | moderate | tidak | dev | `<7.1.6` | `tailwindcss@4.3.3` (major) |
| `postcss-nested` 6.2.0 | moderate | tidak | dev | `2.0.3 – 6.2.0` | tersedia (non-breaking) |
| `@vitest/mocker` 2.1.9 | moderate | tidak | dev | `<=4.1.11` | `vitest@4.1.12` (major) |
| `esbuild` 0.21.5 | moderate | tidak | dev | `<=0.24.2` | `vitest@4.1.12` (major) |
| `vite-node` 2.x | moderate | tidak | dev | `<=2.2.0-beta.2` | `vitest@4.1.12` (major) |

Catatan penting: **dua kerentanan menyentuh dependensi produksi** — `maplibre-gl` (XSS sanitizer
bypass saat merender style/ekspresi peta, CVSS 10, GHSA-jrc7-96c5-q579) dan `next` (DoS lewat Server
Actions, GHSA-7m27-7ghc-44w9). Sisanya rantai alat pengembangan (vitest/vite/tailwind/eslint) dan
tidak ikut ke bundel browser. Semua "fix" yang ditawarkan npmadalah **lonjakan major** yang dilarang
oleh aturan kerja sesi ini (tanpa upgrade dependensi), jadi dicatat sebagai risiko yang diterima,
bukan dijalankan.

## 3. Kebocoran kredensial

### 3.1 Sumber aplikasi — bersih

```
grep -rn "<pola-sandi-demo>\|password" frontend/app frontend/components frontend/lib
```

(Pola sandi demo disamarkan di dokumen ini; perintah yang dijalankan memakai pola literalnya.)

Hasil: 9 kecocokan, **semuanya bukan rahasia** — nama state React (`const [password, setPassword]`),
`type="password"`, `autoComplete="current-password"`, label validasi, dan parameter `login(email,
password)` di `frontend/lib/api.ts:83`. Pemeriksaan pola literal sandi demo (tiga varian, **tidak
dikutip di sini**) pada `app/`, `components/`, `lib/` → **0 kecocokan**.
Daftar akun cepat di `frontend/app/page.tsx:762` hanya memuat **email**, bukan sandi; sandi demo
sekarang berasal dari server (`app.seed.demo_credentials.resolve_demo_password`).

### 3.2 Artefak build — sandi demo tercetak apa adanya

Sisa build lama di working tree masih memuat literal sandi demo (7 kecocokan di satu chunk). Bukti
lokasi (nilai **tidak** dikutip):

| Artefak | Berkas mengandung literal sandi | Jumlah |
|---|---|---|
| `frontend/.next/static/chunks/app/page-*.js` (mtime 2026-10-23 23:03) | chunk + `server/app/page.js` + `standalone/.../page.js` | 3 berkas |
| `frontend/.next-build/` | `server/app/page.js`, `static/chunks/app/page-*.js`, `standalone/...`, 2 pack cache webpack | 5 berkas |
| `frontend/.next-dev2/` | `server/app/page.js`, `static/chunks/app/page.js` | 2 berkas |

Uji paparan langsung (apakah bisa diunduh dari jaringan):

```
curl -s -o live.js -w '%{http_code}' http://localhost:3010/_next/static/chunks/app/page.js   → 200 (7.9 MB), 0 kecocokan pola sandi
curl -s -o old.js  -w '%{http_code}' http://localhost:3010/_next/static/chunks/app/page-df2842c31d1c9675.js → 404
```

Artinya: **chunk yang sedang dilayani dev server bersih** (sumber sudah diperbaiki), sedangkan chunk
lama berisi sandi hanya ada di disk dan **tidak** terjangkau HTTP dengan nama itu. Risiko nyata ada di
jalur deploy: siapa pun yang menerbitkan isi `.next-build/` (atau `standalone/`) apa adanya akan
mengirim sandi demo ke browser.

### 3.3 Hal lain yang ada di bundel (bukan rahasia, tetapi perlu disadari)

Email akun demo (`sppg.head@demo.local` dan kawan-kawan) ikut ke bundel karena dipakai tombol login
cepat. Itu identitas, bukan kredensial; tetap berarti daftar akun demo dapat dipanen dari bundel
publik. `NEXT_PUBLIC_*` hanya memuat URL API (`NEXT_PUBLIC_API_URL`), tidak ada rahasia.

## 4. Autentikasi, otorisasi, dan sesi (diukur langsung)

Probe read-only dijalankan dari dalam kontainer backend (login memakai kredensial demo tanpa pernah
mencetaknya ke keluaran):

| Uji | Permintaan | Hasil |
|---|---|---|
| Tanpa token | `GET /decisions` | **401** `butuh Bearer token` |
| Token tidak sah | `GET /decisions` + Bearer acak | **401** `token tidak valid` |
| Scope lokasi | `sppg_head` Jakarta → `GET /decisions/{id Bandung}` | **403** `keputusan di cakupan lokasi di luar SPPG Anda` |
| Peran nasional | `bgn_monitor` → `GET /decisions/{id Bandung}` | **200** |
| Peran salah | `sppg_head` → `GET /admin/users` | **403** `role tidak diizinkan` |
| Peran admin | `bgn_monitor` → `GET /admin/users` | **200** |
| Sesi demo | `GET /demo/session` | `{active: false, enforced: true, remaining_seconds: 0}` |
| Dokumentasi API | `GET /docs`, `GET /openapi.json` | **404** (sengaja, `app/main.py:97-116`) |

Detail mekanisme yang dibaca dari kode:

- JWT HS256, `JWT_SECRET` wajib ada — bila kosong endpoint balas **503** (`app/api/auth.py:38-45`),
  kedaluwarsa bawaan 30 menit (`JWT_EXPIRE_MINUTES`, `app/api/auth.py:63`).
- Sandi disimpan sebagai bcrypt; email tak dikenal tetap menjalankan `bcrypt.checkpw` terhadap hash
  dummy agar waktu respons tidak membocorkan keberadaan akun (`app/api/auth.py:29,164`).
- Guard mutasi sesi demo: `butuh_sesi_aktif` (`app/api/demo_session.py:35-48`) membalas **409** bila
  `DEMO_SESSION_ENFORCE=true` dan tidak ada sesi aktif. Saat audit, flag menyala dan sesi **tidak**
  aktif, jadi seluruh endpoint mutasi tertutup. Pengujian dihentikan pada tingkat kode + status sesi:
  mengirim POST untuk membuktikannya akan berisiko menulis ke DB demo bila sesi ternyata aktif.

## 5. CORS, header, dan permukaan HTTP

`app/main.py:63-95`:

- `allow_origins` = allow-list eksplisit (`http://localhost:3000`, `127.0.0.1:3000`,
  `localhost:3010`, `127.0.0.1:3010`) ditambah `CORS_ORIGINS` dari env; **tidak ada `*`**.
- `allow_credentials=True`, `allow_methods=["GET","POST","PATCH","OPTIONS"]`,
  `allow_headers=["Authorization","Content-Type"]`.
- Mode produksi memakai proxy Next (`next.config.js` → `BACKEND_INTERNAL_URL`), sehingga browser
  memakai origin sendiri dan CORS tidak terlibat; allow-list tetap diperlukan untuk mode URL absolut.

Header keamanan diverifikasi dengan respons nyata (bukan hanya membaca kode) pada
`/decisions`, `/kpi`, dan `/health`:

| Header | Nilai terukur |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'; base-uri 'none';` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Cross-Origin-Opener-Policy` | `same-origin` |

Catatan: percobaan pertama membaca header lewat `dict(response.headers)` memberi `None` untuk ketiga
endpoint; pembacaan ulang langsung (`response.headers.get(...)`) menunjukkan header **ada**. Yang
dilaporkan adalah hasil pembacaan ulang — bukan `None` yang keliru.

## 6. Kebersihan repo dan rahasia di disk

| Berkas | Status git | Keterangan |
|---|---|---|
| `mealchain-guardian.tailda91db.ts.net.key` (kunci privat TLS, ada di root repo) | **tidak terlacak** — diabaikan `.gitignore:95` (`*.key`) | Materi kunci privat berada di working tree; aman dari commit, tetapi sebaiknya dipindah ke luar repo |
| `secrets/aws-app.env` | tidak terlacak — `.gitignore:84` (`secrets/`) | OK |
| `.env` | diabaikan (`.gitignore:52`), `.env.example` wajib ter-commit | OK |
| `git ls-files` untuk `*.key/*.pem/*.crt/secret/.env` | hanya `.hermes/secret_scan.sh` (skrip, bukan rahasia) | OK |

## 7. Dependensi backend

`backend/requirements.txt` (23 baris, 19 paket terpin):
`fastapi==0.115.0`, `uvicorn[standard]==0.30.6`, `sqlalchemy==2.0.35`, `asyncpg==0.29.0`,
`psycopg[binary]==3.2.3`, `alembic==1.13.2`, `pydantic==2.9.2`, `pydantic-settings==2.5.2`,
`python-dotenv==1.0.1`, `bcrypt==4.2.0`, `pyjwt==2.9.0`, `httpx==0.27.2`, `boto3==1.42.89`,
`pytest==8.3.3`, `pytest-asyncio==0.24.0`, `ruff==0.6.9`, `ecdsa>=0.19`, `reportlab==5.0.1`,
`pypdf==6.21.1`.

| Alat | Status | Bukti |
|---|---|---|
| `pip-audit` | **NOT TESTED** | `python -m pip_audit --version` → `No module named pip_audit` |
| `bandit` | **NOT TESTED** | `bandit --version` → `not found` |
| `safety` | **NOT TESTED** | tidak ada di `pip list` |

Karena itu dokumen ini **tidak** mengklaim backend bebas CVE. Yang bisa dikatakan hanya: dependensi
terpin rapi, dan tidak ada satu pun alat audit dependensi Python yang tersedia di image saat audit.

## 8. Temuan (AUDIT-ID)

| ID | Severity | Status | Temuan | Rekomendasi |
|---|---|---|---|---|
| SEC-01 | **High** | Open | `maplibre-gl@4.7.1` (dependensi produksi langsung) terkena XSS sanitizer bypass `GHSA-jrc7-96c5-q579` (CVSS 10). Peta merender data dari API; ekspresi/style yang tidak tepercaya dapat mengeksekusi skrip di origin aplikasi. | Naikkan ke `maplibre-gl>=6.16.0` pada jendela upgrade terencana (major; butuh uji regresi peta) |
| SEC-02 | **High** | Open | `next@14.2.14` terkena DoS Server Actions `GHSA-7m27-7ghc-44w9` (rentang `<14.2.21`) dan menjadi jalur masuk advisory `postcss` (`<8.5.10`). | Patch `14.2.21` bila tersedia dalam mayor yang sama; jika tidak, jadwalkan upgrade major |
| SEC-03 | **Medium** | Open | Tiga direktori build lama (`.next`, `.next-build`, `.next-dev2`) memuat **literal sandi demo** di chunk JS; sumber sudah bersih tetapi artefak belum dibersihkan/dibangun ulang. Chunk itu tidak dilayani dev server (404) sehingga belum bocor lewat HTTP, tetapi akan bocor bila direktori tersebut diterbitkan. | Hapus artefak build lama dari working tree, bangun ulang sebelum deploy, dan rotasi sandi demo karena nilainya pernah tertulis di artefak |
| SEC-04 | Medium | Open | Enam advisory rantai alat pengembangan (vitest, vite, tinypool, esbuild, glob, postcss-nested/selector-parser) — tidak masuk bundel produksi, tetapi berefek pada mesin developer/CI (path traversal, prototype pollution → RCE pada worker vitest). | Upgrade toolchain dev saat jendela upgrade dibuka; jangan menjalankan suite pada input tak tepercaya |
| SEC-05 | Low | Accepted | `bgn_monitor` dapat menulis `PATCH /admin/users/{id}` dan `/admin/locations/{id}` (`app/api/admin.py:80-99,155-170`). Konsisten dengan desain "monitor = admin", tetapi bertentangan dengan kalimat "bgn_monitor read-only" di docstring `app/api/auth.py:4`. | Perjelas istilah di dokumentasi; pertimbangkan peran admin terpisah bila monitor tidak boleh mengubah data |
| SEC-06 | Low | Accepted | Kunci privat TLS ada di root working tree (git-ignored, tidak terlacak). | Pindahkan ke `secrets/` atau luar repo |
| SEC-07 | Low | Open | Tidak ada audit dependensi Python (pip-audit/bandit) di image maupun CI. | Tambahkan `pip-audit` sebagai langkah CI (bukan install di runtime demo) |
| SEC-08 | Info | Pass | Tidak ada kredensial literal di sumber; login memakai bcrypt + dummy hash; `JWT_SECRET` wajib; `/docs` tertutup; CORS allow-list; header keamanan lengkap; scope lokasi dan role ditegakkan backend (401/403 terukur). | — |
| SEC-09 | Info | **NOT TESTED** | Perilaku rate limit login, DAST, dan pengujian POST terhadap guard sesi demo tidak dijalankan (menghindari tulis ke DB demo). | Uji di stack terisolasi (compose project sendiri) |

## 9. Keterbatasan

1. `npm audit` memakai metadata registry saat audit (26 Okt 2026) — angka dapat berubah tanpa
   perubahan kode.
2. Uji otorisasi hanya menyentuh tiga endpoint contoh (keputusan, admin, sesi); bukan matriks penuh
   seluruh 20+ router.
3. Tidak ada pengujian injeksi (SQLi/XSS aktif), CSRF, atau pemindaian port; semua klaim di atas hanya
   menyangkut apa yang benar-benar dijalankan.
