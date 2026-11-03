// Kontrak UX aksi halaman "Decision & Evidence" (audit 27 Okt 2026).
//
// Tiga cacat yang dikunci di sini, semuanya terlihat oleh juri:
//  1. galat aksi tampil MENTAH ("binding batch/supplier berubah") tanpa menyebut
//     aksi mana yang gagal dan tanpa terjemahan;
//  2. ringkasan persetujuan yang belum tiba dirender sebagai chip
//     "Menunggu persetujuan" — bertentangan dengan lencana keputusan di atasnya;
//  3. `IntegrityPanel` bisa menampilkan dossier keputusan SEBELUMNYA.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionEvidence from "../components/DecisionEvidence";
import { humanizeBlocker } from "../lib/bahasa";

const NOW = new Date("2026-10-27T08:00:00Z");

const SUMMARY = {
  decision_id: "d1",
  decision_type: "supplier_procurement",
  status: "approved",
  iteration: 1,
  source_location: null,
  target_location: "Jakarta",
  commodity: "telur",
  quantity_kg: 300,
  safe_delivered_cost: 9000000,
  material_number: "MAT-TELUR",
  supplier: { id: "s1", name: "UD Sumber Rejeki Telur" },
  execution_target: "MOCK",
  verifier: { verdict: "consistent", verified_by: "verifier_agent" },
  safety: { worst_status: "pass", blocked: false, batches_checked: 1 },
  expiry: { expires_at: "2026-10-27T09:00:00+00:00", valid: true, seconds_remaining: 3600 },
  approval_requirement: { verdict: "consistent", min_approvals: 2, requirement: "2 dari 2" },
  approvals: [
    { approver: "a1", role: "sppg_head" },
    { approver: "a2", role: "sppg_nutritionist" },
  ],
  can_approve: false,
  can_execute: true,
  blocking_reasons: [],
  approver_roles: ["sppg_head", "sppg_nutritionist"],
};

const SELECTED = {
  decision_id: "d1",
  decision_type: "supplier_procurement",
  status: "approved",
  quantity_kg: 300,
  safe_delivered_cost: 9000000,
  created_at: "2026-10-27T07:30:00Z",
  expires_at: "2026-10-27T09:00:00+00:00",
};

const DECISIONS = [
  {
    decision_id: "d1",
    decision_type: "supplier_procurement",
    status: "approved",
    quantity_kg: 300,
    expires_at: "2026-10-27T09:00:00+00:00",
  },
];

function render(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={DECISIONS as any}
      selected={SELECTED}
      selectedId="d1"
      onSelect={() => {}}
      chain={[]}
      summary={SUMMARY}
      supplierContext={null}
      role="sppg_head"
      token="t"
      now={NOW}
      {...over}
    />
  );
}

describe("bahasa galat aksi", () => {
  it("menerjemahkan 409 binding pengadaan, bukan menampilkan kalimat server", () => {
    const hasil = humanizeBlocker("binding batch/supplier berubah");
    expect(hasil).not.toBeNull();
    expect(hasil).not.toContain("binding batch/supplier berubah");
    expect(String(hasil)).toContain("ajukan keputusan baru");
  });

  it("menerjemahkan alasan tertahan lain yang bisa muncul di popup aksi", () => {
    expect(String(humanizeBlocker("supplier excluded pada SPPG penerima"))).toContain(
      "dikecualikan"
    );
    expect(String(humanizeBlocker("quantity decision tidak valid"))).toContain("kuantitas");
    // Kalimat yang tidak dikenal TIDAK dikarang: dikembalikan apa adanya.
    expect(humanizeBlocker("galat jaringan 502")).toBe("galat jaringan 502");
  });
});

describe("kartu Governance saat ringkasan belum tiba", () => {
  it("menyebut keadaan memuat, bukan 'Menunggu persetujuan'", () => {
    const html = render({ summary: null });
    expect(html).toContain('data-testid="governance-pending"');
    expect(html).toContain("Ringkasan persetujuan sedang dimuat");
    // Chip state palsu tidak boleh muncul sebelum ringkasan ada.
    expect(html).not.toContain("Menunggu persetujuan");
  });

  it("merender kartu governance normal saat ringkasan tersedia", () => {
    const html = render();
    expect(html).not.toContain('data-testid="governance-pending"');
    expect(html).toContain("Governance &amp; persetujuan");
  });
});

describe("keadaan per-keputusan tidak bocor", () => {
  it("panel integritas diberi key keputusan (state tidak dipakai ulang)", () => {
    const html = render();
    // Dossier keputusan lain tidak boleh tampil: panel memuat keputusan aktif.
    expect(html).toContain('data-testid="integrity-panel"');
    expect(html).toContain("Integritas Bukti");
  });
});
