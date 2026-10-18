# Runbook manual — jembatan MealChain Guardian ke SAP Joule (Cloud Foundry + Joule Studio)

Semua langkah di bawah dijalankan MANUAL oleh Roy. Tidak ada langkah yang sudah dijalankan
otomatis dari sisi kode: yang ada di repo hanyalah berkasnya (`manifest.yml`, YAML capability,
`server.py`). Sumber angka kredensial: `BTP_Instructions/README.md` di repo
`SAP-AWS-ID-Hackathon-2026/SAP_AWS_Hackathon_ID_2026`.

Urutan: (1) siapkan CLI → (2) kredensial → (3) deploy jembatan → (4) verifikasi → (5) Destination
→ (6) deploy Joule → (7) uji di Joule chat.

---

## 0. Prasyarat (cek dulu, ini yang sering menghambat)

| Alat | Syarat | Cara cek |
|---|---|---|
| Cloud Foundry CLI | v8 | `cf version` |
| Node.js | **24 – 26** untuk Joule Studio CLI | `node -v` |
| Python (opsional, untuk menjalankan jembatan lokal) | 3.12/3.13 | `python --version` |

> **Temuan nyata di mesin ini (10 Okt 2026): `node -v` = v26.7.0 dan `joule --version` = 2.0.4 —
> jalan normal.** `engines.node` pada `@sap/joule-studio-cli@2.0.4` (dibaca dari
> `package.json` paket terpasang) adalah `>=24.0.0 <27`, jadi Node 26 masih di dalam rentang.
> Catatan lama "20.12 – 24" berlaku untuk rilis CLI sebelum 2.x; kalau muncul kegagalan aneh,
> turunkan ke Node 24 (`nvm use 24`) dulu sebelum menuduh YAML-nya salah.

---

## 1. Kredensial (keybroker)

Ganti `<slug-tim>` dengan nama tim huruf kecil (spasi → tanda hubung). Simpan hasilnya di luar git.

> **Di PowerShell, `curl` bukan curl.** `curl` = alias `Invoke-WebRequest`, dan `-s` dianggap
> singkatan `-SessionVariable` sehingga URL ikut tertelan dan muncul prompt
> "Supply values for the following parameters: Uri:". Pakai `curl.exe` (tersedia di
> `C:\Windows\System32\curl.exe`), atau `Invoke-RestMethod -Uri`, atau jalankan di Git Bash.

> **Respons joule key memuat `clientsecret`.** Jangan pernah mencetaknya ke layar/chat:
> `curl.exe -s <url> -o joule-key.json`, lalu tulis nilainya langsung ke `.env` (langkah §7)

```bash
# Di Git Bash/Linux: curl        Di PowerShell: curl.exe (lihat catatan di atas)
curl.exe -s -o ai-core-key.json https://hackathon-keybroker.cfapps.ap10.hana.ondemand.com/ai-core/<slug-tim>-key
curl.exe -s -o joule-key.json   https://hackathon-keybroker.cfapps.ap10.hana.ondemand.com/joule/<slug-tim>-key
curl.exe -s -o group.json       https://hackathon-keybroker.cfapps.ap10.hana.ondemand.com/group/<slug-tim>
```

- `ai-core/<slug>-key` → `clientid`, `clientsecret`, `url`, `serviceurls.AI_API_URL`
  (dipakai `scripts/probe_ai_core.py`; **tidak** dipakai jembatan Joule).
- `joule/<slug>-key` → bagian `uaa` (`clientid`, `clientsecret`, `url`) untuk `joule login`.
  **`uaa.url` = `--authurl`** (sumber kebenaran). Terverifikasi 10 Okt 2026 (slug `4sehat3trio`):
  `uaa.url` = `https://aws-sap-hackathon-si4ykj9d.authentication.ap10.hana.ondemand.com` —
  **beda** dari nilai `--authurl` yang dihardcode di `BTP_Instructions/README.md` §5
  (`https://auisywroy.authentication.ap10.hana.ondemand.com`). Pakai `uaa.url`; nilai README itu
  hanya cadangan kalau login gagal dengan error auth. Catatan: key ini juga punya `uaa.apiurl`,
  tetapi isinya `https://api.authentication.ap10.hana.ondemand.com` (endpoint UAA, **bukan**
  API URL Joule) — `--apiurl` tetap `https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap`.
- `group/<slug>` → `group_id` (UUID) untuk `visibility_condition` bila scenario dikunci ke tim.

