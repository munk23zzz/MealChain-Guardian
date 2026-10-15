// Fase 3 (2026-10-14): layer pemasok di peta — kontrak RENDER (SSR).
//
// Yang dikunci di sini:
// - lapisan MATI secara bawaan (aria-pressed=false) dan pin hanya digambar di
//   client (WebGL tidak ada di node) — jadi SSR tidak boleh mengklaim apa pun
//   tentang zoom;
// - tombol & legenda pemasok hanya muncul kalau pemanggil memang memberikan
//   data pemasok (tanpa data → peta seperti sebelumnya, tidak ada kendali nganggur);
// - jumlah pada label tombol = jumlah pemasok yang PUNYA koordinat dan cocok
//   dengan komoditas terpilih (bukan total baris mentah);
// - legenda memakai makna nada pin, dan enum sertifikasi tidak bocor ke layar.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplyMap from "../components/SupplyMap";

const LOCATIONS = [
  {
    location: "Jakarta",
    region: "DKI Jakarta",
    latitude: -6.2088,
    longitude: 106.8456,
    supply_kg: 300,
    demand_kg: 1080,
    surplus_kg: 0,
    shortage_kg: 780,
    status: "shortage",
  },
];

const SUPPLIERS = {
  count: 3,
  total: 3,
  items: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
      location: "Cianjur",
      commodity: "wortel",
      certification_status: "haccp",
      reliability_score: 0.93,
      latitude: -6.824,
      longitude: 107.1636,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "s2",
      name: "Telur Berkah Cianjur",
      location: "Cianjur",
      commodity: "telur",
      certification_status: "none",
      reliability_score: 0.38,
      latitude: -6.811,
      longitude: 107.1636,
      excluded_at_hub: true,
      excluded_scope_locations: ["Cianjur", "Jakarta"],
    },
    {
      id: "s3",
      name: "Pemasok Tanpa Titik",
      location: "Cianjur",
      commodity: "telur",
      reliability_score: 0.9,
      latitude: null,
      longitude: null,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
  ],
};

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <SupplyMap locations={LOCATIONS} showStatusList={false} showHeader={false} {...props} />
  );
}

describe("SupplyMap — layer pemasok", () => {
  it("tanpa data pemasok: tidak ada kendali layer sama sekali", () => {
    const html = render();
    expect(html).not.toContain("map-supplier-controls");
    expect(html).not.toContain("map-layer-toggle");
    expect(html).not.toContain("Legenda pemasok");
    // Kontrak lama (legenda status) tetap ada.
    expect(html).toContain("Status lokasi:");
  });

  it("dengan data pemasok: tombol layer mati secara bawaan", () => {
    const html = render({ suppliers: SUPPLIERS });
    expect(html).toContain("map-layer-toggle");
    expect(html).toContain('aria-pressed="false"');
    expect(html).toContain('type="button"');
    // 3 baris, satu di antaranya tanpa koordinat → hanya 2 yang bisa dipin.
    expect(html).toContain("Tampilkan pemasok (2)");
  });

  it("label tombol mengikuti filter komoditas peta", () => {
    expect(render({ suppliers: SUPPLIERS, commodity: "telur" })).toContain(
      "Tampilkan pemasok (1)"
    );
    expect(render({ suppliers: SUPPLIERS, commodity: "wortel" })).toContain(
      "Tampilkan pemasok (1)"
    );
    expect(render({ suppliers: SUPPLIERS, commodity: "ayam" })).toContain(
      "Tampilkan pemasok (0)"
    );
  });

  it("legenda pemasok menyebut makna nada pin, bukan enum internal", () => {
    const html = render({ suppliers: SUPPLIERS });
    expect(html).toContain("Legenda pemasok");
    expect(html).toContain("Pemasok:");
    expect(html).toContain("Keandalan rendah");
    expect(html).toContain("Dikecualikan");
    expect(html).toContain("map-legend-box-shape-ok");
    expect(html).toContain("map-legend-box-shape-low");
    expect(html).toContain("map-legend-box-shape-excluded");
    expect(html).not.toContain("haccp");
    expect(html).not.toContain("hygiene");
  });

  it("tanpa pemasok berkoordinat: kendali tetap ada dengan angka jujur (0)", () => {
    const html = render({
      suppliers: { items: [SUPPLIERS.items[2]] },
    });
    expect(html).toContain("Tampilkan pemasok (0)");
  });

  it("lapisan pemasok tidak menambah/mengubah pin SPPG atau angka peta", () => {
    // Daftar status dinyalakan di sini supaya angka peta benar-benar ter-render.
    const withoutSuppliers = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    const withSuppliers = renderToStaticMarkup(
      <SupplyMap locations={LOCATIONS} suppliers={SUPPLIERS} />
    );
    ["Jakarta", "Pasokan: 300 kg", "Kebutuhan: 1.080 kg", "Selisih: kurang 780 kg"].forEach(
      (needle) => {
        expect(withoutSuppliers).toContain(needle);
        expect(withSuppliers).toContain(needle);
      }
    );
    // Titik status peta tidak bertambah/berkurang karena layer pemasok.
    const dots = (html: string) => (html.match(/map-legend-box-dot/g) ?? []).length;
    expect(dots(withSuppliers)).toBe(dots(withoutSuppliers));
    // Pesan "perbesar peta" belum muncul di SSR (zoom belum diketahui) —
    // komponen tidak menebak.
    expect(withSuppliers).not.toContain("Perbesar peta");
  });
});
