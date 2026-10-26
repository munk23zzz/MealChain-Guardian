# Verifikasi Fase 6 — cakupan peran, pemasok di peta, rentang data demo

> **Snapshot tahun 2026 (tanggal tidak tertulis)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Tanggal: 2026-10-15
Rencana: `.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md` (Fase 6)
Lingkungan: Docker Compose lokal — `mealchain-postgres` (:15432), `mealchain-backend` (:8000),
`mealchain-mock-sap` (:8001), `mealchain-frontend` (:3010); migrasi head
`013_origin_generated_at`; DB demo dalam keadaan pulih (snapshot kanonik 144 baris + 5.054 baris demo).

Tujuan dokumen ini: satu tempat yang memuat **bukti** bahwa Fase 1–5 benar-benar bekerja pada
aplikasi yang hidup, dan **catatan jujur** tentang hal yang belum beres. Semua angka di bawah
diambil dari keluaran alat, bukan dari perkiraan.

## 1. Gerbang otomatis

| Gerbang | Perintah | Hasil |
|---|---|---|
| Backend tes | `docker compose exec backend pytest -q` | **757 lulus, 3 skip, 0 gagal** |
| Backend lint | `docker compose exec backend ruff check .` | **All checks passed!** |
| Frontend tes | `docker compose exec frontend npx vitest run` | **518 lulus / 58 berkas** |
| Frontend tipe | `npx tsc --noEmit` | **exit 0** |
| Frontend lint | `npx next lint` | **exit 0** |
| Frontend build | `npx next build` | **exit 0** |

> **Peringatan prosedur:** menjalankan `next build` di kontainer frontend **saat `next dev`
> masih hidup** menimpa isi `.next` sehingga chunk dijawab `404` dan halaman yang sudah terbuka
> kehilangan hidrasi (form login terisi tetapi tombol tidak bereaksi). Sesudah `next build`,
> jalankan `docker compose restart frontend` sebelum memakai aplikasi lagi. Pada verifikasi ini,
> gejalanya muncul dan hilang setelah restart — lihat §4.2.

## 2. Matriks 3 peran × endpoint × angka DB

Skrip baru: **`backend/scripts/verifikasi_fase6.py`** (312 baris). Ia masuk sebagai tiga akun
demo (kata sandi dibaca dari `app.seed.seed_data.DEMO_USERS`, tidak pernah dicetak), memanggil
setiap endpoint penting dengan token peran masing-masing, lalu membandingkan angka yang
dikembalikan API dengan **SQL langsung ke database yang sama**. Keluar dengan kode `≠0` bila ada
satu saja yang tidak sesuai — jadi bisa dipakai sebagai gerbang, bukan sekadar cetakan.

```bash
docker compose exec backend python scripts/verifikasi_fase6.py
```

Peran & cakupan (kutipan keluaran nyata; kolom ANGKA = angka yang dicatat skrip):

```text
PERAN             ENDPOINT                                      HARAP DAPAT ANGKA                        COCOK
sppg_head         GET /decisions                                  200   200 156                          ya
bgn_monitor       GET /decisions                                  200   200 156                          ya
sppg_head         GET /balance/map?commodity=telur                200   200 1                            ya
bgn_monitor       GET /balance/map?commodity=telur                200   200 4900.0                       ya
sppg_head         GET /supply/Jakarta/telur                       200   200 300.0                        ya
sppg_head         GET /supply/Cianjur/telur                       403   403 lokasi di cakupan lokasi di  ya
sppg_nutritionist GET /supply/Cianjur/telur                       403   403 lokasi di cakupan lokasi di  ya
bgn_monitor       GET /supply/Cianjur/telur                       200   200 1400.0                       ya
sppg_head         GET /suppliers                                  200   200 44                           ya
bgn_monitor       GET /admin/users                                200   200                              ya
sppg_head         GET /admin/users                                403   403 role tidak diizinkan         ya
sppg_head         GET /demo/data-status                           200   200 5054                         ya
bgn_monitor       GET /demo/data-status                           403   403 role tidak diizinkan         ya
bgn_monitor       POST /demo/timeseries/purge                     403   403 role tidak diizinkan         ya
-                 GET /decisions                                  401   401 butuh Bearer token           ya
-                 GET /health                                     200   200                              ya
```

