// Kontrak markup halaman "Decision & Evidence" (Langkah 4). Yang dipin:
// - tanpa keputusan terpilih: keadaan kosong yang jelas + saran dari data;
// - dengan keputusan: empat kartu fakta + riwayat iterasi + bukti tersimpan;
// - nilai yang tidak ada ditulis "—", bukan 0 / "Rp0" / "Tidak".
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionEvidence from "../components/DecisionEvidence";

const NOW = new Date("2026-10-11T02:30:00Z");

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
  approvals: [{ approver: "a1", role: "sppg_head" }],
  can_approve: false,
  can_execute: false,
  blocking_reasons: ["Kuota SPPG Jakarta penuh minggu ini"],
  approver_roles: ["sppg_head"],
};

const SELECTED = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  expires_at: "2026-10-11T02:16:47.973521+00:00",
};

const DECISIONS = [
  { decision_id: "d1", decision_type: "regional_balance", status: "pending_approval", quantity_kg: 600, expires_at: "2026-10-11T02:16:47.973521+00:00" },
  { decision_id: "d2", decision_type: "safety_disruption", status: "verifier_flagged", quantity_kg: 780, expires_at: "2026-10-11T09:00:00Z" },
];

const CHAIN = [
  { decision_id: "v1", iteration: 1, status: "rejected", quantity_kg: 600, safe_delivered_cost: 16206000, rejection_reason: "Kuota penuh" },
  { decision_id: "v2", iteration: 2, status: "pending_approval", quantity_kg: 600, safe_delivered_cost: 16206000 },
];

function render(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={DECISIONS as any}
      selected={SELECTED}
      selectedId="d1"
      onSelect={() => {}}
      chain={CHAIN}
      summary={SUMMARY}
      supplierContext={null}
      role="sppg_head"
      token="t"
      now={NOW}
      {...over}
    />
  );
}

describe("Decision & Evidence — tanpa pilihan", () => {
  it("menjelaskan cara memilih dan menyarankan yang menunggu tindakan", () => {
    const html = render({ selected: null, selectedId: null, summary: null, chain: [] });
    expect(html).toContain("Belum ada keputusan dipilih");
    expect(html).toContain("evidence-suggest");
    expect(html).toContain("regional balance");
    expect(html).toContain("safety disruption");
  });

  it("tanpa keputusan menunggu tindakan: dikatakan apa adanya", () => {
    const html = render({ selected: null, selectedId: null, decisions: [], summary: null, chain: [] });
    expect(html).toContain("Tidak ada keputusan yang menunggu tindakan saat ini");
  });

  it("tanpa saran yang menunggu, keputusan lama tetap bisa dipilih lewat dropdown", () => {
    const html = render({
      selected: null,
      selectedId: null,
      summary: null,
      chain: [],
      decisions: [{ decision_id: "old", decision_type: "price_anomaly", status: "rejected", expires_at: "2026-10-01T00:00:00Z" }],
    });
    expect(html).toContain("Tidak ada keputusan yang menunggu tindakan saat ini");
    expect(html).toContain('value="old"');
  });
});

describe("Decision & Evidence — dengan keputusan", () => {
  it("judul halaman + kartu bukti utama", () => {
    const html = render();
    expect(html).toContain("Decision &amp; Evidence");
    expect(html).toContain("Ringkasan keputusan");
    expect(html).toContain("Biaya");
    expect(html).toContain("Keamanan &amp; pemasok");
    expect(html).toContain("Governance &amp; persetujuan");
    expect(html).toContain("Riwayat iterasi");
  });

  it("mengisi fakta nyata: rute, komoditas, biaya, keamanan, pemasok", () => {
    const html = render();
    expect(html).toContain("Cianjur → Jakarta");
    expect(html).toContain("telur");
    expect(html).toContain("Rp15.720.000");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("PASS");
    expect(html).toContain("Supplier A Cianjur");
    expect(html).toContain("keandalan 80%");
    expect(html).toContain("1 dari 2");
  });

  it("tenggat memakai jam yang diberikan pemanggil", () => {
    expect(render()).toContain("Lewat 13 mnt");
  });

  it("riwayat iterasi memuat alasan penolakan (bahan belajar agen)", () => {
    const html = render();
    expect(html).toContain("v1");
    expect(html).toContain("Ditolak: Kuota penuh");
  });

  it("tanpa iterasi sebelumnya: dikatakan, bukan dibiarkan kosong", () => {
    const html = render({ chain: [] });
    expect(html).toContain("Belum ada iterasi sebelumnya untuk keputusan ini.");
  });

  it("panel bukti & integritas terpasang (isi muncul setelah data diambil)", () => {
    const html = render();
    // IntegrityPanel mengambil dossier saat mount, jadi pada markup statis yang
    // terlihat adalah kerangkanya — inilah kontrak yang bisa dipin.
    expect(html).toContain('data-testid="integrity-panel"');
    expect(html).toContain('data-testid="ledger-status"');
    expect(html).toContain('data-testid="dossier-status"');
    expect(html).toContain("Dossier Keputusan");
  });

  it("jam klien belum siap: label tenggat '—' (bukan jam server)", () => {
    const html = render({ now: null });
    expect(html).toContain("Tenggat");
    expect(html).not.toContain("Lewat 13 mnt");
  });

  it("summary belum dimuat: fakta kosong ditulis '—', riwayat iterasi tetap tampil", () => {
    const html = render({ summary: null });
    expect(html).toContain("—");
    expect(html).not.toContain("Rp0");
    // Yang masih diketahui dari payload keputusan tetap terisi:
    expect(html).toContain("600 kg");
    expect(html).toContain("Lewat 13 mnt");
    // Riwayat iterasi tidak ikut hilang.
    expect(html).toContain("v1");
    expect(html).toContain("Ditolak: Kuota penuh");
  });
});

