# Catatan: `sap-rpt-1.6` sebagai provider peramalan kebutuhan — **SUDAH TERSAMBUNG**

> Status per 29 Oktober 2026: klien RPT, kontrak payload, dan penyambungan ke
> `GET /demand/forecast/{location}/{commodity}` sudah ada di kode dan
> **dibuktikan live** (lihat "Bukti live" di bawah). Dokumen ini dulu berjudul
> "belum diintegrasikan ke kode" — itu sudah tidak benar.

Dokumen ini mencatat apa yang sudah TERBUKTI dari repo hackathon dan apa yang masih perlu
dibuktikan sebelum menyentuh `backend/`. Angka deployment di bawah dikutip dari
`BTP_Instructions/README.md` repo `SAP-AWS-ID-Hackathon-2026/SAP_AWS_Hackathon_ID_2026`.

## Kenapa ini relevan untuk MealChain Guardian

MealChain sudah punya jalur peramalan statistik sebagai fallback (`GET /demand/forecast/*`).
`SAP RPT-1.6` adalah model **tabular** (bukan bahasa) yang menerima tabel dengan sel bertanda
`[PREDICT]` lalu mengisi nilainya — bentuk yang persis cocok untuk "berapa kg kebutuhan satu SPPG
besok", yaitu kolom yang di tabel memang kosong.

Pembagian peran yang sesuai `Rules.md`:

- **RPT-1.6 (model)** → mengisi/memperkirakan kolom kebutuhan. Ini prediksi model, bukan angka
  yang dikarang LLM, jadi tidak melanggar §1.1.
- **`backend/app/core/*` (kode deterministik)** → tetap pemegang angka safety-critical
  (kesegaran, keamanan pangan, batas kirim, biaya aman). RPT tidak boleh menyentuh ini.
- **Fallback statistik** → tetap ada sebagai rantai cadangan; pola `with_fallback_chain` sudah
  dipakai proyek ini untuk rantai model.

## Fakta yang sudah pasti (terverifikasi dari repo hackathon)

| Item | Nilai |
|---|---|
| Deployment `sap-rpt-1.6` | `d76cf689a05d504f` |
| Endpoint | `POST {AI_API_URL}/v2/inference/deployments/d76cf689a05d504f/predict` |
| Header | `Authorization: Bearer <token>`, `AI-Resource-Group: default`, `Content-Type: application/json` |
| Payload | `prediction_config.target_columns[]` (`name`, `prediction_placeholder: "[PREDICT]"`, `task_type: regression\|classification`), `index_column`, `rows[]` |
| Balasan | berisi `predictions` + skor keyakinan |
| Kredensial | keybroker `ai-core/<slug-tim>-key` (`clientid`, `clientsecret`, `url`, `serviceurls.AI_API_URL`) |
| Python SDK | `sap-ai-sdk-base==3.4.0`, `sap-ai-sdk-core==3.3.0`, `sap-ai-sdk-gen==6.7.0`; versi tutorial memakai `gen_ai_hub.proxy.native.sap.client.RPTClient` (`predict(body=..., model_name="sap-rpt-1.6")`) |
| JS SDK | `@sap-ai-sdk/rpt` → `new RptClient({ deploymentId, resourceGroup })` |

## Bukti live (29 Oktober 2026)

Klien: `backend/app/ai_providers/sap_ai_core_caller.py` (`build_rpt_caller`).
Penyambung: `backend/app/api/demand.py` (`susun_forecast`).

```
GET /demand/forecast/Bandung/ayam?horizon_days=7
200 {"forecast_qty_kg": 2166.9235, "method": "sap_rpt_1_6",
     "confidence": 0.99559, "source": "SAP-RPT-1.6", "fallback_used": false}
```

Saklar darurat (demo tanpa internet / hemat biaya):

```
FORECAST_PROVIDER=statistical
→ 200 {"forecast_qty_kg": 2164.869, "method": "statistical_fallback",
       "confidence": 1.0, "source": "statistical_fallback", "fallback_used": true}
```

Kontrak respons dibekukan: `forecast_qty_kg`, `method`, `confidence`, **`source`**
(`SAP-RPT-1.6` | `statistical_fallback`), **`fallback_used`**. UI/juri bisa membedakan
angka model dari angka cadangan tanpa menebak.

Tes pengunci: `backend/tests/test_demand_forecast_rpt.py` (5 kasus: RPT berhasil,
balasan sampah, balasan tanpa angka, pemanggil melempar, tanpa pemanggil).

