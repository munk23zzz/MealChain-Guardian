# sap-joule — jembatan MealChain Guardian ke SAP Joule (A2A)

Bagian ini **bukan** aplikasi kedua. Ia adaptor kecil yang membuat aplikasi MealChain Guardian
bisa ditanya lewat SAP Joule memakai protokol A2A ("Bring Your Own Agent"), tanpa menyentuh
`backend/` atau `frontend/` yang sudah lulus gatenya sendiri.

> **Kontrak API (11 Okt 2026).** Jembatan ini menembak API backend klon (a)
> `mealchain-guardian` **v0.2.0**: `POST /auth/login {email, password}` → `access_token`, lalu
> `/admin/locations`, `/batches`, `/balance/map?commodity=`, `/kpi?start&end`, `/decisions`,
> `/decisions/{id}/approval-summary`. Versi sebelum 11 Okt menembak backend v0.1.0 yang hanya
> punya `/ui/*` dengan login `{username, password}` → `token`. Mengganti `MEALCHAIN_API_URL`
> tanpa mencocokkan kontrak ini akan dijawab **422** (field login salah) atau **404** (`/ui/*`).

```
Joule chat (SAP)
   │  scenario cocok (kata kunci)
   ▼
Joule function  ── agent-request (A2A, JSON-RPC) ──▶  BTP Destination: SWZ_JOULE
                                                          │ HTTPS
                                                          ▼
                                       a2a_server/server.py  (Cloud Foundry)
                                                          │ HTTP + JWT akun baca
                                                          ▼
                                       backend MealChain  /batches · /balance/map
                                                          /kpi · /decisions
```

## Aturan yang dipegang jembatan ini

| Aturan | Wujudnya di kode |
|---|---|
| `Rules.md` §1.1 — LLM tidak menghitung angka safety-critical | `report.py` **tidak punya aritmetika**: hanya memformat angka yang backend kirim. Tidak ada model bahasa di jalur ini. |
| `Rules.md` §1.2 — tidak ada auto-execute | Tidak ada endpoint tulis di klien (`ReadOnlyBackend`). Akun yang dipakai berperan `bgn_monitor` (baca-saja); persetujuan TETAP di UI MealChain. |
| `Rules.md` §1.3 — status keamanan tidak pernah di-override | Status keamanan batch (`pass`/`fail`) diteruskan apa adanya; perender hanya memberi label Indonesia (`lolos`/`GAGAL`), tidak mengubah nilainya. |
| `Rules.md` §1.4 — yang mock harus terlihat mock | Setiap laporan menyertakan catatan sumber data dari `/health` (mis. `MOCK`). |
| Joule menunggu sinkron maks 60 detik | Setiap skill hanya memanggil endpoint **baca** yang cepat; tidak ada rantai model. |

Kalau backend tidak bisa dibaca, Joule menjawab "belum bisa diambil" + penyebabnya — **bukan**
tabel kosong atau angka 0 yang terbaca seolah tidak ada masalah.

## Berkas

| Berkas | Isi |
|---|---|
| `a2a_server/server.py` | Aplikasi A2A (kartu agen, 11 skill, `/health`) + executor |
| `a2a_server/mealchain_client.py` | Klien HTTP baca-saja ke API v0.2.0 (`/batches`, `/balance/map`, `/kpi`, `/decisions`, `/sap/purchase-orders`, `/price`, `/demand`, `/waste/summary`, `/supplier-exclusions`, `/supplier-routes`, `/integrations/status`, `/ledger/verify`, `/receipts`), kegagalan eksplisit |
| `a2a_server/report.py` | Perender markdown murni (tabel, format angka Indonesia) |
| `a2a_server/manifest.yml`, `runtime.txt`, `.cfignore` | Deklarasi deploy Cloud Foundry |
| `joule/` | Capability Joule: `da.sapdas.yaml`, `capability.sapdas.yaml`, 10 scenario, 1 function |
| `scripts/probe_ai_core.py` | Probe kredensial + model AI Core (`gpt-5.4`, `sap-rpt-1.6`) — jalur terpisah |
| `scripts/uji-semua-skill.py` | Bukti ujung-ke-ujung: 11 skill dijawab dari backend hidup + angka laporan disilang ke Postgres |
| `docs/runbook-cf-joule.md` | **Langkah manual Roy**: CF CLI → keybroker → `cf push` → Destination → `joule deploy` |
| `docs/rpt-forecast-notes.md` | Rencana memakai `sap-rpt-1.6` untuk peramalan kebutuhan (belum diintegrasikan) |

## Menjalankan & menguji lokal

