/** Gerbang muat KPI (GET /kpi) per tab.

KPI dipakai DUA bagian aplikasi:
- tab **Hari Ini** (kartu KPI 24 jam di rekap operasional), dan
- tab **KPI & Kualitas Agen** (halaman gabungan, keputusan pemilik 2026-10-15).

Sebelum 2026-10-15 `useKpi` TIDAK punya gerbang: potret KPI diambil di setiap tab
walau hanya dua tab yang memakainya. Gerbang ini mempertahankan kedua pemakai itu
secara eksplisit — kalau salah satu dilupakan, angkanya hilang tanpa error, jadi
daftarnya sengaja ditulis sebagai konstanta yang diuji.
 */

export const KPI_TABS: readonly string[] = ["today", "kpi-kualitas"];

/** True bila tab ini benar-benar menampilkan angka KPI. */
export function shouldLoadKpi(tab: string | null | undefined): boolean {
  return KPI_TABS.includes((tab ?? "").trim());
}
