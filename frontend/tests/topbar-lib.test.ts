// Top bar (acuan mockup Stitch: header global 64px) — logika murni diuji
// tanpa DOM: model dropdown cakupan, hitungan notifikasi, inisial, dan
// ringkasan jaringan. Aturan cakupan: HANYA monitor nasional yang boleh
// memilih lokasi; peran SPPG terikat SPPG-nya (fail-closed).
import { describe, expect, it } from "vitest";

import {
  ALL_LOCATIONS,
  countActionable,
  defaultScope,
  initialsOf,
  isScopeChooser,
  networkState,
  scopeModel,
  type TopBarLocation,
} from "../lib/topbar";

const LOCATIONS: TopBarLocation[] = [
  { location: "Bandung", region: "Jawa Barat", status: "surplus" },
  { location: "Bogor", region: "Jawa Barat", status: "surplus" },
  { location: "Jakarta", region: "DKI Jakarta", status: "shortage" },
];

describe("top bar — cakupan lokasi", () => {
  it("hanya monitor nasional yang boleh memilih lokasi", () => {
    expect(isScopeChooser("bgn_monitor")).toBe(true);
    expect(isScopeChooser("sppg_head")).toBe(false);
    expect(isScopeChooser("sppg_nutritionist")).toBe(false);
    expect(isScopeChooser(null)).toBe(false);
    expect(isScopeChooser(undefined)).toBe(false);
  });

  it("monitor melihat semua lokasi + opsi per lokasi (aktif)", () => {
    const model = scopeModel({ role: "bgn_monitor", locations: LOCATIONS });
    expect(model.disabled).toBe(false);
    expect(model.options[0]).toEqual({
      value: ALL_LOCATIONS,
      label: "Semua lokasi SPPG (3 lokasi)",
    });
    expect(model.options.map((o) => o.value)).toEqual([
      ALL_LOCATIONS,
      "Bandung",
      "Bogor",
      "Jakarta",
    ]);
  });

  it("peran SPPG terkunci pada SPPG-nya — cakupan tidak bisa diperluas", () => {
    const model = scopeModel({
      role: "sppg_head",
      locations: LOCATIONS,
      ownLocation: "Jakarta",
    });
    expect(model.disabled).toBe(true);
    expect(model.options).toHaveLength(1);
    expect(model.options[0]).toEqual({ value: "Jakarta", label: "Jakarta" });
  });

  it("gagal-tertutup: lokasi SPPG tak diketahui → tidak ada opsi, tidak bisa diganti", () => {
    const model = scopeModel({ role: "sppg_nutritionist", locations: LOCATIONS });
    expect(model.disabled).toBe(true);
    expect(model.options).toEqual([]);
    expect(model.placeholder).toBe("Lokasi belum diketahui");
  });

  it("peran tak dikenal juga gagal-tertutup", () => {
    const model = scopeModel({ role: null, locations: LOCATIONS });
    expect(model.disabled).toBe(true);
    expect(model.options).toEqual([]);
    expect(model.placeholder).toBe("Cakupan tidak diketahui");
  });

  it("cakupan awal: monitor = semua lokasi, SPPG = lokasinya sendiri", () => {
    expect(defaultScope({ role: "bgn_monitor" })).toBe(ALL_LOCATIONS);
    expect(defaultScope({ role: "sppg_head", ownLocation: "Jakarta" })).toBe("Jakarta");
    // Tanpa lokasi (data belum tiba) jangan menebak cakupan baru.
    expect(defaultScope({ role: "sppg_head" })).toBe(ALL_LOCATIONS);
    expect(defaultScope({ role: null })).toBe(ALL_LOCATIONS);
  });
});

describe("top bar — notifikasi tindakan", () => {
  it("menghitung status yang menunggu tindakan manusia, mengabaikan sisanya", () => {
    expect(
      countActionable([
        { status: "pending_approval" },
        { status: "VERIFIER_FLAGGED" },
        { status: "needs_verification" },
        { status: "executed" },
        { status: "rejected" },
        {},
      ]),
    ).toBe(3);
    expect(countActionable([])).toBe(0);
  });
});

describe("top bar — identitas & ringkasan jaringan", () => {
  it("inisial dari email atau label peran, maksimal dua huruf", () => {
    expect(initialsOf("sppg.head@demo.local")).toBe("SH");
    expect(initialsOf("SPPG Operations Lead")).toBe("SO");
    expect(initialsOf("bgn.monitor@demo.local", "National Inspector")).toBe("BM");
    expect(initialsOf("", null, undefined)).toBe("");
  });

  it("ringkasan jaringan menandai shortage (dan jujur saat normal)", () => {
    expect(networkState(LOCATIONS)).toEqual({
      tone: "warning",
      label: "1 lokasi shortage (3 terpantau)",
    });
    expect(networkState([{ location: "Bogor", status: "surplus" }])).toEqual({
      tone: "safe",
      label: "Jaringan normal (1 lokasi)",
    });
    expect(networkState([])).toEqual({ tone: "safe", label: "Jaringan normal (0 lokasi)" });
  });
});