```bash
cd sap-joule
cd sap-joule/a2a_server
uv venv .venv
uv pip install -r requirements-dev.txt   # requirements.txt + pytest + uvicorn

./.venv/Scripts/python.exe -m pytest tests -q   # 106 tes: format, klien HTTP v0.2.0, routing 11 skill, siklus hidup A2A
```

Menjalankan jembatan di laptop (butuh backend MealChain hidup):

```bash
cd sap-joule/a2a_server
MEALCHAIN_API_URL=http://127.0.0.1:8000 \
MEALCHAIN_READ_USERNAME=bgn.monitor@demo.local \
MEALCHAIN_READ_PASSWORD='Demo#BGN2026' \
python -m uvicorn server:app --host 127.0.0.1 --port 8098
```

## Sebelas skill yang tersedia untuk Joule

| Skill | Endpoint backend | Isi |
|---|---|---|
| `supply_situation` | `/batches` + `/balance/map` (satu panggilan per komoditas yang ada di inventaris) | dua tabel: keseimbangan pasokan/kebutuhan per lokasi (yang KURANG lebih dulu) dan inventaris batch dengan status keamanan + skor kesegaran apa adanya |
| `kpi_snapshot` | `/kpi` (jendela waktu diminta jembatan, default 7 hari) | 7 indikator dengan nama & satuan dari backend; yang tak bisa dihitung tampil `—` + alasannya |
| `approval_queue` | `/decisions` + `/decisions/{id}/approval-summary` (maks 12 baris) | antrean usulan lengkap asal→tujuan + komoditas (nama, bukan id) + catatan bahwa persetujuan dilakukan manusia di UI |
| `purchase_order` | `/sap/purchase-orders` (satu panggilan, plafon 200 baris) | daftar PO (nomor, status, lokasi, bahan, jumlah, total, status keputusan) atau rincian satu PO bila nomornya disebut; PO impor SAP ditandai `impor SAP` |
| `supplier_directory` | `/suppliers` (satu panggilan, plafon 200 baris; 60 pemasok demo) | direktori pemasok per SPPG: komoditas, keandalan, kapasitas/minggu, kiriman aktif (batch + kg), penanda dikecualikan di hub; tanpa baris kiriman = belum mengirim, bukan nol |
| `price_intelligence` | `/price/{lokasi}/{komoditas}` + `/price/quotes/…` per pasangan (maks 8 pasangan) | harga acuan per kg (sumber + waktu catat) dan kuotasi pemasok terbaru; jembatan TIDAK menghitung termurah/rata-rata — dinyatakan di catatan |
| `demand_forecast` | `/demand/{lokasi}/{komoditas}` + `/demand/forecast/…` per pasangan (maks 8) | kebutuhan kg + tenggat, serta prakiraan backend dengan `method` dan `confidence` apa adanya (`statistical_fallback` ditulis sebagai fallback statistik) |
| `food_loss` | `/waste/summary?days=30` | tiga angka terpisah: limbah tercatat, dialihkan ke mitra, tanpa mitra; plus piring mitra pengolahan; "tidak tersedia" + alasan bila tidak ada baris |
| `supplier_risk` | `/supplier-exclusions` + `/supplier-routes` (maks 200, geometri dibuang) + nama pemasok/lokasi dari `/suppliers`, `/admin/locations` | eksklusi pemasok per hub (status, alasan, sejak/dicabut) dan kiriman aktif: jarak jalan, durasi, status perjalanan, ETA |
| `decision_evidence` | `/decisions/{id}/compliance` + `/chain` + `/traces` (maks 3 keputusan terakhir, atau satu keputusan yang UUID-nya disebut) | tanda tangan (algoritma, potongan tanda tangan), hasil verifikasi materi, alamat isi, iterasi rantai + alasan penolakan, jejak langkah agen |
| `system_status` | `/integrations/status` + `/ledger/verify` + `/sap/purchase-orders/summary` + `/admin/locations` | status 7 komponen integrasi beserta buktinya, keabsahan ledger (blok, rasio, peringatan cakupan), ringkasan PO, cakupan jaringan SPPG; `/admin/users` sengaja tidak dibuka (PII) |
| `supply_situation` (lanjutan) | `/receipts?batch_id=…` bila pengguna menyebut satu batch | bagian "Penerimaan barang" satu batch: checklist (suhu/kemasan/berat/catatan), pencatat, waktu |