Catatan yang mudah menjebak: nilai `clientid`/`clientsecret` mengandung karakter `! | $ =`,
jadi selalu kutip tunggal di shell (`'...'`).

---

## 2. Login Cloud Foundry

```bash
cf login -a https://api.cf.ap10.hana.ondemand.com --sso
```

Saat diminta: pilih **alternate/custom identity provider**, isi origin key **`auisywroy-platform`**,
buka URL passcode, masuk dengan email IAS (dari `BTP_Instructions/README.md` §1), lalu tempel passcode.

```bash
cf target -o "SEAIO_aws-sap-hackathon-si4ykj9d" -s "hackathon-<slug-tim>"
```

Kalau muncul pesan token kedaluwarsa: ulangi `cf login --sso`.

---

## 3. Pastikan backend MealChain bisa dijangkau DARI Cloud Foundry

Jembatan ini memanggil backend MealChain lewat HTTP, dan Cloud Foundry **tidak bisa** mencapai
`localhost` laptop. Pilih salah satu:

| Opsi | Cara | Catatan |
|---|---|---|
| a. Tunnel publik | `cloudflared tunnel --url http://localhost:8000` → dapat URL `https://...trycloudflare.com` | Paling cepat; URL berubah tiap dijalankan ulang |
| b. VPS (sudah ada) | deploy backend + Postgres + frontend di VPS, pakai URL publik VPS | Paling dekat dengan "arsitektur nyata"; ada di rencana infra proyek |
| c. Tidak dipakai | — | Jembatan tetap hidup, tetapi setiap permintaan menjawab "backend tidak bisa dihubungi" (jujur, bukan angka palsu) |

Nilai URL itu yang dimasukkan ke `MEALCHAIN_API_URL` di langkah berikutnya.

**Syarat kontrak (penting, 11 Okt 2026).** Yang harus terjangkau adalah backend klon (a)
`mealchain-guardian` **v0.2.0** — bukan backend v0.1.0 yang hanya punya `/ui/*`. Periksa dulu
dengan dua perintah ini sebelum menyentuh Cloud Foundry:

```bash
curl -s "$URL/openapi.json" | python -c "import sys,json;d=json.load(sys.stdin);print(d['info']['title'], d['info']['version'], len(d['paths']))"
# harapan: MealChain Guardian 0.2.0 44

curl -s -o /dev/null -w '%{http_code}\n' -X POST "$URL/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"bgn.monitor@demo.local","password":"Demo#BGN2026"}'
# harapan: 200
```

`422` pada login = field salah (backend v0.1.0 menunggu `username`, bukan `email`);
`404` pada `/ui/*` = wajar untuk v0.2.0 karena rute itu memang tidak ada di sana.

---

## 4. Deploy jembatan ke Cloud Foundry

```bash
cd sap-joule/a2a_server
# edit manifest.yml: ganti `mealchain-joule-bridge-GANTI-SLUG-TIM` -> nama aplikasi tim,
# dan isi MEALCHAIN_API_URL dengan URL dari langkah 3.
cf push --no-start
cf set-env mealchain-joule-bridge-<slug-tim> MEALCHAIN_READ_USERNAME 'bgn.monitor@demo.local'
cf set-env mealchain-joule-bridge-<slug-tim> MEALCHAIN_READ_PASSWORD 'Demo#BGN2026'
cf start mealchain-joule-bridge-<slug-tim>
cf app mealchain-joule-bridge-<slug-tim>      # catat `routes:` -> itulah URL aplikasi
```

Kredensial akun baca: sengaja akun demo berperan **bgn_monitor** (baca-saja). Kalau password demo
di `backend/app/seed/seed_data.py` berubah, ganti juga nilai di sini — jembatan tidak punya jalan tulis,
jadi akun baca-saja adalah pilihan dengan hak paling kecil.

`.env` TIDAK pernah ikut terunggah: sudah ada di `.cfignore`.

---

## 5. Verifikasi sebelum menyentuh Joule

```bash
BRIDGE=https://mealchain-joule-bridge-<slug-tim>-<acak>.cfapps.ap10.hana.ondemand.com
curl -s $BRIDGE/health | head -c 400        # {"status":"ok", "backend":{"reachable":true,...}}
curl -s $BRIDGE/.well-known/agent-card.json | head -c 400
```

`/health` **selalu** 200 selama aplikasi hidup — kalau backend MealChain mati, keterjangkauannya
dilaporkan di dalam body (`backend.reachable: false`), bukan dengan status gagal. Alasannya:
Cloud Foundry me-restart aplikasi yang health check-nya gagal, dan yang bermasalah di sini bukan
aplikasi jembatan.

