// "Papan kiriman" — kontrak komponen (SSR, tanpa jsdom).
// Yang diuji: sepuluh kolom Arah B ada, satu baris per kiriman, pilihan urutan
// dengan pilihan aktif yang dinyatakan (aria-pressed), dan "tidak ada data"
// ditulis sebagai "—" — bukan angka nol.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ShipmentBoard from "../components/ShipmentBoard";

const PAYLOAD = {
  routes: [
    {
      batch_id: "B-1",
      supplier_id: "S1",
      supplier_name: "Supplier A",
      origin: { latitude: -6.8, longitude: 107.1, name: "Supplier A" },
      destination_id: "L1",
      destination_name: "Jakarta",
      destination: { latitude: -6.2, longitude: 106.8, name: "Jakarta" },
      commodity: "telur",
      quantity_kg: 800,
      harvested_at: "2026-10-16T01:00:00+00:00",
      usable_until: "2026-11-07T11:00:00+00:00",
      safety_status: "pass",
      straight_km: 78.35,
      road: {
        distance_km: 110.4,
        duration_min: 84.3,
        ratio_vs_straight: 1.41,
        geometry: { type: "LineString", coordinates: [[107.13, -6.85], [106.84, -6.2]] },
        source: "osrm",
        fetched_at: "2026-10-16T00:10:00+00:00",
      },
      journey: {
        dispatched_at: "2026-10-16T12:24:00+00:00",
        eta_at: "2026-10-16T12:24:00+00:00",
        state: "di_jalan",
        state_label: "Di jalan",
        travel_min: 84,
        elapsed_min: 64,
        remaining_min: 20,
        progress: 0.76,
        usable_until: "2026-11-07T11:00:00+00:00",
        arrives_before_usable_until: true,
      },
    },
    {
      batch_id: "B-2",
      supplier_id: "S2",
      supplier_name: "Supplier B",
      origin: { latitude: -6.9, longitude: 107.6, name: "Supplier B" },
      destination_id: "L2",
      destination_name: "Bandung",
      destination: { latitude: -6.9, longitude: 107.6, name: "Bandung" },
      commodity: "ayam",
      quantity_kg: 200,
      usable_until: null,
      safety_status: "fail",
      straight_km: null,
      road: null,
      road_missing_reason: "belum_disinkron",
      journey: null,
    },
  ],
};

describe("ShipmentBoard", () => {
  it("SSR: sepuluh kolom Arah B ada, satu baris per kiriman", () => {
    const html = renderToStaticMarkup(<ShipmentBoard routes={PAYLOAD} />);
    for (const kolom of [
      "Pemasok",
      "Tujuan",
      "Muatan",
      "Jalur",
      "Berangkat",
      "Estimasi tiba",
      "Sisa",
      "Masa layak",
      "Mutu",
      "Keadaan",
    ]) {
      expect(html).toContain(`>${kolom}</th>`);
    }
    expect(html).toContain("Papan kiriman");
    expect(html).toContain("2 kiriman · 1 di jalan · 1 tanpa laporan server");
    expect(html.match(/<tr>/g)?.length).toBe(3); // 1 kepala + 2 baris
  });

  it("SSR: angka server dipakai apa adanya (jalur, muatan, sisa, mutu, keadaan)", () => {
    const html = renderToStaticMarkup(<ShipmentBoard routes={PAYLOAD} />);
    expect(html).toContain("110,4 km jalan · ± 1 jam 24 menit");
    expect(html).toContain("1,41× jarak lurus");
    expect(html).toContain("800 kg telur");
    expect(html).toContain("20 menit");
    expect(html).toContain("Lolos uji");
    expect(html).toContain("shipment-pill-moving");
    expect(html).toContain("tiba sebelum batas");
  });

  it("SSR: baris tanpa data menulis '—' dan sebabnya, bukan nol", () => {
    const html = renderToStaticMarkup(<ShipmentBoard routes={PAYLOAD} />);
    expect(html).toContain("belum disinkronkan");
    expect(html).toContain("Belum dilaporkan");
    expect(html).toContain("Gagal uji");
    expect(html).not.toMatch(/>0 km</);
  });

  it("SSR: pilihan urutan dinyatakan — 'Paling mendesak' aktif lebih dulu", () => {
    const html = renderToStaticMarkup(<ShipmentBoard routes={PAYLOAD} />);
    expect(html).toContain("Urutkan:");
    expect(html).toContain("Paling mendesak");
    expect(html).toContain("Estimasi tiba");
    expect(html).toContain("Batas layak");
    expect(html).toContain('aria-pressed="true"');
    expect(html.match(/aria-pressed="true"/g)?.length).toBe(1);
  });

  it("SSR: penyaring cakupan dan pesan pengganti dihormati", () => {
    const hanyaJakarta = renderToStaticMarkup(
      <ShipmentBoard routes={PAYLOAD} hanya={(row) => row.destinationName === "Jakarta"} />
    );
    expect(hanyaJakarta).toContain("Supplier A");
    expect(hanyaJakarta).not.toContain("Supplier B");
    expect(hanyaJakarta).toContain("1 kiriman");

    const kosong = renderToStaticMarkup(
      <ShipmentBoard routes={{ routes: [] }} empty="Tidak ada kiriman aktif di jaringan." />
    );
    expect(kosong).toContain("Tidak ada kiriman aktif di jaringan.");
    expect(kosong).not.toContain("<table");
  });

  it("SSR: tanpa kiriman dan tanpa pesan pengganti → tidak ada kartu kosong", () => {
    expect(renderToStaticMarkup(<ShipmentBoard routes={null} />)).toBe("");
  });
});
