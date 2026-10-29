// L0 — kontrak teks halaman "Location Network".
//
// Aturan yang dijaga (prinsip yang sama dengan halaman Pemasok S0):
//   * KEADAAN TETAP DITULIS, MEKANISME DIBUANG. Halaman boleh menyatakan
//     "10 baris terbaru" atau "cadangan statistik dipakai"; ia tidak boleh
//     menyebut mesin di baliknya (server, backend, database, endpoint,
//     payload, schema, historical_seed).
//   * Jejak audit tetap boleh ada sebagai ATRIBUT (`data-source`,
//     `data-testid`), asal tidak terbaca sebagai kalimat.
//
// Lima keadaan diuji karena jargon paling mudah menyelinap lewat jalur yang
// jarang dibuka: galat ("gagal menghubungi server"), kosong, memuat, dan satu
// lokasi (kolom kondisional tidak terpasang).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import LocationNetworkBoard from "../components/LocationNetworkBoard";
import type { BalanceMapLocation } from "../lib/overview-format";
import type { SupplyDemandDetail } from "../lib/supply-demand";

const JAM = 3_600_000;
const SEKARANG = Date.now();

/** Tujuh istilah mesin yang tidak boleh tampil sebagai teks. */
const ISTILAH_MESIN = [
  "backend",
  "server",
  "database",
  "payload",
  "schema",
  "endpoint",
  "historical_seed",
];

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

const RENCANA = {
  available: true,
  min_surplus_kg: 150,
  pairs: [{ from: "Cianjur", to: "Jakarta", kg: 685, distance_km: 76, cost_share_pct: 0.8 }],
};

const LIMBAH = {
  available: true,
  days: 30,
  recorded_kg: 120,
  redirected_kg: 40,
  without_partner_kg: 80,
};

/** Detail satu lokasi dengan daftar batch yang menyentuh plafon. */
const DETAIL: SupplyDemandDetail = {
  location: "Jakarta",
  commodity: "telur",
  supply: { quantityKg: 2150, recordedAt: new Date(SEKARANG - JAM).toISOString(), source: "sap_rpt_1_6" },
  demand: { quantityKg: 2930, neededBy: new Date(SEKARANG + JAM).toISOString() },
  forecast: {
    quantityKg: 2700,
    horizonDays: 7,
    method: "sap_rpt_1_6",
    methodLabel: "perkiraan statistik",
    confidence: 0.427,
    confidenceLabel: "42,7%",
    source: "statistical_fallback",
    sourceLabel: "cadangan statistik",
    fallbackUsed: true,
    note: "dasar tipis — kurang dari 3 catatan permintaan",
  },
  gap: { text: "kurang 780 kg", tone: "danger" },
  notes: ["permintaan belum punya catatan hari ini"],
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
  batchesTruncated: true,
  batchCap: 500,
};

function renderBoard(over: Partial<Parameters<typeof LocationNetworkBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={[JAKARTA, CIANJUR]}
      commodity="telur"
      selected={null}
      onSelect={() => {}}
      detail={null}
      {...over}
    />
  );
}

/** Teks yang benar-benar terbaca: tag dan atributnya dibuang. */
function teksTerbaca(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&[a-z]+;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function periksaBersih(html: string, label: string): void {
  const teks = teksTerbaca(html).toLowerCase();
  for (const istilah of ISTILAH_MESIN) {
    expect(teks, `[${label}] teks terbaca memuat "${istilah}"`).not.toContain(istilah);
  }
  // Metode mentah boleh tersimpan sebagai atribut, tidak boleh tercetak.
  expect(teks, `[${label}] kode metode mentah tercetak`).not.toContain("statistical_fallback");
  expect(teks, `[${label}] kode metode mentah tercetak`).not.toContain("sap_rpt_1_6");
}

describe("L0 — teks halaman Location Network bebas istilah mesin", () => {
  it("keadaan normal: lima bagian tanpa jargon", () => {
    const html = renderBoard({ plan: RENCANA, waste: LIMBAH });
    expect(html).toContain("Keadaan jaringan");
    expect(html).toContain("Lokasi");
    periksaBersih(html, "normal");
  });

  it("memuat: kerangka tanpa jargon", () => {
    const html = renderBoard({ locations: [], loading: true });
    expect(html).toContain("Memuat saldo lokasi");
    periksaBersih(html, "memuat");
  });

  it("kosong: satu kalimat tanpa jargon", () => {
    const html = renderBoard({ locations: [] });
    periksaBersih(html, "kosong");
  });

  it("galat: pesan gagal memakai kalimat pemakaian, bukan nama pipa data", () => {
    const html = renderBoard({ error: "Saldo lokasi tidak terbaca. Coba lagi sebentar." });
    expect(html).toContain("Tidak bisa memuat saldo lokasi");
    periksaBersih(html, "galat");
  });

  it("satu lokasi: kolom kondisional tidak terpasang, teks tetap bersih", () => {
    const html = renderBoard({ locations: [JAKARTA] });
    expect(html).not.toContain("Batch ≤");
    periksaBersih(html, "satu lokasi");
  });

  it("rincian lokasi terbuka: plafon batch ditulis sebagai keadaan, bukan sumber data", () => {
    const html = renderBoard({ selected: "Jakarta", detail: DETAIL });
    expect(html).toContain("dibatasi 500 baris terbaru");
    expect(teksTerbaca(html)).not.toContain("dari server");
    periksaBersih(html, "rincian");
  });

  it("jejak audit tetap boleh sebagai atribut", () => {
    const html = renderBoard({ selected: "Jakarta", detail: DETAIL });
    // Nilai mentah sumber boleh menempel pada elemen, asal tidak terbaca.
    expect(html).toContain('data-source="statistical_fallback"');
  });
});
