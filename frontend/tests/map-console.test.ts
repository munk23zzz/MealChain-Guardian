// Logika murni peta (arah Roy 2026-10-11): nada & label pin + bar telemetri
// node. Tanpa DOM supaya bisa diuji langsung.
import { describe, expect, it } from "vitest";

import {
  MAP_FOCUS_INITIAL,
  nextMapFocus,
  nodeGauges,
  pinDiff,
  pinLabel,
  pinSignatures,
  pinTone,
} from "../lib/map-console";

const CIANJUR = { location: "Cianjur", region: "Jawa Barat", status: "surplus", surplus_kg: 1400, shortage_kg: 0 };
const JAKARTA = { location: "Jakarta", region: "DKI Jakarta", status: "shortage", surplus_kg: 0, shortage_kg: 780 };
const BOGOR = { location: "Bogor", region: "Jawa Barat", status: "balanced", surplus_kg: 0, shortage_kg: 0 };

describe("peta acuan — pin", () => {
  it("memetakan status ke nada pin", () => {
    expect(pinTone("surplus")).toBe("surplus");
    expect(pinTone("shortage")).toBe("shortage");
    expect(pinTone("balanced")).toBe("balanced");
    expect(pinTone(undefined)).toBe("unknown");
    expect(pinTone("entah")).toBe("unknown");
  });

  it("label pin = nama + selisih (tanpa angka karangan)", () => {
    expect(pinLabel(CIANJUR)).toBe("Cianjur +1.400 kg");
    expect(pinLabel(JAKARTA)).toBe("Jakarta −780 kg");
    expect(pinLabel(BOGOR)).toBe("Bogor seimbang");
    // Angka tidak tersedia → jangan menulis 0 atau tebakan.
    expect(pinLabel({ location: "Medan", status: "surplus" })).toBe("Medan");
    expect(pinLabel({ location: "Makassar", status: "entah" })).toBe("Makassar");
  });
});

describe("peta acuan — bar telemetri node", () => {
  it("proporsi bar memakai dua angka yang ada (bukan skala karangan)", () => {
    expect(nodeGauges({ location: "Cianjur", status: "surplus", supply_kg: 1000, demand_kg: 800 })).toEqual({
      supply: { value: 1000, share: 100 },
      demand: { value: 800, share: 80 },
    });
    expect(nodeGauges({ location: "Makassar", status: "shortage", supply_kg: 250, demand_kg: 1000 })).toEqual({
      supply: { value: 250, share: 25 },
      demand: { value: 1000, share: 100 },
    });
  });

  it("angka kosong tetap kosong (share 0, bukan 100%)", () => {
    expect(nodeGauges({ location: "Medan", status: "balanced" })).toEqual({
      supply: { value: null, share: 0 },
      demand: { value: null, share: 0 },
    });
    expect(nodeGauges({ location: "Medan", status: "balanced", supply_kg: 0, demand_kg: 0 })).toEqual({
      supply: { value: 0, share: 0 },
      demand: { value: 0, share: 0 },
    });
  });
});

// Arah Roy 2026-10-11: "ketika sync tidak ngezoom / sync tidak mengganggu
// ukuran zoom". Dua kontrak di bawah yang menjaganya.
describe("peta acuan — sinkronisasi tidak menyentuh zoom", () => {
  const JKT = { location: "Jakarta", region: "DKI Jakarta", status: "shortage", latitude: -6.2088, longitude: 106.8456, supply_kg: 300, demand_kg: 1080, surplus_kg: 0, shortage_kg: 780 };
  const CJR = { location: "Cianjur", region: "Jawa Barat", status: "surplus", latitude: -6.8168, longitude: 107.1425, supply_kg: 1400, demand_kg: 300, surplus_kg: 1100, shortage_kg: 0 };

  it("peta hanya di-dekatkan saat pertama tampil atau saat lokasi aktif berganti", () => {
    // Pertama tampil → boleh fokus.
    const first = nextMapFocus(MAP_FOCUS_INITIAL, "Jakarta");
    expect(first.fit).toBe(true);
    // Polling berikutnya: lokasi aktif sama → JANGAN sentuh zoom.
    expect(nextMapFocus(first.focus, "Jakarta").fit).toBe(false);
    // Ganti pilihan lokasi → boleh fokus ke lokasi baru.
    const moved = nextMapFocus(first.focus, "Cianjur");
    expect(moved.fit).toBe(true);
    expect(moved.focus.active).toBe("Cianjur");
    // Kembali ke tampilan semua lokasi (active null) juga dihitung pergantian.
    expect(nextMapFocus(moved.focus, null).fit).toBe(true);
  });

  it("tanda tangan penanda tidak berubah walau objeknya baru (sync 5 detik)", () => {
    const before = pinSignatures([JKT, CJR]);
    // Payload polling baru: objek/array baru, angka identik.
    const after = pinSignatures([{ ...JKT }, { ...CJR }]);
    expect(after).toEqual(before);
    expect(pinDiff(before, after)).toEqual({ added: [], changed: [], removed: [] });
  });

  it("angka/status yang benar-benar berubah hanya menyentuh penanda itu", () => {
    const before = pinSignatures([JKT, CJR]);
    const after = pinSignatures([{ ...JKT, shortage_kg: 900 }, CJR]);
    expect(pinDiff(before, after)).toEqual({ added: [], changed: ["Jakarta"], removed: [] });
    // Status berubah juga terdeteksi (nada pin + label ikut berubah).
    const toneChanged = pinSignatures([{ ...JKT, status: "surplus", surplus_kg: 0, shortage_kg: 0 }, CJR]);
    expect(pinDiff(before, toneChanged).changed).toEqual(["Jakarta"]);
  });

  it("lokasi baru muncul / lama hilang terdeteksi — tanpa menyentuh yang lain", () => {
    const before = pinSignatures([JKT, CJR]);
    const after = pinSignatures([
      JKT,
      { location: "Bogor", status: "balanced", latitude: -6.595, longitude: 106.8166, supply_kg: 550, demand_kg: 550 },
    ]);
    expect(pinDiff(before, after)).toEqual({ added: ["Bogor"], changed: [], removed: ["Cianjur"] });
  });

  it("lokasi tanpa koordinat tidak punya penanda (tidak dihitung sebagai tambah/hapus)", () => {
    const signatures = pinSignatures([JKT, { location: "Entah", status: "balanced" }]);
    expect(Object.keys(signatures)).toEqual(["Jakarta"]);
    expect(pinDiff({}, signatures)).toEqual({ added: ["Jakarta"], changed: [], removed: [] });
  });
});
