# Catatan: `sap-rpt-1.6` sebagai provider peramalan kebutuhan (belum diintegrasikan ke kode)

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

## Yang TIDAK boleh dilakukan

- Menghitung biaya/kesegaran/keamanan dari keluaran RPT (`Rules.md` §1.1).
- Menampilkan hasil RPT sebagai data SAP nyata kalau kredensial/mode masih mock (`Rules.md` §1.4).
- Menaruh kredensial AI Core di `manifest.yml` atau di repo (`Rules.md` §7): pakai `cf set-env`
  atau environment lokal.