Uji cepat satu tugas A2A (opsional, tanpa Joule):

```bash
curl -s -X POST $BRIDGE -H 'Content-Type: application/json' -d '{
  "jsonrpc":"2.0","id":"1","method":"message/send",
  "params":{"message":{"messageId":"m1","role":"user","kind":"message",
  "parts":[{"kind":"text","text":"Bagaimana kondisi pasokan SPPG hari ini?"}]}}}' | head -c 600
```

---

## 6. BTP Destination (jembatan antara capability dan URL aplikasi)

**Nama yang benar bukan `SWZ_JOULE`.** Diperiksa 11 Okt 2026 dengan
`joule get mealchain_assistant_4sehat3trio -c mealchain_capability` pada asisten yang sudah
ter-deploy, system alias `MEALCHAIN_AGENT` berbunyi:

```
Default Destination:  SWZ_JOULE
Custom Destination:   MEALCHAIN_AGENT_01
```

Runtime memakai **Custom Destination** (menimpa `destination:` di `capability.sapdas.yaml`), dan nilai
itu tersimpan di konfigurasi asisten — bukan di YAML. Karena itu deploy ulang YAML **tidak** mengubah
tujuan panggilan, dan `joule get/update/config/deploy` tidak punya opsi untuk menggantinya.
Gejala kalau destination-nya belum ada: web client hanya bilang "Something went wrong", log berbunyi
`Failed to retrieve destination: MEALCHAIN_AGENT_01 … (JCore - 5802)`.

### Cara membuat destination tanpa cockpit (terbukti 11 Okt 2026)

Cockpit tim hanya punya peran **Subaccount Viewer**, jadi halaman Connectivity tidak bisa dipakai.
Jalan yang berhasil: buat service instance `destination` sendiri, lalu pakai Destination
Configuration API. Plan `lite` gratis dan read+write tingkat akun.

```bash
cf create-service destination lite mealchain-destinations
cf create-service-key mealchain-destinations mealchain-dest-key
cf service-key mealchain-destinations mealchain-dest-key > sap-joule/dest-key.json   # JANGAN dicetak ke layar
```

`dest-key.json` (field `credentials`: `uri`, `url`, `clientid`, `clientsecret`) sudah terabaikan git
lewat pola `*-key.json`. Lalu ambil token `client_credentials` dari `credentials.url` + `/oauth/token`
dan panggil API-nya (`credentials.uri` + `/destination-configuration/...`):

| Tindakan | Permintaan |
|---|---|
| lihat daftar | `GET /destination-configuration/v1/subaccountDestinations` |
| buat | `POST /destination-configuration/v1/subaccountDestinations` |
| baca satu | `GET /destination-configuration/v1/subaccountDestinations/<Nama>` |

Isi badan POST untuk jembatan ini:

```json
{
  "Name": "MEALCHAIN_AGENT_01",
  "Type": "HTTP",
  "URL": "https://mealchain-joule-bridge-4sehat3trio.cfapps.ap10.hana.ondemand.com",
  "Authentication": "NoAuthentication",
  "ProxyType": "Internet",
  "Description": "Jembatan A2A MealChain Guardian (tim 4sehat3trio)"
}
```

Hasil 11 Okt 2026: `POST` → **201**, read-back `GET .../MEALCHAIN_AGENT_01` → **200**, daftar
subaccount = `["MEALCHAIN_AGENT_01", "SWZ_JOULE"]`. Token cukup ber-scope `uaa.resource` — tidak perlu
scope `Destination.*` maupun peran Destination Administrator.

Kalau nanti destination ini dihapus, ulangi dua perintah `cf create-service*` di atas (instance-nya
boleh dipakai ulang; key lama pun masih berlaku) lalu POST lagi. `cf delete-service mealchain-destinations`
untuk membersihkan seluruhnya.

Catatan: destination bernama `SWZ_JOULE` (URL `https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap`,
NoAuthentication) memang milik panitia dan **bukan** endpoint A2A — `POST /` di sana membalas 401 dan
`/.well-known/agent-card.json` membalas 400. Mengarahkan alias ke sana tidak akan menghasilkan data.


---

## 7. Deploy capability Joule

