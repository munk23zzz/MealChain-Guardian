// Ops Console interaktif + hero per role (arah Roy 2026-10-07):
// user harus bisa berinteraksi SEBELUM hasil demo — pilih lokasi &
// komoditas, muat snapshot kondisi, jalankan analisis agent, lalu
// (role approver) mengajukan usulan ke feed untuk approve/reject.
// Render SSR pola sama dengan test lain (tanpa jsdom).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import OpsConsole from "../components/OpsConsole";
import RoleHero, { roleProfile } from "../components/RoleHero";
import RecommendationCard from "../components/RecommendationCard";
import DecisionActions, { visibleActions } from "../components/DecisionActions";
import ApprovalMenu from "../components/ApprovalMenu";

const SNAPSHOT = {
  location: "Jakarta",
  commodity: "telur",
  supply_kg: 300,
  demand_kg: 1080,
  shortage_kg: 780,
  status: "shortage",
};

const ANALYSIS = {
  summary: {
    candidates_total: 14,
    eligible: 14,
    review_required: 0,
    flagged_price: 7,
  },
  recommendations: [
    {
      candidate_id: "Bogor->Jakarta:telur",
      eligible: true,
      safe_delivered_cost: "14873727.00",
      price_anomaly: { flagged: false },
      candidate: {
        source_location: "Bogor",
        destination_location: "Jakarta",
        commodity: "telur",
        quantity_kg: "492.00",
        freshness_score: "0.752408",
      },
    },
    {
      candidate_id: "Cianjur->Jakarta:telur",
      eligible: true,
      safe_delivered_cost: "9200000.00",
      price_anomaly: { flagged: true, ratio: 0.6 },
      candidate: {
        source_location: "Cianjur",
        destination_location: "Jakarta",
        commodity: "telur",
        quantity_kg: "600.00",
        freshness_score: "0.90",
      },
    },
  ],
};

describe("OpsConsole — interaksi sebelum hasil (arah Roy)", () => {
  it("langkah 1: pemilih lokasi, komoditas, tombol Muat kondisi", () => {
    const html = renderToStaticMarkup(
      <OpsConsole role="sppg_head" token={null} />
    );
    expect(html).toContain("ops-console");
    expect(html).toContain("ops-location");
    expect(html).toContain("ops-commodity");
    expect(html).toContain("Muat kondisi");
  });

  it("langkah 2: snapshot kondisi tampil (supply/demand/shortage)", () => {
    const html = renderToStaticMarkup(
      <OpsConsole role="sppg_head" token={null} snapshot={SNAPSHOT} />
    );
    expect(html).toContain("ops-snapshot");
    expect(html).toContain("780 kg");
    expect(html).toContain("SHORTAGE");
  });

  it("langkah 3: tombol analisis + hasil + ajukan usulan (role approver)", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="sppg_head"
        token="demo-token"
        snapshot={SNAPSHOT}
        analysis={ANALYSIS}
      />
    );
    expect(html).toContain("Jalankan Analisis Agent");
    expect(html).toContain("ops-candidates");
    expect(html).toContain("14 kandidat");
    expect(html).toContain("7 kandidat harga janggal");
    expect(html).toContain("FLAGGED");
    // Angka dari data nyata, tanpa karangan.
    expect(html).toContain("Rp14.873.727");
    expect(html).toContain("Ajukan");
  });

  it("bgn_monitor read-only: tidak ada tombol Ajukan", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="bgn_monitor"
        token="demo-token"
        snapshot={SNAPSHOT}
        analysis={ANALYSIS}
      />
    );
    expect(html).not.toContain("Ajukan");
  });

  it("sppg_nutritionist: tanpa tombol usul/Event 1, tetap diberi catatan baca", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="sppg_nutritionist"
        token="demo-token"
        snapshot={SNAPSHOT}
        analysis={ANALYSIS}
      />
    );
    // PLAN.md §13.3: usul & Event 1 hanya Kepala SPPG.
    expect(html).not.toContain("Ajukan usulan");
    expect(html).not.toContain("Jalankan Event 1 penuh");
    expect(html).toContain("hanya untuk Kepala SPPG");
  });
});

