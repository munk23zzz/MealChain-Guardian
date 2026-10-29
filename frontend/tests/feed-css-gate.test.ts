// Tahap 7 redesign Recommendation Feed (30 Okt 2026): kunci hasil konsolidasi.
//
// Dua aturan `.feed` (gap 12 lalu gap 8) dan tujuh aturan mati dari redesign
// sebelumnya sudah dibuang. Tes ini menjaga supaya tidak tumbuh lagi: satu
// aturan `.feed`, tidak ada kelas `feed-*`/`rec-*` tanpa pemakai atau tanpa
// aturan, dan kotak kosong tetap netral.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const AKAR = path.resolve(__dirname, "..");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8");
const BERSIH = CSS.replace(/\/\*[\s\S]*?\*\//g, "");

const sumber = [
  ...fs.readdirSync(path.join(AKAR, "app")).filter((f) => f.endsWith(".tsx")),
  ...fs.readdirSync(path.join(AKAR, "components")).filter((f) => f.endsWith(".tsx")),
];
const TEKS = [
  ...sumber.map((f) => fs.readFileSync(
    path.join(AKAR, fs.existsSync(path.join(AKAR, "app", f)) ? "app" : "components", f), "utf8")),
].join("\n");

/** Kelas yang didefinisikan CSS sebagai aturan sendiri (bukan bagian dari nama lain). */
function kelasCss(prefix: string): string[] {
  const keluaran = new Set<string>();
  for (const m of BERSIH.matchAll(new RegExp(`\\.((?:${prefix})-[a-z0-9-]+)(?![\\w-])`, "g"))) {
    keluaran.add(m[1]);
  }
  return [...keluaran];
}

/** Kelas yang benar-benar dipakai di `className` komponen/halaman. */
function kelasDipakai(prefix: string): string[] {
  const keluaran = new Set<string>();
  for (const m of TEKS.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)) {
    for (const token of (m[1] ?? m[2] ?? "").split(/\s+/)) {
      if (new RegExp(`^(?:${prefix})-[a-z0-9-]+$`).test(token)) keluaran.add(token);
    }
  }
  return [...keluaran];
}

const adaKata = (teks: string, kata: string) =>
  new RegExp(`(?<![\\w-])${kata}(?![\\w-])`).test(teks);

describe("Tahap 7 — konsolidasi CSS feed", () => {
  it("satu aturan .feed, bukan dua yang saling menimpa", () => {
    expect((BERSIH.match(/^\.feed \{/gm) ?? []).length).toBe(1);
    const i = BERSIH.indexOf(".feed {");
    const blok = BERSIH.slice(BERSIH.indexOf("{", i) + 1, BERSIH.indexOf("}", i));
    expect(blok).toContain("display: grid");
    expect(blok).toContain("gap: 10px");
  });

  it("tidak ada kelas feed-*/rec-* yang didefinisikan tanpa pemakai", () => {
    const mati = kelasCss("feed|rec").filter((kelas) => !adaKata(TEKS, kelas));
    expect(mati).toEqual([]);
  });

  it("tidak ada kelas feed-*/rec-* yang dipakai tanpa aturan", () => {
    const tanpa = kelasDipakai("feed|rec").filter(
      (kelas) => !BERSIH.includes(`.${kelas}`)
    );
    expect(tanpa).toEqual([]);
  });

  it("setiap selektor feed/rec dideklarasikan sekali saja di tingkat atas", () => {
    const selektor = [...BERSIH.matchAll(/^([.\w][^\n{}]*?)\s*\{/gm)]
      .map((m) => m[1].trim())
      .filter((s) => /(^|[\s,])\.(feed|rec)-/.test(s));
    expect(selektor).toEqual([...new Set(selektor)]);
  });

  it("keadaan kosong tetap netral: bukan warna peringatan", () => {
    const i = BERSIH.indexOf(".feed-empty {");
    const blok = BERSIH.slice(BERSIH.indexOf("{", i) + 1, BERSIH.indexOf("}", i));
    expect(blok).not.toContain("--status-warning");
    expect(blok).toContain("--surface-sunken");
  });
});
