// Memilih satu kiriman untuk disorot (Arah C) — logika MURNI.
// Aturan yang diuji: gagal-tertutup pada id tak dikenal, urutan mengikuti
// "paling mendesak" yang sama dengan kartu/papan, dan kalimat fokus menyebut
// jumlah kiriman yang disembunyikan (bukan "semua" tanpa angka).
import { describe, expect, it } from "vitest";

import {
  FOCUS_ALL,
  FOCUS_CLEAR_LABEL,
  focusFilterText,
  focusLabel,
  focusNote,
  focusOptions,
  focusPick,
  focusRows,
} from "../lib/route-focus";

function route(
  over: Record<string, unknown> = {}
): Record<string, unknown> {
  return {
    batch_id: "B-1",
    supplier_id: "S1",
    supplier_name: "Supplier A",
    origin: { latitude: -6.8, longitude: 107.1 },
    destination_id: "L1",
    destination_name: "Jakarta",
    destination: { latitude: -6.2, longitude: 106.8 },
    commodity: "telur",
    quantity_kg: 800,
    harvested_at: "2026-10-16T01:00:00+00:00",
    usable_until: "2026-11-07T11:00:00+00:00",
    safety_status: "pass",
    straight_km: 78.4,
    road: {
      distance_km: 110.4,
      duration_min: 84,
      geometry: { type: "LineString", coordinates: [[107.1, -6.8], [106.8, -6.2]] },
      source: "osrm",
      fetched_at: "2026-10-16T00:10:00+00:00",
    },
    journey: {
      dispatched_at: "2026-10-16T12:24:00+00:00",
      eta_at: "2026-10-16T12:24:00+00:00",
      state: "di_jalan",
      state_label: "Di jalan",
      travel_min: 84,
      remaining_min: 20,
      progress: 0.5,
      usable_until: "2026-11-07T11:00:00+00:00",
      arrives_before_usable_until: true,
    },
    ...over,
  };
}

const LANGSUNG: Record<string, unknown>[] = [
  route({
    supplier_id: "S3",
    supplier_name: "Supplier C",
    destination_id: "L3",
    destination_name: "Surabaya",
    journey: { state: "belum_berangkat", state_label: "Belum berangkat", eta_at: null, dispatched_at: null },
  }),
  route(),
  route({
    supplier_id: "S2",
    supplier_name: "Supplier B",
    destination_id: "L2",
    destination_name: "Bandung",
    journey: { state: "sudah_tiba", state_label: "Sudah tiba", eta_at: "2026-10-16T13:00:00+00:00" },
  }),
];

describe("fokus kiriman (Arah C)", () => {
  it("urutan pilihan = paling mendesak dulu (di jalan → belum berangkat → sudah tiba)", () => {
    expect(focusRows({ routes: LANGSUNG }).map((r) => r.id)).toEqual([
      "S1->L1",
      "S3->L3",
      "S2->L2",
    ]);
  });

  it("urutan sama juga berlaku bila data datang sebagai array lepas", () => {
    expect(focusRows(LANGSUNG).map((r) => r.id)).toEqual(["S1->L1", "S3->L3", "S2->L2"]);
  });

  it("baris tanpa dua ujung yang pasti dibuang, bukan ditampilkan setengah", () => {
    const rusak = [...LANGSUNG, { supplier_name: "Tanpa Titik", destination_name: "Entah" }];
    expect(focusRows({ routes: rusak }).map((r) => r.id)).toHaveLength(3);
  });

  it("opsi pemilih memuat label dan keadaan dari server", () => {
    const options = focusOptions({ routes: LANGSUNG });
    expect(options[0]).toMatchObject({
      id: "S1->L1",
      label: "Supplier A → Jakarta",
      state: "Di jalan · 20 menit lagi",
      tone: "moving",
    });
    expect(options[2].label).toBe("Supplier B → Bandung");
    expect(options[1].state).toBe("Belum berangkat");
  });

  it("id tak dikenal / kosong = tampilan SEMUA (gagal-tertutup, bukan tebakan)", () => {
    expect(focusPick({ routes: LANGSUNG }, FOCUS_ALL)).toBeNull();
    expect(focusPick({ routes: LANGSUNG }, "")).toBeNull();
    expect(focusPick({ routes: LANGSUNG }, null)).toBeNull();
    expect(focusPick({ routes: LANGSUNG }, "S9->L9")).toBeNull();
  });

  it("id yang ada mengembalikan kirimannya", () => {
    const row = focusPick({ routes: LANGSUNG }, "S3->L3");
    expect(row?.supplierName).toBe("Supplier C");
    expect(focusLabel(row!)).toBe("Supplier C → Surabaya");
  });

  it("tanpa fokus: kalimat menyebut jumlah kiriman sebenarnya", () => {
    expect(focusNote(null, 3)).toBe("Menampilkan semua 3 kiriman di jaringan.");
    expect(focusNote(null, 1)).toBe("Menampilkan satu-satunya kiriman di jaringan.");
    expect(focusNote(null, 0)).toBe("Menampilkan semua 0 kiriman di jaringan.");
  });

  it("dengan fokus: kalimat menyebut kiriman terpilih + sisanya disembunyikan", () => {
    const row = focusPick({ routes: LANGSUNG }, "S1->L1")!;
    expect(focusNote(row, 3)).toBe(
      "Menampilkan kiriman terpilih di peta: Supplier A → Jakarta (2 kiriman lain disembunyikan)."
    );
    expect(focusNote(row, 1)).toBe(
      "Menampilkan kiriman terpilih di peta: Supplier A → Jakarta (tidak ada kiriman lain)."
    );
  });
});

describe("chip saringan aktif di atas kanvas (celah C8, langkah 7b-2)", () => {
  it("menyebut kiriman yang sedang menyaring, memakai nama yang sama dengan pemilih", () => {
    const row = focusPick({ routes: LANGSUNG }, "S1->L1")!;
    expect(focusFilterText(row)).toBe("Menyaring: Supplier A → Jakarta");
    // Nama kiriman datang dari SATU sumber (`focusLabel`), bukan dirangkai ulang
    // di komponen — supaya chip, pil pemilih, dan kartu tidak pernah beda sebut.
    expect(focusFilterText(row)).toContain(focusLabel(row));
  });

  it("teksnya tetap satu baris pendek: tidak memuat keadaan perjalanan", () => {
    const row = focusPick({ routes: LANGSUNG }, "S1->L1")!;
    expect(focusFilterText(row)).not.toContain("lagi");
    expect(focusFilterText(row)).not.toContain("\n");
  });

  it("nama tombol pelepas tetap satu kata yang sama untuk semua tempat", () => {
    expect(FOCUS_CLEAR_LABEL).toBe("Lepas");
  });
});
