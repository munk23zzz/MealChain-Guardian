# Approve wajib setelah verifikasi — 18 Oktober 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Fase 0 butir 2 dari audit 18 Okt (BLOCKER A2): persetujuan mendahului verifikasi membuat keputusan mati permanen.

## Masalah

`approve_action` tidak memeriksa `verified_by`. Urutan "Setuju dulu, verifikasi kemudian" bisa terjadi, dan setelah kuorum penuh status menjadi `approved`. Status itu **tidak** menerima `/actions/verify` lagi (gerbangnya hanya `proposed`, `pending_approval`, `verifier_flagged`), sementara `/actions/execute` menolak dengan "belum diverifikasi". Tidak ada jalan keluar lewat UI — keputusan berhenti selamanya.

## Perubahan

1. **Endpoint** (`app/api/actions.py`): `approve` dengan `approved=true` ditolak **409** bila `verified_by` kosong — "keputusan belum diverifikasi — catat hasil verifier dulu sebelum meminta persetujuan". Pemeriksaan diletakkan setelah cek duplikat dan status gate, agar pesan yang lebih spesifik tetap menang.
2. **Read model** (`app/services/approval_summary.py`): `can_approve = approval_accepted and not unverified`. `can_reject` tidak dikunci — penolakan menghentikan laju dan tidak butuh verdict.
3. **Menu** (`ApprovalMenu.tsx`): saat `can_approve` false, tombol Setuju tidak dirender; muncul catatan "Setuju belum tersedia — verifikasi belum tercatat …". Blok Tolak tetap ada.
4. **`ApprovalModal`**: tooltip tombol nonaktif menyebut kemungkinan ketiga (kedaluwarsa / ditolak / belum diverifikasi), bukan hanya dua.

## Bukti hidup

Keputusan `989e6bda` (Jakarta, `pending_approval`, `verified_by` NULL, 0 approval).

- Popup sebelum: aksi `["reject","verify"]`, **tidak ada** tombol Setuju, catatan "Setuju belum tersedia" tampil, ringkasan menahan "⛔ decision belum terverifikasi".
- Klik **Verifikasi** → `POST /actions/verify 200`, `verified_by` terisi (verdict `unavailable` karena tidak ada provider dikonfigurasi).
- Popup sesudah: tombol **Setuju** muncul, catatan hilang, aksi tetap `["reject","verify"]`.

Probe backend (`tests/test_approve_wajib_verifikasi.py`, 4 tes): approve tanpa verify → 409 + tidak ada baris approval + status tetap; ringkasan `can_approve=False`, `can_reject=True`, alasan tercantum; verify lalu approve → 200; menolak tanpa verify → 200 `rejected`.

## Gerbang

- Backend: 11 berkas **90 passed**; ruff `All checks passed!`. Dua tes lama di `test_approval_summary.py` disesuaikan: keputusan uji ditandai terverifikasi lebih dulu supaya yang diukur tetap pagar kedaluwarsa / `approved_by_me`, bukan pagar verifikasi.
- Frontend: vitest **1282 tes / 108 berkas**, tsc 0, next lint 0.

## Catatan terbuka

- Pagar ini memakai `verified_by`, bukan kualitas verdict. Verdict `unavailable` (tanpa provider) tetap membuka approval — sesuai desain konservatif sekarang, tetapi berarti "terverifikasi" belum tentu berarti "dinilai". Memperketat ini butuh provider AI aktif (audit M1).
- Keputusan demo yang sudah `pending_approval` tanpa verifikasi kini menampilkan Verifikasi lebih dulu — alur demo berubah urutan, bukan rusak.
