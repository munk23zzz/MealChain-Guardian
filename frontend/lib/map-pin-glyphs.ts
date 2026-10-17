/**
 * Ikon di dalam penanda peta (pin SPPG + pin pemasok).
 *
 * Kenapa SVG dan bukan titik polos: titik 12 px hanya bisa menyampaikan WARNA,
 * padahal di peta ada dua lapisan penanda yang bisa bertumpuk (lokasi SPPG dan
 * pemasok). Bentuk yang berbeda + ikon membuat keduanya bisa dibedakan tanpa
 * membaca legenda lebih dulu. Ikonnya sengaja siluet sederhana (garis 1,8 px,
 * tanpa detail kecil) supaya tetap terbaca pada ukuran 13 px di kanvas.
 *
 * Aturan:
 * - `sppg` = bangunan/gudang dapur (fasilitas penerima).
 * - `supplier` = truk (pemasok yang mengirim).
 * - Ikon selalu `aria-hidden`: maknanya sudah dibawa aria-label penanda.
 */

export type PinGlyphKind = "sppg" | "supplier";

type Glyph = {
  /** Path geometri (viewBox 24×24) — garis, bukan isian. */
  paths: readonly string[];
  /** Lingkaran (mis. roda truk) — diisi `fill` ikon, bukan stroke. */
  circles?: readonly { cx: number; cy: number; r: number }[];
};

export const PIN_GLYPHS: Record<PinGlyphKind, Glyph> = {
  // Gudang/dapur: alas, dinding ber-atap, dan pintu.
  sppg: {
    paths: ["M4 20h16", "M6.5 20V10.6L12 7l5.5 3.6V20", "M10.2 20v-4.4h3.6V20"],
  },
  // Truk: bak, kabin, dan dua roda.
  supplier: {
    paths: ["M3 16.5V7.5h9.5v9", "M12.5 10.5h3.2L19 13.6v2.9h-6.5", "M3 16.5h16"],
    circles: [
      { cx: 6.6, cy: 17.6, r: 1.7 },
      { cx: 15.6, cy: 17.6, r: 1.7 },
    ],
  },
};

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Bangun elemen SVG ikon pin. `doc` bisa diganti di tes (jsdom) — produksi
 * memakai dokumen halaman.
 */
export function buildPinGlyph(kind: PinGlyphKind, doc: Document = document): SVGSVGElement {
  const svg = doc.createElementNS(SVG_NS, "svg") as SVGSVGElement;
  svg.setAttribute("class", `map-pin-icon map-pin-icon-${kind}`);
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.9");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const glyph = PIN_GLYPHS[kind];
  glyph.paths.forEach((d) => {
    const path = doc.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  });
  (glyph.circles ?? []).forEach(({ cx, cy, r }) => {
    const circle = doc.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", String(cx));
    circle.setAttribute("cy", String(cy));
    circle.setAttribute("r", String(r));
    // Roda: isian ikut warna garis supaya tidak terlihat seperti lubang.
    circle.setAttribute("fill", "currentColor");
    circle.setAttribute("stroke", "none");
    svg.append(circle);
  });
  return svg;
}
