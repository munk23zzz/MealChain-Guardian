# AUDIT_08 — Security, Performance, Accessibility

## 8.1 Security

### 8.1.1 Autentikasi & otorisasi (terukur)

| Uji | Hasil | Bukti |
|---|---|---|
| Tanpa token → 401 | `/decisions`, `/batches`, `/ledger/verify` → 401 (3/3) | invariants.spec |
| Peran salah → 403 | `sppg_head` ke `/admin/users`, `/admin/locations` → 403 | roles.spec |
| Monitor read-only → 403 pada mutasi demo | `bgn_monitor` ke `/demo/data-status` → 403 | stack.spec |
| Scope lokasi | kepala Jakarta → `/balance/Bandung` 403; kepala Bandung → `/balance/Jakarta` 403 | roles.spec |
| Empat mata | akun sama dua kali → 409; satu approval belum final | probe API |
| Sesi demo | mutasi tanpa sesi → 409 | probe API |
| Rate limit login | `app/core/rate_limit.py` dipakai `auth.py` (`sisa_tunggu`, `catat_gagal`, `lupakan`) | statis — perilaku tidak diuji dengan percobaan berulang |

Authorization ditegakkan di backend (bukan hanya UI): semua endpoint mutasi memakai `require_roles`/scope, dan gate membuktikan 403 nyata.

### 8.1.2 Header & CORS (terukur `curl -D -`)

| Header | Nilai/observasi | Status |
|---|---|---|
| `x-content-type-options` | `nosniff` | PASS |
| `x-frame-options` | `DENY` | PASS |
| `referrer-policy` | `no-referrer` | PASS |
| `permissions-policy` | `geolocation=(), microphone=(), camera=()` | PASS |
| `cross-origin-opener-policy` | `same-origin` | PASS |
| `content-security-policy` (API) | `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'` | PASS |
| CORS preflight dari origin asing | **400**, tidak ada `access-control-allow-origin` untuk origin itu | PASS |

### 8.1.3 Manajemen rahasia

| Temuan | Detail | Prioritas |
|---|---|---|
| SEC-01 | `.env` berisi 43 kunci (kredensial DB, `JWT_SECRET`, kunci AWS/SAP, `SIGNING_KEY_HEX`). File **tidak dilacak** saat ini, tetapi pernah masuk riwayat git (commit `8f95c98`). Rotasi kredensial masih wajib sebelum repo/instance dibuka publik. Nilai tidak dicetak di laporan ini. | P1 |
| SEC-02 | **Kredensial 7 akun demo hardcoded di bundel klien** (`frontend/app/page.tsx:759-777`): email + password untuk SPPG Head, Nutritionist, BGN Monitor, Bandung, Surabaya. Siapa pun yang membuka instance demo bisa masuk sebagai approver. Nilai tidak dicantumkan di laporan. | P2 (demo) / P1 bila instance memuat data nyata |
| SEC-03 | Tidak ada pemisahan env demo vs produksi pada kredensial: `.env` yang sama dipakai compose lokal dan `docker-compose.prod.yml` | P2 |

Rekomendasi konkret (tidak dieksekusi karena menyentuh desain login/UX demo): pindahkan kredensial quick-login ke endpoint server yang mengembalikan **token** untuk sesi demo yang aktif saja, atau aktifkan hanya saat `DEMO_MODE=true` dan sesi demo berjalan.

### 8.1.4 Dependensi frontend (`npm audit --omit=dev`)

| Paket | Terpasang | Severity | Inti | Perbaikan |
|---|---|---|---|---|
| `next` | 14.2.14 | **critical** | banyak advisory (auth bypass middleware, RCE image optimizer, DoS server actions) | 16.4.3 — **breaking** (14→16) |
| `maplibre-gl` | 4.7.1 | **critical** | XSS sanitizer bypass di `DOM.sanitize()` (GHSA-jrc7-96c5-q579) | 6.16.0 — **breaking** (4→6) |
| `postcss` | 8.4.47 (via next) | high | path traversal / `.map` disclosure di sourceMappingURL | ikut versi next |

