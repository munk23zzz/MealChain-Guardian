// Kontrak tampilan modul persetujuan halaman "Decision & Evidence" —
// dokumen `02-approval-action.md` §7 (keputusan pemilik 28 Okt 2026).
//
// Yang dikunci di sini, semuanya murni (tanpa DOM):
//   1. §7.2 empat keadaan nyata + dua kegagalan yang HARUS dibedakan (§7.4):
//      ditolak (ada alasan manusia) vs kedaluwarsa (waktu habis);
//   2. §7.1 satu kepala yang menjawab tiga hal: apa menahan · siapa dibutuhkan ·
//      apa terjadi setelah ini;
//   3. §7.3 daftar penyetuju membawa NAMA dan JAM, bukan hanya "sudah/belum";
//   4. dua langkah terpisah (menyetujui vs menjalankan) dengan sebab saat
//      tertutup, dan langkah review PO sebagai bagian "menjalankan";
//   5. payload kosong TIDAK diartikan "boleh" — UI menyebut datanya belum ada.
import { describe, expect, it } from "vitest";

import {
  fasePersetujuan,
  langkahPersetujuan,
  ledgerPenyetuju,
  tigaJawaban,
} from "../lib/approval-panel";

const REQUIRED = [["sppg_head"], ["sppg_nutritionist"]];

function ringkas(over: Record<string, unknown> = {}) {
  return {
    decision_id: "d1",
    decision_type: "regional_balance",
    status: "pending_approval",
    approval_requirement: { min_approvals: 2, required_roles: REQUIRED },
    approval_state: {
      satisfied: false,
      missing: REQUIRED,
      approved_roles: [],
      rejected: false,
    },
    approvals: [],
    expiry: { valid: true, seconds_remaining: 900 },
    purchase_order: null,
    can_approve: false,
    can_execute: false,
    blocking_reasons: ["approval belum memenuhi requirement (missing/rejected)"],
    ...over,
  };
}

const HEAD_APPROVED = ringkas({
  approval_state: {
    satisfied: false,
    missing: [["sppg_nutritionist"]],
    approved_roles: ["sppg_head"],
    rejected: false,
  },
  approvals: [
    {
      role: "sppg_head",
      approved_by_name: "Budi Santoso",
      approved: true,
      approved_at: "2026-10-28T02:15:00+00:00",
      comment: null,
    },
  ],
  can_approve: true,
});

const PO_DRAFT = ringkas({
  status: "approved",
  approval_state: {
    satisfied: true,
    missing: [],
    approved_roles: ["sppg_head", "sppg_nutritionist"],
    rejected: false,
  },
  approvals: [
    {
      role: "sppg_head",
      approved_by_name: "Budi Santoso",
      approved: true,
      approved_at: "2026-10-28T02:15:00+00:00",
    },
    {
      role: "sppg_nutritionist",
      approved_by_name: "Rina Wati",
      approved: true,
      approved_at: "2026-10-28T02:41:00+00:00",
    },
  ],
  purchase_order: {
    po_number: "MC-ABC123DEF456",
    status: "draft",
    created_at: "2026-10-28T02:50:00+00:00",
  },
  blocking_reasons: ["purchase order MC-ABC123DEF456 menunggu review Kepala SPPG"],
});

