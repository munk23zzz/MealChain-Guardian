// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import { PIN_GLYPHS, buildPinGlyph } from "../lib/map-pin-glyphs";

describe("ikon penanda peta", () => {
  it("SPPG memakai siluet bangunan, pemasok memakai kardus", () => {
    // Redesign 20 Okt 2026: metafora kendaraan dipakai SATU penanda saja (mobil
    // yang bergerak), jadi ikon pemasok berubah dari truk menjadi kardus.
    expect(PIN_GLYPHS.sppg.paths.length).toBeGreaterThanOrEqual(3);
    expect(PIN_GLYPHS.sppg.circles).toBeUndefined();
    expect(PIN_GLYPHS.supplier.paths.length).toBeGreaterThanOrEqual(3);
    expect(PIN_GLYPHS.supplier.circles).toBeUndefined();
  });

  it("SVG-nya diwarisi warna teks dan disembunyikan dari pembaca layar", () => {
    const svg = buildPinGlyph("supplier");
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg.getAttribute("class")).toBe("map-pin-icon map-pin-icon-supplier");
    expect(svg.getAttribute("viewBox")).toBe("0 0 24 24");
    expect(svg.getAttribute("stroke")).toBe("currentColor");
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    // Jangan pernah jadi target Tab: penanda sendiri sudah fokusable.
    expect(svg.getAttribute("focusable")).toBe("false");
  });

  it("kardus digambar sebagai garis, tanpa isian yang menutupi tile", () => {
    const svg = buildPinGlyph("supplier");
    expect(Array.from(svg.querySelectorAll("circle"))).toHaveLength(0);
    const paths = Array.from(svg.querySelectorAll("path"));
    expect(paths).toHaveLength(PIN_GLYPHS.supplier.paths.length);
    paths.forEach((path) => {
      expect(path.getAttribute("fill")).toBeNull();
    });
  });
});
