# AUDIT_03 — Frontend

Stack: Next.js 14.2.14 (App Router), React 18.3.1, TypeScript, `@tanstack/react-query` 5.56.2, MapLibre 4.7.1, Recharts 2.12.7.
Satu halaman (`app/page.tsx`) dengan navigasi tab; tidak ada route per fitur.

## 3.1 Inventaris permukaan

| Tab | Komponen utama | Sumber data | Peran |
|---|---|---|---|
| Hari Ini | ringkasan harian + agenda | `/decisions`, `/batches`, `/agenda` | semua |
| Overview | peta + grafik stok + animasi kiriman | `/balance/map`, `/supplier-routes`, `/suppliers` | semua |
| Recommendations | feed keputusan + aksi | `/decisions`, `/actions/*` | semua (aksi: approver) |
| Decision & Evidence | detail keputusan, bukti, chain, dossier | `/decisions/{id}*`, `/evidence/fuse` | semua |
| Keamanan Pangan | batch, suhu, karantina | `/batches`, `/safety/*`, `/quarantine/*` | semua |
| Surplus & Limbah | neraca surplus + disposal | `/surplus/allocations`, `/waste/*` | SPPG |
| Pemasok | daftar pemasok + jarak + konteks keputusan | `/suppliers`, `/decisions/{id}/approval-summary` | semua |
| Agent Log | trace DETECT→LEARN | `/decisions/{id}/traces`, `/agent/*` | semua |
| KPI & Kualitas Agen | 7 KPI + mutu agen | `/kpi?periode=`, `/agent/*` | semua |
| Pengaturan | pengguna & lokasi | `/admin/*` | admin/monitor |
| Demo Control | sesi, siapkan data, timeseries | `/demo/*` | approver |

## 3.2 Hasil pengujian UI (matriks tab, stack idle)

| Flow | Hasil |
|---|---|
| SPPG Head (Jakarta) — 10 tab, tanpa Pengaturan | **PASS** (semua tab: tombol ada, `aria-current="page"`, isi nyata, teks khas muncul, tanpa console error baru, tanpa 4xx/5xx baru) |
| BGN Monitor — 9 tab, Pengaturan ada, Surplus & Demo Control tidak | **PASS** |
| Kepala Bandung — 10 tab, cakupan Bandung | **PASS** |

Run pertama (saat `pytest` berjalan paralel terhadap DB yang sama) menghasilkan 2 FAIL pada tab **Pemasok**: 404 berulang ke `/decisions/{id}/approval-summary`. Setelah stack idle, ketiga flow PASS → kegagalan itu **race lingkungan**, bukan cacat produk. Kerapuhan yang tetap dicatat: `useDecisionDetail` terus mem-poll id yang sudah tidak ada (lihat AUDIT_09 WF-01).

## 3.3 Tes & pemeriksaan statis

| Pemeriksaan | Hasil |
|---|---|
| `npx vitest run` (seluruh suite) | **166 berkas / 1793 tes PASS** (66 dtk) |
| `npx tsc --noEmit` | exit 0 |
| `npm run lint` (ESLint Next) | "No ESLint warnings or errors" |
| Console browser | tidak ada error baru per tab (kecuali run paralel di atas) |

## 3.4 State management & integrasi API

| Kriteria | Temuan |
|---|---|
| API client base URL | `NEXT_PUBLIC_API_URL` (dipakai `lib/api.ts`); tidak ada URL hardcoded di komponen |
| Error response konsisten | `request()` melempar error; komponen menampilkan banner `role="alert"` |
| Loading state mencegah double submit | form login memakai `submitting`; tombol aksi keputusan memakai status query + disable |
| Race request | React Query dengan `queryKey` ber-scope (`identityScope = role:lokasi`) → pergantian peran memakai cache berbeda |
| Cache invalidation setelah mutasi | aksi keputusan meng-invalidate `decisions` + `decisionDetail`; KPI memakai `kpiLive` (poll) |
| Optimistic update | tidak dipakai (semua menunggu respons server) — aman dari klaim sukses palsu |
| Tipe TypeScript vs respons | `tsc` bersih; namun tipe respons API sebagian `any` (mis. `approvalSummary: any` di `useDecisionDetail.ts`) → tidak ada jaminan kontrak |
| Mock/fallback yang menyamarkan kegagalan | `useDecisionDetail` memakai `.catch(() => null)` untuk 4 endpoint → kegagalan API tampil sebagai "kosong", bukan sebagai error. **Temuan P3**: halus tetapi bisa menyembunyikan 404/500 |
| Data demo tertinggal setelah sesi | banner sesi + filter `demo_session_id`; data demo dihapus saat sesi kedaluwarsa (diuji backend) |

## 3.5 Aksesibilitas (terbatas)

| Kriteria | Hasil |
|---|---|
| `aria-current="page"` pada tab aktif | PASS (diuji matriks) |
| `role="alert"` untuk galat | PASS (statis) |
| `role="status" aria-atomic` untuk status feed | PASS (statis) |
| Label input | form login memakai `ValidatedField` berlabel; form lain tidak diaudit menyeluruh |
| Keyboard/fokus modal | **NOT TESTED** |
| Kontras | **BLOCKED** (tanpa tool) |

## 3.6 Responsive

Tidak ada pengujian viewport terprogram pada audit ini → **NOT TESTED**. CSS memakai layout grid/flex dengan breakpoint; tidak diverifikasi visual.

## 3.7 Temuan frontend

| ID | Temuan | P | Status |
|---|---|---|---|
| FE-01 | `.catch(() => null)` pada 4 endpoint detail menyamarkan kegagalan API sebagai data kosong | P3 | Terbuka (disengaja untuk ketahanan UI; perlu pembeda 404 vs error) |
| FE-02 | Poll detail terus berjalan untuk id yang sudah tidak ada → 404 berulang | P2 | Terbuka (= WF-01) |
| FE-03 | Tipe respons API sebagian `any` | P3 | Terbuka |
| FE-04 | Password 7 akun demo hardcoded di bundel klien (`app/page.tsx:759-777`) | P2 | Terbuka (= SEC-02) |
| FE-05 | Responsive & keyboard belum diuji | P3 | NOT TESTED |
