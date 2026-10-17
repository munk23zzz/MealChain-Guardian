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
  const popupLog: any[] = [];

  class FakeMap {
    zoom = 4.5;
    handlers: Record<string, Array<() => void>> = {};
    removed = false;
    constructor(public options: Record<string, unknown>) {
      mapLog.push(this);
    }
    // Kontrol (langkah 7b-1): tiruan MENCATAT kontrol + memanggil `onAdd`-nya
    // seperti MapLibre, supaya elemen buatan kontrol sendiri (tombol "Tampilkan
    // semua") benar-benar ada di DOM dan bisa diuji — bukan hanya "addControl
    // pernah dipanggil".
    controls: { control: any; position?: string }[] = [];
    controlElements: HTMLElement[] = [];
    fitBoundsLog: unknown[][] = [];
    addControl(control: any, position?: string) {
      this.controls.push({ control, position });
      if (typeof control?.onAdd === "function") this.controlElements.push(control.onAdd(this));
    }
    // Fase 10: komponen kini juga memasang source/layer GeoJSON (garis jalur
    // kiriman), jadi tiruan peta perlu API-nya seperti MapLibre asli.
    sources: Record<string, { data: unknown; setData: (data: unknown) => void }> = {};
    layers: Record<string, Record<string, unknown>> = {};
    styleLoaded = true;
    isStyleLoaded() {
      return this.styleLoaded;
    }
    getSource(id: string) {
      return this.sources[id];
    }
    getLayer(id: string) {
      return this.layers[id];
    }
    /** MapLibre asli menulis properti paint pada layer yang sudah ada; tiruan
     *  melakukan hal yang sama supaya efek visual (mis. meredupkan garis saat
     *  satu jalur disorot) bisa diperiksa hasilnya, bukan hanya "dipanggil". */
    setPaintProperty(id: string, prop: string, value: unknown) {
      const layer = this.layers[id];
      if (!layer) return;
      const paint = (layer.paint ?? {}) as Record<string, unknown>;
      paint[prop] = value;
      layer.paint = paint;
      this.paintLog.push([id, prop, value]);
    }
    paintLog: [string, string, unknown][] = [];
    addSource(id: string, spec: { data: unknown }) {
      const sumber = {
        data: spec.data,
        setData: (data: unknown) => {
          sumber.data = data;
        },
      };
      this.sources[id] = sumber;
    }
    addLayer(spec: { id: string }) {
      this.layers[spec.id] = spec as unknown as Record<string, unknown>;
    }
    removeLayer(id: string) {
      delete this.layers[id];
    }
    removeSource(id: string) {
      delete this.sources[id];
    }
    fitBounds(bounds?: unknown, options?: unknown) {
      this.fitBoundsLog.push([bounds, options]);
    }
    resize() {}
    getZoom() {
      return this.zoom;
    }
    // MapLibre menerima bentuk `on(tipe, layerId, handler)` untuk event layer
    // (Fase 10 memakai itu untuk popup garis) — handler selalu argumen terakhir.
    on(event: string, ...args: unknown[]) {
      const handler = args[args.length - 1] as () => void;
      (this.handlers[event] ??= []).push(handler);
    }
    off(event: string, ...args: unknown[]) {
      const handler = args[args.length - 1];
      this.handlers[event] = (this.handlers[event] ?? []).filter((item) => item !== handler);
    }
    fire(event: string, payload?: unknown) {
      (this.handlers[event] ?? []).forEach((handler) => (handler as (arg?: unknown) => void)(payload));
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
    setLngLat() {
      return this;
    }
    setDOMContent(node: HTMLElement) {
      this.node = node;
      return this;
    }
    addTo() {
      popupLog.push(this);
      return this;
    }
  }

  return { markerLog, mapLog, popupLog, FakeMap, FakeMarker, FakePopup };
});

vi.mock("maplibre-gl", () => ({
  default: {
    Map: fake.FakeMap,
    Marker: fake.FakeMarker,
    Popup: fake.FakePopup,
    NavigationControl: class {},
    AttributionControl: class {},
    // Langkah 7b-1: peta kini memasang kontrol skala (riset §5 C3). Kelasnya
    // diberi nama supaya tes bisa memastikan kontrol INI yang dipasang.
    ScaleControl: class ScaleControl {},
  },
}));

const markerLog = fake.markerLog as FakeMarker[];
const mapLog = fake.mapLog as any[];
const popupLog = fake.popupLog as any[];

import SupplyMap from "../components/SupplyMap";
import { FOCUS_ALL, FOCUS_CLEAR_LABEL, focusLabel, focusPick } from "../lib/route-focus";

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

function mountWithRoutes() {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mounted = true;
  act(() => {
    root.render(<SupplyMap locations={LOCATIONS} supplierRoutes={ROUTES} />);
  });
}

