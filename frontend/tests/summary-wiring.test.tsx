// Test S4-04 wiring — page memuat summary kanonik via fetchApprovalSummary
// saat decision dipilih, dan meneruskannya ke DecisionActions (bukan objek
// feed `selected`). RED dulu: page belum memakai endpoint kanonik.
// Node-env (tanpa jsdom) → kontrak wiring diverifikasi pada source page:
// (1) memanggil fetchApprovalSummary, (2) tidak lagi pass summary={selected}.

import { describe, expect, it } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";

function pageSource(): string {
  return readFileSync(join(process.cwd(), "app", "page.tsx"), "utf-8");
}

describe("page wiring approval-summary (S4-04)", () => {
  it("page memanggil fetchApprovalSummary (read model kanonik)", () => {
    const src = pageSource();
    expect(src).toContain("fetchApprovalSummary");
    // Dipanggil dengan token + selectedId (bukan dekoratif import).
    expect(src).toMatch(/fetchApprovalSummary\(\s*\w+,\s*\w+\s*\)/);
  });

  it("DecisionActions menerima summary kanonik, bukan objek feed", () => {
    const src = pageSource();
    // Objek feed lama tidak boleh lagi dipakai sebagai summary modal.
    expect(src).not.toMatch(/summary=\{selected\}/);
  });
});
