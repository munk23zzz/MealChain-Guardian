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
    /** MapLibre: pindahkan layer ke akhir urutan gambar. Tiruan cukup menghapus
     *  lalu menambah ulang supaya `Object.keys(layers)` mencerminkan urutan
     *  render sesungguhnya (dipakai untuk memeriksa ekor truk di atas jalur). */
    moveLayer(id: string) {
      const layer = this.layers[id];
      if (!layer) return;
      delete this.layers[id];
      this.layers[id] = layer;
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
    getMaxZoom() {
      return 20;
    }
    /** Proyeksi sederhana: cukup untuk menghitung jarak antar-penanda di tes.
     *  Tidak perlu akurat seperti Mercator — yang diuji perilaku klaster
     *  (mengelompok atau tidak), bukan ketepatan kartografi. */
    project(posisi: [number, number] | { lng: number; lat: number }) {
      const lng = Array.isArray(posisi) ? posisi[0] : posisi.lng;
      const lat = Array.isArray(posisi) ? posisi[1] : posisi.lat;
      return { x: lng * 10, y: -lat * 10 };
    }
    unproject(titik: { x: number; y: number }) {
      return [titik.x / 10, -titik.y / 10];
    }
    easeTo() {
      return this;
    }
    /** Dipakai baris daftar "Status Lokasi" untuk terbang ke titik lokasi. */
    flyLog: { center?: [number, number]; zoom?: number }[] = [];
    flyTo(spec: { center?: [number, number]; zoom?: number }) {
      this.flyLog.push(spec);
      return this;
    }
    // MapLibre menerima bentuk `on(tipe, layerId, handler)` untuk event layer
    // (Fase 10 memakai itu untuk popup garis) — handler selalu argumen terakhir.
    on(event: string, ...args: unknown[]) {
      const handler = args[args.length - 1] as () => void;
      (this.handlers[event] ??= []).push(handler);
      // Bentuk `on(tipe, layerId, handler)`: catat per layer supaya tes bisa
      // memanggil handler lapisan tertentu (mis. garis kiriman "sudah tiba").
      if (args.length >= 2) {
        const layerId = String(args[0]);
        (this.layerHandlers[layerId] ??= []).push(handler);
      }
    }
    /** Handler `click` yang didaftarkan per layer id. */
    layerHandlers: Record<string, ((arg?: unknown) => void)[]> = {};
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
    constructor(options: { element: HTMLElement; anchor?: string }) {
      this.element = options.element;
      // Tiruan perilaku MapLibre 4.7: konstruktor MENAMBAHKAN kelas pustaka ke
      // elemen marker, dan `maplibregl-marker` itulah yang membawa
      // `position: absolute`. Kalau komponen menyegarkan pin dengan menimpa
      // `className` utuh, kelas ini ikut terhapus dan penanda jatuh ke alur
      // normal — bug "pin pemasok bergeser dari koordinatnya saat zoom"
      // (terukur sampai ±192 px di aplikasi hidup).
      this.element.classList.add(
        "maplibregl-marker",
        `maplibregl-marker-anchor-${options.anchor ?? "center"}`
      );
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
    /** Dipakai fitur klaster: posisi penanda dibaca untuk dihitung jaraknya. */
    getLngLat() {
      return this.lngLat ?? [0, 0];
    }
    togglePopup() {
      return this;
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
    on() {
      // jagaPopup memasang listener "open"/"close" pada popup sungguhan.
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

import SupplyMap, { StatusLocationList } from "../components/SupplyMap";
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
  it("zoom jauh: pin SPPG dan titik pemasok tetap digambar", () => {
    mount();
    expect(mapLog).toHaveLength(1);
    expect(locationMarkers()).toHaveLength(1);
    // Sejak 20 Okt 2026 titik pemasok TIDAK digerbang zoom: lapisan yang selalu
    // hidup tidak boleh kehilangan penandanya saat peta diperkecil.
    expect(supplierMarkers()).toHaveLength(2);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).toContain("map-pin-supplier-compact");
    });
  });

  it("zoom jauh: titik pemasok tampil tanpa nama, pengguna diberi tahu alasannya", () => {
    mount();
    expect(supplierMarkers()).toHaveLength(2);
    expect(host.querySelector(".map-layer-hint")?.textContent).toContain("muncul pada zoom 8 ke atas");
  });

  it("keterangan aksesibilitas bertahan setelah MapLibre menimpanya", () => {
    // MapLibre menulis aria-label="Map marker" saat marker dibuat; PIN SPPG
    // pernah kehilangan keterangannya karena dipasang sebelum itu.
    mount();
    expect(locationMarkers()[0]?.element.getAttribute("aria-label")).toContain(
      "permintaan 1.080 kg"
    );
    zoomTo(10);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.getAttribute("aria-label")).not.toBe("Map marker");
      expect(marker.element.getAttribute("aria-label")).toContain("keandalan");
      expect(marker.element.getAttribute("title")).toContain("keandalan");
    });
  });

  it("zoom menengah (6–8): titik tanpa nama, keterangan nama tetap tampil", () => {
    mount();
    zoomTo(6.5);
    expect(supplierMarkers()).toHaveLength(2);
    // Nama belum ditulis, jadi keterangannya MASIH tampil — kalimatnya kini
    // soal nama, bukan soal pin (pin tidak lagi digerbang zoom).
    expect(host.querySelector(".map-layer-hint")?.textContent).toContain("nama pemasok muncul");
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).toContain("map-pin-supplier-compact");
      expect(marker.element.getAttribute("aria-label")).toContain("keandalan");
    });
    // Nama tetap tersedia lewat tooltip/aria, jadi bukan informasi yang hilang.
    zoomTo(9);
    expect(host.querySelector(".map-layer-hint")).toBeNull();
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).not.toContain("map-pin-supplier-compact");
    });
  });

  it("zoom masuk (>= 8): pin muncul, hint hilang", () => {
    mount();
    zoomTo(9);
    expect(supplierMarkers()).toHaveLength(2);
    expect(host.querySelector(".map-layer-hint")).toBeNull();
    // Posisi pin = koordinat pemasok, bukan koordinat SPPG.
    const telur = supplierMarkers().find((marker) =>
      marker.element.getAttribute("aria-label")?.includes("Telur Berkah Cianjur")
    );
    expect(telur?.lngLat).toEqual([107.1636, -6.811]);
  });

  it("zoom dijauhkan lagi: nama hilang, titik tetap (tidak ada penanda menggantung)", () => {
    mount();
    zoomTo(9);
    expect(supplierMarkers()).toHaveLength(2);
    zoomTo(5);
    expect(supplierMarkers()).toHaveLength(2);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).toContain("map-pin-supplier-compact");
    });
    // Pin SPPG tidak ikut terpengaruh.
    expect(locationMarkers()).toHaveLength(1);
  });

  it("kelas MapLibre tidak terhapus saat pin pemasok disegarkan (pin tetap di koordinatnya)", () => {
    // Regresi 2026-10-18: `refreshSupplierPin` menimpa className utuh, sehingga
    // kelas `maplibregl-marker` (pembawa position:absolute) hilang pada zoomend
    // pertama. Pin lalu ikut alur tata letak penanda lain dan bergeser sampai
    // ±192 px dari koordinat aslinya saat zoom in/out.
    mount();
    zoomTo(6.5);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).toContain("maplibregl-marker");
    });
    // Zoom berikutnya memicu `refreshSupplierPin` untuk pin yang sudah ada.
    zoomTo(9);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).toContain("maplibregl-marker");
      expect(marker.element.className).toContain("maplibregl-marker-anchor-center");
      // Nada & keadaan label tetap diperbarui oleh penyegaran itu.
      expect(marker.element.className).toContain("map-pin-supplier");
    });
    zoomTo(7);
    supplierMarkers().forEach((marker) => {
      expect(marker.element.className).toContain("maplibregl-marker");
      expect(marker.element.className).toContain("map-pin-supplier-compact");
    });
  });

  it("pin SPPG juga mempertahankan kelas MapLibre saat data disinkronkan ulang", () => {
    mount();
    const awal = locationMarkers()[0].element;
    expect(awal.className).toContain("maplibregl-marker");
    act(() => {
      root.render(
        <SupplyMap locations={[{ ...LOCATIONS[0], supply_kg: 310 }]} suppliers={SUPPLIERS} />
      );
    });
    const sesudah = locationMarkers().find((marker) => !marker.removed)?.element;
    expect(sesudah?.className).toContain("maplibregl-marker");
    // Anchor pin lokasi tetap di ujung ekor (bukan tengah), jadi tidak berubah.
    expect(sesudah?.className).toContain("maplibregl-marker-anchor-bottom");
  });

  it("zoom dekat: pin pemasok langsung muncul tanpa perlu dinyalakan", () => {
    mount();
    zoomTo(10);
    expect(supplierMarkers()).toHaveLength(2);
  });

  it("kelas & popup pin memakai makna dari data (bukan enum internal)", () => {
    mount();
    zoomTo(10);
    const telur = supplierMarkers().find((marker) =>
      marker.element.getAttribute("aria-label")?.includes("Telur Berkah Cianjur")
    )!;
    expect(telur.element.className).toContain("map-pin-supplier-excluded");
    expect(telur.element.getAttribute("aria-label")).toBe(
      "Telur Berkah Cianjur — pemasok telur, keandalan 38%, hub Cianjur (dikecualikan di Cianjur, Jakarta)"
    );
    const popupText = telur.popup?.node?.textContent ?? "";
    // Popup 21 Okt 2026 memakai kartu berstruktur (kicker/judul/metrik),
    // jadi teksnya dibaca per makna — bukan lagi satu kalimat "Label: nilai".
    expect(popupText).toContain("telur");
    expect(popupText).toContain("38%");
    expect(popupText).toContain("Tidak bersertifikat");
    expect(popupText).toContain("Dikecualikan di: Cianjur, Jakarta");
    expect(popupText).not.toContain("none");

    const wortel = supplierMarkers().find((marker) =>
      marker.element.getAttribute("aria-label")?.includes("Wortel Lestari Cianjur")
    )!;
    expect(wortel.element.className).toContain("map-pin-supplier-ok");
    expect(wortel.popup?.node?.textContent).toContain("HACCP");
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
    expect(done.filter).toEqual(["all", ["==", ["get", "kind"], "done"], ["!=", ["get", "quiet"], true]]);
    expect(todo.filter).toEqual(["all", ["==", ["get", "kind"], "todo"], ["!=", ["get", "quiet"], true]]);
    const cat = (layer: { paint?: unknown }) => (layer.paint ?? {}) as Record<string, unknown>;
    expect(cat(done)["line-dasharray"]).toBeUndefined();
    expect(cat(todo)["line-dasharray"]).toEqual([4, 3]);
    // Audit 21 Okt 2026: jalur "sudah tiba" nyaris tak terlihat (abu 2,5px
    // @0,32). Sekarang ia memakai nada status + alas putih, dan tebalnya
    // minimal 3px dengan opasitas >= 0,4 supaya terbaca di basemap terang.
    const tiba = peta.layers["supplier-route-line-tiba"];
    const tibaAlas = peta.layers["supplier-route-line-tiba-casing"];
    expect(tiba).toBeDefined();
    expect(tibaAlas).toBeDefined();
    expect(tiba.filter).toEqual(["==", ["get", "quiet"], true]);
    expect(cat(tiba)["line-width"] as number).toBeGreaterThanOrEqual(3.6);
    expect(cat(tiba)["line-opacity"] as number).toBeGreaterThanOrEqual(0.7);
    expect(cat(tiba)[`line-color`]).toBe("#475569");
    expect(cat(tibaAlas)[`line-color`]).toBe("#FFFFFF");

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
    // Sejak audit 21 Okt 2026 kiriman berjalan memakai violet --status-live,
    // dan sisa perjalanan memakai violet lebih terang (--route-live-soft):
    // satu kiriman tetap satu keluarga warna, tetapi dua bagian tetap beda nada.
    expect(done[4]).toBe("#7C3AED");
    expect(todo[3]).toBe("#C62828");
    expect(todo[4]).toBe("#8B5CF6");
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
    zoomTo(9);
    const pemasok = supplierMarkers()[0];
    expect(pemasok.element.querySelector("svg.map-pin-icon-supplier")).not.toBeNull();
    // Ikon hiasan: maknanya sudah ada di aria-label penanda.
    pemasok.element
      .querySelectorAll("svg.map-pin-icon")
      .forEach((ikon) => expect(ikon.getAttribute("aria-hidden")).toBe("true"));
  });

  it("kiriman yang sudah tiba tidak digambar dan tidak punya ikon mobil", () => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mounted = true;
    act(() => {
      root.render(
        <SupplyMap
          locations={LOCATIONS}
          supplierRoutes={{
            routes: [
              {
                ...ROUTES.routes[0],
                journey: { ...ROUTES.routes[0].journey, state: "tiba", state_label: "Tiba" },
              },
            ],
          }}
        />
      );
    });
    // Sejak 20 Okt 2026 lapisan dasar hanya menggambar kiriman yang BERJALAN.
    expect(map().sources["supplier-routes"]).toBeUndefined();
    expect(map().layers["supplier-route-line-done"]).toBeUndefined();
    expect(markerLog.filter((m) => m.element.classList.contains("map-truck"))).toHaveLength(0);
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
    expect(casingTodo.filter).toEqual(["all", ["==", ["get", "kind"], "todo"], ["!=", ["get", "quiet"], true]]);
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

  it("kiriman yang sedang berjalan diberi halo tenang, bukan neon berdenyut", async () => {
    mountWithRoutes();
    // Redesign 20 Okt 2026: penekanan garis tidak lagi neon + denyut + titik
    // mengalir. Satu elemen bergerak (ikon mobil, karena posisinya data), dan
    // garis hanya diberi halo sewarna yang tenang.
    const haloDone = map().layers["supplier-route-halo-done"] as Record<string, unknown>;
    const haloTodo = map().layers["supplier-route-halo-todo"] as Record<string, unknown>;
    expect(haloDone).toBeDefined();
    expect(haloTodo).toBeDefined();
    for (const [halo, kind] of [
      [haloDone, "done"],
      [haloTodo, "todo"],
    ] as const) {
      expect(JSON.stringify(halo.filter)).toContain('"state"');
      expect(JSON.stringify(halo.filter)).toContain("di_jalan");
      expect(JSON.stringify(halo.filter)).toContain(kind);
      const paint = halo.paint as Record<string, unknown>;
      expect(Number(paint["line-blur"])).toBeGreaterThan(0);
      // Tenang: opasitas rendah (<= 0,30), dan warnanya nada garis (bukan
      // warna kelima). Batas ini menjaga "halo", bukan "neon" — 20 Okt 2026
      // dinaikkan dari 0,22 ke 0,26 supaya peta lebih hidup, masih jauh dari
      // efek menyala.
      expect(Number(paint["line-opacity"])).toBeLessThanOrEqual(0.3);
      expect(Array.isArray(paint["line-color"])).toBe(true);
    }
    // Halo di bawah alas putih supaya tidak menutupi pin maupun garis.
    const ids = Object.keys(map().layers);
    expect(ids.indexOf("supplier-route-halo-done")).toBeLessThan(
      ids.indexOf("supplier-route-casing-done")
    );
    // Tidak ada denyut: opasitas halo tidak berubah selama seperempat detik.
    const log = (map() as unknown as { paintLog: Array<[string, string, unknown]> }).paintLog;
    const jumlahAwal = log.length;
    await new Promise((r) => setTimeout(r, 250));
    const perubahan = log
      .slice(jumlahAwal)
      .filter(([id, prop]) => id.startsWith("supplier-route-halo") && prop === "line-opacity");
    expect(perubahan).toHaveLength(0);
  });

  it("ikon mobil menandai posisi kiriman berjalan dan menghadap arah perjalanan", () => {
    mountWithRoutes();
    const truk = markerLog.filter((m) => m.element.classList.contains("map-truck"));
    expect(truk.length).toBe(1);
    const el = truk[0].element;
    // Nama aksesibel menyebut kiriman + persentase perjalanan (bukan "Map marker").
    expect(el.getAttribute("aria-label")).toContain("Mobil kiriman");
    expect(el.getAttribute("aria-label")).toMatch(/\d+% perjalanan/);
    // Menghadap arah: sudut disimpan sebagai variabel CSS untuk rotasi glyph.
    expect(el.style.getPropertyValue("--truk-arah")).toMatch(/^-?\d+deg$/);
    // Popup truk 21 Okt 2026: kartu yang sama dengan SPPG/pemasok, dengan
    // progres perjalanan sebagai angka utama.
    const popupText = truk[0].popup?.node?.textContent ?? "";
    expect(popupText).toContain("Perjalanan");
    expect(popupText).toContain("Muatan");
    expect(popupText).toContain("Sisa");
    // Posisinya mengikuti `journey.progress` pada geometri jalan, bukan di ujung
    // pemasok: 71,2% dari Cianjur ke Jakarta.
    const koordinat = ROUTES.routes[0].road.geometry.coordinates as [number, number][];
    const awalJalur = koordinat[0];
    const akhirJalur = koordinat[koordinat.length - 1];
    // `markerLog` diketik sebagai tiruan minimal; posisi dibaca dari `lngLat`.
    const posisiTruk = (truk[0] as unknown as { lngLat: [number, number] | null }).lngLat;
    expect(posisiTruk).not.toBeNull();
    const [lng, lat] = posisiTruk as [number, number];
    const harapan = [
      awalJalur[0] + (akhirJalur[0] - awalJalur[0]) * 0.712,
      awalJalur[1] + (akhirJalur[1] - awalJalur[1]) * 0.712,
    ] as const;
    expect(lng).toBeCloseTo(harapan[0], 3);
    expect(lat).toBeCloseTo(harapan[1], 3);
  });

  it("legenda jalur menyebut asal OSRM dan jumlahnya", () => {
    mountWithRoutes();
    // "Jalur kiriman:" sebagai JUDUL kotak sudah tidak ada (Info map dilebur);
    // maknanya dibawa baris legenda ringkas + tag jumlah di bilah rincian.
    expect(host.querySelector(".map-legend-compact")?.textContent).toContain("Sudah ditempuh");
    expect(host.textContent).toContain("Sisa perjalanan (perkiraan)");
    expect(host.textContent).toContain("1 jalur kiriman");
    expect(host.textContent).toContain("OSRM");
  });

  it("membongkar peta: peta dilepas tanpa error (penanda dibersihkan bersama peta)", () => {
    mount();
    zoomTo(10);
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
    // Sejak 20 Okt 2026 tag menghitung KIRIMAN YANG BERJALAN (peta hanya
    // menggambar jalur `di_jalan`), bukan semua baris yang dilaporkan server.
    expect(host.querySelector(".map-layer-tags")?.textContent).toContain("kiriman berjalan");
    // Tombol lapisan sudah dihapus (20 Okt 2026): tidak ada elemen yang
    // mengapung di kanvas, dan bilah rincian tetap DI BAWAH peta.
    expect(host.querySelector(".map-overlay-toggles")).toBeNull();
    expect(host.querySelector(".map-layer-toggle")).toBeNull();
  });

  it("tanpa kedua lapisan: bilah rincian tidak dirender sama sekali", () => {
    mountEl(<SupplyMap locations={LOCATIONS} />);
    expect(host.querySelector(".map-layer-info")).toBeNull();
    expect(host.querySelector(".map-layer-info-toggle")).toBeNull();
  });
});