function routeToggle() {
  const button = host.querySelector<HTMLButtonElement>(".map-route-toggle");
  if (!button) throw new Error("tombol layer jalur kiriman tidak ada");
  return button;
}

/** Sakelar "Rincian lapisan peta" (bilah di bawah kanvas). */
function infoButton() {
  const button = host.querySelector<HTMLButtonElement>(".map-layer-info-toggle");
  if (!button) throw new Error("tombol rincian lapisan peta tidak ada");
  return button;
}

function infoPanel() {
  const panel = host.querySelector<HTMLElement>(".map-layer-info-panel");
  if (!panel) throw new Error("panel rincian lapisan peta tidak ada");
  return panel;
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
  /** Opsi konstruktor peta asli (mis. `cooperativeGestures`, langkah 7b-2). */
  options: Record<string, unknown>;
  sources: Record<string, { data: unknown; setData: (data: unknown) => void }>;
  layers: Record<string, Record<string, unknown>>;
  setZoom: (zoom: number) => void;
  fire: (event: string) => void;
  /** Kontrol yang dipasang + elemen hasil `onAdd()` + jejak `fitBounds()`
   *  (langkah 7b-1: skala & tombol "Tampilkan semua"). */
  controls: { control: any; position?: string }[];
  controlElements: HTMLElement[];
  fitBoundsLog: unknown[][];
};

/** Jalur kiriman uji — angka dari respons nyata `GET /supplier-routes`. */
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
      // Perjalanan kiriman (Fase 12): berangkat 21.30 WIB, tiba ± 22.54 WIB.
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

