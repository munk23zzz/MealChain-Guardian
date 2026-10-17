// Test rejection loop di UI (TDD): timeline iterasi, badge versi,
// alasan penolakan, tombol re-propose, tanpa link 404.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import DecisionChain from "../components/DecisionChain";
import RecommendationCard from "../components/RecommendationCard";
import { visibleActions } from "../components/DecisionActions";

const CHAIN = [
  {
    decision_id: "a1",
    iteration: 1,
    status: "rejected",
    rejection_reason: "Kuota SPPG Jakarta penuh minggu ini",
    quantity_kg: 600,
    safe_delivered_cost: 16206000,
    created_at: "2026-10-07T10:00:00Z",
    demo_case: "rejection-loop-kuota",
  },
  {
    decision_id: "a2",
    iteration: 2,
    status: "rejected",
    rejection_reason: "Harga per kg naik 12% dari referensi",
    quantity_kg: 600,
    safe_delivered_cost: 16206000,
    created_at: "2026-10-07T10:30:00Z",
    demo_case: "rejection-loop-kuota",
  },
  {
    decision_id: "a3",
    iteration: 3,
    status: "pending_approval",
    rejection_reason: null,
    quantity_kg: 600,
    safe_delivered_cost: 16206000,
    created_at: "2026-10-07T11:00:00Z",
    demo_case: "rejection-loop-kuota",
  },
];

describe("DecisionChain (timeline iterasi)", () => {
  const html = renderToStaticMarkup(<DecisionChain chain={CHAIN} />);

  it("menampilkan tiap versi v1/v2/v3", () => {
    expect(html).toContain("v1");
    expect(html).toContain("v2");
    expect(html).toContain("v3");
  });

  it("menampilkan alasan penolakan tiap iterasi yang ditolak", () => {
    expect(html).toContain("Kuota SPPG Jakarta penuh minggu ini");
    expect(html).toContain("Harga per kg naik 12% dari referensi");
  });

  it("status tiap iterasi pakai badge", () => {
    expect(html).toContain("Ditolak");
    expect(html).toContain("Menunggu persetujuan");
  });

  it("chain kosong tidak merender apa pun", () => {
    expect(renderToStaticMarkup(<DecisionChain chain={[]} />)).toBe("");
  });
});

describe("RecommendationCard (iterasi + alasan)", () => {
  const rejected = renderToStaticMarkup(
    <RecommendationCard
      decision={{
        decision_id: "a2",
        decision_type: "regional_balance",
        status: "rejected",
        quantity_kg: 600,
        safe_delivered_cost: 16206000,
        expires_at: "2026-10-07T12:00:00Z",
        valid: false,
        iteration: 2,
        rejection_reason: "Harga per kg naik 12% dari referensi",
      }}
    />
  );

  it("menampilkan badge versi dan alasan penolakan", () => {
    expect(rejected).toContain("v2");
    expect(rejected).toContain("Harga per kg naik 12% dari referensi");
  });

  it("TIDAK lagi punya link /decisions/{id} (404)", () => {
    expect(rejected).not.toContain("decisions/a2");
    expect(rejected).not.toContain("Lihat Detail");
  });
});

describe("visibleActions (repropose)", () => {
  it("approver: rejected → bisa minta re-propose, tidak bisa approve", () => {
    const a = visibleActions("sppg_head", "rejected");
    expect(a.repropose).toBe(true);
    expect(a.approve).toBe(false);
    expect(a.readOnly).toBe(false);
  });

  it("bgn_monitor: selalu read-only", () => {
    const a = visibleActions("bgn_monitor", "rejected");
    expect(a.repropose).toBe(false);
    expect(a.readOnly).toBe(true);
  });

  it("pending_approval: Nutritionist hanya approve (execute milik Head)", () => {
    const a = visibleActions("sppg_nutritionist", "pending_approval");
    expect(a.approve).toBe(true);
    // PLAN.md §13.1/§13.3: eksekusi transfer hanya oleh Head.
    expect(a.execute).toBe(false);
    expect(a.repropose).toBe(false);
  });

  it("pending_approval: Head mendapat approve & execute", () => {
    const a = visibleActions("sppg_head", "pending_approval");
    expect(a.approve).toBe(true);
    expect(a.execute).toBe(true);
  });
});
