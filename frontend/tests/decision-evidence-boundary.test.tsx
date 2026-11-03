// Batas domain Fase 6 — kontrak tampilan keputusan.
//
// Tiga hal yang dijaga di sini, semuanya tentang KEJUJURAN layar:
//
//   1. Kandidat yang tertahan gate TIDAK boleh hilang dari layar (dulu
//      `generate_candidates` menyaringnya tanpa jejak sehingga penyetuju
//      membaca "tidak ada usulan" tanpa sebab). Ia tampil dengan alasan yang
//      sudah diterjemahkan, lapisan hierarki, langkah berikutnya, dan TANPA
//      tombol "Ajukan" — karena kandidat tertahan bukan usulan.
//   2. Kode alasan diterjemahkan di SATU kamus (`lib/bahasa`). Kode yang tidak
//      dikenal dikembalikan apa adanya: menebak artinya lebih buruk daripada
//      menampilkan kode mentah.
//   3. Review bukti manusia hanya boleh dikirim bila peran berwenang, batch
//      dipilih, alasan cukup panjang, dan ada rujukan bukti — aturan yang sama
//      dengan yang menolak 422 di server (`lib/review-gate`).

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import HeldCandidates from "../components/HeldCandidates";
import KPIDashboard from "../components/KPIDashboard";
import RoleHero from "../components/RoleHero";
import { humanizeBlocker } from "../lib/bahasa";
import { REASON_MIN, reviewReadiness } from "../lib/review-gate";

const HELD = {
  source_location: "Bandung",
  destination_location: "Jakarta",
  commodity: "telur",
  quantity_kg: "120",
  status: "on_hold",
  blocking_reasons: ["temperature_evidence_incomplete", "safety_needs_verification"],
  next_step: "lengkapi bukti suhu lalu selesaikan verifikasi",
  layer: 1,
  layer_name: "keselamatan/bukti",
  batch_ids: ["b-1"],
  is_candidate: false,
};

describe("kandidat ditahan — tampil apa adanya", () => {
  it("menyebut alasan, lapisan, dan langkah berikutnya", () => {
    const html = renderToStaticMarkup(<HeldCandidates held={[HELD]} />);
    expect(html).toContain("Kandidat ditahan (1)");
    expect(html).toContain("Bandung");
    expect(html).toContain("bukti suhu belum lengkap");
    expect(html).toContain("batch menunggu verifikasi");
    expect(html).toContain("keselamatan/bukti");
    expect(html).toContain("lengkapi bukti suhu lalu selesaikan verifikasi");
  });

  it("tidak pernah menawarkan pengajuan untuk kandidat tertahan", () => {
    const html = renderToStaticMarkup(<HeldCandidates held={[HELD]} />);
    expect(html).not.toMatch(/<button/i);
    expect(html).not.toContain("Ajukan");
  });

  it("kilogram yang tertahan diberi label fisik, bukan tersedia", () => {
    const html = renderToStaticMarkup(<HeldCandidates held={[HELD]} />);
    expect(html).toContain("Fisik tertahan");
    expect(html).not.toContain("Tersedia");
  });

  it("kosong berarti tidak merender apa pun (tanpa kotak hantu)", () => {
    expect(renderToStaticMarkup(<HeldCandidates held={[]} />)).toBe("");
    expect(renderToStaticMarkup(<HeldCandidates held={null} />)).toBe("");
  });
});

describe("kamus alasan — satu tempat, tanpa tebakan", () => {
  const kode = [
    "temperature_evidence_incomplete",
    "evidence_missing",
    "safety_fail",
    "safety_pending",
    "safety_needs_verification",
    "safety_status_unknown",
    "freshness_fail",
    "batch_expired",
    "expiry_unknown",
    "expired_before_arrival",
    "delivery_window_exceeded",
    "quarantined",
  ];

  it("setiap kode gerbang punya padanan bahasa Indonesia", () => {
    for (const k of kode) {
      const hasil = humanizeBlocker(k);
      expect(hasil, k).toBeTruthy();
      expect(hasil, k).not.toBe(k);
      expect(hasil, k).not.toMatch(/_/);
    }
  });

  it("kode tak dikenal dibiarkan apa adanya", () => {
    expect(humanizeBlocker("kode_yang_belum_ada")).toBe("kode_yang_belum_ada");
  });
});

