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
| `a2a_server/server.py` | Aplikasi A2A (kartu agen, 3 skill, `/health`) + executor |
| `a2a_server/mealchain_client.py` | Klien HTTP baca-saja ke API v0.2.0 (`/batches`, `/balance/map`, `/kpi`, `/decisions`), kegagalan eksplisit |
| `a2a_server/report.py` | Perender markdown murni (tabel, format angka Indonesia) |
| `a2a_server/manifest.yml`, `runtime.txt`, `.cfignore` | Deklarasi deploy Cloud Foundry |
| `joule/` | Capability Joule: `da.sapdas.yaml`, `capability.sapdas.yaml`, 3 scenario, 1 function |
| `scripts/probe_ai_core.py` | Probe kredensial + model AI Core (`gpt-5.4`, `sap-rpt-1.6`) — jalur terpisah |
| `docs/runbook-cf-joule.md` | **Langkah manual Roy**: CF CLI → keybroker → `cf push` → Destination → `joule deploy` |
| `docs/rpt-forecast-notes.md` | Rencana memakai `sap-rpt-1.6` untuk peramalan kebutuhan (belum diintegrasikan) |

## Menjalankan & menguji lokal

```bash
cd sap-joule
cd sap-joule/a2a_server
uv venv .venv
uv pip install -r requirements-dev.txt   # requirements.txt + pytest + uvicorn

./.venv/Scripts/python.exe -m pytest tests -q   # 42 tes: format, klien HTTP v0.2.0, siklus hidup A2A
```

Menjalankan jembatan di laptop (butuh backend MealChain hidup):

```bash
cd sap-joule/a2a_server
MEALCHAIN_API_URL=http://127.0.0.1:8000 \
MEALCHAIN_READ_USERNAME=bgn.monitor@demo.local \
MEALCHAIN_READ_PASSWORD='Demo#BGN2026' \
python -m uvicorn server:app --host 127.0.0.1 --port 8098
```

## Tiga skill yang tersedia untuk Joule

| Skill | Endpoint backend | Isi |
|---|---|---|
| `supply_situation` | `/batches` + `/balance/map` (satu panggilan per komoditas yang ada di inventaris) | dua tabel: keseimbangan pasokan/kebutuhan per lokasi (yang KURANG lebih dulu) dan inventaris batch dengan status keamanan + skor kesegaran apa adanya |
| `kpi_snapshot` | `/kpi` (jendela waktu diminta jembatan, default 7 hari) | 7 indikator dengan nama & satuan dari backend; yang tak bisa dihitung tampil `—` + alasannya |
| `approval_queue` | `/decisions` + `/decisions/{id}/approval-summary` (maks 12 baris) | antrean usulan lengkap asal→tujuan + komoditas (nama, bukan id) + catatan bahwa persetujuan dilakukan manusia di UI |

Pemilihan skill **deterministik** (bukan LLM): pesan JSON dengan field `skill`, atau kata kunci
pada kalimat pengguna (`kpi`/`indikator` → KPI; `usulan`/`persetujuan`/`approval` → antrean;
sisanya → pasokan). Batas jujur: kalimat yang ambigu bisa memilih skill yang bukan maksud
pengguna; perbaikan yang lebih kuat adalah satu BTP Destination + satu kartu agen per skill —
sengaja belum diambil agar konfigurasi tidak melebar sebelum dipakai di panggung.

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