Angka API vs SQL langsung:

```text
YANG DIUKUR                               API           DB    SELISIH  COCOK
jumlah pemasok                           44.0         44.0        0.0  ya
baris deret waktu demo                 5054.0       5054.0        0.0  ya
total pasokan telur (kg)               4900.0       4900.0        0.0  ya
Cianjur telur (kg)                     1400.0       1400.0        0.0  ya
jumlah keputusan (monitor)              156.0        156.0        0.0  ya

Jangkar kanonik (4.900 kg total telur, Cianjur 1.400 kg): UTUH
HASIL: SEMUA COCOK
```

Yang dibuktikan: penolakan cakupan dijawab `403` (bukan daftar kosong) untuk ketiga endpoint
lintas-lokasi; `bgn_monitor` read-only di seluruh `/demo/*`; endpoint tanpa token `401`; dan
angka yang tampil di panel berasal dari DB yang sama (bukan hitungan frontend).

Catatan apa adanya: **seluruh 156 keputusan menyasar Jakarta**, jadi penyaringan cakupan
`/decisions` tidak bisa dibedakan lewat jumlah pada DB ini — yang membuktikannya adalah
`/supply/Cianjur/telur` (`403` vs `200`) dan `/balance/map` (1 lokasi vs 10 lokasi). Kasus
lintas-lokasi untuk `/decisions` diuji di suite backend dengan data uji sendiri.

## 3. Latihan demo (enam ketukan, dijalankan betulan)

| # | Ketukan | Bukti |
|---|---|---|
| 1 | Masuk sebagai **SPPG Head** lewat tombol akun demo | 11 tab tampil; notifikasi `Notifikasi: 12 keputusan menunggu tindakan`; cakupan lokasi terkunci Jakarta |
| 2 | Feed rekomendasi | `12 perlu tindakan` · `156 total rekomendasi`; chip status: 11 menunggu persetujuan, 1 ditandai verifier, 139 diusulkan, 5 ditolak; pencarian per-ID keputusan bekerja |
| 3 | Klik kartu → tab **Decision & Evidence** | tetap di konsol (bukan halaman baru); kartu kasus `safety_disruption` menampilkan badge `PENDING APPROVAL` + `berlaku 7184 dtk` |
| 4 | **Setujui → eksekusi** kasus `safety_disruption` (Bogor → Jakarta, telur 780 kg) | Modal memuat ringkasan dari server: supplier `Supplier A Cianjur` (keandalan 0,92), material `MAT-TELUR`, total `Rp14.787.096`, safety batch `pass`, verdict verifier `consistent`, requirement `1 approval — sppg_head + sppg_nutritionist`, target eksekusi `MOCK`. `Setuju` (`POST /actions/approve` → 200) menulis baris `approvals` (approver SPPG Head, `2026-10-15 06:32:26 UTC`), baris "⛔ approval belum memenuhi requirement" hilang dan tombol `Eksekusi` aktif; `POST /actions/execute` → 200; status keputusan `executed`; **ledger 2.197 → 2.198 blok** (`valid:true`, head baru) |
| 5 | Peta + layer pemasok | `Tampilkan pemasok (10)` → 10 pin `telur`: Bandung, Bogor, Cianjur, Jakarta, Malang, Medan, Palembang, Semarang, Surabaya, Yogyakarta (2 di antaranya `map-pin-supplier-low`: Cianjur 38%, Surabaya 35%); legenda "Pemasok · Keandalan rendah · Dikecualikan" |
| 6 | Demo Control — panel "Data & rentang waktu" | pratinjau default `66 hari: 2.190 pasokan · 2.274 harga · 660 rencana menu`; rentang 1–30 Sep → `1.740 / 1.810 / 300`; "Bersihkan data demo" (2 langkah) → `Dihapus 5.054 baris demo`; "Pulihkan" → `2.190 / 2.274 / 590` (bukti Fase 5, diulang hari ini) |

