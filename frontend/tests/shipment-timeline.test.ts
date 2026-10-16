// Riwayat kejadian per kiriman — logika MURNI (menutup kesenjangan #12 riset).
//
// Aturan yang diuji: hanya kejadian yang PUNYA WAKTU di server yang masuk daftar
// (waktu uji keamanan tidak disimpan model → jangan dikarang), "rencana" dibedakan
// dari "terjadi" (estimasi tiba jangan terbaca sebagai sudah tiba), dan urutannya
// terbaru dulu.
import { describe, expect, it } from "vitest";

import {
  shipmentEvents,
  shipmentLoadLabel,
  shipmentRouteAudit,
  shipmentTimelineLabel,
} from "../lib/shipment-timeline";
import type { SupplierRoute } from "../lib/supplier-routes";

type Journey = NonNullable<SupplierRoute["journey"]>;

function journey(over: Partial<Journey> = {}): Journey {
  return {
    dispatchedAt: "2026-10-16T12:24:00+00:00",
    etaAt: "2026-10-16T12:24:00+00:00",
    state: "di_jalan",
    stateLabel: "Di jalan",
    travelMin: 84,
    elapsedMin: 64,
    remainingMin: 20,
    progress: 0.76,
    usableUntil: "2026-11-07T11:00:00+00:00",
    arrivesBeforeUsableUntil: true,
    ...over,
  };
}

function route(over: Partial<SupplierRoute> = {}): SupplierRoute {
  return {
    id: "S1->L1",
    batchId: "B-1",
    routeKey: "k1",
    supplierId: "S1",
    supplierName: "Supplier A",
    originLatitude: -6.8,
    originLongitude: 107.1,
    destinationId: "L1",
    destinationName: "Jakarta",
    destinationLatitude: -6.2,
    destinationLongitude: 106.8,
    commodity: "telur",
    quantityKg: 800,
    harvestedAt: "2026-10-16T01:00:00+00:00",
    usableUntil: "2026-11-07T11:00:00+00:00",
    safetyStatus: "pass",
    straightKm: 78.35,
    road: {
      distanceKm: 110.4,
      durationMin: 84.3,
      ratioVsStraight: 1.41,
      coordinates: [
        [107.1, -6.8],
        [106.8, -6.2],
      ],
      source: "osrm",
      fetchedAt: "2026-10-16T00:10:00+00:00",
    },
    missingReason: null,
    journey: journey(),
    ...over,
  };
}

