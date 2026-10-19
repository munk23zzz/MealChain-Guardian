import { describe, expect, it } from "vitest";

import { governanceView } from "../lib/governance";

/**
 * Governance & persetujuan — turunan status untuk kepala kartu (Langkah 2).
 *
 * Semua angka HARUS berasal dari read model server (`approval_requirement`
 * + `approval_state`), bukan dihitung ulang dari daftar approval di UI:
 * UI tidak boleh punya logika approval sendiri (design.md §1.3).
 */

const duaPeran = {
  approval_requirement: {
    verdict: "flagged",
    min_approvals: 2,
    required_roles: [["sppg_head"], ["sppg_nutritionist"]],
  },
  approval_state: {
    satisfied: false,
    rejected: false,
    missing: [["sppg_head"], ["sppg_nutritionist"]],
    approved_roles: [],
  },
  approver_roles: ["sppg_head", "sppg_nutritionist"],
  can_approve: true,
  can_execute: false,
  blocking_reasons: ["approval belum lengkap: 2 dari 2 role"],
};

function dengan(patch: Record<string, unknown>) {
  return { ...duaPeran, ...patch };
}

describe("governanceView — status", () => {
  it("belum ada persetujuan: menunggu, 0 dari 2", () => {
    const v = governanceView(duaPeran);
    expect(v.state).toBe("menunggu");
    expect(v.label).toBe("Menunggu persetujuan");
    expect(v.done).toBe(0);
    expect(v.total).toBe(2);
    expect(v.groups.map((g) => g.done)).toEqual([false, false]);
  });

  it("satu peran sudah menyetujui: sebagian, 1 dari 2", () => {
    const v = governanceView(
      dengan({
        approval_state: {
          satisfied: false,
          rejected: false,
          missing: [["sppg_nutritionist"]],
          approved_roles: ["sppg_head"],
        },
      })
    );
    expect(v.state).toBe("sebagian");
    expect(v.label).toBe("Sebagian disetujui");
    expect(v.done).toBe(1);
    expect(v.missingLabels).toEqual(["Ahli Gizi SPPG"]);
    expect(v.groups[0]).toMatchObject({ done: true, label: "Kepala SPPG" });
  });

  it("semua peran terpenuhi: siap dieksekusi", () => {
    const v = governanceView(
      dengan({
        approval_state: {
          satisfied: true,
          rejected: false,
          missing: [],
          approved_roles: ["sppg_head", "sppg_nutritionist"],
        },
        can_execute: true,
      })
    );
    expect(v.state).toBe("siap");
    expect(v.label).toBe("Siap dieksekusi");
    expect(v.done).toBe(2);
    expect(v.missingLabels).toEqual([]);
  });

  it("semua peran terpenuhi tetapi eksekusi tertahan: 'lengkap', bukan 'siap'", () => {
    // Kasus nyata di layar 19 Okt: peran syarat lengkap, `can_execute` masih
    // false (pemasok belum terikat / verifikasi / jendela lewat). Chip tidak
    // boleh menjanjikan "Siap dieksekusi" selama server menolak.
    const v = governanceView(
      dengan({
        approval_state: {
          satisfied: true,
          rejected: false,
          missing: [],
          approved_roles: ["sppg_head", "sppg_nutritionist"],
        },
        can_execute: false,
      })
    );
    expect(v.state).toBe("lengkap");
    expect(v.label).toBe("Persetujuan lengkap");
    expect(v.done).toBe(2);
    expect(v.canExecute).toBe(false);
  });

  it("ditolak menang atas hitungan peran", () => {
    const v = governanceView(
      dengan({
        approval_state: {
          satisfied: false,
          rejected: true,
          missing: [["sppg_head"], ["sppg_nutritionist"]],
          approved_roles: ["sppg_head"],
        },
      })
    );
    expect(v.state).toBe("ditolak");
    expect(v.label).toBe("Ditolak");
  });

  it("keputusan yang sudah dieksekusi berstatus selesai", () => {
    const v = governanceView(
      dengan({
        status: "executed",
        approval_state: {
          satisfied: true,
          rejected: false,
          missing: [],
          approved_roles: ["sppg_head", "sppg_nutritionist"],
        },
      })
    );
    expect(v.state).toBe("selesai");
    expect(v.label).toBe("Selesai");
  });
});

describe("governanceView — bentuk data", () => {
  it("grup gabungan (consistent) ditulis 'A atau B' dan selesai bila salah satu setuju", () => {
    const v = governanceView({
      approval_requirement: {
        verdict: "consistent",
        min_approvals: 1,
        required_roles: [["sppg_head", "sppg_nutritionist"]],
      },
      approval_state: {
        satisfied: true,
        rejected: false,
        missing: [],
        approved_roles: ["sppg_nutritionist"],
      },
      can_approve: false,
      can_execute: true,
      blocking_reasons: [],
    });
    expect(v.total).toBe(1);
    expect(v.done).toBe(1);
    expect(v.groups[0].label).toBe("Kepala SPPG atau Ahli Gizi SPPG");
    expect(v.groups[0].done).toBe(true);
  });

  it("alasan tertahan diteruskan apa adanya (tidak dikarang ulang)", () => {
    const v = governanceView(duaPeran);
    expect(v.blocker).toEqual(["approval belum lengkap: 2 dari 2 role"]);
  });

  it("summary kosong tidak melempar dan tidak mengarang angka", () => {
    const v = governanceView(null);
    expect(v.state).toBe("menunggu");
    expect(v.done).toBe(0);
    expect(v.total).toBe(0);
    expect(v.groups).toEqual([]);
    expect(v.blocker).toEqual([]);
    expect(v.canApprove).toBe(false);
  });

  it("done tidak pernah negatif walau data server tidak konsisten", () => {
    const v = governanceView({
      approval_requirement: { required_roles: [["sppg_head"]] },
      approval_state: { missing: [["sppg_head"], ["sppg_nutritionist"]], satisfied: false },
    });
    expect(v.done).toBe(0);
    expect(v.total).toBe(1);
  });
});
