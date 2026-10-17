// Kontrak deep link keputusan: `?keputusan=<id>`.
//
// Alasan: sebelum ini keputusan hanya hidup di state React, jadi tidak bisa
// dibagikan ("coba lihat yang ini") dan hilang saat halaman dimuat ulang.
// Fungsi di sini murni supaya bisa diuji tanpa DOM; halaman hanya membaca &
// menulis URL lewat `lib/decision-link.ts`.
import { describe, expect, it } from "vitest";

import { DECISION_PARAM, readDecisionLink, withDecisionLink } from "../lib/decision-link";

describe("readDecisionLink — membaca ?keputusan=", () => {
  it("mengambil id dari query string", () => {
    expect(readDecisionLink("?keputusan=4fd1b640-00f9-4e95-b58e-855fb1283db0")).toBe(
      "4fd1b640-00f9-4e95-b58e-855fb1283db0"
    );
  });

  it("parameter lain tidak mengganggu", () => {
    expect(readDecisionLink("?tab=evidence&keputusan=abc123")).toBe("abc123");
    expect(readDecisionLink("keputusan=abc123")).toBe("abc123");
  });

  it("tidak ada / kosong → null (jangan membuka keputusan karangan)", () => {
    expect(readDecisionLink(null)).toBeNull();
    expect(readDecisionLink("")).toBeNull();
    expect(readDecisionLink("?")).toBeNull();
    expect(readDecisionLink("?tab=evidence")).toBeNull();
    expect(readDecisionLink("?keputusan=")).toBeNull();
    expect(readDecisionLink("?keputusan=%20%20")).toBeNull();
  });

  it("nilai yang jelas bukan id ditolak", () => {
    expect(readDecisionLink("?keputusan=ada spasi di sini")).toBeNull();
    expect(readDecisionLink("?keputusan=" + "x".repeat(65))).toBeNull();
  });

  it("nama parameter diekspor, bukan string ajaib di dua tempat", () => {
    expect(DECISION_PARAM).toBe("keputusan");
  });
});

describe("withDecisionLink — menulis URL tanpa merusak param lain", () => {
  it("menambahkan param keputusan", () => {
    expect(withDecisionLink("", "abc")).toBe("?keputusan=abc");
    expect(withDecisionLink("?tab=evidence", "abc")).toBe("?tab=evidence&keputusan=abc");
  });

  it("mengganti id lama, bukan menumpuk", () => {
    expect(withDecisionLink("?keputusan=lama", "baru")).toBe("?keputusan=baru");
  });

  it("menghapus param saat tidak ada keputusan dipilih", () => {
    expect(withDecisionLink("?keputusan=abc", null)).toBe("");
    expect(withDecisionLink("?tab=evidence&keputusan=abc", null)).toBe("?tab=evidence");
    expect(withDecisionLink("", null)).toBe("");
  });

  it("stabil: hasilnya bisa dibaca ulang oleh readDecisionLink", () => {
    const qs = withDecisionLink("?tab=evidence", "9e1e7c6f-f78f-4677-9b72-6529c3ad1d2e");
    expect(readDecisionLink(qs)).toBe("9e1e7c6f-f78f-4677-9b72-6529c3ad1d2e");
  });
});
