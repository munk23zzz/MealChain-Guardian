// @vitest-environment jsdom
//
// Fase 3 (2026-10-14): perilaku layer pemasok di peta — diuji dengan MapLibre
// yang dipalsukan supaya bisa diperiksa tanpa WebGL dan tanpa kredensial:
//
// - pin pemasok TIDAK digambar saat lapisan masih mati;
// - lapisan yang dinyalakan pada zoom jauh (peta Indonesia, ±4,5) belum
//   menggambar pin, dan pengguna diberi tahu kenapa (bukan diam-diam kosong);
// - zoom menengah (6–8) = titik tanpa nama; setelah zoom masuk (>= 8) nama
//   muncul; saat zoom dijauhkan lagi pin dibuang;
// - mematikan lapisan membuang SEMUA pin pemasok, tanpa menyentuh pin SPPG;
// - label aksesibilitas & popup pemasok berisi angka/status dari data.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type FakeMarker = {
  element: HTMLElement;
  lngLat: [number, number] | null;
  popup: { node?: HTMLElement } | null;
  added: boolean;
  removed: boolean;
};

// `vi.mock` diangkat (hoisted) ke atas berkas, jadi kelas palsu harus dibuat di
// dalam `vi.hoisted` — kalau tidak, "Cannot access 'FakeMap' before initialization".
const fake = vi.hoisted(() => {
  const markerLog: any[] = [];
  const mapLog: any[] = [];

  class FakeMap {
    zoom = 4.5;
    handlers: Record<string, Array<() => void>> = {};
    removed = false;
    constructor(public options: Record<string, unknown>) {
      mapLog.push(this);
    }
    addControl() {}
    fitBounds() {}
    resize() {}
    getZoom() {
      return this.zoom;
    }
    on(event: string, handler: () => void) {
      (this.handlers[event] ??= []).push(handler);
    }
    off(event: string, handler: () => void) {
      this.handlers[event] = (this.handlers[event] ?? []).filter((item) => item !== handler);
    }
    fire(event: string) {
      (this.handlers[event] ?? []).forEach((handler) => handler());
    }
    setZoom(zoom: number) {
      this.zoom = zoom;
    }
    remove() {
      this.removed = true;
    }
  }

  class FakeMarker {
    element: HTMLElement;
    lngLat: [number, number] | null = null;
    popup: { node?: HTMLElement } | null = null;
    added = false;
    removed = false;
    constructor(options: { element: HTMLElement }) {
      this.element = options.element;
      // Tiruan perilaku MapLibre 4.7: konstruktor MENIMPA aria-label elemen
      // dengan "Map marker". Kalau komponen memasang keterangan aksesibilitas
      // sebelum marker dibuat, teksnya hilang — dan tes ini gagal.
      this.element.setAttribute("aria-label", "Map marker");
      markerLog.push(this);
    }
    setLngLat(coords: [number, number]) {
      this.lngLat = coords;
      return this;
    }
    setPopup(popup: { node?: HTMLElement }) {
      this.popup = popup;
      return this;
    }
    addTo() {
      this.added = true;
      return this;
    }
    remove() {
      this.removed = true;
    }
    getElement() {
      return this.element;
    }
  }

  class FakePopup {
    node?: HTMLElement;
    constructor(public options: Record<string, unknown>) {}
    setDOMContent(node: HTMLElement) {
      this.node = node;
      return this;
    }
  }

  return { markerLog, mapLog, FakeMap, FakeMarker, FakePopup };
});

vi.mock("maplibre-gl", () => ({
  default: {
    Map: fake.FakeMap,
    Marker: fake.FakeMarker,
    Popup: fake.FakePopup,
    NavigationControl: class {},
    AttributionControl: class {},
  },
}));

const markerLog = fake.markerLog as FakeMarker[];
const mapLog = fake.mapLog as any[];

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
  items: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
      location: "Cianjur",
      commodity: "wortel",
      certification_status: "haccp",
      reliability_score: 0.93,
      latitude: -6.824,
      longitude: 107.1636,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "s2",
      name: "Telur Berkah Cianjur",
      location: "Cianjur",
      commodity: "telur",
      certification_status: "none",
      reliability_score: 0.38,
      latitude: -6.811,
      longitude: 107.1636,
      excluded_at_hub: true,
      excluded_scope_locations: ["Cianjur", "Jakarta"],
    },
  ],
};

let root: Root;
let host: HTMLDivElement;
let mounted = false;

function mount() {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mounted = true;
  act(() => {
    root.render(<SupplyMap locations={LOCATIONS} suppliers={SUPPLIERS} />);
  });
}

function unmount() {
  if (!mounted) return;
  act(() => root.unmount());
  mounted = false;
}

/** Potongan API peta palsu yang dipakai tes (kelas aslinya ada di vi.hoisted). */
type FakeMapInstance = {
  removed: boolean;
  zoom: number;
  setZoom: (zoom: number) => void;
  fire: (event: string) => void;
};

const map = () => mapLog[mapLog.length - 1] as FakeMapInstance;
const supplierMarkers = () =>
  markerLog.filter((marker) =>
    marker.element.className.includes("map-pin-supplier") && !marker.removed
  );
const locationMarkers = () =>
  markerLog.filter(
    (marker) =>
      marker.element.className.includes("map-pin") &&
      !marker.element.className.includes("map-pin-supplier") &&
      !marker.removed
  );

function toggle() {
  const button = host.querySelector<HTMLButtonElement>(".map-layer-toggle");
  if (!button) throw new Error("tombol layer pemasok tidak ada");
  act(() => {
    button.click();
  });
  return button;
}

function zoomTo(zoom: number) {
  act(() => {
    map().setZoom(zoom);
    map().fire("zoomend");
  });
}

