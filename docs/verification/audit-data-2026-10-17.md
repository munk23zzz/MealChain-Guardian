# Audit integritas data — cara memastikan data demo "terstruktur", bukan cuma terlihat rapi

Tanggal: 17 Okt 2026 · Skrip: `backend/scripts/audit_data_integrity.py` (read-only)
Hasil sekarang: **VERDICT: BERSIH** (exit 0) · cadangan DB sebelum perapian:
`C:\Users\User\AppData\Local\hermes\cache\scratch\db-demo-20261017-2130.sql` (5,7 MB, data-only)

## 1. Kenapa audit, bukan lagi hapus manual

Merapikan sekali (dokumen `data-demo-rapi-2026-10-17.md`) menghilangkan residu hari
ini, tetapi tidak menjawab "apakah datanya **secara struktur** sehat". Kerusakan
yang paling mahal di repo ini bukan error, melainkan keadaan yang tampak normal:
baris yatim, natural key ganda, deret yang kurang separuh, atau kasus demo yang
sudah lewat tenggat — semuanya tampil sebagai layar kosong atau angka aneh,
bukan sebagai kegagalan. Karena itu perapian berikutnya harus **diukur**, dan
pengukurannya harus bisa diulang siapa pun.

## 2. Cara pakai

```bash
# laporan manusia (bawaan)
docker compose exec -T -e PYTHONPATH=/app backend python scripts/audit_data_integrity.py

# untuk dibaca mesin / disimpan ke artefak
... scripts/audit_data_integrity.py --json

# dipakai sebagai gerbang: keluar 2 bila ada temuan
... scripts/audit_data_integrity.py --strict
```

`PYTHONPATH=/app` wajib — tanpa itu `import app…` gagal karena `sys.path[0]`
menunjuk folder `scripts/`.

## 3. Tujuh lapisan yang diperiksa

| # | Lapisan | Cara diperiksa | Arti bila merah |
|---|---|---|---|
| 1 | Skema | `alembic_version` di DB vs kepala `alembic/versions` | migrasi belum dijalankan / DB tertinggal |
| 2 | Hitungan per origin | `GROUP BY origin` untuk supply/price/demand/menu/kiriman/limbah. **`seed` harus persis** baseline (kontrak kanonik); **`demo` minimal** baseline, karena deret demo memang bertambah tiap hari aktivitas disemai | ada generasi seed dobel (seed > kanonik) atau deret demo hilang (demo < kanonik) |
| 3 | **Baris yatim** | **setiap** foreign key di skema publik diuji generik `child.col NOT NULL AND NOT EXISTS parent` | data menunjuk baris yang tidak ada lagi |
| 4 | Natural key ganda | `users.email`, `locations.name`, `commodities.name`, `(suppliers.name, location_id)` | seed dobel / baris duplikat |
| 5 | Residu | keputusan non-demo, PO `MC-*` tanpa keputusan, user `@test.local`/`@uji-peran.local` | sisa run tes |
| 5b | Kesiapan demo | per kasus: status, sisa TTL (menit), jumlah trace, jumlah approval | kasus sudah lewat tenggat / jejak tidak lengkap |
| 6 | Rantai bukti | `verify_chain()` dari `app.services.ledger_service` (fungsi aplikasi, bukan SQL tandingan) | blok ledger putus |
| 7 | Selisih baseline | angka nyata vs baseline terdokumentasi | keadaan DB bukan kanonik |

Catatan penting pada #3: pemeriksaan yatim **tidak** memakai daftar FK yang
diingat manusia. Daftar FK dibaca dari `information_schema`, jadi FK baru yang
ditambahkan migrasi berikutnya otomatis ikut diperiksa.

## 4. Hasil hari ini

