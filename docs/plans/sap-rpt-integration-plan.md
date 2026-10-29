# Rencana Integrasi SAP-RPT-1.6 — MealChain Guardian

**Tanggal:** 29 Oktober 2026
**Basis:** kondisi kode terukur, bukan asumsi. Setiap baris di §1 punya bukti di repo.
**Status titik awal:** klien RPT lengkap + **3 titik panggil** sudah memakai `run_forecast`; satu di antaranya baru disambungkan (29 Okt). Yang belum ada: cache/biaya, tampilan, dan bukti berulang.

---

## 1. Kondisi nyata hari ini (fakta terukur)

| # | Fakta | Bukti |
|---|---|---|
| F1 | Klien RPT lengkap (OAuth, payload `[PREDICT]`, baris QUERY, parse `confidence_interval`, sanitasi rahasia) | `backend/app/ai_providers/sap_ai_core_caller.py` |
| F2 | RPT dipanggil di 3 jalur: endpoint peramalan, Event 1 (PREDICT), orkestrator pengadaan demo | `api/demand.py:67`, `services/event1_orchestrator.py:338`, `services/demo_procurement_orchestrator.py:301` |
| F3 | Endpoint peramalan mengembalikan `source` + `fallback_used` (label jujur) | `api/demand.py` → `susun_forecast()` |
| F4 | Terbukti live: `Bandung/ayam` → `method=sap_rpt_1_6`, `confidence=0.99559`, `fallback_used=false` | probe 29 Okt; tes `tests/test_demand_forecast_rpt.py` |
| F5 | Saklar `FORECAST_PROVIDER=statistical` mematikan panggilan model tanpa ubah kode | `api/demand.py::_rpt_diizinkan` |
| F6 | **Tidak ada cache** hasil peramalan; hanya token OAuth yang di-cache | `sap_ai_core_caller.py:216`; tak ada `lru_cache`/TTL di jalur forecast |
| F7 | **Frontend tidak pernah memanggil** `/demand/forecast` — `fetchForecast` ada tapi 0 pemanggil | `frontend/lib/api.ts:1182`; grep `fetchForecast` = 0 hasil |
| F8 | Riwayat yang dikirim ke model hanya **3 titik** (`limit(3)`) | `api/demand.py` |
| F9 | Event 1 sudah mencatat `method`/`provider`/`fallback_used`/`attempts` ke trace keputusan | `event1_orchestrator.py:346-352` |
| F10 | Pengujian RPT yang ada: kontrak caller, fallback, 5 kasus endpoint | `tests/test_sap_ai_core_caller.py`, `test_forecast_client.py`, `test_demand_forecast_rpt.py` |

**Kesimpulan:** integrasi *fungsional* sudah ada dan terbukti. Yang belum adalah integrasi *produk*: angka model tidak sampai ke layar, biaya per panggilan tidak dikendalikan, dan kualitas masukan (3 titik) terlalu tipis untuk model tabular.

---

## 2. Definisi "sempurna" untuk proyek ini

Integrasi disebut sempurna bila **semua** terpenuhi:

1. **Satu pintu** — hanya satu fungsi yang boleh memanggil RPT; tiga jalur memakai fungsi itu (tidak ada logika ganda).
2. **Murah** — satu kombinasi (lokasi, komoditas, horizon, jendela data) hanya memicu paling banyak satu inferensi per TTL.
3. **Terlihat** — UI menampilkan angka + **label sumber** + alasan bila cadangan dipakai.
4. **Jujur** — gagal/timeout/balasan tak terbaca → turun ke statistik dengan label, tidak pernah mengarang angka.
5. **Tidak melanggar batas peran** — RPT hanya mengisi angka **kebutuhan**; biaya, kesegaran, keamanan pangan, dan keputusan tetap deterministik (`Rules.md` §1.1).
6. **Bisa diaudit** — setiap pemakaian meninggalkan jejak (kapan, parameter, sumber, durasi, fallback) tanpa rahasia.
7. **Bisa dimatikan** — satu env memaksa statistik; demo tanpa internet tetap jalan.