describe("§7.2 fase keputusan persetujuan", () => {
  it("requirement belum lengkap", () => {
    const fase = fasePersetujuan({ summary: ringkas(), role: "sppg_nutritionist" });
    expect(fase.kode).toBe("belum_lengkap");
    expect(fase.nada).toBe("warning");
  });

  it("bisa disetujui oleh pembaca sekarang", () => {
    const fase = fasePersetujuan({ summary: HEAD_APPROVED, role: "sppg_nutritionist" });
    expect(fase.kode).toBe("bisa_setujui");
    expect(fase.nada).toBe("safe");
  });

  it("cukup approval, menunggu review PO — keadaan yang dulu hilang", () => {
    const fase = fasePersetujuan({ summary: PO_DRAFT, role: "sppg_head" });
    expect(fase.kode).toBe("menunggu_review_po");
    expect(fase.nada).toBe("warning");
    expect(fase.label.toLowerCase()).toContain("review po");
    // PO-nya disebut, supaya pembaca tahu dokumen mana yang ditunggu.
    expect(fase.sebab).toContain("MC-ABC123DEF456");
  });

  it("sudah dieksekusi", () => {
    const selesai = ringkas({
      status: "executed",
      approval_state: {
        satisfied: true,
        missing: [],
        approved_roles: ["sppg_head", "sppg_nutritionist"],
        rejected: false,
      },
      purchase_order: { po_number: "MC-ABC123DEF456", status: "submitted" },
      blocking_reasons: [],
    });
    expect(fasePersetujuan({ summary: selesai, role: "sppg_head" }).kode).toBe("selesai");
  });

  it("§7.4 penolakan dan kedaluwarsa TIDAK memakai nada yang sama", () => {
    const ditolak = fasePersetujuan({
      summary: ringkas({
        status: "rejected",
        approval_state: {
          satisfied: false,
          missing: REQUIRED,
          approved_roles: [],
          rejected: true,
        },
      }),
      role: "sppg_head",
    });
    const kedaluwarsa = fasePersetujuan({
      summary: ringkas({ expiry: { valid: false, seconds_remaining: 0 } }),
      role: "sppg_head",
    });
    expect(ditolak.kode).toBe("ditolak");
    expect(kedaluwarsa.kode).toBe("kedaluwarsa");
    expect(ditolak.nada).not.toBe(kedaluwarsa.nada);
    // Penolakan punya alasan manusia; kedaluwarsa tidak boleh mengaku punya.
    expect(ditolak.label.toLowerCase()).toContain("tolak");
    expect(kedaluwarsa.label.toLowerCase()).toContain("kedaluwarsa");
  });

  it("payload belum ada → tidak mengaku apa pun (§4.3)", () => {
    const fase = fasePersetujuan({ summary: null, role: "sppg_head" });
    expect(fase.kode).toBe("tidak_diketahui");
    expect(fase.label).toContain("Belum ada data approval");
  });
});

describe("§7.1 satu kepala yang menjawab tiga hal", () => {
  it("apa menahan · siapa dibutuhkan · apa setelah ini", () => {
    const jawab = tigaJawaban({
      summary: HEAD_APPROVED,
      role: "sppg_nutritionist",
      now: new Date("2026-10-28T03:00:00Z"),
    });
    // Apa yang menahan: kalimat server, sudah diterjemahkan.
    expect(jawab.menahan.join(" ")).toContain("persetujuan belum lengkap");
    // Siapa yang dibutuhkan: peran yang masih kurang, dengan progres dari server.
    expect(jawab.dibutuhkan).toContain("Ahli Gizi SPPG");
    expect(jawab.dibutuhkan).toContain("1 dari 2");
    // Apa yang terjadi setelah ini: dua gerbang, bukan satu.
    expect(jawab.setelah.toLowerCase()).toContain("po");
    expect(jawab.setelah.toLowerCase()).toContain("review");
  });

  it("tanpa penghalang, kalimatnya jujur (bukan daftar kosong)", () => {
    const jawab = tigaJawaban({ summary: PO_DRAFT, role: "sppg_head", now: null });
    // Satu-satunya yang menahan pada keadaan ini ADALAH review PO — bukan daftar
    // kosong, dan bukan pula penghalang lain yang tidak dilaporkan server.
    expect(jawab.menahan).toHaveLength(1);
    expect(jawab.menahan[0].toLowerCase()).toContain("review");
    expect(jawab.setelah).toContain("MC-ABC123DEF456");
  });
});

