import { describe, expect, it } from "vitest";
import { formatClockUtc, formatDate, formatDateTime } from "../lib/datetime";

describe("formatDateTime (WIB, id-ID)", () => {
  it("format acuan: tanggal + jam titik + WIB", () => {
    // 24 Sep 2026 15:08 UTC = 22:08 WIB
    expect(formatDateTime("2026-09-24T15:08:00Z")).toBe("24 Sep 2026 22.08 WIB");
  });

  it("mikrodetik + offset UTC dari envelope backend tetap terbaca", () => {
    // 2026-10-10T18:16:47.844642+00:00 = 11 Okt 2026 01.16 WIB
    expect(formatDateTime("2026-10-10T18:16:47.844642+00:00")).toBe(
      "11 Okt 2026 01.16 WIB",
    );
  });

  it("tengah malam WIB tidak memakai jam 24", () => {
    expect(formatDateTime("2026-09-24T17:00:00Z")).toBe("25 Sep 2026 00.00 WIB");
  });

  it("kosong atau tidak sah tidak pernah jadi tanggal karangan", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
    expect(formatDateTime("")).toBe("—");
    expect(formatDateTime("bukan-tanggal")).toBe("—");
  });
});

describe("formatDate", () => {
  it("tanpa jam", () => {
    expect(formatDate("2026-09-24T15:08:00Z")).toBe("24 Sep 2026");
  });

  it("kosong atau tidak sah → —", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("bukan-tanggal")).toBe("—");
  });
});

describe("formatClockUtc (jam langkah jejak agen)", () => {
  it("ISO dengan mikrodetik + offset → jam:menit:detik UTC", () => {
    expect(formatClockUtc("2026-10-10T18:16:47.844642+00:00")).toBe("18:16:47");
  });

  it("kosong atau tidak sah → — (tidak melempar RangeError)", () => {
    expect(formatClockUtc(null)).toBe("—");
    expect(formatClockUtc(undefined)).toBe("—");
    expect(formatClockUtc("bukan-tanggal")).toBe("—");
  });
});
