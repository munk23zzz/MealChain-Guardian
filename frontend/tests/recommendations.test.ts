import { describe, expect, it } from "vitest";

import { cardEdge } from "../lib/recommendations";

// Warna tepi kartu rekomendasi = bahasa isyarat utama di halaman ini.
// Aturan yang dijaga: status bahaya selalu menang; kartu kedaluwarsa TIDAK
// memakai warna "perhatikan saya" (biru/amber) supaya yang masih hidup menonjol.
describe("cardEdge", () => {
  it("status menunggu tindakan → tepi peringatan", () => {
    expect(cardEdge({ status: "PENDING_APPROVAL" })).toBe("edge-warning");
    expect(cardEdge({ status: "VERIFIER_FLAGGED" })).toBe("edge-warning");
    expect(cardEdge({ status: "NEEDS_VERIFICATION" })).toBe("edge-warning");
    expect(cardEdge({ status: "needs_verification" })).toBe("edge-warning"); // huruf kecil
  });

  it("status ditolak/gagal → tepi bahaya (tetap meski kedaluwarsa)", () => {
    expect(cardEdge({ status: "REJECTED" })).toBe("edge-danger");
    expect(cardEdge({ status: "FAIL" })).toBe("edge-danger");
    expect(cardEdge({ status: "REJECTED", valid: false })).toBe("edge-danger");
  });

  it("status netral yang masih berlaku → tepi utama (biru)", () => {
    expect(cardEdge({ status: "PROPOSED", valid: true })).toBe("edge-primary");
    expect(cardEdge({ status: "APPROVED", valid: true })).toBe("edge-primary");
  });

  it("kartu kedaluwarsa → tepi netral, BUKAN warna ajakan bertindak", () => {
    expect(cardEdge({ status: "PROPOSED", valid: false })).toBe("edge-expired");
    expect(cardEdge({ status: "PENDING_APPROVAL", valid: false })).toBe("edge-expired");
  });

  it("data kosong/tak dikenal tidak meledak", () => {
    expect(cardEdge(null)).toBe("edge-primary");
    expect(cardEdge(undefined)).toBe("edge-primary");
    expect(cardEdge({})).toBe("edge-primary");
    expect(cardEdge({ status: "" })).toBe("edge-primary");
    expect(cardEdge({ status: "STATUS_BARU_YANG_BELUM_DIPETAKAN" })).toBe("edge-primary");
    expect(cardEdge({ status: "STATUS_BARU", valid: false })).toBe("edge-expired");
  });
});
