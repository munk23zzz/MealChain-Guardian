# Rencana build ulang halaman "Decision & Evidence"

Dokumen ini rencana, bukan laporan selesai. Disusun 29 Okt 2026 dari keadaan kode
yang ada (`frontend/app/page.tsx`, `components/DecisionDetail.tsx`,
`components/DecisionEvidence.tsx`, `backend/app/api/decisions.py`) dan dari
inventaris endpoint yang benar-benar hidup. Tidak ada endpoint baru yang
diusulkan.

## 0. Satu keputusan desain yang menyelesaikan kebingungannya

Halaman ini **bukan** "halaman kumpulan panel". Halaman ini satu berkas per
keputusan: **satu keputusan = satu dossier**. Yang boleh ada di halaman hanya
data yang bisa dijawab dengan pertanyaan "milik keputusan ini?".

Konsekuensi yang penting:

- Setiap bagian wajib punya `decision_id` sebagai kunci. Kalau sebuah blok
  butuh "semua PO", "semua batch", "feed rekomendasi", atau "log agen seluruh
  sistem" supaya masuk akal, blok itu milik halaman lain.
- Daftar keputusan tetap ada di halaman (itu indeks halaman ini sendiri), tetapi
  isinya hanya pemilih: id, judul, status, tenggat. Bukan feed rekomendasi.
- Halaman tidak lagi menavigasi keluar untuk "lihat jejak" atau "lihat
  rekomendasi"; kalau datanya milik keputusan ini, ditampilkan di sini.

## 1. Yang ada hari ini (hasil inventaris)

`page.tsx` tab `evidence` merender dua hal:

1. `<DecisionEvidence>` → daftar keputusan + `<DecisionDetail>` (halaman hidup).
2. `<PurchaseOrderList>` → daftar PO **seluruh jaringan** (modul procurement).

`DecisionDetail.tsx` (532 baris) menyusun: hero → zona keputusan
(`<ApprovalOverview/>` + `<DecisionActions/>`) → jalur persetujuan → bukti
(biaya, keamanan & pemasok, identitas & tenggat, evaluasi batch) → jejak &
riwayat (`<DecisionAudit/>`, `<IntegrityPanel/>`). Di dalamnya juga dipasang
`<SupplierExclusionView>` dan `<GoodsReceiptDrawer>`.

## 2. Data yang tersedia dan sudah ber-scope keputusan

| Kebutuhan bagian | Endpoint (sudah ada) | Fungsi klien |
|---|---|---|
| Kepala keputusan | `GET /decisions/{id}` | `fetchDecision` |
| Daftar pemilih | `GET /decisions` | `fetchDecisions` |
| Tiga jawaban + langkah persetujuan | `GET /decisions/{id}/approval-summary` | `fetchApprovalSummary` |
| Jalur persetujuan | `GET /decisions/{id}/chain` | `fetchDecisionChain` |
| Jejak agen keputusan ini | `GET /decisions/{id}/traces` | `fetchDecisionTraces` |
| Bukti kanonik + tanda tangan | `GET /decisions/{id}/packet`, `GET /decisions/{id}/compliance` | `fetchDecisionPacket` |
| Integritas baris ledger | `GET /decisions/{id}/ledger` | `fetchDecisionLedger` |
| Fakta audit | `GET /decisions/{id}/audit-facts` | — (belum ada pemanggil di UI) |
| Ekspor dossier | `GET /decisions/{id}/dossier` | `fetchDossier`, `downloadDossier` |
| PO milik keputusan ini | `GET /sap/purchase-orders?decision_id={id}` | `fetchPurchaseOrders(token, { decisionId })` — opsinya sudah ada, tetapi hook `usePurchaseOrders` masih meminta `limit: 200` tanpa `decisionId` (itu yang harus diubah) |
| Ceklis penerimaan | `GET /receipts?batch_id={id}` | `fetchReceipts` |
| Aksi | `POST /actions/*`, `POST /decisions/{id}/review`, `POST /actions/purchase-orders/{po}/approve` | `approveAction`, `executeAction`, `reviewDecision`, `approvePurchaseOrder` |

