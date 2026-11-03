"use client";

// Navigasi "lompat ke bagian halaman" — satu komponen untuk semua halaman.
//
// Kenapa tautan, bukan tombol: daftar ini adalah daftar TUJUAN halaman. Tautan
// bisa dibuka di tab baru, disalin, dan dibacakan pembaca layar sebagai daftar
// tujuan; tombol tidak. Halaman "Hari Ini" memakai tombol karena di sana
// lompatan juga harus memindahkan fokus (lihat TodaySummary.jumpToSection) —
// itu kasus berbeda, bukan alasan menyalin dua perilaku ke satu komponen.
//
// Yang ditandai `aria-current="true"` hanya SATU: bagian yang sedang dibaca,
// diukur lib/hooks/useActiveSection. Tanpa penanda ini nav menempel di atas
// layar hanya jadi hiasan yang tidak memberi tahu posisi pembaca.

import { useActiveSection } from "../lib/hooks/useActiveSection";
import type { JumpItem } from "../lib/section-jump";

export default function SectionJump({
  items,
  label = "Bagian",
  ariaLabel = "Lompat ke bagian halaman",
}: {
  items: JumpItem[];
  /** Label kecil di kiri daftar. */
  label?: string;
  /** Nama nav untuk pembaca layar; sebut halamannya bila perlu. */
  ariaLabel?: string;
}) {
  const aktif = useActiveSection(items.map((item) => item.id));

  if (items.length === 0) return null;

  return (
    <nav className="section-jump" aria-label={ariaLabel}>
      <span className="section-jump-label">{label}</span>
      <ul className="section-jump-list">
        {items.map((item) => (
          <li key={item.id}>
            <a
              className="section-jump-link"
              href={`#${item.id}`}
              aria-current={aktif === item.id ? "true" : undefined}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
