# Penomoran PO seragam — 18 Okt 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

## Masalah

`sap_mock_purchase_orders` menyimpan tiga gaya nomor:

| nomor | asal | `decision_id` | panel menyebut |
|---|---|---|---|
| `MC-40FF4838DA53` | `POST /actions/execute` | ada | `origin=execution` |
| `DEMO-PO-JAKA-AYAM` | seed aktivitas demo (`demo_activity.py`) | ada | `origin=execution` |
| `4500000001` | baris impor SAP (seed) | tidak ada | `origin=demo` |

Dua baris pertama sama-sama lahir dari keputusan, tetapi bentuk nomornya
berbeda. Dari nomor saja orang tidak bisa menebak asal atau artinya; satu-satunya
aturan yang benar-benar berlaku adalah "12 hex pertama id keputusan" pada satu
jalur dan "kota + komoditas" pada jalur lain.

## Perbaikan

- `backend/app/core/po_number.py::nomor_po()` — satu-satunya pembentuk nomor:
  `MC-` + 12 hex pertama id keputusan (huruf besar). Deterministik; id non-UUID
  ditolak (`ValueError`) alih-alih menghasilkan nomor karangan.
- `POST /actions/execute` dan seed aktivitas demo sama-sama memakai fungsi itu.
- Migrasi `021_po_number_seragam` menormalkan baris historis `DEMO-PO-*` yang
  punya `decision_id`. Baris impor SAP (`4500000001`) tidak disentuh: itu objek
  lain (PO diimpor, bukan diterbitkan aplikasi) dan panel sudah menandainya
  `origin=demo`.
- Docstring `api/sap_orders.py` diperbarui: `origin=execution` berarti "lahir
  dari keputusan" (eksekusi manual maupun seed demo), `origin=demo` berarti
  "baris impor tanpa keputusan".

## Bukti

**Tes (dalam kontainer).**
```
pytest -q tests/test_po_number.py   → 4 passed
pytest -q tests/test_sap_orders_api.py tests/test_demo_activity.py \
          tests/test_po_number.py tests/test_kpi_safe_delivered_cost.py → 20 passed
```
Tes menutup: format `MC-<12 hex>`, determinisme (UUID vs str vs hex), beda id →
beda nomor, dan penolakan id non-UUID. Tes lama yang menuntut prefix `MC-`
(`test_actions`, `test_action_boundary_e2e`, `test_event1_e2e_acceptance`)
tetap hijau — jalur eksekusi tidak berubah bentuk.

**DB setelah migrasi 021.**
```
 MC-E7150DA4CB4B | confirmed | t
 MC-B54D0F110D61 | confirmed | t
 MC-775289583C6E | confirmed | t
 MC-51092B0C2B26 | submitted | t
 MC-40FF4838DA53 | submitted | t
 4500000001      | confirmed | f
```

**DOM (Jakarta, panel Purchase order).** Dua PO tampil sebagai
`MC-B54D0F110D61` (terkonfirmasi) dan `MC-40FF4838DA53` (terkirim), keduanya
berlabel "dari eksekusi"; tidak ada lagi `DEMO-PO-*` di layar.

## Tes lama yang ikut diperbaiki

Gerbang ini menyingkap dua tes `test_event1_e2e_acceptance.py` yang masih
memakai aturan SEBELUM audit M1: keduanya menyetujui keputusan yang verdict
verifier-nya `UNAVAILABLE` dan mengharap 200. Sejak M1 endpoint menolak dengan
409 ("keputusan belum diverifikasi"), jadi tes itu tidak bisa hijau tanpa
mengubah artinya.

Perbaikannya bukan melonggarkan pagar: tes mencatat verdict lebih dulu lewat
`/actions/verify` dengan provider uji (`_force_server_verdict("CONSISTENT")`,
helper yang sama dipakai tes pagar lain), lalu memeriksa `recorded is True`.
Yang diuji tetap kuorum dua peran dan tulisan PO — bukan jalur verifikasi.

## Catatan

- Nomor lama tidak bisa direkonstruksi otomatis (kota/komoditas tidak disimpan
  di baris PO), jadi `downgrade()` migrasi ini sengaja tidak mengubah nomor —
  hanya skema yang dikembalikan (dan skema tidak berubah).
- Nomor PO tetap deterministik dari id keputusan: menjalankan ulang eksekusi
  tidak pernah membuat nomor kedua.
