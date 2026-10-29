// L4 — rincian lokasi sebagai dossier DI BAWAH barisnya.
//
// Yang dijaga:
//   * Rincian bukan kartu ketiga di luar tabel: ia baris penuh (`colSpan` = jumlah
//     kolom) tepat SETELAH baris lokasi yang dibuka, jadi konteks barisnya tidak
//     hilang dari layar saat dibuka.
//   * `colSpan` mengikuti kolom kondisional (3 / 4 / 5), bukan angka mati.
//   * Angka "Selisih" dipromosikan (`data-lead`) seperti strip ringkasan halaman
//     Pemasok; tiga angka lain tetap sama.
//   * Tabel batch di dalam rincian menjadi kartu berlabel di ≤760 px, jadi rincian
//     tidak menambah geseran mendatar yang baru.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import LocationNetworkBoard from "../components/LocationNetworkBoard";
import type { BalanceMapLocation } from "../lib/overview-format";
import type { SupplyDemandDetail } from "../lib/supply-demand";

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

const DETAIL: SupplyDemandDetail = {
  location: "Jakarta",
  commodity: "telur",
  supply: { quantityKg: 2150, recordedAt: new Date(SEKARANG - JAM).toISOString(), source: "sap_rpt_1_6" },
  demand: { quantityKg: 2930, neededBy: new Date(SEKARANG + JAM).toISOString() },
  forecast: null,
  gap: { text: "kurang 780 kg", tone: "danger" },
  notes: [],
  batches: [
    {
      id: "8ae7976a-59f3-4ced-a9bc-607409a7dbb8",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 120,
      safety_status: "PASS",
      quarantine_status: null,
      usable_until: new Date(SEKARANG + 26 * JAM).toISOString(),
    },
  ],
  batchSummary: { total: 1, pass: 1, fail: 0, quarantined: 0, others: [] },
  batchesTruncated: false,
  batchCap: 500,
};

const BATCH_DEKAT = [
  {
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 10,
    safety_status: "PASS",
    usable_until: new Date(SEKARANG + 26 * JAM).toISOString(),
  },
];

function renderBoard(over: Partial<Parameters<typeof LocationNetworkBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={[JAKARTA, CIANJUR]}
      commodity="telur"
      selected="Jakarta"
      onSelect={() => {}}
      detail={DETAIL}
      {...over}
    />
  );
}

/**
 * Isi <tbody> tabel LOKASI saja.
 *
 * Rincian memuat tabel batch di dalam selnya, jadi `</tbody>` pertama di dalam
 * rentang itu milik tabel batch — penutup yang dicari adalah yang langsung
 * diikuti `</table>` tabel luar.
 */
function tbody(html: string): string {
  const mulai = html.indexOf('<table class="location-table network-table"');
  const buka = html.indexOf("<tbody>", mulai);
  // Penutup tabel luar: `</tbody>` yang diikuti `</table>` (spasi/indentasi
  // dibiarkan), bukan `</tbody>` milik tabel batch di dalam rincian.
  const sisa = html.slice(buka);
  const cocok = sisa.match(/<\/tbody>\s*<\/table>/);
  return cocok ? html.slice(buka, buka + (cocok.index ?? 0)) : sisa;
}

