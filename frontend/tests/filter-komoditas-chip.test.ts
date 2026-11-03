import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Gugus filter "Komoditas" memakai bahasa chip filter yang sama dengan
 * Recommendations (29 Okt 2026, pilihan pemilik).
 *
 * Sebelumnya gugus ini dibungkus kartu putih sendiri (`.filter-card`) dengan
 * pil 24 px/13 px-500, sementara blok filter di Recommendations berupa chip
 * 32 px/13 px-600 langsung di atas latar halaman. Dua bahasa untuk satu jenis
 * kontrol. Sekarang satu bahasa: tanpa kartu putih, chip 32 px.
 *
 * Yang diuji adalah KONTRAK, bukan tampilan: kelas pembungkus di sumber
 * komponen, dan deklarasi CSS untuk chip di dalamnya. jsdom tidak punya tata
 * letak, jadi angka pikselnya dibuktikan di aplikasi hidup.
 */
const AKAR = join(__dirname, "..");

function baca(berkas: string): string {
  return readFileSync(join(AKAR, berkas), "utf8");
}

function blokCss(selektor: string): string {
  const isi = baca("app/globals.css");
  // Selektor bisa berada di daftar (`a,\n a:hover { ... }`), jadi setelah nama
  // selektor izinkan sisa daftar sebelum kurawal buka.
  const pola = new RegExp(
    `(?:^|\\n)\\s*${selektor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^{};]*\\{([^}]*)\\}`
  );
  const cocok = pola.exec(isi);
  expect(cocok, `blok ${selektor} tidak ada di globals.css`).toBeTruthy();
  return cocok![1];
}

describe("gugus filter komoditas tidak lagi berupa kartu sendiri", () => {
  for (const berkas of [
    "components/LocationNetworkBoard.tsx",
    "components/SurplusBoard.tsx",
    "app/page.tsx",
  ]) {
    it(`${berkas}: memakai .commodity-filters tanpa .filter-card`, () => {
      const src = baca(berkas);
      expect(src).toContain("commodity-filters");
      // Kartu putih di dalam kartu = bahasa kedua yang ingin dihapus.
      expect(src).not.toContain("commodity-filters filter-card");
    });
  }
});

describe("pembungkus filter bukan permukaan kartu", () => {
  it("tanpa latar, garis, atau padding kartu", () => {
    const isi = blokCss(".commodity-filters");
    expect(isi).not.toContain("background:");
    expect(isi).not.toContain("border");
    expect(isi).not.toContain("padding:");
  });
});

describe("chip di dalam gugus filter memakai geometri chip Recommendations", () => {
  it("32 px tinggi, 13 px/600, padding 5px 13px", () => {
    const isi = blokCss(".commodity-filters .commodity-pill");
    expect(isi).toContain("min-height: 32px");
    expect(isi).toContain("padding: 5px 13px");
    expect(isi).toContain("font-size: var(--fs-2)");
    expect(isi).toContain("font-weight: 600");
  });

  it("keadaan aktif mengisi aksen dan menang atas aturan dasar", () => {
    const isi = blokCss(".commodity-filters .commodity-pill-active");
    expect(isi).toContain("background: var(--accent-strong)");
    expect(isi).toContain("color: var(--ink-inverse)");
  });
});
