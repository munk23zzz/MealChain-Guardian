// Fase 10: garis jalur kiriman (pemasok → tujuan) di peta.
//
// Angka di tes ini diambil dari respons nyata `GET /supplier-routes` untuk
// kiriman kanonik Supplier A Cianjur → SPPG Jakarta (lihat
// docs/verification/fase-10.md): jalur jalan OSRM 110,434 km, 5.060 s,
// jarak lurus 78,35 km → rasio 1,41×.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  MISSING_REASON_LABEL,
  ROUTE_LINE_COLORS,
  roadKmLabel,
  routeBoundsPoints,
  routeGeoJson,
  routeLabel,
  routeLayerSummary,
  routeLegendEntries,
  routeLineClass,
  routeLineTone,
  routePopupLines,
  routeToggleLabel,
  supplierRoutes,
} from "../lib/supplier-routes";

const GEOMETRI: [number, number][] = [
  [107.1306, -6.854],
  [107.0, -6.7],
  [106.8456, -6.2088],
];

function kiriman(ubah: Record<string, unknown> = {}) {
  return {
    batch_id: "b-1",
    supplier_id: "s-1",
    supplier_name: "Supplier A Cianjur",
    origin: { latitude: -6.854, longitude: 107.1306, name: "Supplier A Cianjur" },
    destination_id: "l-1",
    destination_name: "Jakarta",
    destination: { latitude: -6.2088, longitude: 106.8456, name: "Jakarta" },
    commodity: "telur",
    quantity_kg: 800,
    usable_until: "2026-11-07T12:00:00+00:00",
    safety_status: "pass",
    straight_km: 78.35,
    road: {
      distance_km: 110.4,
      duration_min: 84.3,
      ratio_vs_straight: 1.41,
      geometry: { type: "LineString", coordinates: GEOMETRI },
      source: "osrm",
      fetched_at: "2026-10-16T00:00:00+00:00",
    },
    road_missing_reason: null,
    ...ubah,
  };
}

describe("supplierRoutes", () => {
  it("membaca amplop {routes} maupun array langsung", () => {
    expect(supplierRoutes({ routes: [kiriman()] })).toHaveLength(1);
    expect(supplierRoutes([kiriman()])).toHaveLength(1);
  });

  it("membuang baris tanpa dua ujung berkoordinat", () => {
    const rusak = kiriman({ destination: { latitude: null, longitude: null, name: "?" } });
    expect(supplierRoutes({ routes: [rusak, kiriman()] })).toHaveLength(1);
  });

  it("jatuh ke nama tujuan di dalam blok destination bila nama atas kosong", () => {
    const [row] = supplierRoutes({ routes: [kiriman({ destination_name: "  " })] });
    expect(row.destinationName).toBe("Jakarta");
  });

  it("membuang baris yang nama tujuannya tidak ada di mana pun", () => {
    const tanpaNama = kiriman({
      destination_name: "",
      destination: { latitude: -6.2088, longitude: 106.8456, name: null },
    });
    expect(supplierRoutes({ routes: [tanpaNama] })).toHaveLength(0);
  });

  it("mengurai rute jalan apa adanya", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    expect(row.road?.distanceKm).toBeCloseTo(110.4, 5);
    expect(row.road?.durationMin).toBeCloseTo(84.3, 5);
    expect(row.road?.ratioVsStraight).toBeCloseTo(1.41, 5);
    expect(row.road?.source).toBe("osrm");
    expect(row.road?.coordinates).toHaveLength(3);
    expect(row.straightKm).toBeCloseTo(78.35, 5);
  });

  it("geometri kurang dari dua titik berarti tidak ada rute", () => {
    const rusak = kiriman({
      road: {
        distance_km: 110.4,
        duration_min: 84.3,
        geometry: { type: "LineString", coordinates: [[107.1306, -6.854]] },
        source: "osrm",
      },
      road_missing_reason: "belum_disinkron",
    });
    const [row] = supplierRoutes({ routes: [rusak] });
    expect(row.road).toBeNull();
    expect(row.missingReason).toBe("belum_disinkron");
  });
});

describe("warna garis", () => {
  it("nilai paint MapLibre sama dengan token CSS (webgl tak bisa baca CSS var)", () => {
    const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");
    const token = (nama: string) => {
      const match = css.match(new RegExp(`${nama}\\s*:\\s*(#[0-9A-Fa-f]{6})`));
      expect(match, `token ${nama} tidak ditemukan di app/globals.css`).not.toBeNull();
      return (match as RegExpMatchArray)[1].toUpperCase();
    };
    expect(ROUTE_LINE_COLORS.ok.toUpperCase()).toBe(token("--status-safe"));
    expect(ROUTE_LINE_COLORS.fail.toUpperCase()).toBe(token("--status-danger"));
  });
});

