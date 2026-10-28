/**
 * Kontrak jendela periode feed rekomendasi (24 Okt 2026).
 *
 * Pemilik minta menu "hari ini / 7 hari / 1 bulan" di tab Recommendations.
 * Tes ini mengunci arti tiap label, kuncinya yang dipakai API, dan label yang
 * muncul di kalimat status — supaya teks di layar tidak pernah menyimpang dari
 * parameter yang dikirim ke backend.
 */
import { describe, expect, it } from "vitest";

import {
  FEED_WINDOWS,
  FEED_WINDOW_DEFAULT,
  feedWindowHint,
  feedWindowHintBilaBerbeda,
  feedWindowLabel,
} from "../lib/decisions-window";

describe("jendela periode feed", () => {
  it("tiga pilihan, urut dari tersempit", () => {
    expect(FEED_WINDOWS.map((w) => w.key)).toEqual(["24h", "7d", "30d"]);
    expect(FEED_WINDOWS.map((w) => w.label)).toEqual([
      "Hari ini",
      "7 hari",
      "1 bulan",
    ]);
  });

  it("bawaannya hari ini", () => {
    expect(FEED_WINDOW_DEFAULT).toBe("24h");
  });

  it("label dan bantuan cocok dengan kuncinya", () => {
    expect(feedWindowLabel("24h")).toBe("Hari ini");
    expect(feedWindowHint("24h")).toBe("24 jam terakhir");
    expect(feedWindowLabel("7d")).toBe("7 hari");
    expect(feedWindowLabel("30d")).toBe("1 bulan");
    expect(feedWindowHint("30d")).toContain("bulan berjalan");
  });

  it("kunci tak dikenal jatuh ke hari ini, bukan kosong", () => {
    expect(feedWindowLabel("9z" as never)).toBe("Hari ini");
    expect(feedWindowHint("9z" as never)).toBe("24 jam terakhir");
  });

  // 29 Okt 2026 — petunjuk periode hanya dicetak bila menambah arti. Label
  // "7 hari" + petunjuk "7 hari terakhir" adalah kalimat yang sama dua kali,
  // dan di layar ia terbaca seperti chip keempat.
  it("petunjuk periode hanya keluar bila menambah arti di luar labelnya", () => {
    expect(feedWindowHintBilaBerbeda("24h")).toBe("24 jam terakhir");
    expect(feedWindowHintBilaBerbeda("7d")).toBeNull();
    expect(feedWindowHintBilaBerbeda("30d")).toContain("bulan berjalan");
  });
});
