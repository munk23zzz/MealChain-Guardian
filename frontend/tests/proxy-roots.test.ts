import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Kontrak proxy Next ↔ lib/api.ts.
//
// Kalau NEXT_PUBLIC_API_URL kosong (docker-compose.override.yml) semua panggilan
// API memakai path relatif dan bergantung pada rewrites di next.config.js. Root
// yang tidak terdaftar di sana jatuh ke router Next sendiri → 404 HTML, bukan
// JSON — dan request() melempar "Respons bukan JSON dari /<root>...".
// Ini yang dulu terjadi pada /admin/* (tab Pengaturan, S4-11).

const akar = join(__dirname, "..");

const POLA_REQUEST = /request\(\s*[`"]\/([a-z0-9-]+)/;

function unik(nilai: string[]): string[] {
  const hasil: string[] = [];
  for (let i = 0; i < nilai.length; i++) {
    if (hasil.indexOf(nilai[i]) === -1) hasil.push(nilai[i]);
  }
  return hasil;
}

function rootDariApiClient(): string[] {
  const src = readFileSync(join(akar, "lib", "api.ts"), "utf8");
  const baris = src.split("\n");
  const hasil: string[] = [];
  // request("/foo/...") dan request(`/foo/...`) → ambil segmen pertama.
  // Loop indeks (bukan for..of atas iterator): target tsc proyek ini belum
  // menyalakan downlevelIteration.
  for (let i = 0; i < baris.length; i++) {
    const m = POLA_REQUEST.exec(baris[i]);
    if (m) hasil.push(m[1]);
  }
  return unik(hasil).sort();
}

function rootDariNextConfig(): string[] {
  const src = readFileSync(join(akar, "next.config.js"), "utf8");
  const awal = src.indexOf("const API_ROOTS = [");
  if (awal === -1) throw new Error("API_ROOTS tidak ditemukan di next.config.js");
  const akhir = src.indexOf("];", awal);
  const blok = src.slice(awal, akhir === -1 ? undefined : akhir);
  const hasil: string[] = [];
  const pola = /"([a-z0-9-]+)"/g;
  let m: RegExpExecArray | null = pola.exec(blok);
  while (m !== null) {
    hasil.push(m[1]);
    m = pola.exec(blok);
  }
  return unik(hasil).sort();
}

describe("kontrak proxy API Next", () => {
  it("setiap root yang dipanggil lib/api.ts punya rewrite di next.config.js", () => {
    const dipakai = rootDariApiClient();
    const terdaftar = rootDariNextConfig();
    const hilang = dipakai.filter((r) => !terdaftar.includes(r));
    expect(hilang).toEqual([]);
  });

  it("menemukan root nyata dari lib/api.ts (penjaga tes itu sendiri)", () => {
    const dipakai = rootDariApiClient();
    // Kalau regex gagal, tes di atas lolos secara palsu.
    expect(dipakai).toContain("auth");
    expect(dipakai).toContain("admin");
    expect(dipakai.length).toBeGreaterThan(5);
  });
});