---

## 3. Peta permukaan integrasi

| Lokasi | Sekarang | Pekerjaan |
|---|---|---|
| `api/demand.py` | RPT + label | Ganti ke gateway tunggal (§4 F1), riwayat 3 → 28 hari (F2), header `X-Forecast-Source` |
| `services/event1_orchestrator.py` | RPT + trace | Pakai gateway; trace menambah `source` + `cache_hit` |
| `services/demo_procurement_orchestrator.py` | RPT | Pakai gateway; hormati cache agar satu siklus demo tidak memicu puluhan inferensi |
| `agent/*` (worker) | — | Tidak boleh memanggil RPT langsung; hanya membaca hasil lewat API |
| `frontend/lib/api.ts` | fungsi mati | Dipakai kartu peramalan (F3) |
| `frontend/app/page.tsx` | hanya builder mock | Kartu "Peramalan" + badge sumber |

---

## 4. Fase dan langkah

### F1 — Satu pintu pemanggilan (S)

**Tujuan:** hilangkan tiga salinan logika (validasi riwayat, kebijakan horizon, label).

- Buat `backend/app/services/forecast_service.py`:
  `forecast_kebutuhan(db, *, location_id, commodity_id, horizon_days) -> ForecastHasil`
  Berisi: ambil riwayat (batas waktu sama dengan `/balance`), validasi panjang riwayat, panggil `run_forecast`, kembalikan `{qty_kg, method, source, confidence, fallback_used, sample_count, window}`.
- Ganti tiga titik panggil memakai service ini.
- `api/demand.py` tinggal: resolve lokasi/komoditas → scope check → service → respons.

**Acceptance**
- `grep -rn "run_forecast(" backend/app | grep -v ai_providers/forecast_client.py` → **1 hasil** (di `services/forecast_service.py`).
  *(Titik awal terukur 29 Okt: 3 titik panggil — `api/demand.py`, `event1_orchestrator.py`, `demo_procurement_orchestrator.py` — di luar definisi di `forecast_client.py`.)*
- `grep -rn "sap_rpt_caller_from_env(" backend/app | grep -v ai_providers/forecast_client.py` → **1 hasil**.
- 3 tes lama (`test_demand_forecast_rpt`, event1 flow, demo procurement) tetap hijau.
- Respons endpoint tetap memuat `forecast_qty_kg`, `method`, `confidence`, `source`, `fallback_used` (kontrak tidak berubah).

**Risiko regresi:** event1 & demo orchestrator punya bentuk keluaran sendiri (`predict_out`); service harus mengembalikan objek yang mudah dipetakan, bukan memaksa satu bentuk respons HTTP.

---

### F2 — Kualitas masukan (S)

**Tujuan:** model tabular butuh deret, bukan 3 titik.

- Naikkan jendela riwayat: `limit(3)` → **28 hari terakhir** (batas waktu tetap `_batas_waktu(None)` supaya baris masa depan tidak ikut).
- Aturan minimum: `< 7` titik → **jangan panggil model**, langsung statistik dengan `reason="riwayat kurang dari 7 hari"` (murah + jujur).
- Bulatkan keluaran ke 2 desimal di service (`quantize2` yang sudah ada), supaya UI dan trace tidak menampilkan 2166.9235229492188.
- Satuan: seluruh rantai **kg**; konversi (jika ada) dilakukan sebelum masuk model, tidak sesudah.

**Acceptance**
- Tes: riwayat 3 titik → `source="statistical_fallback"`, `reason` menyebut jumlah hari; riwayat 28 titik → jalur model dipanggil (fake caller).
- Nilai yang dikembalikan API selalu ≤ 2 desimal.
- Tidak ada baris `recorded_at > batas` yang masuk masukan (tes dengan 1 baris masa depan).

---

### F3 — Cache dan biaya (M)

**Tujuan:** satu halaman tidak boleh memicu puluhan inferensi berbayar.

