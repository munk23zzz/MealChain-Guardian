// P4 — default tab Agent Log harus memilih keputusan yang PUNYA review 7 agen.
//
// Kenapa: tanpa ini, tab membuka keputusan terbaru apa pun dan menampilkan
// "Belum ada review 7 agen untuk keputusan ini" walau review-nya ada di
// keputusan lain — di depan juri itu terbaca "agen tidak jalan".

import { describe, expect, it } from "vitest";

import { defaultAgentLogId } from "../lib/agent-swarm";

const baris = (id: string, punyaReview: boolean | undefined) => ({
  decision_id: id,
  has_agent_review: punyaReview,
});

describe("defaultAgentLogId", () => {
  it("mempertahankan pilihan pengguna bila keputusan itu punya review", () => {
    const daftar = [baris("baru", false), baris("pilihan", true)];
    expect(defaultAgentLogId(daftar, "pilihan")).toBe("pilihan");
  });

  it("memilih keputusan terbaru yang punya review bila yang terpilih tidak punya", () => {
    const daftar = [baris("baru", false), baris("review-1", true), baris("review-2", true)];
    expect(defaultAgentLogId(daftar, "baru")).toBe("review-1");
  });

  it("memilih keputusan ber-review saat belum ada yang dipilih", () => {
    const daftar = [baris("baru", false), baris("review-1", true)];
    expect(defaultAgentLogId(daftar, null)).toBe("review-1");
  });

  it("tidak mengarang: bila tak satu pun punya review, kembalikan pilihan semula", () => {
    const daftar = [baris("a", false), baris("b", false)];
    expect(defaultAgentLogId(daftar, "b")).toBe("b");
    expect(defaultAgentLogId(daftar, null)).toBe(null);
  });

  it("baris tanpa field has_agent_review dianggap belum direview", () => {
    const daftar = [baris("tanpa-field", undefined), baris("punya", true)];
    expect(defaultAgentLogId(daftar, "tanpa-field")).toBe("punya");
  });

  it("daftar kosong / null aman", () => {
    expect(defaultAgentLogId([], "x")).toBe("x");
    expect(defaultAgentLogId(null, null)).toBe(null);
  });
});