## Langkah berikutnya (kalau Roy memilih jalur ini)

1. **Buktikan jalur kredensial dulu, tanpa menyentuh kode aplikasi**:
   `AICORE_*` diisi dari keybroker → `python sap-joule/scripts/probe_ai_core.py --rpt`.
   Kalau ini belum hijau, integrasi ke kode hanya akan menambah variabel gagal.
2. **Bekukan kontrak**: `GET /demand/forecast/{location}/{commodity}` mengembalikan deret harian
   + `source` yang jelas (`sap-rpt-1.6` atau `statistical_fallback`) supaya juri bisa melihat mana
   yang model dan mana yang fallback — pola penandaan yang sama dengan `X-Data-Source` mock SAP.
3. **Tulis test kontrak lebih dulu** (TDD): satu kasus "RPT hidup → `source=sap-rpt-1.6`",
   satu kasus "RPT gagal/timeout → turun ke fallback statistik tanpa membuang label kejujuran",
   satu kasus "balasan RPT tidak lengkap → **tidak** diisi angka taksiran".
4. **Baru** sambungkan ke rantai provider yang ada, default tetap statistik sampai hasil live
   RPT terbukti lebih baik pada data seed.

> **Status 29 Okt 2026:** langkah 1–4 selesai. Penyimpangan yang disengaja: default adalah
> **RPT bila kredensial terisi** (bukan statistik) karena demo butuh angka model yang nyata;
> cadangan statistik tetap otomatis dan dilabeli. `FORECAST_PROVIDER=statistical` mengembalikan
> perilaku lama kapan pun dibutuhkan.

## Yang TIDAK boleh dilakukan

- Menghitung biaya/kesegaran/keamanan dari keluaran RPT (`Rules.md` §1.1).
- Menampilkan hasil RPT sebagai data SAP nyata kalau kredensial/mode masih mock (`Rules.md` §1.4).
- Menaruh kredensial AI Core di `manifest.yml` atau di repo (`Rules.md` §7): pakai `cf set-env`
  atau environment lokal.

## Satu pintu + anggaran panggilan (29 Okt 2026)

Seluruh pemanggilan model kini melewati `backend/app/services/forecast_service.py`.
Sebelumnya tiga jalur memanggil `run_forecast` sendiri-sendiri
(`/demand/forecast`, `event1_orchestrator`, `demo_procurement_orchestrator`) dengan
masukan berbeda: endpoint memakai 3 catatan terakhir, orkestrator memakai SELURUH
catatan termasuk baris bertanggal masa depan. Sekarang ketiganya berbagi:

- jendela **28 hari** dan hanya baris `recorded_at <= batas` (masa depan bukan riwayat);
- ambang minimum **7 titik** — di bawahnya model tidak dipanggil sama sekali;
- pembulatan **2 desimal** (`quantize2`) supaya angka kartu dan trace sama;
- **cache** 15 menit per (lokasi, komoditas, horizon, tanggal) — `FORECAST_CACHE_TTL_SECONDS`;
- **batas 20 panggilan/menit** per proses — `FORECAST_MAX_CALLS_PER_MINUTE`;
- **circuit breaker**: 5 kegagalan beruntun membuka 5 menit — `FORECAST_BREAKER_FAILS`,
  `FORECAST_BREAKER_SECONDS`. Tidak ada retry: inferensi berbayar tidak diulang diam-diam;
- `GET /health` menampilkan `forecast.sap_rpt_configured`, jumlah panggilan, jumlah
  cadangan, jumlah cache hit, dan breaker terbuka.

Dijaga tes: `tests/test_demand_forecast_rpt.py`, `tests/test_forecast_service_budget.py`,
`tests/test_forecast_role_boundary.py` (AST: modul keselamatan/biaya dilarang
mengimpor `ai_providers`/`forecast_service`).

### Bukti HTTP (uvicorn sungguhan, DB disposable `mealchain_fix`)

```
GET /demand/forecast/Bandung/ayam?horizon_days=7 → 200
  {"forecast_qty_kg":2113.41,"method":"sap_rpt_1_6","confidence":0.9488,
   "source":"SAP-RPT-1.6","fallback_used":false,"sample_count":28,"cache_hit":false}
GET … (ulang)                                    → 200, cache_hit=true
GET /health → forecast_calls_total=2, forecast_cache_hit_total=1, sap_rpt_configured=true
```