- Cache TTL di proses: kunci `(location_id, commodity_id, horizon_days, tanggal_jendela)`, TTL **15 menit** (`FORECAST_CACHE_TTL_SECONDS`).
- `horizon_days` ikut kunci: 7 dan 14 hari adalah prediksi berbeda, jangan saling menimpa.
- Catat `cache_hit` di respons (boleh tidak ditampilkan ke juri, tapi ada untuk audit).
- Batas panggilan: `FORECAST_MAX_CALLS_PER_MINUTE` (bawaan 20). Lewat batas → statistik + `reason="batas panggilan peramalan"`.
- Invalidate: TTL saja untuk versi pertama. Invalidasi berbasis peristiwa (demand baru masuk) **jangan** dikerjakan sekarang — belum ada jalur tulis demand dari UI.

**Acceptance**
- 10 permintaan berurutan kombinasi sama → 1 panggilan ke caller (dihitung via fake caller), 9 `cache_hit=true`.
- Setelah TTL lewat (dimundurkan di tes) → panggilan baru.
- Kombinasi horizon berbeda → panggilan terpisah.
- Saat batas terlampaui → tidak ada panggilan jaringan sama sekali.

**Catatan biaya:** biaya nyata per inferensi **BELUM TERVERIFIKASI** (tidak ada akses Cost Explorer AI Core). Jangan menulis angka rupiah di laporan sebelum diukur.

---

### F4 — Tampilan (M) — *bagian yang paling terlihat juri*

**Tujuan:** angka RPT terlihat, sumbernya tidak disembunyikan.

- Pakai `fetchForecast` (sekarang mati) di kartu peramalan pada halaman yang relevan (lokasi × komoditas).
- Kartu menampilkan: angka kg, horizon, **badge sumber** (`SAP-RPT-1.6` hijau / `cadangan statistik` abu), `confidence` bila ada, dan kalimat penjelas bila fallback.
- Jangan menampilkan `confidence` sebagai "akurasi" — itu keyakinan model, bukan jaminan.
- Sertakan keterangan satu baris: "prediksi model untuk kebutuhan; keputusan tetap deterministik".

**Acceptance**
- Kartu merender 3 keadaan: model (badge SAP), fallback (badge cadangan + alasan), memuat/gagal (skeleton + pesan, bukan 0 kg).
- `tsc --noEmit` + `next lint` bersih; ada tes komponen untuk ketiga keadaan.
- Tidak ada angka 0 yang ditampilkan saat data tidak tersedia.

---

### F5 — Observability dan audit (S)

- Log terstruktur per pemanggilan: `event=forecast`, `location_id`, `commodity_id`, `horizon_days`, `source`, `fallback_used`, `cache_hit`, `duration_ms`, `http_status`. **Tanpa** token/secret.
- Simpan ringkasan ke trace keputusan (Event 1 sudah melakukannya — tambahkan `source` + `cache_hit`).
- Penghitung sederhana di `/health` atau endpoint internal: `forecast_calls_total`, `forecast_fallback_total`, `forecast_cache_hit_total` (in-process; reset saat restart — cukup untuk demo, bukan produksi).

**Acceptance**
- Satu pemanggilan menghasilkan tepat satu baris log dengan field di atas.
- Tidak ada nilai secret pada log (tes: scan log contoh untuk pola Bearer/AKIA/`client_secret`).
- Endpoint kesehatan menampilkan tiga penghitung.

---

### F6 — Ketahanan (M)

- Timeout: 30 s (nilai sekarang) dipertahankan; tambahkan tes bahwa timeout → fallback, bukan 500.
- Retry: **tidak** untuk RPT (inferensi berbayar + tidak idempoten secara biaya). Satu percobaan, lalu fallback. (Berbeda dari chain LLM yang boleh retry.)
- Circuit breaker sederhana: 5 kegagalan berturut-turut → 5 menit memaksa statistik tanpa panggilan, lalu coba lagi.
- Degradasi: AI Core mati ≠ aplikasi mati. Semua jalur harus tetap 200 dengan label cadangan.

