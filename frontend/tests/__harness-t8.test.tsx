// Harness ukur (sementara, dihapus setelah dipakai): render halaman Decision &
// Evidence apa adanya — markah nyata + CSS aplikasi — ke satu berkas HTML.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { it } from "vitest";

import DecisionEvidence from "../components/DecisionEvidence";

const AKAR = join(__dirname, "..");

const CSS = [
  "app/globals.css",
  "app/theme-ext.css",
  "app/map-console.css",
  "app/evidence-dossier.css",
  "app/overview-p0.css",
  "app/supply-adequacy.css",
]
  .map((f) => readFileSync(join(AKAR, f), "utf8"))
  .join("\n");

const NOW = new Date("2026-10-29T03:00:00Z");

const SUMMARY: Record<string, unknown> = {
  decision_id: "9e0cb1fb-1111-4c4c-8a8a-000000000001",
  decision_type: "regional_balance",
  status: "pending_approval",
  iteration: 2,
  supersedes_id: "86cad754-2222-4c4c-8a8a-000000000002",
  proposed_by: "supervisor_agent",
  source_location: "Cianjur",
  target_location: "Jakarta",
  commodity: "telur",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  material_number: "MAT-TELUR",
  supplier: { id: "s1", name: "CV Sumber Pangan", reliability_score: 0.94 },
  execution_target: "mock",
  verifier: { verdict: "consistent", verified_by: "verifier_agent" },
  safety: { worst_status: "fail", blocked: true, batches_checked: 4 },
  expiry: { expires_at: "2026-10-29T03:13:00+00:00", valid: true, seconds_remaining: 780 },
  approval_requirement: { verdict: "consistent", min_approvals: 2, requirement: "2 dari 2" },
  approvals: [
    { role: "kepala_sppg", approved: true, approved_at: "2026-10-29T02:00:00Z" },
    { role: "ahli_gizi_sppg", approved: null, approved_at: null },
  ],
  verifier_note: "consistent",
  approved_by: null,
  can_approve: true,
  can_execute: false,
  blocking_reasons: ["safety_status_bukan_pass", "persetujuan_kurang_satu"],
  approver_roles: ["sppg_head", "sppg_nutritionist"],
  commercial_cost: {
    purchase_total: "5700000.00",
    transport_total: "34200.00",
    handling_total: "150000.00",
    invoice_total: "5884200.00",
    invoice_unit_price: "29421.00",
    expected_loss: "900000.00",
    freshness_risk: "250000.00",
    safety_penalty: "400000.00",
    sdc_total: "7434200.00",
    sdc_unit_price: "37171.00",
    risk_method: { kind: "simulated_policy", source: "s", version: "v1", period: null, baseline: null },
  },
  market_reference: { source: "pihps_reference", price_per_kg: 31000, recorded_at: "2026-10-28T00:00:00+00:00" },
  analytical_cost: {
    components: [
      { label: "Susut gudang", amount: 900000 },
      { label: "Risiko kesegaran", amount: 250000 },
      { label: "Penalti keamanan", amount: 400000 },
    ],
    total: 7434200,
    per_kg: 37171,
  },
  batches: [
    { batch_id: "b1", status: "pass", gate: "safety", note: "suhu kiriman tercatat" },
    { batch_id: "b2", status: "fail", gate: "safety_status_bukan_pass", note: "suhu kiriman tidak tercatat" },
    { batch_id: "b3", status: "warn", gate: "freshness", note: "kesegaran 0.91" },
  ],
};

const SELECTED: Record<string, unknown> = {
  decision_id: "9e0cb1fb-1111-4c4c-8a8a-000000000001",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  created_at: "2026-10-29T01:30:00Z",
  expires_at: "2026-10-29T03:13:00+00:00",
  commercial_cost: {
    purchase_total: "5700000.00",
    transport_total: "34200.00",
    handling_total: "150000.00",
    invoice_total: "5884200.00",
    invoice_unit_price: "29421.00",
    expected_loss: "900000.00",
    freshness_risk: "250000.00",
    safety_penalty: "400000.00",
    sdc_total: "7434200.00",
    sdc_unit_price: "37171.00",
    risk_method: { kind: "simulated_policy", source: "s", version: "v1", period: null, baseline: null },
  },
  market_reference: { source: "pihps_reference", price_per_kg: 31000, recorded_at: "2026-10-28T00:00:00+00:00" },
  summary: SUMMARY,
};

it("menulis berkas ukur", () => {
  const markah = renderToStaticMarkup(
    <DecisionEvidence
      decisions={[SELECTED] as never}
      selected={SELECTED as never}
      selectedId="9e0cb1fb-1111-4c4c-8a8a-000000000001"
      onSelect={() => {}}
      chain={
        [
          {
            decision_id: "86cad754-e175-49da-96ca-a0250ad81cb7",
            iteration: 1,
            status: "rejected",
            rejection_reason: "stok tidak cukup",
            created_at: "2026-10-28T01:00:00Z",
          },
        ] as never
      }
      summary={SUMMARY as never}
      supplierContext={
        {
          suppliers: [
            { id: "s1", name: "CV Sumber Pangan", reliability_score: 0.94 },
            { id: "s2", name: "UD Tani Makmur", reliability_score: 0.71 },
          ],
          reason_unavailable: null,
          exclusions: [
            {
              id: "x1",
              supplier_id: "s2",
              scope_location_id: "loc-jakarta",
              status: "active",
              reason: "suhu kiriman tidak tercatat pada dua penerimaan terakhir",
              evidence_refs: [{ type: "incident", id: "i1" }],
            },
          ],
        } as never
      }
      role="sppg_head"
      token="t"
      purchaseOrders={[] as never}
      now={NOW}
    />,
  );

  const html = `<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8"><style>
html,body{margin:0;width:100%;background:#f4f4f2}
body{font-family:system-ui,sans-serif}
${CSS}
</style></head>
<body><div style="padding:16px">${markah}</div></body></html>`;

  writeFileSync(join("C:/Users/User/AppData/Local/hermes/cache/scratch", "ev-tahap8.html"), html);
  writeFileSync(
    join("C:/Users/User/AppData/Local/hermes/cache/scratch", "ev8-wrap1360.html"),
    `<!DOCTYPE html><body style="margin:0"><iframe src="ev-tahap8.html" style="width:1360px;height:3000px;border:0"></iframe></body>`,
  );
  writeFileSync(
    join("C:/Users/User/AppData/Local/hermes/cache/scratch", "ev8-wrap375.html"),
    `<!DOCTYPE html><body style="margin:0"><iframe src="ev-tahap8.html" style="width:375px;height:3000px;border:0"></iframe></body>`,
  );
});