Ringkasan: 3 kerentanan (1 high, 2 critical). Semua perbaikannya memerlukan upgrade mayor — tidak dikerjakan di audit ini karena (a) memicu perubahan besar yang harus diuji ulang penuh, (b) menyentuh peta (komponen inti demo), dan (c) keputusan risiko ada di owner. Mitigasi yang berlaku sekarang: instance demo tidak diekspos publik, CSP API ketat, dan tidak ada konten HTML tak tepercaya yang dikirim ke peta.

### 8.1.5 Dependensi backend

`pip-audit`/`bandit` tidak tersedia (AUDIT_07 §7.3) → **BLOCKED**. Tidak ada klaim aman untuk dependensi Python.

### 8.1.6 Injeksi & XSS

- Query memakai SQLAlchemy `text()` dengan parameter terikat (contoh `:loc`, `:start`, `:end`); tidak ditemukan konkatenasi input pengguna pada sampel yang diperiksa (`kpi_service.py`, `balance.py`, `decisions.py`).
- Input ID divalidasi sebagai UUID oleh FastAPI → 422 untuk `bukan-uuid` (terukur).
- Frontend merender teks dari API sebagai teks React (tidak ada `dangerouslySetInnerHTML` pada berkas yang diperiksa) — pencarian menyeluruh tidak dijalankan (BLOCKED tanpa semgrep).

## 8.2 Performance

Baseline latency dari gate (satu request, stack hangat, tanpa beban lain):

| Endpoint | Latency terukur |
|---|---|
| `/health` | 4 ms |
| `/decisions` (Jakarta, 11 kartu) | 27 ms |
| `/balance/map` | 40 ms |
| `/kpi?periode=today` | 121–123 ms |
| `/auth/login` (bcrypt) | 275–303 ms |
| `/demo/data-status` | 165 ms |
| `/supplier-routes` | tidak diukur terpisah; termasuk dalam UI tab PASS |

Catatan:
- `/kpi` ±120 ms untuk 7 metrik adalah endpoint terberat yang diukur; belum ada target SLA resmi di repo, jadi angka ini baseline, bukan lulus/gagal.
- Tidak ada uji beban (k6/locust tidak tersedia) → **BLOCKED** untuk throughput/konkurensi.
- Kandidat optimasi yang terlihat dari kode (belum diukur dampaknya): `compute_kpis` menjalankan beberapa query terpisah per metrik; `price_signals` 5.924 baris dan `supply_records` 5.240 baris sudah terindeks pada kolom FK (migrasi 033).

## 8.3 Accessibility

| Pemeriksaan | Hasil | Status |
|---|---|---|
| `axe-core` otomatis | tidak tersedia | **BLOCKED** |
| Atribut ARIA pada navigasi | tab aktif memakai `aria-current="page"` (diuji matriks tab) | PASS |
| Status & galat | `role="alert"` pada pesan login/galat peta, `role="status" aria-atomic="true"` pada status feed | PASS (statis) |
| Grup kontrol | `role="group"` + `aria-label` pada filter status | PASS (statis) |
| Navigasi keyboard & fokus modal | belum diuji terprogram | **NOT TESTED** |
| Kontras warna | tidak diukur (butuh tool) | **BLOCKED** |
| Reduced motion untuk animasi kiriman | belum diverifikasi (`prefers-reduced-motion`) | **NOT TESTED** |

## 8.4 Ringkasan prioritas

| ID | Temuan | P |
|---|---|---|
| SEC-01 | Kredensial di riwayat git, rotasi belum dilakukan | P1 |
| SEC-04 | 3 kerentanan dependensi (next/maplibre critical, postcss high) | P1 (upgrade) / risiko diterima untuk demo tertutup |
| SEC-02 | Password 7 akun demo di bundel klien | P2 |
| SEC-03 | Tidak ada pemisahan env demo/produksi | P2 |
| A11Y-01 | axe, keyboard, kontras belum diuji | BLOCKED |
| PERF-01 | Tidak ada uji beban/SLA | BLOCKED |
| DEP-01 | Dependensi Python tidak dipindai | BLOCKED |
