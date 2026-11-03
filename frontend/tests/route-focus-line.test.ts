/**
 * Tes murni khusus GEOMETRI SOROTAN (Arah C): bagian padat vs putus-putus.
 * Dipisah dari tests/route-focus.test.ts supaya berkas tes tidak menggelembung.
 */
import { describe, expect, it } from "vitest";

import { focusLineFeatures } from "../lib/route-focus";
import type { SupplierRoute } from "../lib/supplier-routes";
import { supplierRoutes } from "../lib/supplier-routes";

type Raw = Record<string, unknown>;

function payload(journey: Raw | null, road: Raw | null = { distance_km: 110.4, duration_min: 84, geometry: { type: "LineString", coordinates: [[0, 0], [2, 0], [2, 1]] }, source: "osrm" }) {
  return {
    routes: [
      {
        supplier_id: "S1",
        supplier_name: "Supplier A",
        origin: { latitude: 0, longitude: 0 },
        destination_id: "L1",
        destination_name: "Jakarta",
        destination: { latitude: 1, longitude: 2 },
        safety_status: "pass",
        road,
        journey,
      },
    ],
  };
}

function row(journey: Raw | null, road: Raw | null = undefined as unknown as Raw): SupplierRoute | null {
  const rows = supplierRoutes(payload(journey, road === undefined ? undefined : road));
  return rows[0] ?? null;
}

describe("geometri sorotan kiriman (Arah C)", () => {
  it("di jalan 50%: dua potong — padat (selesai) dan putus-putus (sisa)", () => {
    const koleksi = focusLineFeatures(row({ state: "di_jalan", progress: 0.5 }));
    expect(koleksi.type).toBe("FeatureCollection");
    expect(koleksi.features.map((f) => f.properties.kind)).toEqual(["done", "todo"]);
    const [done, todo] = koleksi.features;
    expect(done.geometry.coordinates.length).toBeGreaterThanOrEqual(2);
    // Titik sambung tidak boleh hilang: ujung potongan pertama = awal potongan kedua.
    expect(done.geometry.coordinates.at(-1)).toEqual(todo.geometry.coordinates[0]);
  });

  it("kiriman yang sudah tiba: seluruh garis padat, walau progress tidak ada", () => {
    const koleksi = focusLineFeatures(row({ state: "sudah_tiba" }));
    expect(koleksi.features).toHaveLength(1);
    expect(koleksi.features[0].properties.kind).toBe("done");
    expect(koleksi.features[0].geometry.coordinates).toEqual([
      [0, 0],
      [2, 0],
      [2, 1],
    ]);
  });

  it("belum berangkat / tanpa progress: garis utuh putus-putus (bukan klaim sudah jalan)", () => {
    const koleksi = focusLineFeatures(row({ state: "belum_berangkat" }));
    expect(koleksi.features).toHaveLength(1);
    expect(koleksi.features[0].properties.kind).toBe("todo");
    expect(koleksi.features[0].geometry.coordinates).toEqual([
      [0, 0],
      [2, 0],
      [2, 1],
    ]);
  });

  it("tanpa jalur jalan: tidak ada yang digambar (bukan garis lurus palsu)", () => {
    expect(focusLineFeatures(row({ state: "di_jalan", progress: 0.5 }, null)).features).toEqual([]);
  });

  it("tidak ada kiriman disorot: koleksi kosong", () => {
    expect(focusLineFeatures(null).features).toEqual([]);
  });

  it("mutu gagal → warna garis sorotan mengikuti nada gagal", () => {
    const fail = supplierRoutes({
      routes: [
        {
          supplier_id: "S1",
          supplier_name: "Supplier A",
          origin: { latitude: 0, longitude: 0 },
          destination_id: "L1",
          destination_name: "Jakarta",
          destination: { latitude: 1, longitude: 2 },
          safety_status: "fail",
          road: { distance_km: 110.4, duration_min: 84, geometry: { type: "LineString", coordinates: [[0, 0], [2, 0]] }, source: "osrm" },
          journey: { state: "di_jalan", progress: 0.5 },
        },
      ],
    })[0];
    expect(focusLineFeatures(fail).features.every((f) => f.properties.tone === "fail")).toBe(true);
  });
});
