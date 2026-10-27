// Fase 9 butir 5 — regresi: panel review TIDAK boleh jatuh saat induk belum
// punya paket.
//
// Terukur di browser (Decision & Evidence, 27 Okt 2026 22.2x): halaman mati
// dengan `TypeError: Cannot read properties of null (reading 'batch_evaluations')`
// — `const paket = packet ?? packetSendiri` sudah benar, tetapi dua baris di
// bawahnya masih membaca `packet`. Begitu unduhan sendiri selesai (induk masih
// mengirim `packet=null`), render berikutnya melempar dan SELURUH tab hilang.
//
// Tes ini menirukan urutan itu: render dengan `packet={null}`, biarkan efek
// mengambil paket sendiri, lalu pastikan panel tetap tampil dengan batch yang
// perlu ditinjau.

// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

const PAKET = {
  batch_evaluations: [
    {
      batch_id: "b1aaaaaa-1111-2222-3333-444455556666",
      status: "on_hold",
      blocking_reasons: ["safety_pending"],
      next_step: "uji keamanan pangan lalu catat verifikasi",
      safety_status: "pending",
      usable_until: null,
      evidence_state: "missing",
    },
  ],
  review: { human_reviews: [] },
};

vi.mock("../lib/api", () => ({
  fetchDecisionPacket: vi.fn(async () => PAKET),
  reviewDecision: vi.fn(async () => ({ status_changed: false })),
}));

import { act } from "react";
import { createRoot } from "react-dom/client";

import HumanReviewPanel from "../components/HumanReviewPanel";

const asalAct = globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean };
asalAct.IS_REACT_ACT_ENVIRONMENT = true;

afterEach(() => {
  document.body.innerHTML = "";
});

describe("Fase 9 butir 5 — panel review tanpa paket dari induk", () => {
  it("paket sendiri termuat tanpa melempar, batch tinjauan ikut tampil", async () => {
    const wadah = document.createElement("div");
    document.body.appendChild(wadah);
    const root = createRoot(wadah);

    await act(async () => {
      root.render(
        <HumanReviewPanel
          decisionId="d1"
          token="tok"
          role="sppg_head"
          packet={null}
        />
      );
    });

    expect(wadah.innerHTML).toContain("Verifikasi bukti batch");
    // Satu opsi placeholder + satu batch dari paket sendiri.
    // Spread NodeListOf tidak diizinkan tsconfig ini (TS2802); Array.from
    // menghasilkan daftar yang sama tanpa mengubah target proyek.
    const opsi = Array.from(wadah.querySelectorAll("select option")).map((o) =>
      o.textContent?.trim()
    );
    expect(opsi.length).toBe(2);
    expect(opsi[1]).toContain("b1aaaaaa");

    await act(async () => root.unmount());
  });
});
