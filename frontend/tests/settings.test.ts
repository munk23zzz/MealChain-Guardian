import { describe, expect, it } from "vitest";

import {
  canManageSettings,
  draftUserUpdate,
  roleLabel,
} from "../lib/settings";

describe("canManageSettings", () => {
  it("hanya monitor yang boleh mengelola", () => {
    expect(canManageSettings("bgn_monitor")).toBe(true);
    expect(canManageSettings("sppg_head")).toBe(false);
    expect(canManageSettings("sppg_nutritionist")).toBe(false);
  });

  it("peran kosong/null ditolak (fail-closed)", () => {
    expect(canManageSettings(null)).toBe(false);
    expect(canManageSettings(undefined)).toBe(false);
    expect(canManageSettings("")).toBe(false);
  });
});

describe("roleLabel", () => {
  it("menerjemahkan peran yang dikenal", () => {
    expect(roleLabel("sppg_head")).toBe("Kepala SPPG");
    expect(roleLabel("bgn_monitor")).toBe("Monitor BGN");
  });

  it("peran tak dikenal ditampilkan apa adanya (jangan menebak)", () => {
    expect(roleLabel("peran-baru")).toBe("peran-baru");
  });
});

describe("draftUserUpdate", () => {
  const user = { role: "sppg_head", locationId: "loc-1" };

  it("tanpa perubahan → payload kosong", () => {
    expect(draftUserUpdate(user, "sppg_head", "loc-1")).toEqual({});
  });

  it("pindah lokasi → hanya location_id", () => {
    expect(draftUserUpdate(user, "sppg_head", "loc-2")).toEqual({
      location_id: "loc-2",
    });
  });

  it("naik jadi monitor → hanya role (lokasi tidak dikirim)", () => {
    expect(draftUserUpdate(user, "bgn_monitor", "loc-1")).toEqual({
      role: "bgn_monitor",
    });
  });

  it("monitor turun jadi peran SPPG → role + lokasi baru", () => {
    expect(
      draftUserUpdate({ role: "bgn_monitor", locationId: null }, "sppg_nutritionist", "loc-3"),
    ).toEqual({ role: "sppg_nutritionist", location_id: "loc-3" });
  });

  it("ganti peran antar SPPG dengan lokasi sama → hanya role", () => {
    expect(draftUserUpdate(user, "sppg_nutritionist", "loc-1")).toEqual({
      role: "sppg_nutritionist",
    });
  });
});
