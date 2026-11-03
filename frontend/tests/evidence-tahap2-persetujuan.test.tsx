// TAHAP 2 redesign Decision & Evidence (29 Okt 2026): blok PERSETUJUAN gaya
// clean dashboard.
//
// Yang dipaku di sini:
//   1. bentuk: satu kartu, satu judul, satu pil status, satu pemicu aksi;
//   2. isi: jawaban berurutan (menahan → dibutuhkan → setelah ini), lalu SATU
//      tabel penyetuju (peran · keadaan · dicatat);
//   3. kejujuran: "tidak ada yang menahan" TIDAK boleh muncul saat peran masih
//      kurang; ringkasan yang belum tiba ditulis sebagai keadaan, bukan
//      disimpulkan "tidak ada persetujuan";
//   4. bahasa: nama peran manusia, bukan enum (`sppg_nutritionist`).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionApproval from "../components/DecisionApproval";

const root = join(__dirname, "..");
const css = readFileSync(join(root, "app/evidence-dossier.css"), "utf8");
const NOW = new Date("2026-10-11T02:30:00Z");

const SYARAT = { required_roles: [["sppg_head"], ["sppg_nutritionist"]], min_approvals: 2 };

const MENUNGGU = {
  status: "pending_approval",
  approval_requirement: SYARAT,
  approval_state: { missing: [["sppg_nutritionist"]], approved_roles: ["sppg_head"], satisfied: false },
  approvals: [
    {
      role: "sppg_head",
      approved: true,
      approved_by_name: "Rina Kusuma",
      approved_at: "2026-10-08T02:00:00Z",
    },
  ],
  can_approve: true,
  blocking_reasons: [],
};

const LENGKAP = {
  status: "approved",
  approval_requirement: SYARAT,
  approval_state: { missing: [], approved_roles: ["sppg_head", "sppg_nutritionist"], satisfied: true },
  approvals: [
    { role: "sppg_head", approved: true, approved_by_name: "Rina Kusuma", approved_at: "2026-10-08T02:00:00Z" },
    { role: "sppg_nutritionist", approved: true, approved_by_name: "Bayu S", approved_at: "2026-10-08T03:10:00Z" },
  ],
  can_execute: true,
  blocking_reasons: [],
};

const TERTAHAN = {
  ...MENUNGGU,
  blocking_reasons: ["supplier belum terikat pada batch", "batch kedaluwarsa"],
};

function html(summary: unknown) {
  return renderToStaticMarkup(
    <DecisionApproval
      decisionId="d1"
      role="sppg_head"
      status={(summary as { status?: string } | null)?.status ?? "pending_approval"}
      token="t"
      summary={summary}
      now={NOW}
    />
  );
}

describe("bentuk blok: satu kartu, satu judul, satu aksi", () => {
  it("judul 'Persetujuan' + pil status + tepat satu pemicu aksi", () => {
    const out = html(MENUNGGU);
    expect(out).toContain("<h2>Persetujuan</h2>");
    expect(out).toContain("evidence-header-status");
    expect(out).toMatch(/data-status="pending_approval"/);
    expect(out).toContain("Menunggu persetujuan");
  });

  it("tiga jawaban hadir berurutan: menahan → dibutuhkan → setelah ini", () => {
    const out = html(TERTAHAN);
    const iMenahan = out.indexOf("Yang menahan");
    const iButuh = out.indexOf("Dibutuhkan");
    const iSetelah = out.indexOf("Setelah ini");
    expect(iMenahan).toBeGreaterThan(-1);
    expect(iButuh).toBeGreaterThan(iMenahan);
    expect(iSetelah).toBeGreaterThan(iButuh);
  });

  it("penyetuju sebagai satu tabel dengan tiga kolom", () => {
    const out = html(MENUNGGU);
    expect(out).toContain('class="approval-roles"');
    expect(out).toContain(">Peran<");
    expect(out).toContain(">Keadaan<");
    expect(out).toContain(">Dicatat<");
  });
});

describe("kejujuran keadaan", () => {
  it("peran masih kurang tanpa sebab tertulis: TIDAK mengklaim 'tidak ada yang menahan'", () => {
    const out = html(MENUNGGU);
    expect(out).not.toContain("Tidak ada yang menahan persetujuan keputusan ini.");
    expect(out).toContain("Tidak ada sebab tertulis");
    expect(out).toContain("menunggu Ahli Gizi SPPG");
  });

  it("semua syarat terpenuhi: kalimat positif baru muncul", () => {
    const out = html(LENGKAP);
    expect(out).toContain("Tidak ada yang menahan persetujuan keputusan ini.");
  });

  it("sebab dari server diterjemahkan dan ditampilkan sebagai daftar", () => {
    const out = html(TERTAHAN);
    expect(out).toContain("Yang menahan");
    expect(out).toContain("batch kedaluwarsa");
  });

  it("ringkasan belum tiba: ditulis sebagai keadaan, bukan 'tidak ada persetujuan'", () => {
    const out = html(null);
    expect(out).toContain('data-testid="persetujuan-menunggu"');
    expect(out).not.toContain("Belum ada baris persetujuan untuk keputusan ini.");
    expect(out).not.toContain('class="approval-roles"');
  });
});

describe("bahasa: tidak ada enum di layar", () => {
  it("nama peran manusia, bukan kode role", () => {
    const out = html(MENUNGGU);
    expect(out).not.toContain("sppg_nutritionist");
    expect(out).not.toContain("sppg_head");
    expect(out).toContain("Ahli Gizi SPPG");
  });

  it("status tidak tampil sebagai enum Inggris", () => {
    const out = html(MENUNGGU);
    expect(out).not.toContain("PENDING_APPROVAL");
  });
});

describe("CSS clean dashboard", () => {
  it("kartu memakai token, tanpa hex baru", () => {
    const blok = css.slice(css.indexOf(".approval-block {"));
    const isi = blok.slice(0, blok.indexOf("}"));
    expect(isi).toContain("border: 1px solid var(--line)");
    expect(isi).toContain("box-shadow: var(--shadow-1)");
    expect(isi).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });

  it("kolom waktu rata kanan dan tabular", () => {
    const blok = css.slice(css.indexOf(".approval-role-waktu {"));
    const isi = blok.slice(0, blok.indexOf("}"));
    expect(isi).toContain("text-align: right");
    expect(isi).toContain("font-variant-numeric: tabular-nums");
  });

  it("tabel berubah jadi baris bertumpuk di bawah 640 px", () => {
    const media = css.slice(css.indexOf("@media (max-width: 640px)", css.indexOf(".approval-roles {")));
    expect(media).toContain(".approval-roles thead");
    expect(media).toContain("display: none");
    expect(media).toContain("display: grid");
  });
});
