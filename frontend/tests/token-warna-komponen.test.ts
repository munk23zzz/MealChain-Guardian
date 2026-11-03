import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak: dua komponen yang dulu mewarnai dirinya dengan hex mentah.
 *
 * `StockChart.tsx` mengunci #C62828/#2E7D32/#E2E8F0/#64748B di dalam props
 * Recharts, jadi perubahan token tidak pernah sampai ke grafik — dan #64748B
 * bahkan bukan nilai token mana pun (--ink-muted = #475569). Uji hidup
 * 20 Okt 2026 membuktikan `fill="var(--status-danger)"` resolve di Chrome
 * (terukur rgb(198, 40, 40)), jadi grafik bisa ikut token.
 *
 * `ComplianceEvidencePanel.module.css` menulis hex status langsung plus
 * cadangan hex untuk token yang sebenarnya sudah ada (--line, --surface,
 * --muted-foreground) sehingga ia tidak ikut tema.
 */
const AKAR = join(__dirname, "..");

function baca(rel: string): string {
  return readFileSync(join(AKAR, rel), "utf8");
}

const HEX = /#[0-9a-fA-F]{3,8}\b/g;

/** Komentar boleh menyebut hex (alasan perubahan); yang diuji hanya kode. */
function tanpaKomentar(isi: string): string {
  return isi.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

describe("warna komponen ikut token", () => {
  it("StockChart.tsx tidak memuat hex mentah", () => {
    const isi = baca("components/StockChart.tsx");
    expect(tanpaKomentar(isi).match(HEX) ?? []).toEqual([]);
  });

  it("StockChart.tsx memakai token status, garis, dan tinta sekunder", () => {
    const isi = baca("components/StockChart.tsx");
    expect(isi).toContain('var(--status-danger)');
    expect(isi).toContain('var(--status-safe)');
    expect(isi).toContain('stroke="var(--line)"');
    expect(isi).toContain('fill: "var(--ink-muted)"');
  });

  it("ComplianceEvidencePanel.module.css tidak memuat hex mentah", () => {
    const isi = baca("components/ComplianceEvidencePanel.module.css");
    expect(tanpaKomentar(isi).match(HEX) ?? []).toEqual([]);
  });

  it("ComplianceEvidencePanel.module.css memakai token, bukan cadangan hex", () => {
    const isi = baca("components/ComplianceEvidencePanel.module.css");
    expect(isi).toContain("var(--line)");
    expect(isi).toContain("var(--surface)");
    expect(isi).toContain("var(--muted-foreground)");
    expect(isi).toContain("color: var(--status-safe)");
    expect(isi).toContain("color: var(--status-danger)");
    // #1F3B4D tidak punya token setara; teks keadaan memakai tinta sekunder.
    expect(isi).toContain("color: var(--navy-700)");
  });
});
