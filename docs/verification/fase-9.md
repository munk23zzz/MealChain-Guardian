# Fase 9 — pemasok: profil kanonik dari data nyata & penanda "sedang mengirim"

Tanggal: 2026-10-16. Permintaan pemilik (verbatim):

> "untuk db suplier anda cek laagi apakah sudah benar, jika belum perbaiki dan
> tambahkan juga suplier yang lagi mengirim barang nanti mau saya tampilkan di map
> dimana ada"

Dua keputusan yang dikunci lewat tanya-jawab sebelum kode disentuh:

1. **"Sedang mengirim"** = pemasok yang punya batch kiriman dengan
   `usable_until >= sekarang` (masih layak hari ini). Kiriman kedaluwarsa bukan
   kiriman aktif — itu temuan mutu.
2. **Profil pemasok kanonik** diisi HANYA dari yang bisa diturunkan dari data
   yang sudah ada: `commodity` + `certification_status` dari batch kiriman
   mereka. `capacity_kg_per_week` dibiarkan kosong karena tidak ada satu pun
   sumbernya.

## 1. Audit sebelum perubahan (kenapa "belum benar")

| Temuan | Angka |
|---|---|
| Pemasok total | 35 (21 demo + 14 kanonik) |
| Kanonik tanpa `commodity_id`/`certification_status`/`capacity_kg_per_week` | **14 dari 14** |
| Kanonik yang benar-benar dipakai batch | **3** (`Supplier A`, `B`, `C` Cianjur) |
| Kanonik tanpa batch sama sekali | 11 (`Supplier Medan-1`, `Jakarta-1`, …) |
| Baris `batches` | 6 (A→Bogor 500 kg, A→Cianjur 500 kg, A→Bandung 400 kg, B→Surabaya 600 kg *fail*, B→Semarang 200 kg, C→Palembang 250 kg) |
| Duplikat nama / koordinat kembar / koordinat di luar Indonesia | 0 / 0 / 0 |
| Referensi `batches.supplier_id` yang menggantung | 0 |
| `alembic_version` vs head repo | 013 = head (tidak ada drift migrasi) |

Akibat temuan itu di layar: baris kanonik tampil dengan Komoditas/Sertifikasi
kosong di tab Pemasok dan tidak bisa ikut tersaring per komoditas di peta.

## 2. Perubahan

**Backend**

| Berkas | Isi |
|---|---|
| `backend/app/seed/supplier_profile.py` (BARU) | Modul murni `derive_supplier_profiles()`: komoditas = total `quantity_kg` terbesar (seri → batch terbaru; masih seri → `None`), sertifikasi = nilai terbanyak (seri → `None`), kapasitas TIDAK diturunkan |
| `backend/app/seed/seed_data.py` | Baris supplier memuat hasil turunan; saat memuat ke DB profil **hanya diisi bila masih kosong** (`suppliers_commodity_filled` / `suppliers_certification_filled`) — nilai yang sudah ada tidak pernah ditimpa |
| `backend/app/core/supplier_shipping.py` (BARU) | Modul murni `shipping_summary()` + `shipping_for()`: hanya batch `usable_until >= now`; melaporkan `count`, `total_kg`, `until`, `commodities`, `safety_fail_count` |
| `backend/app/api/suppliers.py` | `GET /suppliers` menambah kunci `shipping` per baris (null bila tidak sedang mengirim) |
| `backend/scripts/verifikasi_pemasok_kirim.py` (BARU) | Bukti jalur nyata: login akun demo → API vs SQL per pemasok pengirim + rekap profil |

**Frontend**

| Berkas | Isi |
|---|---|
| `frontend/lib/supplier-pins.ts` | `shipping` pada baris pin, `supplierShipping()`, `shippingLabel()`, kelas tambahan `map-pin-supplier-shipping`, baris popup + aria-label "sedang mengirim N kiriman", hitungan `supplierLayerSummary().shipping`, legenda "Sedang mengirim" |
| `frontend/lib/suppliers-board.ts` | Baris tabel membawa `shipping` + `shippingLabel`; `directoryMetrics().shipping` |
| `frontend/components/SupplierBoard.tsx` | Kartu "Sedang mengirim barang: N dari M" + kolom Status menampilkan kalimat kiriman (bukan lagi hanya "Aktif") |
| `frontend/app/globals.css` | `.shipping-tag` (token ok), cincin pin `.map-pin-supplier-shipping`, bentuk legenda `.map-legend-box-shape-shipping` |

