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

function detailHookSource(): string {
  return readFileSync(join(process.cwd(), "lib", "hooks", "useDecisionDetail.ts"), "utf-8");
}

describe("page wiring approval-summary (S4-04)", () => {
  it("hook useDecisionDetail memanggil fetchApprovalSummary (read model kanonik)", () => {
    // Rules.md §3: halaman memakai useDecisionDetail; panggilan API-nya di hook.
    const page = pageSource();
    const hook = detailHookSource();
    expect(page).toContain("useDecisionDetail");
    expect(hook).toContain("fetchApprovalSummary");
    // Dipanggil dengan id keputusan + token (bukan import dekoratif).
    expect(hook).toMatch(/fetchApprovalSummary\(\s*id,\s*token as string\s*\)/);
  });

  it("DecisionActions menerima summary kanonik, bukan objek feed", () => {
    const src = pageSource();
    // Objek feed lama tidak boleh lagi dipakai sebagai summary modal.
    expect(src).not.toMatch(/summary=\{selected\}/);
  });
});

describe("kegagalan detail keputusan tidak lagi ditelan", () => {
  const baca = () => readFileSync(join(process.cwd(), "lib", "hooks", "useDecisionDetail.ts"), "utf-8");

  it("memakai allSettled dan melaporkan bagian yang gagal", () => {
    const isi = baca();
    expect(isi).toContain("Promise.allSettled");
    expect(isi).toContain("errors: string[]");
    expect(isi).toContain('gagal.push(label)');
    // `catch(() => null)` lama menyembunyikan galat; tidak boleh kembali.
    expect(isi).not.toContain("catch(() => null)");
  });

  it("halaman menampilkan peringatan saat sebagian bukti gagal", () => {
    const page = readFileSync(join(process.cwd(), "app", "page.tsx"), "utf-8");
    expect(page).toContain("detail.errors.length > 0");
    expect(page).toContain("Sebagian bukti gagal dibaca");
  });
});