describe("§7.3 daftar penyetuju dengan nama dan jam", () => {
  it("menyebut nama orang dan jam approval-nya", () => {
    const baris = ledgerPenyetuju({ summary: PO_DRAFT, now: null });
    expect(baris).toHaveLength(2);
    const head = baris.find((b) => b.roles.includes("sppg_head"));
    expect(head?.done).toBe(true);
    expect(head?.nama).toBe("Budi Santoso");
    // 02.15 UTC = 09.15 WIB — jam datang dari `approved_at`, bukan dikarang.
    expect(head?.jam).toContain("09.15");
    const gizi = baris.find((b) => b.roles.includes("sppg_nutritionist"));
    expect(gizi?.nama).toBe("Rina Wati");
    expect(gizi?.jam).toContain("09.41");
  });

  it("peran yang belum menyetujui tidak diberi nama atau jam palsu", () => {
    const baris = ledgerPenyetuju({ summary: HEAD_APPROVED, now: null });
    const gizi = baris.find((b) => b.roles.includes("sppg_nutritionist"));
    expect(gizi?.done).toBe(false);
    expect(gizi?.nama).toBeNull();
    expect(gizi?.jam).toBeNull();
  });

  it("tanpa baris approvals, UI menyebut datanya belum dicatat", () => {
    const baris = ledgerPenyetuju({
      summary: ringkas({ approval_requirement: { required_roles: REQUIRED } }),
      now: null,
    });
    expect(baris.every((b) => b.done === false && b.nama === null)).toBe(true);
    expect(baris.some((b) => b.catatan !== null)).toBe(true);
  });
});

describe("dua langkah terpisah, dengan sebab saat tertutup", () => {
  it("menyetujui tertutup karena requirement belum lengkap", () => {
    const langkah = langkahPersetujuan({ summary: ringkas(), role: "sppg_nutritionist" });
    expect(langkah.menyetujui.tersedia).toBe(false);
    expect(langkah.menyetujui.alasan).toContain("persetujuan belum lengkap");
  });

  it("setelah approval lengkap: terbitkan PO tersedia, review belum", () => {
    const lengkap = ringkas({
      status: "approved",
      can_execute: true,
      blocking_reasons: [],
      approval_state: {
        satisfied: true,
        missing: [],
        approved_roles: ["sppg_head", "sppg_nutritionist"],
        rejected: false,
      },
    });
    const langkah = langkahPersetujuan({ summary: lengkap, role: "sppg_head" });
    expect(langkah.menyetujui.tersedia).toBe(false);
    expect(langkah.terbitkanPo.tersedia).toBe(true);
    expect(langkah.reviewPo.tersedia).toBe(false);
    expect(String(langkah.reviewPo.alasan).toLowerCase()).toContain("belum ada po");
  });

  it("PO draft: hanya Kepala SPPG yang bisa mereview, dengan sebab untuk yang lain", () => {
    const head = langkahPersetujuan({ summary: PO_DRAFT, role: "sppg_head" });
    expect(head.terbitkanPo.tersedia).toBe(false);
    expect(head.reviewPo.tersedia).toBe(true);
    expect(head.reviewPo.label).toContain("MC-ABC123DEF456");

    const gizi = langkahPersetujuan({ summary: PO_DRAFT, role: "sppg_nutritionist" });
    expect(gizi.reviewPo.tersedia).toBe(false);
    expect(String(gizi.reviewPo.alasan).toLowerCase()).toContain("kepala sppg");

    const monitor = langkahPersetujuan({ summary: PO_DRAFT, role: "bgn_monitor" });
    expect(monitor.reviewPo.tersedia).toBe(false);
    expect(String(monitor.reviewPo.alasan).toLowerCase()).toContain("memantau");
  });
});