Cincin sengaja TAMBAHAN, bukan nada kelima: warna pin tetap berarti
keandalan/jangkauan, cincin berarti kiriman berjalan — dua fakta berbeda, dua
kanal. Semua warna memakai token (`--status-safe`, `--ok-*`), tanpa hex mentah.

## 3. Hasil di DB (seeder dijalankan dengan REF kanonik `2026-10-08T12:00:00+00:00`)

```
Seed selesai (idempoten). Row baru: {'suppliers_commodity_filled': 3,
                                     'suppliers_certification_filled': 3}
```

Tidak ada baris baru selain pengisian itu. Pengukuran sebelum/sesudah identik
untuk seluruh tabel lain — jadi perbaikan profil tidak menyentuh data operasional:

| Metrik | Sebelum | Sesudah |
|---|---|---|
| `batches` (jumlah / total kg) | 6 / 2450,00 | 6 / 2450,00 |
| `supply_records` (jumlah / total kg) | 2220 / 741663,62 | 2220 / 741663,62 |
| `price_signals` (jumlah / total harga) | 2318 / 68649282,95 | 2318 / 68649282,95 |
| `decisions` | 165 | 165 |
| `users` | 1141 | 1141 |
| `suppliers` dengan komoditas | 21 | **24** |

Profil lengkap sekarang: **24/35** komoditas, **24/35** sertifikasi, **21/35**
kapasitas (hanya baris demo — kanonik sengaja kosong), kanonik terisi **3/14**.

## 4. Bukti jalur nyata (API vs SQL)

`docker compose exec -e PYTHONPATH=/app backend python scripts/verifikasi_pemasok_kirim.py` → exit 0:

```
pemasok dikembalikan API : 35 dari 35
rujukan jarak            : {'location': 'Jakarta', ...}
pemasok dengan kiriman   : 2 (SQL: 2)

  Supplier A Cianjur: 3 kiriman · 1400.0 kg · s/d 2026-11-02 · komoditas telur
  Supplier B Cianjur: 1 kiriman · 600.0 kg · s/d 2026-10-26 · komoditas telur · 1 GAGAL UJI (dilaporkan apa adanya)

profil pemasok: 24/35 punya komoditas, 24/35 punya sertifikasi,
21/35 punya kapasitas (sengaja kosong: tanpa sumber), kanonik terisi 3/14

API == SQL untuk semua pemasok yang mengirim. Bukti lulus.
```

## 5. Bukti layar (konsol :3010, akun demo "SPPG Head" lewat tombol akun demo aplikasi)

- **Peta (Overview, layer pemasok dinyalakan):** 7 pin, **2 di antaranya** berkelas
  `map-pin-supplier-shipping`:
  `Supplier A Cianjur — pemasok telur, keandalan 92%, hub Cianjur, dalam jangkauan (78,3 km), sedang mengirim 3 kiriman`
  dan `Supplier B Cianjur — … 77,1 km, sedang mengirim 1 kiriman`. 5 pin lain
  tanpa cincin (`Supplier C Cianjur`, `Telur Berkah Bekasi/Bogor/Cianjur/Jakarta`).
- **Legenda peta** memuat entri baru "Sedang mengirim" (bentuk cincin) di samping
  Pemasok / Keandalan rendah / Dikecualikan / Di luar jangkauan.
- **Tab Pemasok (35 baris):** kartu ringkasan "Sedang mengirim barang **2 dari 35**";
  dua baris Status berisi kalimat kiriman:
  `Sedang mengirim · 1 kiriman · 600 kg · s/d 26 Okt 2026 · 1 gagal uji` (Supplier B Cianjur)
  dan `Sedang mengirim · 3 kiriman · 1.400 kg · s/d 2 Nov 2026` (Supplier A Cianjur).
  *(Angka ini keadaan saat Fase 9 ditulis. Fase 10 menambah kiriman Jakarta sehingga A
  menjadi 4 kiriman/2.200 kg, dan REF kanonik saat seeder F10 dijalankan menggeser tanggal
  B→Surabaya ke 1 Nov 2026 — lihat catatan di akhir dokumen ini.)*
  Baris kanonik itu juga kini menampilkan `telur` + `HACCP` — bukti profil yang
  terisi benar-benar sampai ke layar.
