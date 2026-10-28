// Kontrak blok 4–5 halaman Location Network: rencana alih (dari server) dan
// limbah. Yang dijaga:
//   * rencana TIDAK dihitung klien — baris datang dari payload /surplus/allocations;
//   * ambang yang dipakai server disebut sekali di kaki tabel;
//   * tanpa rencana, halaman menyebut SEBABNYA (reason), bukan "0";
//   * limbah tanpa data menulis "belum dicatat", bukan 0 kg;
//   * kartu "Neraca hari ini" (duplikat kalimat ringkasan) tidak lagi ada.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import AllocationTable from "../components/AllocationTable";
import LocationNetworkBoard from "../components/LocationNetworkBoard";

const LOCATIONS = [
  {
    location: "Jakarta",
    region: "DKI Jakarta",
    status: "shortage",
    supply_kg: 300,
    demand_kg: 1080,
    shortage_kg: 780,
    surplus_kg: null,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: "2026-10-29T01:00:00Z",
    demand_recorded_at: "2026-10-29T01:00:00Z",
  },
  {
    location: "Bogor",
    region: "Jawa Barat",
    status: "surplus",
    supply_kg: 700,
    demand_kg: 208,
    shortage_kg: null,
    surplus_kg: 492,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: "2026-10-29T01:00:00Z",
    demand_recorded_at: "2026-10-29T01:00:00Z",
  },
];

const PLAN = {
  available: true,
  min_surplus_kg: 150,
  pairs: [
    {
      from: "Bogor",
      to: "Jakarta",
      kg: 400,
      distance_km: 62,
      region: "DKI Jakarta",
      cost_share_pct: 3.4,
    },
  ],
};

const WASTE = {
  window_days: 30,
  recorded: { available: true, kg: 0, events: 0 },
  diverted: { available: false },
  unassigned: { available: false },
  partners: [],
};

function renderAllocation(over: Partial<Parameters<typeof AllocationTable>[0]> = {}) {
  return renderToStaticMarkup(<AllocationTable plan={PLAN} {...over} />);
}

describe("Rencana alih", () => {
  it("mencetak baris pasangan dari server apa adanya", () => {
    const html = renderAllocation();
    expect(html).toContain('data-testid="allocation-table"');
    expect(html).toContain("<td>Bogor</td>");
    expect(html).toContain("<td>Jakarta</td>");
    expect(html).toContain("400 kg");
    expect(html).toContain("62 km");
  });

  it("menyebut ambang server sekali di kaki, bukan paragraf", () => {
    const html = renderAllocation();
    expect(html).toContain("Hanya surplus ≥ 150 kg per lokasi.");
    expect(html.match(/150 kg/g) ?? []).toHaveLength(1);
  });

  it("tanpa pasangan: menulis sebab dari server, bukan angka 0", () => {
    const html = renderAllocation({
      plan: { available: false, reason: "surplus_di_bawah_ambang" },
    });
    expect(html).toContain("Tidak ada lokasi dengan surplus 150 kg atau lebih");
    // "150 kg" mengandung "0 kg" — periksa nilai sel, bukan substring.
    expect(html).not.toMatch(/>0 kg</);
  });

  it("gagal memuat: pesan galat, tanpa tabel", () => {
    const html = renderAllocation({ plan: null, error: "jaringan terputus" });
    expect(html).toContain("Rencana alih tidak bisa dimuat: jaringan terputus");
    expect(html).not.toContain('data-testid="allocation-table"');
  });
});

describe("Kerangka halaman gabungan", () => {
  it("hanya satu baris filter komoditas untuk seluruh halaman", () => {
    const html = renderToStaticMarkup(
      <LocationNetworkBoard
        locations={LOCATIONS}
        commodities={["telur", "ayam"]}
        onCommodityChange={() => {}}
        commodity="telur"
        selected={null}
        onSelect={() => {}}
        detail={null}
        plan={PLAN}
        waste={WASTE}
      />
    );
    // Hanya gugus filter, bukan label di dalamnya (.commodity-filters-label).
    // 29 Okt 2026: pembungkusnya tidak lagi berkartu (`.filter-card`) — gugus
    // filter memakai bahasa chip filter Recommendations, jadi kelas keduanya
    // sengaja hilang dari markup.
    expect((html.match(/class="commodity-filters"/g) ?? []).length).toBe(1);
  });

  it("neraca ditulis sekali: tidak ada kartu 'Neraca hari ini' duplikat", () => {
    const html = renderToStaticMarkup(
      <LocationNetworkBoard
        locations={LOCATIONS}
        selected={null}
        onSelect={() => {}}
        detail={null}
        plan={PLAN}
        waste={WASTE}
      />
    );
    expect(html).toContain("Keadaan jaringan");
    expect(html).not.toContain("Neraca hari ini");
    expect(html).toContain("Rencana alih");
    expect(html).toContain("Limbah · 30 hari");
  });

  it("limbah tanpa data menulis 'Belum dicatat', tidak menulis 0 kg", () => {
    const html = renderToStaticMarkup(
      <LocationNetworkBoard
        locations={LOCATIONS}
        selected={null}
        onSelect={() => {}}
        detail={null}
        plan={null}
        waste={null}
      />
    );
    expect(html).toContain("Belum dicatat.");
    expect(html).not.toMatch(/>0 kg</);
  });
});