Catatan penting: `/receipts` berkunci **batch**, bukan keputusan. Karena itu
ceklis hanya boleh muncul untuk batch yang tercatat pada keputusan itu
(`batch_id` diambil dari paket/biaya keputusan). Ini tetap "milik keputusan ini",
bukan papan catatan jaringan.

## 3. Yang dikeluarkan dari halaman (dan alasannya)

| Blok sekarang | Asal modul | Masalah | Gantinya di halaman ini |
|---|---|---|---|
| `<PurchaseOrderList>` seluruh jaringan | procurement | Daftar PO semua keputusan dipasang di bawah satu keputusan; pembaca mengira itu milik keputusan yang dibuka (keluhan 19 Okt 2026, sudah ditambal penanda "keputusan ini") | Ringkas: **PO keputusan ini saja** (`decision_id`), maksimal 1–3 baris, tautan "buka di Pemasok/PO" bila perlu |
| `onOpenRecommendations` (lompat ke tab Recommendations) | recommendations | Navigasi keluar dari dossier | Bagian "Rekomendasi asal" cukup satu baris identitas + tombol lompat (bukan konten) |
| `onOpenTraces` (lompat ke Agent Log) | agent-log | Jejak keputusan ini sudah tersedia lewat `/decisions/{id}/traces` | Tampilkan langsung di bagian Jejak |
| `<SupplierExclusionView>` (pembuatan pengecualian pemasok) | suppliers | Aksi modul pemasok dilakukan dari halaman bukti | **Baca saja**: nama pemasok, jarak, status kelayakan; aksinya di halaman Pemasok |
| `<GoodsReceiptDrawer>` (isi ceklis) | penerimaan barang | Formulir modul lain dibuka dari halaman bukti | Ringkasan ceklis per batch (sudah terisi/belum) + tombol menuju halaman penerimaan |
| Panel provider/model, Demo Control, Price Monitor | lain-lain | Tidak ada hubungannya dengan satu keputusan | Tidak ada |

Aturan pengikat: **halaman ini tidak menulis apa pun selain aksi keputusan**
(setujui, tolak, eksekusi, review PO, review manusia). Pembuatan pemasok,
pencatatan ceklis, pengecualian pemasok, dan pengaturan demo adalah pekerjaan
halaman lain.

## 4. Anatomi baru: 5 bagian, urut pertanyaan pembaca

| # | Bagian | Pertanyaan yang dijawab | Isi | Data |
|---|---|---|---|---|
| 1 | **Kepala** | "Keputusan apa ini, dan apakah saya harus bertindak?" | judul, komoditas & jumlah, asal→tujuan, penghematan, tenggat, status, penanda (flags) | `GET /decisions/{id}` |
| 2 | **Keputusan** | "Boleh saya setujui? Siapa lagi? Setelah ini apa?" | tiga jawaban, daftar penyetuju berjam, tiga langkah, tombol aksi | `approval-summary` + `POST /actions/*` |
| 3 | **Jalur** | "Sudah sampai mana?" | kronologi: diajukan → verifikasi agen → persetujuan → eksekusi | `/chain` |
| 4 | **Bukti** | "Atas dasar apa angka ini?" | biaya & komponennya, keamanan batch + pemasok (baca saja), identitas & tenggat, evaluasi batch, integritas ledger | `/packet`, `/compliance`, `/ledger`, batches milik keputusan |
| 5 | **Jejak & hasil** | "Apa yang sudah terjadi, dan apa buktinya?" | trace agen keputusan ini, riwayat audit, review manusia, **PO keputusan ini**, ringkasan ceklis per batch | `/traces`, `/audit-facts`, `/sap/purchase-orders?decision_id`, `/receipts?batch_id` |

Urutan itu satu arah: identitas → tindakan → proses → dasar → akibat. Tidak ada
bagian yang mengulang angka bagian lain (aturan yang sama yang dipakai di
Location Network: satu angka, satu tempat).

## 5. Perilaku keadaan (wajib, bukan tambahan)

