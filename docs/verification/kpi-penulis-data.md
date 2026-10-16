# Penulis data KPI — kenapa halaman "KPI & Kualitas Agen" tampak kosong

Tanggal: 2026-10-16 (malam). Permintaan pemilik (verbatim):

> "untuk page kpi kenapa informasi seperti tidak di berikan atau berjalan?
> apakah ada dibalik layar yang masih belum jadi atau belum jalan??"

dilanjutkan:

> "kerjakan saja berurutan, namun tetap di cek bahwa semua berjalan di
> frontend maupun backend dll"

## 1. Diagnosis: halaman TIDAK rusak, tiga metrik tidak punya produsen data

Jendela pertama (24 jam) vs dataset demo. REF demo = `2026-10-08 12:00 UTC`,
approval terakhir `2026-10-10`; dalam 24 jam terakhir dataset berisi 0
delivery_event, 0 disposal_event, 0 supplier_quote, 0 PO, 0 approval. Karena
itu sebagian kartu memang tidak punya baris untuk dihitung — itu **sebab
pertama, bukan bug**.

Setelah jendela dilebarkan ke 30 hari, dua kartu tetap kosong. Di situlah
sebab kedua: **rantaian datanya belum ada penulisnya di backend.**

| Metrik | Sumber yang dibaca `kpi_service.py` | Keadaan sebelum |
|---|---|---|
| Decision Time | trace `step_name='ACT'` | 0 baris ACT dari 255 trace. `ACT` sah di CHECK model, ada di whitelist, dan PRD menulis DETECT→…→DECIDE→ACT→LEARN — tapi **tidak ada kode yang menulisnya** |
| Evidence Completeness | `decision_evidence.is_consistent = true` | 130/130 baris NULL (78 temperature + 52 human_inspection); kedua penulis lama mengirim `None` |
| Safe Delivered Cost | JOIN `sap_mock_purchase_orders po ON po.decision_id = d.id` | 3 PO seed ber-`decision_id` NULL; hanya `POST /actions/execute` yang mengisi kolom itu |
| Avoidable Food Loss / Price Deviation | tabel facts | hanya butuh data pada jendela yang dipilih (metrik ini sehat) |

Penyebut Evidence Completeness juga terlalu lebar: ia menghitung **semua**
keputusan di jendela, termasuk 172 keputusan non-demo yang belum punya
approval sama sekali — padahal yang bisa dinilai hanya 7.

## 2. Yang dikerjakan, berurutan

**A. Penulis trace `ACT`.** `app/api/actions.py` menulis trace saat status
keputusan berpindah ke `executed` (satu-satunya jalur eksekusi yang nyata).
Tanpa ini Decision Time tidak akan pernah terisi, apa pun jendelanya.

**B. Penulis bukti konsisten.** `app/core/evidence_consistency.py` (fungsi
murni, tanpa I/O) menurunkan ulang payload dari sumbernya, lalu dipanggil
empat penulis bukti: `event3_service` (temperature), `event2_service`
(market_price), `supplier_eligibility` (binding), `supplier_exclusion_service`
(administrative). Fungsi murni dipilih supaya bisa diuji tanpa DB, dan tiap
penulis tetap bertanggung jawab atas payload-nya sendiri — tidak ada payload
palsu yang dikarang di lapisan KPI.

**C. Penyebut + sampel.** Kartu Evidence Completeness kini membagi dengan
keputusan yang **punya cutoff approval** (yang memang bisa dinilai), dan
envelope KPI membawa `sample_count` + `coverage` supaya sempitnya cakupan
terlihat di layar, bukan tersembunyi di balik angka 0%. Safe Delivered Cost
diverifikasi lewat uji alur nyata (bukan dengan mengakali seed): metrik baru
terisi setelah ada eksekusi, dan itu memang perilaku yang benar.

**D. Label satuan.** Decision Time baru pertama kali punya nilai, dan
nilainya tampil sebagai "0,11 minutes". `KPIDashboard` menerjemahkan
`minutes` → "menit", pola yang sama dengan `percent` → "persen" (kontrak API
tidak diubah).

