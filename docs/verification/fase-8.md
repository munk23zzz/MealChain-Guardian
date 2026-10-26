# Verifikasi F8 — Tab gabungan "KPI & Kualitas Agen" (+ strip Target KPI dihapus)

> **Snapshot tahun 2026 (tanggal tidak tertulis)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Tanggal: 2026-10-15 · Lingkup: frontend saja (backend tidak disentuh) · Status: **selesai & terverifikasi**

Dasar: permintaan pemilik 2026-10-15 — *"pada halaman KPI hapus bagian Target KPI. setelah itu …
menggabungkan page kualitas agent dan juga page kpi lalu buat nama baru untuk di sidebar"*.
Plan: `.hermes/plans/2026-10-15_gabung-halaman-kpi-kualitas-agen.md` (keputusan pemilik dikunci di §3).

## 1. Apa yang berubah

| Bagian | Sebelum | Sesudah |
|---|---|---|
| Strip "Target KPI Demo Day" | `components/KpiTargets.tsx` (PRD §5, berlabel TARGET DEMO) | **dihapus**; berkas + import + pemakaian + CSS `.kpi-target*` (1.798 byte) hilang |
| Tab sidebar | dua tab: `kpi` ("KPI") + `quality` ("Kualitas Agen") | **satu tab**: id `"kpi-kualitas"`, label **"KPI & Kualitas Agen"** |
| Susunan halaman | dua halaman terpisah | satu halaman: KPI dulu, lalu mutu kerja agen, dipisah satu pembatas |
| "Rincian per run" | tampil penuh | tetap tampil penuh (keputusan pemilik) |
| Komposisi | `KPIDashboard` / `AgentQualityBoard` dipanggil langsung dari `app/page.tsx` | dipanggil dari `components/KpiQualityBoard.tsx` (tipis: urutan + pembatas; **isi keduanya tidak diubah**) |
| Muat `/kpi` | tanpa gerbang — diambil di **semua** tab | gerbang `lib/kpi.ts::shouldLoadKpi` = `today \| kpi-kualitas` |
| Sampel mutu agen | `tab === "quality" \| tab === "suppliers"` | `tab === "kpi-kualitas" \| tab === "suppliers"` |

Berkas: `components/KpiQualityBoard.tsx` (baru), `lib/kpi.ts` (baru), `components/NavIcon.tsx`
(union `NavId` + satu ikon gauge untuk tab gabungan), `app/page.tsx` (union `Tab`, `navItems`, blok
render), `lib/hooks/useKpi.ts`, `lib/hooks/useQualitySample.ts`, `app/globals.css` (§ blok baru, hanya
token), `tests/kpi.test.ts` (baru), `tests/kpi-quality-board.test.tsx` (baru),
`tests/kpi-wiring.test.tsx`, `tests/prd-nav.test.tsx`, `tests/supplier-pins.test.ts`,
`tests/supplier-exclusions.test.ts` (diperbarui).

## 2. Gerbang (hasil nyata)

| Gerbang | Hasil |
|---|---|
| `vitest run` | **542 lulus / 60 berkas** (sebelumnya 532/58 → +10 tes, +2 berkas) |
| `npx tsc --noEmit` | **exit 0** (ditemukan & diperbaiki satu galat nyata: `NavId` di `NavIcon.tsx` belum punya id baru) |
| `npx next lint` | **0 warning, 0 error** |
| `npx next build` | **BUILD_EXIT=0** — rute `/` prerendered, First Load JS 454 kB |
| Backend | tidak dijalankan ulang: tidak ada berkas backend yang berubah |

Catatan prosedur build: `next build` harus dijalankan dengan `next dev` **dimatikan**
(`docker compose stop frontend` → `docker compose run --rm --no-deps frontend sh -c 'cd /app && npx next build'`
→ `docker compose start frontend`). Dua percobaan pertama lewat `docker compose exec` pada kontainer dev
yang hidup membunuh hidrasi halaman (form terisi tapi tombol mati) — pulih setelah restart kontainer.
Percobaan ketiga (dev dimatikan) keluar 0; hidrasi diperiksa ulang sesudahnya (lihat §3, bukti 3).