Tidak ditekan dan sengaja: tombol **"Segarkan ke hari ini"**. Seeder memindahkan jangkar snapshot
kanonik (8 Okt 12.00 UTC) dan akan menggeser angka yang dipaku banyak tes; perilakunya sudah
diuji lewat `test_refresh_hari_ini_bergeser_dan_bisa_dikembalikan`.

## 4. Temuan dan catatan jujur

### 4.1 Suite pytest menulis ke database demo
`docker compose exec backend pytest -q` berjalan pada DB yang sama dengan demo. Akibatnya DB
demo memuat residu uji:

- 156 keputusan, sedangkan narasi demo hanya punya **15** (11 seed kanonik + 4 kasus skrip).
  Sisanya (139 `diusulkan` + 5 `ditolak`, dan 8 dari 12 kartu "perlu tindakan" yang kedaluwarsa)
  berasal dari suite uji.
- Tabel `users` berisi **1.073 baris** untuk sesuatu yang seharusnya 3 akun demo.
- Dampak ke demo: kartu kedaluwarsa menumpuk di puncak feed (urut urgensi), dan angka
  "/decisions" tidak bisa dipertanggungjawabkan sebagai data cerita.

Usulan perbaikan (belum dikerjakan): variabel `TEST_DATABASE_URL` di `conftest.py` sehingga
suite memakai database terpisah, atau langkah bersih-bersih eksplisit sesudah suite.

### 4.2 `next build` mengganggu `next dev` yang hidup
Gejala: halaman `/` kembali `200`, tetapi chunk `/_next/static/chunks/*.js` dijawab `404`
terlihat di log frontend; form login tidak bereaksi (React tidak ter-hidrasi —
`Object.keys(button)` tidak memuat kunci `__reactProps`). Perbaikan: `docker compose restart frontend`.
Aturan operasional: jalankan build hanya saat dev berhenti, atau restart kontainer sesudahnya.

### 4.3 Filter komoditas peta memuat pilihan yang tidak ada di DB
Filter peta/beranda menyediakan 4 komoditas (`telur`, `ayam`, `beras`, `wortel`) sedangkan DB
demo hanya punya `ayam`, `telur`, `wortel`. Memilih `beras` dijawab API `404` dan UI menampilkan
galat + "Coba lagi" — perilaku jujur yang disengaja (tidak ada angka kosong yang menyamar jadi
data), tetapi tetap perlu diselaraskan (komoditas diambil dari API, bukan di-hardcode di 4 tempat).

### 4.4 `AGENTS.md` belum diperbarui
`AGENTS.md` (berkas instruksi agent) dilindungi dan tulisan saya ke sana tidak disetujui dalam
sesi ini, jadi dua batasan berikut **belum** masuk ke berkas itu. Teks usulannya:

```text
- Cakupan per peran tidak boleh dilonggarkan tanpa ruling tertulis: peran SPPG hanya membaca
  lokasi sendiri (selain data sumber pemasok), bgn_monitor read-only lintas lokasi.
  Ringkasan + tabel: docs/ruling-2026-10-14-scope-lokasi.md, docs/design.md §2
- Suite pytest menulis ke database yang sama dengan demo. Jalankan di DB terpisah atau
  bersihkan sesudahnya — residu uji membuat angka demo menggelembung.
```

## 5. Menjalankan ulang verifikasi ini

```bash
cd /e/hackathon/HackathonAWS/mealchain-guardian
docker compose up -d
docker compose exec backend pytest -q
docker compose exec backend ruff check .
docker compose exec backend python scripts/verifikasi_fase6.py     # exit 0 = semua cocok
docker compose exec frontend sh -c "npx vitest run && npx tsc --noEmit && npx next lint"
docker compose restart frontend                                    # WAJIB bila sempat menjalankan build
```