```
== 1. SKEMA ==                       alembic DB 017_event_origin = kepala repo: cocok
== 2. HITUNGAN PER ORIGIN ==
  supply_records     demo=3870 ok, seed=30 ok
  price_signals      demo=4010 ok, seed=44 ok
  demand_records     seed=168 ok
  menu_plans         demo=590 ok, seed=70 ok
  batches            demo=2, seed=9
  delivery_events    demo=290 ok, seed=70 ok
  disposal_events    demo=60 ok, seed=20 ok      <- 58 kanonik + 2 limbah "hari ini"
== 3. BARIS YATIM (semua FK) ==      tidak ada
== 4. NATURAL KEY GANDA ==           tidak ada
== 5. RESIDU ==
  keputusan non-demo  : 0      PO tanpa keputusan: 0
  user tes tersisa    : 0      kasus demo terpasang: 4
== 5b. KESIAPAN KASUS DEMO ==
  gangguan-logistik     pending_approval  sisa 276 mnt  2 trace  0 approval
  rejection-loop-kuota  pending_approval  sisa 456 mnt  2 trace  0 approval
  shortage-darurat      pending_approval  sisa  96 mnt  3 trace  0 approval
  supplier-janggal      verifier_flagged  sisa 456 mnt  2 trace  0 approval
  (3 keputusan 'rejected' dari kasus loop kuota — riwayat, bukan utang)
  siap ditindak sekarang: 4 · lewat tenggat: 0
== 6. RANTAI BUKTI & DEMOGRAFI ==
  ledger valid: True (6381 blok) · users 3 · locations 10 · commodities 3
  suppliers 35 · decisions 10 · approvals 6 · agent_traces 27
== 7. SELISIH BASELINE ==            tidak ada
VERDICT: BERSIH
```

Yang dibaca dari angka itu:

- **Data kanonik utuh**: 30 supply + 3.870 demo, 44 price + 4.010, 70 menu + 590,
  70 kiriman + 290, 20 limbah + 58, 168 demand — persis baseline terdokumentasi.
- **Tidak ada satu pun baris yatim** di seluruh skema (bukan hanya tabel yang biasa diperiksa).
- **10 keputusan** = 4 kasus demo (7 keputusan) + 3 keputusan selesai untuk KPI.
  Nol keputusan sisa tes.
- **4 PO**: 3 `DEMO-PO-*` tertaut keputusan + 1 `4500000001` yang **memang**
  di-seed tanpa keputusan (`mock_sap.purchase_orders` di seed JSON). Karena itu
  pemeriksaan residu hanya menghitung `MC-*` — baris adapter bukan cacat.
- **Rantai bukti** valid (6.381 blok saat audit ini; angkanya bergerak karena ledger
  *append-only* — setiap eksekusi/penyemaian menambah blok). Keputusan yang
  dihapus kemarin tidak memangkas blok, dan itu memang perilaku yang benar —
  memangkasnya akan menghapus bukti, bukan merapikan data.

## 4b. Temuan semantik — SUDAH DIPERBAIKI di akarnya (bukan tambal data)

Awalnya tiga keputusan `executed` (pengisi KPI "hari ini") **lolos semua pemeriksaan
struktural** — tidak yatim, tidak duplikat, ledgernya sah — tetapi ringkasan
persetujuannya memuat penghalang yang mustahil pada keputusan yang sudah dieksekusi:

```
supplier_unknown: keputusan lama perlu binding batch eksplisit
decision sudah dieksekusi
approval belum memenuhi requirement (missing/rejected)
safety revalidation gagal: tidak ada batch sumber
```

Akar masalahnya bukan datanya, melainkan **penyemainya** (`seed_demo_completed_decisions`).
Memperbaiki baris DB saja akan hilang pada tombol "Segarkan ke hari ini" berikutnya,
jadi yang diperbaiki penyemainya, dan kesiapannya dikunci tes.

| Cacat di penyemai | Perbaikan | Bukti |
|---|---|---|
| hanya **1 approval** (kepala), padahal `regional_balance` operasional wajib dua role | menulis approval kedua (ahli gizi) dengan jam setelah approval kepala | `approvals: 2` per keputusan |
| tidak ada `allocation_binding` | menulis `decision_evidence` bertipe `human_inspection` (tipe yang dipakai jalur produksi; tipe lain ditolak CHECK constraint) berisi `supplier_id` + `batch_ids` | `supplier` terbaca: Supplier A Cianjur / Ayam Segar Serang / Prima Ayam Sejahtera Bogor |
| tidak ada batch sumber untuk pasangan (lokasi, komoditas) | memakai batch yang **sudah ada** lebih dulu; hanya pasangan kosong yang diberi batch baru `origin='demo'` | `safety: pass, blocked=False, batches_checked=1` |
| `verifier_note` diisi kalimat naratif | kolom itu **adalah** verdict yang dibaca read model (`_verdict_of`), jadi diisi `"consistent"` | layar: `aturan persetujuan: konsisten` (dulu "tidak dapat dievaluasi") |
| `expires_at` hanya +2 jam untuk baris `executed` | +30 hari — riwayat yang sudah tutup tidak boleh tampak "decision expired" dua jam kemudian | `Alasan tertahan` tinggal satu |

