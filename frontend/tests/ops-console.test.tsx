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
import DecisionActions from "../components/DecisionActions";

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
});

describe("RoleHero — konsol tiap role tidak polos", () => {
  it("tiap role punya judul + langkah kerja dari profil", () => {
    for (const role of ["sppg_head", "sppg_nutritionist", "bgn_monitor"]) {
      const html = renderToStaticMarkup(<RoleHero role={role} />);
      expect(html).toContain("role-hero");
      expect(html).toContain("role-steps");
      expect(html).toContain(roleProfile[role].title);
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
    const html = renderToStaticMarkup(
      <DecisionActions
        decisionId="d1"
        role="sppg_head"
        status="pending_approval"
        token="t"
      />
    );
    expect(html).toContain("Verifikasi");
    expect(html).toContain("Execute");
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
