// Kontrak RecommendationCard: kartu hanya menampilkan yang benar-benar ada di
// data. Kata penanda dari backend (mis. verifier_note "unavailable") bukan
// narasi — jangan dicetak sebagai paragraf.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import RecommendationCard from "../components/RecommendationCard";

const BASE = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  created_at: "2026-10-10T18:16:47.844642+00:00",
  expires_at: "2026-10-11T02:16:47.973521+00:00",
  valid: false,
  iteration: 3,
};

describe("RecommendationCard — narasi", () => {
  it("alasan penolakan dicetak apa adanya", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, rejection_reason: "Kuota SPPG Jakarta penuh" } as any} />
    );
    expect(html).toContain("Kuota SPPG Jakarta penuh");
  });

  it("catatan penanda 'unavailable' TIDAK dicetak sebagai paragraf", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE, verifier_note: "unavailable" } as any} />);
    expect(html).not.toContain("rec-narrative");
    expect(html).not.toContain("unavailable");
  });

  it("catatan verifier yang bermakna tetap dicetak", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, verifier_note: "Konsisten dengan data batch" } as any} />
    );
    expect(html).toContain("Konsisten dengan data batch");
    expect(html).toContain("rec-narrative");
  });

  it("tanpa narasi: tidak ada paragraf kosong", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} />);
    expect(html).not.toContain("rec-narrative");
  });

  it("valid tanpa sisa waktu: TIDAK mencetak '0 dtk' yang dikarang", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, valid: true, seconds_remaining: null } as any} />
    );
    expect(html).not.toContain("0 dtk");
    expect(html).toContain("berlaku");
  });

  it("valid dengan sisa waktu: angka aslinya dicetak", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, valid: true, seconds_remaining: 600 } as any} />
    );
    expect(html).toContain("berlaku 600 dtk");
  });
});
