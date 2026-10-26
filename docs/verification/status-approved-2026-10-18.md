# Status `approved` saat kuorum penuh — 18 Oktober 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Keputusan produk 2A (pilihan user): status `approved` ditulis sebagai keadaan sah, bukan dihapus dari kosakata.

## Masalah yang ditutup

CHECK constraint `decisions` sejak awal mengizinkan `approved`, tetapi **tidak ada kode yang menulisnya**. Akibatnya:

- dua approval lengkap tetap berstatus `pending_approval` sampai dieksekusi — tidak ada keadaan "disetujui, menunggu eksekusi" yang bisa dilaporkan;
- blok ledger approval ke-1 dan ke-2 sama-sama menyimpan `pending_approval`, sehingga auditor tidak bisa membedakan kuorum separuh dari kuorum penuh;
- UI punya cabang `approved` yang tidak pernah tercapai, dan `needs_verification` yang justru dilarang CHECK.

## Perilaku sekarang

| Kejadian | Status sesudah | Efek lain |
|---|---|---|
| Ajukan (`/actions/propose`) | `pending_approval` | — |
| Approval pertama (salah satu role) | tetap `pending_approval` | `approval_state.satisfied=false` |
| Approval kedua (role berbeda) | **`approved`** | `satisfied=true`, `can_approve=false`, `can_execute=true`, blok ledger mencatat `approved` |
| Eksekusi (`/actions/execute`) | `executed` | PO `MC-*` terbit, trace ACT, blok ledger `execute` |
| Approve lagi oleh user yang sama | 409 `approval sudah tercatat` | status gate dipindah SETELAH cek duplikat agar pesannya tidak menyesatkan |
| Verify setelah kuorum | 409 | approval sudah tercatat |

`/actions/execute` menerima `pending_approval`, `verifier_flagged`, dan `approved`; status lain tetap 409.

## Perubahan UI

- `ACTIONABLE_STATUSES` = `PENDING_APPROVAL`, `APPROVED`, `VERIFIER_FLAGGED` (bukan lagi `NEEDS_VERIFICATION`). `approved` tetap dihitung "menunggu tindakan" karena Kepala SPPG masih harus menekan Eksekusi.
- `visibleActions()` memisahkan tiga izin yang dulu menumpang pada satu predikat:
  - `approve` — `pending_approval` / `verifier_flagged` (Head + Ahli Gizi);
  - `verify` — `proposed` / `pending_approval` / `verifier_flagged` (Head);
  - `execute` — hanya `approved` dan hanya Head.
  Sebelumnya `Eksekusi` digantung pada status pra-approval sehingga `approved` tidak punya tombol apa pun, dan `Verifikasi` menumpang `execute` sehingga ikut hilang.
- `STATUS_ORDER` feed tidak lagi memuat `needs_verification`.

## Bukti hidup (probe di dalam kontainer, akun demo Jakarta)

```
1. buat keputusan        : 201 proposed
2. ajukan                : 201 pending_approval
3. verifikasi            : 200 UNAVAILABLE
4. approve Ahli Gizi     : 200 status=pending_approval satisfied=False
5. approve Kepala        : 200 status=approved        satisfied=True
6. read model            : 200 can_approve=False can_execute=True blocking=[]
7. approve lagi (dobel)  : 409 approval sudah tercatat
8. eksekusi              : 200 status=executed po=MC-40FF4838DA53
```

DOM (Head, keputusan `ebe01e1b`): popup "Governance & persetujuan" hanya menampilkan satu aksi —
`execute: Eksekusi` — dan ringkasan menulis "status approved". Tidak ada Setuju/Tolak/Verifikasi.

## Gerbang

- Backend: `test_status_approved.py` **6/6** (baru), grup 7 berkas **70 passed**, grup demo/event 5 berkas **36 passed**, ruff bersih.
- Frontend: vitest **1276 tes / 108 berkas**, `tsc` 0, `next lint` 0.
- Satu kegagalan sesaat di `test_actions.py` berasal dari sesi lain yang menyapu user `@test.local` (401 "token tidak valid"); hijau saat dijalankan sendiri — bukan regresi.

## Catatan terbuka

- Dua keputusan uji dari probe sengaja **tidak dihapus** agar rantai ledger tidak bertambah yatim: `40ff4838` (executed, PO `MC-40FF4838DA53`) dan `ebe01e1b` (approved, tanpa eksekusi).
- Probe menunjukkan `/actions/verify` tetap menulis `verified_by` walau verdict `UNAVAILABLE` — temuan audit #3, di luar lingkup langkah ini.
