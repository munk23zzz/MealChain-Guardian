import type { ReactNode } from "react";

/**
 * PageHeader — kepala halaman seragam untuk setiap tab.
 *
 * Pola acuan (MealchainGuardian `app/(protected)/kpi/page.tsx`): satu `h1`
 * kecil-tegas + kalimat penjelas di kiri, meta pendek (periode, waktu, jumlah)
 * di kanan, lalu isi halaman. Dipakai semua tab supaya hierarki judul konsisten
 * — sebelumnya tab KPI hanya punya `h3` dan tab lain `h2`, sehingga tidak ada
 * satu pun `h1` di konsol.
 */
export default function PageHeader({
  title,
  description,
  meta,
  eyebrow,
  level = 1,
}: {
  title: string;
  description?: string;
  meta?: ReactNode;
  /** Baris kecil di ATAS judul (mis. sapaan halaman "Hari Ini"). Opsional —
   *  halaman lain tidak mengirimnya, jadi tampilannya tidak berubah. */
  eyebrow?: string | null;
  /** Tingkat heading. Default 1 (judul halaman). Dipakai `2` oleh bagian yang
   *  BUKAN judul halaman melainkan salah satu bagian di dalamnya — tab
   *  "KPI & Kualitas Agen" memuat dua kepala (KPI dan Kualitas Agen) dan hanya
   *  yang pertama boleh jadi `h1`; sebelumnya keduanya `h1` (temuan audit
   *  aksesibilitas Fase 7: satu halaman satu h1). */
  level?: 1 | 2;
}) {
  const Judul = level === 2 ? "h2" : "h1";
  return (
    <header className="page-header">
      <div className="page-header-text">
        {eyebrow ? <p className="page-header-eyebrow">{eyebrow}</p> : null}
        <Judul>{title}</Judul>
        {description && <p>{description}</p>}
      </div>
      {meta && <div className="page-header-meta">{meta}</div>}
    </header>
  );
}
