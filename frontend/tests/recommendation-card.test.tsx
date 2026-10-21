// Kontrak RecommendationCard: kartu hanya menampilkan yang benar-benar ada di
// data. Kata penanda dari backend (mis. verifier_note "unavailable") bukan
// narasi — jangan dicetak sebagai paragraf.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import RecommendationCard, { CARD_HINT } from "../components/RecommendationCard";

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
    expect(html).not.toContain("dtk");
    expect(html).toContain("berlaku");
  });

  it("valid dengan sisa waktu: dicetak dalam menit, bukan detik", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, valid: true, seconds_remaining: 600 } as any} />
    );
    expect(html).toContain("berlaku 10 menit");
    expect(html).not.toContain("dtk");
  });

  it.each([
    [59, "kurang dari 1 menit"],
    [90, "1 menit"],
    [3600, "1 jam"],
    [5400, "1 jam 30 menit"],
    [90000, "1 hari 1 jam"],
  ])("sisa %i detik ditulis '%s'", (seconds, expected) => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, valid: true, seconds_remaining: seconds } as any} />
    );
    expect(html).toContain(`berlaku ${expected}`);
    expect(html).not.toContain("dtk");
  });
});

// Ajakan "klik" hanya jujur kalau kartunya memang terbungkus tombol (di feed).
// Di halaman Decision & Evidence kartunya dirender polos, jadi pemanggil di
// sana mengirim hint={null} — lihat tests/decision-evidence.test.tsx.
describe("RecommendationCard — ajakan klik", () => {
  it("bawaan (dipakai feed): ajakan tampil, dan tetap disembunyikan dari pembaca layar", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} />);
    // React meng-escape "&" jadi "&amp;" di markup — bandingkan setelah dibalik.
    expect(html.replace(/&amp;/g, "&")).toContain(CARD_HINT);
    expect(html).toContain('aria-hidden="true"');
  });

  it("hint={null}: tidak ada ajakan sama sekali", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} hint={null} />);
    expect(html).not.toContain("rec-hint");
    expect(html).not.toContain("Klik untuk rincian");
  });

  it("hint kosong: juga tidak menghasilkan penanda kosong", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} hint="" />);
    expect(html).not.toContain("rec-hint");
  });
});
