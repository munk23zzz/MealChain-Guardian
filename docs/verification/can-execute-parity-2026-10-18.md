# `can_execute` mencerminkan pagar eksekusi — 18 Oktober 2026

Audit 18 Okt butir **M5** (eksekusi): read model menyatakan `can_execute=True`
padahal `/actions/execute` pasti menolak. Empat penyebab yang tidak diperiksa
read model:

| pagar di endpoint | akibat di UI sebelum perbaikan |
|---|---|
| `commodity is None` → 422 | tombol Eksekusi aktif, lalu 422 |
| `quantity_kg` kosong/≤0 → 422 | idem |
| `safe_delivered_cost` kosong/≤0 (unit price) → 422 | idem |
| supplier ber-`supplier_exclusions` status `active` untuk SPPG target → 409 | idem |

Ini jenis cacat yang paling terasa di demo: janji di layar, galat di endpoint.

## Perbaikan

`backend/app/services/approval_summary.py` menambah empat pemeriksaan ke
`blocking_reasons`, hanya untuk keputusan non-administratif (tipe admin punya
jalur eksekusi sendiri):

- `commodity decision tidak valid`
- `quantity decision tidak valid`
- `unit price decision tidak valid`
- `supplier excluded pada SPPG penerima` — kalimat **sama persis** dengan
  `revalidate_transfer` supaya UI dan endpoint tidak bercerita beda.

`can_execute = not blocking` tidak berubah; yang berubah isi `blocking`.

## Tes

`backend/tests/test_can_execute_parity.py` (5 tes). Fixture membangun keputusan
yang **semua** syarat lainnya sudah terpenuhi (verified + dua approval Jakarta +
batch sumber aman + binding eksplisit ke Supplier A Cianjur), lalu merusak satu
syarat per tes:

| tes | hasil |
|---|---|
| `test_kendali_semua_syarat_terpenuhi` | `blocking_reasons == []`, `can_execute is True` |
| `test_kuantitas_kosong_memblokir_eksekusi` | `can_execute False` + "quantity decision tidak valid" |
| `test_biaya_kosong_memblokir_eksekusi` | `can_execute False` + "unit price decision tidak valid" |
| `test_komoditas_hilang_memblokir_eksekusi` | `can_execute False` + "commodity decision tidak valid" |
| `test_supplier_dikecualikan_memblokir_eksekusi` | `can_execute False` + "supplier excluded pada SPPG penerima" |

Tes kendali penting: tanpa dia, empat tes lain bisa hijau hanya karena fixture
tidak pernah memenuhi syarat lain.

## Catatan desain

- Pagar di endpoint TIDAK dilonggarkan; read model yang dinaikkan. Arah
  perbaikan ini sengaja satu arah: server tetap penentu, UI hanya cermin.
- Pemeriksaan supplier memakai `scope_location_id == target_location_id`,
  sama seperti `revalidate_transfer` — bukan "supplier dikecualikan di mana pun".
- Keputusan `price_anomaly` dari Event 2 yang tidak punya `quantity_kg` kini
  jujur: `can_execute False` dengan alasan kuantitas, bukan tombol aktif.

## Sisa berurutan

1. `price_anomaly` tanpa `quantity_kg` masih belum punya jalan keluar
   (status terminal "review-only") — sekarang setidaknya tidak lagi menjanjikan
   eksekusi.
2. Angka UI "lewat tenggat" & "menunggu tindakan" mencampur cakupan.