/** Kiriman yang gagal uji — untuk menguji entri legenda nada bahaya. */
const ROUTES_GAGAL = {
  routes: [{ ...ROUTES.routes[0], batch_id: "b2", destination_name: "Bogor", safety_status: "fail" }],
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
    expect(button.textContent).toBe("Pemasok (2)");
    // Kalimat panjang "tampilkan/sembunyikan" pindah ke tooltip (arah pemilik
    // 2026-10-16: tombol lapisan dibuat kecil) — bukan dihapus.
    expect(button.title).toBe("Sembunyikan pemasok (2)");
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

  it("memasang source & layer garis untuk jalur kiriman (Fase 10)", () => {
    mountWithRoutes();
    const peta = map();
    expect(peta.sources["supplier-routes"]).toBeDefined();
    // K1: dua layer dari satu source — padat (sudah ditempuh) dan putus-putus
    // (sisa/perkiraan). `line-dasharray` tidak bisa data-driven di MapLibre,
    // jadi pemisahan dilakukan lewat filter `kind` pada fitur.
    const done = peta.layers["supplier-route-line-done"];
    const todo = peta.layers["supplier-route-line-todo"];
    expect(done).toBeDefined();
    expect(todo).toBeDefined();
    expect(done.type).toBe("line");
    expect(done.filter).toEqual(["==", ["get", "kind"], "done"]);
    expect(todo.filter).toEqual(["==", ["get", "kind"], "todo"]);
    const cat = (layer: { paint?: unknown }) => (layer.paint ?? {}) as Record<string, unknown>;
    expect(cat(done)["line-dasharray"]).toBeUndefined();
    expect(cat(todo)["line-dasharray"]).toEqual([4, 3]);
    // Geometrinya dari server (cache OSRM) — bukan garis lurus buatan UI.
    const data = peta.sources["supplier-routes"].data as {
      features: { properties: { kind: string }; geometry: { coordinates: number[][] } }[];
    };
    expect(data.features.map((fitur) => fitur.properties.kind)).toEqual(["done", "todo"]);
    expect(data.features[0].geometry.coordinates[0]).toEqual([107.1306, -6.854]);
    expect(data.features[1].geometry.coordinates.slice(-1)[0]).toEqual([106.8456, -6.2088]);
  });

  it("jalur yang belum ditempuh memakai warna berbeda dari yang sudah (bukan hijau yang sama)", () => {
    mountWithRoutes();
    const peta = map();
    const warna = (id: string) =>
      (peta.layers[id].paint as Record<string, unknown>)["line-color"] as unknown[];
    // Bentuk ekspresi: ["match", ["get","tone"], "fail", <merah>, <warna dasar>].
    const done = warna("supplier-route-line-done");
    const todo = warna("supplier-route-line-todo");
    expect(done[3]).toBe("#C62828");
    expect(done[4]).toBe("#2E7D32");
    expect(todo[3]).toBe("#C62828");
    // Sisa perjalanan = perkiraan, bukan fakta terkirim → nada berbeda (biru aksi UI).
    expect(todo[4]).toBe("#2563EB");
    expect(todo[4]).not.toBe(done[4]);
  });

  it("penanda memakai ikon: bangunan untuk SPPG, truk untuk pemasok", () => {
    mount();
    const lokasi = locationMarkers()[0];
    // Pin SPPG = kepala bulat + ekor segitiga (koordinat di ujung ekor).
    expect(lokasi.element.querySelector("svg.map-pin-icon-sppg")).not.toBeNull();
    expect(lokasi.element.querySelector(".map-pin-tip")).not.toBeNull();
    // Lapisan pemasok mati secara bawaan (keputusan Fase 3) dan pin baru muncul
    // setelah peta diperbesar — hidupkan keduanya dulu.
    toggle();
    zoomTo(9);
    const pemasok = supplierMarkers()[0];
    expect(pemasok.element.querySelector("svg.map-pin-icon-supplier")).not.toBeNull();
    // Ikon hiasan: maknanya sudah ada di aria-label penanda.
    pemasok.element
      .querySelectorAll("svg.map-pin-icon")
      .forEach((ikon) => expect(ikon.getAttribute("aria-hidden")).toBe("true"));
  });

  it("memberi alas putih (casing) di bawah garis jalur supaya terbaca di basemap terang", () => {
    mountWithRoutes();
    const peta = map();
    const casingDone = peta.layers["supplier-route-casing-done"];
    const casingTodo = peta.layers["supplier-route-casing-todo"];
    expect(casingDone).toBeDefined();
    expect(casingTodo).toBeDefined();
    // Alas memakai source + filter yang sama; kalau tidak, bentuknya bisa beda
    // dengan garis yang dialasinnya.
    expect(casingDone.source).toBe("supplier-routes");
    expect(casingTodo.filter).toEqual(["==", ["get", "kind"], "todo"]);
    const paint = (layer: { paint?: unknown }) => (layer.paint ?? {}) as Record<string, unknown>;
    expect(paint(casingDone)["line-color"]).toBe("#FFFFFF");
    // Bagian putus-putus: alas ikut putus, supaya tidak terbaca sebagai jalan solid.
    expect(paint(casingTodo)["line-dasharray"]).toEqual([4, 3]);
    // Urutan render: alas HARUS ditambahkan sebelum garis (di bawahnya).
    const urutan = Object.keys(peta.layers);
    expect(urutan.indexOf("supplier-route-casing-done")).toBeLessThan(
      urutan.indexOf("supplier-route-line-done")
    );
    expect(urutan.indexOf("supplier-route-casing-todo")).toBeLessThan(
      urutan.indexOf("supplier-route-line-todo")
    );
    // Lebih lebar dari garis: tanpa selisih, alasnya tidak terlihat sama sekali.
    const lebarAlas = paint(casingDone)["line-width"] as unknown[];
    const lebarGaris = paint(peta.layers["supplier-route-line-done"])["line-width"] as unknown[];
    expect(Number(lebarAlas[4])).toBeGreaterThan(Number(lebarGaris[4]));
  });

  it("tanpa data jalur: tidak ada source sama sekali (bukan garis kosong)", () => {
    mount();
    expect(map().sources["supplier-routes"]).toBeUndefined();
    expect(host.querySelector(".map-route-toggle")).toBeNull();
  });

  it("sakelar jalur dimatikan membuang layer dan source", () => {
    mountWithRoutes();
    expect(map().layers["supplier-route-line-done"]).toBeDefined();
    expect(map().layers["supplier-route-line-todo"]).toBeDefined();
    act(() => {
      routeToggle().click();
    });
    expect(map().layers["supplier-route-line-done"]).toBeUndefined();
    expect(map().layers["supplier-route-line-todo"]).toBeUndefined();
    expect(map().sources["supplier-routes"]).toBeUndefined();
    expect(routeToggle().textContent).toContain("Jalur kiriman (1)");
    expect(routeToggle().title).toContain("Tampilkan jalur kiriman (1)");
  });

  it("legenda jalur menyebut asal OSRM dan jumlahnya", () => {
    mountWithRoutes();
    expect(host.textContent).toContain("Jalur kiriman:");
    expect(host.textContent).toContain("Sudah ditempuh");
    expect(host.textContent).toContain("Sisa perjalanan (perkiraan)");
    expect(host.textContent).toContain("1 jalur kiriman");
    expect(host.textContent).toContain("OSRM");
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

describe("SupplyMap — rincian lapisan peta (bisa dibuka & ditutup)", () => {
  /** Render sewenang-wenang (jumlah lapisan berbeda per kasus). */
  function mountEl(node: Parameters<Root["render"]>[0]) {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mounted = true;
    act(() => {
      root.render(node);
    });
  }

  it("tertutup secara bawaan: angka ringkas terlihat, kalimat penuh hanya dilipat", () => {
    mount();
    expect(infoButton().getAttribute("aria-expanded")).toBe("false");
    expect(infoPanel().getAttribute("data-open")).toBe("false");
    // Kalimat jujur TIDAK dihapus dari DOM (tidak ada penyembunyian diam-diam);
    // hanya dilipat. Angka ringkas di bilah tetap terbaca tanpa membuka apa pun.
    expect(infoPanel().textContent).toContain("pemasok ditampilkan (nasional");
    expect(host.querySelector(".map-layer-tags")?.textContent).toContain("pemasok");
  });

  it("satu klik membuka, klik berikutnya menutup", () => {
    mount();
    act(() => infoButton().click());
    expect(infoButton().getAttribute("aria-expanded")).toBe("true");
    expect(infoPanel().getAttribute("data-open")).toBe("true");
    act(() => infoButton().click());
    expect(infoButton().getAttribute("aria-expanded")).toBe("false");
    expect(infoPanel().getAttribute("data-open")).toBe("false");
  });

  it("panel memuat catatan pemasok & jalur saat kedua lapisan ada", () => {
    mountEl(<SupplyMap locations={LOCATIONS} suppliers={SUPPLIERS} supplierRoutes={ROUTES} />);
    expect(infoPanel().textContent).toContain("pemasok ditampilkan (nasional");
    expect(infoPanel().textContent).toContain("OSRM");
    expect(host.querySelector(".map-layer-tags")?.textContent).toContain("jalur kiriman");
    // Sakelar lapisan tetap satu-satunya elemen yang mengapung di kanvas; bilah
    // rincian ada DI BAWAH peta (bukan overlay yang menutupi pin).
    expect(
      host.querySelector(".map-overlay-toggles")?.querySelectorAll(".map-layer-toggle")
    ).toHaveLength(2);
  });

  it("tanpa kedua lapisan: bilah rincian tidak dirender sama sekali", () => {
    mountEl(<SupplyMap locations={LOCATIONS} />);
    expect(host.querySelector(".map-layer-info")).toBeNull();
    expect(host.querySelector(".map-layer-info-toggle")).toBeNull();
  });
});

describe("SupplyMap — kotak Info map (nama, susunan isi, perjalanan kiriman)", () => {
  /** Render sewenang-wenang (jumlah lapisan berbeda per kasus). */
  function mountEl(node: Parameters<Root["render"]>[0]) {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mounted = true;
    act(() => {
      root.render(node);
    });
  }

  /** Tombol lipat kotak Info map (dulu "Legenda peta"). */
  function infoMapToggle() {
    const button = host.querySelector<HTMLButtonElement>(".map-legend-toggle");
    if (!button) throw new Error("tombol Info map tidak ada");
    return button;
  }

  function infoMap() {
    const box = host.querySelector<HTMLElement>(".map-legend-boxes");
    if (!box) throw new Error("kotak Info map tidak ada");
    return box;
  }

  /** Sakelar lapisan pemasok (satu-satunya `.map-layer-toggle` tanpa kelas rute). */
  function supplierToggle() {
    const button = host.querySelector<HTMLButtonElement>(
      ".map-layer-toggle:not(.map-route-toggle)"
    );
    if (!button) throw new Error("tombol lapisan pemasok tidak ada");
    return button;
  }

  function bukaInfoMap() {
    act(() => infoMapToggle().click());
  }

  it("namanya 'Info map', bukan 'Legenda peta'", () => {
    mountWithRoutes();
    expect(infoMapToggle().textContent).toContain("Info map");
    expect(infoMapToggle().getAttribute("aria-expanded")).toBe("false");
    expect(infoMap().getAttribute("aria-label")).toBe("Info map");
    expect(host.textContent).not.toContain("Legenda peta");
  });

  it("kelompok keterangan hanya untuk lapisan yang hidup", () => {
    mountEl(<SupplyMap locations={LOCATIONS} suppliers={SUPPLIERS} supplierRoutes={ROUTES} />);
    bukaInfoMap();
    // Bawaan: jalur hidup, pemasok mati → keterangan pemasok belum ditampilkan.
    expect(infoMap().querySelector('[aria-label="Keterangan jalur kiriman"]')).not.toBeNull();
    expect(infoMap().querySelector('[aria-label="Keterangan pemasok"]')).toBeNull();

    act(() => supplierToggle().click());
    const kotakPemasok = infoMap().querySelector('[aria-label="Keterangan pemasok"]');
    expect(kotakPemasok).not.toBeNull();
    expect(kotakPemasok?.textContent).toContain("Keandalan rendah");

    // Mematikan lapisan jalur: keterangan jalur + daftar perjalanan ikut hilang,
    // supaya tidak ada warna/jam yang diterangkan tanpa gambarnya di peta.
    act(() => routeToggle().click());
    expect(infoMap().querySelector('[aria-label="Keterangan jalur kiriman"]')).toBeNull();
    expect(infoMap().querySelector('[aria-label="Perjalanan kiriman"]')).toBeNull();
    expect(infoMap().querySelector('[aria-label="Keterangan status lokasi"]')).not.toBeNull();
  });

  it("perjalanan kiriman menyebut estimasi tiba saat lapisan jalur hidup", () => {
    mountWithRoutes();
    bukaInfoMap();
    const perjalanan = infoMap().querySelector('[aria-label="Perjalanan kiriman"]');
    expect(perjalanan).not.toBeNull();
    expect(perjalanan?.textContent).toContain("Perjalanan kiriman:");
    expect(perjalanan?.textContent).toContain("Jakarta · di jalan · tiba ± 22.54");
    expect(perjalanan?.textContent).toContain("24 menit lagi");
    // Tanpa perlu membuka kotak: tag bilah rincian sudah menyebut estimasi tiba.
    expect(host.querySelector(".map-layer-tags")?.textContent).toContain(
      "tiba terdekat ± 22.54"
    );
  });

  it("entri 'gagal uji' hanya muncul kalau ada kiriman bergaris gagal", () => {
    mountWithRoutes();
    expect(infoMap().textContent).toContain("Sudah ditempuh");
    expect(infoMap().textContent).toContain("Sisa perjalanan (perkiraan)");
    expect(infoMap().textContent).not.toContain("gagal uji");

    unmount();
    mountEl(<SupplyMap locations={LOCATIONS} supplierRoutes={ROUTES_GAGAL} />);
    expect(infoMap().textContent).toContain("Jalur kiriman gagal uji");
  });

  it("kiriman yang belum berangkat tidak diberi jam tiba", () => {
    const belumBerangkat = {
      routes: [
        {
          ...ROUTES.routes[0],
          destination_name: "Bandung",
          journey: {
            ...ROUTES.routes[0].journey,
            state: "belum_berangkat",
            state_label: "Belum berangkat",
            dispatched_at: null,
            eta_at: null,
            remaining_min: null,
            progress: null,
          },
        },
      ],
    };
    mountEl(<SupplyMap locations={LOCATIONS} supplierRoutes={belumBerangkat} />);
    bukaInfoMap();
    const perjalanan = infoMap().querySelector('[aria-label="Perjalanan kiriman"]');
    expect(perjalanan?.textContent).toContain("belum berangkat · estimasi tiba belum ada");
    expect(perjalanan?.textContent).not.toContain("tiba ±");
    // Tag lapisan pun tidak mengarang jam; ia jatuh ke keterangan asal geometri.
    expect(host.querySelector(".map-layer-tags")?.textContent).toContain("jalur jalan OSRM");
  });

  /**
   * Arah pemilik 2026-10-16 (kutipan): "Jarak lurus: 78,4 km, Tiba sebelum batas
   * layak (25 Okt 2026) dan ini Jalur jalan 1,41× jarak lurus (jalan berkelok,
   * bukan garis lurus) hapus saja."
   *
   * Diuji di tingkat POPUP yang benar-benar dirender (bukan hanya fungsi murni),
   * karena ketiga baris itu hanya pernah terlihat saat pengguna mengklik garis.
   */
  it("popup garis tidak lagi memuat jarak lurus, rasio, dan kalimat batas layak", () => {
    mountWithRoutes();
    const map = mapLog[mapLog.length - 1];
    const fitur = (map.sources["supplier-routes"].data as any).features[0];
    map.fire("click", {
      features: [{ properties: fitur.properties }],
      lngLat: { lng: 107.1, lat: -6.85 },
    });

    const popup = popupLog[popupLog.length - 1];
    expect(popup).toBeTruthy();
    const baris = Array.from((popup.node as HTMLElement).querySelectorAll(".map-popup-line")).map(
      (p) => p.textContent ?? ""
    );
    const teks = baris.join(" | ");
    // Yang tetap ada: identitas jalur, perjalanan, masa layak.
    expect(teks).toContain("Jalur jalan (OSRM)");
    expect(teks).toContain("Estimasi tiba: ± 22.54 WIB");
    expect(teks).toContain("Layak dipakai s/d");
    // Yang dibuang.
    expect(teks).not.toContain("Jarak lurus");
    expect(teks).not.toContain("jarak lurus");
    expect(teks).not.toContain("berkelok");
    expect(teks).not.toContain("Tiba sebelum batas layak");
  });
});

describe("SupplyMap — sorotan kiriman di peta (Arah C)", () => {
  /** Mount dengan pilihan fokus yang dikendalikan pemanggil. */
  function mountFocus(
    focused: string | null,
    onFocus: ((id: string) => void) | null = () => {}
  ) {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mounted = true;
    act(() => {
      root.render(
        <SupplyMap
          locations={LOCATIONS}
          supplierRoutes={ROUTES}
          focusedRouteId={focused}
          onFocusRoute={onFocus}
        />
      );
    });
  }

  it("tanpa kiriman disorot: tidak ada layer sorotan yang tertinggal", () => {
    mountFocus(null);
    expect(map().layers["supplier-route-focus-done"]).toBeUndefined();
    expect(map().layers["supplier-route-focus-todo"]).toBeUndefined();
    expect(map().sources["supplier-route-focus"]).toBeUndefined();
  });

  it("kiriman disorot: dua potong garis (padat = sudah ditempuh, putus-putus = sisa)", () => {
    mountFocus("s1->l1");
    expect(map().layers["supplier-route-focus-done"]).toBeTruthy();
    expect(map().layers["supplier-route-focus-todo"]).toBeTruthy();
    const data = map().sources["supplier-route-focus"].data as {
      features: { properties: { kind: string } }[];
    };
    expect(data.features.map((f) => f.properties.kind)).toEqual(["done", "todo"]);
    // Garis dasar TETAP ada — sorotan menambah, bukan menggantikan.
    expect(map().layers["supplier-route-line-done"]).toBeTruthy();
  });

  it("sorotan meredupkan garis dasar, dan warna normal kembali saat dilepas", () => {
    mountFocus("s1->l1");
    const opasitas = () =>
      (map().layers["supplier-route-line-done"].paint as Record<string, unknown>)[
        "line-opacity"
      ];
    // Garis lain tidak dihapus (konteks jaringan tetap ada), hanya diredupkan.
    expect(opasitas()).toBeLessThan(0.5);
    act(() => {
      root.render(
        <SupplyMap
          locations={LOCATIONS}
          supplierRoutes={ROUTES}
          focusedRouteId={null}
          onFocusRoute={() => {}}
        />
      );
    });
    expect(opasitas()).toBeGreaterThan(0.8);
  });

  it("melepas sorotan membuang layer + source-nya (tidak ada garis tersisa)", () => {
    mountFocus("s1->l1");
    expect(map().layers["supplier-route-focus-done"]).toBeTruthy();
    act(() => {
      root.render(
        <SupplyMap
          locations={LOCATIONS}
          supplierRoutes={ROUTES}
          focusedRouteId={null}
          onFocusRoute={() => {}}
        />
      );
    });
    expect(map().layers["supplier-route-focus-done"]).toBeUndefined();
    expect(map().sources["supplier-route-focus"]).toBeUndefined();
  });

  it("id tak dikenal = tampilan semua (gagal-tertutup, bukan menyorot kiriman lain)", () => {
    mountFocus("s9->l9");
    expect(map().layers["supplier-route-focus-done"]).toBeUndefined();
  });

  it("pemilih memanggil pemanggil dengan id kiriman, dan FOCUS_ALL untuk 'Semua'", () => {
    const dipanggil: string[] = [];
    mountFocus(null, (id) => dipanggil.push(id));
    const pil = host.querySelectorAll<HTMLButtonElement>(".route-focus-pill");
    expect(pil).toHaveLength(2);
    expect(pil[0].textContent).toContain("Semua (1)");
    act(() => pil[1].click());
    act(() => pil[0].click());
    expect(dipanggil).toEqual(["s1->l1", "__all__"]);
  });

  it("tanpa pengendali pilihan: pemilih tidak dirender (peta tetap seperti sebelumnya)", () => {
    mountWithRoutes();
    expect(host.querySelector(".route-focus")).toBeNull();
  });
});

describe("SupplyMap — kontrol peta (langkah 7b-1: skala + tombol Tampilkan semua)", () => {
  /** Tombol "Tampilkan semua" buatan aplikasi (di grup kontrol kanan-atas). */
  function tombolReset(): HTMLButtonElement {
    const button = map().controlElements.find(
      (el) => el instanceof HTMLButtonElement && el.classList.contains("map-reset-view")
    );
    if (!button) throw new Error('tombol "Tampilkan semua" tidak dipasang ke peta');
    return button as HTMLButtonElement;
  }

  it("menambah kontrol skala jarak di kiri-bawah (kontrol yang tadinya tidak ada)", () => {
    mountWithRoutes();
    // Langkah 7b-1 menaruhnya di kanan-bawah karena sudut kiri-bawah dipakai
    // panggung legenda; langkah 7b-2 memindahkan legenda ke bawah kanvas, jadi
    // skala kembali ke posisi bawaan MapLibre & acuan industri (kiri-bawah).
    const kiriBawah = map().controls.filter((c) => c.position === "bottom-left");
    expect(kiriBawah.some((c) => c.control?.constructor?.name === "ScaleControl")).toBe(true);
  });

  it('tombol "Tampilkan semua" adalah <button> asli dengan nama aksesibilitas', () => {
    mountWithRoutes();
    const button = tombolReset();
    expect(button.tagName).toBe("BUTTON");
    // Nama (aria-label) tetap; keterangan (title) yang berubah mengikuti data.
    expect(button.getAttribute("aria-label")).toBe("Tampilkan semua");
    expect(button.title).toContain("1 lokasi");
    expect(button.title).toContain("jalur kiriman");
  });

  it("klik tombol memanggil fitBounds ulang dengan batas yang SAMA seperti tampilan awal", () => {
    mountWithRoutes();
    const awal = map().fitBoundsLog[0][0];
    const sebelum = map().fitBoundsLog.length;
    act(() => tombolReset().click());
    expect(map().fitBoundsLog).toHaveLength(sebelum + 1);
    expect(map().fitBoundsLog.at(-1)?.[0]).toEqual(awal);
  });

  it("judul berhenti menyebut jalur begitu lapisan jalur dimatikan (janji ikut berubah)", () => {
    mountWithRoutes();
    expect(tombolReset().title).toContain("jalur kiriman");
    act(() => routeToggle().click());
    expect(tombolReset().title).not.toContain("jalur");
    expect(tombolReset().title).toContain("1 lokasi");
  });

  it('tanpa jalur kiriman: tombol tetap ada, judulnya tidak menyebut jalur', () => {
    mount();
    const button = tombolReset();
    expect(button.title).not.toContain("jalur");
    expect(button.getAttribute("aria-label")).toBe("Tampilkan semua");
  });
});

describe("SupplyMap — baris legenda ringkas selalu terlihat (C2, langkah 7b-2)", () => {
  /** Baris legenda ringkas di bawah kanvas. */
  function baris() {
    const el = host.querySelector<HTMLElement>(".map-legend-compact");
    if (!el) throw new Error("baris legenda ringkas tidak ada");
    return el;
  }

  it("dirender DI BAWAH kanvas, bukan mengapung di atasnya", () => {
    mountWithRoutes();
    expect(baris()).not.toBeNull();
    // Aturan pemilik 2026-10-16: kanvas tidak boleh tertutup panel putih. Karena
    // itu legenda yang selalu terlihat ini hidup di luar `.map-shell`.
    expect(host.querySelector(".map-shell")?.contains(baris())).toBe(false);
  });

  it("maknanya terbaca tanpa satu klik pun (status lokasi selalu ada)", () => {
    mountWithRoutes();
    const teks = baris().textContent ?? "";
    for (const status of ["Surplus", "Seimbang", "Shortage"]) {
      expect(teks).toContain(status);
    }
    // Bukan tombol dan tidak punya keadaan buka/tutup — memang selalu tampil.
    expect(baris().getAttribute("aria-expanded")).toBeNull();
    expect(baris().querySelector("button")).toBeNull();
  });

  it("butir jalur mengikuti sakelar lapisannya (tidak ada keterangan tanpa lapisan)", () => {
    mountWithRoutes();
    // Labelnya dari `routeLegendEntries` — legenda menyebut makna yang BENAR
    // dipakai garis di peta, bukan karangan teks di tes.
    expect(baris().textContent).toContain("Sudah ditempuh");
    expect(baris().textContent).toContain("Sisa perjalanan (perkiraan)");
    act(() => routeToggle().click());
    expect(baris().textContent).not.toContain("Sudah ditempuh");
    expect(baris().textContent).not.toContain("Sisa perjalanan (perkiraan)");
    expect(baris().textContent).toContain("Surplus");
  });

  it("butir pemasok baru muncul setelah lapisan pemasok dinyalakan", () => {
    // Butuh data pemasok: tanpa prop `suppliers` tidak ada sakelar pemasok sama
    // sekali (kendali nganggur tidak dirender).
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mounted = true;
    act(() => {
      root.render(
        <SupplyMap locations={LOCATIONS} suppliers={SUPPLIERS} supplierRoutes={ROUTES} />
      );
    });
    expect(baris().textContent).not.toContain("Keandalan rendah");
    toggle(); // sakelar "Pemasok (n)"
    expect(baris().textContent).toContain("Keandalan rendah");
  });

  it("tanda di baris memakai kelas legenda yang sama dengan kotak Info map", () => {
    mountWithRoutes();
    expect(baris().querySelectorAll(".map-legend-box-dot")).toHaveLength(3);
    expect(baris().querySelectorAll(".map-legend-line").length).toBeGreaterThan(0);
  });
});

describe("SupplyMap — satu zona kendali di kanvas (C5, langkah 7b-2)", () => {
  /** Pil kendali kiri-atas: satu-satunya elemen yang mengapung di kanvas. */
  function pil() {
    const el = host.querySelector<HTMLElement>(".map-overlay-toggles");
    if (!el) throw new Error("pil kendali peta tidak ada");
    return el;
  }

  function kotakInfo() {
    const el = host.querySelector<HTMLElement>(".map-legend-boxes");
    if (!el) throw new Error("kotak Info map tidak ada");
    return el;
  }

  it("chip Info map duduk di dalam pil yang sama dengan sakelar lapisan", () => {
    // Butuh KEDUA data lapisan supaya kedua sakelar ada (kendali nganggur tidak
    // dirender: tanpa prop `suppliers` hanya sakelar jalur yang tampil).
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mounted = true;
    act(() => {
      root.render(
        <SupplyMap locations={LOCATIONS} suppliers={SUPPLIERS} supplierRoutes={ROUTES} />
      );
    });
    expect(pil().querySelector(".map-legend-toggle")).not.toBeNull();
    // Dua sakelar lapisan tetap terbaca sebagai sakelar (bukan ikut terhitung
    // sebagai chip Info map), jadi keadaan tekan & keadaan buka tidak tertukar.
    expect(pil().querySelectorAll(".map-layer-toggle")).toHaveLength(2);
  });

  it("isi Info map dirender di luar pil dan di luar kanvas — tidak menutupi peta", () => {
    mountWithRoutes();
    expect(pil().contains(kotakInfo())).toBe(false);
    expect(host.querySelector(".map-gl")?.contains(kotakInfo())).toBe(false);
    // Ia ikut alur di dalam `.map-shell`, persis di bawah kanvas.
    expect(host.querySelector(".map-shell")?.contains(kotakInfo())).toBe(true);
  });

  it("membuka Info map tidak menambah satu pun elemen di dalam pil", () => {
    mountWithRoutes();
    const sebelum = pil().querySelectorAll("*").length;
    act(() => host.querySelector<HTMLButtonElement>(".map-legend-toggle")?.click());
    expect(pil().querySelectorAll("*").length).toBe(sebelum);
    expect(kotakInfo().parentElement?.getAttribute("data-open")).toBe("true");
  });
});

describe("SupplyMap — gestur kooperatif (C9, langkah 7b-2)", () => {
  /** Media query tiruan: satu perangkat, satu jawaban per pertanyaan. */
  function perangkat(jenis: "sentuh" | "tetikus") {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("pointer: coarse") && jenis === "sentuh",
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent: () => false,
    }));
  }

  it("perangkat sentuh utama: peta dibuat dengan gestur kooperatif", () => {
    perangkat("sentuh");
    mountWithRoutes();
    expect(map().options.cooperativeGestures).toBe(true);
  });

  it("desktop: tidak diaktifkan — roda tetikus tetap memperbesar peta", () => {
    perangkat("tetikus");
    mountWithRoutes();
    expect(map().options.cooperativeGestures).toBe(false);
  });

  it("tanpa matchMedia (jsdom/lingkungan lama): peta tetap jalan seperti desktop", () => {
    vi.stubGlobal("matchMedia", undefined);
    mountWithRoutes();
    expect(map().options.cooperativeGestures).toBe(false);
  });
});

