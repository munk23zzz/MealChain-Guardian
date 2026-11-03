// Panel bukti tidak boleh mencetak kunci backend sebagai teks layar
// (audit 29 Okt 2026). Sebelumnya satu baris berbunyi:
//   "human_inspection NEEDS_VERIFICATION … Waktu: 2026-10-28T02:15:46.147185Z"
// — kunci enum + ISO mentah, tanpa tanggal yang bisa dibaca manusia.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import ComplianceEvidencePanel from "../components/ComplianceEvidencePanel";

const DOSSIER = {
  decision_id: "x",
  evidence: [
    {
      id: "e1",
      evidence_type: "human_inspection",
      payload: { safety_status: "NEEDS_VERIFICATION" },
      recorded_at: "2026-10-28T02:15:46.147185Z",
      is_consistent: true,
    },
  ],
} as never;

describe("ComplianceEvidencePanel", () => {
  it("menerjemahkan jenis bukti dan keadaan", () => {
    const html = renderToStaticMarkup(<ComplianceEvidencePanel dossier={DOSSIER} />);
    expect(html).toContain("Pemeriksaan manusia");
    expect(html).not.toContain("human_inspection");
    expect(html).not.toContain("NEEDS_VERIFICATION");
    expect(html).toContain("Perlu verifikasi");
  });

  it("menulis waktu yang bisa dibaca, bukan ISO mentah", () => {
    const html = renderToStaticMarkup(<ComplianceEvidencePanel dossier={DOSSIER} />);
    expect(html).not.toContain("2026-10-28T02:15:46");
    expect(html).toMatch(/28 Okt 2026 09\.15 WIB/);
  });

  it("keputusan tanpa bukti tetap jujur", () => {
    const html = renderToStaticMarkup(
      <ComplianceEvidencePanel dossier={{ decision_id: "y" } as never} />,
    );
    expect(html).toContain("Belum ada bukti pengukuran untuk keputusan ini.");
  });
});
