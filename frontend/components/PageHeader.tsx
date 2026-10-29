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
  filters,
  eyebrow,
  level = 1,
  id,
  titleId,
  ariaLabel,
  className,
}: {
  title: string;
  description?: string;
  meta?: ReactNode;
  /** Baris kontrol halaman (mis. filter komoditas) yang duduk di DALAM pita
   *  kepala, bukan sebagai pita kedua di bawahnya. Halaman yang tidak
   *  mengirimnya tidak berubah tampilannya. */
  filters?: ReactNode;
  /** Baris kecil di ATAS judul (mis. sapaan halaman "Hari Ini"). Opsional —
   *  halaman lain tidak mengirimnya, jadi tampilannya tidak berubah. */
  eyebrow?: string | null;
  /** Tingkat heading. Default 1 (judul halaman). Dipakai `2` oleh bagian yang
   *  BUKAN judul halaman melainkan salah satu bagian di dalamnya — tab
   *  "KPI & Kualitas Agen" memuat dua kepala (KPI dan Kualitas Agen) dan hanya
   *  yang pertama boleh jadi `h1`; sebelumnya keduanya `h1` (temuan audit
   *  aksesibilitas Fase 7: satu halaman satu h1). `3` dipakai kepala yang
   *  duduk DI DALAM bagian berjudul `h2` (blok "Mutu agen" tab Performance &
   *  Audit, tahap 5): tanpa itu judulnya jadi `h2` kedua di dalam `h2` yang
   *  sama. */
  level?: 1 | 2 | 3;
  /** Id pada `<header>` — dipakai sebagai sasaran lompatan (`#ov-ringkas`). */
  id?: string;
  /** Id pada judul. Halaman yang menamai section-nya lewat judul
   *  (`aria-labelledby`) membutuhkannya. */
  titleId?: string;
  /** Nama blok untuk pembaca layar saat judul tidak cukup. */
  ariaLabel?: string;
  /** Kelas tambahan pada `<header>` (mis. `jump-target` untuk sasaran lompatan). */
  className?: string;
}) {
  const Judul = level === 3 ? "h3" : level === 2 ? "h2" : "h1";
  return (
    <header className={`page-header${className ? ` ${className}` : ""}`} id={id} aria-label={ariaLabel}>
      <div className="page-header-text">
        {eyebrow ? <p className="page-header-eyebrow">{eyebrow}</p> : null}
        <Judul id={titleId}>{title}</Judul>
        {description && <p>{description}</p>}
      </div>
      {meta && <div className="page-header-meta">{meta}</div>}
      {filters ? <div className="page-header-filters">{filters}</div> : null}
    </header>
  );
}
