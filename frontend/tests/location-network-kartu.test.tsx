// L3 — tabel lokasi terbaca sebagai papan, bukan dinding.
//
// Yang dijaga:
//   * Setiap sel membawa `data-label` yang SAMA dengan judul kolomnya, supaya
//     kartu di layar sempit tetap menyebut nama kolomnya.
//   * Baris memakai pola disclosure yang benar: `aria-expanded` + `aria-controls`,
//     bukan `aria-pressed` (tombol buka bukan tombol tekan).
//   * Selisih tidak dibedakan warna saja: ada penanda bentuk di samping kata
//     ("kurang 780 kg" + "−").
//   * Di ≤760 px tabel berubah jadi kartu (thead hilang, wadah tidak menggeser).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import LocationNetworkBoard from "../components/LocationNetworkBoard";
import type { BalanceMapLocation } from "../lib/overview-format";

const JAM = 3_600_000;
const SEKARANG = Date.now();

function lokasi(over: Partial<BalanceMapLocation> & { location: string }): BalanceMapLocation {
  return {
    region: "DKI Jakarta",
    latitude: -6.2,
    longitude: 106.8,
    supply_kg: 2150,
    demand_kg: 2930,
    status: "shortage",
    shortage_kg: 780,
    surplus_kg: 0,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: new Date(SEKARANG - JAM).toISOString(),
    demand_recorded_at: new Date(SEKARANG - JAM).toISOString(),
    ...over,
  } as BalanceMapLocation;
}

const JAKARTA = lokasi({ location: "Jakarta" });
const CIANJUR = lokasi({
  location: "Cianjur",
  region: "Jawa Barat",
  status: "surplus",
  supply_kg: 2292,
  demand_kg: 900,
  shortage_kg: 0,
  surplus_kg: 1392,
});
const MEDAN = lokasi({
  location: "Medan",
  region: "Sumatera Utara",
  status: "balanced",
  supply_kg: 300,
  demand_kg: 300,
  shortage_kg: 0,
  surplus_kg: 0,
});

function renderBoard(over: Partial<Parameters<typeof LocationNetworkBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={[JAKARTA, CIANJUR, MEDAN]}
      commodity="telur"
      selected={null}
      onSelect={() => {}}
      detail={null}
      {...over}
    />
  );
}

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

/** Blok @media (max-width: 760px) yang memuat `.network-table`. */
function blokKartu(): string {
  const awal = css.indexOf("@media (max-width: 760px)");
  let i = awal;
  while (i !== -1) {
    const buka = css.indexOf("{", i);
    let dalam = 1;
    let j = buka + 1;
    while (j < css.length && dalam > 0) {
      if (css[j] === "{") dalam += 1;
      if (css[j] === "}") dalam -= 1;
      j += 1;
    }
    const blok = css.slice(i, j);
    if (blok.includes(".network-table")) return blok;
    i = css.indexOf("@media (max-width: 760px)", j);
  }
  return "";
}

describe("L3 — tabel lokasi: label sel dan pola buka-baris", () => {
  it("setiap sel membawa data-label yang sama dengan judul kolomnya", () => {
    const html = renderBoard();
    for (const label of ["Lokasi", "Wilayah", "Selisih"]) {
      expect(html).toContain(`data-label="${label}"`);
    }
  });

  it("kolom kondisional memakai label yang sama dengan kepalanya", () => {
    const html = renderBoard({
      batches: [
        {
          location: "Jakarta",
          commodity: "telur",
          quantity_kg: 10,
          safety_status: "PASS",
          usable_until: new Date(SEKARANG + 26 * JAM).toISOString(),
        },
      ],
      decisions: [{ status: "pending_approval", target_location_name: "Jakarta" }],
    });
    expect(html).toContain(">Batch ≤7h</th>");
    expect(html).toContain('data-label="Batch ≤7h"');
    expect(html).toContain('data-label="Rekomendasi"');
  });

  it("tombol baris memakai aria-expanded + aria-controls, bukan aria-pressed", () => {
    const html = renderBoard({ selected: "Jakarta" });
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain('aria-controls="rincian-lokasi"');
    expect((html.match(/aria-expanded="true"/g) ?? []).length).toBe(1);
    expect((html.match(/aria-expanded="false"/g) ?? []).length).toBe(2);
    expect(html).not.toContain("aria-pressed");
  });

  it("selisih ditandai bentuk + kata, bukan warna saja", () => {
    const html = renderBoard();
    expect(html).toMatch(/data-mark="shortage"[^>]*>−</);
    expect(html).toMatch(/data-mark="surplus"[^>]*>\+</);
    expect(html).toMatch(/data-mark="balanced"[^>]*>=</);
    expect(html).toContain("kurang 780 kg");
    expect(html).toContain("lebih 1.392 kg");
  });

  it("tabel membawa kelas papan sendiri supaya kartu tidak menimpa tabel lain", () => {
    const html = renderBoard();
    expect(html).toContain('class="location-table network-table"');
    expect(html).toContain('class="board-table-wrap network-table-wrap"');
  });
});

describe("L3 — kartu lokasi di layar sempit", () => {
  it("ada blok media 760 px untuk papan lokasi", () => {
    expect(blokKartu()).not.toBe("");
  });

  it("kepala tabel disembunyikan dan sel jadi baris berlabel", () => {
    const blok = blokKartu();
    expect(blok).toMatch(/\.network-table thead \{\s*display: none/);
    expect(blok).toMatch(/\.network-table td::before \{\s*content: attr\(data-label\)/);
  });

  it("wadah tidak lagi menggeser mendatar di papan lokasi", () => {
    // Dua kelas wajib: `.board-table-wrap` memaksa overflow-x auto dan selektor
    // satu kelas kalah urutan.
    expect(blokKartu()).toMatch(/\.board-table-wrap\.network-table-wrap \{[^}]*overflow: visible/);
  });

  it("tabel lain tidak ikut jadi kartu", () => {
    const blok = blokKartu();
    // Semua selektor di blok ini harus ber-scope `.network-table*`.
    const selektor = Array.from(blok.matchAll(/^\s{2}([^{}\n]+)\{/gm), (m) => m[1].trim());
    for (const sel of selektor) {
      // `.network-detail*` = dossier di dalam baris lokasi (L4): ia memang
      // menumpang blok media yang sama, tetapi tetap ter-scope ke halaman ini.
      expect(sel, `selektor tanpa scope: ${sel}`).toMatch(/network-table|network-detail/);
    }
  });
});
