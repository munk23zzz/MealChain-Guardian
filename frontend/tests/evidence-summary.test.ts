// Langkah 4 (permintaan Roy 2026-10-11): logika murni halaman
// "Decision & Evidence" — halaman tersendiri untuk bukti satu keputusan.
//
// Semua nilai diambil dari payload API yang sudah ada:
//   /decisions/{id}                 → identitas & biaya keputusan
//   /decisions/{id}/approval-summary → asal/tujuan, keamanan, pemasok, governance
//   /decisions/{id}/dossier          → alamat konten + tanda tangan + verifikasi
//   /decisions/{id}/compliance       → daftar bukti (evidence[])
//
// Aturan: nilai yang tidak ada ditulis "—" dan TIDAK dikarang/dinolkan.
import { describe, expect, it } from "vitest";

import {
  approvalFacts,
  costFacts,
  decisionFacts,
  defaultEvidenceId,
  dossierMeta,
  evidenceTally,
  safetyFacts,
  supplierFact,
} from "../lib/evidence";

const SUMMARY = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  iteration: 3,
  supersedes_id: "0267f818-f8f2-4e65-a299-f2627ad8ec71",
  proposed_by: "supervisor_agent",
  source_location: "Cianjur",
  target_location: "Jakarta",
  commodity: "telur",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  cost_breakdown: { note: "seed demo — angka konsisten docs", purchase: "15720000", logistics: "486000" },
  material_number: "MAT-TELUR",
  supplier: { id: "s1", name: "Supplier A Cianjur", reliability_score: 0.8 },
  execution_target: "MOCK",
  verifier: { verdict: "unavailable", verified_by: "verifier_agent" },
  safety: { worst_status: "pass", blocked: false, batches_checked: 1 },
  expiry: { expires_at: "2026-10-11T02:16:47.973521+00:00", valid: false, seconds_remaining: 0 },
  approval_requirement: { verdict: "unavailable", min_approvals: 2, requirement: "2 dari 2" },
  approval_state: "pending",
  approvals: [{ approver: "a1", role: "sppg_head" }],
  can_approve: false,
  can_execute: false,
  blocking_reasons: ["Kuota SPPG Jakarta penuh minggu ini", "Verifikator belum tersedia"],
  approver_roles: ["sppg_head", "sppg_nutritionist"],
};

function find(rows: { label: string }[], label: string) {
  const row = rows.find((r) => r.label === label);
  if (!row) throw new Error(`baris "${label}" tidak ada. Ada: ${rows.map((r) => r.label).join(" | ")}`);
  return row as any;
}

describe("evidenceTally — hitungan status bukti", () => {
  it("menghitung PASS/FAIL/NEEDS_VERIFICATION apa adanya", () => {
    const tally = evidenceTally([
      { id: "1", evidenceType: "human_inspection", status: "PASS" },
      { id: "2", evidenceType: "cold_chain", status: "FAIL" },
      { id: "3", evidenceType: "sensor", status: "NEEDS_VERIFICATION" },
      { id: "4", evidenceType: "sensor", status: "PASS" },
    ] as any);
    expect(tally).toEqual({ pass: 2, fail: 1, needsVerification: 1, total: 4 });
  });

  it("daftar kosong tetap nol yang jujur", () => {
    expect(evidenceTally([])).toEqual({ pass: 0, fail: 0, needsVerification: 0, total: 0 });
  });
});

