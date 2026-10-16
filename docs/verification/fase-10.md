# Fase 10 — garis JALUR KIRIMAN (pemasok → tujuan) mengikuti jalan

Tanggal: 2026-10-16. Permintaan pemilik (verbatim):

> "dimap ada seperti garis mengikuti jalur dari suplier ke tujuan"

Empat keputusan yang dikunci lewat tanya-jawab SEBELUM kode disentuh:

1. **Garisnya mengikuti JALAN lewat OSRM** (routing OpenStreetMap) — bukan garis
   lurus. Jarak jalan dan jarak lurus dilaporkan berdampingan supaya bedanya
   terlihat, bukan disembunyikan.
2. **Rute diambil saat seeding/sync lalu disimpan di DB** (tabel `road_routes`),
   bukan saat peta dibuka. Demo tidak boleh bergantung pada internet, hasilnya
   harus sama setiap kali, dan server OSRM demo publik tidak dibanjiri peramban
   pengunjung.
3. **Ada kiriman demo baru menuju SPPG Jakarta** supaya jalurnya terlihat di peta
   akun SPPG Jakarta: **Supplier A Cianjur → SPPG Jakarta, telur, 800 kg, layak
   s/d 7 Nov 2026, status keamanan `pass`** (angka dan tanggal disebut pemilik).
4. **Cincin "sedang mengirim" dari Fase 9 tetap terpisah** dari warna garis: dua
   fakta berbeda (mutu kiriman vs kiriman berjalan) tidak boleh saling menutupi.

## 1. Kenapa perlu kiriman baru (temuan sebelum perubahan)

Kiriman yang ada tidak ada satu pun yang menuju Jakarta: Bogor, Cianjur, Bandung,
Surabaya (aktif) serta Semarang, Palembang (kedaluwarsa). Akun SPPG Jakarta hanya
melihat SPPG-nya sendiri, jadi tanpa kiriman baru tidak akan ada garis yang bisa
dilihat di peta Jakarta — dan itu yang diminta pemilik.

Perhitungan tanggal: `usable_until = harvested_at + shelf_life_days × freshness_score`
(mesin seed yang sudah ada). Dengan REF kanonik `2026-10-08T12:00:00+00:00`,
offset harvest −36 jam (7 Okt 00:00) + 35 hari × 0,90 = 31,5 hari → **7 Nov 2026
12:00** — tepat seperti yang dipilih pemilik, tanpa angka tambahan di luar mesin.

## 2. Perubahan

**Backend**

| Berkas | Isi |
|---|---|
| `backend/alembic/versions/014_road_routes.py` (BARU) | Tabel `road_routes`: kunci normalisasi UNIK, koordinat dua ujung, `distance_m`, `duration_s`, `geometry` JSONB, `source`, `fetched_at`; CHECK jarak/durasi ≥ 0 dan kosakata `source` |
| `backend/app/models/road_routes.py` (BARU) | Model `RoadRoute` (didaftarkan di `app/models/__init__.py`) |
| `backend/app/core/road_route.py` (BARU) | Murni: `route_key` (4 desimal), `osrm_url` (urutan **lon,lat** dikunci di sini), `parse_osrm_route` (ketat: menolak geometri < 2 titik, LineString salah, jarak bukan angka), `plan_route_sync` (lewati yang ada + dedup), `build_route_payloads` (jarak lurus server + jarak jalan cache + alasan jujur) |
| `backend/app/seed/road_routes.py` (BARU) | Sinkronisasi ke OSRM: hanya kiriman `usable_until >= now`, dedup per kunci, laporan gagal beralasan; jaringan mati tidak menggagalkan seeding |
| `backend/scripts/sync_road_routes.py` (BARU) | CLI: `--semua-batch`, `--reference-time`, `--timeout`, `--wajib` |
| `backend/app/seed/seed_data.py` | Kiriman baru + `sync_routes_after_seed()` dipanggil di akhir seeding (bisa dilewati `--skip-routes`) |
| `backend/app/api/supplier_routes.py` (BARU) | `GET /supplier-routes`: cakupan server (kepala SPPG = kiriman ke SPPG-nya, monitor = nasional), filter komoditas/tujuan, `reference_time`, ringkasan jujur (`with_road`/`without_road`/`dilewati_tanpa_koordinat`) |
| `backend/scripts/verifikasi_rute_jalan.py` (BARU) | Bukti jalur nyata: login akun demo → API vs SQL (cache + kiriman aktif) |