describe("SupplyMap — chip saringan aktif di atas kanvas (C8, langkah 7b-2)", () => {
  /** Mount dengan pilihan sorotan yang dikendalikan pemanggil. */
  function mountFokus(focused: string | null, onFocus: ((id: string) => void) | null = () => {}) {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mounted = true;
    act(() => {
      root.render(
        <SupplyMap
          locations={LOCATIONS}
          supplierRoutes={ROUTES}
          focusedRouteId={focused}
          onFocusRoute={onFocus}
        />
      );
    });
  }

  function chip() {
    const el = host.querySelector<HTMLElement>(".map-filter");
    if (!el) throw new Error("chip saringan tidak ada");
    return el;
  }

  it("tanpa sorotan: tidak ada chip yang mengaku menyaring", () => {
    mountFokus(null);
    expect(host.querySelector(".map-filter")).toBeNull();
  });

  it("peta mandiri (tanpa pengendali pilihan): chip tidak dirender", () => {
    mount();
    expect(host.querySelector(".map-filter")).toBeNull();
  });

  it("satu kiriman disorot: chip menyebut nama kiriman yang sama dengan pemilih", () => {
    mountFokus("s1->l1");
    const row = focusPick(ROUTES, "s1->l1");
    expect(row).not.toBeNull();
    expect(chip().textContent).toBe(`Menyaring: ${focusLabel(row!)}Lepas`);
    expect(chip().textContent).toContain("Menyaring:");
  });

  it("chip duduk DI ATAS kanvas dan di luar kanvas itu sendiri", () => {
    mountFokus("s1->l1");
    const kanvas = host.querySelector(".map-shell")!;
    // jsdom tidak menghitung tata letak, jadi posisinya diperiksa lewat urutan DOM:
    // chip HARUS muncul sebelum wadah peta.
    expect(chip().compareDocumentPosition(kanvas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(host.querySelector(".map-gl")?.contains(chip())).toBe(false);
  });

  it('tombol "Lepas" mengirim penanda "semua kiriman", bukan id kosong', () => {
    const dipanggil: string[] = [];
    mountFokus("s1->l1", (id) => dipanggil.push(id));
    const tombol = chip().querySelector<HTMLButtonElement>(".map-filter-clear")!;
    expect(tombol.textContent).toBe(FOCUS_CLEAR_LABEL);
    act(() => tombol.click());
    expect(dipanggil).toEqual([FOCUS_ALL]);
  });
});
