"use client";

// Ikon navigasi sidebar — inline SVG, tanpa dependensi ikon tambahan
// (pola sama seperti ikon metrik KPI). Bentuknya mengikuti ikon pada aplikasi
// acuan MealchainGuardian (dashboard, gauge, clipboard-list, terminal, slider).
// aria-hidden: label tombol tetap menjadi nama aksesibel (nav tetap "Overview",
// "KPI & Kualitas Agen", dst.) sehingga pembaca layar dan tes tidak berubah.

import type { ReactNode } from "react";

export type NavId =
  | "today"
  | "overview"
  | "kpi-kualitas"
  | "recommendations"
  | "evidence"
  | "safety"
  | "surplus"
  | "suppliers"
  | "agent-log"
  | "demo-control"
  | "settings";

const GLYPHS: Record<NavId, ReactNode> = {
  // sun (Hari Ini) — hari berjalan
  today: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  // layout-dashboard
  overview: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </>
  ),
  // gauge
  // gauge — tab gabungan "KPI & Kualitas Agen" (2026-10-15): satu ikon untuk
  // dua bagiannya (keduanya dulu memakai ikon gauge yang sama).
  "kpi-kualitas": (
    <>
      <path d="M12 14l4-4" />
      <path d="M3.3 18a9 9 0 1 1 17.4 0" />
      <circle cx="12" cy="14" r="1" />
    </>
  ),
  // clipboard-list
  recommendations: (
    <>
      <rect x="8" y="2" width="8" height="4" rx="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <path d="M12 11h4" />
      <path d="M12 16h4" />
      <path d="M8 11h.01" />
      <path d="M8 16h.01" />
    </>
  ),
  // gavel (Decision & Evidence) — keputusan + buktinya
  evidence: (
    <>
      <path d="m14 13-7.5 7.5a2.12 2.12 0 0 1-3-3L11 10" />
      <path d="m16 16 6-6" />
      <path d="m8 8 6-6" />
      <path d="m9 7 8 8" />
      <path d="m21 11-8-8" />
    </>
  ),
  // terminal
  "agent-log": (
    <>
      <path d="m4 17 6-6-6-6" />
      <path d="M12 19h8" />
    </>
  ),
  // sliders-horizontal
  "demo-control": (
    <>
      <path d="M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3" />
      <path d="M14 2v4M8 10v4M16 18v4" />
    </>
  ),

  // shield-check (Keamanan Pangan)
  safety: (
    <>
      <path d="M12 3l7 3v6c0 4.2-2.9 7.9-7 9-4.1-1.1-7-4.8-7-9V6l7-3z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  // recycle (Surplus & Limbah)
  surplus: (
    <>
      <path d="M7 19H5a2 2 0 0 1-1.7-3l2-3.2" />
      <path d="M10.5 4.6a2 2 0 0 1 3.4 0l1.8 2.9" />
      <path d="M17 19h2a2 2 0 0 0 1.7-3L18 11.4" />
      <path d="M9 19h6" />
      <path d="M4.5 12.8l2.4-1.4M15.6 8.6l2.3 1.3M12 5v3" />
    </>
  ),
  // users (Pemasok)
  suppliers: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
    </>
  ),
  // slider/gear (Pengaturan — admin pengguna & lokasi)
  settings: (
    <>
      <path d="M4 6h16M4 12h16M4 18h16" />
      <circle cx="9" cy="6" r="2" />
      <circle cx="15" cy="12" r="2" />
      <circle cx="8" cy="18" r="2" />
    </>
  ),
};

export default function NavIcon({ id, size = 16 }: { id: NavId; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {GLYPHS[id]}
    </svg>
  );
}

// --- Ikon kerangka sidebar (bentuk mengikuti ikon acuan) ---

function Glyph({ children, size = 16, strokeWidth = 1.8 }: { children: ReactNode; size?: number; strokeWidth?: number }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <Glyph size={size} strokeWidth={1.7}>
      <path d="M12 3 4.5 6v5.5c0 4.4 3.1 8.4 7.5 9.5 4.4-1.1 7.5-5.1 7.5-9.5V6z" />
      <path d="m8.8 12 2.2 2.2 4.4-4.4" />
    </Glyph>
  );
}

export function ChevronIcon({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <Glyph strokeWidth={2}>
      {collapsed ? <path d="m9 18 6-6-6-6" /> : <path d="m15 18-6-6 6-6" />}
    </Glyph>
  );
}

export function LogoutIcon() {
  return (
    <Glyph>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5" />
      <path d="M21 12H9" />
    </Glyph>
  );
}

export function SeedIcon() {
  return (
    <Glyph>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
      <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </Glyph>
  );
}

export function ClockIcon({ size = 12 }: { size?: number }) {
  return (
    <Glyph size={size} strokeWidth={1.9}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.2 1.9" />
    </Glyph>
  );
}

// --- Ikon top bar (bentuk mengikuti header acuan) ---

/** Truk pengiriman — dipakai baris "dikirim pemasok … → …" di kartu rekomendasi. */
export function TruckIcon({ size = 14 }: { size?: number }) {
  return (
    <Glyph size={size} strokeWidth={1.8}>
      <path d="M3 7h10v9H3z" />
      <path d="M13 10h4l3 3v3h-7z" />
      <circle cx="7" cy="18" r="1.8" />
      <circle cx="17" cy="18" r="1.8" />
    </Glyph>
  );
}

export function BellIcon({ size = 16 }: { size?: number }) {
  return (
    <Glyph size={size}>
      <path d="M18 8a6 6 0 1 0-12 0c0 6-2 7-2 7h16s-2-1-2-7" />
      <path d="M13.7 20a2 2 0 0 1-3.4 0" />
    </Glyph>
  );
}

export function RoleIcon({ size = 16 }: { size?: number }) {
  return (
    <Glyph size={size}>
      <path d="M12 3 4.5 6v5.5c0 4.4 3.1 8.4 7.5 9.5 4.4-1.1 7.5-5.1 7.5-9.5V6z" />
      <circle cx="12" cy="10.5" r="2.2" />
      <path d="M8.8 16.2c.7-1.5 1.9-2.3 3.2-2.3s2.5.8 3.2 2.3" />
    </Glyph>
  );
}

/** Penutup panel/popup (mis. popup notifikasi). */
export function CloseIcon({ size = 16 }: { size?: number }) {
  return (
    <Glyph size={size}>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </Glyph>
  );
}

/** Pemicu pemilih tanggal (permintaan pemilik 2026-10-17): ikon kecil yang
 *  diklik untuk membuka popup bulan/tahun — kalender garis ala ikon acuan. */
export function CalendarIcon({ size = 14 }: { size?: number }) {
  return (
    <Glyph size={size} strokeWidth={1.9}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M3.5 10h17" />
      <path d="M8 3v3M16 3v3" />
    </Glyph>
  );
}