describe("RoleHero — identitas role tanpa panduan peran", () => {
  it("judul role tetap tampil, panduan peran & langkahnya sudah dihapus", () => {
    for (const role of ["sppg_head", "sppg_nutritionist", "bgn_monitor"]) {
      const html = renderToStaticMarkup(<RoleHero role={role} />);
      expect(html).toContain("role-hero");
      expect(html).toContain(roleProfile[role].title);
      // 27 Okt 2026: pemilik meminta blok "Panduan peran" (misi + langkah)
      // dilepas untuk SEMUA peran. Tes ini memaku KETIADAANNYA — bukan
      // menghapus cakupan — sambil memastikan identitas role & batas domain
      // peran tetap ada.
      expect(html).not.toContain("Panduan peran");
      expect(html).not.toContain("role-hero-more");
      expect(html).not.toContain("role-steps");
      expect(html).not.toContain("<ol");
      expect(html).toContain('data-testid="role-scope-note"');
    }
  });

  it("bgn_monitor ditandai sebagai pengawasan", () => {
    const html = renderToStaticMarkup(<RoleHero role="bgn_monitor" />);
    expect(html).toContain("Pengawasan");
  });
});

describe("Label kasus demo pada kartu feed", () => {
  it("kartu dengan demo_case menampilkan label kasus", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard
        decision={{
          decision_type: "regional_balance",
          status: "pending_approval",
          quantity_kg: 780,
          safe_delivered_cost: 14787096.28,
          valid: true,
          seconds_remaining: 600,
          demo_case: "shortage-darurat",
          iteration: 1,
        }}
      />
    );
    expect(html).toContain("Kasus: Shortage Darurat");
  });

  it("kartu tanpa demo_case tidak menampilkan label kasus", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard
        decision={{
          decision_type: "regional_balance",
          status: "pending_approval",
          quantity_kg: 600,
          safe_delivered_cost: 16206000,
          valid: true,
          seconds_remaining: 600,
          iteration: 1,
        }}
      />
    );
    expect(html).not.toContain("Kasus:");
  });
});

describe("Langkah Verifikasi (syarat execute — kontrol backend nyata)", () => {
  it("role approver melihat tombol Verifikasi pada status actionable", () => {
    // 2026-10-14: tombol pindah ke popup — yang diperiksa adalah ISI popup
    // (ApprovalMenu dengan aksi hasil visibleActions), bukan lagi deretan
    // tombol di dalam kartu halaman.
    const noop = async () => null;
    const html = renderToStaticMarkup(
      <ApprovalMenu
        summary={{
          decision_id: "d1",
          status: "pending_approval",
          can_approve: true,
          can_execute: false,
          verifier: { verdict: null, verified_by: null },
        }}
        actions={visibleActions("sppg_head", "pending_approval")}
        administrative={false}
        onApprove={noop}
        onReject={noop}
        onVerify={noop}
        onPropose={noop}
        onExecute={noop}
        onRepropose={noop}
        onClose={() => {}}
        />
        );
        expect(html).toContain("Verifikasi");
    // Eksekusi baru ditawarkan setelah kuorum penuh (status `approved`).
    expect(html).not.toContain('data-action="execute"');
  });

  it("Eksekusi muncul saat kuorum penuh, hanya untuk Head", () => {
    const noop = async () => null;
    const html = renderToStaticMarkup(
      <ApprovalMenu
        summary={{
          decision_id: "d1",
          status: "approved",
          can_approve: false,
          can_execute: true,
          verifier: { verdict: "consistent", verified_by: "verifier_agent" },
        }}
        actions={visibleActions("sppg_head", "approved")}
        administrative={false}
        onApprove={noop}
        onReject={noop}
        onVerify={noop}
        onPropose={noop}
        onExecute={noop}
        onRepropose={noop}
        onClose={() => {}}
      />
    );
    expect(html).toContain('data-action="execute"');
    expect(html).not.toContain('data-action="verify"');
  });

  it("bgn_monitor tidak melihat Verifikasi (read-only)", () => {
    const html = renderToStaticMarkup(
      <DecisionActions
        decisionId="d1"
        role="bgn_monitor"
        status="pending_approval"
        token="t"
      />
    );
    expect(html).not.toContain("Verifikasi");
    expect(html).toContain("read-only");
  });
});