```bash
node -v            # 24–26 (lihat §0)
npm i -g @sap/joule-studio-cli   # di mesin ini sudah terpasang 2.0.4
joule --version    # harus mencetak 2.0.4
joule login --no-app-tid \
  --authurl '<uaa.url dari joule key>' \
  --apiurl  'https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap' \
  -c '<uaa.clientid dari joule key>' \
  -s '<uaa.clientsecret dari joule key>'
# lalu CLI menanyakan username (email IAS) + password secara interaktif
joule status        # harus "Logged in"
```

Alternatif tanpa menaruh secret di riwayat shell (pola `--use-env` yang dibaca langsung oleh CLI):

```bash
cd sap-joule/joule
cp joule.env.example .env      # isi clientid/secret + email/password; .env sudah di .gitignore
joule login --use-env .env     # JOULE_AUTH_NO_APP_TID=true di berkas itu menggantikan --no-app-tid
```

Jalur paling sedikit langkah manual: `scripts/joule-login.ps1` (PowerShell 5.1, sudah diuji di mesin ini).

```powershell
powershell -ExecutionPolicy Bypass -File sap-joule\scripts\joule-login.ps1          # pakai .env yang ada
powershell -ExecutionPolicy Bypass -File sap-joule\scripts\joule-login.ps1 -Force   # tulis ulang .env dari joule-key.json
powershell -ExecutionPolicy Bypass -File sap-joule\scripts\joule-login.ps1 -DryRun  # siapkan .env saja, tanpa login
```

Skrip itu membaca `joule-key.json`, menulis `joule\.env` (UTF-8 tanpa BOM, `uaa.url` sebagai authurl),
lalu menjalankan `joule login --use-env .env` + `joule status`. Email/password IAS tetap diketik manual
saat CLI bertanya — skrip tidak pernah menyimpan atau mencetak `clientsecret`.

Detail yang mudah menyesatkan:

- `deploy`, `list`, dan `launch` **belum muncul** di `joule --help` sebelum login
  ("To see all the available commands please log in") — jadi lakukan login dulu, bukan menyimpulkan
  perintahnya tidak ada.
- `joule launch` mengambil **nama digital assistant** (nama yang dipakai saat `-n`), bukan nama
  folder capability. URL yang dibuka selalu `<apiurl>/webclient/standalone/<nama-asisten>`
  (dikonfirmasi dari `launchApiClient.js` pada paket 2.0.4).
- `joule deploy --compile .` (bentuk di `BTP_Instructions/README.md` §5) **ekuivalen** dengan
  `joule deploy -c` di folder yang memuat `da.sapdas.yaml`; pakai bentuk `-c -n "<nama>"` supaya
  nama asistennya eksplisit dan sama dengan yang dipakai `joule launch`.
- `jl` adalah **Joule Work CLI** (solutions/agents/MCP) yang dikirim dalam paket npm yang sama —
  bukan jalan untuk capability legacy ini.

```bash
cd sap-joule/joule
joule lint                                    # periksa YAML dulu (juga butuh login)
joule deploy -c -n "mealchain_assistant_4sehat3trio"
joule list                                    # cari nama asisten di kolom "Digital Assistant Name"
joule launch "mealchain_assistant_4sehat3trio"
```

Nama itu **satu sumber**: `name:` di `da.sapdas.yaml` (sekarang `mealchain_assistant_4sehat3trio`).
Akhiran slug tim dipakai karena tenant Joule ini dipakai bersama semua tim hackathon — nama
generik seperti `mealchain_assistant` berisiko bentrok dengan tim lain. Kalau `-n "<nama>"` di
`joule deploy` diisi nilai lain, nilai ITU yang menang dan harus dipakai juga di `joule launch`
(verifikasi lewat `joule list`).

`joule deploy -c` akan memberi peringatan `DTA did not define an optional i18n folder` — itu normal.

---

## 8. Uji di Joule chat

Kirim salah satu kalimat ini (kata kuncinya yang memilih skill — lihat
`a2a_server/server.py` → `resolve_skill`):

| Kalimat | Skill | Yang muncul |
|---|---|---|
| "Bagaimana kondisi pasokan SPPG hari ini?" | situasi pasokan | tabel stok/kebutuhan/selisih per SPPG + komoditas |
| "Tampilkan KPI mingguan" | indikator kinerja | tabel KPI, `—` + alasan untuk yang tak bisa dihitung |
| "Apa saja usulan yang menunggu persetujuan?" | antrean usulan | tabel usulan + catatan bahwa persetujuan di UI MealChain |

