// Regresi audit 29 Okt 2026: batch yang masa layaknya sudah lewat tidak boleh
// bersembunyi di "Aman", dan chip saringan harus memakai definisi yang sama
// dengan lencana tabel serta angka ringkasan.
import { describe, expect, it } from "vitest";

import {
  matchesSafetyFilter,
  safetyBadge,
  safetyFilterCounts,
  safetyRows,
  safetyState,
  safetySummaryOfRows,
  safetyStatusGroups,
} from "../lib/food-safety";

const NOW = new Date("2026-10-29T04:00:00Z");

const batch = (over: Record<string, unknown> = {}) => ({
  id: "x",
  location: "Jakarta",
  commodity: "wortel",
  quantity_kg: 100,
  safety_status: "pass",
  freshness_score: 0.8,
  usable_until: "2026-11-02T04:00:00Z",
  ...over,
});

const baris = (over: Record<string, unknown> = {}) => safetyRows([batch(over)], NOW)[0];

describe("keadaan batch: kedaluwarsa punya tempat sendiri", () => {
  it("lolos uji tapi sudah lewat masa layak = kedaluwarsa, bukan aman", () => {
    const row = baris({ usable_until: "2026-10-29T02:00:00Z" });
    expect(safetyState(row)).toBe("kedaluwarsa");
    expect(safetyBadge(row)).toEqual({ label: "Kedaluwarsa", tone: "danger" });
  });

  it("kedaluwarsa menang atas perlu verifikasi, tetapi karantina dan gagal tetap di atasnya", () => {
    const lewat = "2026-10-28T04:00:00Z";
    expect(safetyState(baris({ safety_status: "needs_verification", usable_until: lewat }))).toBe(
      "kedaluwarsa"
    );
    expect(safetyState(baris({ safety_status: "fail", usable_until: lewat }))).toBe("gagal");
    expect(
      safetyState(baris({ quarantine_status: "quarantined", usable_until: lewat }))
    ).toBe("ditahan");
  });

  it("masa layak yang tidak tercatat (null) bukan kedaluwarsa", () => {
    const row = baris({ usable_until: null });
    expect(safetyState(row)).toBe("aman");
    expect(safetyBadge(row)).toEqual({ label: "Aman", tone: "ok" });
  });

  it("lencana tabel tetap memakai label status untuk baris yang masih layak", () => {
    expect(safetyBadge(baris({ safety_status: "needs_verification" }))).toEqual({
      label: "Perlu verifikasi",
      tone: "warn",
    });
    expect(safetyBadge(baris({ safety_status: "pending" }))).toEqual({
      label: "Belum diuji",
      tone: "muted",
    });
  });
});

describe("chip saringan dan ringkasan memakai keadaan yang sama", () => {
  const rows = safetyRows(
    [
      batch({ id: "aman" }),
      batch({ id: "lewat", usable_until: "2026-10-29T02:00:00Z" }),
      batch({ id: "gagal", safety_status: "fail" }),
      batch({ id: "verif", safety_status: "needs_verification" }),
      batch({ id: "belum", safety_status: "pending" }),
      batch({ id: "tahan", quarantine_status: "quarantined" }),
    ],
    NOW
  );

  it("chip Aman tidak memuat batch kedaluwarsa", () => {
    const aman = rows.filter((row) => matchesSafetyFilter(row, "aman"));
    expect(aman.map((row) => row.id)).toEqual(["aman"]);
  });

  it("chip Perlu tindakan memuat batch kedaluwarsa", () => {
    expect(rows.filter((row) => matchesSafetyFilter(row, "tindakan")).map((row) => row.id)).toEqual(
      ["lewat", "gagal", "verif", "tahan"]
    );
  });

  it("chip Perlu verifikasi tidak lagi memuat batch yang ditahan", () => {
    const verifikasi = rows.filter((row) => matchesSafetyFilter(row, "verifikasi"));
    expect(verifikasi.map((row) => row.id)).toEqual(["verif"]);
    const grup = safetyStatusGroups(rows);
    expect(grup.find((g) => g.key === "verifikasi")?.value).toBe(verifikasi.length);
  });

  it("angka chip sama dengan angka tile untuk setiap irisan", () => {
    const hitung = safetyFilterCounts(rows);
    const grup = new Map(safetyStatusGroups(rows).map((g) => [g.key, g.value]));
    expect(hitung.aman).toBe(grup.get("aman"));
    expect(hitung.gagal).toBe(grup.get("gagal"));
    expect(hitung.verifikasi).toBe(grup.get("verifikasi"));
    expect(hitung.tindakan).toBe(
      (grup.get("gagal") ?? 0) +
        (grup.get("kedaluwarsa") ?? 0) +
        (grup.get("verifikasi") ?? 0) +
        (grup.get("ditahan") ?? 0)
    );
  });

  it("ringkasan: aman + gagal + kedaluwarsa + verifikasi + belum + ditahan = total", () => {
    const ringkas = safetySummaryOfRows(rows);
    expect(ringkas.safe).toBe(1);
    expect(ringkas.failed).toBe(1);
    expect(ringkas.expired).toBe(1);
    expect(ringkas.needsVerification).toBe(1);
    expect(ringkas.unchecked).toBe(1);
    const jumlahDitahan = safetyStatusGroups(rows).find((g) => g.key === "ditahan")?.value ?? 0;
    expect(
      ringkas.safe +
        ringkas.failed +
        ringkas.expired +
        ringkas.needsVerification +
        ringkas.unchecked +
        jumlahDitahan
    ).toBe(rows.length);
  });

  it("berat batch kedaluwarsa dilaporkan terpisah, bukan hilang", () => {
    const ringkas = safetySummaryOfRows(rows);
    expect(ringkas.expiredKg).toBe(100);
    expect(ringkas.failedKg).toBe(100);
  });
});
