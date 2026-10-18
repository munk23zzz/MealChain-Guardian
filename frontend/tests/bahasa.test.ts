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
  statusLabel,
  toolLabel,
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

  it("kode teknis di awal kalimat server tidak tampil mentah", () => {
    // 409 dari /supplier-eligibility: "supplier_unknown: keputusan lama ..."
    // tampil di kartu Lanjutkan pada Decision & Evidence.
    expect(humanizeBlocker("supplier_unknown: keputusan lama perlu binding batch eksplisit")).toBe(
      "pemasok tidak dikenal: keputusan lama perlu binding batch eksplisit"
    );
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
  it("PASS/FAIL/NEEDS_VERIFICATION/PENDING", () => {
    expect(safetyLabel("PASS")).toBe("Lolos");
    expect(safetyLabel("pass")).toBe("Lolos");
    expect(safetyLabel("FAIL")).toBe("Gagal");
    expect(safetyLabel("NEEDS_VERIFICATION")).toBe("Perlu verifikasi");
    // "pending" = belum diuji (bukan "gagal", bukan "aman"); dipakai kolom
    // "Mutu" di papan kiriman supaya enum mentah tidak tampil di layar.
    expect(safetyLabel("pending")).toBe("Belum diuji");
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
    expect(executionTargetLabel("MOCK")).toBe("Simulasi");
    expect(executionTargetLabel("mock")).toBe("Simulasi");
  });

  it("LOCAL = tindakan administratif lokal tanpa PO", () => {
    expect(executionTargetLabel("LOCAL")).toBe("Lokal (tanpa PO)");
  });

  it("target lain dikembalikan apa adanya", () => {
    expect(executionTargetLabel("SAP")).toBe("SAP");
    expect(executionTargetLabel(null)).toBeNull();
  });
});

// Lencana status dulu menampilkan enum mentah ("PENDING APPROVAL", 23 kali di
// feed Recommendation) di UI berbahasa Indonesia. Pemetaan tinggal di sini, dan
// StatusBadge memakainya — satu tempat, bukan peta kedua di komponen.
describe("statusLabel — lencana status ke bahasa Indonesia", () => {
  it("memetakan status yang benar-benar muncul di layar", () => {
    expect(statusLabel("PENDING_APPROVAL")).toBe("Menunggu persetujuan");
    expect(statusLabel("pending_approval")).toBe("Menunggu persetujuan");
    expect(statusLabel("VERIFIER_FLAGGED")).toBe("Ditandai verifikator");
    expect(statusLabel("NEEDS_VERIFICATION")).toBe("Perlu verifikasi");
    expect(statusLabel("PROPOSED")).toBe("Diusulkan");
    expect(statusLabel("APPROVED")).toBe("Disetujui");
    expect(statusLabel("REJECTED")).toBe("Ditolak");
    expect(statusLabel("EXECUTED")).toBe("Dieksekusi");
    expect(statusLabel("PASS")).toBe("Lolos");
    expect(statusLabel("FAIL")).toBe("Gagal");
  });

  it("status tak dikenal TIDAK diterjemahkan, hanya garis bawahnya dibuang", () => {
    expect(statusLabel("CUSTOM_STATE")).toBe("CUSTOM STATE");
    expect(statusLabel(null)).toBeNull();
    expect(statusLabel("  ")).toBeNull();
  });
});

// Nama alat internal ("supply_balance.propose") pernah tampil apa adanya di
// kartu kualitas agen. Yang dikenal diberi sebutan, yang tidak dikenal tetap
// tampil apa adanya (bukti, jangan disembunyikan).
describe("toolLabel — nama alat agen", () => {
  it("menerjemahkan alat yang dikenal", () => {
    expect(toolLabel("supply_balance.propose")).toBe("Neraca pasokan · usulkan");
    expect(toolLabel("rejection_loop.repropose")).toBe("Usulan ulang setelah penolakan");
    expect(toolLabel("demand.snapshot")).toBe("Potret permintaan");
    expect(toolLabel("logistics.reroute")).toBe("Alih rute kiriman");
    expect(toolLabel("POST /decisions")).toBe("Buat keputusan");
  });

  it("alat lain dibiarkan apa adanya", () => {
    expect(toolLabel("price_anomaly.detect")).toBe("price_anomaly.detect");
    expect(toolLabel(null)).toBeNull();
  });
});
