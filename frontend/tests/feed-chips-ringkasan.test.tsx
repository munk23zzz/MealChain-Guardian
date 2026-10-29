// Tahap 2 redesign Recommendation Feed (30 Okt 2026): chip status menjadi
// ringkasan yang bisa ditekan — urutan menaruh "Perlu tindakan" lebih dulu,
// chip berangka 0 tidak lagi bisa ditekan, dan tiap chip punya nama yang
// menyebut cakupan + jumlah untuk pembaca layar.
//
// Kenapa ada bagian sumber (bukan render): chip hidup di dalam `app/page.tsx`
// yang butuh sesi login. Bagian lib diuji langsung karena di situlah urutan dan
// angka chip diputuskan.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

import { FEED_SCOPE_ACTION, feedChips } from "../lib/decision-feed";

const AKAR = path.resolve(__dirname, "..");
const HALAMAN = fs.readFileSync(path.join(AKAR, "app/page.tsx"), "utf8");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8");

/** Potongan JSX khusus tab Recommendations (batas: tab evidence). */
function tabRekomendasi(sumber: string): string {
  const mulai = sumber.indexOf('{tab === "recommendations" && (');
  const selesai = sumber.indexOf('tab === "evidence"', mulai);
  expect(mulai).toBeGreaterThan(-1);
  expect(selesai).toBeGreaterThan(mulai);
  return sumber.slice(mulai, selesai);
}

function luminans(hex: string): number {
  const h = hex.replace("#", "");
  const penuh = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const kanal = [0, 2, 4].map((i) => parseInt(penuh.slice(i, i + 2), 16) / 255);
  const linier = kanal.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * linier[0] + 0.7152 * linier[1] + 0.0722 * linier[2];
}

function kontras(a: string, b: string): number {
  const [x, y] = [luminans(a), luminans(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

function token(nama: string): string {
  const m = new RegExp(`--${nama}:\\s*([^;]+);`).exec(CSS);
  if (!m) throw new Error(`token --${nama} tidak ditemukan`);
  return m[1].trim();
}

describe("chip status Recommendation Feed", () => {
  it("lib: 'Perlu tindakan' selalu chip pertama, sisanya urut status", () => {
    const chip = feedChips([
      { status: "approved" },
      { status: "proposed" },
      { status: "proposed" },
      { status: "executed" },
    ]);
    expect(chip[0].id).toBe(FEED_SCOPE_ACTION);
    expect(chip[0].label).toBe("Perlu tindakan");
    // Urutan mengikuti STATUS_ORDER di lib/decision-feed.ts (proposed sebelum
    // approved sebelum executed) — bukan urutan yang saya karang di tes.
    expect(chip.slice(1).map((c) => c.id)).toEqual(["proposed", "approved", "executed"]);
  });

  it("lib: chip 'Perlu tindakan' bisa bernilai 0 — itulah kasus yang harus dinonaktifkan", () => {
    // `approved` termasuk ACTIONABLE_STATUSES (lib/topbar.ts), jadi untuk
    // mendapatkan chip "Perlu tindakan" bernilai 0 dipakai status yang memang
    // tidak menunggu tindakan: executed & rejected.
    const chip = feedChips([{ status: "executed" }, { status: "rejected" }]);
    const pertama = chip.find((c) => c.id === FEED_SCOPE_ACTION);
    expect(pertama).toBeDefined();
    expect(pertama!.count).toBe(0);
    // Statusnya tetap muncul dengan angka masing-masing, bukan dihilangkan.
    expect(chip.map((c) => c.count)).toEqual([0, 1, 1]);
  });

  it("markup: chip 0 dinonaktifkan, tetapi chip yang sedang aktif tidak terkunci", () => {
    const tab = tabRekomendasi(HALAMAN);
    expect(tab).toContain("const habis = chip.count === 0;");
    // `disabled` hanya bila kosong DAN bukan chip aktif: pengguna harus tetap
    // bisa melepas saringan yang kebetulan menyisakan 0 baris.
    expect(tab).toContain("disabled={habis && !aktif}");
  });

  it("markup: setiap chip punya nama berisi cakupan + jumlah untuk pembaca layar", () => {
    const tab = tabRekomendasi(HALAMAN);
    expect(tab).toContain("aria-label={`Saring daftar ke ${chip.label}: ${chip.count} rekomendasi`}");
    expect(tab).toContain("aria-pressed={aktif}");
    expect(tab).toContain('data-utama={chip.id === FEED_SCOPE_ACTION}');
  });

  it("pengumuman tetap satu live region (tidak menambah pesaing)", () => {
    // Komentar JSX ikut terpotong di sini: komentar yang MENYEBUT role="status"
    // bukan live region, dan tes ini menghitung elemen, bukan kata.
    const tab = tabRekomendasi(HALAMAN)
      .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")  // komentar JSX {/* … */}
      .replace(/\/\*[\s\S]*?\*\//g, "");        // komentar JS /* … */
    const live = tab.match(/role="status"/g) ?? [];
    expect(live).toHaveLength(1);
    expect(tab).toContain('aria-atomic="true"');
  });

  it("CSS: chip kosong tetap lolos kontras AA (tanpa opacity)", () => {
    const blok = CSS.match(/\.feed-filters > \.filter-chip:disabled,[\s\S]*?\}/);
    expect(blok, "aturan chip kosong tidak ditemukan").not.toBeNull();
    expect(blok![0]).toContain("background: var(--surface-sunken)");
    expect(blok![0]).toContain("color: var(--ink-subtle)");
    expect(blok![0]).not.toContain("opacity");
    const rasio = kontras(token("ink-subtle"), token("surface-sunken"));
    expect(rasio).toBeGreaterThanOrEqual(4.5);
  });

  it("CSS: angka chip utama ditebalkan tanpa warna baru, dan chip tetap membungkus", () => {
    expect(CSS).toMatch(/\.feed-filters > \.filter-chip\[data-utama="true"\] \.legend-count\s*\{[^}]*font-weight: 700/);
    const filters = CSS.match(/\.feed-filters \{([^}]*)\}/);
    const adaWrap = (CSS.match(/\.feed-filters \{([^}]*)\}/g) ?? []).some((b) => b.includes("flex-wrap: wrap"));
    expect(adaWrap || filters, ".feed-filters harus membungkus baris (flex-wrap)").toBeTruthy();
    expect(CSS).toMatch(/\.feed-filters \{[\s\S]{0,120}?flex-wrap: wrap/);
  });
});
