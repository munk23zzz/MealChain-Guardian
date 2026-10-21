// Kontrak gerak halaman "Hari Ini": satu reveal untuk lima tile ringkasan.
// Animasi ini sengaja hanya opacity+transform dan WAJIB berhenti total saat
// pengguna meminta gerak minimum — bukan sekadar dipercepat.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

describe("gerak strip ringkasan Hari Ini", () => {
  it("memakai satu keyframe masuk, bukan animasi per kartu", () => {
    expect(css).toMatch(/@keyframes today-tile-in \{[\s\S]*?translateY\(5px\)/);
    expect(css).toMatch(/\.today-summary-list > li \{\s*animation: today-tile-in/);
  });

  it("menghormati prefers-reduced-motion: reduce", () => {
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\) \{\s*\.today-summary-list > li \{ animation: none; \}/
    );
  });
});