describe("nada & kelas garis", () => {
  it("kiriman gagal uji dapat nada bahaya", () => {
    const [gagal] = supplierRoutes({ routes: [kiriman({ safety_status: "fail" })] });
    expect(routeLineTone(gagal)).toBe("fail");
    expect(routeLineClass(gagal)).toBe("ship-route ship-route-fail");
  });

  it("kiriman biasa memakai nada aman", () => {
    const [aman] = supplierRoutes({ routes: [kiriman()] });
    expect(routeLineTone(aman)).toBe("ok");
    expect(routeLineClass(aman)).toBe("ship-route ship-route-ok");
  });

  it("legenda menyebut kedua nada", () => {
    const entri = routeLegendEntries();
    expect(entri.map((e) => e.tone)).toEqual(["ok", "fail"]);
    expect(entri[0].label).toContain("Jalur kiriman");
    expect(entri[1].label).toContain("gagal uji");
  });
});

describe("layer GeoJSON", () => {
  it("hanya menggambar kiriman yang punya geometri jalan", () => {
    const tanpaRute = kiriman({
      road: null,
      road_missing_reason: "belum_disinkron",
      destination_name: "Bogor",
    });
    const fc = routeGeoJson({ routes: [kiriman(), tanpaRute] });
    expect(fc.type).toBe("FeatureCollection");
    expect(fc.features).toHaveLength(1);
    expect(fc.features[0].geometry.type).toBe("LineString");
    expect(fc.features[0].geometry.coordinates).toEqual(GEOMETRI);
  });

  it("properti fitur cukup untuk label & popup", () => {
    const fc = routeGeoJson({ routes: [kiriman()] });
    const props = fc.features[0].properties;
    expect(props.supplierName).toBe("Supplier A Cianjur");
    expect(props.destinationName).toBe("Jakarta");
    expect(props.tone).toBe("ok");
    expect(props.roadKm).toBeCloseTo(110.4, 5);
    expect(props.quantityKg).toBe(800);
    expect(props.label).toContain("→ Jakarta");
  });

  it("payload kosong menghasilkan koleksi kosong, bukan error", () => {
    expect(routeGeoJson(null).features).toEqual([]);
    expect(routeGeoJson({ routes: [] }).features).toEqual([]);
  });
});

describe("batas peta", () => {
  it("menyertakan dua ujung kiriman walau rutenya belum disinkron", () => {
    const tanpaRute = kiriman({ road: null, road_missing_reason: "belum_disinkron" });
    const titik = routeBoundsPoints({ routes: [tanpaRute] });
    expect(titik).toEqual([
      [107.1306, -6.854],
      [106.8456, -6.2088],
    ]);
  });
});

describe("label & popup", () => {
  it("label pendek gaya id-ID", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    expect(routeLabel(row)).toBe("Supplier A Cianjur → Jakarta · 110,4 km jalan · 800 kg telur");
  });

  it("popup menyandingkan jarak jalan dan jarak lurus + rasionya", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    const baris = routePopupLines(row);
    expect(baris[0]).toContain("OSRM");
    expect(baris[0]).toContain("110,4 km");
    expect(baris[0]).toContain("84 menit");
    expect(baris[1]).toContain("78,4 km");
    expect(baris[2]).toContain("1,41×");
    expect(baris[3]).toContain("7 Nov 2026");
  });

  it("popup menyebut alasan bila rute belum ada, tanpa angka karangan", () => {
    const [row] = supplierRoutes({
      routes: [kiriman({ road: null, road_missing_reason: "belum_disinkron" })],
    });
    const baris = routePopupLines(row);
    expect(baris[0]).toBe(`Jalur jalan: belum ada — ${MISSING_REASON_LABEL.belum_disinkron}`);
    expect(baris.join(" ")).not.toContain("110,4");
  });

  it("popup menandai kiriman gagal uji", () => {
    const [row] = supplierRoutes({ routes: [kiriman({ safety_status: "fail" })] });
    expect(routePopupLines(row).join(" ")).toContain("GAGAL UJI");
  });

  it("roadKmLabel mempertahankan satu desimal pada jarak jauh", () => {
    expect(roadKmLabel(110.43)).toBe("110,4 km");
    expect(roadKmLabel(3.2)).toBe("3,2 km");
    expect(roadKmLabel(null)).toBe("—");
  });
});

describe("ringkasan layer", () => {
  it("menghitung jalur yang sudah & belum punya rute", () => {
    const tanpaRute = kiriman({
      road: null,
      road_missing_reason: "belum_disinkron",
      destination_name: "Bogor",
    });
    const ringkasan = routeLayerSummary({ routes: [kiriman(), tanpaRute] });
    expect(ringkasan.routes).toBe(2);
    expect(ringkasan.withRoad).toBe(1);
    expect(ringkasan.missing).toBe(1);
    expect(ringkasan.label).toBe("2 jalur kiriman · 1 belum disinkronkan");
  });

  it("menyebut semuanya lewat jalur jalan bila lengkap", () => {
    const ringkasan = routeLayerSummary({ routes: [kiriman()] });
    expect(ringkasan.label).toBe("1 jalur kiriman · semua lewat jalur jalan");
  });

  it("label sakelar memuat jumlah jalur", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    expect(routeToggleLabel([row], false)).toBe("Tampilkan jalur kiriman (1)");
    expect(routeToggleLabel([row], true)).toBe("Sembunyikan jalur kiriman (1)");
  });
});