Pemilihan skill **deterministik** (bukan LLM): pesan JSON dengan field `skill`, nomor PO di dalam
teks (`MC-661695B2C685`), atau kata kunci pada kalimat pengguna, dengan urutan yang diuji:
`kpi`/`indikator` → KPI; nomor/kata `po` → PO; `bukti`/`jejak`/`audit`/`dossier`/`tanda tangan` →
bukti keputusan; `usulan`/`persetujuan`/`approval`/`keputusan` → antrean; `eksklusi`/`dikecualikan`/
`rute`/`jarak` → risiko pemasok; `harga`/`kuotasi` → harga; `kebutuhan`/`prakiraan`/`forecast` →
kebutuhan; `limbah`/`kehilangan`/`susut` → kehilangan pangan; `pemasok`/`supplier`/`direktori` →
direktori; `integrasi`/`ledger`/`status sistem` → status sistem; sisanya → pasokan. PO sengaja
diperiksa **sebelum** antrean: "PO mana yang sudah disetujui?" memuat kata `setuju` milik antrean.
Bukti diperiksa **sebelum** antrean: "bukti keputusan X" memuat kata `keputusan`. Eksklusi diperiksa
**sebelum** direktori: "pemasok mana yang dikecualikan?" memuat `pemasok`. Batas jujur: kalimat yang
ambigu bisa memilih skill yang bukan maksud pengguna; perbaikan yang lebih kuat adalah satu BTP
Destination + satu kartu agen per skill — sengaja belum diambil agar konfigurasi tidak melebar
sebelum dipakai di panggung.

Untuk skill berbasis pasangan (harga, kebutuhan), laporan memeriksa maksimal 8 pasangan
(SPPG × komoditas) dan **menyebutkan berapa yang tidak diperiksa**; kalau pengguna menyebut nama
SPPG atau komoditas, pemeriksaan dipersempit ke pasangan itu (bukan dipotong acak).

## Variabel environment

| Variabel | Untuk | Wajib |
|---|---|---|
| `MEALCHAIN_API_URL` | URL backend MealChain (dari sudut pandang Cloud Foundry) | ya |
| `MEALCHAIN_READ_USERNAME` / `MEALCHAIN_READ_PASSWORD` | akun baca-saja (`bgn.monitor@demo.local`) | ya |
| `MEALCHAIN_BRIDGE_CORS_ORIGINS` | origin yang boleh memanggil jembatan (default `*`) | tidak |
| `PORT` | port yang didengarkan (diisi Cloud Foundry) | tidak |
| `AICORE_*` | hanya untuk `scripts/probe_ai_core.py`, bukan untuk jembatan | tidak |

Semua kredensial diisi lewat `cf set-env` / environment lokal — **tidak pernah** di berkas repo.

## Status verifikasi (11 Okt 2026)

- `pytest tests -q` → **42 passed** (`report.py`, klien HTTP v0.2.0 via `httpx.MockTransport`,
  kartu agen + `/health` + siklus hidup A2A `working → artefak → completed`, jalur backend mati,
  `cancel`, tes kesesuaian protokol klien nyata, dan skill antrean).
- Uji **ujung-ke-ujung sungguhan** (11 Okt): jembatan lokal (uvicorn :8098) menembak backend
  MealChain v0.2.0 yang hidup → tiga permintaan `message/send` menjawab `completed`:
  (a) 20 baris keseimbangan pasokan (Jakarta telur kurang 780 kg di baris teratas) + inventaris
  6 batch termasuk `Surabaya telur 600 kg — GAGAL` keamanan; (b) 7 metrik KPI dengan satuan
  benar dan 2 metrik bertanda `—` beserta alasannya; (c) 12 usulan lengkap
  (`Cianjur → Jakarta | telur | 600 kg | pending_approval`) + catatan persetujuan tidak lewat Joule.
- `scripts/probe_ai_core.py` diuji pada jalur gagal: tanpa kredensial ia berhenti dengan pesan
  jelas + exit 2 (bukan jejak galat). Jalur live menunggu kredensial tim.

### Status verifikasi (20 Okt 2026) — skill PO

- `pytest tests -q` → **69 passed, 4 skipped** (sebelumnya 54). Tambahan: routing nomor PO,
  prioritas PO di atas antrean, batas kata (`produk`/`pasokan` bukan PO), renderer PO,
  kontrak YAML 4 scenario, protokol klien nyata, dan artefak skill PO.
- Tes integrasi backend hidup (`test_integrasi_backend_hidup.py`) → **6 passed** setelah
  ditambah satu tes PO; tes itu memeriksa `total = harga × jumlah` pada baris yang SAMA
  (konsistensi backend, bukan hitungan jembatan).
- Uji ujung-ke-ujung: jembatan lokal (uvicorn :8099, akun `bgn.monitor@demo.local`) menerima
  `message/send` "Tampilkan PO MC-661695B2C685" → `completed` dengan rincian
  `beras 600 kg, Rp13.300/kg, total Rp7.980.000, keputusan dieksekusi, Jakarta`.
  Angka yang sama dibaca langsung dari Postgres (`sap_mock_purchase_orders`), dan jumlah baris
  yang disebut laporan (23) sama dengan `SELECT count(*)`.
