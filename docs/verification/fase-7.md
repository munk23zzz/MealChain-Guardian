# Verifikasi Fase 7 — pemasok mock yang benar-benar terjangkau SPPG Jakarta

> **Snapshot tahun 2026 (tanggal tidak tertulis)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Tanggal: 2026-10-15
Rencana: `.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md` (Fase 7: 7a data, 7b aturan
tampilan, 7c bukti)
Lingkungan: Docker Compose lokal — `mealchain-postgres` (:15432), `mealchain-backend` (:8000),
`mealchain-mock-sap` (:8001), `mealchain-frontend` (:3010); migrasi head `013_origin_generated_at`.

Tujuan dokumen ini: mencatat **bukti** Fase 7 pada aplikasi yang hidup, dan **hal yang belum
beres**. Semua angka diambil dari keluaran alat (pytest, ruff, vitest, API langsung lewat
`httpx`, dan DOM halaman yang berjalan), bukan dari perkiraan.

## 1. Gerbang otomatis

| Gerbang | Perintah | Hasil |
|---|---|---|
| Backend tes | `docker compose exec backend pytest -q` | **767 lulus, 3 skip, 0 gagal** |
| Backend lint | `docker compose exec backend ruff check .` | **All checks passed!** |
| Frontend tes | `docker compose exec frontend npx vitest run` | **532 lulus / 58 berkas** |
| Frontend tipe | `npx tsc --noEmit` | **exit 0** |
| Frontend lint | `npx next lint` | **exit 0** |
| Frontend build | `npx next build` (dijalankan **setelah** `docker compose stop frontend`) | **exit 0** |

Sebelum Fase 7 gerbangnya 760 (backend) / 518 (frontend) — Fase 7 menambah **7 tes backend** dan
**14 tes frontend**; tidak ada tes lama yang dilemahkan. Yang **sengaja diubah** hanya angka yang
memaku keadaan lama: `?commodity=telur` 10 → 6, `?location=cianjur` 7 → 5, `offset=40` → 30
(paginasi), dan legenda pemasok 3 → 4 makna.

> **Peringatan prosedur (terbukti lagi di sesi ini):** `next build` di kontainer frontend **saat
> `next dev` hidup** menimpa `.next`; BUILD sendiri gagal
> (`PageNotFoundError: Cannot find module for page: /_document`) dan halaman yang sudah terbuka
> kehilangan hidrasi secara DIAM — form login terisi tapi tombol demo tidak mengisi apa pun dan
> tombol "Masuk" tidak bereaksi, tanpa satu pun error di konsol. Obat: hentikan `next dev` sebelum
> build, lalu `docker compose restart frontend`.

## 2. Data pemasok (7a)

Berkas `data/seed/suppliers_demo.json` ditulis ulang: **21 baris** demo (sebelumnya 30) —
12 pemasok klaster Jakarta berkoordinat **absolut** + 9 pemasok lokal satu per hub lain.

Jarak berjenjang dari SPPG Jakarta (-6,2088 / 106,8456), dihitung haversine:

| Jenjang | Pemasok (jarak km) |
|---|---|
| 0–25 km | Sayur Segar Kramat Jati 7,7 · Telur Berkah Jakarta 8,6 · Prima Ayam Sejahtera Jakarta 13,4 · Telur Berkah Bekasi 16,3 · Sayur Segar Depok 22,3 · Prima Ayam Sejahtera Tangerang 23,9 |
| 25–60 km | Telur Berkah Bogor 43,4 · Ayam Segar Karawang 51,2 · Sayur Segar Puncak 54,7 |
| 60–150 km | Telur Berkah Cianjur 75,1 · Ayam Segar Serang 77,7 · Wortel Lestari Subang 108,6 |

Akibatnya di database: **35 pemasok** = 14 kanonik (`data/seed/sprint1_seed.json`, tidak disentuh)
+ 21 demo; `?commodity=telur` = **6** (4 klaster Jakarta + Surabaya + Medan).
Seeder `backend/app/seed/suppliers_demo.py`:
- dua mode koordinat (absolut dari berkas, atau titik hub + geseran tetap);
- validasi: koordinat separuh/ di luar Indonesia ditolak, klaster Jakarta **wajib absolut** dan
  **wajib ≤150 km** dari SPPG Jakarta (`REACH_KM_MAX`);
