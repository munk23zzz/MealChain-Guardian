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
}: {
  title: string;
  description?: string;
  meta?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {meta && <div className="page-header-meta">{meta}</div>}
    </header>
  );
}
