// L5 — "Rencana alih" & "Limbah" satu keluarga bentuk.
//
// Yang dijaga:
//   * Kedua kartu memakai kepala yang sama: judul + pil jumlah + SATU kalimat.
//     Kalimat yang dulu jadi catatan kaki di bawah tabel Rencana alih pindah ke
//     kepala, supaya kedua kartu dibaca dengan urutan yang sama.
//   * Limbah bukan lagi tiga baris fakta label/nilai, melainkan tiga angka
//     sejajar (`.card-figures`). Angka yang tidak tersedia tetap "—" + kata
//     "belum tercatat" — tidak pernah berubah jadi 0 kg.
//   * Tidak ada angka baru: semua nilai berasal dari GET /waste/summary dan
//     GET /surplus/allocations yang sudah dipakai.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import LocationNetworkBoard from "../components/LocationNetworkBoard";
import { wasteRingkas, wasteSentence } from "../lib/surplus";
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

const BARIS = [
  lokasi({ location: "Jakarta" }),
  lokasi({
    location: "Cianjur",
    region: "Jawa Barat",
    status: "surplus",
    supply_kg: 2292,
    demand_kg: 900,
    shortage_kg: 0,
    surplus_kg: 1392,
  }),
];

const PLAN_TIGA = {
  available: true,
  min_surplus_kg: 150,
  pairs: [
    { from: "Cianjur", to: "Jakarta", kg: 685, distance_km: 76, cost_share_pct: 0.8 },
    { from: "Bogor", to: "Jakarta", kg: 420, distance_km: 61, cost_share_pct: 0.9 },
    { from: "Bandung", to: "Jakarta", kg: 300, distance_km: 148, cost_share_pct: 1.1 },
  ],
};

const WASTE_PENUH = {
  recorded: { available: true, kg: 240, events: 6 },
  diverted: { available: true, kg: 160, events: 4 },
  unassigned: { available: true, kg: 80, events: 2 },
};

const WASTE_SEBAGIAN = {
  recorded: { available: true, kg: 240, events: 6 },
  diverted: { available: false, kg: null, events: 0 },
  unassigned: { available: true, kg: 80, events: 2 },
};

function render(plan: unknown = PLAN_TIGA, waste: unknown = WASTE_PENUH): string {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={BARIS}
      commodity="telur"
      commodities={["telur", "ayam"]}
      onCommodityChange={() => {}}
      selected={null}
      onSelect={() => {}}
      detail={null}
      batches={[]}
      decisions={[]}
      plan={plan}
      waste={waste}
      wasteDays={30}
      snapshot="Data per 29 Okt 2026"
    />
  );
}

/** Potongan satu kartu berdasarkan id jangkarnya. */
function kartu(html: string, id: string): string {
  const mulai = html.indexOf(`id="${id}"`);
  expect(mulai).toBeGreaterThan(-1);
  const akhir = html.indexOf("</article>", mulai);
  return html.slice(mulai, akhir);
}

describe("L5 — kepala 'Rencana alih' dan 'Limbah' sepadan", () => {
  it("Rencana alih: judul + pil jumlah pasangan", () => {
    const isi = kartu(render(), "network-alih");
    expect(isi).toContain("<h2>Rencana alih</h2>");
    expect(isi).toContain('class="count-pill"');
    expect(isi).toContain("3 pasangan");
  });

  it("Rencana alih: kalimat ambang ada SEBELUM tabel, bukan catatan kaki", () => {
    const isi = kartu(render(), "network-alih");
    const kalimat = isi.indexOf("Hanya surplus ≥ 150 kg per lokasi.");
    const tabel = isi.indexOf('data-testid="allocation-table"');
    expect(kalimat).toBeGreaterThan(-1);
    expect(tabel).toBeGreaterThan(-1);
    expect(kalimat).toBeLessThan(tabel);
  });

  it("Rencana alih: satu pasangan tetap ditulis apa adanya", () => {
    const plan = { available: true, min_surplus_kg: 200, pairs: [PLAN_TIGA.pairs[0]] };
    const isi = kartu(render(plan), "network-alih");
    expect(isi).toContain("1 pasangan");
    expect(isi).toContain("Hanya surplus ≥ 200 kg per lokasi.");
  });

  it("Limbah: judul tanpa periode, periode pindah ke pil", () => {
    const isi = kartu(render(), "network-limbah");
    expect(isi).toContain("<h2>Limbah</h2>");
    expect(isi).not.toContain("Limbah · ");
    expect(isi).toContain("30 hari");
  });

  it("Limbah: satu kalimat ringkas, bukan tiga baris fakta", () => {
    const isi = kartu(render(), "network-limbah");
    expect(isi).toContain(
      "240 kg tercatat · 160 kg dialihkan ke mitra · 80 kg tanpa mitra — 30 hari terakhir."
    );
    expect(isi).not.toContain("fact-list");
  });

  it("Limbah: tiga angka sejajar dengan label dan petunjuk peristiwa", () => {
    const isi = kartu(render(), "network-limbah");
    expect(isi).toContain('class="card-figures"');
    const angka = [...isi.matchAll(/data-figure="([^"]+)"/g)].map((m) => m[1]);
    expect(angka).toEqual(["tercatat", "dialihkan", "tanpa-mitra"]);
    expect(isi).toContain("240 kg");
    expect(isi).toContain("160 kg");
    expect(isi).toContain("80 kg");
    expect(isi).toContain("6 peristiwa");
    expect(isi).toContain("2 peristiwa");
  });
});

