// Kontrak "bahasa" — menerjemahkan enum & kalimat backend ke bahasa penyetuju.
//
// Aturan utama: TIDAK mengarang. String yang tidak dikenal dikembalikan apa
// adanya; hanya padanan yang memang diketahui yang diterjemahkan. Ini penting
// karena `blocking_reasons` adalah teks bebas dari server: kalau kita menebak,
// penyetuju membaca sebab yang salah.
import { describe, expect, it } from "vitest";

import {
  agentLabel,
  blockingReasons,
  executionTargetLabel,
  humanizeBlocker,
  safetyLabel,
} from "../lib/bahasa";

describe("humanizeBlocker — sebab tertahan dari server", () => {
  it("memetakan kalimat yang benar-benar dikirim approval_summary.py", () => {
    expect(humanizeBlocker("decision expired")).toBe(
      "jendela berlaku keputusan sudah lewat"
    );
    expect(humanizeBlocker("decision belum terverifikasi")).toBe("keputusan belum diverifikasi");
    expect(humanizeBlocker("decision ditolak")).toBe("keputusan sudah ditolak");
    expect(humanizeBlocker("decision sudah dieksekusi")).toBe("keputusan sudah dieksekusi");
    expect(humanizeBlocker("approval belum memenuhi requirement (missing/rejected)")).toBe(
      "persetujuan belum lengkap — masih ada kelompok peran yang belum menyetujui"
    );
    expect(humanizeBlocker("safety revalidation gagal")).toBe("pemeriksaan ulang keamanan gagal");
    expect(humanizeBlocker("batch sumber FAIL")).toBe("batch sumber gagal pemeriksaan keamanan");
  });

  it("menerjemahkan status dinamis lewat kosakata status yang sama", () => {
    expect(humanizeBlocker("status verifier_flagged tidak dapat dieksekusi")).toBe(
      "status ditandai verifier tidak dapat dieksekusi"
    );
  });

  it("teks yang sudah berbahasa manusia dibiarkan", () => {
    expect(humanizeBlocker("tidak ada batch sumber")).toBe("tidak ada batch sumber");
    expect(humanizeBlocker("Kuota SPPG Jakarta penuh minggu ini")).toBe(
      "Kuota SPPG Jakarta penuh minggu ini"
    );
  });

  it("kalimat yang dibungkus pesan error tetap diterjemahkan, sisanya dipertahankan", () => {
    const pesan = humanizeBlocker("Gagal menyetujui: approval belum memenuhi requirement (missing/rejected)");
    expect(pesan).toContain("Gagal menyetujui:");
    expect(pesan).toContain("persetujuan belum lengkap");
    expect(pesan).not.toContain("requirement");
  });

  it("kosong / bukan teks → null (pemanggil yang memutuskan tampilannya)", () => {
    expect(humanizeBlocker(null)).toBeNull();
    expect(humanizeBlocker("")).toBeNull();
    expect(humanizeBlocker("   ")).toBeNull();
  });
});

describe("blockingReasons — daftar penghalang siap baca", () => {
  it("membaca blocking_reasons lalu menerjemahkan tiap barisnya", () => {
    const reasons = blockingReasons({
      blocking_reasons: ["decision expired", "approval belum memenuhi requirement (missing/rejected)"],
    });
    expect(reasons).toEqual([
      "jendela berlaku keputusan sudah lewat",
      "persetujuan belum lengkap — masih ada kelompok peran yang belum menyetujui",
    ]);
  });

  it("tidak ada daftar → daftar kosong, bukan baris palsu", () => {
    expect(blockingReasons({})).toEqual([]);
    expect(blockingReasons(null)).toEqual([]);
  });
});

describe("safetyLabel — status keamanan jadi kata", () => {
  it("PASS/FAIL/NEEDS_VERIFICATION", () => {
    expect(safetyLabel("PASS")).toBe("Lolos");
    expect(safetyLabel("pass")).toBe("Lolos");
    expect(safetyLabel("FAIL")).toBe("Gagal");
    expect(safetyLabel("NEEDS_VERIFICATION")).toBe("Perlu verifikasi");
  });

  it("nilai tak dikenal dikembalikan apa adanya", () => {
    expect(safetyLabel("QUARANTINE")).toBe("QUARANTINE");
    expect(safetyLabel(null)).toBeNull();
  });
});

describe("agentLabel — nama teknis agen", () => {
  it("agen yang dikenal diberi nama manusia", () => {
    expect(agentLabel("supervisor_agent")).toBe("Agen supervisor");
    expect(agentLabel("verifier_agent")).toBe("Agen verifikator");
  });

  it("nama lain dibiarkan (jangan mengarang agen yang tidak ada)", () => {
    expect(agentLabel("compliance_agent")).toBe("compliance_agent");
    expect(agentLabel(null)).toBeNull();
  });
});

describe("executionTargetLabel — target eksekusi", () => {
  it("MOCK adalah simulasi, dan dikatakan", () => {
    expect(executionTargetLabel("MOCK")).toBe("Simulasi (mock)");
    expect(executionTargetLabel("mock")).toBe("Simulasi (mock)");
  });

  it("LOCAL = tindakan administratif lokal tanpa PO", () => {
    expect(executionTargetLabel("LOCAL")).toBe("Lokal (tanpa PO)");
  });

  it("target lain dikembalikan apa adanya", () => {
    expect(executionTargetLabel("SAP")).toBe("SAP");
    expect(executionTargetLabel(null)).toBeNull();
  });
});
