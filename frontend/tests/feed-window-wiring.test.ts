/**
 * Wiring periode di tab Recommendations (24 Okt 2026).
 *
 * Halaman konsol adalah komponen monolitik yang butuh sesi + token untuk
 * dirender, jadi kontraknya dipaku lewat sumber — pola yang sama dengan tes
 * `kpi-wiring`. Yang dijaga: kontrol periode memakai bahasa visual yang sudah
 * ada (`.kpi-period`), aksesibel (`aria-pressed`), mengirim jendela ke API,
 * dan mengembalikan pengguna ke halaman 1 saat jendela berganti.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const pageSrc = readFileSync(join(process.cwd(), "app/page.tsx"), "utf8").replace(
  /\r\n/g,
  "\n",
);
const cssSrc = readFileSync(join(process.cwd(), "app/globals.css"), "utf8");

describe("feed rekomendasi — pemilih periode", () => {
  it("memakai kontrol periode yang sama dengan KPI", () => {
    expect(pageSrc).toContain("className=\"kpi-period feed-period\"");
    expect(pageSrc).toContain("kpi-period-pill");
  });

  it("tombol asli dengan aria-pressed, bukan div yang diklik", () => {
    const blok = pageSrc.slice(pageSrc.indexOf("Periode rekomendasi"));
    expect(blok.slice(0, 1400)).toContain("aria-pressed={aktif}");
    expect(blok.slice(0, 1400)).toContain("type=\"button\"");
  });

  it("mengirim jendela ke hook dan mengembalikan halaman ke 1", () => {
    expect(pageSrc).toContain("useDecisions(\n    token,\n    identityScope,\n    feedWindow,");
    const blok = pageSrc.slice(pageSrc.indexOf("Periode rekomendasi"));
    expect(blok.slice(0, 1400)).toContain("setFeedWindow(w.key)");
    expect(blok.slice(0, 1400)).toContain("setFeedPage(1)");
  });

  it("daftar feed memakai hasil berjendela, bukan riwayat penuh", () => {
    expect(pageSrc).toContain("feedChips(feedWindowDecisions)");
    expect(pageSrc).toContain("feedVisible(feedWindowDecisions, feedFilter)");
  });

  it("keadaan aktif terisi aksen (bukan hanya garis) — kontras teks aman", () => {
    expect(cssSrc).toContain(".kpi-period-pill.is-active {");
    const blok = cssSrc.slice(cssSrc.indexOf(".kpi-period-pill.is-active {"));
    expect(blok.slice(0, 800)).toContain("background: var(--primary)");
    expect(blok.slice(0, 800)).toContain("color: var(--surface)");
  });

  it("chip periode membungkus (tidak terpotong satu baris)", () => {
    const blok = cssSrc.slice(cssSrc.indexOf(".kpi-period {"));
    expect(blok.slice(0, 200)).toContain("flex-wrap: wrap");
  });
});