- **Memuat**: kerangka per bagian, bukan satu spinner halaman.
- **Kosong**: tulis sebabnya ("belum ada eksekusi", "belum ada ceklis"), jangan `0` atau `—` tanpa alasan.
- **Gagal**: satu bagian gagal tidak mengosongkan halaman; bagian itu menulis "gagal dimuat: …" + tombol coba lagi untuk query-nya sendiri.
- **Kedaluwarsa**: status `expired` mengubah nada kepala + menonaktifkan aksi, dengan sebab tertulis.
- **Peran**: `sppg_head` boleh setujui/eksekusi/review PO; `sppg_nutritionist` boleh setujui; `bgn_monitor` **baca saja** — tombol tetap terlihat tetapi `disabled` dengan alasan peran, bukan hilang diam-diam (kontrak F9).
- **Fokus & papan tunjuk**: dialog/drawer mengembalikan fokus ke tombol pemicu; `Esc` menutup.

## 6. Langkah implementasi (bertahap, tiap langkah berhenti untuk verifikasi)

1. **Inventaris & kontrak** — tulis daftar bagian + data di `lib/decision-dossier.ts` (fungsi murni: `susunBagian(decision, summary, chain, packet, po, receipts)`), dengan tes murni lebih dulu (tanpa DOM).
2. **Kepala & Keputusan** — pecah `DecisionDetail.tsx` menjadi `DecisionHero`, `DecisionVerdict` (pakai `ApprovalOverview` yang sudah ada). Tes markup: urutan bagian + tidak ada angka bagian lain.
3. **Jalur** — pindahkan kronologi ke komponen sendiri; tes: langkah yang belum terjadi tidak diberi jam.
4. **Bukti** — pecah menjadi kartu-kartu kecil; tambahkan `SupplierFactsReadOnly` (pengganti `SupplierExclusionView`). Tes: tidak ada tombol tulis selain aksi keputusan.
5. **Jejak & hasil** — pindahkan trace ke sini (dari `/decisions/{id}/traces`), tambah `DecisionPurchaseOrder` (satu PO, `decision_id`) dan `ReceiptSummary` per batch.
6. **Keluarkan blok lintas-halaman** — hapus `<PurchaseOrderList>` dari tab `evidence`, hapus `onOpenTraces`/`onOpenRecommendations` sebagai navigasi, ganti dengan tautan satu baris.
7. **Peran & keadaan** — matriks tombol per peran + keadaan kosong/gagal/kedaluwarsa, tes per peran.
8. **Gerbang penuh** — `tsc --noEmit`, `vitest run`, `next build`, lalu bukti DOM live untuk tiga peran di `:3010` (seperti verifikasi Location Network).

## 7. Kriteria terima

- Satu keputusan tampil lengkap tanpa memuat daftar milik modul lain: tidak ada PO seluruh jaringan, tidak ada feed rekomendasi, tidak ada log agen global, tidak ada formulir pemasok/ceklis.
- Semua angka di halaman bisa ditelusuri ke respons endpoint ber-`decision_id`; tidak ada angka yang dihitung ulang di klien kecuali turunan sederhana yang diuji.
- Tombol aksi hanya empat: setujui, tolak, eksekusi, review PO (+ review manusia bila ada). Peran `bgn_monitor` tidak punya tombol aktif.
- `tsc` 0, seluruh tes hijau, build produksi lolos, bukti DOM tiga peran tercatat.

## 8. Risiko & pertanyaan terbuka

1. **Ceklis penerimaan**: `/receipts` berkunci batch. Perlu dipastikan paket keputusan memang memuat `batch_id`; kalau tidak, bagian "ringkasan ceklis" harus diberi tanda "batch tidak tertaut".
2. **PO draft (dua gerbang)**: halaman ini sudah punya tombol "Review & kirim" untuk PO `draft`; setelah pemisahan, tombol itu tetap di bagian Jejak & hasil (bukan di bagian Bukti) supaya alurnya satu arah.
3. **`/audit-facts` belum dipakai UI**: usulannya masuk bagian Jejak; perlu dicek apakah isinya tumpang tindih dengan `DecisionAudit`.
4. **Pembagian berkas saat ini**: `DecisionEvidence.tsx` adalah cangkang halaman (pemilih + memanggil `DecisionDetail`), dan `DecisionDetail.tsx` memuat seluruh isi A–E. Jadi build ulang berarti memecah `DecisionDetail.tsx` menjadi bagian-bagian, **bukan** menghapus `DecisionEvidence.tsx`. Nama komponen isi sebaiknya ikut dipecah (`DecisionHero`, `DecisionVerdict`, `DecisionPath`, `DecisionEvidenceBlocks`, `DecisionTraceAndResult`) agar "satu keputusan = satu dossier" terbaca dari nama berkasnya.
5. **Kolaborasi**: dua proses lain sedang menulis `DecisionDrawer.tsx`/`DecisionActions.tsx`; langkah 1–2 harus menunggu atau dikoordinasikan agar tidak saling menimpa.