**Acceptance**
- Tes: caller melempar 5× → panggilan ke-6 **tidak** menyentuh jaringan; setelah jendela lewat, dicoba lagi.
- Tes: AI Core 503 → endpoint 200, `source="statistical_fallback"`, `fallback_used=true`.
- Tidak ada endpoint yang membalas 5xx hanya karena AI Core gagal.

---

### F7 — Batas peran (S) — *pengaman aturan*

- Tes arsitektur: modul yang menghitung **biaya/kesegaran/keamanan** (`core/safe_delivered_cost.py`, `core/temperature.py`, `core/batch_eligibility*.py`) **tidak boleh** mengimpor apa pun dari `ai_providers` atau `services/forecast_service`.
- RPT hanya boleh memengaruhi angka **kebutuhan** (`KEBUTUHAN_KG`), tidak pernah `safety_status`, `usable_until`, atau komponen biaya.

**Acceptance**
- Tes impor-modul gagal bila aturan dilanggar.
- Tidak ada kolom safety/biaya yang nilainya berasal dari `forecast_qty_kg` (grep + tes).

---

### F8 — Dokumentasi dan skrip demo (S)

- `sap-joule/docs/rpt-forecast-notes.md` sudah diperbarui (bukti live + saklar) — tambahkan bagian cache/biaya setelah F3.
- Skrip demo 90 detik: (1) buka kartu → badge SAP-RPT-1.6, (2) `FORECAST_PROVIDER=statistical` → badge cadangan + alasan, (3) kembalikan → badge SAP. Tiga keadaan itu bukti paling kuat ke juri karena tidak bisa dipalsukan.
- Catat di README: RPT = model tabular, bukan LLM; angkanya prediksi, bukan data SAP nyata (`Rules.md` §1.4).

**Acceptance**
- Langkah demo bisa dijalankan ulang tanpa edit kode.
- Dokumen menyebut apa yang **belum** dibuktikan (biaya, kualitas vs statistik pada data seed).

---

## 5. Keputusan owner (default bila tidak ada jawaban)

| # | Pertanyaan | Default rencana |
|---|---|---|
| O1 | TTL cache | 15 menit |
| O2 | Riwayat minimum untuk memanggil model | 7 hari |
| O3 | Batas panggilan per menit | 20 |
| O4 | Retry RPT | tidak ada retry, langsung fallback |
| O5 | `confidence` ditampilkan ke juri | ya, dengan label "keyakinan model" |
| O6 | Default provider | RPT bila kredensial terisi; `FORECAST_PROVIDER=statistical` mematikan |

---

## 6. Urutan eksekusi

1. **F1** (satu pintu) — fondasi; semua fase lain menempel di sini.
2. **F7** (batas peran) — murah, mencegah pelanggaran aturan sejak awal.
3. **F2** (kualitas masukan) — memperbaiki angka sebelum angka itu ditampilkan.
4. **F3** (cache/biaya) — sebelum UI memanggil berkali-kali.
5. **F5** (observability) — supaya F4 bisa dibuktikan.
6. **F4** (UI) — setelah angka murah dan terukur.
7. **F6** (ketahanan) — sebelum demo, bukan sesudah.
8. **F8** (dokumen + skrip demo).

Alasan urutan: F1 dulu karena menggandakan pekerjaan bila tiga jalur berevolusi sendiri; F7 sedini mungkin karena pelanggaran `Rules.md` §1.1 adalah risiko yang tidak boleh menunggu; F3 harus sebelum F4 agar UI tidak menciptakan biaya tak terkendali.

---

## 7. Definition of Done

1. `run_forecast` dan `sap_rpt_caller_from_env` hanya dipanggil dari satu modul. ✔ terukur dengan grep.
2. Semua respons peramalan memuat `source` + `fallback_used`; tidak ada 0 kg untuk data tidak tersedia.
3. 10 permintaan kombinasi sama → ≤1 inferensi.
4. UI menampilkan tiga keadaan (model / cadangan / gagal).
5. Tidak ada impor dari `ai_providers` ke modul safety/biaya (tes gagal bila dilanggar).
6. Semua kegagalan AI Core → 200 + label cadangan; tidak ada 5xx.
7. `ruff check .` bersih, `tsc --noEmit` bersih, suite backend pada DB sekali-pakai hijau (kegagalan tersisa harus sudah terdokumentasi sebelumnya).
8. Log memuat field audit tanpa rahasia.
9. Dokumen menyebut batas: biaya nyata belum diukur, kualitas RPT vs statistik belum dibandingkan pada data seed.