## 3. Bukti di aplikasi yang berjalan (:3010)

Aplikasi hidup: 4 kontainer Up, `http://localhost:3010/` HTTP 200.

1. **Peran SPPG Head** (`sppg.head@demo.local`), tab gabungan:
   - rail: `["Hari Ini","Overview","Recommendations (12)","Decision & Evidence","Keamanan Pangan",
     "Surplus & Limbah","Pemasok","Agent Log","KPI & Kualitas Agen","Demo Control"]` —
     **0** entri bernama "KPI" atau "Kualitas Agen" (tab lama benar-benar hilang).
   - isi satu halaman: `.kpi-quality-page` ada, **7 kartu KPI**, judul bagian
     `["KPI","Kualitas Agen","Skor agregat","Putusan verifikator","Rincian per run"]`, pembatas
     `.kpi-quality-divider` = 1.
   - urutan terverifikasi: `innerHTML.indexOf("kpi-dashboard") < indexOf("board-page")` → **true**.
   - kontrol negatif: teks **"Target KPI" 0 kemunculan**, "TARGET DEMO" 0 kemunculan.
2. **Peran BGN Monitor** (`bgn.monitor@demo.local`), tab gabungan: 7 kartu KPI dengan
   `scope global (bgn_monitor)`, "Skor agregat" + "Rincian per run" tetap ada; rail monitor memuat
   "Pengaturan" dan **tidak** memuat "Surplus & Limbah" (aturan peran lama utuh, tidak tersentuh F8).
3. **Hidrasi pasca-build**: quick-fill akun demo mengisi form (terisi = true), submit masuk konsol,
   klik rail mengganti halaman, dan halaman gabungan terisi data → keadaan "handler mati / 200 tanpa
   hidrasi" TIDAK terjadi.
4. **Tab "Hari Ini" tetap dapat KPI-nya** (regresi yang paling mungkin dari gerbang baru): kartu
   `.today-card.today-kpi` berisi "KPI 24 jam | 3/7 | …" dengan baris metrik asli
   ("Meal Continuity Rate | tersedia | 0,00 percent" … "Evidence Completeness | tersedia | 0,00 percent"),
   tanpa teks galat. Kalau `today` lupa dimasukkan ke `shouldLoadKpi`, kartu ini kosong tanpa error.
5. **Rail terlipat (68 px)**: label tab gabungan ber-`title` penuh ("KPI & Kualitas Agen"),
   `.side-tab-label` tetap `overflow:hidden / text-overflow:ellipsis / white-space:nowrap`, elemen label
   masih ada di pohon aksesibilitas (lebar 0) sehingga nama aksesibel tidak hilang saat terlipat.

## 4. Yang TIDAK diubah (sengaja)

- Isi & perhitungan `KPIDashboard` dan `AgentQualityBoard` — angka di layar karena itu tidak bisa
  berbeda dari sebelum penggabungan.
- Seluruh backend, endpoint `/kpi`, `/decisions/{id}/traces`, `approval-summary`.
- Aturan peran pada rail (Surplus & Limbah = SPPG; Pengaturan = admin/monitor).
- `queryKeys.kpi` di `lib/query.ts` (kunci cache React Query memakai string `"kpi"`, tidak ada
  hubungannya dengan id tab — dibiarkan supaya tidak mengubah kunci cache tanpa alasan).

## 5. Sisa / catatan jujur

- Halaman gabungan masih memuat **dua `PageHeader`** ("KPI" dan "Kualitas Agen"). Itu sengaja
  (komponen tidak disentuh) dan bisa disatukan jadi satu judul halaman di pekerjaan berikutnya.
- Dua percobaan build pertama menghasilkan galat prosedur (bukan galat kode) dan outputnya tidak
  tersimpan karena batas waktu alat; percobaan yang sah sudah dijalankan ulang dan hasilnya di §2.
- Semua perubahan F1–F8 masih **uncommitted**.
