# Pin peta Overview menempel di koordinat saat zoom in/out

Tanggal: 2026-10-18 · Frontend · Commit: `fix(peta): pin menempel di koordinat saat zoom`

## 1. Gejala yang dilaporkan

Permintaan pemilik (verbatim): *"untuk bagian Pin pemasok tolong perbaiki dimana ketika zoom in
atau zoom out tidak tergeser anda buat di stay di posii kordinat"*.

Saat peta di-zoom in/out, pin pemasok bergeser dari koordinatnya.

## 2. Akar masalah (diukur di aplikasi hidup, bukan diduga)

`refreshPin` dan `refreshSupplierPin` menyegarkan penanda yang sudah ada dengan **menimpa seluruh
class elemen**:

```ts
el.className = `map-pin map-pin-supplier map-pin-supplier-ok`;
```

Itu menghapus kelas yang dipasang MapLibre sendiri saat marker dibuat:
`maplibregl-marker` dan `maplibregl-marker-anchor-*`. Kelas `maplibregl-marker` itulah yang membawa
`position: absolute`. Begitu hilang, `.map-pin { position: relative }` menang, penanda masuk alur
normal di dalam wadah kanvas, dan posisinya menjadi **transform + offset alur**.

Offset alur tidak konstan: ia bergeser setiap kali jumlah penanda berubah — pin pemasok muncul di
ambang zoom 6, kartu nama muncul di zoom 8, gelembung klaster muncul/hilang di tampilan jaringan.
Karena itulah gejalanya "pin bergeser saat zoom", bukan "pin di tempat yang salah".

Pengukuran sebelum perbaikan (`map.project([lng,lat])` vs pusat titik penanda, akun BGN Monitor,
komoditas telur, 9 pin pemasok):

| Keadaan | Kelas `maplibregl-marker` | Simpangan maksimum |
|---|---|---|
| zoom 6,2 (pertama muncul) | utuh | 0,5 px |
| zoom ≥ 6,5 (setelah zoomend pertama) | **hilang di SEMUA pin** | **192 px** |
| zoom 8,5–10,5 | hilang | 191–192 px |

Pin SPPG kena bug yang sama secara laten: `refreshPin` memakai pola yang sama, jadi pin lokasi akan
bergeser begitu data disinkronkan ulang (polling Overview). Belum terlihat di sesi pengukuran karena
penyegaran data belum berjalan.

## 3. Perbaikan

- `frontend/lib/map-pin-class.ts` (baru): `gabungKelasPin(lama, baru)` — mempertahankan semua kelas di
  luar awalan `map-pin` (kelas pustaka: `maplibregl-marker`, `maplibregl-marker-anchor-*`) dan
  mengganti hanya kelas milik aplikasi. Kelas pin lama yang tidak berlaku lagi dibuang, tidak
  menumpuk.
- `frontend/components/SupplyMap.tsx`: `refreshPin` dan `refreshSupplierPin` memakai penggabungan itu,
  tidak lagi menimpa `className`.

## 4. Bukti

Unit test (RED dulu, lalu hijau): `tests/map-pin-class.test.ts` — 8 tes kontrak penggabungan kelas
(kelas pustaka bertahan, nada lama diganti dan tidak menumpuk, kelas pin basi dibuang, tanpa
duplikasi, elemen baru, kelas asing yang memuat "map-pin" di tengah tetap dipertahankan).

Bukti di aplikasi hidup (BGN Monitor, komoditas telur, 9 pin pemasok + 10 pin SPPG; simpangan diukur
terhadap `map.project`):

| Zoom | Kelas MapLibre utuh | Simpangan maks pin pemasok | Simpangan maks pin SPPG |
|---|---|---|---|
| 5,5 | ya | — (ambang zoom saat itu: belum digambar) | 0,5 px |
| 6,2 | ya | 0,5 px | 0,5 px |
| 6,5 | ya | 0,4 px | 0,5 px |
| 7,5 | ya | 0,5 px | 0,5 px |
| 8,2 | ya | 0,5 px | 0,5 px |
| 9,5 | ya | 0,5 px | 0,4 px |
| 10,5 | ya | 0,5 px | 0,5 px |

Simpangan ≤ 0,5 px = pembulatan sub-piksel (titik penanda 24 px). Sebelum perbaikan: 192 px.

Gerbang pada pohon kerja yang berisi perbaikan koordinat: `tsc --noEmit` 0 error, `next lint` 0
peringatan, vitest **1314 lulus / 112 berkas**.

## 5. Batas jujur

- Komponen belum punya tes regresi tingkat DOM untuk bug ini: tiruan `FakeMarker` di
  `tests/supply-map-layer.test.tsx` belum menambahkan kelas `maplibregl-marker` seperti pustaka asli,
  dan berkas uji itu sedang dipakai sesi lain. Yang mengunci kontraknya untuk sekarang: tes murni
  `map-pin-class` + pengukuran di aplikasi hidup di atas.
- Commit ini menyimpan `SupplyMap.tsx` sebagai **HEAD + perbaikan kelas pin saja**; pekerjaan ikon
  sakelar lapisan milik sesi lain yang belum di-commit sengaja TIDAK ikut (lihat `git status`:
  `map-toggle-icons.tsx` masih untracked).
- Perubahan "pin pemasok tampil di semua tingkat zoom" yang diminta setelahnya **belum** masuk commit
  ini: menyentuh `SUPPLIER_PIN_MIN_ZOOM` membuat satu tes komponen di `supply-map-layer.test.tsx`
  (yang sedang disunting sesi lain) menuntut pembaruan. Dicatat sebagai TODO F13b.