## 3. Tes

| Perintah (di container `mealchain-backend`) | Hasil |
|---|---|
| `pytest -q tests/test_kpi_act_trace.py` | 4 lulus (RED dulu → GREEN) |
| `pytest -q tests/test_evidence_consistency.py` | 18 lulus (unit murni) |
| `pytest -q tests/test_evidence_consistency_wiring.py` | 4 lulus (menembus layanan nyata + kartu KPI) |
| `pytest -q tests/test_kpi_safe_delivered_cost.py` | 3 lulus |
| `pytest -q` (seluruh suite) | **891 passed, 3 skipped, EXIT=0** (273 s) |
| `ruff check .` | 0 error pada berkas yang disentuh |

Frontend (di container `mealchain-frontend`):

| Perintah | Hasil |
|---|---|
| `npx vitest run tests/kpi-*.test.*` | 32 lulus |
| `npx vitest run` | **716 lulus / 716, 67 berkas** |
| `npx next lint` | 0 peringatan/error |
| `npx tsc --noEmit` | bersih untuk berkas KPI (satu error sisa ada di berkas sesi paralel, lihat §5) |

Satu catatan kejujuran: pada satu kali jalan suite penuh, 6 uji
`tests/test_tool_contracts.py` gagal 401 "token tidak valid". Dijalankan
sendiri → 9 lulus, dan digabung dengan berkas uji baru → 19 lulus; jalan
ulang suite penuh → semuanya hijau. Sebabnya sesi paralel: fixture autouse
`bersihkan_sisa_test` (sesi lain) menghapus semua user `%@test.local` di DB
kerja, termasuk user milik fixture `auth_headers` session ini, saat dua
pytest berjalan bersamaan di DB yang sama. Bukan regresi dari perubahan ini.

## 4. Bukti hidup di stack yang berjalan (bukan hanya tes)

Satu alur penuh dijalankan lewat API nyata (`POST /demo/event1` →
`/actions/propose` → `/actions/approve` ×2 → `/actions/execute`), keputusan
non-demo `4aa0c365-5c73-4f7a-916b-75c7716002cd`:

    DETECT | ... | telur Jakarta
    VERIFY
    TRACE
    PREDICT
    OPTIMIZE
    DECIDE
    SUPERVISE
    ACT | sap_mock.create_purchase_order | MC-4AA0C3655C73
    → sap_mock_purchase_orders: PO MC-4AA0C3655C73 decision_id=4aa0c365-…

Tidak ada satu baris `ACT` di DB sebelum perubahan ini. Kartu KPI untuk
scope SPPG Head (jendela yang sama dengan layar):

| Kartu | Sebelum | Sesudah |
|---|---|---|
| Meal Continuity Rate | 0,00% | 0,00% (sampel 1) |
| Avoidable Food Loss | belum ada data | belum ada data |
| Regional Imbalance Resolution Rate | 0,00% | **7,69%** (sampel 13) |
| Safe Delivered Cost | belum ada data | **Rp15.077.905** |
| Procurement Price Deviation | belum ada data | belum ada data |
| Decision Time | belum ada data | **0,11 menit** (sampel 1 · coverage 0,08) |
| Evidence Completeness | 0,00% (tanpa info sampel) | 0,00% (sampel 1 · coverage 0,03) — kini jujur soal cakupan |

Pembacaan diambil dari DOM halaman hidup (tab "KPI & Kualitas Agen",
`http://localhost:3010`, login SPPG Head), bukan dari API saja.

Dua keputusan `safety_disruption` yang dibuat lewat Event 3 di stack hidup
juga membawa bukti konsisten: `temperature` + `human_inspection`,
`is_consistent = true` (bukti bagian B bekerja di luar tes).

## 5. Temuan di luar lingkup (sesi paralel, sudah dilaporkan ke pemilik)