describe("riwayat kejadian per kiriman", () => {
  it("terbaru dulu — diurut menurut WAKTU server, bukan urutan tetap", () => {
    // Fixture: panen 08.00 WIB, berangkat 13.20, estimasi 14.20.
    const keys = shipmentEvents(route()).map((e) => e.key);
    expect(keys).toEqual(["estimasi-tiba", "berangkat", "panen"]);
  });

  it("setiap baris BERTANGGAL (waktu lengkap WIB, bukan jam saja)", () => {
    for (const event of shipmentEvents(route())) {
      expect(event.atLabel).toMatch(/\d{1,2} \w+ \d{4} \d{2}\.\d{2} WIB/);
    }
  });

  it("estimasi tiba ditandai 'rencana', bukan kejadian yang sudah terjadi", () => {
    const estimasi = shipmentEvents(route()).find((e) => e.key === "estimasi-tiba");
    expect(estimasi?.kind).toBe("rencana");
    expect(estimasi?.title).toBe("Estimasi tiba");
  });

  it("kiriman yang sudah tiba: kejadian 'Tiba' menggantikan estimasi", () => {
    const events = shipmentEvents(
      route({ journey: journey({ state: "sudah_tiba", remainingMin: 0 }) })
    );
    expect(events[0].key).toBe("tiba");
    expect(events[0].kind).toBe("terjadi");
    expect(events.map((e) => e.key)).not.toContain("estimasi-tiba");
  });

  it("belum berangkat: tidak ada kejadian berangkat, estimasi tetap ditandai rencana", () => {
    const events = shipmentEvents(
      route({ journey: journey({ state: "belum_berangkat", dispatchedAt: null, etaAt: "2026-10-16T14:00:00+00:00" }) })
    );
    expect(events.map((e) => e.key)).not.toContain("berangkat");
    expect(events.find((e) => e.key === "estimasi-tiba")?.kind).toBe("rencana");
  });

  it("mutu TIDAK dikarang tanggalnya: tidak ada kejadian uji keamanan", () => {
    const events = shipmentEvents(route({ safetyStatus: "fail" }));
    expect(events.some((e) => /uji|mutu|keamanan/i.test(e.title))).toBe(false);
  });

  it("tanpa satu pun waktu yang dilaporkan → daftar kosong, bukan blok kosong", () => {
    expect(
      shipmentEvents(
        route({ harvestedAt: null, journey: null, road: null, missingReason: "belum_disinkron" })
      )
    ).toEqual([]);
  });

  it("waktu yang tidak terbaca tidak masuk daftar (jangan tulis '—' sebagai kejadian)", () => {
    const events = shipmentEvents(route({ harvestedAt: "bukan tanggal", journey: null, road: null }));
    expect(events).toEqual([]);
  });

  it("jejak audit jalur jadi catatan kaki, BUKAN baris kejadian", () => {
    // Kalau dijadikan kejadian, ia duduk di atas kejadian "Tiba" bertanggal lebih
    // awal (waktu hitung = hari ini) dan garis waktunya terbaca rusak.
    expect(shipmentEvents(route()).map((e) => e.key)).not.toContain("jalur-dihitung");
    const catatan = shipmentRouteAudit(route());
    expect(catatan).toContain("Angka jalur dihitung server 16 Okt 2026 07.10 WIB");
    expect(catatan).toContain("OSRM 110,4 km");
  });

  it("catatan audit kosong bila tidak ada geometri atau waktunya tidak terbaca", () => {
    expect(shipmentRouteAudit(route({ road: null }))).toBeNull();
    expect(
      shipmentRouteAudit(route({ road: { ...route().road!, fetchedAt: "bukan tanggal" } }))
    ).toBeNull();
  });

  it("berangkat menyebut sumber jalur bila geometrinya ada", () => {
    const berangkat = shipmentEvents(route()).find((e) => e.key === "berangkat");
    expect(berangkat?.detail).toBe("Jalur jalan OSRM");
    expect(
      shipmentEvents(route({ road: null })).find((e) => e.key === "berangkat")?.detail
    ).toBeNull();
  });

  it("dua kejadian berwaktu sama diurutkan menurut kepentingan (tiba lebih dulu)", () => {
    const sama = "2026-10-16T12:24:00+00:00";
    const events = shipmentEvents(
      route({
        harvestedAt: sama,
        journey: journey({ dispatchedAt: sama, etaAt: sama, state: "sudah_tiba" }),
      })
    );
    expect(events.map((e) => e.key)).toEqual(["tiba", "berangkat", "panen"]);
  });

  it("kalimat jumlah memisahkan kejadian dari perkiraan", () => {
    // Kiriman di jalan: 2 kejadian sudah terjadi (berangkat, panen) + 1 perkiraan.
    expect(shipmentTimelineLabel(shipmentEvents(route()))).toBe("2 kejadian tercatat · 1 perkiraan");
    expect(
      shipmentTimelineLabel(shipmentEvents(route({ journey: journey({ state: "sudah_tiba" }) })))
    ).toBe("3 kejadian tercatat");
    expect(shipmentTimelineLabel([])).toBe("Belum ada kejadian yang tercatat server.");
  });

  it("ringkasan muatan untuk baris panen memakai format kg repo", () => {
    expect(shipmentLoadLabel(route())).toBe("800 kg telur");
    expect(shipmentLoadLabel(route({ commodity: null }))).toBe("800 kg");
    expect(shipmentLoadLabel(route({ quantityKg: null }))).toBeNull();
  });
});
