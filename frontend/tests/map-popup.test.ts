import { describe, expect, it } from "vitest";

import {
  routePopupView,
  sppgPopupView,
  supplierPopupView,
  truckPopupView,
} from "../lib/map-popup";
import type { BalanceMapLocation } from "../lib/overview-format";
import type { SupplierPinRow } from "../lib/supplier-pins";
import type { SupplierRoute } from "../lib/supplier-routes";

const SPPG: BalanceMapLocation = {
  location: "Jakarta",
  status: "shortage",
  supply_kg: 300,
  demand_kg: 1080,
  shortage_kg: 780,
  surplus_kg: 0,
  region: "DKI Jakarta",
};

const PEMASOK: SupplierPinRow = {
  id: "s1",
  name: "CV Barokah Telur",
  hub: "Cianjur",
  commodity: "telur",
  certification: "hygiene",
  reliability: 0.85,
  latitude: -6.82,
  longitude: 107.14,
  distanceKm: 42.4,
  excludedAtHub: false,
  excludedScopes: [],
  shipping: { count: 1, totalKg: 600, commodities: ["telur"], until: null, safetyFailCount: 0 },
};

const RUTE: SupplierRoute = {
  id: "r1",
  batchId: "b1",
  routeKey: null,
  supplierId: "s1",
  supplierName: "CV Barokah Telur",
  originLatitude: -6.82,
  originLongitude: 107.14,
  destinationId: "loc-jkt",
  destinationName: "Jakarta",
  destinationLatitude: -6.2,
  destinationLongitude: 106.84,
  commodity: "telur",
  quantityKg: 600,
  harvestedAt: "2026-10-20T02:00:00Z",
  usableUntil: "2026-11-01T00:00:00Z",
  safetyStatus: "pass",
  straightKm: 78.35,
  road: {
    distanceKm: 110.4,
    durationMin: 84.3,
    ratioVsStraight: 1.41,
    coordinates: [],
    source: "osrm",
    fetchedAt: null,
  },
  missingReason: null,
  journey: {
    dispatchedAt: "2026-10-20T05:00:00Z",
    etaAt: "2026-10-20T08:24:00Z",
    state: "di_jalan",
    stateLabel: "Di jalan",
    travelMin: 84,
    elapsedMin: 50,
    remainingMin: 34,
    progress: 0.42,
    usableUntil: "2026-11-01T00:00:00Z",
    arrivesBeforeUsableUntil: true,
  },
};

describe("popup SPPG", () => {
  it("menulis keadaan, dua angka pembentuk, dan bar pasokan", () => {
    const view = sppgPopupView(SPPG);
    expect(view.kind).toBe("sppg");
    expect(view.kicker).toContain("SPPG");
    expect(view.title).toBe("Jakarta");
    expect(view.chip).toBe("Shortage");
    expect(view.tone).toBe("danger");
    expect(view.hero.value).toContain("780");
    expect(view.metrics.map((m) => m.label)).toEqual(["Pasokan", "Permintaan"]);
    expect(view.meter?.pct).toBe(28);
    expect(view.meter?.text).toContain("28%");
  });

  it("surplus memakai nada hijau dan labelnya sendiri", () => {
    const view = sppgPopupView({ ...SPPG, status: "surplus", surplus_kg: 240, shortage_kg: 0 });
    expect(view.tone).toBe("safe");
    expect(view.chip).toBe("Surplus");
  });
});

describe("popup pemasok", () => {
  it("keandalan jadi angka utama, sertifikasi & jangkauan jadi metrik", () => {
    const view = supplierPopupView(PEMASOK, 150);
    expect(view.tone).toBe("accent");
    expect(view.hero.value).toBe("85%");
    expect(view.metrics.map((m) => m.value)).toContain("Higienis");
    expect(view.metrics.find((m) => m.label === "Jarak")?.value).toBe("42,4 km");
    expect(view.aria).toContain("dalam jangkauan");
    expect(view.callout?.text).toContain("Sedang mengirim 1 kiriman");
    expect(view.meter?.pct).toBe(85);
  });

  it("exclusion menang atas status kiriman dan menyebut lingkupnya", () => {
    const view = supplierPopupView(
      { ...PEMASOK, excludedAtHub: true, excludedScopes: ["Jakarta"] },
      150
    );
    expect(view.tone).toBe("danger");
    expect(view.chip).toBe("Dikecualikan");
    expect(view.callout?.tone).toBe("danger");
    expect(view.callout?.text).toContain("Jakarta");
  });
});

describe("popup truk & garis jalur", () => {
  it("progres perjalanan jadi angka utama; muatan, jarak, ETA jadi metrik", () => {
    const view = truckPopupView(RUTE);
    expect(view.kind).toBe("truck");
    expect(view.title).toBe("CV Barokah Telur → Jakarta");
    expect(view.hero.value).toBe("42%");
    expect(view.meter?.text).toContain("34");
    expect(view.metrics.map((m) => m.label)).toEqual(["Muatan", "Jarak", "Estimasi tiba"]);
    expect(view.metrics[1].value).toContain("110,4");
    expect(view.callout).toBeNull();
  });

  it("kiriman gagal uji diberi callout bahaya, bukan warna saja", () => {
    const view = truckPopupView({ ...RUTE, safetyStatus: "fail" });
    expect(view.tone).toBe("danger");
    expect(view.callout?.tone).toBe("danger");
    expect(view.callout?.text).toContain("GAGAL UJI");
  });

  it("popup garis memakai fakta jalur yang sama dengan sebelumnya", () => {
    const view = routePopupView(RUTE);
    expect(view.kind).toBe("route");
    expect(view.facts.join(" | ")).toContain("Jalur jalan (OSRM)");
    expect(view.facts.join(" | ")).toContain("tiba ± 15.24 WIB");
    expect(view.facts.join(" | ")).toContain("Layak dipakai s/d");
  });
});