**Frontend**

| Berkas | Isi |
|---|---|
| `frontend/lib/supplier-routes.ts` (BARU) | Murni: penguraian toleran, kelas garis (`ship-route`-*), GeoJSON hanya dari geometri yang ada, titik batas peta, label & popup, ringkasan layer, `ROUTE_LINE_COLORS` (nilai paint WebGL — dikunci tes agar sama dengan token CSS) |
| `frontend/lib/hooks/useSupplierRoutes.ts` (BARU) + `lib/api.ts` + `lib/query.ts` | Query React Query + `fetchSupplierRoutes` + kunci query |
| `frontend/lib/hooks/...`/`next.config.js` | Rewrite proxy `/supplier-routes` (kontrak tes repo sendiri yang menuntut ini) |
| `frontend/components/SupplyMap.tsx` | Source/layer MapLibre (garis putus-putus), warna per mutu kiriman, popup klik, sakelar "Tampilkan/Sembunyikan jalur kiriman (N)" (aktif bawaan), legenda, dan pembukaan tampilan SEKALI saat jalur pertama tiba |
| `frontend/app/page.tsx` | Query jalur untuk peta (ikut komoditas yang dilihat) + prop `supplierRoutes` |
| `frontend/app/globals.css` | `.map-layer-controls` (wadah kontrol agar tidak menumpuk), contoh garis legenda/popup, gaya baris popup |

Catatan penamaan: kelas DOM memakai prefiks **`ship-route`**, bukan `route-line`
— `route-line` sudah milik signature halaman login (`.brand-route .route-line`,
dikunci `tests/login.test.tsx`).

## 3. Angka nyata dari OSRM (tersimpan di cache)

```text
driving:-6.8540,107.1306>-6.2088,106.8456 → Jakarta   110.434 m  5.060 s  36 titik
driving:-6.8540,107.1306>-6.5950,106.8166 → Bogor      62.788 m  2.960 s  50 titik
driving:-6.8540,107.1306>-6.9175,107.6191 → Bandung    67.854 m  3.130 s  38 titik
driving:-6.8540,107.1306>-6.8420,107.1426 → Cianjur     3.232 m    211 s  34 titik
driving:-6.8420,107.1306>-7.2575,112.7521 → Surabaya  730.790 m 32.464 s  54 titik
```

Cianjur → Jakarta: **110,4 km jalan vs 78,35 km lurus = 1,41×**. Itu justru isi
pesannya: jalur jalan berkelok, bukan garis lurus. Geometri disimpan
`overview=simplified` (36 titik / 1,5 KB per rute) — cukup halus untuk digambar,
jauh lebih ringan daripada `full` (3.083 titik / 71 KB).

## 4. Bukti jalur nyata (API vs SQL)

`docker compose exec -e PYTHONPATH=/app backend python scripts/verifikasi_rute_jalan.py` → exit 0:

```
rute di cache DB      : 5
kiriman aktif (SQL)   : 5
kepala SPPG Jakarta   : 1 jalur (cakupan lokasi user = Jakarta)
bgn_monitor (nasional): 5 jalur, 5 punya jalur jalan

  Supplier A Cianjur -> Jakarta: lurus 78.35 km | jalan 110.4 km (± 84 menit, osrm, 36 titik)

Cakupan, geometri, dan jarak jalan konsisten dengan DB. Bukti lulus.
```

Yang diperiksa skrip: cakupan per peran, geometri API persis baris cache (jumlah
titik + jarak), **jarak jalan tidak pernah lebih pendek dari jarak lurus**
(kalau terbalik → GAGAL), dan setiap kiriman aktif menurut SQL ada di API.

## 5. Bukti layar (konsol :3010, akun demo "SPPG Head")

- Sakelar: **"Sembunyikan jalur kiriman (1)"**, `aria-pressed="true"` (aktif bawaan).
- Catatan: "1 jalur kiriman · semua lewat jalur jalan — jalur jalan dari OSRM
  (diambil saat sinkronisasi, bukan saat peta dibuka)."