describe("L5 — angka yang tidak ada tetap '—' + kata, bukan 0 kg", () => {
  it("angka kosong memakai tanda pisah dan kata 'belum tercatat'", () => {
    const isi = kartu(render(PLAN_TIGA, WASTE_SEBAGIAN), "network-limbah");
    expect(isi).toContain("—");
    expect(isi).toContain("belum tercatat");
    expect(isi).not.toMatch(/\b0 kg\b/);
  });

  it("kalimat ikut jujur saat satu angka tidak tersedia", () => {
    const isi = kartu(render(PLAN_TIGA, WASTE_SEBAGIAN), "network-limbah");
    expect(isi).toContain("pengalihan ke mitra belum tercatat");
    expect(isi).not.toMatch(/\b0 kg\b/);
  });

  it("tanpa angka sama sekali: satu kalimat, tanpa deret angka", () => {
    const isi = kartu(render(PLAN_TIGA, { recorded: { available: false, kg: null, events: 0 } }), "network-limbah");
    expect(isi).toContain("Belum dicatat.");
    expect(isi).not.toContain('class="card-figures"');
    expect(isi).not.toMatch(/\b0 kg\b/);
  });

  it("wasteRingkas menandai angka kosong dengan kata, bukan nilai palsu", () => {
    const baris = wasteRingkas(WASTE_SEBAGIAN);
    expect(baris.map((b) => b.value)).toEqual(["240 kg", "—", "80 kg"]);
    expect(baris[1].hint).toBe("belum tercatat");
  });

  it("wasteSentence mengikuti ketersediaan tiap angka", () => {
    expect(wasteSentence(wasteRingkas(WASTE_PENUH), 30)).toBe(
      "240 kg tercatat · 160 kg dialihkan ke mitra · 80 kg tanpa mitra — 30 hari terakhir."
    );
    expect(wasteSentence(wasteRingkas(WASTE_SEBAGIAN), 7)).toBe(
      "240 kg tercatat · pengalihan ke mitra belum tercatat · 80 kg tanpa mitra — 7 hari terakhir."
    );
    expect(wasteSentence([], 30)).toBe("");
  });
});

describe("L5 — kontrak CSS tiga angka sejajar", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  it("deret angka memakai grid tiga kolom dan turun ke satu kolom di layar sempit", () => {
    expect(css).toMatch(/\.card-figures \{[^}]*display: grid/);
    expect(css).toMatch(/\.card-figures \{[^}]*grid-template-columns: repeat\(3/);
    const sempit = css.slice(css.indexOf("@media (max-width: 560px)"));
    expect(sempit).toMatch(/\.card-figures \{[^}]*grid-template-columns: 1fr/);
  });

  it("label angka memakai token font terkecil, bukan ukuran mentah", () => {
    expect(css).toMatch(/\.card-figure-label \{[^}]*font-size: var\(--fs-1\)/);
  });

  it("kalimat kepala tidak memakai radius atau warna mentah", () => {
    const aturan = css.slice(css.indexOf(".board-card-sentence {"));
    const blok = aturan.slice(0, aturan.indexOf("}"));
    expect(blok).not.toMatch(/border-radius:\s*\d/);
    expect(blok).not.toMatch(/#[0-9A-Fa-f]{3,6}/);
  });
});
