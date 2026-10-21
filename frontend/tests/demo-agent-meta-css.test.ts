/**
 * Tujuh kartu agen di Demo Control berbagi satu baris: dengan dua kolom di
 * dalam kartu, nilai pendek pun pecah jadi dua baris ("268 md" -> "268"/"md",
 * "1 peringatan" -> "1"/"peringatan") dan panel terbaca seperti layout rusak.
 *
 * Tes ini mengunci bentuk CSS-nya, bukan hanya niatnya: satu kolom per kartu
 * dan nilai tidak boleh dipotong di tengah.
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

describe("meta kartu agen", () => {
  it("satu kolom per kartu, bukan dua", () => {
    const isi = blok(".dc-agent-meta");
    expect(isi).toContain("flex-direction: column");
    expect(isi).not.toMatch(/flex-direction:\s*row/);
  });

  it("nilai durasi/peringatan tidak dipotong di tengah", () => {
    expect(blok(".dc-agent-meta dd")).toContain("white-space: nowrap");
  });
});
