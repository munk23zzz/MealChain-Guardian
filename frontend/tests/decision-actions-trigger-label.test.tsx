import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionActions from "../components/DecisionActions";

/**
 * Label pemicu mengikuti KEADAAN persetujuan (Langkah 4, 19 Okt 2026).
 *
 * Alasan: "Kelola persetujuan" pada keputusan yang sudah selesai/ditolak
 * menjanjikan pekerjaan yang tidak ada; pada keputusan yang baru disetujui
 * sebagian, pengguna perlu tahu bahwa yang ditunggu adalah REKAN, bukan dirinya.
 * Semua keadaan tetap bisa dibuka (tidak ada tombol mati), dan tidak ada aksi
 * satu klik — popup tetap gerbangnya.
 */

const dasar = {
  decisionId: "3860992a-0000-0000-0000-000000000000",
  role: "sppg_head",
  token: "t",
};

function ringkas(over: Record<string, unknown> = {}) {
  return {
    status: "pending_approval",
    approval_requirement: {
      verdict: "consistent",
      min_approvals: 2,
      required_roles: [["sppg_head"], ["sppg_nutritionist"]],
    },
    approval_state: {
      satisfied: false,
      rejected: false,
      missing: [["sppg_head"], ["sppg_nutritionist"]],
      approved_roles: [],
    },
    can_approve: true,
    can_execute: false,
    blocking_reasons: ["approval belum lengkap"],
    ...over,
  };
}

function label(html: string): string {
  const cocok = /class="button"[^>]*>([^<]+)/.exec(html);
  return (cocok?.[1] ?? "").trim();
}

describe("DecisionActions — label pemicu per keadaan", () => {
  it("menunggu: 'Kelola persetujuan'", () => {
    const html = renderToStaticMarkup(
      <DecisionActions {...dasar} status="pending_approval" summary={ringkas()} />
    );
    expect(label(html)).toBe("Kelola persetujuan");
  });

  it("sebagian disetujui: 'Menunggu rekan' (tetap bisa dibuka)", () => {
    const html = renderToStaticMarkup(
      <DecisionActions
        {...dasar}
        status="pending_approval"
        summary={ringkas({
          approval_state: {
            satisfied: false,
            rejected: false,
            missing: [["sppg_nutritionist"]],
            approved_roles: ["sppg_head"],
          },
        })}
      />
    );
    expect(label(html)).toBe("Menunggu rekan");
    expect(html).toContain('aria-haspopup="dialog"');
  });

  it("selesai dieksekusi: 'Lihat hasil' — bukan tawaran menyetujui lagi", () => {
    const html = renderToStaticMarkup(
      <DecisionActions
        {...dasar}
        status="executed"
        summary={ringkas({
          status: "executed",
          approval_state: {
            satisfied: true,
            rejected: false,
            missing: [],
            approved_roles: ["sppg_head", "sppg_nutritionist"],
          },
          can_approve: false,
          can_execute: false,
        })}
      />
    );
    expect(label(html)).toBe("Lihat hasil");
  });

  it("ditolak: 'Lihat hasil' (keputusan sudah final)", () => {
    const html = renderToStaticMarkup(
      <DecisionActions
        {...dasar}
        status="rejected"
        summary={ringkas({
          status: "rejected",
          approval_state: {
            satisfied: false,
            rejected: true,
            missing: [["sppg_head"], ["sppg_nutritionist"]],
            approved_roles: [],
          },
          can_approve: false,
        })}
      />
    );
    expect(label(html)).toBe("Lihat hasil");
  });
});
