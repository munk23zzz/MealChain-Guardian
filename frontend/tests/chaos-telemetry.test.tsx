/**
 * Kontrak P4/P5 FE (paket 1-6, keputusan Roy 2026-10-09):
 * - tab demo-control memuat ChaosPanel (chaos-panel) utk approver
 * - halaman "Decision & Evidence" memuat IntegrityPanel (Langkah 4,
 *   permintaan Roy 2026-10-11: panel bukti pindah dari tab agent-log ke
 *   halaman bukti keputusan — jejak reasoning & bukti jadi dua halaman)
 * - (revisi Roy 2026-10-10) telemetry banner DIHAPUS dari halaman login
 */

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

describe("markup kontrak P4/P5 (file-level, tanpa render app penuh)", () => {
  it("konsol memuat panel integritas & chaos (di halamannya masing-masing)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../app/page.tsx"),
      "utf-8"
    );
    const evidence = fs.readFileSync(
      path.resolve(__dirname, "../components/DecisionEvidence.tsx"),
      "utf-8"
    );
    // Panel integritas dipasang di halaman Decision & Evidence, bukan lagi
    // di tab agent-log (jejak agen vs bukti keputusan = dua halaman).
    expect(src).toContain("DecisionEvidence");
    expect(evidence).toContain("IntegrityPanel");
    expect(src).toContain("ChaosPanel");
    // Banner telemetry dihapus dari login (arah Roy 2026-10-10).
    expect(src).not.toContain("telemetry-banner");
  });

  it("ChaosPanel TIDAK menghitung safety di browser (server-side only)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/ChaosPanel.tsx"),
      "utf-8"
    );
    // Safety tidak pernah dihitung client — hanya POST /events/safety-disruption.
    expect(src).toContain("/events/safety-disruption");
    expect(src).not.toMatch(/safety_status\s*[:=]\s*(?!.*server)/);
  });

  it("ChaosPanel memakai penjaga cakupan lokasi (Ruling 2026-10-14)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const panel = fs.readFileSync(
      path.resolve(__dirname, "../components/ChaosPanel.tsx"),
      "utf-8"
    );
    const page = fs.readFileSync(
      path.resolve(__dirname, "../app/page.tsx"),
      "utf-8"
    );
    // Target event = lokasi SPPG pemakai (bukan lokasi batch) — kalau lokasi
    // batch dikirim sebagai target, server membalas 403 setelah ruling.
    expect(panel).toContain("lib/chaos-scope");
    expect(panel).toContain("resolveEventTarget");
    expect(panel).toContain("blockedReason");
    expect(panel).not.toMatch(/location_id\s*\?\?\s*""/);
    // Lokasi pemakai datang dari identitas server (/auth/me), bukan tebakan.
    expect(page).toMatch(/ownLocationId=\{me\?\.location_id/);
    expect(page).toMatch(/ownLocationName=\{me\?\.location_name/);
  });

  it("IntegrityPanel memanggil endpoint ledger & dossier", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/IntegrityPanel.tsx"),
      "utf-8"
    );
    expect(src).toContain("verifyLedger");
    expect(src).toContain("fetchDossier");
  });
});