- baris demo yang hilang dari berkas dibuang saat seeding (15 baris), dan pembuangan **ditolak**
  bila masih ada `batches`/`price_signals`/PO/eksklusi yang menunjuk baris itu;
- haversine kini hidup di satu tempat: `app/core/geo.py` (dipakai seeder dan endpoint).

## 3. API `GET /suppliers` (7b)

Bukti diambil dengan `httpx` **dari dalam kontainer backend** ke API yang hidup, memakai kredensial
di `app.seed.seed_data.DEMO_USERS` (kata sandi dibaca, tidak pernah dicetak).

| Panggilan | Peran | Hasil nyata |
|---|---|---|
| `GET /suppliers?limit=200` | SPPG Head | `total 35`, `distance_reference.location = Jakarta` (-6,2088) |
| `GET /suppliers?max_distance_km=150&limit=200` | SPPG Head | `total 22`, `reach = {max_distance_km: 150.0, excluded_out_of_reach: 13, excluded_unknown_distance: 0}` |
| `GET /suppliers?commodity=telur&max_distance_km=150` | SPPG Head | `total 4`, `excluded_out_of_reach 2` (Surabaya 665 km, Medan 1.419 km) |
| `GET /suppliers?limit=200` | bgn_monitor | `total 35`, `distance_reference null`, `distance_km` semua `null` |
| `GET /suppliers?max_distance_km=150` | bgn_monitor | **422** — `penyaring jarak butuh titik rujukan: akun yang terikat lokasi atau filter location=` |
| `GET /suppliers?location=Jakarta&max_distance_km=150` | bgn_monitor | `total 13`, `distance_reference.location Jakarta` |
| `GET /suppliers?max_distance_km=-1`, `=5000` | SPPG Head | **422** (batas `ge=0, le=2000`) |

Kontrak respons berubah sadar (diuji di `tests/test_suppliers_api.py`):
- kunci tingkat atas: `count`, `total`, `limit`, `offset`, **`distance_reference`**, **`reach`**, `items`;
- kunci per baris: 16 kunci lama + **`distance_km`**;
- `total` = jumlah **setelah** penyaringan (bukan jumlah tabel) — inilah yang membuat paginasi dan
  angka di layar tidak bisa berbeda.

**Kenapa 422, bukan filter yang diabaikan:** tanpa rujukan, "dalam jangkauan" tidak punya arti;
menjawab seluruh tabel seolah tersaring akan membuat angka di layar menipu. Fail-closed, dengan
pesan yang menyebut cara memperbaikinya.

## 4. Bukti layar (7c)

Diambil dari DOM aplikasi di :3010 (bukan tangkapan layar yang ditafsirkan).

### 4.1 Peran SPPG Head (cakupan Jakarta)

```text
catatan layer peta : "4 dari 6 pemasok dalam jangkauan 150 km dari Jakarta ·
                      2 di luar jangkauan tidak dipasang di peta"
tombol layer       : "Tampilkan pemasok (4)"
legenda            : Pemasok · Keandalan rendah · Dikecualikan · Di luar jangkauan
pin setelah dinyalakan: 4 — Telur Berkah Bekasi, Telur Berkah Bogor,
                        Telur Berkah Cianjur, Telur Berkah Jakarta
                        (pin "di luar jangkauan": 0)
```

Sebelum Fase 7, tampilan ini memasang **10 pin telur lintas pulau** (Medan … Malang) untuk SPPG
Jakarta. Sekarang 4, dan sisanya dijelaskan — bukan hilang tanpa keterangan.

Halaman Pemasok (peran yang sama):