- `{"skill": "purchase_order"}` tanpa nomor → tabel 10 baris pertama + catatan sisa;
  nomor tak dikenal (`MC-000000000000`) → pesan jujur "tidak ditemukan di antara 23 PO",
  bukan tabel kosong.
- **Belum diverifikasi:** panggilan dari tenant Joule (butuh `cf push` + `joule deploy` oleh
  pemilik akun). Sampai itu dijalankan, kemampuan ini hanya terbukti di jembatan lokal.

### Status verifikasi (20 Okt 2026) — sebelas skill, semua domain data

- `pytest tests -q` → **106 passed, 14 skipped** (sebelumnya 69 passed). Tambahan: perender harga,
  kebutuhan, kehilangan pangan, risiko pemasok, bukti keputusan, status sistem, penerimaan barang;
  routing baru + uji presedensi terhadap skill lama; kontrak YAML 10 scenario.
- `test_integrasi_backend_hidup.py` → **15 passed** menembak backend hidup: `/batches` (158 baris,
  bukan 50), `/price`, `/price/quotes`, `/demand`, `/demand/forecast`, `/supply`, `/waste/summary`,
  `/supplier-exclusions`, `/supplier-routes`, `/decisions/{id}/{compliance,chain,traces}`,
  `/integrations/status`, `/ledger/verify`, `/sap/purchase-orders/summary`, `/receipts`.
- `scripts/uji-semua-skill.py` → **SEMUA OK**: 11 pertanyaan gaya Joule dijawab `completed` dari
  backend hidup, dan angka laporan disilang langsung ke Postgres (jumlah batch, blok ledger, PO,
  eksklusi pemasok, limbah 30 hari). Angka itu **dibaca ulang dari DB setiap kali** — dua run pada
  dataset berbeda sama-sama cocok (run 08.11: batch 158, blok 115, limbah 631,5 kg; run 08.13
  setelah dataset kanonik dimuat ulang: batch 78, blok 223, limbah 311,5 kg). Limbah butuh jendela
  `disposed_at <= now()` karena data demo memuat baris bertanggal masa depan (di luar jendela panel).
- Bukti lewat **bridge CF publik** (jalur yang dipakai Joule, bukan lokal): 10 pertanyaan domain
  dijawab `completed` dengan data, 2,6–9,7 detik per jawaban (batas tunggu Joule 60 detik).
  `/health` jembatan → `{"backend":{"reachable":true,…}}`.
- Bug yang diperbaiki: `GET /batches` dulu mengunci `.limit(50)` tanpa parameter (158 batch tampak
  50 tanpa galat). Sekarang `limit`/`offset` + `total`, `ORDER BY created_at DESC, id` (paginasi
  stabil saat `created_at` seri), dan jembatan meminta plafon 500.
- **Masih terbuka:** bridge CF `mealchain-joule-bridge-4sehat3trio` menunjuk
  `MEALCHAIN_API_URL` ke tunnel quick Cloudflare. Tunnel itu **mati setiap mesin tidur**, dan URL-nya
  berganti setiap dijalankan ulang — itulah sebabnya Joule pernah menjawab "backend tidak bisa
  dihubungi … Name or service not known". Pemulihan satu perintah:
  `bash sap-joule/scripts/tunnel-untuk-cf.sh` (tunnel baru → uji dari internet → `cf set-env` →
  restage → pastikan `reachable:true`). Untuk demo yang tidak boleh putus, pakai tunnel bernama atau
  backend di VPS — bukan quick tunnel.

## Yang sengaja BELUM ada

- **Mengusulkan/menyetujui dari Joule.** Endpoint tulis belum dipakai: angka safety-critical
  harus datang dari kode deterministik backend, dan persetujuan butuh identitas approver.
  Setelah jalur analisis deterministik tersedia, usulan bisa dibuka tanpa melanggar §1.1/§1.2.
- **Streaming A2A** (`capabilities.streaming = false`) dan status async multi-turn; Joule 60 detik
  sudah cukup karena semua skill cepat.
- **Provider RPT-1.6 di `/demand/forecast/*`** — rencananya di `docs/rpt-forecast-notes.md`.

## Atribusi (Apache-2.0)

Kerangka A2A (pola `AgentExecutor`, kartu agen, `manifest.yml`, bentuk YAML capability/function/
scenario, `.cfignore`) diadaptasi dari repo
[`SAP-AWS-ID-Hackathon-2026/SAP_AWS_Hackathon_ID_2026`](https://github.com/SAP-AWS-ID-Hackathon-2026/SAP_AWS_Hackathon_ID_2026)
(folder `joule_a2a/`, lisensi Apache-2.0). Rincian berkas ada di `NOTICE`.
