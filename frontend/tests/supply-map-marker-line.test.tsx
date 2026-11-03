// K3 — peta menyediakan padanan teks untuk isinya, dan TIDAK menghidupkan
// kembali tabel "Rincian Pasokan per Lokasi" yang sudah dihapus pemilik.
//
// Dikunci di sini:
// 1. baris penanda selalu dirender, termasuk saat showStatusList={false}
//    (keadaan Overview hari ini);
// 2. daftar sr-only memuat SATU butir per lokasi — jalur pembaca layar;
// 3. tidak ada <table> maupun kolom "Pasokan"/"Kebutuhan" di blok itu.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplyMap from "../components/SupplyMap";

const LOCATIONS = [
  {
    location: "Jakarta",
    region: "DKI Jakarta",
    latitude: -6.2088,
    longitude: 106.8456,
    supply_kg: 314.2,
    demand_kg: 1080,
    surplus_kg: 0,
    shortage_kg: 765.8,
    status: "shortage",
  },
  {
    location: "Bandung",
    region: "Jawa Barat",
    latitude: -6.9175,
    longitude: 107.6191,
    supply_kg: 220,
    demand_kg: 100,
    surplus_kg: 120,
    shortage_kg: 0,
    status: "surplus",
  },
];

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <SupplyMap locations={LOCATIONS} showStatusList={false} showHeader={false} {...props} />
  );
}

describe("SupplyMap — padanan teks penanda (K3)", () => {
  it("merender baris penanda walau daftar status lokasi dimatikan", () => {
    const html = render();
    expect(html).toContain('class="map-marker-line"');
    expect(html).toContain("Jakarta");
    expect(html).toContain("kurang 765,8 kg");
    expect(html).toContain("lebih 120 kg");
  });

  it("menyediakan daftar sr-only: satu butir per lokasi, dengan status + selisih", () => {
    const html = render();
    expect(html).toContain('aria-label="Daftar penanda peta"');
    expect(html).toContain("Jakarta — Shortage, kurang 765,8 kg");
    expect(html).toContain("Bandung — Surplus, lebih 120 kg");
    const butir = (html.match(/<li/g) ?? []).length;
    expect(butir).toBeGreaterThanOrEqual(LOCATIONS.length);
  });

  it("tidak menghidupkan kembali tabel pasokan/kebutuhan", () => {
    const html = render();
    expect(html).not.toContain("<table");
    const potongan = html.slice(html.indexOf("map-marker-line"), html.indexOf("Daftar penanda peta"));
    expect(potongan).not.toContain("Kebutuhan");
    expect(potongan).not.toContain("Pasokan tercatat");
  });
});
