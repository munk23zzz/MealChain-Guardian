# Ledger: keterkaitan blok, bukan hanya integritas rantai — 18 Oktober 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Fase 0 butir 4 dari audit 18 Okt (BLOCKER A4): `/ledger/verify` menjawab `{"valid": true}` padahal seluruh blok menunjuk entitas yang sudah tidak ada.

## Masalah

`verify_chain()` hanya menghitung `sha256(prev_hash + payload)` dan kesinambungan `prev_hash`. Itu benar sebagai integritas teknis, tetapi responsnya tidak memuat satu pun angka keterkaitan. Di DB demo: **8.732 blok, 11 tertaut, 8.721 yatim** — hijau penuh, nol bukti yang bisa ditelusuri. Auditor yang membaca "✅ Rantai valid" akan menyimpulkan lebih dari yang dibuktikan.

## Perubahan

1. **`ledger_service.verify_chain()`**: menghitung keterkaitan lebih dulu, lalu tetap memverifikasi rantai. Respons kini memuat `entity_blocks`, `linked_blocks`, `orphan_blocks`, `linked_ratio`, dan `coverage_warning` — termasuk pada respons `valid:false` (rantai putus tidak boleh menyembunyikan angka yatim).
2. **Definisi yatim**: blok dengan `entity_id` yang tidak ada lagi di `decisions` **maupun** `batches`. Blok tanpa `entity_id` tidak dihitung — ia memang tidak menunjuk apa pun.
3. **`valid` tidak diubah**: tetap berarti integritas rantai. Memalsukan `valid:false` hanya karena ada yatim akan membuat dua masalah berbeda tampak satu.
4. **UI** (`IntegrityPanel` + `lib/ledger.coverageNote`): baris peringatan `⚠️ rantai utuh, tetapi N blok menunjuk entitas yang sudah tidak ada (X dari Y blok masih tertaut)` di bawah status rantai.

## Bukti hidup

```
GET /ledger/verify
{"valid": true, "blocks": 8732, "head": "b8719f42…",
 "entity_blocks": 8732, "linked_blocks": 11, "orphan_blocks": 8721,
 "linked_ratio": 0.001,
 "coverage_warning": "rantai utuh, tetapi 8721 blok menunjuk entitas yang sudah tidak ada"}
```

DOM (tab Decision & Evidence, akun BGN Monitor):
`Merkle Ledger (append-only) ✅ Rantai valid · 8732 block · head b8719f42a318…`
`⚠️ rantai utuh, tetapi 8721 blok menunjuk entitas yang sudah tidak ada (11 dari 8732 blok masih tertaut)`

## Gerbang

- Backend: `test_ledger.py` + `test_ledger_linkage.py` (tes baru, membandingkan angka respons dengan hitungan SQL langsung) hijau; ruff bersih.
- Frontend: `ledger-coverage.test.ts` (3 tes) + panel/integritas/today hijau; gate penuh dijalankan.

## Catatan terbuka

- Angka yatim besar karena banyak keputusan/batch demo dihapus sementara blok ledger append-only (memang tidak boleh dihapus). Solusi jangka panjang: blok menyimpan snapshot payload (sudah) dan UI menyebut "entitas sumber tidak lagi ada", bukan menghapus blok.
- `linked_ratio` memakai pembulatan 3 desimal; angka mentah tersedia lewat `orphan_blocks`/`entity_blocks`.
