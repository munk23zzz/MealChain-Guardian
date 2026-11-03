import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak token alias `--primary` / `--danger`.
 *
 * Kenapa ada: blok agenda, pil periode KPI, dan pil urutan papan memakai
 * `--primary` dengan cadangan hex teal warisan tema lama (#005C55), padahal
 * token itu tidak pernah dideklarasikan di `:root` — jadi cadangan itulah yang
 * benar-benar tampil. Terukur di aplikasi hidup: pil "24 jam" (KPI) dan
 * "Paling mendesak" (Pemasok) berwarna rgb(0, 92, 85), sementara
 * `docs/design.md` §376 menetapkan keadaan terpilih = `--accent-strong`
 * (#2563EB). Hal yang sama untuk `--danger` (#B42318 vs `--status-danger`
 * #C62828). Keduanya hanya bisa dijaga lewat deklarasi CSS, jadi diuji di sini.
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

describe("token alias --primary / --danger", () => {
  it("mendeklarasikan --primary sebagai alias --accent-strong", () => {
    expect(css).toMatch(/--primary:\s*var\(--accent-strong\)/);
  });

  it("mendeklarasikan --danger sebagai alias --status-danger", () => {
    expect(css).toMatch(/--danger:\s*var\(--status-danger\)/);
  });

  it("tidak lagi memakai cadangan hex teal warisan pada --primary", () => {
    // Deklarasi, bukan komentar: komentar yang menyebut alasan penghapusan
    // tidak boleh memerahkan tes ini.
    expect(css).not.toMatch(/var\(\s*--primary\s*,\s*#005c55/i);
  });

  it("tidak lagi memakai cadangan hex merah warisan pada --danger", () => {
    expect(css).not.toMatch(/var\(\s*--danger\s*,\s*#b42318/i);
  });

  it("keadaan terpilih agenda memakai --primary tanpa cadangan hex", () => {
    const aktif = /^\.agenda-cell-active\s*\{([^}]*)\}/m.exec(css);
    expect(aktif).not.toBeNull();
    expect(aktif![1]).toContain("border-color: var(--primary)");
    expect(aktif![1]).toContain("color-mix(in srgb, var(--primary)");
  });

  it("pil keadaan terpilih KPI & papan memakai --primary tanpa cadangan hex", () => {
    for (const sel of [".kpi-period-pill.is-active", ".board-sort-pill.is-active"]) {
      const blok = new RegExp(`^${sel.replace(/\./g, "\\.")}\\s*\\{([^}]*)\\}`, "ms").exec(css);
      expect(blok, `blok ${sel} tidak ditemukan`).not.toBeNull();
      expect(blok![1]).toContain("var(--primary)");
      expect(blok![1]).not.toMatch(/#005c55/i);
    }
  });
});
