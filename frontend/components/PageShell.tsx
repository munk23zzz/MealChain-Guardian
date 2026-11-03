"use client";

// PageShell — cangkang halaman yang SAMA untuk semua tab panjang.
//
// Masalah yang diselesaikan (29 Okt 2026): lima halaman menyusun kepalanya sendiri
// dengan urutan yang berbeda-beda, jadi navigasi bagian hanya muncul di sebagian
// halaman:
//
//   Decision & Evidence   PageHeader → SectionJump → isi
//   Food Safety           PageHeader → SectionJump → isi
//   Suppliers             PageHeader → isi                       (tanpa nav)
//   Agent Activity Log    PageHeader → isi                       (tanpa nav)
//   Location Network      PageHeader → isi                       (tanpa nav)
//
// Sekarang urutannya satu: kepala halaman → navigasi bagian → isi. Komponen ini
// TIDAK menambah kelas pembungkus baru (setiap halaman tetap membawa kelas
// lamanya, mis. `board-page safety-page`), supaya tata letak & tes tata letak yang
// sudah ada tidak berubah karena redesign ini.
//
// Aturan nav tetap mengikuti docs/design.md §24: hanya dipasang bila halaman
// benar-benar panjang dan punya ≥3 bagian tetap; maksimum lima tujuan. Karena itu
// `sections` opsional — halaman pendek tidak dipaksa punya nav kosong.

import type { ReactNode } from "react";

import PageHeader from "./PageHeader";
import SectionJump from "./SectionJump";
import type { JumpItem } from "../lib/section-jump";

export default function PageShell({
  title,
  description,
  meta,
  filters,
  eyebrow,
  className,
  busy,
  sections,
  jumpLabel,
  jumpAriaLabel,
  wideDescription = false,
  children,
}: {
  title: string;
  description?: string;
  meta?: ReactNode;
  /** Baris kontrol yang menempel di pita kepala (mis. filter komoditas). */
  filters?: ReactNode;
  eyebrow?: string | null;
  /** Kelas pembungkus yang sudah dipakai halaman ini (tidak diubah). */
  className?: string;
  busy?: boolean;
  /** Tujuan navigasi bagian; kosong/undefined = tanpa nav. */
  sections?: JumpItem[];
  jumpLabel?: string;
  jumpAriaLabel?: string;
  /** Diteruskan ke `PageHeader`: deskripsi halaman selebar kartu. */
  wideDescription?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={className} aria-busy={busy || undefined}>
      <PageHeader
        title={title}
        description={description}
        meta={meta}
        filters={filters}
        eyebrow={eyebrow}
        wideDescription={wideDescription}
      />
      {sections && sections.length > 0 ? (
        <SectionJump items={sections} label={jumpLabel} ariaLabel={jumpAriaLabel} />
      ) : null}
      {children}
    </section>
  );
}