---

## 8. Yang sengaja TIDAK dikerjakan
- **Perbandingan akurasi RPT vs statistik pada data seed** — butuh data historis panjang + ground truth; kalau dipaksakan, hasilnya akan menyesatkan. Bisa fase terpisah setelah F1–F3.
- **Biaya per inferensi dalam rupiah** — butuh akses penagihan AI Core.
- **Invalidasi cache berbasis peristiwa** — belum ada jalur tulis demand dari UI.
- **Membuat RPT memengaruhi keselamatan/biaya** — dilarang `Rules.md` §1.1, bukan sekadar belum dikerjakan.
- **gRPC/SDK `sap-ai-sdk-*`** — REST yang sudah terbukti live lebih sedikit dependensi.

---

## 9. Status eksekusi — 29 Oktober 2026

Semua fase F1–F8 dikerjakan pada working tree `feature/db-modes-demo-coverage`
(belum di-commit). Bukti di bawah berasal dari perintah yang benar-benar dijalankan.

| Fase | Status | Bukti |
| --- | --- | --- |
| F1 satu pintu | **SELESAI** | `app/services/forecast_service.py`; `run_forecast(` tinggal 1 titik panggil di luar definisi (dijaga tes) |
| F2 kualitas masukan | **SELESAI** | jendela 28 hari, `recorded_at <= batas` (baris masa depan tidak dipakai), ambang 7 titik, bulat 2 desimal |
| F3 cache + anggaran | **SELESAI** | TTL 900 s, 20 panggilan/menit, breaker 5 gagal → 300 s; terukur: 3 permintaan → **2 inferensi + 1 cache hit** |
| F4 tampilan | **SELESAI** | `buildForecastView` + kartu `SupplyDemandPanel` menampilkan sumber (`SAP-RPT-1.6` / `cadangan statistik`); 10 tes vitest lulus |
| F5 observability | **SELESAI** | `GET /health` → `forecast.{forecast_calls_total, forecast_fallback_total, forecast_cache_hit_total, sap_rpt_configured, cache_entries, breaker_open}` |
| F6 ketahanan | **SELESAI** | timeout/exception → cadangan tanpa retry; breaker teruji; `FORECAST_PROVIDER=statistical` kill switch |
| F7 batas peran | **SELESAI** | `tests/test_forecast_role_boundary.py` (AST): modul keselamatan/biaya dilarang mengimpor `ai_providers`/`forecast_service` |
| F8 dokumentasi | **SELESAI** | dokumen ini + `sap-joule/docs/rpt-forecast-notes.md` + skrip demo §10 |

### Bukti HTTP lewat server uvicorn sungguhan

Instance uvicorn kedua (port 8011) dijalankan **di dalam container**, menunjuk DB
disposable `mealchain_fix`, dengan `.env` asli (kredensial AI Core terisi):

```
GET /demand/forecast/Bandung/ayam?horizon_days=7   → 200
  {"forecast_qty_kg":2113.41,"method":"sap_rpt_1_6","confidence":0.9488,
   "source":"SAP-RPT-1.6","fallback_used":false,"sample_count":28,"cache_hit":false}

GET ...?horizon_days=7   (ulang)                  → 200, cache_hit=true, angka sama
GET ...?horizon_days=14                           → 200, 4244.75  (≈2×, horizon dihormati)
GET /health                                       → forecast_calls_total=2,
                                                    forecast_cache_hit_total=1,
                                                    sap_rpt_configured=true
```

Artinya: tiga permintaan pengguna hanya menghasilkan **dua** inferensi berbayar.

### Gate akhir (29 Okt, DB `mealchain_fix` yang di-seed ulang)

