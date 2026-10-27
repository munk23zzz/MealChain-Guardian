/**
 * Grid panel Agent Log kini menampung SEMBILAN kartu (tujuh worker +
 * supervisor + verifier). Empat kolom menyisakan satu kartu sendirian di baris
 * terakhir (4+4+1), dan kartu sendirian itu memanjang selebar grid sehingga
 * terbaca seperti kartu rusak. Tiga kolom memberi 3x3 yang rapi.
 *
 * Tes ini mengunci bentuk CSS-nya karena tes teks tidak bisa melihat tata
 * letak: jumlah elemen di DOM bisa benar sementara barisnya berantakan.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const akar = path.resolve(__dirname, "..");
const css = readFileSync(path.join(akar, "app/globals.css"), "utf8");

function blok(selektor: string): string {
  const pola = new RegExp(`^\\${selektor}\\s*\\{([^}]*)\\}`, "m");
  const hasil = pola.exec(css);
  expect(hasil, `blok ${selektor} tidak ditemukan`).not.toBeNull();
  return hasil![1];
}

describe("grid sembilan agen di Agent Log", () => {
  it("tiga kolom di desktop — sembilan kartu jadi 3x3, bukan 4+4+1", () => {
    expect(blok(".swarm-grid")).toMatch(
      /grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/
    );
  });

  it("kartu boleh membungkus isi panjang, tidak meluber", () => {
    const isi = css.match(/^\.swarm-card,\s*\n\.swarm-supervisor\s*\{([^}]*)\}/m);
    expect(isi, "blok .swarm-card/.swarm-supervisor tidak ditemukan").not.toBeNull();
    expect(isi![1]).toContain("min-width: 0");
    expect(isi![1]).toContain("overflow-wrap: anywhere");
  });
});
