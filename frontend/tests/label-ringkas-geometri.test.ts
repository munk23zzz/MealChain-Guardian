import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak geometri label ringkas (lencana status).
 *
 * Kenapa ada: lencana status punya 8 keluarga (board-badge, kpi-state,
 * safety-state, shipping-tag, integration-badge, shipment-pill, route-tag,
 * reach-tag) yang mengukur dirinya sendiri-sendiri. Terukur di aplikasi hidup
 * 20 Okt 2026: tinggi 20 / 22 / 24 px, padding 1px 6px vs 1px 8px vs 2px 8px,
 * font 12 px semuanya. Penyebabnya bukan angkanya berbeda jauh, melainkan
 * (a) padding vertikal 1 vs 2 px, (b) padding horizontal 6 vs 8 px, dan
 * (c) `line-height` tidak diset sehingga leading body ikut masuk.
 *
 * Perbaikannya satu lapisan di AKHIR stylesheet dengan satu geometri:
 * 2px 8px + line-height 16px + min-height 22px → semua label 22 px, satu baris.
 * Kendali (commodity-pill, board-sort-pill, route-focus-pill) TIDAK termasuk:
 * itu tombol dengan target sentuh sendiri.
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

const KELAS = [
  ".board-badge",
  ".kpi-state",
  ".safety-state",
  ".shipping-tag",
  ".shipping-tag-fail",
  ".integration-badge",
  ".shipment-pill",
  ".shipment-chip",
  ".route-tag",
  ".reach-tag",
];

describe("geometri label ringkas", () => {
  it("blok standar ada dan menyebut semua keluarga label", () => {
    const m = /\/\* Geometri standar label ringkas[\s\S]*?\{([^}]*)\}/.exec(css);
    expect(m, "blok standar tidak ditemukan").not.toBeNull();
    for (const k of KELAS) {
      expect(m![0], `${k} tidak ikut di blok standar`).toContain(k);
    }
  });

  it("satu geometri: padding 2px 8px, line-height 16px, min-height 22px", () => {
    const m = /\/\* Geometri standar label ringkas[\s\S]*?\{([^}]*)\}/.exec(css);
    const isi = m![1];
    expect(isi).toContain("padding: 2px 8px");
    expect(isi).toContain("line-height: 16px");
    expect(isi).toContain("min-height: 22px");
    expect(isi).toContain("white-space: nowrap");
    expect(isi).toContain("box-sizing: border-box");
  });

  it("kendali pil tidak ikut dinormalkan (target sentuh miliknya sendiri)", () => {
    const m = /\/\* Geometri standar label ringkas[\s\S]*?\{([^}]*)\}/.exec(css);
    for (const kontrol of [".commodity-pill", ".board-sort-pill", ".route-focus-pill"]) {
      expect(m![0].replace(/[\s\S]*?\{/, "").split("}")[0]).not.toContain(kontrol);
    }
  });
});