// Dropdown 126 keputusan dulu mencetak istilah backend mentah
// ("regional_balance · pending_approval · ef347f91") berurutan apa adanya,
// sehingga pengguna tidak tahu mana yang perlu ditindak. Kontrak barunya:
// dikelompokkan + kata manusia (lib/decision-picker).
describe("Decision & Evidence — pemilih keputusan", () => {
  it("dikelompokkan dan memakai bahasa manusia, bukan istilah backend mentah", () => {
    const html = render();
    expect(html).toContain("<optgroup");
    expect(html).toContain("Menunggu tindakan (2)");
    expect(html).toContain("Alokasi regional direkomendasikan");
    expect(html).toContain("Pengalihan pasokan (gangguan keamanan)");
    // Bentuk lama label opsi: "<jenis> · <status> · <id 8>".
    expect(html).not.toContain("regional_balance ·");
    expect(html).not.toContain("safety_disruption ·");
    expect(html).not.toContain("pending_approval ·");
  });

  it("yang menunggu tindakan membawa sisa waktu supaya bisa diprioritaskan", () => {
    expect(render()).toContain("Lewat 13 mnt · d1");
  });

  it("tanpa jam klien, sisa waktu tidak dikarang jadi '—' di dalam opsi", () => {
    const html = render({ now: null });
    expect(html).toContain('value="d1"');
    expect(html).not.toContain("— · d1");
  });

  it("keputusan lama tetap dapat dipilih sendiri (nilai opsi = id utuh)", () => {
    const html = render({
      decisions: [
        {
          decision_id: "0267f818-f8f2-4e65-a299-f2627ad8ec71",
          decision_type: "price_anomaly",
          status: "rejected",
          created_at: "2026-10-01T00:00:00Z",
        },
      ],
    });
    expect(html).toContain('value="0267f818-f8f2-4e65-a299-f2627ad8ec71"');
    expect(html).toContain("Tidak menunggu tindakan (1)");
    expect(html).toContain("ditolak");
    expect(html).toContain("Penyesuaian harga direkomendasikan");
  });
});

// Ajakan "Klik untuk rincian & jejak agen" benar di feed (seluruh kartu
// dibungkus <button>), tapi di halaman ini kartu dirender tanpa pembungkus:
// kursor auto, tak ada induk yang bisa diklik, klik tidak mengubah apa pun.
// Jadi di sini diganti tombol nyata ke tab Agent Log.
describe("Decision & Evidence — jejak agen", () => {
  it("tidak ada lagi ajakan klik yang mati di kartu ringkasan", () => {
    const html = render({ onOpenTraces: () => {} });
    expect(html).not.toContain("Klik untuk rincian");
    expect(html).not.toContain("rec-hint");
  });

  it("jejak agen punya tombol nyata + keterangan ke mana ia membawa", () => {
    const html = render({ onOpenTraces: () => {} });
    expect(html).toContain("Buka jejak agen");
    expect(html).toContain("evidence-traces");
    expect(html).toContain("tab Agent Log");
  });

  it("tanpa callback, tombolnya tidak dirender (bukan tombol mati)", () => {
    expect(render()).not.toContain("Buka jejak agen");
  });
});
