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
  auditTimeline,
  windowUsage,
  approvalRoute,
  attentionFlags,
  butuhTindakan,
  zonaShortcut,
  consequences,
  decisionHeadline,
  decisionMetrics,
  costFacts,
  decisionFacts,
  hiddenFactsLabel,
  nextStep,
  hasValue,
  splitFacts,
  defaultEvidenceId,
  dossierMeta,
  evidenceTally,
  safetyFacts,
  supplierFact,
  supplierNameOf,
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
  it("mengambil asal/tujuan, komoditas, iterasi dari summary kanonik", () => {
    const rows = decisionFacts(SUMMARY, new Date("2026-10-11T02:00:00Z"));
    expect(find(rows, "Rute").value).toBe("Cianjur → Jakarta");
    expect(find(rows, "Komoditas").value).toBe("telur");
    expect(find(rows, "Iterasi").value).toBe("3");
    expect(find(rows, "Menggantikan").value).toBe("0267f818");
    expect(find(rows, "Diusulkan oleh").value).toBe("Agen supervisor");
  });

  // F1 redesign (18 Okt 2026): "Jumlah" dan "Tenggat" pindah ke strip metrik
  // kepala halaman supaya angkanya tidak muncul dua kali. Lihat
  // _qa/rencana-decision-evidence-v3.md §4.2 dan tests/evidence-dedup.test.ts.
  it("tidak lagi memuat Jumlah/Tenggat (keduanya di strip metrik)", () => {
    const labels = decisionFacts(SUMMARY, new Date("2026-10-11T02:00:00Z")).map((r) => r.label);
    expect(labels).not.toContain("Jumlah");
    expect(labels).not.toContain("Tenggat");
  });

  it("tenggat tetap terbaca — sebagai metrik dari expiry bersarang", () => {
    const rows = decisionMetrics({}, SUMMARY, new Date("2026-10-11T02:30:00Z"));
    expect(find(rows, "Tenggat").value).toBe("Lewat 13 menit");
  });

  it("tenggat di root payload keputusan juga terbaca sebagai metrik", () => {
    const rows = decisionMetrics(
      { expires_at: "2026-10-11T05:00:00Z", quantity_kg: 600 },
      {},
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
    expect(find(rows, "Iterasi").value).toBe("1");
    expect(find(rows, "Menggantikan").value).toBe("—");
  });
});

describe("costFacts — biaya", () => {
  // 19 Okt 2026: kontrak berubah — kartu Biaya memuat ENAM komponen Safe
  // Delivered Cost, bukan dua. Dulu hanya purchase+logistics sehingga
  // total tidak bisa direkonsiliasi; komponen yang tidak dikirim backend
  // tampil "—" beserta alasannya (bukan disembunyikan).
  it("enam komponen SDC tampil; komponen yang tidak ada ditandai '—' + alasan", () => {
    const rows = costFacts(SUMMARY);
    expect(find(rows, "Harga beli").value).toBe("Rp15.720.000");
    expect(find(rows, "Logistik").value).toBe("Rp486.000");
    for (const label of ["Penanganan", "Potensi susut", "Risiko kesegaran", "Penalti keamanan"]) {
      expect(find(rows, label).value).toBe("—");
      expect(find(rows, label).hint).toMatch(/tidak ada di data keputusan ini/);
    }
    expect(find(rows, "Dasar hitung").value).toBe("seed demo — angka konsisten docs");
    // F1 redesign: total tetap tidak diulang di kartu (sudah ada di strip).
    expect(rows.map((r) => r.label)).not.toContain("Biaya aman terkirim");
  });

  it("tanpa cost_breakdown: '—' (bukan Rp0)", () => {
    const rows = costFacts({ safe_delivered_cost: null });
    expect(find(rows, "Harga beli").value).toBe("—");
    expect(find(rows, "Logistik").value).toBe("—");
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
    // Urutan komponen mengikuti kontrak SDC; "Rekonsiliasi rincian" muncul
    // karena baris lama hanya punya dua dari enam komponen.
    expect(labels).toEqual([
      "Harga beli",
      "Logistik",
      "Penanganan",
      "Potensi susut",
      "Risiko kesegaran",
      "Penalti keamanan",
      "Rekonsiliasi rincian",
      "Dasar hitung",
    ]);
  });

  it("rincian lengkap yang menjumlah ke total: tidak memunculkan baris rekonsiliasi", () => {
    const rows = costFacts({
      cost_breakdown: {
        purchase: "1000000", transport: "48600", handling: "150000",
        expected_loss: "20000", freshness_risk: "0", safety_penalty: "0",
        basis: "dihitung: kutipan pemasok Rp20.000/kg, linehaul 162 km",
      },
      safe_delivered_cost: "1218600",
    });
    expect(rows.map((r) => r.label)).not.toContain("Rekonsiliasi rincian");
    expect(find(rows, "Penalti keamanan").value).toBe("Rp0");
  });
});

