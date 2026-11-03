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
import { SUPPLIER_PIN_LEGEND } from "../lib/supplier-pins";

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
    // Legenda status tetap terbaca tanpa klik — kini di baris ringkas bawah
    // kanvas (kotak "Info map" yang memuat judul "Status lokasi:" sudah dilebur).
    expect(html).toContain("Legenda:");
    expect(html).toContain("Shortage");
  });

  it("dengan data pemasok: tidak ada tombol lapisan, pin & legenda langsung aktif", () => {
    const html = render({ suppliers: SUPPLIERS });
    // Tombol lapisan dihapus 20 Okt 2026: tidak ada lagi sakelar untuk
    // menyembunyikan pin pemasok — datanya ada, legendanya ikut tampil.
    expect(html).not.toContain("map-layer-toggle");
    expect(html).not.toContain("map-overlay-toggles");
    expect(html).toContain("map-legend-box-shape-excluded");
    expect(html).toContain("Keandalan rendah");
  });

  it("keterangan pemasok dirender karena lapisannya selalu hidup", () => {
    // Arah pemilik 2026-10-16: kotak keterangan tidak menerangkan warna yang
    // tidak ada di peta. Sejak tombolnya dihapus (20 Okt 2026) lapisan pemasok
    // selalu hidup, jadi keterangannya selalu ada begitu datanya dikirim.
    const html = render({ suppliers: SUPPLIERS });
    expect(html).toContain("map-legend-box-shape-excluded");
    const label = SUPPLIER_PIN_LEGEND.map((entry) => entry.label).join(" | ");
    expect(label).toContain("Keandalan rendah");
    expect(label).toContain("Dikecualikan");
    expect(label).not.toContain("haccp");
    expect(label).not.toContain("hygiene");
    expect(html).not.toContain("haccp");
    expect(html).not.toContain("hygiene");
  });

  it("tanpa pemasok berkoordinat: tidak ada tombol lapisan yang menganggur", () => {
    const html = render({
      suppliers: { items: [SUPPLIERS.items[2]] },
    });
    // Dulu ada tombol "Pemasok (0)" — kendali tanpa isi. Sekarang tidak ada
    // kendali sama sekali; yang jujur adalah ketiadaan tombolnya.
    expect(html).not.toContain("map-layer-toggle");
    expect(html).not.toContain('aria-label="Pemasok (0)"');
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
