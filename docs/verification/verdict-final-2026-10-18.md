# Verdict audit tidak bisa ditimpa — 18 Oktober 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Audit 18 Okt butir **M2**: `/actions/verify` boleh dipanggil berulang selama
belum ada approval, dan setiap panggilan menimpa `verifier_note`. Tidak ada
jejak percobaan, tidak ada blok ledger. Akibatnya hasil audit bisa "diulang
sampai menyenangkan": `FLAGGED` (dua approval wajib) bisa diubah menjadi
`CONSISTENT` hanya dengan menekan Verifikasi lagi — syarat persetujuan turun,
tanpa satu pun bukti bahwa percobaan pertama pernah ada.

## Aturan sekarang

1. Verdict yang sudah **tercatat** (`consistent`/`flagged`) bersifat final:
   verify berikutnya **409** "verdict sudah tercatat — hasil audit tidak bisa
   ditimpa". Penilaian ulang hanya lewat keputusan baru (ajukan/putuskan ulang),
   bukan dengan menimpa catatan lama.
2. Retry tetap sah bila percobaan sebelumnya **tidak** menghasilkan verdict
   (`unavailable`) — provider boleh pulih dan belum ada hasil untuk ditimpa.
3. Setiap percobaan yang sampai ke verifier menulis **satu baris
   `agent_traces` VERIFY**: verdict, `recorded`, provider, `fallback_used`,
   potongan alasan. Jadi riwayat "berapa kali dicoba, hasilnya apa" terbaca.
4. Verdict yang tercatat menambah **satu blok ledger `action='verify'`**
   (entity = keputusan, actor = pemanggil, payload = verdict + provider).
   Percobaan tanpa verdict tidak menambah blok: tidak ada perubahan keadaan
   yang perlu dicatat, cukup jejak percobaan.

Urutan pagar di `/actions/verify` sekarang: status → cakupan lokasi → approval
belum ada → kedaluwarsa → **verdict belum tercatat** → jalankan provider.

## Bukti hidup (kontainer, provider nyata)

```
A. Keputusan baru tanpa trace (e288c7cc…)
   propose → pending_approval, verified=False
   verify-1 → 200 verdict=UNAVAILABLE recorded=False
   verify-2 → 200 verdict=UNAVAILABLE recorded=False   (retry sah: belum ada verdict)
   agent_traces VERIFY = 2 baris (UNAVAILABLE / recorded=false)
   ledger_blocks tidak bertambah

B. Keputusan Event 1 yang verdict-nya sudah tercatat (b74e82cf…, flagged)
   verify → 409 "verdict sudah tercatat — hasil audit tidak bisa ditimpa; …"
   approval-summary → verdict=flagged, min_approvals=2 (syarat tidak turun)

C. Blok ledger hasil verdict tercatat
   SELECT count(*) FROM ledger_blocks WHERE action='verify' → 21
   contoh: height 9016 CONSISTENT · 9008 FLAGGED · 9003 FLAGGED
```

## Tes

`backend/tests/test_verifier_tidak_bisa_diulang.py` (4 tes):

| tes | yang dikunci |
|---|---|
| `test_verdict_tercatat_tidak_bisa_ditimpa` | verify kedua 409; `verifier_note` tetap `consistent`; status tetap `pending_approval` |
| `test_retry_setelah_unavailable_tetap_boleh` | UNAVAILABLE → CONSISTENT boleh, `verified_by` baru terisi di percobaan yang menghasilkan verdict |
| `test_setiap_percobaan_meninggalkan_trace_verify` | 2 percobaan = 2 baris VERIFY, yang terakhir `CONSISTENT` |
| `test_verdict_tercatat_menambah_satu_blok_ledger` | tanpa verdict: 0 blok; verdict tercatat: +1 blok `action='verify'` |

## Tes lama yang ikut diperbaiki (bukan dilonggarkan)

`test_ledger.py::test_approve_appends_ledger_block` memilih keputusan
`pending_approval` **apa saja** lalu approve sebagai Kepala Jakarta. Sejak seed
per kota (M4) dan suite lain mengisi Bandung/Surabaya, baris yang terambil bisa
milik kota lain → 403 cakupan. Kegagalan itu terbaca seperti regresi pagar
padahal pagarnya benar. Tes kini memilih baris sesuai cakupan tokennya (Jakarta,
verdict sudah tercatat, user belum menyetujui) dan `pytest.skip` bila tidak ada —
pola yang sama dengan pelajaran "tes ber-token harus menyaring dengan cakupannya".

## Gerbang

- Backend: 116 tes lulus di 16 berkas (verdict, retry, approve-wajib,
  approval-summary, actions, action-boundary, event3, s4, status-approved,
  peran, event1-supervisor, demo-event1, dossier, ledger, ledger-linkage);
  `ruff check` bersih.
- Frontend tidak disentuh pada langkah ini (pesan 409 tampil lewat jalur galat
  yang sudah ada).

## Sisa yang belum ditutup dari audit

- `POST /actions/repropose` belum memakai `require_scope` (celah lintas lokasi).
- `can_execute` read model belum memeriksa kuantitas/harga & eksklusi pemasok.
- `price_anomaly` tanpa `quantity_kg` tidak punya status terminal.
- Angka UI: "lewat tenggat" & "menunggu tindakan" masih mencampur cakupan.
