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

import { DURASI_ANIMASI_MS, fraksiAnimasi, fraksiBerjalan } from "../lib/truck-progress";
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

/**
 * Animasi perjalanan di peta (permintaan 30 Okt 2026): ikon mobil harus
 * MENUNTASKAN jalurnya di bawah satu menit waktu nyata, sementara waktu tempuh
 * dan ETA yang tertulis tetap angka asli. Yang diuji: laju animasi, monotonitas,
 * dan batas 1 — bukan angka estimasi.
 */
describe("fraksiAnimasi", () => {
  it("tepat di jangkar memakai progress server apa adanya", () => {
    expect(fraksiAnimasi(journey({ progress: 0.25 }), { progress: 0.25, at: T0 }, T0)).toBeCloseTo(0.25, 9);
  });

  it("tuntas (fraksi 1) paling lambat DURASI_ANIMASI_MS", () => {
    expect(DURASI_ANIMASI_MS).toBeLessThan(60_000);
    expect(fraksiAnimasi(journey(), { progress: 0.1, at: T0 }, T0 + DURASI_ANIMASI_MS)).toBe(1);
    expect(fraksiAnimasi(journey(), { progress: 0, at: T0 }, T0 + DURASI_ANIMASI_MS)).toBe(1);
  });

  it("di tengah durasi animasi sudah setengah jalan menuju ujung", () => {
    expect(
      fraksiAnimasi(journey({ progress: 0.2 }), { progress: 0.2, at: T0 }, T0 + DURASI_ANIMASI_MS / 2)
    ).toBeCloseTo(0.2 + 0.5 * 0.8, 9);
  });

  it("angka server yang menyusul tidak memundurkan ikon", () => {
    // Server baru melaporkan 0,4 padahal animasi sudah maju; posisi tetap maju.
    const sudah = fraksiAnimasi(journey({ progress: 0.2 }), { progress: 0.2, at: T0 }, T0 + 10_000);
    const sesudah = fraksiAnimasi(
      journey({ progress: 0.4 }),
      { progress: 0.2, at: T0 },
      T0 + 10_000
    );
    expect(sesudah).toBeCloseTo(0.4, 9);
    // dan pada waktu berikutnya tetap tidak mundur
    expect(
      fraksiAnimasi(journey({ progress: 0.4 }), { progress: 0.2, at: T0 }, T0 + 20_000)
    ).toBeGreaterThan(sesudah);
    expect(sudah).toBeLessThan(sesudah);
  });

  it("tidak pernah melewati 1 dan tahan jam mundur", () => {
    expect(fraksiAnimasi(journey(), { progress: 0.9, at: T0 }, T0 + 10 * DURASI_ANIMASI_MS)).toBe(1);
    expect(fraksiAnimasi(journey({ progress: 0.5 }), { progress: 0.5, at: T0 }, T0 - 5_000)).toBeCloseTo(0.5, 9);
  });

  it("jangkar/durasi tidak masuk akal jatuh ke angka server", () => {
    expect(fraksiAnimasi(journey({ progress: 0.3 }), null, T0 + 60_000)).toBeCloseTo(0.3, 9);
    expect(
      fraksiAnimasi(journey({ progress: 0.3 }), { progress: 0.3, at: T0 }, T0 + 1_000, 0)
    ).toBeCloseTo(0.3, 9);
  });
});