- 11 kanonik tanpa batch tetap menampilkan `—` (tidak dikarang).

## 6. Gerbang

| Gerbang | Hasil |
|---|---|
| `pytest` (kontainer backend) | **806 lulus / 3 skip** (sebelumnya 782; +24) |
| `ruff check .` | bersih |
| `vitest run` | **552 lulus / 60 berkas** (sebelumnya 545; +7) |
| `tsc --noEmit` | 0 |
| `next lint` | 0 |
| `next build` | TIDAK dijalankan (aturan repo: jangan build saat `next dev` hidup) |

Tes lama yang angkanya **sadar berubah** karena data berubah: filter
`commodity=telur` 6 → **9** (A/B/C Cianjur kini ikut), dan
`test_supplier_without_profile_reports_null_not_zero` dipisah menjadi "yang
punya batch terisi" vs "yang tidak punya batch tetap kosong".

## 7. Batas jujur

1. `capacity_kg_per_week` kanonik **tetap kosong** — tidak ada sumber datanya.
   Tidak dikarang demi kolom yang rapi.
2. 11 pemasok kanonik tanpa batch tetap tanpa komoditas/sertifikasi. Kalau mau
   terisi, harus ada batch atau keputusan pemilik yang menyebut angkanya.
3. Kiriman kanonik **tidak ditambah** baru — definisi "sedang mengirim" memakai
   batch yang sudah ada, jadi hanya 2 pemasok. Kalau demo butuh lebih banyak
   pengirim aktif, itu keputusan data baru (angka kg + tujuan harus dari pemilik).
4. `Supplier B Cianjur` sedang mengirim batch yang status keamanannya `fail`.
   Itu fakta DB dan dilaporkan apa adanya (`safety_fail_count`), bukan
   disembunyikan — tapi kalau narasi juri ingin "pengirim bersih", batch ini
   yang harus dibicarakan dulu.
5. Residu uji di DB demo masih ada (suite menulis ke DB yang sama; lihat Fase 6)
   → hitungan `users`/`decisions` naik setiap kali suite dijalankan.

---

## Catatan pasca-Fase 10 (2026-10-16) — angka yang bergeser

Dokumen ini merekam keadaan **saat Fase 9 selesai** dan tidak diubah agar tetap bisa dibaca
sebagai bukti historis. Fase 10 (`docs/verification/fase-10.md`) mengubah dua hal yang
bersinggungan dengan angka di atas:

1. **Kiriman demo baru** A Cianjur → SPPG Jakarta ditambahkan atas permintaan pemilik (angka
   dari pemilik). Akibatnya pemasok A Cianjur: **3 → 4 kiriman**, **1.400 → 2.200 kg**; total
   `batches` **6 → 7**, total kg **2.450 → 3.250** (baris pengukuran §"sebelum/sesudah" di atas
   tetap benar sebagai pengukuran saat itu). Jumlah **pengirim aktif tidak berubah (2 pemasok)**.
2. **Satu tanggal batch ternormalkan.** Seeder Fase 10 dijalankan dengan REF kanonik
   (`2026-10-08T12:00:00+00:00`), sehingga batch B→Surabaya yang tadinya `26 Okt 2026` menjadi
   **1 Nov 2026**; kalimat Status di tabel Pemasok karena itu terbaca `s/d 1 Nov 2026`. Status
   keamanannya tetap `fail` dan tetap dilaporkan (`safety_fail_count`).

Tes yang ekspektasinya ikut diselaraskan secara sadar (bukan aturan produksi yang dilonggarkan):
`test_shipping_matches_sql_for_active_supplier`, `test_approval_summary_canonical_fields`, dan
`test_approval_summary_or_complete_then_execute_parity[missing]` — alasan tiap perubahan ditulis
di komentar berkas tes masing-masing, ringkasannya di `docs/verification/fase-10.md` §6.
