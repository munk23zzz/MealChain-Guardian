# Pesan galat server sampai ke layar — 18 Okt 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Dua sisa audit 18 Okt yang dikerjakan berurutan: alasan 409 yang hilang di UI,
dan kata "ulang" yang salah pada `/actions/propose`.

## M9a — `ApiError.detail`

**Masalah.** `lib/api.ts` melempar `new ApiError(status, path)` tanpa membaca
body galat. Pesannya selalu `HTTP 409: /actions/verify`. Backend sudah menulis
alasan yang jelas — "verdict sudah tercatat — hasil audit tidak bisa ditimpa" —
tetapi pengguna tidak pernah melihatnya, sehingga satu-satunya jalan keluar
adalah menebak.

**Perbaikan.**
- `request()` membaca body SEKALI untuk sukses maupun galat (body tidak bisa
  dibaca dua kali) dan meneruskan `detail` ke `ApiError`.
- `ApiError.message` = `detail` bila ada; `HTTP <status>: <path>` hanya bila
  server tidak memberi alasan (mis. body HTML dari proxy).
- `detail` berupa daftar validasi FastAPI (422) diringkas menjadi
  `field: pesan`, bukan `[object Object]`.
- Properti `detail` disimpan terpisah supaya pemanggil bisa membedakan "tidak
  ada alasan" dari "alasan kosong".
- Semua layar yang sudah memakai `err.message` (DecisionActions, OpsConsole,
  DemoDataPanel, Event2Panel, ChaosPanel, FoodSafetyBoard, IntegrityPanel)
  ikut mendapat pesan server tanpa perubahan satu per satu.

**Tes** `frontend/tests/api-error.test.ts` (4): detail string → pesan = detail;
422 daftar → "decision_id: UUID input should be a string"; body HTML → pesan
status jujur tanpa "Unexpected token"; 200 JSON tetap objek apa adanya.

**Bukti live (DOM).** Kepala Surabaya membuka `884f1761` → "Kelola
persetujuan…" → "Verifikasi" pada keputusan yang verdict-nya sudah tercatat:
popup menampilkan
`verdict sudah tercatat — hasil audit tidak bisa ditimpa; tarik/ajukan keputusan
baru bila perlu penilaian ulang` — tanpa `HTTP 409`.

## M9b — kata "ulang" pada `/actions/propose`

Pesan 409 untuk status yang tidak boleh diajukan berbunyi "tidak dapat
**dipropose ulang**". Kata "ulang" hanya benar untuk `/actions/repropose`;
`/actions/propose` adalah pengajuan pertama. Sekarang:
`decision status <x> tidak dapat diajukan untuk persetujuan`.

Tes `test_review_only.py` menambah asersi bahwa detail untuk
`/actions/propose` tidak mengandung "ulang".

## Gerbang & catatan lingkungan

- Backend (subset yang menyentuh perubahan): **57 passed, 1 skipped, ruff bersih**.
- Frontend: **1302 passed / 1303** (tsc 0). Satu yang merah adalah
  `tests/proxy-roots.test.ts` milik sesi lain (root `/safety/evaluate` dan
  `/freshness/evaluate` belum terdaftar di `API_ROOTS`) — bukan berkas sesi ini.
- **Dua tes `test_actions.py` (execute) sedang merah karena DATA demo, bukan
  karena perubahan ini**: `batches` punya dua pemasok berbeda untuk pasangan
  Cianjur×telur (baris seed `ec78d45e…` + baris `origin='demo'` `64c95b8a…`
  yang dibuat 18 Okt 16.49). `resolve_binding` menolak menebak bila pemasok
  tidak tunggal ("supplier_unknown: keputusan lama perlu binding batch
  eksplisit") — perilaku yang memang diuji di `test_approval_summary.py`.
  Keputusan uji di `test_actions.py` dibuat tanpa `allocation_binding`, jadi
  kesimpulan pemasoknya bergantung pada invariant "satu pemasok per
  lokasi×komoditas" yang sekarang dilanggar data demo. Pagar tidak dilonggarkan
  dan tes tidak dihapus; yang perlu diperbaiki adalah seed demo yang menambah
  batch pemasok kedua untuk pasangan yang sudah punya batch.
