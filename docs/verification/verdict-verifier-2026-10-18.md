# Verdict verifier: dicatat hanya bila ADA hasil audit — 18 Oktober 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Audit 18 Okt butir **M1**: `/actions/verify` selalu menulis `verified_by` —
termasuk saat provider menjawab `UNAVAILABLE`. `verified_by` lalu dipakai
sebagai pagar approve (A2), jadi "terverifikasi" bisa berarti "belum pernah
dinilai". Di depan auditor itu bukti yang tidak bisa dipertahankan.

## Akar masalah (dua lapis)

1. **Pagar salah ukur.** `approve` memeriksa `verified_by IS NOT NULL`; endpoint
   verify menulisnya tanpa syarat apa pun soal isi verdict.
2. **Verifier tidak punya bahan.** `_event_verifier_ctx` mengirim
   `safety_status=None`, `freshness_score=None`, `candidates=[]`,
   `logistics=None`. Model hanya bisa menjawab UNAVAILABLE — jadi hampir semua
   keputusan "terverifikasi" tanpa satu pun dimensi diperiksa.

Dibuktikan dengan probe di kontainer: ctx lama → model menjawab
`UNAVAILABLE` ("data tidak lengkap"); ctx yang diisi data kanonik → model
menjawab `FLAGGED` dengan alasan spesifik (safety FAIL, freshness 0.92, SDC
konsisten).

## Aturan sekarang

- `verified_by` **hanya** ditulis bila verdict `CONSISTENT` atau `FLAGGED`;
  `verifier_note` selalu diisi (`consistent|flagged|unavailable`).
- Respons `/actions/verify` menyatakan `recorded: true|false` apa adanya.
- `approve` (setuju) menuntut `verified_by` **dan** verdict
  `consistent|flagged`. UNAVAILABLE → 409 "keputusan belum diverifikasi".
  Menolak tetap bebas (tidak butuh verdict).
- Read model: `blocking_reasons` membedakan "decision belum terverifikasi"
  (belum ada baris verify) dari "verdict verifier tidak tersedia — bukan hasil
  audit" (ada baris verify, tapi tanpa penilaian).
- UI: menu persetujuan tidak menampilkan Setuju dan menjelaskan alasannya;
  pesan setelah Verifikasi membedakan "verdict tercatat" vs "belum dihitung
  sebagai verifikasi".

## Konteks yang dikirim ke verifier (dari DB, bukan browser)

- `safety_status`, `freshness_score`: batch terbaru di lokasi sumber untuk
  komoditas yang sama; trace DETECT (peristiwa pemicu) menang bila ada.
- `candidates`: daftar kandidat dari trace DETECT, jatuh ke `chosen_candidate_id`
  + skor OPTIMIZE, lalu ke `candidate_score` snapshot.
- `logistics`: komponen supplier leg dari cost breakdown; bila tidak ada,
  rute cache OSRM untuk pasangan lokasi. Tidak ada rute → tetap `None`
  (tidak dikarang).
- `cost`: Safe Delivered Cost + breakdown apa adanya.

## Bukti hidup (18 Okt, kontainer)

| Skenario | Hasil |
|---|---|
| Keputusan baru tanpa trace (`POST /decisions` → propose → verify) | `200 verdict=UNAVAILABLE recorded=False`; DB `verified_by=NULL`, `verifier_note=unavailable`; `approve` → **409 "keputusan belum diverifikasi"** |
| Keputusan Event 1 (ctx lengkap) | `200 verdict=FLAGGED recorded=True`; alasan menyebut safety/freshness/SDC; `approve` → 200 |
| DOM (Kepala Bandung, `41a72f38`) | Menu: aksi `["reject","verify"]` — tanpa Setuju; catatan "Verifikasi belum menghasilkan verdict…"; langkah berikutnya menyebut "keputusan belum diverifikasi" |
| DB setelah verify UNAVAILABLE | `verifier_note=unavailable`, `verified_by` kosong |

## Konsekuensi yang diterima

Provider eksternal bisa gagal (sesekali 502 dari backend AgentCore). Saat itu
verify **tidak** mencatat apa pun dan approve tetap terkunci — sengaja: lebih
baik demo berhenti di "belum dinilai" daripada mengklaim audit yang tidak
terjadi. Kalau provider mati total, satu-satunya jalan adalah memperbaiki
provider atau menambah jalur adjudikasi lokal yang eksplisit (belum dibuat).

## Gerbang

- Backend: 83 tes lulus (verdict, approve-wajib, approval-summary, actions,
  action-boundary, event3, s4, status-approved, peran, demo-seed, akun-multi-kota);
  `ruff check` bersih untuk semua berkas yang disentuh.
- Frontend: 1291 tes / 110 berkas lulus; `tsc --noEmit` 0; `next lint` 0.

## Berkas

- `backend/app/api/actions.py` — `_verifier_ctx` (async, DB), `recorded`,
  `_verifier_unverified` (verdict-based).
- `backend/app/services/approval_summary.py` — `unverified` + alasan terpisah.
- `backend/tests/test_verifier_verdict_recorded.py` (baru, 4 tes).
- `backend/tests/test_approval_summary.py`, `test_approve_wajib_verifikasi.py`,
  `test_event3_api.py`, `test_action_boundary_e2e.py` — verdict dikunci agar
  tes mengukur pagar server, bukan ketersediaan provider.
- `frontend/components/DecisionActions.tsx`, `ApprovalMenu.tsx`,
  `frontend/tests/approval-menu.test.tsx`.