describe("dossierMeta — alamat konten, tanda tangan, verifikasi", () => {
  it("dossier bertanda tangan & terverifikasi", () => {
    const meta = dossierMeta({
      content_address: "mc1-4hags0ksj5q0r87lha8wfohutmjpm96si9t10vs3chnmz42dh9",
      signature: { state: "signed", algorithm: "ECDSA-secp256k1" },
      verify: true,
    });
    expect(meta.contentAddress).toBe("mc1-4hags0ksj5q0r87lha8wfohutmjpm96si9t10vs3chnmz42dh9");
    expect(meta.signatureLabel).toBe("Tertanda (ECDSA-secp256k1)");
    expect(meta.verifyLabel).toBe("Terverifikasi");
    expect(meta.verifyOk).toBe(true);
    expect(meta.hasDossier).toBe(true);
  });

  it("belum ditandatangani: alasan backend ikut ditampilkan", () => {
    const meta = dossierMeta({
      content_address: "mc1-abc",
      signature: { state: "unsigned", reason: "SIGNING_KEY_HEX tidak diset (.env)" },
      verify: null,
    });
    expect(meta.signatureLabel).toBe("Belum ditandatangani");
    expect(meta.signatureReason).toBe("SIGNING_KEY_HEX tidak diset (.env)");
    expect(meta.verifyLabel).toBe("—");
    expect(meta.verifyOk).toBeNull();
  });

  it("tidak ada dossier sama sekali: semua '—'", () => {
    const meta = dossierMeta(null);
    expect(meta).toMatchObject({ contentAddress: "—", signatureLabel: "—", verifyLabel: "—", hasDossier: false });
  });

  it("verifikasi gagal dinyatakan gagal", () => {
    const meta = dossierMeta({ content_address: "mc1-x", signature: { state: "signed" }, verify: false });
    expect(meta.verifyLabel).toBe("Tidak terverifikasi");
    expect(meta.verifyOk).toBe(false);
  });
});

describe("decisionFacts — identitas keputusan", () => {
  it("mengambil asal/tujuan, komoditas, jumlah dari summary kanonik", () => {
    const rows = decisionFacts(SUMMARY, new Date("2026-10-11T02:00:00Z"));
    expect(find(rows, "Rute").value).toBe("Cianjur → Jakarta");
    expect(find(rows, "Komoditas").value).toBe("telur");
    expect(find(rows, "Jumlah").value).toBe("600 kg");
    expect(find(rows, "Iterasi").value).toBe("3");
    expect(find(rows, "Menggantikan").value).toBe("0267f818");
    expect(find(rows, "Diusulkan oleh").value).toBe("supervisor_agent");
  });

  it("tenggat ditulis sebagai sisa waktu manusiawi (dari expiry bersarang)", () => {
    // /approval-summary menaruh tenggat di `expiry.expires_at`; /decisions/{id}
    // menaruhnya di root. Keduanya harus terbaca.
    const rows = decisionFacts(SUMMARY, new Date("2026-10-11T02:30:00Z"));
    expect(find(rows, "Tenggat").value).toBe("Lewat 13 mnt");
  });

  it("tenggat di root payload keputusan juga terbaca", () => {
    const rows = decisionFacts(
      { expires_at: "2026-10-11T05:00:00Z", quantity_kg: 600 },
      new Date("2026-10-11T02:00:00Z")
    );
    expect(find(rows, "Tenggat").value).toBe("3 jam lagi");
  });

  it("summary belum ada: tetap terbaca dari payload keputusan, sisanya '—'", () => {
    const rows = decisionFacts(
      { decision_type: "price_anomaly", quantity_kg: 600, iteration: 1, proposed_by: "supervisor_agent" },
      new Date("2026-10-11T02:00:00Z")
    );
    expect(find(rows, "Rute").value).toBe("—");
    expect(find(rows, "Komoditas").value).toBe("—");
    expect(find(rows, "Jumlah").value).toBe("600 kg");
    expect(find(rows, "Tenggat").value).toBe("—");
    expect(find(rows, "Menggantikan").value).toBe("—");
  });
});

