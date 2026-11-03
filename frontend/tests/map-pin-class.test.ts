/**
 * Regresi bug "pin bergeser saat zoom" (2026-10-18).
 *
 * MapLibre menaruh `position: absolute` pada elemen marker lewat kelas
 * `maplibregl-marker`. Menyegarkan pin dengan `el.className = ...` menghapus
 * kelas itu, penanda jatuh ke alur normal, dan posisinya bergeser mengikuti
 * tata letak penanda lain — bukan koordinatnya.
 */
import { describe, expect, it } from "vitest";
import { AWALAN_KELAS_PIN, gabungKelasPin } from "../lib/map-pin-class";

describe("gabungKelasPin", () => {
  it("mempertahankan kelas milik MapLibre", () => {
    const hasil = gabungKelasPin(
      "map-pin map-pin-supplier map-pin-supplier-ok maplibregl-marker maplibregl-marker-anchor-center",
      "map-pin map-pin-supplier map-pin-supplier-low"
    );
    expect(hasil).toContain("maplibregl-marker");
    expect(hasil).toContain("maplibregl-marker-anchor-center");
  });

  it("mengganti kelas nada lama, tidak menumpuknya", () => {
    const hasil = gabungKelasPin(
      "map-pin map-pin-supplier map-pin-supplier-ok",
      "map-pin map-pin-supplier map-pin-supplier-low"
    );
    expect(hasil).not.toContain("map-pin-supplier-ok");
    expect(hasil).toContain("map-pin-supplier-low");
  });

  it("membuang kelas pin yang sudah tidak berlaku (mis. nama disembunyikan)", () => {
    const hasil = gabungKelasPin(
      "map-pin map-pin-supplier map-pin-supplier-compact",
      "map-pin map-pin-supplier"
    );
    expect(hasil).not.toContain("map-pin-supplier-compact");
  });

  it("menjaga urutan: kelas pustaka dulu, kelas pin sesudahnya", () => {
    const hasil = gabungKelasPin("map-pin maplibregl-marker", "map-pin map-pin-shortage");
    expect(hasil.split(" ")).toEqual(["maplibregl-marker", "map-pin", "map-pin-shortage"]);
  });

  it("tidak menggandakan kelas yang sama", () => {
    const hasil = gabungKelasPin(
      "map-pin map-pin-active maplibregl-marker",
      "map-pin map-pin-active"
    );
    expect(hasil.split(" ").filter((kelas) => kelas === "map-pin-active")).toHaveLength(1);
  });

  it("elemen baru (tanpa kelas) mendapat kelas pin apa adanya", () => {
    expect(gabungKelasPin("", "map-pin map-pin-surplus")).toBe("map-pin map-pin-surplus");
  });

  it("kelas asing yang kebetulan memuat 'map-pin' di tengah tetap dipertahankan", () => {
    const hasil = gabungKelasPin("bukan-map-pin maplibregl-marker", "map-pin");
    expect(hasil).toContain("bukan-map-pin");
  });

  it("awalannya memang 'map-pin' (kontrak dengan CSS & tes lain)", () => {
    expect(AWALAN_KELAS_PIN).toBe("map-pin");
  });
});
