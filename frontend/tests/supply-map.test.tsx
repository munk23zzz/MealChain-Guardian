// S4-07 (arah Roy 2026-10-09): peta = MapLibre GL sungguhan (bukan SVG
// skematik) — sesuai docs/design.md §5. Kontrak render:
// - SSR-safe: container .map-gl dirender server (maplibre di-mount client
//   via useEffect — WebGL tidak ada di node);
// - atribusi OpenStreetMap (tile raster gratis, tanpa API key);
// - marker diwarnakan per status (shortage merah, surplus hijau, balanced
//   abu) — diverifikasi via konfigurasi marker yang diekspos untuk test;
// - legenda + daftar angka supply/demand/gap tetap (sumber angka utama);
// - tanpa data → pesan kosong jujur.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplyMap, { markerColor } from "../components/SupplyMap";

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
  {
    location: "Cianjur",
    region: "Jawa Barat",
    latitude: -6.842,
    longitude: 107.1426,
    supply_kg: 1400,
    demand_kg: 300,
    surplus_kg: 1100,
    shortage_kg: 0,
    status: "surplus",
  },
  {
    location: "Bogor",
    region: "Jawa Barat",
    latitude: -6.595,
    longitude: 106.8166,
    supply_kg: 550,
    demand_kg: 550,
    surplus_kg: 0,
    shortage_kg: 0,
    status: "balanced",
  },
];

describe("SupplyMap (MapLibre GL)", () => {
  it("merahkan shortage, hijaukan surplus, abukan balanced (markerColor)", () => {
    expect(markerColor("shortage")).toBe("#C62828");
    expect(markerColor("surplus")).toBe("#2E7D32");
    expect(markerColor("balanced")).toBe("#555555");
  });

  it("SSR merender container .map-gl (mount MapLibre di client)", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).toContain("map-gl");
  });

  it("atribusi tile OpenStreetMap tampil", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).toContain("OpenStreetMap");
  });

  it("menampilkan nama semua lokasi + angka gap REAL dari data", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).toContain("Jakarta");
    expect(html).toContain("Cianjur");
    expect(html).toContain("Bogor");
    expect(html).toContain("780 kg"); // shortage Jakarta
    expect(html).toContain("1.100 kg"); // surplus Cianjur (id-ID)
  });

  it("menampilkan komoditas pada judul peta", () => {
    const html = renderToStaticMarkup(
      <SupplyMap locations={LOCATIONS} commodity="telur" />
    );
    expect(html).toContain("telur");
  });

  it("tanpa lokasi → pesan kosong jujur, bukan peta karangan", () => {
    const html = renderToStaticMarkup(
      <SupplyMap locations={[]} commodity="telur" />
    );
    expect(html).toContain("map-empty");
    expect(html).not.toContain("map-gl");
  });

  it("menyediakan legenda status", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).toContain("Shortage");
    expect(html).toContain("Surplus");
    expect(html).toContain("Seimbang");
  });
});