describe("SupplyMap — rincian lapisan & perjalanan kiriman", () => {
  /**
   * 19 Okt 2026: panel "Info map" dilebur ke "Rincian lapisan peta".
   *
   * Sebabnya bukan ruang, tapi kebenaran: isi panel itu (status lokasi, jalur,
   * pemasok) memang SAMA dengan baris legenda di bawah kanvas — satu fakta
   * dibaca dua tempat, yang kedua lewat klik tambahan. Yang tidak duplikat,
   * daftar perjalanan kiriman, pindah ke panel rincian. Tes di bawah menjaga
   * dua hal: legenda tetap terbaca tanpa klik, dan perjalanan tetap ada.
   */
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

  function infoPanel() {
    const panel = host.querySelector<HTMLElement>("#map-layer-info-panel");
    if (!panel) throw new Error("panel rincian lapisan tidak ada");
    return panel;
  }

  it("tidak ada lagi tombol 'Info map'; legenda terbaca tanpa klik", () => {
    mountWithRoutes();
    expect(host.textContent).not.toContain("Info map");
    expect(host.querySelector(".map-legend-toggle")).toBeNull();
    expect(host.querySelector(".map-legend-boxes")).toBeNull();
    const legenda = host.querySelector(".map-legend-compact")?.textContent ?? "";
    // Status lokasi selalu ada; jalur ikut karena lapisannya hidup secara bawaan.
    expect(legenda).toContain("Surplus");
    expect(legenda).toContain("Sudah ditempuh");
    expect(legenda).toContain("Sisa perjalanan (perkiraan)");
  });

  it("perjalanan kiriman pindah ke panel rincian, bukan hilang", () => {
    mountWithRoutes();
    const perjalanan = infoPanel().querySelector('[aria-label="Perjalanan kiriman"]');
    expect(perjalanan).not.toBeNull();
    expect(perjalanan?.textContent).toContain("Perjalanan kiriman:");
    expect(perjalanan?.textContent).toContain("Jakarta · di jalan · tiba ± 22.54");
    expect(perjalanan?.textContent).toContain("24 menit lagi");
    // Tanpa membuka panel: tag bilah rincian sudah menyebut estimasi tiba.
    expect(host.querySelector(".map-layer-tags")?.textContent).toContain("tiba terdekat ± 22.54");
  });

  it("keterangan pemasok selalu ada selama data pemasok dikirim", () => {
    mountEl(<SupplyMap locations={LOCATIONS} suppliers={SUPPLIERS} supplierRoutes={ROUTES} />);
    const legenda = () => host.querySelector(".map-legend-compact")?.textContent ?? "";
    // Tidak ada sakelar lagi: kalau datanya ada, warnanya diterangkan.
    expect(legenda()).toContain("Keandalan rendah");
  });

  it("entri 'gagal uji' hanya muncul kalau ada kiriman bergaris gagal", () => {
    mountWithRoutes();
    const legenda = () => host.querySelector(".map-legend-compact")?.textContent ?? "";
    expect(legenda()).toContain("Sudah ditempuh");
    expect(legenda()).not.toContain("gagal uji");

    unmount();
    mountEl(<SupplyMap locations={LOCATIONS} supplierRoutes={ROUTES_GAGAL} />);
    expect(legenda()).toContain("Jalur kiriman gagal uji");
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
    const perjalanan = infoPanel().querySelector('[aria-label="Perjalanan kiriman"]');
    expect(perjalanan?.textContent).toContain("belum berangkat · estimasi tiba belum ada");
    expect(perjalanan?.textContent).not.toContain("tiba ±");
    // Tag lapisan pun tidak mengarang jam: tidak ada kiriman berjalan, jadi
    // tag menyatakan itu apa adanya (bukan "1 jalur kiriman" yang tidak tergambar).
    expect(host.querySelector(".map-layer-tags")?.textContent).toContain("tidak ada kiriman berjalan");
  });

  it("butir 'Sedang mengirim' di legenda hanya bila ada pin yang memakainya", () => {
    // Legenda tidak boleh menyebut warna yang tidak tergambar di kanvas.
    const semuaTiba = {
      routes: [
        {
          ...ROUTES.routes[0],
          journey: {
            ...ROUTES.routes[0].journey,
            state: "sudah_tiba",
            state_label: "Sudah tiba",
            progress: 1,
          },
        },
      ],
    };
    mountEl(<SupplyMap locations={LOCATIONS} supplierRoutes={semuaTiba} />);
    expect(host.querySelector(".map-legend-compact")?.textContent).not.toContain("Sedang mengirim");

    mountEl(<SupplyMap locations={LOCATIONS} supplierRoutes={ROUTES} />);
    expect(host.querySelector(".map-legend-compact")?.textContent).toContain("Sedang mengirim");
  });

  it("garis kiriman yang SUDAH TIBA pun bisa diklik: popup + sorotan", () => {
    // Kiriman yang sudah tiba punya layer sendiri (ROUTE_QUIET_LAYER_ID). Layer
    // itu dulu tidak didaftarkan ke handler klik, jadi garis yang paling banyak
    // terlihat sore hari justru satu-satunya yang mati saat diklik (audit 22 Okt).
    const tiba = {
      routes: [
        {
          ...ROUTES.routes[0],
          journey: {
            ...ROUTES.routes[0].journey,
            state: "sudah_tiba",
            state_label: "Sudah tiba",
            progress: 1,
          },
        },
      ],
    };
    const onFocus = vi.fn();
    mountEl(<SupplyMap locations={LOCATIONS} supplierRoutes={tiba} onFocusRoute={onFocus} />);
    const map = mapLog[mapLog.length - 1] as any;
    const handler = map.layerHandlers["supplier-route-line-tiba"]?.[0];
    expect(handler, "layer garis 'sudah tiba' harus punya handler klik").toBeTypeOf("function");
    const fitur = (map.sources["supplier-routes"].data as any).features[0];
    act(() => {
      handler({
        features: [{ properties: fitur.properties }],
        lngLat: { lng: 106.9, lat: -6.2 },
      });
    });
    const popup = popupLog[popupLog.length - 1];
    expect(popup?.node?.textContent).toContain("Jalur jalan (OSRM)");
    expect(onFocus).toHaveBeenCalled();
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
    expect(teks).toContain("tiba ± 22.54 WIB");
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
    const pil = host.querySelectorAll<HTMLButtonElement>("button.route-focus-pill");
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

  it("bilah skala TIDAK dipasang — kiri-bawah dipakai pil sakelar lapisan", () => {
    mountWithRoutes();
    // Keputusan pemilik 19 Okt 2026: "info km di kiri-bawah hapus saja".
    // Konsekuensi yang disengaja: jarak tidak bisa diukur langsung dari peta;
    // angka km tetap di popup jalur dan kartu kiriman.
    const semua = map().controls.map((c) => c.control?.constructor?.name);
    expect(semua).not.toContain("ScaleControl");
    // Kiri-bawah tidak lagi ditempati kontrol apa pun — sudut itu milik pil.
    expect(map().controls.filter((c) => c.position === "bottom-left")).toHaveLength(0);
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

  it("butir jalur selalu diterangkan selama data jalur ada", () => {
    mountWithRoutes();
    // Labelnya dari `routeLegendEntries` — legenda menyebut makna yang BENAR
    // dipakai garis di peta, bukan karangan teks di tes.
    expect(baris().textContent).toContain("Sudah ditempuh");
    expect(baris().textContent).toContain("Sisa perjalanan (perkiraan)");
    expect(baris().textContent).toContain("Surplus");
  });

  it("butir pemasok muncul begitu data pemasok ada", () => {
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
    expect(baris().textContent).toContain("Keandalan rendah");
  });

  it("tanda di baris memakai kelas legenda yang sama dengan kotak Info map", () => {
    mountWithRoutes();
    expect(baris().querySelectorAll(".map-legend-box-dot")).toHaveLength(3);
    expect(baris().querySelectorAll(".map-legend-line").length).toBeGreaterThan(0);
  });
});

describe("SupplyMap — satu zona kendali di kanvas (C5, langkah 7b-2)", () => {
  /**
   * 19 Okt 2026: chip "Info map" DIHAPUS. Pil kendali kini hanya dua tombol
   * ikon; legenda hidup di baris bawah kanvas (terbaca tanpa klik) dan
   * rincian panjang di panel "Rincian lapisan peta". Tes ini menjaga aturan
   * pemilik 2026-10-16 yang tidak berubah: kanvas hanya punya SATU elemen
   * mengapung, dan tidak ada keterangan panjang yang menutupi pin.
   */
  function pil() {
    const el = host.querySelector<HTMLElement>(".map-overlay-toggles");
    if (!el) throw new Error("pil kendali peta tidak ada");
    return el;
  }

  function renderKeduaLapisan() {
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
  }

  it("pil lapisan tidak dirender lagi (tombol dihapus 20 Okt 2026)", () => {
    renderKeduaLapisan();
    expect(host.querySelector(".map-overlay-toggles")).toBeNull();
    expect(host.querySelector(".map-layer-toggle")).toBeNull();
    expect(host.querySelector(".map-legend-toggle")).toBeNull();
  });

  it("legenda & rincian dirender DI LUAR kanvas", () => {
    renderKeduaLapisan();
    const legenda = host.querySelector<HTMLElement>(".map-legend-compact");
    const rincian = host.querySelector<HTMLElement>(".map-layer-info");
    for (const el of [legenda, rincian]) {
      expect(el).not.toBeNull();
      expect(host.querySelector(".map-gl")?.contains(el as Node)).toBe(false);
      // Ikut alur di dalam `.map-body`, persis DI BAWAH kanvas — bukan overlay.
      expect(host.querySelector(".map-body")?.contains(el as Node)).toBe(true);
    }
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

describe("SupplyMap — penanda bertumpuk jadi gelembung klaster", () => {
  // Dua lokasi berdekatan: pada proyeksi tiruan (10 px per derajat) jaraknya
  // 9,4 px — jauh di bawah ambang klaster 34 px, persis seperti kondisi nyata
  // yang dilaporkan audit (pin berjarak 5–9 px dan target-nya saling menutup).
  const DEKAT = [
    LOCATIONS[0],
    { ...LOCATIONS[0], location: "Bekasi", longitude: 106.94, latitude: -6.2388 },
  ];

  it("menggambar satu gelembung berisi jumlah lokasi, bukan dua pin bertumpuk", () => {
    mount();
    act(() => root.render(<SupplyMap locations={DEKAT} />));
    const gelembung = markerLog.filter((m) => m.element.className.includes("map-cluster"));
    expect(gelembung).toHaveLength(1);
    expect(gelembung[0].element.textContent).toBe("2");
    expect(gelembung[0].element.tagName).toBe("BUTTON");
    // Nama aksesibel menyebut lokasinya, bukan sekadar angka.
    const label = gelembung[0].element.getAttribute("aria-label") ?? "";
    expect(label).toContain("2 lokasi berdekatan");
    expect(label).toContain("Jakarta");
  });

  it("menyembunyikan pin anggota dari tampilan DAN dari urutan Tab", () => {
    mount();
    act(() => root.render(<SupplyMap locations={DEKAT} />));
    const pin = locationMarkers();
    expect(pin).toHaveLength(2);
    pin.forEach((marker) => {
      expect(marker.element.style.visibility).toBe("hidden");
      expect(marker.element.getAttribute("aria-hidden")).toBe("true");
      expect(marker.element.getAttribute("tabindex")).toBe("-1");
    });
  });

  it("lokasi yang berjauhan tetap jadi pin sendiri (tidak diklaster)", () => {
    const jauh = [LOCATIONS[0], { ...LOCATIONS[0], location: "Surabaya", longitude: 112.75, latitude: -7.25 }];
    mount();
    act(() => root.render(<SupplyMap locations={jauh} />));
    expect(markerLog.filter((m) => m.element.className.includes("map-cluster"))).toHaveLength(0);
    expect(locationMarkers().every((marker) => marker.element.style.visibility !== "hidden")).toBe(true);
  });
});

describe("SupplyMap — daftar Status Lokasi menyorot penanda", () => {
  it("baris daftar adalah tombol yang terbang ke koordinat lokasi", () => {
    mount();
    const tombol = host.querySelector<HTMLButtonElement>(".map-row-btn")!;
    expect(tombol).not.toBeNull();
    expect(tombol.tagName).toBe("BUTTON");
    expect(tombol.textContent).toContain("JKT");
    act(() => tombol.click());
    const fly = mapLog[0].flyLog as { center?: [number, number]; zoom?: number }[];
    expect(fly).toHaveLength(1);
    expect(fly[0].center).toEqual([LOCATIONS[0].longitude, LOCATIONS[0].latitude]);
    // Zoom minimal 9 supaya penanda yang tadinya berklaster terpisah.
    expect(fly[0].zoom).toBeGreaterThanOrEqual(9);
  });

  it("penanda lokasi yang dipilih diberi cincin aktif, yang lain dilepas", () => {
    const dua = [LOCATIONS[0], { ...LOCATIONS[0], location: "Surabaya", longitude: 112.75, latitude: -7.25 }];
    mount();
    act(() => root.render(<SupplyMap locations={dua} />));
    const surabaya = Array.from(host.querySelectorAll<HTMLButtonElement>(".map-row-btn")).find((b) =>
      (b.textContent ?? "").includes("SBY")
    )!;
    act(() => surabaya.click());
    const aktif = locationMarkers().filter((m) => m.element.classList.contains("map-pin-active"));
    expect(aktif).toHaveLength(1);
    // Label penanda mengikuti teks yang DILIHAT operator (kode wilayah), bukan
    // nama panjang: satu sumber label, tidak ada dua penamaan untuk satu pin.
    expect(aktif[0].element.getAttribute("aria-label")).toContain("SBY");
  });

  it("tanpa peta (pemanggil tanpa onSorot) baris tetap statis, bukan tombol mati", () => {
    const wadah = document.createElement("div");
    document.body.append(wadah);
    const akar = createRoot(wadah);
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    act(() => {
      akar.render(<StatusLocationList locations={LOCATIONS} />);
    });
    expect(wadah.querySelector(".map-row-btn")).not.toBeNull();
    expect(wadah.querySelector("button.map-row-btn")).toBeNull();
    act(() => akar.unmount());
    wadah.remove();
  });
});
