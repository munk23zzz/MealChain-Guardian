// Kartu "Informasi pengiriman" — kontrak komponen (SSR, tanpa jsdom CSS).
// Yang diuji: struktur empat lapis (pil → stepper → angka kunci → kalimat),
// panel rincian yang bisa dibuka, dan aturan "tidak ada kartu kosong".
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ShipmentCard from "../components/ShipmentCard";

const PAYLOAD = {
  routes: [
    {
      batch_id: "B-1",
      supplier_id: "S1",
      supplier_name: "Supplier A",
      origin: { latitude: -6.8, longitude: 107.1, name: "Supplier A" },
      destination_id: "L1",
      destination_name: "SPPG Cianjur",
      destination: { latitude: -6.2, longitude: 106.8, name: "SPPG Cianjur" },
      commodity: "telur",
      quantity_kg: 800,
      harvested_at: "2026-10-16T01:00:00+00:00",
      usable_until: "2026-10-16T11:00:00+00:00",
      safety_status: "pass",
      straight_km: 13.1,
      road: {
        distance_km: 14.2,
        duration_min: 60,
        ratio_vs_straight: 1.08,
        geometry: { type: "LineString", coordinates: [[107.1, -6.8], [106.8, -6.2]] },
        source: "osrm",
        fetched_at: "2026-10-16T00:10:00+00:00",
      },
      journey: {
        dispatched_at: "2026-10-16T06:20:00+00:00",
        eta_at: "2026-10-16T07:20:00+00:00",
        state: "di_jalan",
        state_label: "Di jalan",
        travel_min: 60,
        elapsed_min: 40,
        remaining_min: 20,
        progress: 0.667,
        usable_until: "2026-10-16T11:00:00+00:00",
        arrives_before_usable_until: true,
      },
    },
  ],
};

describe("ShipmentCard", () => {
  it("SSR: empat lapis informasi ada (pil status, stepper, angka kunci, kalimat)", () => {
    const html = renderToStaticMarkup(<ShipmentCard routes={PAYLOAD} />);
    expect(html).toContain("Informasi pengiriman");
    expect(html).toContain("Supplier A → SPPG Cianjur");
    expect(html).toContain("shipment-pill");
    expect(html).toContain("Di jalan");
    expect(html).toContain("20 menit lagi");
    expect(html).toContain("shipment-step-active");
    expect(html).toContain("67% jalur");
    expect(html).toContain("14,2 km jalan");
    expect(html).toContain("800 kg telur");
    expect(html).toContain("masih sebelum batas layak");
  });

  it("rincian ada di dalam <details> (tertutup bawaan, tetap di DOM)", () => {
    const html = renderToStaticMarkup(<ShipmentCard routes={PAYLOAD} />);
    expect(html).toContain("<details");
    expect(html).toContain("Rincian kiriman");
    expect(html).not.toContain("<details open");
    expect(html).toContain("Jalur jalan");
    expect(html).toContain("Jarak lurus");
  });

  it("tanpa kiriman → tidak merender kartu kosong", () => {
    expect(renderToStaticMarkup(<ShipmentCard routes={{ routes: [] }} />)).toBe("");
    expect(renderToStaticMarkup(<ShipmentCard routes={null} />)).toBe("");
  });

  it("maks: membatasi blok kiriman dan menyatakan sisanya", () => {
    const banyak = {
      routes: [PAYLOAD.routes[0], { ...PAYLOAD.routes[0], supplier_id: "S2", supplier_name: "Supplier B" }],
    };
    const html = renderToStaticMarkup(<ShipmentCard routes={banyak} maks={1} />);
    expect(html).toContain("Supplier A");
    expect(html).not.toContain("Supplier B");
    expect(html).toContain("+1 lain");
  });

  it("hanya: menyaring per tujuan dan menghitung sisa dari yang cocok saja", () => {
    const dua = {
      routes: [
        PAYLOAD.routes[0],
        {
          ...PAYLOAD.routes[0],
          supplier_name: "Supplier B",
          destination_name: "Bandung",
          destination: { latitude: -6.9, longitude: 107.6, name: "Bandung" },
        },
      ],
    };
    const html = renderToStaticMarkup(
      <ShipmentCard routes={dua} hanya={(row) => row.destinationName === "SPPG Cianjur"} />
    );
    expect(html).toContain("Supplier A");
    expect(html).not.toContain("Supplier B");
    expect(html).toContain("1 kiriman");
    expect(html).not.toContain("+1 lain");
  });

  it("empty: pesan pengganti dirender saat tidak ada kiriman (bukan kartu kosong)", () => {
    const html = renderToStaticMarkup(
      <ShipmentCard
        routes={{ routes: [] }}
        title="Pasokan masuk menuju Jakarta"
        empty="Tidak ada kiriman aktif yang menuju lokasi ini menurut catatan jalur kiriman."
      />
    );
    expect(html).toContain("Pasokan masuk menuju Jakarta");
    expect(html).toContain("Tidak ada kiriman aktif");
    expect(html).not.toContain("shipment-item");
  });

  it("action: tombol per kiriman dirender di dalam blok kiriman", () => {
    const html = renderToStaticMarkup(
      <ShipmentCard routes={PAYLOAD} action={() => <button type="button">Periksa kiriman</button>} />
    );
    expect(html).toContain("Periksa kiriman");
    expect(html).toContain("shipment-action");
  });

  it("riwayat kejadian ada di dalam panel rincian, terbaru dulu, perkiraan ditandai", () => {
    const html = renderToStaticMarkup(<ShipmentCard routes={PAYLOAD} />);
    expect(html).toContain("Riwayat kiriman");
    expect(html).toContain("2 kejadian tercatat · 1 perkiraan");
    // Berada DI DALAM panel rincian (setelah <details>), bukan bentuk baru di kartu.
    expect(html.indexOf("<details")).toBeLessThan(html.indexOf("Riwayat kiriman"));
    // Terbaru dulu: estimasi (14.20) → berangkat (13.20) → panen (08.00).
    const urut = ["Estimasi tiba", "Berangkat dari pemasok", "Panen dicatat"].map((t) =>
      html.indexOf(t)
    );
    expect(urut.every((pos) => pos >= 0)).toBe(true);
    expect([...urut].sort((a, b) => a - b)).toEqual(urut);
    // Estimasi tidak boleh terbaca sebagai kejadian yang sudah terjadi.
    expect(html).toContain("perkiraan");
    expect(html).toContain("shipment-event-rencana");
    // Waktu hitung jalur: catatan kaki audit, bukan baris kejadian.
    expect(html).toContain("shipment-timeline-note");
    expect(html).toContain("Angka jalur dihitung server");
    expect(html.indexOf("shipment-timeline-note")).toBeGreaterThan(html.indexOf("Panen dicatat"));
  });

  it("jalur belum disinkron: sebabnya ditulis, bukan 0 km", () => {
    const html = renderToStaticMarkup(
      <ShipmentCard
        routes={{
          routes: [
            {
              ...PAYLOAD.routes[0],
              road: null,
              road_missing_reason: "belum_disinkron",
              journey: { ...PAYLOAD.routes[0].journey, state: "tidak_diketahui", eta_at: null },
            },
          ],
        }}
      />
    );
    expect(html).toContain("belum disinkronkan");
    expect(html).not.toContain("0,0 km");
    expect(html).toContain("lurus");
  });
});
