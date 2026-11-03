# Re-propose dijaga cakupan lokasi — 18 Oktober 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Audit 18 Okt butir **M3** (izin & cakupan): `POST /actions/repropose` hanya
memanggil `require_scope` di cabang `ADMIN_TYPES`. Untuk keputusan operasional
(`regional_balance`, `safety_disruption`, `price_anomaly`) penjaga cakupan tidak
ada sama sekali — padahal pagar yang sama sudah dipasang di propose, verify,
approve, dan execute sejak 17 Okt.

## Akibatnya (sebelum)

Kepala SPPG Bandung membuka keputusan `rejected` milik Jakarta, menekan
"ajukan ulang", dan menerima iterasi baru yang **menyalin `target_location_id`
parent** — yaitu keputusan baru untuk SPPG Jakarta, dibuat oleh peran dari kota
lain. Ia tidak bisa menyetujuinya sendiri (approve tetap 403), tetapi ia bisa
membanjiri antrean SPPG lain dengan iterasi yang tidak diminta, dan jejak
`LEARN` mencatatnya sebagai tanggapan atas penolakan yang bukan wilayahnya.

## Perbaikan

`_require_decision_scope(user, parent)` dipanggil **sebelum** cabang tipe, untuk
semua tipe keputusan. Urutan pagar: cakupan → admin → status → alasan.

Konsekuensi urutan yang perlu diketahui: re-propose keputusan administratif oleh
user **di luar** cakupan kini menjawab **403** (bukan 409 "lewat panel
supplier"). Itu konsisten dengan endpoint tulis lain, dan pesan 403 menyebut
cakupan SPPG — bukan mengarahkan orang ke panel yang juga akan menolaknya.

## Tes

`backend/tests/test_repropose_scope.py` (4 tes):

| tes | yang dikunci |
|---|---|
| `test_repropose_lintas_lokasi_ditolak_403` | Kepala Bandung → keputusan rejected Jakarta: 403, **0** anak dibuat |
| `test_repropose_di_lokasi_sendiri_tetap_201` | Kepala Bandung → keputusan Bandung: 201, iterasi 2, 1 anak |
| `test_repropose_admin_lintas_lokasi_tetap_403` | tipe `supplier_exclusion` dari luar cakupan: 403 |
| `test_repropose_admin_di_lokasi_sendiri_tetap_409` | tipe admin di dalam cakupan: 409 dengan arahan panel supplier-exclusions (perilaku lama dipertahankan) |

## Tes lama yang ikut diperbaiki (bukan dilonggarkan)

`test_supplier_exclusion_api.py` (3 tes) menekan Verifikasi lalu Approve dan
mengharap 200. Sejak M1 approve menuntut verdict hasil audit, dan provider nyata
bisa menjawab UNAVAILABLE, sehingga tes itu mengukur ketersediaan LLM — bukan
pagar administratif. Kini modul itu mengunci verdict `FLAGGED` lewat override
chain: verdict tercatat **dan** syarat dua-approver tetap seperti yang diukur
tes (`CONSISTENT` akan menurunkan syarat menjadi satu approval dan mengubah arti
tesnya).

## Gerbang

Angka lengkap ada di laporan lisan sesi ini; berkas dokumen ini sengaja tidak
memuat angka yang bisa berubah antar-run.

## Sisa berurutan

1. `can_execute` belum memeriksa kuantitas/harga & eksklusi pemasok.
2. `price_anomaly` tanpa `quantity_kg` tidak punya jalan keluar.
3. Angka UI "lewat tenggat" & "menunggu tindakan" mencampur cakupan.
