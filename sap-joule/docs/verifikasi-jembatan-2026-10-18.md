# Verifikasi jembatan Joule — 18 Okt 2026

Tujuan: membuktikan (a) artefak Joule di repo lengkap dan sesuai syarat deploy, (b) jembatan
benar-benar membaca **backend kita**, bukan instans lain, dan (c) tes menangkap kalau salah satu
dari keduanya rusak.

## 1. Artefak Joule di repo (tidak terhapus)

| Berkas | Isi yang dikunci |
|---|---|
| `joule/da.sapdas.yaml` | `schema_version 1.4.0`, `name: mealchain_assistant_4sehat3trio`, satu capability `local` |
| `joule/mealchain_capability/capability.sapdas.yaml` | `schema_version 3.28.0`, `namespace: joule.ext`, alias `MEALCHAIN_AGENT → SWZ_JOULE` |
| `.../functions/mealchain_query_function.yaml` | `status-update → agent-request (remote, result_variable apiResponse) → message` |
| `.../scenarios/{situasi_pasokan,indikator_kinerja,antrean_usulan}.yaml` | tiga skill, semua menargetkan fungsi yang sama |

Jalur artefak yang dipakai Joule: `<? apiResponse.body.artifacts[0].parts[0].text ?>`.
Kalau ini berubah tanpa mengubah `server.py`, Joule menampilkan kosong tanpa error.

## 2. Jembatan lokal vs backend kita (bukti hidup)

```
cd sap-joule && MEALCHAIN_READ_PASSWORD='<akun baca demo>' bash scripts/uji-jembatan-lokal.sh
```

Hasil 18 Okt 2026 09:5x:

```
OK   /health: jembatan sehat, backend http://localhost:8000 terjangkau
OK   'situasi pasokan SPPG' -> Keseimbangan pasokan per lokasi (20 baris), yang kurang ditampilkan lebih dulu:
OK   'indikator kinerja KPI' -> Indikator kinerja MealChain Guardian (7 metrik, angka dari backend):
OK   'antrean usulan keputusan' -> Antrean usulan keputusan MealChain Guardian (11 baris):
OK   antrean: ID 235db32c-7ae0-4dad-9893-583f021dd69b benar-benar ada di database demo
SEMUA OK
```

Pemeriksaan terakhir itu yang penting: laporan antrean bisa terlihat benar padahal berasal dari
database lain. Skrip mengambil UUID pertama dari laporan lalu menanyakan langsung ke tabel
`decisions`.

## 3. Temuan: jembatan yang TERDEPLOY di Cloud Foundry menunjuk backend lain

Diukur pada 18 Okt 2026 sebelum perubahan apa pun:

| Pemeriksaan | Hasil |
|---|---|
| `GET <bridge>/.well-known/agent-card.json` | 200, 3 skill, tanpa `securitySchemes` |
| `GET <bridge>/health` | `"reachable": true` |
| `POST <bridge>/` `message/send` "antrean usulan" | 5 baris, ID `29cd1436-…`, `3cf3576c-…` |
| Cek ID tersebut di DB demo | **0 baris** |
| `MEALCHAIN_API_URL` di `manifest.yml` | `https://gossip-move-emphasis-alice.trycloudflare.com` → **DNS tidak resolve** |
| `cf env <app>` | gagal: token CF kedaluwarsa, jadi URL runtime tidak bisa dibaca dari sini |

Kesimpulan: bridge hidup, tetapi data yang dijawab bukan milik DB kita — dan URL yang tercatat di
repo sudah mati, jadi nilai runtime-nya berada di luar repo. Perbaikan butuh `cf login` (kredensial
pemilik akun): `cf set-env <app> MEALCHAIN_API_URL <url backend> && cf restage <app>`, lalu
verifikasi ulang dengan skrip di bagian 2.

## 4. Tes yang menjaga

| Berkas | Isi | Hasil |
|---|---|---|
| `a2a_server/tests/test_kontrak_joule.py` (baru, 10 tes) | syarat deploy Joule dari YAML apa adanya + kecocokan kata kunci scenario dengan `resolve_skill` + tidak ada secret di templat env | lulus |
| `a2a_server/tests/test_integrasi_backend_hidup.py` (baru, 5 tes) | klien nyata ke backend nyata: `/batches`, `/balance/map`, `/kpi`, antrean + ringkasan, tidak ada metode tulis | 5 lulus (skip bila backend/creds tidak ada) |
| suite lama | `test_client.py`, `test_report.py`, `test_server.py` | lulus |

Total: **53 lulus, 4 dilewati** (yang dilewati = tes integrasi tanpa env backend/kredensial).

## 5. Perubahan lain

- `manifest.yml`: URL tunnel mati diganti placeholder `…invalid` (gagal berisik, bukan senyap) dan
  CORS `*` diganti daftar origin frontend. Jembatan ini tidak punya autentikasi.
- `requirements-dev.txt`: tambah `pyyaml` (tes kontrak membaca YAML).
- `docs/runbook-cf-joule.md` §10: urutan pasang ulang DA kalau hilang dari tenant, termasuk cara
  memisahkan "jembatan mati" dari "DA hilang".