// Keadaan kelima: semua peran syarat sudah menyetujui dan `can_execute` true,
// tetapi PO belum terbit. Dokumen 02 §7.2 tidak menyebutnya, aplikasi hidup
// memilikinya (keputusan ade9e486, 28 Okt 2026) — kepala modul tidak boleh
// menulis "Belum bisa disetujui" ketika ada pekerjaan yang menunggu.
describe("fasePersetujuan — sudah disetujui, PO belum terbit", () => {
  const SIAP = {
    status: "approved",
    can_approve: false,
    can_execute: true,
    blocking_reasons: [],
    purchase_order: null,
    approval_requirement: {
      min_approvals: 2,
      required_roles: [["sppg_head"], ["sppg_nutritionist"]],
    },
    approval_state: {
      satisfied: true,
      missing: [],
      approved_roles: ["sppg_head", "sppg_nutritionist"],
    },
    approvals: [
      { role: "sppg_head", approved: true, approved_by_name: "A", approved_at: "2026-10-28T00:10:00Z" },
      { role: "sppg_nutritionist", approved: true, approved_by_name: "B", approved_at: "2026-10-28T00:20:00Z" },
    ],
    expiry: { valid: true },
  };

  it("mengaku siap menerbitkan PO draft, bukan 'belum bisa disetujui'", () => {
    const fase = fasePersetujuan({ summary: SIAP, role: "sppg_head" });
    expect(fase.kode).toBe("siap_eksekusi");
    expect(fase.label.toLowerCase()).toContain("po draft");
    expect(fase.label.toLowerCase()).not.toContain("belum bisa");
    expect(fase.nada).toBe("safe");
    expect(fase.sebab.toLowerCase()).toContain("review");
  });

  it("tiga jawaban tetap mengarah ke dua gerbang", () => {
    const jawab = tigaJawaban({ summary: SIAP, role: "sppg_head", now: null });
    expect(jawab.dibutuhkan.toLowerCase()).toContain("tidak ada peran yang kurang");
    expect(jawab.setelah.toLowerCase()).toContain("po draft");
    expect(jawab.setelah.toLowerCase()).toContain("review");
    expect(jawab.menahan).toEqual([]);
  });

  it("langkah eksekusi terbuka, review PO belum", () => {
    const langkah = langkahPersetujuan({ summary: SIAP, role: "sppg_head" });
    expect(langkah.terbitkanPo.tersedia).toBe(true);
    expect(langkah.reviewPo.tersedia).toBe(false);
    expect(langkah.menyetujui.tersedia).toBe(false);
  });
});

// Dokumen 02 §7.5: pengawas (bgn_monitor) melihat SEMUA, tetapi tidak punya
// giliran. Sebelum 28 Okt 2026 read model bahkan menjawab `can_approve: true`
// untuk peran ini; panel lalu menulis "Bisa Anda setujui sekarang" kepada orang
// yang tidak boleh menyetujui.
describe("peran pengawas — hanya-baca, bukan 'bisa Anda setujui'", () => {
  const MENUNGGU = {
    status: "pending_approval",
    can_approve: false,
    can_execute: false,
    blocking_reasons: ["approval belum lengkap"],
    approval_requirement: { min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
    approval_state: {
      satisfied: false,
      missing: [["sppg_head"], ["sppg_nutritionist"]],
      approved_roles: [],
    },
    approvals: [],
    expiry: { valid: true },
  };

  it("fase membaca 'hanya-baca', bukan tawaran menyetujui", () => {
    const fase = fasePersetujuan({ summary: MENUNGGU, role: "bgn_monitor" });
    expect(fase.kode).toBe("hanya_baca");
    expect(fase.label.toLowerCase()).toContain("hanya-baca");
    expect(fase.sebab.toLowerCase()).toContain("memantau");
  });

  it("tidak ada langkah yang 'tersedia', dan alasannya soal peran", () => {
    const l = langkahPersetujuan({ summary: MENUNGGU, role: "bgn_monitor" });
    expect(l.menyetujui.tersedia).toBe(false);
    expect(l.terbitkanPo.tersedia).toBe(false);
    expect(l.reviewPo.tersedia).toBe(false);
    for (const s of [l.menyetujui, l.terbitkanPo, l.reviewPo]) {
      expect(String(s.alasan).toLowerCase()).toContain("memantau");
    }
  });

  it("penyetuju tetap mendapat fasenya sendiri", () => {
    const fase = fasePersetujuan({ summary: MENUNGGU, role: "sppg_nutritionist" });
    expect(fase.kode).not.toBe("hanya_baca");
  });
});
