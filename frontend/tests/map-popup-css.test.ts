import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const app = join(process.cwd(), "app");
const globals = readFileSync(join(app, "globals.css"), "utf8");
const mapCss = readFileSync(join(app, "map-console.css"), "utf8");

function block(css: string, selector: string): string {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`selektor tidak ditemukan: ${selector}`);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  return css.slice(open + 1, close);
}

describe("CSS popup peta", () => {
  it("ikon truk menerima klik (punya popup, bukan hiasan)", () => {
    const truk = block(globals, ".map-truck {");
    expect(truk).toContain("pointer-events: auto");
    expect(truk).toContain("cursor: pointer");
  });

  it("kartu popup punya aksen per jenis + nada keadaan, dan chip berteks", () => {
    expect(mapCss).toContain('.map-card .map-popup[data-kind="supplier"]');
    expect(mapCss).toContain('.map-card .map-popup[data-kind="truck"]');
    expect(mapCss).toContain('.map-card .map-popup[data-tone="danger"]');
    expect(mapCss).toContain(".map-card .map-popup-chip");
    expect(mapCss).toContain(".map-card .maplibregl-popup");
    expect(mapCss).toContain("z-index: 6");
  });

  it("aturan 375px diletakkan SETELAH ukuran dasar agar menang", () => {
    const dasar = mapCss.indexOf(".map-card .map-popup-hero-value {");
    const mobile = mapCss.lastIndexOf("@media (max-width: 480px)");
    expect(dasar).toBeGreaterThan(-1);
    expect(mobile).toBeGreaterThan(dasar);
    expect(mapCss.slice(mobile)).toContain("font-size: 18px");
  });
});
