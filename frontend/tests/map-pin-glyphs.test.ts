// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import { PIN_GLYPHS, buildPinGlyph } from "../lib/map-pin-glyphs";

describe("ikon penanda peta", () => {
  it("SPPG memakai siluet bangunan, pemasok memakai truk", () => {
    expect(PIN_GLYPHS.sppg.paths.length).toBeGreaterThanOrEqual(3);
    expect(PIN_GLYPHS.sppg.circles).toBeUndefined();
    expect(PIN_GLYPHS.supplier.paths.length).toBeGreaterThanOrEqual(3);
    expect(PIN_GLYPHS.supplier.circles).toHaveLength(2);
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

  it("roda truk diisi warna, bukan stroke — supaya tidak tampak berlubang", () => {
    const svg = buildPinGlyph("supplier");
    const circles = Array.from(svg.querySelectorAll("circle"));
    expect(circles).toHaveLength(2);
    circles.forEach((circle) => {
      expect(circle.getAttribute("fill")).toBe("currentColor");
      expect(circle.getAttribute("stroke")).toBe("none");
    });
  });
});
