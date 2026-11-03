# Ruling 2026-10-14 — Cakupan lokasi per peran (scope) kembali ke satu SPPG

**Tanggal:** 14 Oktober 2026
**Status:** BERLAKU. Menggantikan ruling "approver lintas lokasi" (S4-05 p10, 2026-10-08).
**Pengaju:** pemilik proyek (MealChain Guardian 2.0)
**Pelaksana:** Fase 1 rencana `.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md`

---

## 1. Keputusan

| Peran | Cakupan baca | Cakupan tulis |
|---|---|---|
| `sppg_head` | **Hanya lokasinya sendiri** (`target_location_id = user.location_id`) | Membuat/menyetujui keputusan yang menyasar lokasinya sendiri |
| `sppg_nutritionist` | **Hanya lokasinya sendiri** | idem |
| `bgn_monitor` | **Seluruh lokasi** (read-only, pengawasan nasional) | Tidak boleh menulis apa pun |

**Lokasi TUJUAN (target) yang dikunci ke SPPG sendiri. Lokasi SUMBER (source) tetap lintas
daerah** — redistribusi Jakarta dari surplus Cianjur tetap sah dan tetap bisa dibuat oleh
kepala SPPG Jakarta. Yang hilang hanyalah kemampuan melihat/menyetujui keputusan milik
SPPG lain.

## 2. Kenapa

1. **Kode kembali selaras dengan dokumen yang sudah berlaku.** `docs/Architecture.md` §7
   ("Keamanan") baris 238 sudah menyatakan sejak awal: *"SPPG Head/Nutritionist hanya bisa
   lihat/approve untuk `location_id` miliknya; `bgn_monitor` read-only lintas lokasi"*.
   Yang menyimpang adalah kode (ruling 2026-10-08), bukan dokumennya.
2. **Simetri baca–tulis.** Jalur tulis sudah dikunci lokasi sendiri sejak awal
   (`_assert_target_location_allowed`, `api/decisions.py`). Jalur baca yang terbuka membuat
   aturan tidak simetris: SPPG tidak boleh *membuat* keputusan untuk lokasi lain, tetapi
   boleh *melihat dan menyetujui* keputusan lokasi lain.
3. **Data akan menjadi multi-lokasi.** Mulai Fase 4 (data s/d 5 Nov 2026) keputusan akan ada
   untuk banyak SPPG. Tanpa scope server-side, kepala SPPG Jakarta akan melihat pekerjaan
   SPPG Bandung/Surabaya — persis yang ingin dihindari.

## 3. Konsekuensi yang diterima sadar

- **Matriks AND dua verifier tetap berlaku, tetapi di dalam satu SPPG.** Keputusan yang
  menyasar SPPG X hanya bisa disetujui oleh approver dari SPPG X (kepala + ahli gizi X).
  Verifier kedua tidak lagi boleh berasal dari SPPG lain.
- **Alur demo lama "approve ganda lintas lokasi" tidak berlaku lagi** (dulu tercatat di
  TODO.md S4-05: "approve ganda lintas lokasi via UI, 2 rows DB"). Demo disesuaikan:
  satu keputusan disetujui oleh dua approver SPPG yang sama.
- **Uji yang masih menegaskan bacaan lintas lokasi wajib diubah sadar** — teridentifikasi:
  `backend/tests/test_s4_rulings_tdd.py` (ruling lama), plus tes ringkasan keputusan yang
  memakai approver dari lokasi lain sebagai fixture. Perubahan tes dicatat per berkas di
  laporan Fase 1 (bukan dihapus diam-diam).
- **Bila nanti perlu approver nasional**, jalannya adalah menambah peran/flag baru secara
  eksplisit (mis. `bgn_approver`), bukan membuka kembali bacaan lintas lokasi untuk
  `sppg_head`. Belum dibutuhkan sekarang.

## 4. Cakupan teknis pelaksanaan (Fase 1)

Satu helper: `backend/app/core/scope.py` (`is_national_scope`, `scope_location_id`,
`in_scope`, `assert_in_scope`, `apply_location_scope`). Pola ini menyalin yang sudah
berlaku di `GET /kpi` — tidak ada gaya scope kedua. Semua peran SPPG tanpa
`location_id` ditolak 403 (gagal-tertutup), bukan "lihat semua".

### 4.1 Dikunci (target-side)