1. **`frontend/lib/api.ts` — `triggerSafetyDisruption` terdefinisi dua kali**
   (baris 184 dan 450, hasil sunting sesi paralel 22:47). Akibatnya esbuild
   gagal: 16 berkas tes frontend gagal dikompilasi dan dev server memunculkan
   overlay error. Saya dedup (buang salinan kedua, komentar penjelasnya
   dipindah ke salinan pertama) → `vitest run` 67/67 berkas, 716/716 tes
   hijau, halaman hidup kembali normal. Perubahan ini tidak mengubah perilaku
   (kedua salinan berbadan identik).
2. **`frontend/components/FoodSafetyBoard.tsx:253,256` — TS2304 `Cannot find
   name 'idTerima'`** (berkas disunting sesi paralel, 541 baris ditambah).
   Ini masih terbuka; `tsc --noEmit` masih merah karena baris itu. Saya TIDAK
   menambal karena artinya milik alur Event 3 yang sedang ditulis — menebak
   nama variabel justru berisiko salah perilaku.
3. **`backend/tests/test_supplier_routes_api.py:258` — E501** (baris >100
   karakter), sisa milik berkas sesi paralel.

## 6. Residual (sengaja dibiarkan, bukan bug)

- **Avoidable Food Loss & Procurement Price Deviation** tetap "belum ada
  data" pada jendela 24 jam karena deret data demo berhenti di 8 Okt. Melebarkan
  jendela ke 30 hari mengisinya (Food Loss 0,02%, Price Deviation 3,39%).
- **Safe Delivered Cost & Decision Time hanya terisi setelah ada eksekusi
  nyata.** Itu memang definisinya, dan justru jadi alur demo yang bagus:
  jalankan Event 1, setujui, eksekusi → kartu terisi di depan juri.
- **Evidence Completeness masih 0,00%** karena 7 keputusan yang bisa dinilai
  belum punya ≥2 jenis bukti konsisten sebelum approval. Bahan mentahnya sudah
  ada (dua keputusan `safety_disruption` hidup membawa 2 jenis bukti
  `is_consistent = true`); begitu keputusan seperti itu di-approve, kartunya
  naik tanpa perubahan kode lagi.
- **Data uji hidup:** satu keputusan `4aa0c365-…` (status `executed`) +
  PO `MC-4AA0C3655C73` + satu baris bukti ditambahkan ke DB demo sebagai
  bukti. Hapus bila pemilik ingin DB demo bersih sebelum jury.

## 8. Pemilih periode di tab KPI (24 jam / 7 hari / 30 hari)

Setelah langkah 1–7, halaman jalan tetapi masih menunjukkan dua kartu "belum ada
data" dan satu 0,00%. Sebabnya BUKAN kode dan BUKAN database: halaman itu selalu
meminta jendela **24 jam** (`KPI_WINDOW_MS` dipaku di `lib/hooks/useKpi.ts`),
sedangkan dataset demo beracuan 8 Okt — datanya ada di DB, hanya di luar 24 jam.
Diukur langsung dari API:

| Jendela | Metrik tersedia | Isi |
|---|---|---|
| 24 jam | 5/7 | Meal Continuity 0,00% (rencana ada, kiriman tidak), Food Loss & Price Deviation kosong |
| 7 hari | 5/7 | pola sama |
| **30 hari** | **7/7** | Meal 23,70% · Food Loss 0,02% · Price Deviation 3,39% |

Yang dikerjakan (permintaan pemilik, opsi "tanpa risiko data"):

1. `lib/kpi.ts` — `KPI_WINDOWS` (label + jam ditulis berdampingan supaya tidak
   bisa menyimpang) + `kpiWindowRange(key, now)` sebagai fungsi murni. Kunci tak
   dikenal jatuh ke 24 jam (perilaku lama), bukan rentang kosong.
2. `lib/hooks/useKpi.ts` — menerima `windowKey`; rentangnya tetap dihitung SAAT
   fetch, dan KUNCI JENDELA (bukan tanggalnya) yang masuk `queryKeys.kpiLive`,
   jadi berpindah jendela memakai cache yang benar dan tak ada query yang tak
   pernah tenang.