| Gate | Hasil |
| --- | --- |
| `vitest` (frontend) | **2773 lulus / 252 file** (termasuk 3 tes render kartu sumber) |
| `tsc --noEmit` | **0** |
| `next lint` | **0** |
| `ruff check .` | **All checks passed** |
| pytest (2321 tes) | **14 gagal / 2331 lulus / 34 skip**, 1020 s |

Klasifikasi 14 kegagalan (bukan semuanya milik pekerjaan ini):

1. **1 milik pekerjaan ini, sudah diperbaiki** — `test_openapi_artifact_drift`
   gagal karena docstring `/health` berubah setelah `openapi.json` diregenerasi;
   artefak diregenerasi ulang → lulus.
2. **4 kontrak KPI 8-metrik** (`test_kpi_api` ×2, `test_hari_ini` ×2) — di working
   tree, `kpi_service._kpi_ep_aktif()` kini *default aktif* (delapan metrik) dengan
   docstring "Konsep Performance & Audit (29 Okt 2026)". Perubahan ini **tidak**
   berasal dari pekerjaan RPT (sebelumnya opt-in, default tujuh) dan belum di-commit;
   tes lama masih menuntut 7.
3. **6 pre-existing** — `test_demo_cases_procurement_binding`,
   `test_demo_template_provenance_ledger`, `test_supplier_procurement_eval` ×2,
   `test_procurement_execute_guard` ×2 (keluarga AUD-010/012/016, tergantung seed).
4. **3 bergantung urutan** — `test_api_decision_intelligence` ×2 dan
   `test_demo_timeseries_api` ×1; **lulus saat dijalankan sendiri**, gagal di suite
   penuh karena state DB bersama.

### Batas yang masih berlaku

- Biaya per inferensi (rupiah) belum terukur: tidak ada akses penagihan AI Core.
- Akurasi RPT vs statistik pada data seed belum dibandingkan (tidak ada ground truth).
- Cache bersifat per-proses: beberapa replika backend tidak berbagi cache (lihat §8).
- Penghitung `/health` juga per-proses dan hilang saat restart.

---

## 10. Skrip demo 90 detik — "RPT ini benar-benar jalan"

Tujuan: juri melihat angka model, labelnya, dan bukti bahwa cadangan tidak
menyamar sebagai model.

**Persiapan (sebelum tampil)**

1. `curl -s localhost:8000/health` → pastikan `forecast.sap_rpt_configured: true`.
2. Buka pop-up *Pasokan & permintaan* untuk satu lokasi/komoditas, biarkan kartu
   perkiraan tampil sekali (memanaskan cache).

**Alur 90 detik**

| Detik | Yang dilakukan | Yang dikatakan |
| --- | --- | --- |
| 0–15 | Tunjuk kartu "Perkiraan 7 hari" | "Angka ini bukan rata-rata kami — ini keluaran SAP-RPT-1.6 di SAP AI Core. Label di bawahnya menyebut sumbernya." |
| 15–35 | `curl` endpoint yang sama | "Permintaan kedua tidak memanggil model lagi: cache 15 menit. Di demo yang sama kami tunjukkan penghitungnya di `/health`." |
| 35–55 | `curl -s localhost:8000/health` | "Dua permintaan, dua inferensi, satu dari cache. Itu alasan kami menaruh anggaran panggilan, bukan sekadar menyambung model." |
| 55–70 | Set `FORECAST_PROVIDER=statistical`, muat ulang kartu | "Kalau AI Core mati, angka tetap muncul — tapi labelnya berubah jadi 'cadangan statistik'. Kami tidak membiarkan cadangan menyamar sebagai model." |
| 70–90 | Kembalikan ke `sap_rpt` | "Saklar ini juga yang kami pakai saat latihan, supaya tidak membakar kuota." |

**Jangan diucapkan (belum terbukti)**

- "RPT lebih akurat" — belum dibandingkan pada data seed.
- "Terintegrasi penuh ke SAP" — yang tersambung adalah model RPT di AI Core;
  PO/pengadaan masih mock (`sap_mock_po`, header `X-Data-Source: MOCK`).
