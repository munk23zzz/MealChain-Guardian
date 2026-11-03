// Jejak agen untuk UI (Fase 4 redesign, 2026-10-16).
//
// Agent Log harus terasa hidup TANPA mengarang: tidak ada kolom status di tabel
// agent_traces, jadi "sedang berjalan" hanya boleh muncul kalau datanya sendiri
// mengatakannya (output_summary.status ∈ RUNNING_STATUSES). Yang selalu bisa
// dihitung adalah WAKTU — umur langkah dari step_at — dan itu dipakai apa
// adanya ("baru masuk 12 dtk lalu"), bukan sebagai klaim bahwa agen bekerja.
import { describe, expect, it } from "vitest";

import {
  NEW_STEP_MS,
  RUNNING_STATUSES,
  isNewStep,
  isRunningStep,
  stepAgeLabel,
  stepDurationLabel,
} from "../lib/agent-trace";

const NOW = new Date("2026-10-16T10:00:00Z");

describe("stepAgeLabel — umur langkah dari step_at", () => {
  it("detik, menit, jam, hari dalam bahasa Indonesia", () => {
    expect(stepAgeLabel("2026-10-16T09:59:40Z", NOW)).toBe("baru masuk 20 dtk lalu");
    expect(stepAgeLabel("2026-10-16T09:55:00Z", NOW)).toBe("baru masuk 5 mnt lalu");
    expect(stepAgeLabel("2026-10-16T07:00:00Z", NOW)).toBe("3 jam lalu");
    expect(stepAgeLabel("2026-10-13T10:00:00Z", NOW)).toBe("3 hari lalu");
  });

  it("waktu tak terbaca → null, bukan 'baru masuk 0 dtk lalu'", () => {
    for (const v of [undefined, null, "", "bukan-tanggal"]) {
      expect(stepAgeLabel(v, NOW)).toBeNull();
    }
  });

  it("waktu di masa depan (jam klien mundur) tidak diklaim 'baru'", () => {
    expect(stepAgeLabel("2026-10-16T10:05:00Z", NOW)).toBeNull();
  });

  it("tanpa jam klien → null (bukan memakai jam server)", () => {
    expect(stepAgeLabel("2026-10-16T09:00:00Z", null)).toBeNull();
  });
});

describe("isRunningStep — hanya bila data yang mengatakannya", () => {
  it("status eksplisit dari trace dianggap sedang berjalan", () => {
    for (const status of RUNNING_STATUSES) {
      expect(isRunningStep({ output_summary: { status } }), status).toBe(true);
    }
  });

  it("status selesai/lain tidak pernah diklaim berjalan", () => {
    for (const status of ["narrated", "ok", "done", "completed", "verdict_ok"]) {
      expect(isRunningStep({ output_summary: { status } }), status).toBe(false);
    }
  });

  it("tanpa output_summary/status → bukan berjalan", () => {
    expect(isRunningStep({})).toBe(false);
    expect(isRunningStep({ output_summary: null })).toBe(false);
    expect(isRunningStep({ output_summary: {} })).toBe(false);
    expect(isRunningStep(null)).toBe(false);
  });
});

describe("isNewStep — langkah yang baru masuk (fakta waktu, bukan klaim kerja)", () => {
  it("dalam jendela → baru; di luar jendela → tidak", () => {
    expect(isNewStep("2026-10-16T09:59:30Z", NOW)).toBe(true);
    expect(isNewStep("2026-10-16T09:50:00Z", NOW)).toBe(false);
    expect(NEW_STEP_MS).toBe(120_000);
  });

  it("waktu tak terbaca / tanpa jam → tidak baru", () => {
    expect(isNewStep(null, NOW)).toBe(false);
    expect(isNewStep("bukan-tanggal", NOW)).toBe(false);
    expect(isNewStep("2026-10-16T09:59:30Z", null)).toBe(false);
  });
});

describe("stepDurationLabel — durasi langkah apa adanya", () => {
  it("milidetik dan detik", () => {
    expect(stepDurationLabel({ duration_ms: 812 })).toBe("812 ms");
    expect(stepDurationLabel({ duration_ms: 1500 })).toBe("1,5 dtk");
    expect(stepDurationLabel({ duration_ms: 1000 })).toBe("1,0 dtk");
  });

  it("tanpa durasi/ tidak sah → null, bukan 0 ms", () => {
    expect(stepDurationLabel({})).toBeNull();
    expect(stepDurationLabel({ duration_ms: null })).toBeNull();
    expect(stepDurationLabel({ duration_ms: "x" })).toBeNull();
    expect(stepDurationLabel({ duration_ms: -1 })).toBeNull();
  });
});
