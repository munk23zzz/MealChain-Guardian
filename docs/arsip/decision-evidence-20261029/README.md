# Arsip — Decision & Evidence dikosongkan (29 Oktober 2026)

Permintaan pemilik: *"hapus seluruh isi halaman Decision & Evidence, sisakan kerangka
kosong (pemilih keputusan + kepala), lalu bangun ulang dari nol"* + *"balikin design
yang tadi"*.

## Keadaan sesudah perubahan ini

- Halaman tetap punya **kepala kartu** (pola Overview) dan **bilah kendali** berisi
  pemilih keputusan — desain yang sama seperti tahap 1.
- **Isi halaman tidak dirender**: ringkasan keputusan, persetujuan, bukti, PO, jejak,
  integritas. Sebagai gantinya satu kartu jujur "Isi halaman sedang dibangun ulang".
- **Navigasi bagian dimatikan** selama isi kosong: keempat tujuannya menunjuk jangkar
  yang belum ada.
- Kode isi lama **tidak dihapus**: ia duduk di balik konstanta `ISI_DIBANGUN_ULANG`
  di `frontend/components/DecisionEvidence.tsx`.

## Cara memulihkan

1. Salin balik berkas di folder ini (salinan utuh sebelum perubahan):
   - `DecisionEvidence.tsx` → `frontend/components/DecisionEvidence.tsx`
   - `DecisionDetail.tsx` → `frontend/components/DecisionDetail.tsx`
   - `evidence-dossier.css` → `frontend/app/evidence-dossier.css`
2. Ganti nama berkas tes yang dipause kembali (hapus akhiran `.pause`):
   ```
   cd frontend/tests
   for f in *.pause; do mv "$f" "${f%.pause}"; done
   ```
3. Buka `tests/evidence-rapi.test.tsx` dan ubah `describe.skip(` kembali ke
   `describe(` untuk blok "kerapian — kepala keputusan".
4. `npx tsc --noEmit && npx vitest run && npx next lint`

## Tes yang dipause (bukan dihapus)

| Berkas | Tes | Alasan |
| --- | --- | --- |
| `decision-evidence.test.tsx` | 28 | memaku isi halaman (hero, fakta, riwayat, governance) |
| `evidence-dossier.test.tsx` | 6 | memaku bentuk dossier/bukti |
| `decision-evidence-cost-block.test.tsx` | 4 | memaku blok biaya |
| `decision-evidence-actions-ux.test.tsx` | 3 | memaku aksi keputusan |
| `safety-badge-count.test.tsx` | 2 | memaku lencana di kartu Keamanan & pemasok |
| `evidence-rapi.test.tsx` (1 blok) | 1 | memaku kepala hero keputusan |

Total 44 tes dipause; suite yang tersisa: **252 berkas / 2.727 lulus / 2 dilewati**.
