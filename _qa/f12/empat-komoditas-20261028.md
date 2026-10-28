# Bukti — "semua komoditas bisa dijalankan", 28 Okt 2026

Lingkungan: stack demo (`mealchain-*`, backend `:8000`, UI `:3010`), DB demo
`mealchain`, akun `sppg.head@demo.local` (SPPG Jakarta).

## 1. Sebelum perbaikan (gejala)

- `POST /demo/agent/run {"commodity":"wortel"}` → 409
  `"SPPG ini tidak kekurangan komoditas tersebut"`.
- Sebab: seed kanonik menyimpan Jakarta/wortel **surplus** (`372 kg` pasokan vs
  `159 kg` kebutuhan). Pengadaan hanya membuat keputusan bila `gap_kg > 0`,
  jadi tombolnya jujur menolak — datanya tidak punya kekurangan.

## 2. Perbaikan yang dipilih

`backend/app/seed/demo_template.py` → `_pastikan_kebutuhan_demo()`:

- hanya untuk kota yang punya akun SPPG (`sppg_head`/`sppg_nutritionist`);
- hanya bila belum ada celah (`kebutuhan > pasokan` tetap dihormati);
- menaikkan **kebutuhan** (`target = pasokan × 1,25 + 40 kg`), bukan menurunkan
  pasokan, supaya angka pasokan tetap sesuai data kanonik;
- hanya pada sesi **realtime** (`boleh_menambah_celah`); mode **replay**
  mempertahankan surplus kanonik beserta kasus surplus Jakarta→Bogor.

## 3. Sesudah perbaikan (terukur)

Celah per kota pada DB demo setelah "Muat Demo" (realtime, sesi `0e20ba60`):

| komoditas | pasokan | kebutuhan |
|---|---|---|
| ayam | 200 | 215 |
| beras | 900 | 3010 |
| telur | 300 | 1080 |
| wortel | 360 | 490 |

Empat putaran berturut-turut pada stack demo (semua `HTTP 201`):

```
beras  d19adb8b   telur  aa318395   ayam  cf80c135   wortel  7318da23
```

Putaran lewat UI `:3010` (tombol "Jalankan agent", komoditas `wortel`):
keputusan `81b2113e-8c95-4f29-8987-017603b56ea1`, `16` langkah jejak,
`pending_approval`; kartu "Bukti agent" menampilkan komoditas wortel
(CV Hortikultura Subang Lestari, kurang `130 kg`, stok pemasok `420 kg`).

## 4. Dua bug yang ikut tertutup

1. `batches_dispatch_after_harvest` — `UPDATE` panen bisa melewati
   `dispatched_at` (batch `0ff8f2b1`: panen 07:29, berangkat 07:00) sehingga
   seluruh build realtime gagal 503. Ditambahkan `panen_aman()`: panen dijepit
   5 menit sebelum keberangkatan.
2. Bukti agent kosong/salah komoditas — `GET /demo/agent/last-run` sekarang
   menerima `?decision_id=` (id dari respons run) dan **menggantikan** pencarian
   "terbaru", bukan menambahkannya: id yang tidak punya jejak dijawab
   `found=false`, bukan bukti komoditas lain.

## 5. Alias jaringan yang menyesatkan

`_qa/f10/docker-compose.p10.yml` memakai nama service `backend`, sehingga
jaringan eksternal `mealchain-network` punya DUA alamat untuk `backend`
(demo + klon p10). Akibatnya UI `:3010` kadang membaca sesi klon
(`2b8ecfb5`) lalu menulis ke backend demo → `"sesi demo ... tidak ditemukan"`.
Service diganti menjadi `p10-backend`; stack `mcg-p10` dan `mcg-f12`
diturunkan, kini `getent hosts backend` di container frontend hanya
menghasilkan `172.20.0.5` (backend demo).

## 6. Gerbang yang dijalankan

| gerbang | hasil |
|---|---|
| `pytest` target (5 berkas) di klon `mealchain_verif_wortel` | 34 lulus, 1 gagal **preexisting** (`test_demo_cases_procurement_binding::test_kasus_pengadaan_lolos_resolve_binding_dan_safety`, sudah ada di daftar Fase 12) |
| `pytest tests/test_demo_template_celah_pasokan.py` | 9 lulus |
| `vitest run` (frontend penuh) | 2050 lulus / 187 berkas |
| `tsc --noEmit` | 0 |
| `ruff check` (`demo_template.py`, `api/demo.py`) | bersih |

Catatan: pytest penuh Fase 12 (2120+ tes) **belum** dijalankan ulang; butir 7
Fase 12 tetap terbuka dan tidak diklaim selesai di sini.