beforeEach(() => {
  markerLog.length = 0;
  mapLog.length = 0;
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    }
  );
});

afterEach(() => {
  unmount();
  host?.remove();
  vi.unstubAllGlobals();
});

describe("SupplyMap — perilaku layer pemasok", () => {
  it("lapisan mati: hanya pin SPPG yang digambar", () => {
    mount();
    expect(mapLog).toHaveLength(1);
    expect(locationMarkers()).toHaveLength(1);
    expect(supplierMarkers()).toHaveLength(0);
  });

  it("dinyalakan pada zoom jauh: pin belum digambar, pengguna diberi tahu", () => {
    mount();
    const button = toggle();
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect(button.textContent).toBe("Sembunyikan pemasok (2)");
    expect(supplierMarkers()).toHaveLength(0);
    expect(host.querySelector(".map-layer-hint")?.textContent).toContain("Perbesar peta");
  });

  it("keterangan aksesibilitas bertahan setelah MapLibre menimpanya", () => {
    // MapLibre menulis aria-label="Map marker" saat marker dibuat; PIN SPPG
    // pernah kehilangan keterangannya karena dipasang sebelum itu.
    mount();
    expect(locationMarkers()[0]?.element.getAttribute("aria-label")).toContain(
      "permintaan 1.080 kg"
    );
    toggle();
    zoomTo(10);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.getAttribute("aria-label")).not.toBe("Map marker");
      expect(marker.element.getAttribute("aria-label")).toContain("keandalan");
      expect(marker.element.getAttribute("title")).toContain("keandalan");
    });
  });

  it("zoom menengah (6–8): pin tampil sebagai titik tanpa nama", () => {
    mount();
    toggle();
    zoomTo(6.5);
    expect(supplierMarkers()).toHaveLength(2);
    expect(host.querySelector(".map-layer-hint")).toBeNull();
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).toContain("map-pin-supplier-compact");
      expect(marker.element.getAttribute("aria-label")).toContain("keandalan");
    });
    // Nama tetap tersedia lewat tooltip/aria, jadi bukan informasi yang hilang.
    zoomTo(9);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).not.toContain("map-pin-supplier-compact");
    });
  });

  it("zoom masuk (>= 8): pin muncul, hint hilang", () => {
    mount();
    toggle();
    zoomTo(9);
    expect(supplierMarkers()).toHaveLength(2);
    expect(host.querySelector(".map-layer-hint")).toBeNull();
    // Posisi pin = koordinat pemasok, bukan koordinat SPPG.
    const telur = supplierMarkers().find((marker) =>
      marker.element.getAttribute("aria-label")?.includes("Telur Berkah Cianjur")
    );
    expect(telur?.lngLat).toEqual([107.1636, -6.811]);
  });

  it("zoom dijauhkan lagi: pin dibuang (tidak menyisakan penanda menggantung)", () => {
    mount();
    toggle();
    zoomTo(9);
    expect(supplierMarkers()).toHaveLength(2);
    zoomTo(5);
    expect(supplierMarkers()).toHaveLength(0);
    // Pin SPPG tidak ikut terpengaruh.
    expect(locationMarkers()).toHaveLength(1);
  });

  it("zoom dekat lebih dulu, lalu dinyalakan: pin langsung muncul", () => {
    mount();
    zoomTo(10);
    expect(supplierMarkers()).toHaveLength(0); // lapisan masih mati
    toggle();
    expect(supplierMarkers()).toHaveLength(2);
  });

  it("mematikan lapisan membuang semua pin pemasok", () => {
    mount();
    zoomTo(10);
    toggle();
    expect(supplierMarkers()).toHaveLength(2);
    toggle();
    expect(supplierMarkers()).toHaveLength(0);
    expect(host.querySelector(".map-layer-hint")).toBeNull();
    expect(locationMarkers()).toHaveLength(1);
  });

  it("kelas & popup pin memakai makna dari data (bukan enum internal)", () => {
    mount();
    zoomTo(10);
    toggle();
    const telur = supplierMarkers().find((marker) =>
      marker.element.getAttribute("aria-label")?.includes("Telur Berkah Cianjur")
    )!;
    expect(telur.element.className).toContain("map-pin-supplier-excluded");
    expect(telur.element.getAttribute("aria-label")).toBe(
      "Telur Berkah Cianjur — pemasok telur, keandalan 38%, hub Cianjur (dikecualikan di Cianjur, Jakarta)"
    );
    const popupText = telur.popup?.node?.textContent ?? "";
    expect(popupText).toContain("Komoditas: telur");
    expect(popupText).toContain("Keandalan: 38%");
    expect(popupText).toContain("Sertifikasi: Tidak bersertifikat");
    expect(popupText).toContain("Dikecualikan di: Cianjur, Jakarta");
    expect(popupText).not.toContain("none");

    const wortel = supplierMarkers().find((marker) =>
      marker.element.getAttribute("aria-label")?.includes("Wortel Lestari Cianjur")
    )!;
    expect(wortel.element.className).toContain("map-pin-supplier-ok");
    expect(wortel.popup?.node?.textContent).toContain("Sertifikasi: HACCP");
  });

  it("membongkar peta: peta dilepas tanpa error (penanda dibersihkan bersama peta)", () => {
    mount();
    zoomTo(10);
    toggle();
    expect(supplierMarkers()).toHaveLength(2);
    expect(() => unmount()).not.toThrow();
    expect(map().removed).toBe(true);
    // Pembersihan penanda didelegasikan ke map.remove() — sama seperti pin SPPG
    // yang sudah ada. Yang penting: tidak ada peta kedua yang dibuat dan tidak
    // ada error saat lapisan pemasok sedang aktif.
    expect(mapLog).toHaveLength(1);
  });
});
