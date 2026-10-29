// L6 redesign Location Network (30 Okt 2026): target sentuh 44 px, cincin fokus
// yang terlihat, dan gerak yang bisa dimatikan.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const AKAR = path.resolve(__dirname, "..");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8")
  .replace(/\/\*[\s\S]*?\*\//g, "");
const BOARD = fs.readFileSync(path.join(AKAR, "components/LocationNetworkBoard.tsx"), "utf8");
const PANEL = fs.readFileSync(path.join(AKAR, "components/SupplyDemandPanel.tsx"), "utf8");

/** Blok @media pertama yang memuat penanda. */
function media(pembuka: string, penanda: string): string {
  let i = CSS.indexOf(pembuka);
  while (i > -1) {
    const buka = CSS.indexOf("{", i);
    let d = 0;
    let akhir = -1;
    for (let j = buka; j < CSS.length; j += 1) {
      if (CSS[j] === "{") d += 1;
      else if (CSS[j] === "}") {
        d -= 1;
        if (d === 0) { akhir = j; break; }
      }
    }
    const isi = CSS.slice(buka, akhir);
    if (isi.includes(penanda)) return isi;
    i = CSS.indexOf(pembuka, akhir);
  }
  throw new Error(`tidak ada ${pembuka} berisi ${penanda}`);
}

describe("L6 — aksesibilitas & gerak halaman Location Network", () => {
  const sentuh = media("@media (pointer: coarse), (max-width: 760px)", ".commodity-pill");

  it("empat kontrol utama punya target ≥ 44 px di layar sentuh", () => {
    expect(sentuh).toMatch(/\.commodity-filters \.commodity-pill \{\s*min-height: 44px/);
    expect(sentuh).toMatch(/\.network-table button \{\s*min-height: 44px/);
    expect(sentuh).toMatch(/\.network-detail button \{[^}]*min-height: 44px/);
    expect(sentuh).toMatch(/\.location-retry \{\s*min-height: 44px/);
    // Tombol "Coba lagi" benar-benar memakai kelas itu.
    expect(BOARD).toContain("location-retry");
  });

  it("cincin fokus tidak dihapus, tapi digambar", () => {
    // Kemunculan TERAKHIR: grup fokus yang saya tambahkan (sebelumnya sudah ada
    // grup fokus global untuk pill/chip, tanpa tombol papan lokasi).
    const mulai = CSS.lastIndexOf(".commodity-pill:focus-visible");
    const blok = CSS.slice(mulai, CSS.indexOf("@media (prefers-reduced-motion: reduce)", mulai));
    expect(blok).toContain(".commodity-pill:focus-visible");
    expect(blok).toContain(".network-table button:focus-visible");
    expect(blok).toContain(".network-detail button:focus-visible");
    expect(blok).toContain(".location-retry:focus-visible");
    expect(blok).toContain("outline: 2px solid");
    expect(blok).toContain("outline-offset: 2px");
    expect(blok).not.toContain("outline: none");
  });

  it("gerak baris dimatikan saat pengguna meminta reduced-motion", () => {
    const blok = media("@media (prefers-reduced-motion: reduce)", ".network-table tr");
    expect(blok).toContain(".network-table tr");
    expect(blok).toContain(".network-table td");
    expect(blok).toContain('[data-klik-baris="true"]');
    expect(blok).toContain("transition: none");
  });

  it("satu baris hanya punya satu tombol pembuka, dengan aria-expanded", () => {
    // Tombol nama lokasi (bukan karakter ▸/▾) + aria-controls ke kartu rincian.
    expect(BOARD).toContain("aria-expanded={aktif}");
    expect(BOARD).toContain('aria-controls="rincian-lokasi"');
    // Tombol baris memakai kelas CSS module, jadi ukurannya diatur modul.
    expect(BOARD).toContain("styles.rowButton");
    // Panel rincian tidak menambah tombol buka kedua di dalam baris.
    expect(PANEL).not.toContain("aria-expanded");
  });
});
