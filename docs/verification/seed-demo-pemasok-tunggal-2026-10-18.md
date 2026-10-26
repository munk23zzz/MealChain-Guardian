# Satu pasangan lokasi×komoditas, satu pemasok batch — 18 Okt 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

## Masalah

`seed_demo_activity` membuat empat kiriman demo per lokasi dengan pemasok
bergilir. Bila pasangan (lokasi, komoditas) itu sudah punya batch kanonik
(`origin='seed'`) dari pemasok lain, seed demo menambah batch KEDUA dengan
pemasok berbeda. Akibatnya:

- `resolve_binding` tidak bisa menyimpulkan pemasok untuk keputusan yang dibuat
  tanpa `allocation_binding` → 409 "supplier_unknown: keputusan lama perlu
  binding batch eksplisit";
- dua tes execute di `test_actions.py` ikut merah — bukan karena pagarnya salah,
  tetapi karena data demo memicu pagar itu.

Bukti sebelum perbaikan: `batches` untuk Cianjur×telur berisi baris kanonik
`ec78d45e…` (seed) dan baris `origin='demo'` `64c95b8a…` (dibuat hari ini).
Pola yang sama muncul di 8 pasangan lain (Bandung beras/telur, Bogor beras,
Cianjur beras, Palembang, Semarang, Surabaya, dst).

## Perbaikan

`seed_demo_activity` membaca pemasok kanonik per pasangan lebih dulu:

- pasangan dengan **tepat satu** pemasok kanonik → batch demo memakai pemasok
  itu (bukan pemasok slot). Id batch tetap id deterministik lama, jadi baris
  yang sudah ada diperbarui di tempat: tidak ada baris yatim dan tidak ada
  rujukan `allocation_binding` yang menunjuk batch yang hilang.
- pasangan dengan **beberapa** pemasok kanonik sejak awal (mis. Jakarta×telur
  punya tiga) tidak dipaksa menjadi satu — itu data kanonik, bukan buatan seed
  demo. Keputusan untuk pasangan seperti itu memang harus membawa
  `allocation_binding` eksplisit, dan pagarnya tetap berlaku.

## Tes

`backend/tests/test_demo_batch_pemasok_tunggal.py` menjalankan seeder pada DB
kerja lalu memeriksa:

1. setiap pasangan yang SEBELUM seeder punya tepat satu pemasok kanonik tetap
   punya satu pemasok sesudahnya;
2. batch demo untuk pasangan itu memakai pemasok yang sama dengan kanonik.

Tes ini merah sebelum perbaikan (8 pasangan dilanggar) dan hijau sesudahnya.

## Verifikasi live

Setelah seeder dijalankan ulang, seluruh berkas yang menyentuh data demo
hijau kembali:

```
pytest -q tests/test_demo_batch_pemasok_tunggal.py tests/test_demo_activity.py \
          tests/test_demo_seed.py tests/test_demo_seed_per_kota.py \
          tests/test_actions.py tests/test_action_boundary_e2e.py
→ 26 passed, exit 0
ruff check app/seed/demo_activity.py tests/test_demo_batch_pemasok_tunggal.py
→ All checks passed!
```

Dua tes execute di `test_actions.py` (yang tadinya merah karena
`supplier_unknown` pada Cianjur×telur) kini hijau tanpa satu pun pagar
dilonggarkan.

Sesudah perbaikan, pasangan yang masih punya lebih dari satu pemasok hanyalah
pasangan KANONIK Jakarta (beras 2 pemasok / 3 batch, telur 3 pemasok / 4 batch).
Seed demo tidak menambah pemasok baru ke sana — ia memakai salah satu pemasok
kanonik (id terkecil, deterministik). Keputusan untuk pasangan seperti itu
memang wajib membawa `allocation_binding` eksplisit.

## Dua perbaikan lint kecil di berkas yang sama

`ruff check app/seed/demo_activity.py` menemukan dua temuan yang sudah ada di
HEAD (bukan dari perubahan ini): impor `DisposalEvent` ganda (F811) dan variabel
lokal `MITRA` (N806). Keduanya diperbaiki di commit yang sama supaya gerbang
berkas ini benar-benar bersih: impor ganda dihapus (impor tingkat modul tetap
ada) dan `MITRA` → `mitra_hari_ini`. Tidak ada perubahan perilaku.