describe("L4 — rincian menempel pada barisnya", () => {
  it("rincian adalah baris penuh di dalam tabel, bukan kartu di luar tabel", () => {
    const html = renderBoard();
    const isi = tbody(html);
    expect(isi).toContain('class="network-detail-row"');
    expect(isi).toContain('id="rincian-lokasi"');
    expect(html).not.toContain('<article class="card" id="rincian-lokasi"');
  });

  it("colSpan mengikuti jumlah kolom yang benar-benar dipasang", () => {
    // Tanpa kolom kondisional: Lokasi · Wilayah · Selisih = 3.
    // React menulis atribut ini sebagai `colSpan` pada render statis.
    expect(renderBoard()).toMatch(/colspan="3"/i);
    // Kolom Batch ≤7h muncul (ada batch hampir kedaluwarsa).
    expect(renderBoard({ batches: BATCH_DEKAT })).toMatch(/colspan="4"/i);
    // Keduanya muncul.
    expect(
      renderBoard({ batches: BATCH_DEKAT, decisions: [{ status: "pending_approval", target_location_name: "Jakarta" }] })
    ).toMatch(/colspan="5"/i);
  });

  it("baris rincian duduk tepat setelah baris lokasi yang dibuka", () => {
    // Diukur pada HTML utuh, bukan potongan: rincian memuat tabel batch sendiri,
    // jadi memotong sampai `</tbody>` pertama akan berhenti di tabel batch.
    const html = renderBoard();
    const bukaJakarta = html.indexOf('aria-expanded="true"');
    const rincian = html.indexOf('id="rincian-lokasi"');
    const cianjur = html.indexOf(">Cianjur<") === -1 ? html.indexOf("Cianjur</button>") : html.indexOf(">Cianjur<");
    expect(bukaJakarta).toBeGreaterThan(-1);
    expect(rincian).toBeGreaterThan(bukaJakarta);
    expect(cianjur).toBeGreaterThan(-1);
    expect(rincian).toBeLessThan(cianjur);
  });

  it("tidak ada baris rincian saat tidak ada yang dibuka", () => {
    const html = renderBoard({ selected: null });
    expect(html).not.toContain('id="rincian-lokasi"');
    expect(html).not.toContain("network-detail-row");
  });

  it("kepala rincian menyebut lokasi + komoditas dan tetap bisa ditutup", () => {
    const html = renderBoard();
    expect(html).toContain("<h3>Jakarta · telur</h3>");
    expect(html).toContain('aria-label="Tutup rincian Jakarta"');
  });
});

describe("L4 — empat angka rincian", () => {
  it("Selisih dipromosikan sebagai angka utama", () => {
    const html = renderBoard();
    expect(html).toMatch(/data-lead="true"/);
    expect(html).toContain("<dt>Selisih</dt>");
  });

  it("empat label angka tetap lengkap", () => {
    const html = renderBoard();
    for (const label of ["Pasokan terakhir", "Kebutuhan", "Selisih", "Perkiraan 7 hari"]) {
      expect(html).toContain(`<dt>${label}</dt>`);
    }
  });

  it("sel tabel batch membawa data-label untuk mode kartu", () => {
    const html = renderBoard();
    for (const label of ["Jumlah", "Keamanan", "Masa layak"]) {
      expect(html).toContain(`data-label="${label}"`);
    }
  });
});

describe("L4 — CSS dossier", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  it("baris rincian tidak memakai bingkai kartu sel tabel", () => {
    expect(css).toMatch(/\.network-detail-row > td \{[^}]*padding: 0/);
  });

  it("di ≤760 px baris rincian tidak ikut jadi kartu berbingkai", () => {
    const blok = css.slice(css.indexOf("@media (max-width: 760px)", css.indexOf(".network-detail {")));
    expect(blok).toMatch(/\.network-detail-row \{[^}]*border: 0/);
  });

  it("tabel batch di dalam rincian jadi kartu berlabel di ≤760 px", () => {
    expect(css).toMatch(/\.network-detail table thead \{[^}]*display: none/);
    expect(css).toMatch(/\.network-detail table td::before \{[^}]*attr\(data-label\)/);
  });

  it("angka Selisih yang dipromosikan memakai token ukuran", () => {
    expect(css).toMatch(/\.network-detail dl > div\[data-lead\] dd \{[^}]*font-size: var\(--fs-[0-9]\)/);
  });
});

describe("L4 — lebar kolom tabel tidak bergeser saat dossier dibuka", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  it("isi dossier tidak boleh menyumbang lebar min-content ke tabel luar", () => {
    // Terukur 29 Okt pada 1280 px (scrollbar disamakan): kolom 368 · 226 · 227 ·
    // 170 · 212 baik saat rincian terbuka maupun tertutup. `contain` menjaga
    // supaya tabel batch tidak pernah mengubah angka itu.
    expect(css).toMatch(/\.network-detail \{[^}]*contain: inline-size/);
  });

  it("sel dossier tidak memakai padding sel tabel biasa", () => {
    expect(css).toMatch(/\.network-detail-row > td \{[^}]*padding: 0/);
  });
});
