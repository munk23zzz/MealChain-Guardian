"use client";

// Rail navigasi sidebar. Dulu ditulis inline di app/page.tsx; dipindahkan ke
// sini supaya bisa diuji sebagai komponen (lihat tests/side-nav.test.tsx).
//
// WS-D (QA 16 Okt): tab aktif HANYA ditandai kelas CSS `.side-tab-active`.
// Kelas CSS tidak terlihat oleh pembaca layar, jadi ditambahkan
// `aria-current="page"` — nilai standar untuk item di dalam sekumpulan
// navigasi yang sedang terbuka.
//
// SENGAJA BUKAN role="tab"/tablist: pola itu mewajibkan navigasi panah dan
// roving tabindex di dalamnya (WAI-ARIA APG). Menambahkannya tanpa itu justru
// memberi janji palsu ke pembaca layar, lebih buruk daripada tidak ada.
import NavIcon, { type NavId } from "./NavIcon";

export type NavItem = { id: NavId; label: string; title?: string };

export default function SideNav({
  items,
  active,
  collapsed,
  onSelect,
}: {
  items: NavItem[];
  /** id tab yang sedang terbuka. */
  active: NavId;
  collapsed: boolean;
  onSelect: (id: NavId) => void;
}) {
  return (
    <nav className="side-tabs" aria-label="Bagian konsol">
      {items.map((n) => {
        const current = n.id === active;
        return (
          <button
            key={n.id}
            type="button"
            className={`side-tab${current ? " side-tab-active" : ""}`}
            // Tandanya hanya pada tab yang terbuka: satu sinyal, bukan sepuluh.
            aria-current={current ? "page" : undefined}
            onClick={() => onSelect(n.id)}
            title={n.title ?? (collapsed ? n.label : undefined)}
          >
            <NavIcon id={n.id} />
            <span className="side-tab-label">{n.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