describe("costFacts — biaya", () => {
  it("harga beli, logistik, total aman terkirim, catatan", () => {
    const rows = costFacts(SUMMARY);
    expect(find(rows, "Harga beli").value).toBe("Rp15.720.000");
    expect(find(rows, "Logistik").value).toBe("Rp486.000");
    expect(find(rows, "Biaya aman terkirim").value).toBe("Rp16.206.000");
    expect(find(rows, "Catatan").value).toBe("seed demo — angka konsisten docs");
  });

  it("tanpa cost_breakdown: '—' (bukan Rp0)", () => {
    const rows = costFacts({ safe_delivered_cost: null });
    expect(find(rows, "Harga beli").value).toBe("—");
    expect(find(rows, "Logistik").value).toBe("—");
    expect(find(rows, "Biaya aman terkirim").value).toBe("—");
  });

  // Fase 7d: jarak pemasok masuk biaya → panel menampilkan pecahannya.
  it("pecahan angkut (pemasok → SPPG + antar SPPG) tampil dengan km dan label", () => {
    const rows = costFacts({
      cost_breakdown: {
        purchase: "13772500",
        logistics: "18471.85",
        transport_supplier_leg: "6653.07",
        transport_linehaul: "11818.78",
        supplier_leg_km: "45.075",
        supplier_leg_reference: "supplier_coordinates",
      },
      safe_delivered_cost: "14980976.71",
    });
    expect(find(rows, "Logistik").value).toBe("Rp18.472");
    expect(find(rows, "Angkut pemasok → SPPG").value).toBe("Rp6.653");
    expect(find(rows, "Angkut pemasok → SPPG").hint).toBe("45,075 km dari pemasok");
    expect(find(rows, "Angkut antar SPPG").value).toBe("Rp11.819");
  });

  it("koordinat pemasok kosong: biayanya 0 tetapi alasannya ditulis, bukan diklaim 0 km", () => {
    const rows = costFacts({
      cost_breakdown: {
        transport_supplier_leg: "0.00",
        transport_linehaul: "21600.00",
        supplier_leg_km: null,
        supplier_leg_reference: "supplier_coordinates_missing",
      },
    });
    expect(find(rows, "Angkut pemasok → SPPG").value).toBe("Rp0");
    expect(find(rows, "Angkut pemasok → SPPG").hint).toBe(
      "jarak tidak diketahui — koordinat pemasok kosong"
    );
  });

  it("keputusan lama tanpa pecahan: tidak ada baris angkut tambahan", () => {
    const labels = costFacts(SUMMARY).map((r) => r.label);
    expect(labels).not.toContain("Angkut pemasok → SPPG");
    expect(labels).not.toContain("Angkut antar SPPG");
    expect(labels).toEqual(["Harga beli", "Logistik", "Biaya aman terkirim", "Catatan"]);
  });
});

describe("safetyFacts — keamanan & pemasok", () => {
  it("status terburuk, batch diperiksa, pemblokiran, verifikator, material, target", () => {
    const rows = safetyFacts(SUMMARY);
    expect(find(rows, "Status keamanan terburuk").value).toBe("PASS");
    expect(find(rows, "Batch diperiksa").value).toBe("1");
    expect(find(rows, "Diblokir keamanan").value).toBe("Tidak");
    expect(find(rows, "Verifikator").value).toBe("unavailable · verifier_agent");
    expect(find(rows, "Nomor material").value).toBe("MAT-TELUR");
    expect(find(rows, "Target eksekusi").value).toBe("MOCK");
  });

  it("aman → nada ok; gagal/blokir → nada bahaya", () => {
    const rows = safetyFacts({ safety: { worst_status: "fail", blocked: true, batches_checked: 2 } });
    expect(find(rows, "Status keamanan terburuk").tone).toBe("danger");
    expect(find(rows, "Diblokir keamanan").value).toBe("Ya");
    expect(find(rows, "Diblokir keamanan").tone).toBe("danger");
  });

  it("tanpa blok safety: semua '—'", () => {
    const rows = safetyFacts({});
    expect(find(rows, "Status keamanan terburuk").value).toBe("—");
    expect(find(rows, "Status keamanan terburuk").tone).toBe("muted");
    expect(find(rows, "Batch diperiksa").value).toBe("—");
    expect(find(rows, "Diblokir keamanan").value).toBe("—");
  });

  it("pemasok: nama + skor keandalan sebagai persen", () => {
    const row = supplierFact(SUMMARY);
    expect(row.value).toBe("Supplier A Cianjur");
    expect(row.hint).toBe("keandalan 80%");
    expect(supplierFact({}).value).toBe("—");
    expect(supplierFact({}).hint).toBeNull();
  });
});

