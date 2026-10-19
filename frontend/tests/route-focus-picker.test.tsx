// Pemilih kiriman untuk disorot di peta (Arah C) — kontrak komponen (SSR).
// Menjaga jalur setara bagi keyboard & pembaca layar: garis MapLibre di kanvas
// tidak bisa difokus, jadi tombol inilah yang harus memuat nama + keadaan.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import RouteFocusPicker from "../components/RouteFocusPicker";
import { focusOptions } from "../lib/route-focus";

const PAYLOAD = {
  routes: [
    {
      supplier_id: "S1",
      supplier_name: "Supplier A",
      origin: { latitude: -6.8, longitude: 107.1 },
      destination_id: "L1",
      destination_name: "Jakarta",
      destination: { latitude: -6.2, longitude: 106.8 },
      quantity_kg: 800,
      commodity: "telur",
      road: {
        distance_km: 110.4,
        duration_min: 84,
        geometry: { type: "LineString", coordinates: [[107.1, -6.8], [106.8, -6.2]] },
        source: "osrm",
      },
      journey: {
        dispatched_at: "2026-10-16T12:24:00+00:00",
        eta_at: "2026-10-16T12:24:00+00:00",
        state: "di_jalan",
        state_label: "Di jalan",
        remaining_min: 20,
        progress: 0.76,
      },
    },
    {
      supplier_id: "S2",
      supplier_name: "Supplier B",
      origin: { latitude: -6.9, longitude: 107.6 },
      destination_id: "L2",
      destination_name: "Bandung",
      destination: { latitude: -6.9, longitude: 107.6 },
      journey: { state: "sudah_tiba", state_label: "Sudah tiba", eta_at: "2026-10-16T13:00:00+00:00" },
    },
  ],
};

const noop = () => {};

describe("RouteFocusPicker", () => {
  it("SSR: satu tombol per kiriman + tombol Semua dengan JUMLAH sebenarnya", () => {
    const html = renderToStaticMarkup(
      <RouteFocusPicker
        options={focusOptions(PAYLOAD)}
        focused={null}
        total={2}
        onFocus={noop}
      />
    );
    expect(html).toContain("Semua (2)");
    expect(html).toContain("Supplier A → JKT");
    expect(html).toContain("Supplier B → BDG");
    expect(html).toContain("Di jalan · 20 menit lagi");
    expect(html).toContain("aria-label=\"Pilih kiriman yang disorot di peta\"");
  });

  it("tanpa fokus: tombol Semua yang aktif (aria-pressed hanya pada satu)", () => {
    const html = renderToStaticMarkup(
      <RouteFocusPicker options={focusOptions(PAYLOAD)} focused={null} total={2} onFocus={noop} />
    );
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(html).toContain("route-focus-pill is-active");
  });

  it("dengan fokus: hanya kiriman itu yang ditandai aktif", () => {
    const html = renderToStaticMarkup(
      <RouteFocusPicker
        options={focusOptions(PAYLOAD)}
        focused="S1->L1"
        total={2}
        onFocus={noop}
      />
    );
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1);
    const aktif = html.slice(html.indexOf("aria-pressed=\"true\""));
    expect(aktif).toContain("Supplier A → JKT");
  });

  it("tidak ada kiriman → tidak ada bentuk kosong yang dirender", () => {
    const html = renderToStaticMarkup(
      <RouteFocusPicker options={[]} focused={null} total={0} onFocus={noop} />
    );
    expect(html).toBe("");
  });
});
