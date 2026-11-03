// Penolakan di Agent Activity Log harus MERAH (permintaan pemilik 29 Okt 2026).
//
// Sebelum ini lencana status "Ditolak" memakai `--status-warning` — kuning tua,
// sama dengan "Ditandai verifikator" yang memang bukan penolakan. Akibatnya
// satu-satunya keadaan yang benar-benar gugur terbaca seperti peringatan biasa,
// dan barisnya tidak bisa dibedakan sekilas dari baris yang masih berjalan.
//
// Kontrak yang dijaga tes ini:
//   1. Baris berstatus `rejected` membawa kelas `aa-row-rejected`; status lain
//      tidak (satu penanda, bukan tebakan dari teks).
//   2. Lencana `.aa-status-rejected` memakai token bahaya (`--danger-*`), bukan
//      `--status-warning`.
//   3. `.aa-row-rejected` memberi aksen merah di sisi kiri baris tanpa
//      menimpa latar baris terpilih (`aa-row-selected` tetap ada).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionAuditTable from "../components/DecisionAuditTable";
import type { AuditDecision } from "../lib/decision-table";

const css = readFileSync(join(__dirname, "..", "app", "agent-activity.css"), "utf8");

function blok(selektor: string): string {
  const i = css.indexOf(selektor);
  expect(i, `selektor tidak ditemukan: ${selektor}`).toBeGreaterThan(-1);
  const buka = css.indexOf("{", i);
  const tutup = css.indexOf("}", buka);
  // Komentar dibuang dulu: penjelasan boleh menyebut token lama, deklarasinya
  // tidak boleh.
  return css
    .slice(buka + 1, tutup)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .trim();
}

function row(over: Partial<AuditDecision>): AuditDecision {
  return {
    decision_id: "aaaaaaaa-1111-2222-3333-444444444444",
    decision_type: "supplier_procurement",
    status: "pending_approval",
    created_at: "2026-10-27T05:00:00.000Z",
    expires_at: "2026-10-30T05:00:00.000Z",
    quantity_kg: 300,
    safe_delivered_cost: 4500000,
    ...over,
  } as AuditDecision;
}

function render(rows: AuditDecision[], selectedId: string | null = null) {
  return renderToStaticMarkup(
    <DecisionAuditTable
      rows={rows}
      total={rows.length}
      page={1}
      onPage={() => {}}
      selectedId={selectedId}
      onSelect={() => {}}
      summary="tes"
      now={null}
    />,
  );
}

describe("penolakan ditandai merah", () => {
  it("baris rejected membawa aa-row-rejected, status lain tidak", () => {
    const html = render([
      row({ decision_id: "ditolak-1", status: "rejected" }),
      row({ decision_id: "jalan-1", status: "pending_approval" }),
      row({ decision_id: "selesai-1", status: "executed" }),
    ]);
    const baris = html.split("<tr").slice(1);
    const denganPenanda = baris.filter((b) => b.includes("aa-row-rejected"));
    expect(denganPenanda).toHaveLength(1);
    expect(denganPenanda[0]).toContain("ditolak-1".slice(0, 8));
  });

  it("baris rejected yang terpilih tetap membawa penanda merah", () => {
    const html = render([row({ decision_id: "ditolak-2", status: "rejected" })], "ditolak-2");
    expect(html).toContain("aa-row-rejected");
    expect(html).toContain("aa-row-selected");
  });

  it("lencana Ditolak memakai token bahaya, bukan warn kuning", () => {
    const isi = blok(".aa-status-rejected");
    expect(isi).toContain("--danger-ink");
    expect(isi).not.toContain("--status-warning");
  });

  it("baris rejected punya aksen merah di sisi kiri", () => {
    const isi = blok(".aa-row-rejected");
    expect(isi).toMatch(/border-left|box-shadow/);
    expect(isi).toContain("--danger");
  });
});