| Endpoint | Perlakuan |
|---|---|
| `GET /decisions` | feed disaring `target_location_id = user.location_id` untuk peran SPPG |
| `GET /decisions/{id}` | 403 bila target di luar lokasi (pengecualian `VERIFIER_ROLES` 2026-10-08 **dicabut**) |
| `GET /decisions/{id}/approval-summary` | idem |
| `GET /decisions/{id}/traces`, `/chain`, `/dossier`, `/compliance` | idem (dua yang pertama sebelumnya bahkan tanpa pemeriksaan) |
| `GET /supplier-exclusions/context/{id}` | idem |
| `GET /balance/map` | peran SPPG menerima satu titik (lokasinya sendiri) |
| `GET /supply/{loc}/{com}`, `/demand/{loc}/{com}`, `/demand/forecast/{loc}/{com}`, `/price/{loc}/{com}`, `/price/quotes/{loc}/{com}` | 403 bila `{loc}` bukan lokasi sendiri |
| `GET /supplier-exclusions` | perannya hanya melihat eksklusi ber-`scope_location_id` sendiri; parameter `scope_location_id` asing → 403 (bukan diabaikan) |
| `POST /events/price-anomaly`, `POST /events/safety-disruption` | `target_location_id` wajib lokasi sendiri (menutup celah O-SEC-2 yang dicatat audit 2026-10-11) |
| `GET /kpi` | **sudah** sesuai sejak awal — dipakai sebagai acuan pola, tidak diubah |

### 4.2 Sengaja TIDAK dikunci (sisi sumber / bukan data bisnis)

| Endpoint | Alasan |
|---|---|
| `GET /batches` | batch = data sisi SUMBER (lokasi asal pasokan), bukan target SPPG. Dikuncikan akan mengosongkan panel chaos karena **tidak ada satu pun batch di lokasi SPPG demo (Jakarta)** — keenam batch seed ada di Cianjur/Bogor/Bandung/Palembang/Semarang/Surabaya |
| `GET /suppliers` (Fase 2, 2026-10-14) | daftar + profil pemasok juga data sisi SUMBER: nama, koordinat, kapasitas, sertifikasi tidak dikunci per lokasi. Yang lokal-cakupan adalah **eksklusi**, dan itu dibawa per baris (`excluded_scope_locations`) alih-alih menyembunyikan pemasok di luar cakupan |
| `POST /events/safety-disruption` — batch pemicu | batch boleh dari lokasi mana pun; yang dikunci adalah **tujuan** keputusannya. Terbukti oleh `tests/test_event3_api.py`: batch Cianjur + target Jakarta → 201 |
| `POST /cost/*`, `/logistics/*`, `/freshness/evaluate`, `/safety/evaluate`, `/price/deviation` | komputasi murni dari payload — tidak membaca baris milik SPPG lain (tidak ada data yang bocor) |
| `GET /ledger/verify` | pemeriksaan integritas rantai audit nasional (read-only, hash + status) |
| `/admin/*` | **sudah** `bgn_monitor`-only lewat `require_roles`; peran SPPG sudah 403 sebelum ruling ini |

### 4.3 Konsekuensi UI yang ikut disesuaikan

- `ChaosPanel` dulu mengirim **lokasi batch** sebagai `target_location_id`; itu keliru secara
  semantik dan akan dibalas 403 untuk batch luar. Sekarang mengirim lokasi SPPG pemakai
  (dari `/auth/me`), dan menampilkan keterangan tujuan keputusan. Logika murninya di
  `frontend/lib/chaos-scope.ts` (ada tes sendiri).
- Pemilih lokasi di `OpsConsole` dan `Event2Panel` **dikunci** untuk peran SPPG (dulu bebas
  memilih 5 kota → jadi 403). Hanya `bgn_monitor` yang bebas memilih, dengan keterangan
  cakupan di bawah kontrol.
- Kop peta Overview menyesuaikan: satu lokasi ditulis "Peta SPPG Anda", bukan "Peta 1 lokasi SPPG".

## 5. Verifikasi yang disyaratkan

1. `backend/tests/test_scope_matrix.py` (baru): matriks peran × endpoint → count terlihat + 403
   untuk lokasi asing; `backend/tests/test_scope_core.py` (baru): aturan helper tanpa DB.
2. Uji manual 3 akun demo terhadap ≥10 endpoint, tabel *expected vs actual* di laporan.
3. Bukti bahwa kepala SPPG Jakarta **tidak** bisa membaca keputusan SPPG lain (403) dan
   tidak melihatnya di feed (count cocok dengan `count(*) ... WHERE target_location_id = Jakarta`).