describe("approvalFacts — governance", () => {
  it("jumlah persetujuan, syarat, izin, alasan tertahan, peran", () => {
    const rows = approvalFacts(SUMMARY);
    expect(find(rows, "Persetujuan").value).toBe("1 dari 2");
    expect(find(rows, "Syarat persetujuan").value).toBe("2 dari 2");
    expect(find(rows, "Boleh disetujui").value).toBe("Belum");
    expect(find(rows, "Boleh dieksekusi").value).toBe("Belum");
    expect(find(rows, "Alasan tertahan").value).toBe(
      "Kuota SPPG Jakarta penuh minggu ini · Verifikator belum tersedia"
    );
    expect(find(rows, "Peran penyetuju").value).toBe("sppg_head · sppg_nutritionist");
  });

  it("tanpa kalimat syarat: ambang ditulis, verdict jadi petunjuk", () => {
    const rows = approvalFacts({
      approvals: [],
      approval_requirement: { verdict: "unavailable", min_approvals: 2 },
    });
    expect(find(rows, "Syarat persetujuan").value).toBe("minimal 2 persetujuan");
    expect(find(rows, "Syarat persetujuan").hint).toBe("putusan aturan: tidak dapat dievaluasi");
  });

  it("verdict ok tidak ditampilkan sebagai petunjuk (tidak ada yang tertahan)", () => {
    const rows = approvalFacts({ approvals: [], approval_requirement: { verdict: "ok", min_approvals: 1 } });
    expect(find(rows, "Syarat persetujuan").hint).toBeNull();
  });

  it("boleh disetujui/dieksekusi → 'Ya'", () => {
    const rows = approvalFacts({ can_approve: true, can_execute: true, approvals: [] });
    expect(find(rows, "Boleh disetujui").value).toBe("Ya");
    expect(find(rows, "Boleh dieksekusi").value).toBe("Ya");
    expect(find(rows, "Persetujuan").value).toBe("0 dari —");
    expect(find(rows, "Alasan tertahan").value).toBe("—");
  });

  it("tanpa summary: '—' semua (bukan 'Tidak' yang menyesatkan)", () => {
    const rows = approvalFacts(null);
    expect(find(rows, "Persetujuan").value).toBe("—");
    expect(find(rows, "Boleh disetujui").value).toBe("—");
    expect(find(rows, "Boleh dieksekusi").value).toBe("—");
  });

  it("putusan aturan dibaca manusia, nilai asing tetap apa adanya", () => {
    const rows = (verdict: string) =>
      approvalFacts({
        approvals: [],
        approval_requirement: { verdict, min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
      });
    expect(find(rows("unavailable"), "Syarat persetujuan").value).toBe("minimal 2 persetujuan");
    expect(find(rows("unavailable"), "Syarat persetujuan").hint).toBe("putusan aturan: tidak dapat dievaluasi");
    expect(find(rows("flagged"), "Syarat persetujuan").hint).toBe("putusan aturan: terindikasi");
    expect(find(rows("consistent"), "Syarat persetujuan").hint).toBe("putusan aturan: konsisten");
    expect(find(rows("ok"), "Syarat persetujuan").hint).toBe(null);
    expect(find(rows("aneh-sekali"), "Syarat persetujuan").hint).toBe("putusan aturan: aneh-sekali");
  });
});

describe("defaultEvidenceId — halaman bukti tidak boleh terbuka kosong", () => {
  it("utamakan keputusan yang menunggu persetujuan, paling dekat tenggat", () => {
    const list = [
      { decision_id: "d-proposed", status: "proposed", created_at: "2026-10-11T01:00:00Z" },
      { decision_id: "d-pending-lama", status: "pending_approval", expires_at: "2026-10-11T05:00:00Z" },
      { decision_id: "d-pending-dekat", status: "pending_approval", expires_at: "2026-10-11T03:00:00Z" },
    ];
    expect(defaultEvidenceId(list)).toBe("d-pending-dekat");
  });

  it("tanpa yang butuh tindakan: ambil yang paling baru", () => {
    const list = [
      { decision_id: "lama", status: "executed", created_at: "2026-10-10T01:00:00Z" },
      { decision_id: "baru", status: "executed", created_at: "2026-10-11T01:00:00Z" },
    ];
    expect(defaultEvidenceId(list)).toBe("baru");
  });

  it("daftar kosong / null → null (keadaan kosong tetap jujur)", () => {
    expect(defaultEvidenceId([])).toBe(null);
    expect(defaultEvidenceId(null)).toBe(null);
    expect(defaultEvidenceId([{ status: "proposed" } as any])).toBe(null);
  });
});