- Legenda: "Jalur kiriman (jalan)" dan "Jalur kiriman gagal uji" (contoh garis,
  bukan kotak).
- Peta: garis putus-putus terlihat dari Jakarta menurun ke arah Cianjur; tampilan
  peta ikut membuka kedua ujung kiriman (sebelum ini pin Cianjur berada di luar
  bingkai peta SPPG Jakarta).
- `GET /supplier-routes` lewat proxy Next menjawab **401 tanpa token** (bukan 404):
  rewrite benar, endpoint terpasang.

## 6. Gerbang

| Gerbang | Hasil |
|---|---|
| `pytest` (kontainer backend) | **851 lulus / 3 skip** (sebelum Fase 10: 806 lulus / 3 skip → **+45**: 22 murni OSRM + 9 sinkronisasi + 14 endpoint) |
| `ruff check` | bersih |
| `vitest run` | **578 lulus / 61 berkas** (sebelumnya 552/60; +26) |
| `tsc --noEmit` | 0 |
| `next lint` | 0 (tanpa peringatan) |
| `next build` | TIDAK dijalankan (aturan repo: jangan build saat `next dev` hidup) |

**Ekspektasi tes lama yang berubah SADAR karena data berubah** (bukan aturan
dilonggarkan) — semuanya diberi komentar alasannya di berkas tes:

1. `test_shipping_matches_sql_for_active_supplier`: Supplier A Cianjur 3 → **4**
   kiriman, 1.400 → **2.200 kg** (kiriman Jakarta menambah satu kiriman layak).
2. `test_approval_summary_canonical_fields`: keputusan telur Jakarta kini punya
   pemasok (**Supplier A Cianjur**) karena `resolve_binding` menyimpulkan pemasok
   dari batch sumber — dan sekarang memang ADA batch menuju Jakarta. Perilaku
   "jangan menebak pemasok" tetap diuji.
3. `test_approval_summary_or_complete_then_execute_parity[missing]`: skenario
   "pemasok tak diketahui" dipindah ke komoditas **ayam** (belum ada kiriman ke
   Jakarta), supaya penjagaannya tidak hilang bersama data lama.
4. `tests/proxy-roots.test.ts` (frontend) menuntut rewrite `/supplier-routes` —
   sudah ditambahkan di `next.config.js`; ini gunanya kontrak itu.

## 7. Batas jujur

1. **Rute bergantung pada OSRM sebagai data pihak ketiga.** Karena itu `source`
   disimpan dan ditampilkan ("jalur jalan dari OSRM"); angka jalan tidak pernah
   diklaim sebagai hitungan kita. Kalau OSRM tidak terjangkau saat sinkronisasi,
   peta menulis **"belum disinkronkan"** — bukan menggambar garis lurus yang
   menyamar sebagai rute jalan.
2. **Jalur hanya digambar untuk kiriman yang layak** (`usable_until >= sekarang`).
   Kiriman kedaluwarsa tidak dipanggil rutenya (tidak pernah digambar) sehingga
   server OSRM demo tidak dibebani tanpa hasil.
3. **Pengirim aktif masih 2 pemasok** (A dan B Cianjur). Kiriman Jakarta menambah
   jalur, bukan menambah pengirim baru.
4. **Seeding ulang menormalkan tanggal.** Menjalankan seeder dengan REF kanonik
   mengubah satu tanggal lama: B→Surabaya 26 Okt → **1 Nov 2026** (baris itu
   sebelumnya mengikuti REF lama). Fitur "sedang mengirim" tidak berubah (keduanya
   masih layak pada 16 Okt); catatan di `docs/verification/fase-9.md` sudah diberi
   keterangan silang.
5. **Batas peta berubah hanya SEKALI** saat jalur pertama tiba. Setelah itu zoom
   dan geser pengguna tidak pernah disentuh lagi (aturan lama tetap berlaku).
6. **Tabel Pemasok belum punya kolom jalur.** Data `GET /supplier-routes` sudah
   bisa dipakai untuk itu, tapi menambah kolom tabel adalah lingkup baru yang
   belum diminta pemilik.
