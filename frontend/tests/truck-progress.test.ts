/**
 * Tes posisi mobil kiriman antar denyut (audit 24 Okt 2026).
 *
 * Alasan tes ini ada: sebelum perbaikan, mobil hanya bergeser saat data
 * disegarkan dan denyutnya 60 detik — di layar tampak diam. Yang diuji di sini
 * adalah fungsi waktu murni, tanpa peta.
 *
 * Kontrak penting: fraksi HARUS mulai dari `progress` server (bukan dihitung
 * dari `etaAt`), supaya jam peramban yang berbeda tidak pernah membuat mobil
 * melompat ke awal/ujung jalur.
 */
import { describe, expect, it } from "vitest";

import { fraksiBerjalan } from "../lib/truck-progress";
import type { RouteJourney } from "../lib/supplier-routes";

function journey(over: Partial<RouteJourney> = {}): RouteJourney {
  return {
    dispatchedAt: "2026-10-24T00:00:00.000Z",
    etaAt: "2026-10-24T01:00:00.000Z",
    state: "di_jalan",
    stateLabel: "Di jalan",
    travelMin: 60,
    elapsedMin: 0,
    remainingMin: 60,
    progress: 0.5,
    usableUntil: null,
    arrivesBeforeUsableUntil: null,
    ...over,
  };
}

const T0 = Date.parse("2026-10-24T00:30:00.000Z");

describe("fraksiBerjalan", () => {
  it("tepat di jangkar memakai progress server apa adanya", () => {
    expect(fraksiBerjalan(journey(), { progress: 0.5, at: T0 }, T0)).toBeCloseTo(
      0.5,
      9
    );
    // Kasus nyata di tes peta: 71,2% harus tetap 71,2% pada detik pertama.
    expect(
      fraksiBerjalan(journey({ progress: 0.712 }), { progress: 0.712, at: T0 }, T0)
    ).toBeCloseTo(0.712, 9);
  });

  it("maju satu menit = 1/60 perjalanan untuk durasi 60 menit", () => {
    expect(
      fraksiBerjalan(journey(), { progress: 0.5, at: T0 }, T0 + 60_000)
    ).toBeCloseTo(0.5 + 1 / 60, 6);
  });

  it("maju 15 detik mengikuti durasi tempuh 82 menit", () => {
    expect(
      fraksiBerjalan(
        journey({ travelMin: 82, progress: 0.4 }),
        { progress: 0.4, at: T0 },
        T0 + 15_000
      )
    ).toBeCloseTo(0.4 + 15 / (82 * 60), 9);
  });

  it("tidak pernah melewati 1", () => {
    expect(
      fraksiBerjalan(journey(), { progress: 0.999, at: T0 }, T0 + 3_600_000)
    ).toBe(1);
  });

  it("tahan jam peramban mundur (tidak bergerak ke belakang)", () => {
    expect(
      fraksiBerjalan(journey(), { progress: 0.6, at: T0 }, T0 - 60_000)
    ).toBe(0.6);
  });

  it("jatuh ke jangkar kalau durasi tidak masuk akal", () => {
    expect(
      fraksiBerjalan(
        journey({ travelMin: 0, progress: 0.23 }),
        { progress: 0.23, at: T0 },
        T0 + 60_000
      )
    ).toBeCloseTo(0.23, 9);
  });

  it("tanpa jangkar memakai progress server; tanpa data = 0", () => {
    expect(fraksiBerjalan(journey({ progress: 0.33 }), null, T0)).toBeCloseTo(
      0.33,
      9
    );
    expect(fraksiBerjalan(null, null, T0)).toBe(0);
  });
});