## 9. Status pengerjaan (29 Okt 2026, sesi ini)

| Langkah | Keadaan | Bukti |
|---|---|---|
| 1. Modul aturan halaman | **selesai** | `lib/decision-dossier.ts` + `tests/decision-dossier.test.ts` (14 tes) |
| 2. Kepala & Keputusan | **selesai (penanda)** | lima bagian bertanda `data-bagian` berurut; bukti DOM live `["kepala","keputusan","jalur","bukti","jejak"]` |
| 3. Jalur | **selesai (penanda)** | `data-bagian="jalur"` pada kartu jalur persetujuan |
| 4. Bukti | **selesai (penanda)** | `data-bagian="bukti"`; kartu bukti tetap dari `/packet` + `/compliance` |
| 5. Jejak & hasil | **selesai** | `DecisionPurchaseOrder` (6 tes) + `DecisionTraceList` (5 tes) + 2 tes di `evidence-dossier.test.tsx` |
| 6. Keluarkan blok lintas-halaman | **selesai** | `<PurchaseOrderList>` jaringan dicabut (0 rujukan di `page.tsx`); tombol "Buka jejak agen" ke tab Agent Log dihapus, jejak dirender di tempat |
| 7. Peran & keadaan | **selesai (terverifikasi)** | bgn_monitor: catatan "Peran ini hanya dapat melihat catatan review (read-only)", tanpa tombol setujui/eksekusi; tes `decision-evidence.test.tsx` menambah kasus peran baca-saja |
| 8. Gerbang penuh | **selesai** | `tsc` 0 galat; `vitest run` 207/207 berkas, 2.429/2.429 tes lulus; `NEXT_DIST_DIR=.next-verif npm run build` EXIT 0 |

### Bukti DOM live (`:3010`, 29 Okt 2026)

- **SPPG Head** (`sppg.head@demo.local`), keputusan `b5b391fe…`: urutan bagian
  `kepala → keputusan → jalur → bukti → jejak`; kartu "PO keputusan ini"
  menulis "Belum ada PO untuk keputusan ini…" (benar: PO keputusan itu tidak
  ada di DB setelah seed ulang); kartu "Jejak agen keputusan ini" menampilkan
  langkah nyata `DETECT 28 Okt 23.31 · beras.supply_gap` dan
  `VERIFY 28 Okt 23.36`.
- **BGN Monitor** (`bgn.monitor@demo.local`): lima bagian tetap tampil, tidak ada
  tombol setujui/eksekusi, dan pada panel review tertulis "Peran ini hanya dapat
  melihat catatan review (read-only)".

### Keputusan yang menyimpang dari rencana awal

- **`ReceiptSummary` tidak dibuat.** Ceklis penerimaan untuk keputusan ini sudah
  ditangani `GoodsReceiptDrawer` yang membaca `receipt_gate` dari server
  (`can_receive`/`can_quarantine` + alasan kode). Menambah ringkasan kedua akan
  menciptakan dua sumber kebenaran untuk satu pertanyaan. Yang dipakai dari
  rencana hanya `ringkasCeklis()` di `lib/decision-dossier.ts`, untuk kasus bila
  batch keputusan memang perlu dihitung per batch.
- **Pemecahan `DecisionDetail.tsx` menjadi berkas terpisah per bagian belum
  dilakukan.** Yang dikerjakan adalah bagian yang punya nilai nyata lebih dulu
  (PO, jejak, penanda bagian); sisanya menunggu karena berkas itu masih ditulis
  proses paralel. Kontraknya (lima bagian + sebab kosong) sudah terkunci di
  `lib/decision-dossier.ts` sehingga pemecahan berikutnya tidak mengubah perilaku.
