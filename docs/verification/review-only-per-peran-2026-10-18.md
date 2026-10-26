# Temuan review-only & angka per peran — 18 Okt 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Dua sisa audit 18 Okt yang butuh keputusan produk. Owner memilih **A1** (status
terminal `review_only`) dan **B1** (hitungan "menunggu tindakan" per peran).

## A1 — temuan `price_anomaly` lahir `review_only`

**Masalah.** Event 2 membuat keputusan `price_anomaly` berstatus `proposed`
tanpa `quantity_kg`. `/actions/propose` menawarkannya sebagai usulan transfer,
`/actions/execute` selalu menolaknya (422 "quantity decision tidak valid"), dan
tidak ada jalan menutupnya. Keputusan seperti itu menggantung selamanya: tampil
di antrean tindakan, tetapi tidak ada tindakan yang mungkin.

**Perbaikan.**
- Migrasi `020_review_only_status`: CHECK `decisions.status` menerima
  `review_only`; baris `price_anomaly` yang masih `proposed` dipindah ke status
  baru (koreksi, bukan perubahan arti — baris yang sudah masuk alur manusia
  tidak disentuh).
- `event2_service`: temuan lahir `review_only`.
- `approval_summary`: `can_approve`/`can_reject`/`can_execute` semuanya `false`
  dengan SATU alasan: "Temuan tinjauan (review-only): tidak menuntut
  verifikasi, approval, atau eksekusi." Alasan lain (belum terverifikasi,
  approval kurang, kuantitas kosong) tidak lagi ditumpuk — benar tetapi derau.
- `/actions/execute` menolak 409 "decision tinjauan (review-only) — tidak untuk
  dieksekusi" SEBELUM memeriksa verifikasi, supaya pesannya tidak menyesatkan.
- UI: label "tinjauan (review-only)", langkah berikutnya menjelaskan temuan
  adalah bukti, tombol "Kelola persetujuan" tidak dirender, dan "Jendela
  berlaku" disembunyikan (temuan tidak punya jendela tindakan).

## B1 — angka "menunggu tindakan" per peran

**Masalah.** `proposed` tidak dihitung untuk siapa pun, padahal Kepala SPPG
harus menekan "Ajukan". Menambahkannya untuk semua peran juga salah: Ahli Gizi
tidak boleh mengajukan (`/actions/propose` 403), jadi ia akan mengejar pekerjaan
yang tombolnya tidak ada.

**Perbaikan.** `isActionableForRole(status, role)` di `lib/topbar.ts`:
`proposed` hanya dihitung untuk `sppg_head`. Lonceng, kartu "menunggu tindakan",
picker bukti, dan hitungan "lewat tenggat" memakai satu definisi itu, dengan
`role` diteruskan dari halaman.

## Bukti

**Backend (dalam kontainer).**
```
docker compose exec -T backend pytest -q tests/test_review_only.py
2 passed
```
Probe live `probe_m6m7.py` (Event 2 dengan quote sintetis 2x harga acuan):
```
EVENT2: 201 {"status":"anomaly","decision_id":"...","deviation_pct":"124.89"}
SUMMARY: 200 status= review_only can_execute= False can_approve= False
BLOCKING: ['Temuan tinjauan (review-only): tidak menuntut verifikasi, approval, atau eksekusi.']
/actions/propose -> 409 decision status review_only tidak dapat dipropose ulang
/actions/verify  -> 409 verify hanya untuk decision pra-approval (status kini review_only)
/actions/execute -> 409 decision tinjauan (review-only) — tidak untuk dieksekusi
```
Keputusan uji dan price signal sintetis dihapus setelah probe (feed demo bersih).

**Frontend (DOM, peramban).** Bandung, 18 Okt:
- Kepala Bandung: lonceng "Notifikasi: 9 keputusan menunggu tindakan"
  (5 `proposed` + 3 `pending_approval` + 1 `verifier_flagged`).
- Ahli Gizi Bandung: "Notifikasi: 4 keputusan menunggu tindakan"
  (5 `proposed` tidak dihitung).
- Halaman bukti keputusan `review_only`: status "tinjauan (review-only)",
  langkah berikutnya "Temuan tinjauan — dicatat sebagai bukti…", tidak ada
  "Kelola persetujuan", tidak ada "Jendela berlaku".

## Catatan

- `review_only` TIDAK menuntut approval: temuan bukan perintah transfer.
  Menutupnya sebagai `rejected` akan menyiratkan usulan yang buruk — itu sebabnya
  status baru dipilih.
- Migrasi hanya memindahkan `price_anomaly` berstatus `proposed`; baris
  `pending_approval`/`verifier_flagged`/`approved` tidak disentuh karena sudah
  ada approval manusia di sana.