describe("review bukti — kesiapan kirim", () => {
  const dasar = {
    role: "sppg_head",
    batchId: "b-1",
    reason: "suhu ruang muat dicek ulang dengan termometer kalibrasi",
    evidenceRefs: ["BA-2026-10-27-01"],
  };

  it("lengkap → boleh kirim", () => {
    expect(reviewReadiness(dasar)).toEqual({ ok: true, blockers: [] });
  });

  it("tanpa alasan → ditahan", () => {
    const hasil = reviewReadiness({ ...dasar, reason: "  " });
    expect(hasil.ok).toBe(false);
    expect(hasil.blockers.join(" ")).toContain(`minimal ${REASON_MIN}`);
  });

  it("alasan terlalu pendek → ditahan (batas sama dengan server)", () => {
    const pendek = "a".repeat(REASON_MIN - 1);
    expect(reviewReadiness({ ...dasar, reason: pendek }).ok).toBe(false);
    expect(reviewReadiness({ ...dasar, reason: "a".repeat(REASON_MIN) }).ok).toBe(true);
  });

  it("tanpa rujukan bukti → ditahan", () => {
    const hasil = reviewReadiness({ ...dasar, evidenceRefs: ["", "  "] });
    expect(hasil.ok).toBe(false);
    expect(hasil.blockers.join(" ")).toContain("rujukan bukti");
  });

  it("peran pembaca tidak boleh meninjau", () => {
    const hasil = reviewReadiness({ ...dasar, role: "bgn_monitor" });
    expect(hasil.ok).toBe(false);
    expect(hasil.blockers.join(" ")).toContain("tidak berwenang");
  });

  it("tanpa batch terpilih → ditahan", () => {
    expect(reviewReadiness({ ...dasar, batchId: null }).ok).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Butir 6 — batas domain: bahan untuk rencana, bukan porsi yang sudah disajikan
// ---------------------------------------------------------------------------

/** Envelope KPI minimal: yang diuji adalah KALIMAT batas domain, bukan kartunya. */
const KPI_MIN = {
  metrics: [],
  data_mode: "operational",
  period: {},
  scope: {},
};

describe("batas domain pada dashboard", () => {
  it("menyatakan angka dihitung dari bahan rencana, bukan porsi tersaji", () => {
    const html = renderToStaticMarkup(<KPIDashboard kpi={KPI_MIN} />);
    const catatan = /data-testid="kpi-domain-note"[^>]*>([\s\S]*?)<\/p>/.exec(html);
    expect(catatan).not.toBeNull();
    const teks = catatan![1].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
    // Klaim intinya tetap ada, tetapi dalam SATU baris (bukan paragraf teknis
    // yang dulu memakan tiga baris di atas semua kartu).
    expect(teks).toContain("bahan rencana");
    expect(teks).toContain("bukan porsi tersaji");
    // Nama enum internal tidak boleh kembali ke layar.
    expect(teks).not.toContain("no_data");
    expect(teks.trim().split(/\s+/).length).toBeLessThan(20);
  });

  it("menampilkan batas yang sama pada cakupan simulasi (bukan hanya operasional)", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={{ ...KPI_MIN, data_mode: "demo" }} />,
    );
    expect(html).toContain('data-testid="kpi-domain-note"');
  });
});

// ---------------------------------------------------------------------------
// Butir 7 — peran: kepala & ahli gizi tidak mengaku memeriksa menu yang tak ada
// ---------------------------------------------------------------------------

describe("batas domain peran", () => {
  it("nutritionist menyatakan persetujuannya atas BAHAN, bukan validasi menu", () => {
    const html = renderToStaticMarkup(<RoleHero role="sppg_nutritionist" />);
    expect(html).toContain('data-testid="role-scope-note"');
    expect(html).toContain("bukan validasi menu");
    expect(html).toContain("fakta menu/porsi tidak ada");
    // Klaim lama yang menyesatkan tidak boleh kembali.
    expect(html).not.toContain("kecocokan gizi");
  });

  it("kepala SPPG menyatakan yang diputuskan adalah bahan (kg)", () => {
    const html = renderToStaticMarkup(<RoleHero role="sppg_head" />);
    expect(html).toContain('data-testid="role-scope-note"');
    expect(html).toContain("BAHAN (kg)");
    expect(html).toContain("tidak ada pemeriksaan menu");
  });

  it("BGN monitor tetap dinyatakan hanya-baca", () => {
    const html = renderToStaticMarkup(<RoleHero role="bgn_monitor" />);
    expect(html).toContain("hanya-baca");
    expect(html).toContain("tidak dapat mengubah apa pun");
  });
});