```text
judul kolom : Pemasok | Hub | Komoditas | Keandalan | Sertifikasi | Koordinat | JARAK | Status
catatan     : "22 dari 35 pemasok dalam jangkauan 150 km dari Jakarta"
baris       : 35 (semua pemasok tetap tampil, jauh punya label)
label jauh  : "di luar jangkauan (665 km)" (Telur Berkah Surabaya),
              "(1419 km)" (Telur Berkah Medan), "(426 km)" (Semarang)
contoh baris: Telur Berkah Surabaya | Surabaya | telur | 35% | Tidak bersertifikat |
              -7,2395 / 112,7731 | 665 km | Aktif · di luar jangkauan (665 km)
tombol      : "Hanya dalam jangkauan (22)"
catatan tombol: "Menyembunyikan 13 pemasok yang jaraknya di atas 150 km dari Jakarta.
                Baris yang disembunyikan bukan dihapus — matikan penyaring untuk melihatnya lagi."
sesudah diklik: 22 baris (0 label "di luar jangkauan"); diklik lagi → 35 baris
```

### 4.2 Peran BGN Monitor (nasional, tanpa ambang)

```text
catatan layer peta : "6 pemasok ditampilkan (nasional, tanpa ambang jarak)"
tombol layer       : "Tampilkan pemasok (6)"   ← 6 = SEMUA pemasok telur se-Indonesia
halaman Pemasok    : 35 baris; kolom JARAK berisi "—" (server tidak melaporkan rujukan)
catatan tabel      : "35 pemasok ditampilkan (semua, tanpa ambang jarak) · 35 tanpa jarak"
penyaring jangkauan: tidak ada (tanpa rujukan tidak ada yang bisa disaring)
ringkasan          : "Pemasok terdaftar = 35" (tanpa baris "Di luar jangkauan")
```

Jadi aturan "terjangkau" **tidak** mengurangi pandangan nasional monitor: 6 vs 4 pin, 35 vs 35
baris, dan angka 150 km tidak pernah muncul di layar monitor.

## 5. Aturan yang dipegang (dan diuji)

1. **Jarak dihitung server, sekali.** `app/core/geo.py::haversine_km` dipakai seeder dan endpoint;
   UI hanya membandingkan `distance_km` dengan ambang. Tidak ada dua rumus yang bisa berbeda.
2. **Penyaringan bukan penyembunyian.** Peta menyebut berapa yang tidak dipasang (angkanya dari
   `reach.excluded_out_of_reach` server); halaman Pemasok menampilkan semua baris dengan label
   "di luar jangkauan (N km)" dan penyaring yang bisa dimatikan.
3. **Jarak tak diketahui ≠ dekat.** Baris tanpa koordinat dikeluarkan saat penyaringan aktif dan
   dihitung terpisah (`excluded_unknown_distance`), di API maupun di UI (`withinReachKm`).
4. **Relevansi, bukan scope.** Ruling 2026-10-14 §4 tidak berubah: semua peran tetap boleh membaca
   pemasok lintas lokasi; yang berubah hanya apa yang ditonjolkan untuk peran SPPG.
5. **Filter komoditas ikut ke server** supaya angka "N di luar jangkauan" menceritakan komoditas
   yang sedang dilihat, bukan komoditas lain.

## 6. Belum beres (jujur)

- **Fase 7d belum dikerjakan**: jarak pemasok belum masuk perhitungan biaya engine (keputusan
  pemilik §7.4b — mengubah skor/keputusan demo, butuh tes jangkar baru).
- **14 pemasok kanonik tidak punya komoditas**, jadi tampilan yang difilter komoditas hanya berisi
  pemasok demo. Itu keadaan data Sprint 1, bukan efek Fase 7.
- **Kata sandi akun demo masih tertulis di `frontend/app/page.tsx`** (blok tombol demo). Sudah ada
  sebelum sesi ini; dicatat di sini supaya tidak terlupakan, belum diubah (keputusan pemilik).
- **DB demo masih mengandung residu** dari latihan/lari tes sebelumnya (jumlah keputusan jauh di
  atas 4 kasus skrip); tombol "Muat kasus demo" tetap cara membersihkannya.
