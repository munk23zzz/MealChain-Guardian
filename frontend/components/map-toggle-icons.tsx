/**
 * Ikon dua sakelar lapisan di pil kendali peta.
 *
 * Kenapa SVG sebaris (bukan pustaka ikon): repo ini tidak memuat paket ikon,
 * dan dua bentuk ini harus tetap sama di SSR & klien. Aturan yang dipegang
 * (ui-ux-pro-max prioritas 1 & 4): ikon dekoratif `aria-hidden`, kontrolnya
 * sendiri yang punya nama aksesibel; tidak memakai emoji sebagai ikon.
 *
 * Bentuk dipilih supaya tidak bisa tertukar:
 * - pemasok = penanda peta (pin) — sama dengan bentuk pin di peta;
 * - jalur kiriman = polyline dengan dua ujung — sama dengan garis di peta.
 */
type Props = { className?: string };

const BASE = {
  viewBox: "0 0 16 16",
  width: 16,
  height: 16,
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

/** Penanda pemasok (pin). */
export function IkonLapisanPemasok({ className }: Props) {
  return (
    <svg {...BASE} className={className}>
      <path d="M8 1.9c-2.2 0-4 1.8-4 4 0 3 4 8.2 4 8.2s4-5.2 4-8.2c0-2.2-1.8-4-4-4Z" />
      <circle cx="8" cy="5.9" r="1.5" />
    </svg>
  );
}

/** Jalur kiriman (polyline + dua ujung). */
export function IkonLapisanJalur({ className }: Props) {
  return (
    <svg {...BASE} className={className}>
      <path d="M2.6 12.4 6 8.2l3.4 2.4L13.4 3.6" />
      <circle cx="2.6" cy="12.4" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="13.4" cy="3.6" r="1.2" fill="currentColor" stroke="none" />
    </svg>
  );
}
