"use client";

// Ikon navigasi sidebar — inline SVG, tanpa dependensi ikon tambahan
// (pola sama seperti ikon metrik KPI). Bentuknya mengikuti ikon pada aplikasi
// acuan MealchainGuardian (dashboard, gauge, clipboard-list, terminal, slider).
// aria-hidden: label tombol tetap menjadi nama aksesibel (nav tetap "Overview",
// "KPI", dst.) sehingga pembaca layar dan tes tidak berubah.

import type { ReactNode } from "react";

type NavId = "overview" | "kpi" | "recommendations" | "agent-log" | "demo-control";

const GLYPHS: Record<NavId, ReactNode> = {
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
  kpi: (
    <>
      <path d="m12 14 4-4" />
      <path d="M3.34 19a10 10 0 1 1 17.32 0" />
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
