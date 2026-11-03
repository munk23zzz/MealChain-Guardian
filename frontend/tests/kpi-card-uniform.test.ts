// Bentuk kartu KPI seragam, 4 per baris (permintaan pemilik, 29 Okt 2026).
//
// Ini tes CSS, bukan tes render: yang dijaga adalah ATURAN tata letak yang
// membuat delapan kartu berbentuk sama. Tanpa `grid-auto-rows: 1fr` baris 1 dan
// baris 2 berbeda tinggi (terukur 299 px vs 333 px sebelum perbaikan), dan
// tanpa `margin-top: auto` baris status tidak rata di dasar kartu.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  join(process.cwd(), "app", "theme-ext.css"),
  "utf8"
);

function blok(selector: string): string {
  const i = css.indexOf(selector + " {");
  if (i === -1) return "";
  const end = css.indexOf("}", i);
  return css.slice(i, end + 1);
}

describe("kartu KPI seragam", () => {
  it("grid memaksa semua baris setinggi baris tertinggi", () => {
    expect(blok(".kpi-grid")).toMatch(/grid-auto-rows:\s*1fr/);
  });

  it("kartu mengisi sel grid, bukan mengikuti isinya sendiri", () => {
    expect(blok(".kpi-grid > .kpi-card")).toMatch(/height:\s*100%/);
  });

  it("baris status menempel di dasar kartu", () => {
    expect(blok(".kpi-card-flags")).toMatch(/margin-top:\s*auto/);
  });

  it("tidak memotong alasan no_data demi tinggi seragam", () => {
    // Alasan adalah informasi wajib; tinggi yang menyesuaikan isi, bukan
    // sebaliknya. Clamp hanya boleh ada pada deskripsi satu baris.
    expect(blok(".kpi-reason")).not.toMatch(/line-clamp/);
    expect(blok(".kpi-reason")).not.toMatch(/max-height/);
  });
});