Lalu coba juga jalur kegagalan yang memang diinginkan: matikan backend (opsi c) → Joule harus
menjawab "belum bisa diambil", **bukan** tabel kosong yang terbaca seolah tidak ada masalah.

---

## 9. Kalau ada masalah

| Gejala | Penyebab yang paling sering |
|---|---|
| `joule: command not found` | `$(npm config get prefix)/bin` belum ada di PATH |
| `cf push` gagal, health check | Baca `cf logs <app> --recent`; pastikan `MEALCHAIN_API_URL` terisi (aplikasi tetap harus hidup walau backend mati) |
| `destination not found` | Nama destination ≠ nilai di `capability.sapdas.yaml`, atau salah `XX` |
| Joule menjawab kosong | Cek `curl $BRIDGE/health`, lalu `cf logs <app> --recent` |
| Timeout di Joule | Joule menunggu maks 60 detik; jembatan ini hanya memanggil endpoint baca cepat — kalau timeout, backend-nya yang lambat |
| Scenario tidak cocok | Kata kunci pada deskripsi scenario harus ada di kalimat pengguna ("pasokan", "kpi", "usulan") |
| Setelah ubah role/group, akses gagal | Logout-login ulang Joule CLI **dan** web client: token masih menyimpan role lama |

---

## 10. Kalau asisten Joule hilang dari tenant (pasang ulang)

Digital Assistant hasil `joule deploy` hidup di tenant, **bukan** di repo. Kalau tenant di-reset,
DA dihapus orang lain, atau `joule list` kosong, artefak di repo tidak hilang — yang hilang hanya
hasil deploy-nya. Urutan diagnosis lalu pasang ulang:

**1. Pisahkan "jembatan mati" dari "DA hilang".**

```
curl -s https://mealchain-joule-bridge-4sehat3trio.cfapps.ap10.hana.ondemand.com/health
```

| Hasil | Artinya | Tindakan |
|---|---|---|
| `"reachable":true` | jembatan hidup & backend terjangkau | lanjut ke langkah 2 (masalahnya di sisi Joule) |
| `"reachable":false` | jembatan hidup, URL backend salah/mati | `cf set-env <app> MEALCHAIN_API_URL <url baru>` + `cf restage <app>` — **bukan** deploy ulang DA |
| tidak menjawab / 502 | aplikasi CF mati | `cf app <app>` lalu `cf logs <app> --recent` |

**2. Pastikan prasyarat yang sering terlupa** (tanpa ini deploy tetap "berhasil" tapi chat diam):

- Destination `SWZ_JOULE` ada di cockpit, Proxy Type = Internet, Authentication = NoAuthentication.
  Nama harus **persis** — salah huruf → `destination not found`.
- Agent card jembatan hidup: `curl -s https://<bridge>/.well-known/agent-card.json` → 3 skill.
- `capability.sapdas.yaml`: `schema_version: 3.28.0` dan `namespace: joule.ext`.

**3. Deploy ulang dari folder `joule/`** (tempat `da.sapdas.yaml`):

```
cd sap-joule/joule
joule login --no-app-tid          # authurl = uaa.url dari key tim, bukan URL di README
joule lint
joule deploy -c -n "mealchain_assistant_4sehat3trio"
joule list                        # nama di kolom "Digital Assistant Name" harus muncul
joule launch "mealchain_assistant_4sehat3trio"
```

`joule deploy` **tidak** punya `--use-env`; hanya `joule login` yang punya. Login selalu meminta
username+password IAS — tidak bisa diotomasi, dan secret tidak boleh masuk riwayat shell.

**4. Verifikasi bahwa yang dijawab Joule adalah data kita, bukan instans lain.**

Jalankan dari akar repo (stack demo hidup):

```
cd sap-joule
MEALCHAIN_READ_PASSWORD='<password akun baca demo>' bash scripts/uji-jembatan-lokal.sh
```

Skrip itu memeriksa `/health`, tiga skill, dan **mencocokkan satu UUID keputusan dari laporan
antrean dengan tabel `decisions`**. Kalau UUID-nya tidak ada di DB kita, jembatan menunjuk backend
lain — gejala yang pernah terjadi 18 Okt 2026 (tunnel mati, host di manifest sudah tidak resolve).

Kontrak artefak Joule (DA, capability, fungsi, scenario, kata kunci) dikunci tes di
`a2a_server/tests/test_kontrak_joule.py`, supaya perubahan/penghapusan berkas ketahuan sebelum
deploy, bukan saat demo.
