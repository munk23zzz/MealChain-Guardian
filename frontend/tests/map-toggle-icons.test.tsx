/**
 * Sakelar lapisan peta: IKON SAJA (19 Okt 2026).
 *
 * Keputusan pemilik: "untuk pemasok dan jalur, tombolnya dibuat ikon saja".
 * Mengganti teks dengan ikon menghapus satu-satunya nama yang dibaca pembaca
 * layar, jadi tes ini menjaga syarat yang membuatnya tetap bisa dipakai
 * (ui-ux-pro-max prioritas 1 & 2):
 *
 * 1. setiap tombol punya NAMA aksesibel yang menyebut jumlah — "Pemasok (2)";
 * 2. aksinya ada di `title` ("Tampilkan …" / "Sembunyikan …"), karena tidak ada
 *    teks yang bisa dibaca untuk menebak arti ikon;
 * 3. keadaannya dibawa `aria-pressed`, bukan hanya warna;
 * 4. ikonnya dekoratif (`aria-hidden`) — tidak boleh muncul sebagai nama ganda;
 * 5. dua ikon itu BEDA bentuk: pin untuk pemasok, polyline untuk jalur.
 */
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
  count: 2,
  total: 2,
  items: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
      location: "Cianjur",
      commodity: "telur",
      certification_status: "haccp",
      reliability_score: 0.93,
      latitude: -6.824,
      longitude: 107.1636,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "s2",
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

const ROUTES = {
  routes: [
    {
      batch_id: "b1",
      supplier_id: "s1",
      supplier_name: "Supplier A Cianjur",
      origin: { latitude: -6.854, longitude: 107.1306, name: "Supplier A Cianjur" },
      destination_id: "l1",
      destination_name: "Jakarta",
      destination: { latitude: -6.2088, longitude: 106.8456, name: "Jakarta" },
      commodity: "telur",
      quantity_kg: 800,
      harvested_at: "2026-10-15T00:30:00+00:00",
      usable_until: "2026-11-07T12:00:00+00:00",
      safety_status: "pass",
      straight_km: 78.35,
      route_key: "driving:-6.854,107.1306>-6.2088,106.8456",
      journey: {
        dispatched_at: "2026-10-16T14:30:00+00:00",
        eta_at: "2026-10-16T15:54:18+00:00",
        state: "di_jalan",
        state_label: "Di jalan",
        travel_s: 5058,
        travel_min: 84.3,
        travel_source: "osrm",
        elapsed_min: 60,
        remaining_min: 24.3,
        progress: 0.712,
        usable_until: "2026-11-07T12:00:00+00:00",
        arrives_before_usable_until: true,
      },
      road: {
        distance_km: 110.4,
        duration_min: 84.3,
        ratio_vs_straight: 1.41,
        geometry: {
          type: "LineString",
          coordinates: [
            [107.1306, -6.854],
            [106.8456, -6.2088],
          ],
        },
        source: "osrm",
        fetched_at: "2026-10-16T00:00:00+00:00",
      },
      road_missing_reason: null,
    },
  ],
};

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <SupplyMap locations={LOCATIONS} showStatusList={false} showHeader={false} {...props} />
  );
}

/** Isi satu tombol dari HTML mentah (cukup untuk tes SSR). */
function tombol(html: string, kelas: string): string {
  const idx = html.indexOf(`class="map-layer-toggle ${kelas}"`);
  if (idx === -1) throw new Error(`tombol ${kelas} tidak ada`);
  const mulai = html.lastIndexOf("<button", idx);
  const akhir = html.indexOf("</button>", idx);
  return html.slice(mulai, akhir + "</button>".length);
}

describe("sakelar lapisan peta — ikon saja", () => {
  const html = render({ suppliers: SUPPLIERS, supplierRoutes: ROUTES });

  it("pemasok & jalur jadi dua tombol ikon tanpa teks terlihat", () => {
    const pemasok = tombol(html, "map-supplier-toggle");
    const jalur = tombol(html, "map-route-toggle");
    for (const isi of [pemasok, jalur]) {
      const tanpaSvg = isi.replace(/<svg[\s\S]*?<\/svg>/g, "").replace(/<[^>]+>/g, "");
      expect(tanpaSvg.trim()).toBe("");
      expect(isi).toContain('class="map-layer-toggle-icon"');
      expect(isi).toContain("<svg");
    }
  });

  it("nama aksesibel menyebut jumlah, aksi ada di tooltip", () => {
    const pemasok = tombol(html, "map-supplier-toggle");
    const jalur = tombol(html, "map-route-toggle");
    expect(pemasok).toContain('aria-label="Pemasok (1)"');
    expect(pemasok).toContain('title="Tampilkan pemasok (1)"');
    expect(jalur).toContain('aria-label="Jalur kiriman (1)"');
    expect(jalur).toContain('title="Sembunyikan jalur kiriman (1)"');
  });

  it("keadaan nyala/mati dibawa aria-pressed, bukan warna", () => {
    const pemasok = tombol(html, "map-supplier-toggle");
    const jalur = tombol(html, "map-route-toggle");
    // Bawaan: pemasok mati, jalur hidup.
    expect(pemasok).toContain('aria-pressed="false"');
    expect(jalur).toContain('aria-pressed="true"');
  });

  it("ikon dekoratif disembunyikan dari pembaca layar", () => {
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain('focusable="false"');
  });

  it("dua ikonnya beda bentuk (pin vs polyline), bukan salinan", () => {
    const jalurSvg = (html.match(/<svg[^>]*>[\s\S]*?<\/svg>/g) ?? []).find((s) => s.includes("M2.6 12.4"));
    expect(jalurSvg).toBeTruthy();
    expect(jalurSvg).toContain("<path");
    // Pin memakai bentuk penanda (path dengan 'Z' = tertutup), jalur memakai
    // polyline terbuka + dua titik ujung berisi.
    expect(jalurSvg).not.toContain("<path d=\"M8");
  });

  it("pil hanya memuat dua kendali: tidak ada chip 'Info map' lagi", () => {
    expect(html).not.toContain("Info map");
    expect(html).not.toContain("map-legend-toggle");
    expect(html).toContain('aria-label="Lapisan peta"');
  });
});