describe("safetyFacts — keamanan & pemasok", () => {
  it("status terburuk, batch diperiksa, pemblokiran, verifikator, material, target", () => {
    const rows = safetyFacts(SUMMARY);
    expect(find(rows, "Status keamanan terburuk").value).toBe("Lolos");
    expect(find(rows, "Batch diperiksa").value).toBe("1");
    expect(find(rows, "Diblokir keamanan").value).toBe("Tidak");
    expect(find(rows, "Verifikator").value).toBe("tidak dapat dievaluasi · Agen verifikator");
    expect(find(rows, "Nomor material").value).toBe("MAT-TELUR");
    expect(find(rows, "Target eksekusi").value).toBe("Simulasi");
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
  it("syarat, izin, alasan tertahan, peran (hitungan ada di stepper)", () => {
    const rows = approvalFacts(SUMMARY);
    // F1 redesign: "1 dari 2" hanya di stepper; kartu ini tidak mengulangnya.
    expect(rows.map((r) => r.label)).not.toContain("Persetujuan");
    expect(find(rows, "Syarat persetujuan").value).toBe("2 dari 2");
    expect(find(rows, "Boleh disetujui").value).toBe("Belum");
    expect(find(rows, "Boleh dieksekusi").value).toBe("Belum");
    expect(find(rows, "Alasan tertahan").value).toBe(
      "Kuota SPPG Jakarta penuh minggu ini · Verifikator belum tersedia"
    );
    expect(find(rows, "Peran penyetuju").value).toBe("Kepala SPPG · Ahli Gizi SPPG");
  });

  it("tanpa kalimat syarat: ambang ditulis, verdict jadi petunjuk", () => {
    const rows = approvalFacts({
      approvals: [],
      approval_requirement: { verdict: "unavailable", min_approvals: 2 },
    });
    expect(find(rows, "Syarat persetujuan").value).toBe("minimal 2 persetujuan");
    expect(find(rows, "Syarat persetujuan").hint).toBe("aturan persetujuan: tidak dapat dievaluasi");
  });

  it("verdict ok tidak ditampilkan sebagai petunjuk (tidak ada yang tertahan)", () => {
    const rows = approvalFacts({ approvals: [], approval_requirement: { verdict: "ok", min_approvals: 1 } });
    expect(find(rows, "Syarat persetujuan").hint).toBeNull();
  });

  it("boleh disetujui/dieksekusi → 'Ya'", () => {
    const rows = approvalFacts({ can_approve: true, can_execute: true, approvals: [] });
    expect(find(rows, "Boleh disetujui").value).toBe("Ya");
    expect(find(rows, "Boleh dieksekusi").value).toBe("Ya");
    expect(rows.map((r) => r.label)).not.toContain("Persetujuan");
    expect(find(rows, "Alasan tertahan").value).toBe("—");
  });

  it("tanpa summary: '—' semua (bukan 'Tidak' yang menyesatkan)", () => {
    const rows = approvalFacts(null);
    expect(rows.map((r) => r.label)).not.toContain("Persetujuan");
    expect(find(rows, "Boleh disetujui").value).toBe("—");
    expect(find(rows, "Boleh dieksekusi").value).toBe("—");
  });

  it("aturan persetujuan dibaca manusia, nilai asing tetap apa adanya", () => {
    const rows = (verdict: string) =>
      approvalFacts({
        approvals: [],
        approval_requirement: { verdict, min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
      });
    expect(find(rows("unavailable"), "Syarat persetujuan").value).toBe("minimal 2 persetujuan");
    expect(find(rows("unavailable"), "Syarat persetujuan").hint).toBe("aturan persetujuan: tidak dapat dievaluasi");
    expect(find(rows("flagged"), "Syarat persetujuan").hint).toBe("aturan persetujuan: terindikasi");
    expect(find(rows("consistent"), "Syarat persetujuan").hint).toBe("aturan persetujuan: konsisten");
    expect(find(rows("ok"), "Syarat persetujuan").hint).toBe(null);
    expect(find(rows("aneh-sekali"), "Syarat persetujuan").hint).toBe("aturan persetujuan: aneh-sekali");
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

  it("utamakan yang MASIH BERLAKU, bukan yang paling lama lewat", () => {
    // Keadaan nyata 17 Okt: default lama memilih keputusan pending yang
    // kedaluwarsa 9 hari lalu (sortir tenggat menaik), lalu juri membuka
    // keputusan tanpa tombol Eksekusi. Yang masih hidup didahulukan.
    const NOW2 = new Date("2026-10-11T06:00:00Z");
    const list = [
      { decision_id: "d-mati", status: "pending_approval", expires_at: "2026-10-10T00:00:00Z", valid: false },
      { decision_id: "d-hidup-jauh", status: "pending_approval", expires_at: "2026-10-12T00:00:00Z", valid: true },
      { decision_id: "d-hidup-dekat", status: "verifier_flagged", expires_at: "2026-10-11T12:00:00Z", valid: true },
    ];
    expect(defaultEvidenceId(list, NOW2)).toBe("d-hidup-dekat");
  });

  it("kalau semua sudah lewat, tetap memilih yang butuh tindakan (tidak kosong)", () => {
    const NOW2 = new Date("2026-10-20T00:00:00Z");
    const list = [
      { decision_id: "d-mati-dekat", status: "pending_approval", expires_at: "2026-10-19T00:00:00Z", valid: false },
      { decision_id: "d-mati-lama", status: "pending_approval", expires_at: "2026-10-10T00:00:00Z", valid: false },
    ];
    expect(defaultEvidenceId(list, NOW2)).toBe("d-mati-lama");
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

describe("rincian yang belum ada datanya disembunyikan (progressive disclosure)", () => {
  it("hanya nilai \"—\" yang dianggap kosong; 0 / Rp0 / Tidak tetap terisi", () => {
    expect(hasValue({ label: "Logistik", value: "—" })).toBe(false);
    expect(hasValue({ label: "Jumlah", value: "0" })).toBe(true);
    expect(hasValue({ label: "Biaya", value: "Rp0" })).toBe(true);
    expect(hasValue({ label: "Dibekai", value: "Tidak" })).toBe(true);
  });

  it("baris \"—\" tetap kosong walau ada keterangan tambahan", () => {
    expect(hasValue({ label: "Catatan", value: "—", hint: "belum ada catatan" })).toBe(false);
  });

  it("splitFacts mengelompokkan tanpa mengubah urutan", () => {
    const rows = [
      { label: "Harga beli", value: "Rp14.022.000" },
      { label: "Logistik", value: "—" },
      { label: "Biaya aman terkirim", value: "Rp14.875.421" },
      { label: "Catatan", value: "—" },
    ];
    const { filled, empty } = splitFacts(rows);
    expect(filled.map((r) => r.label)).toEqual(["Harga beli", "Biaya aman terkirim"]);
    expect(empty.map((r) => r.label)).toEqual(["Logistik", "Catatan"]);
  });

  it("daftar tanpa baris kosong tidak menambah apa pun", () => {
    const { filled, empty } = splitFacts([{ label: "Jumlah", value: "492 kg" }]);
    expect(filled).toHaveLength(1);
    expect(empty).toHaveLength(0);
  });

  it("label ringkasan memakai bahasa manusia dan bentuk tunggal yang benar", () => {
    expect(hiddenFactsLabel(0)).toBe("");
    expect(hiddenFactsLabel(1)).toBe("1 rincian belum ada datanya");
    expect(hiddenFactsLabel(4)).toBe("4 rincian belum ada datanya");
  });
});

describe("langkah berikutnya: satu kalimat yang menjawab \"apa yang harus saya lakukan\"", () => {
  const dasar = { role: "sppg_head", status: "pending_approval", summary: SUMMARY };

  it("menunggu persetujuan: menyebut jumlah persetujuan dan yang menahan", () => {
    const hasil = nextStep({
      role: "sppg_head",
      status: "pending_approval",
      summary: { ...SUMMARY, can_execute: false, blocking_reasons: ["menunggu ahli gizi"], expiry: { valid: true } },
    });
    expect(hasil.text).toContain("Menunggu persetujuan (1 dari 2)");
    expect(hasil.text).toContain("menunggu ahli gizi");
    expect(hasil.tone).toBe("warn");
  });

  it("keputusan `proposed`: menyuruh mengajukan, bukan diam", () => {
    // Audit 18 Okt BLOCKER A1: dulu keputusan ini jatuh ke "Tidak ada tindakan
    // mendesak", padahal justru di sinilah satu-satunya langkah yang hilang.
    const hasil = nextStep({
      role: "sppg_head",
      status: "proposed",
      summary: { ...SUMMARY, can_execute: false, expiry: { valid: true } },
    });
    expect(hasil.text).toContain("belum diajukan");
    expect(hasil.text).toContain("ajukan untuk persetujuan");
    expect(hasil.tone).toBe("warn");
  });

  it("jendela berlaku lewat: dikatakan lewat, bukan disembunyikan", () => {
    const hasil = nextStep({ ...dasar, summary: { ...SUMMARY, expiry: { valid: false }, can_execute: false } });
    expect(hasil.text).toContain("sudah lewat");
    expect(hasil.tone).toBe("warn");
  });

  it("semua syarat terpenuhi: siap dieksekusi", () => {
    const hasil = nextStep({ ...dasar, summary: { ...SUMMARY, can_execute: true, expiry: { valid: true } } });
    expect(hasil.text).toContain("siap dieksekusi");
    expect(hasil.tone).toBe("ok");
  });

  it("ditolak: menjelaskan agent bisa mengajukan iterasi baru", () => {
    const hasil = nextStep({ ...dasar, status: "rejected", summary: { ...SUMMARY, expiry: { valid: true } } });
    expect(hasil.text).toContain("ditolak");
    expect(hasil.tone).toBe("danger");
  });

  it("peran pengawas: tidak dijanjikan tombol yang tidak ada (paritas dengan DecisionActions)", () => {
    const hasil = nextStep({ role: "bgn_monitor", status: "pending_approval", summary: SUMMARY });
    expect(hasil.tone).toBe("muted");
    expect(hasil.text.toLowerCase()).toContain("pengawasan");
    const approver = nextStep({ role: "sppg_nutritionist", status: "pending_approval", summary: { ...SUMMARY, expiry: { valid: true } } });
    expect(approver.tone).not.toBe("muted");
  });

  it("daftar penahan dipangkas supaya kalimatnya tetap terbaca", () => {
    const hasil = nextStep({
      role: "sppg_head",
      status: "pending_approval",
      summary: {
        ...SUMMARY,
        expiry: { valid: true },
        blocking_reasons: ["alasan satu", "alasan dua", "alasan tiga", "alasan empat"],
      },
    });
    expect(hasil.text).toContain("alasan satu · alasan dua");
    expect(hasil.text).toContain("(+2 lain)");
    expect(hasil.text).not.toContain("alasan tiga");
  });
  it("tanpa ringkasan (data belum tiba): tidak mengarang, tetap satu kalimat", () => {
    const hasil = nextStep({ role: "sppg_head", status: "pending_approval", summary: null });
    expect(hasil.text.length).toBeGreaterThan(10);
    expect(hasil.text).not.toContain("undefined");
  });
});

// ── Desain baru halaman bukti (17 Okt 2026) ────────────────────────────────
// Struktur "catatan keputusan": apa yang diminta → seberapa besar → siapa
// memegang → saya harus apa → bukti. Riset: _qa/rencana-decision-evidence-v2.md.
describe("kepala keputusan: satu kalimat aksi + angka kunci", () => {
  it("judul menyebut aksi, jumlah, komoditas, dan rute", () => {
    expect(decisionHeadline({ decision_type: "regional_balance", quantity_kg: 600 }, SUMMARY)).toBe(
      "Alihkan 600 kg telur: Cianjur → Jakarta"
    );
  });

  it("tanpa nama lokasi: rute tidak dikarang, sisanya tetap", () => {
    const hasil = decisionHeadline({ decision_type: "regional_balance", quantity_kg: 600 }, { commodity: "telur" });
    expect(hasil).toBe("Alihkan 600 kg telur");
    expect(hasil).not.toContain("→");
    expect(hasil).not.toContain("null");
  });

  it("jenis tak dikenal memakai kata manusia dari peta yang ada, bukan istilah mentah", () => {
    const hasil = decisionHeadline({ decision_type: "regional_balance" }, { quantity_kg: 1, commodity: "beras" });
    expect(hasil.startsWith("Alihkan")).toBe(true);
    const asing = decisionHeadline({ decision_type: "sesuatu_baru" }, {});
    expect(asing).not.toContain("_");
  });

  it("metrik kunci: kuantitas, biaya aman, selisih — hanya yang benar-benar ada", () => {
    const rows = decisionMetrics({ quantity_kg: 600 }, SUMMARY);
    const pick = (label: string) => rows.find((r) => r.label === label)?.value;
    expect(pick("Kuantitas")).toBe("600 kg");
    expect(pick("Biaya aman terkirim")).toBe("Rp16.206.000");
    expect(pick("Selisih dari harga beli")).toBe("+Rp486.000");
    expect(decisionMetrics({}, {})).toEqual([]);
  });
});

describe("flag triase: yang perlu diperhatikan, bersumber data", () => {
  it("jendela lewat + belum diverifikasi muncul sebagai flag", () => {
    const flags = attentionFlags({
      decision: { status: "pending_approval" },
      summary: { ...SUMMARY, verifier: { verdict: null, verified_by: null } },
    });
    const ids = flags.map((f) => f.id);
    expect(ids).toContain("expiry");
    expect(ids).toContain("verifier");
    expect(flags.every((f) => f.text.length > 10)).toBe(true);
  });

  it("safety diblokir memakai alasan dari server, bukan karangan UI", () => {
    const flags = attentionFlags({
      decision: { status: "pending_approval" },
      summary: {
        ...SUMMARY,
        safety: { worst_status: "fail", blocked: true, reason: "safety revalidation gagal: batch sumber kini FAIL" },
      },
    });
    const safety = flags.find((f) => f.id === "safety");
    expect(safety?.tone).toBe("danger");
    expect(safety?.text).toContain("batch sumber kini FAIL");
  });

  it("keputusan sehat tidak menandai apa pun (tidak ada alarm palsu)", () => {
    const flags = attentionFlags({
      decision: { status: "pending_approval" },
      summary: {
        ...SUMMARY,
        expiry: { valid: true, expires_at: "2026-10-25T06:59:00+00:00" },
        verifier: { verdict: "flagged", verified_by: "verifier_agent" },
        safety: { worst_status: "pass", blocked: false },
      },
    });
    expect(flags).toEqual([]);
  });
});

describe("jalur persetujuan: siapa memegang, siapa berikutnya", () => {
  const ringkas = {
    ...SUMMARY,
    approval_requirement: { verdict: "flagged", min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
    approval_state: { satisfied: false, rejected: false, missing: [["sppg_nutritionist"]], approved_roles: ["sppg_head"] },
  };

  it("empat langkah tetap, urut, dengan keadaan dan rincian", () => {
    const steps = approvalRoute({ decision: { status: "pending_approval", created_at: "2026-10-07T23:47:00+07:00", proposed_by: "supervisor_agent" }, summary: ringkas, now: new Date(0) });
    expect(steps.map((s) => s.id)).toEqual(["proposed", "verify", "approve", "execute"]);
    expect(steps[0].state).toBe("done");
    expect(steps[0].detail).toContain("Agen supervisor");
    expect(steps[2].state).toBe("current");
    expect(steps[2].detail).toContain("1 dari 2");
    expect(steps[2].detail).toContain("Ahli Gizi SPPG");
    expect(steps[3].state).toBe("waiting");
  });

  it("sudah tidak ada yang kurang: langkah persetujuan selesai", () => {
    const steps = approvalRoute({
      decision: { status: "approved" },
      summary: { ...ringkas, approval_state: { satisfied: true, rejected: false, missing: [], approved_roles: ["sppg_head", "sppg_nutritionist"] } },
      now: null,
    });
    expect(steps[2].state).toBe("done");
    expect(steps[2].detail).toContain("2 dari 2");
  });

  it("ditolak: langkah persetujuan jadi terhalang, bukan diam-diam selesai", () => {
    const steps = approvalRoute({ decision: { status: "rejected" }, summary: ringkas, now: null });
    expect(steps[2].state).toBe("blocked");
  });
});

describe("konsekuensi: akibat tiap pilihan, dari data", () => {
  it("bisa dieksekusi di target MOCK: dikatakan bahwa tidak ada pesanan nyata", () => {
    const hasil = consequences({ decision: { status: "pending_approval" }, summary: { ...SUMMARY, can_execute: true } });
    expect(hasil.approve).toContain("simulasi (mock)");
    expect(hasil.approve).toContain("tidak ada pesanan nyata");
  });

  it("terhalang: sebabnya disebut dari blocking_reasons, dipangkas", () => {
    const hasil = consequences({
      decision: { status: "pending_approval" },
      summary: { ...SUMMARY, can_execute: false, blocking_reasons: ["a satu", "b dua", "c tiga", "d empat"] },
    });
    expect(hasil.approve).toContain("a satu · b dua");
    expect(hasil.approve).toContain("(+2 lain)");
    expect(hasil.approve).not.toContain("c tiga");
  });

  it("ditolak: agent bisa mengajukan iterasi berikutnya", () => {
    const hasil = consequences({ decision: { status: "rejected", iteration: 3 }, summary: SUMMARY });
    expect(hasil.reject.toLowerCase()).toContain("ditola");
    const belum = consequences({ decision: { status: "pending_approval", iteration: 3 }, summary: SUMMARY });
    expect(belum.reject).toContain("v4");
  });
});

// ── Langkah 2 (17 Okt 2026): lini masa audit + umur jendela ───────────────
describe("lini masa audit: siapa, kapan, versi mana", () => {
  const CHAIN = [
    { decision_id: "v1", iteration: 1, status: "rejected", rejection_reason: "Kuota penuh", created_at: "2026-10-07T13:47:00+07:00" },
    { decision_id: "v2", iteration: 2, status: "rejected", rejection_reason: "Harga belum turun", created_at: "2026-10-08T08:10:00+07:00" },
  ];
  const SEKARANG = {
    decision_id: "v3",
    decision_type: "regional_balance",
    status: "pending_approval",
    iteration: 3,
    proposed_by: "supervisor_agent",
    created_at: "2026-10-09T09:00:00+07:00",
    rejection_reason: null,
  };
  const RINGKAS = {
    ...SUMMARY,
    verifier: { verdict: "flagged", verified_by: "verifier_agent" },
    approvals: [
      { role: "sppg_head", approved: true, comment: "Setuju, satu kali", approved_at: "2026-10-09T10:15:00+07:00" },
    ],
  };

  it("urutannya bercerita: iterasi lama → diajukan → verifikasi → keputusan orang", () => {
    const events = auditTimeline({ decision: SEKARANG, summary: RINGKAS, chain: CHAIN });
    expect(events.map((e) => e.title)).toEqual([
      "v1 diajukan",
      "v2 diajukan",
      "v3 diajukan",
      "Diverifikasi",
      "Disetujui",
    ]);
    expect(events[0].detail).toContain("Kuota penuh");
    expect(events[0].tone).toBe("danger");
    expect(events[2].actor).toBe("Agen supervisor");
    // Peran diterjemahkan ke bahasa manusia, bukan enum backend.
    expect(events[4].actor).toBe("Kepala SPPG");
    expect(events[4].detail).toContain("Setuju, satu kali");
  });

  it("waktu yang tidak ada ditulis null, bukan dikarang", () => {
    const events = auditTimeline({ decision: SEKARANG, summary: RINGKAS, chain: CHAIN });
    const verifikasi = events.find((e) => e.title === "Diverifikasi");
    expect(verifikasi?.at).toBeNull();
    expect(verifikasi?.actor).toBe("Agen verifikator");
    expect(verifikasi?.detail).toContain("terindikasi");
  });

  it("penolakan tanpa baris approval tetap tercatat dengan alasan", () => {
    const events = auditTimeline({
      decision: { ...SEKARANG, status: "rejected", rejection_reason: "Stok gudang belum siap" },
      summary: { ...RINGKAS, approvals: [] },
      chain: CHAIN,
    });
    const tolak = events.find((e) => e.title === "Ditolak");
    expect(tolak?.detail).toBe("Stok gudang belum siap");
    expect(tolak?.tone).toBe("danger");
  });

  it("tanpa riwayat keluarga: hanya jejak keputusan ini", () => {
    const events = auditTimeline({ decision: SEKARANG, summary: RINGKAS, chain: [] });
    expect(events.map((e) => e.title)).toEqual(["v3 diajukan", "Diverifikasi", "Disetujui"]);
  });
});

describe("auditTimeline — detail verifier tidak mengulang putusan", () => {
  it("catatan yang cuma salinan verdict mentah tidak diulang", () => {
    const events = auditTimeline({
      decision: { decision_id: "x", status: "verified", verified_by: "verifier_agent" },
      summary: { verifier: { verdict: "consistent", verified_by: "verifier_agent" } },
      chain: [],
    });
    const verifikasi = events.find((e) => e.id === "verifikasi");
    expect(verifikasi?.detail).toBe("konsisten");
  });

  it("catatan yang benar-benar berbeda tetap ditampilkan", () => {
    const events = auditTimeline({
      decision: {
        decision_id: "x",
        status: "verified",
        verified_by: "verifier_agent",
        verifier_note: "foto batch cocok",
      },
      summary: { verifier: { verdict: "consistent", verified_by: "verifier_agent" } },
      chain: [],
    });
    const verifikasi = events.find((e) => e.id === "verifikasi");
    expect(verifikasi?.detail).toBe("konsisten · foto batch cocok");
  });
});

describe("umur jendela berlaku: dipakai apa adanya, tanpa ambang karangan", () => {
  it("menghitung persen jendela yang sudah terpakai", () => {
    const hasil = windowUsage({
      created_at: "2026-10-07T00:00:00Z",
      expires_at: "2026-10-11T00:00:00Z",
      now: new Date("2026-10-09T12:00:00Z"),
    });
    expect(hasil.persen).toBe(63);
    expect(hasil.state).toBe("aman");
    expect(hasil.label).toBe("Jendela terpakai 63%");
  });

  it("jendela lewat: dikatakan lewat dan penuh, bukan menebak sisa", () => {
    const hasil = windowUsage({
      created_at: "2026-10-07T00:00:00Z",
      expires_at: "2026-10-11T00:00:00Z",
      now: new Date("2026-10-12T00:00:00Z"),
    });
    expect(hasil.state).toBe("lewat");
    expect(hasil.persen).toBe(100);
  });

  it("jam klien belum siap / tanggal tak terbaca: jujur tidak tahu", () => {
    expect(windowUsage({ created_at: "2026-10-07T00:00:00Z", expires_at: "2026-10-11T00:00:00Z", now: null }).state).toBe("tidak diketahui");
    expect(windowUsage({ created_at: null, expires_at: null, now: new Date(0) }).state).toBe("tidak diketahui");
  });
});

describe("nextStep — temuan review_only (audit M6)", () => {
  it("temuan tidak menyuruh eksekusi dan tidak bicara jendela kedaluwarsa", () => {
    const hasil = nextStep({
      role: "sppg_head",
      status: "review_only",
      summary: {
        status: "review_only",
        can_execute: false,
        expiry: { valid: false },
        blocking_reasons: ["decision tinjauan (review-only) — tidak untuk dieksekusi"],
      },
    });
    expect(hasil.text).toContain("Temuan tinjauan");
    expect(hasil.text).not.toContain("Jendela berlaku");
    expect(hasil.tone).toBe("plain");
  });
});

// --- pengadaan pemasok (19 Okt 2026) ---------------------------------------
// Keputusan pengadaan punya source_location_id NULL (barang datang dari
// pemasok, bukan dari stok SPPG lain). Sebelum diperbaiki, barisnya berbunyi
// "Rute —" dan judulnya kehilangan asal — terbaca seperti data rusak.

const PENGADAAN = {
  decision_type: "supplier_procurement",
  source_location: null,
  target_location: "Jakarta",
  commodity: "telur",
  quantity_kg: 779.86,
  iteration: 1,
  supplier: { id: "036f2597-83e8-4985-81c2-47626a8a1395", name: "Telur Berkah Bekasi" },
};

describe("decisionFacts — pengadaan pemasok", () => {
  it("menampilkan pemasok sebagai asal, bukan Rute kosong", () => {
    const rows = decisionFacts(PENGADAAN, new Date("2026-10-19T14:41:00Z"));
    expect(rows.map((r) => r.label)).not.toContain("Rute");
    const baris = rows.find((r) => r.label === "Pemasok → SPPG");
    expect(baris?.value).toBe("Telur Berkah Bekasi → Jakarta");
  });

  it("judul menyebut pemasok, bukan kota tujuan sebagai asal", () => {
    const judul = decisionHeadline(PENGADAAN, null);
    expect(judul).toContain("Adakan dari pemasok");
    expect(judul).toContain("Telur Berkah Bekasi → Jakarta");
  });

  it("tanpa nama pemasok tetap jujur (—), bukan ditebak dari lokasi", () => {
    const rows = decisionFacts({ ...PENGADAAN, supplier: null }, null);
    const baris = rows.find((r) => r.label === "Pemasok → SPPG");
    expect(baris?.value).toBe("—");
  });

  it("supplierNameOf menerima objek maupun string", () => {
    expect(supplierNameOf({ supplier: { name: "Telur Berkah Bekasi" } })).toBe(
      "Telur Berkah Bekasi"
    );
    expect(supplierNameOf({ supplier: "UD Beras Rancaekek" })).toBe("UD Beras Rancaekek");
    expect(supplierNameOf({})).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Pintasan "Ke zona keputusan" (permintaan pemilik, 20 Okt 2026):
//   1) hanya muncul kalau memang ADA yang harus disetujui — bukan setiap kali
//      zona tergulir, dan bukan untuk peran pengawas;
//   2) arah panahnya jujur: zona masih di bawah → turun (↓); zona sudah
//      dilewati → panah dibalik, ajakan kembali (↑).
// Keduanya logika murni supaya bisa diuji tanpa DOM.
describe("pintasan 'Ke zona keputusan' — hanya saat persetujuan memang tertunda", () => {
  const ringkas = (ubah: Record<string, unknown> = {}) => ({
    status: "pending_approval",
    can_approve: true,
    can_reject: true,
    approvals: [{ approver_role: "sppg_head" }],
    approval_requirement: { min_approvals: 2, roles: ["sppg_head", "sppg_nutritionist"] },
    ...ubah,
  });

  it("muncul untuk Kepala SPPG & Ahli Gizi saat kuorum belum penuh", () => {
    expect(
      butuhTindakan({ role: "sppg_head", status: "pending_approval", summary: ringkas() })
    ).toBe(true);
    expect(
      butuhTindakan({ role: "sppg_nutritionist", status: "verifier_flagged", summary: ringkas() })
    ).toBe(true);
  });

  it("tidak muncul untuk peran pengawasan", () => {
    expect(
      butuhTindakan({ role: "bgn_monitor", status: "pending_approval", summary: ringkas() })
    ).toBe(false);
    expect(butuhTindakan({ role: "", status: "pending_approval", summary: ringkas() })).toBe(false);
  });

  it("tidak muncul saat kuorum sudah penuh atau keputusan sudah selesai", () => {
    const penuh = ringkas({ approvals: [{}, {}] });
    expect(butuhTindakan({ role: "sppg_head", status: "pending_approval", summary: penuh })).toBe(
      false
    );
    for (const status of ["approved", "executed", "rejected", "review_only", "expired"]) {
      expect(butuhTindakan({ role: "sppg_head", status, summary: ringkas() })).toBe(false);
    }
  });

  it("tidak muncul sebelum ringkasan tiba atau saat gerbang aksi tertutup", () => {
    expect(butuhTindakan({ role: "sppg_head", status: "pending_approval", summary: null })).toBe(
      false
    );
    expect(
      butuhTindakan({
        role: "sppg_head",
        status: "pending_approval",
        summary: ringkas({ can_reject: false }),
      })
    ).toBe(false);
  });
});

describe("pintasan 'Ke zona keputusan' — panah mengikuti posisi zona", () => {
  it("zona masih di bawah lipatan: ajak turun", () => {
    expect(zonaShortcut("bawah")).toEqual({
      text: "Ke zona keputusan",
      arrow: "↓",
      label: "Pintasan ke zona keputusan",
    });
  });

  it("zona sudah dilewati: panah dibalik, ajak kembali", () => {
    expect(zonaShortcut("lewat")).toEqual({
      text: "Kembali ke zona keputusan",
      arrow: "↑",
      label: "Pintasan kembali ke zona keputusan",
    });
  });
});