4. `pytest` (backend) + `vitest`/`tsc`/`lint` (frontend) hijau; perubahan tes lama
   didaftarkan satu per satu beserta alasannya.

## 6. Status pelaksanaan — Fase 1 SELESAI (2026-10-14)

Implementasi: `app/core/scope.py` + penerapan di `api/decisions.py`, `balance.py`, `supply.py`,
`demand.py`, `price.py`, `supplier_exclusions.py`, `events.py`, `dossier.py`.

**Tes lama yang diubah sadar** (semuanya karena mengunci bacaan lintas lokasi; tidak ada yang
dihapus):

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests/test_s4_rulings_tdd.py` | 2 tes ruling 2026-10-08 dibalik menjadi 403 (200 → 403) + 1 tes positif baru | ruling lama dicabut |
| `tests/test_s4_sec_guards.py` | `test_sppg_foreign_decision_detail_read_allowed_by_ruling` → ekspektasi 403 | idem |
| `tests/test_approval_summary.py` | `..._verifier_lintas_lokasi_200_ruling_a` → 403; baris tanpa lokasi dibaca `bgn_monitor` + pin 403 untuk kepala; +1 tes positif | idem |
| `tests/test_compliance.py` | baca compliance lintas SPPG → 403 | idem |
| `tests/test_event2_api.py` | target event = Jakarta (SPPG kepala demo), quote tetap di lokasi uji terisolasi (sisi sumber) | target wajib lokasi sendiri |
| `tests/test_balance_map.py` | tes "semua 10 lokasi" pindah ke `bgn_monitor`; +1 tes "kepala 1 titik" | peta ikut tercakup |
| `tests/test_sprint1_acceptance.py` | nilai lintas lokasi (Cianjur/Bogor) dibaca sebagai bgn_monitor (`national_client` / header per-permintaan); endpoint mutasi tetap peran approver | idem |
| `tests/conftest.py` | fixture baru `monitor_headers` (bgn_monitor tanpa lokasi) + `far_nutritionist_headers` (ahli gizi di Bogor, dibuat sendiri) | peran yang sah membaca nasional; tes aturan tidak boleh bergantung pada lokasi akun demo |
| `tests/test_demo_users.py` | pin lokasi ahli gizi demo: Bogor → Jakarta | keputusan di bawah (satu SPPG untuk matriks AND) |
| `app/seed/seed_data.py` | `DEMO_USERS` ahli gizi demo pindah ke Jakarta | idem |

### 6.1 Keputusan yang diambil: ahli gizi demo ikut ke Jakarta

`DEMO_USERS` menempatkan `sppg.nutritionist@demo.local` di **Bogor**, sedangkan seluruh
keputusan seed menyasar Jakarta. Setelah ruling, akun itu membuka feed **kosong** — dan yang
lebih penting, matriks AND dua approver tidak bisa didemokan sama sekali, karena jalur tulis
pun sudah terkunci lokasi (`app/api/actions.py` memakai
`exclusions.require_scope(user, decision.target_location_id)` di approve/execute, dan
evaluasi matriks hanya menghitung approval dari `u.location_id == decision.target_location_id`).

**Diputuskan: akun demo ahli gizi dipindah ke Jakarta** (satu SPPG dengan kepala demo), bukan
menunggu data Bogor di Fase 4. Alasannya: (a) matriks AND memang berlaku di dalam satu SPPG —
itu isi ruling ini, jadi akun demo harus mencerminkan aturan yang berlaku; (b) kasus demo
`supplier-janggal`/`gangguan-logistik` yang butuh approval kedua jadi bisa ditunjukkan hari
ini; (c) `bgn_monitor` tetap memberi sudut pandang nasional untuk kontras "SPPG vs nasional".

Yang dijaga agar tidak menipu: **uji aturan scope tidak boleh bergantung pada lokasi akun
demo**. Karena itu `tests/conftest.py` menyediakan `far_nutritionist_headers` (ahli gizi di
Bogor, dibuat dan dibersihkan per sesi tes), dan dua tes 403 bicara memakai fixture itu —
bukan akun demo. Kalau nanti akun demo dipindah lagi, tes aturan tetap sahih.

**Sisa untuk Fase 2/4:** SPPG lain (Bogor, Bandung, Surabaya, …) belum punya akun demo
maupun keputusan sendiri. Kalau demo ingin memperlihatkan "SPPG lain tidak bisa lihat", itu
disiapkan sebagai data Fase 4 (keputusan per lokasi), bukan dengan membuka kembali cakupan.