3. `KPIDashboard` — grup pil `role="group"` + `aria-pressed`; komponen TIDAK
   menyimpan state (kalau state ada di komponen, hook tak bisa menerimanya dan
   pilihannya jadi hiasan belaka). Halaman → hook (untuk fetch) dan halaman →
   board → dashboard (untuk menandai pilihan aktif) dipaku di `kpi-wiring`.
4. `app/globals.css` — gaya `.kpi-period*` memakai bentuk pil yang sudah ada,
   target sentuh 44 px di perangkat sentuh.

Tes: 8 uji baru RED→GREEN (3 di `kpi.test.ts`, 3 di `kpi-dashboard.test.tsx`,
2 di `kpi-wiring.test.tsx`). Hasil: 40 uji di 5 berkas KPI hijau; suite frontend
penuh **69 berkas / 792 uji hijau**; `tsc` 0; `next lint` 0.

Bukti di browser hidup (SPPG Head, `localhost:3010`, tab KPI & Kualitas Agen):
pil "30 hari" aktif → header "Periode 16 Sep 2026 – 16 Okt 2026" → **ketujuh
kartu `tersedia`**, tidak ada satu pun "belum ada data":

    Meal Continuity Rate            23,72 persen   sampel 30
    Avoidable Food Loss              0,04 persen   sampel 2
    Regional Imbalance Resolution    2,30 persen   sampel 87
    Safe Delivered Cost              Rp15.079.436  sampel 2
    Procurement Price Deviation      1,20 persen   sampel 4
    Decision Time                    0,11 menit    sampel 2 · coverage 0,02
    Evidence Completeness           22,22 persen   sampel 9 · coverage 0,05

Penting: langkah ini **tidak menambah/mengubah satu baris data pun**. Jangkar
kanonik 8 Okt, 26 berkas tes berjangkar, dan snapshot ekspor tetap utuh — yang
berubah hanya rentang yang diminta halaman.

Keputusan pemilik yang SENGAJA tidak diambil pada malam ini: menggeser hari demo
ke hari ini (`POST /demo/refresh`). Itu membuat kartu 24 jam terisi, tetapi
memindahkan snapshot kanonik (26 berkas tes + ekspor harus diselaraskan) dan
tetap tidak mengisi Food Loss di 24 jam, karena seeder menaruh disposal pada hari
ke-2 dan ke-5. Prosedur rollback-nya sudah ada di rencana Fase 6 bila nanti
diinginkan.

## 9. Berkas yang disentuh

Backend — diubah:
- `app/api/actions.py` (penulis trace ACT di jalur eksekusi)
- `app/services/kpi_service.py` (penyebut Evidence Completeness + docstring)
- `app/services/event2_service.py`, `app/services/event3_service.py`,
  `app/services/supplier_eligibility.py`,
  `app/services/supplier_exclusion_service.py` (mengisi `is_consistent`)

Backend — baru:
- `app/core/evidence_consistency.py`
- `tests/test_kpi_act_trace.py`, `tests/test_evidence_consistency.py`,
  `tests/test_evidence_consistency_wiring.py`,
  `tests/test_kpi_safe_delivered_cost.py`

Frontend — diubah:
- `components/KPIDashboard.tsx` (`minutes` → "menit"; pemilih periode)
- `components/KpiQualityBoard.tsx` + `app/page.tsx` (meneruskan jendela terpilih)
- `lib/kpi.ts` (`KPI_WINDOWS` + `kpiWindowRange`), `lib/hooks/useKpi.ts`
  (`windowKey` menggantikan `KPI_WINDOW_MS`), `lib/query.ts` (`kpiLive(scope, key)`)
- `app/globals.css` (gaya `.kpi-period*`)
- `tests/kpi.test.ts`, `tests/kpi-dashboard.test.tsx`, `tests/kpi-wiring.test.tsx`
  (uji RED lebih dulu)
- `lib/api.ts` (dedup `triggerSafetyDisruption` — perbaikan gangguan kompilasi)

Dokumen: `TODO.md` (blok revisi Sprint 4) + berkas ini.
