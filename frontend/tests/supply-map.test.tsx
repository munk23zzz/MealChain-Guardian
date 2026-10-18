// S4-07 (arah Roy 2026-10-09): peta = MapLibre GL sungguhan (bukan SVG
// skematik) — sesuai docs/design.md §5. Gaya peta (arah Roy 2026-10-11):
// peta TERANG seperti acuan — kanvas OSM apa adanya, legenda putih kiri-bawah,
// kontrol bawaan MapLibre (zoom/kompas kanan-atas, atribusi kanan-bawah).
// Kontrak render:
// - SSR-safe: container .map-gl dirender server (maplibre di-mount client
//   via useEffect — WebGL tidak ada di node);
// - atribusi OpenStreetMap tampil (kontrol bawaan MapLibre, bukan SSR);
// - warna pin dari NADA status (shortage/surplus/balanced) via token CSS
//   `--status-*`; lib/map-console.ts memutuskan nada + label, bukan hex;
// - legenda putih memakai makna status aplikasi;
// - legenda + daftar angka supply/demand/gap tetap (sumber angka utama);
// - tanpa data → pesan kosong jujur.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplyMap from "../components/SupplyMap";
import { pinLabel, pinTone } from "../lib/map-console";

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
  it("nada pin mengikuti status, label pin dari angka data (gaya panel acuan)", () => {
    // Warna tak lagi dipegang komponen: nada → kelas → token CSS --pin-*.
    expect(pinTone("shortage")).toBe("shortage");
    expect(pinTone("surplus")).toBe("surplus");
    expect(pinTone("balanced")).toBe("balanced");
    expect(pinLabel(LOCATIONS[0])).toBe("Jakarta −780 kg");
    expect(pinLabel(LOCATIONS[1])).toBe("Cianjur +1.100 kg");
    expect(pinLabel(LOCATIONS[2])).toBe("Bogor seimbang");
  });

  it("peta terang: legenda memakai makna status aplikasi", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    // 19 Okt 2026: kotak "Info map" (judul "Status lokasi:") dilebur ke baris
    // legenda ringkas — satu tempat baca, dan terbaca tanpa klik.
    expect(html).toContain("map-legend-box");
    expect(html).toContain("map-legend-compact");
    expect(html).toContain("Legenda:");
    expect(html).toContain("Shortage");
    expect(html).toContain("map-legend-box-dot-surplus");
    expect(html).toContain("map-legend-box-dot-shortage");
    // Tanpa kepala/kaki panel gelap dari versi sebelumnya.
    expect(html).not.toContain("map-panel-dark");
    expect(html).not.toContain("map-toggle");
  });

  it("SSR merender container .map-gl (mount MapLibre di client)", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).toContain("map-gl");
  });

  it("kepala peta tidak menyebut tumpukan teknologi", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).not.toContain("MapLibre GL");
    expect(html).toContain("Peta Kondisi");
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
    expect(html).not.toContain("aria-busy");
  });

  it("menyediakan legenda status", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).toContain("Shortage");
    expect(html).toContain("Surplus");
    expect(html).toContain("Seimbang");
  });

  it("memisahkan header kolom dan label angka untuk daftar lokasi", () => {
    const html = renderToStaticMarkup(<SupplyMap locations={LOCATIONS} />);
    expect(html).toContain("Lokasi");
    expect(html).toContain("Status");
    expect(html).toContain("Pasokan");
    expect(html).toContain("Kebutuhan");
    expect(html).toContain("Selisih");
    expect(html).toContain("Pasokan: 300 kg");
    expect(html).toContain("Kebutuhan: 1.080 kg");
    expect(html).toContain("Selisih: kurang 780 kg");
    expect(html).toContain("Shortage");
    expect(html).toContain("Surplus");
    expect(html).toContain("Seimbang");
  });

  it("tidak mengubah field angka yang hilang menjadi nol", () => {
    const html = renderToStaticMarkup(
      <SupplyMap locations={[{ ...LOCATIONS[0], demand_kg: undefined }]} />
    );
    expect(html).toContain("Kebutuhan: —");
    expect(html).not.toContain("Kebutuhan: 0 kg");
  });
});