Hasil sesudah perbaikan, diukur dari API (bukan dari layar saja) untuk ketiga keputusan:

```
supplier: terisi · approvals: 2 · safety: pass, blocked=False
blocking_reasons: ['decision sudah dieksekusi']      <-- satu-satunya alasan, dan itu fakta
```

Dikunci `backend/tests/test_demo_completed_decisions_konsisten.py` (4 tes). Bukti RED→GREEN:
dengan kode lama 3 tes gagal dan pesannya persis daftar penghalang di atas; dengan kode
baru 4 lulus.

### Cacat isolasi yang ikut ketahuan
`test_demo_activity.py` menghapus keputusan selesai + `DEMO-PO-*` yang ia buat, lalu
**tidak memulihkannya**. Karena suite berbagi DB dengan aplikasi, akibatnya: menjalankan
`pytest tests/test_demo_activity.py` diikuti `tests/test_sap_orders_api.py` membuat tes
kedua gagal (`StopIteration` pada "seed punya PO Jakarta") — bukan karena kode, tetapi
karena urutan berkas — dan membuka aplikasi sesudah pytest memperlihatkan panel PO kosong.
Sekarang tes itu menyemai ulang di akhir, jadi keadaan demo utuh kembali.

### Putaran kedua: binding yang menunjuk batch yang sudah hilang

Sesudah suite penuh dijalankan, layar menampilkan penghalang baru pada keputusan yang
sama: `binding batch/supplier berubah`. Sebabnya bukan tes baru itu, melainkan
siklus hidup data demo:

- `purge_demo_rows()` (dipakai tes deret waktu dan tombol "Bersihkan data demo")
  menghapus SELURUH baris `origin='demo'`, **termasuk `batches`**;
- keputusan, evidence, dan PO demo tidak ikut terhapus (origin sama, tetapi bukan
  anggota himpunan yang dipurge), sehingga binding menunjuk batch yang lenyap;
- penyemai dulu menulis binding **sekali** (`if evidence is None`), jadi penyemaian
  ulang tidak pernah memperbaikinya.

Perbaikan: penyemai **menulis ulang** payload binding setiap kali dijalankan
(deterministik, id tetap, jadi idempoten), dan keadaannya sekarang ikut diperiksa
audit — `binding->batch hilang` harus 0. Dikunci
`test_menyemai_ulang_menyembuhkan_binding_yang_menunjuk_batch_hilang`.

Aturan operasional: **sesudah suite penuh, semai ulang aktivitas demo** (jalankan
`seed_demo_completed_decisions`, atau tombol "Muat kasus demo"/"Segarkan ke hari ini"),
lalu jalankan audit. Tanpa itu, DB sah secara struktural tetapi aktivitas KPI-nya
menunjuk batch yang sudah dibersihkan — persis yang dilaporkan audit sebagai merah.


## 5. Dua hal yang memang bergerak sendiri (jangan dibaca sebagai kerusakan)

1. **TTL kasus demo.** Hari ini jendelanya 96 menit (kasus `shortage-darurat`
   paling cepat). Kalau audit dijalankan besok, kolom `sisa` akan negatif dan
   `siap ditindak` jadi 0 — itu **waktu**, bukan data rusak. Tindakannya:
   `POST /demo/refresh` (tombol "Segarkan ke hari ini") tepat sebelum presentasi.
   Perhatikan konsekuensinya: refresh menulis generasi seed hari itu, sehingga
   `seed` di bagian #2 bisa menjadi 60/88/140 — sesudah presentasi, pulihkan
   baseline dengan `scripts/pulihkan-baseline-demo.py` sebelum menjalankan pytest.
2. **Residu pytest.** Setiap `pytest` menulis keputusan baru ke DB yang sama.
   Jalankan audit lagi sesudahnya; kalau `keputusan non-demo` > 0, itu sisa tes,
   bukan data demo yang hilang.

## 6. Batas skrip

- Read-only: tidak pernah menulis, tidak pernah "memperbaiki" sendiri.
- Baseline dipaku untuk data seed/deret; `batches` hanya dilaporkan (9) karena
  jumlahnya bergantung pada seed yang dipakai.
- Tidak memeriksa isi semantik (mis. apakah angka surplus masuk akal) — itu
  wilayah `docs/verification/` yang lain dan tes masing-masing endpoint.