const NOW = new Date("2026-10-29T03:00:00Z");

function renderWith(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={LOCATIONS}
      selected={null}
      onSelect={() => {}}
      detail={null}
      plan={PLAN}
      waste={WASTE}
      now={NOW}
      {...over}
    />
  );
}

describe("Dua kolom tambahan di tabel lokasi", () => {
  it("kolom tidak dipasang bila tidak ada batch mendesak maupun rekomendasi", () => {
    const html = renderWith({ batches: [], decisions: [] });
    expect(html).not.toContain("Batch ≤7h");
    expect(html).not.toContain(">Rekomendasi<");
  });

  it("kolom Batch ≤7h muncul hanya bila ada batch yang layak ≤7 hari dan tidak ditahan", () => {
    const html = renderWith({
      batches: [
        {
          id: "a",
          location: "Jakarta",
          safety_status: "pass",
          quarantine_status: "none",
          usable_until: "2026-10-31T03:00:00Z",
        },
        {
          id: "b",
          location: "Bogor",
          safety_status: "pass",
          quarantine_status: "none",
          usable_until: "2026-12-31T03:00:00Z",
        },
      ],
    });
    expect(html).toContain("Batch ≤7h");
    // Jakarta punya 1 batch mendesak; Bogor hanya punya yang masih lama → "—".
    expect(html).toMatch(/data-kind="expiry">1</);
    expect(html).toMatch(/data-kind="expiry">—</);
  });

  it("batch yang ditahan tidak memunculkan kolom", () => {
    const html = renderWith({
      batches: [
        {
          id: "a",
          location: "Jakarta",
          safety_status: "pass",
          quarantine_status: "quarantined",
          usable_until: "2026-10-31T03:00:00Z",
        },
      ],
    });
    expect(html).not.toContain("Batch ≤7h");
  });

  it("kolom Rekomendasi menghitung keputusan terbuka per lokasi", () => {
    const html = renderWith({
      decisions: [
        { status: "proposed", target_location_name: "Jakarta" },
        { status: "pending_approval", target_location_name: "Jakarta" },
        { status: "executed", target_location_name: "Bogor" },
      ],
    });
    expect(html).toContain(">Rekomendasi<");
    expect(html).toMatch(/data-kind="decision">2</);
    expect(html).toMatch(/data-kind="decision">—</);
  });
});

describe("Keadaan blok limbah", () => {
  it("saat memuat menulis 'Memuat limbah…', bukan 'Belum dicatat'", () => {
    const html = renderWith({ waste: null, wasteLoading: true });
    expect(html).toContain("Memuat limbah…");
    expect(html).not.toContain("Belum dicatat.");
  });

  it("saat galat menyebut sebabnya, bukan 'Belum dicatat'", () => {
    const html = renderWith({ waste: null, wasteError: "jaringan terputus" });
    expect(html).toContain("Limbah tidak bisa dimuat: jaringan terputus");
    expect(html).not.toContain("Belum dicatat.");
  });

  it("tiga baris limbah memakai label pendek", () => {
    const html = renderWith({
      waste: {
        recorded: { available: true, kg: 469.7, events: 64 },
        diverted: { available: true, kg: 12.5, events: 1 },
        unassigned: { available: true, kg: 457.2, events: 63 },
        partners: [{ name: "Bank Sampah Melati", kg: 12.5, events: 1 }],
      },
    });
    expect(html).toContain(">Tercatat<");
    expect(html).toContain(">Dialihkan<");
    expect(html).toContain(">Tanpa mitra<");
    // Daftar nama mitra tidak lagi ditampilkan di halaman ini.
    expect(html).not.toContain("Bank Sampah Melati");
  });
});
