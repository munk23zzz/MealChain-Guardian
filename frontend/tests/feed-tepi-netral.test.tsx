// Tahap 4 redesign Recommendation Feed (30 Okt 2026): tepi kiri berwarna
// dilepas. Status dibawa lencana (bertulisan), bukan pita warna di tepi kartu.
//
// Kenapa diuji di CSS, bukan di render: yang berubah justru hal yang tidak
// muncul di markup — pseudo-elemen `::before` beserta lima nadanya. Tanpa tes
// ini, satu baris `background: var(--status-danger)` bisa masuk lagi tanpa
// ada yang memerahkan apa pun.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

import { cardEdge } from "../lib/recommendations";

const AKAR = path.resolve(__dirname, "..");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8");
const KARTU = fs.readFileSync(path.join(AKAR, "components/RecommendationCard.tsx"), "utf8");

/** Semua isi aturan yang selektornya menyebut .rec-edge (termasuk ::before). */
function aturanRecEdge(css: string): Array<{ sel: string; isi: string }> {
  const hasil: Array<{ sel: string; isi: string }> = [];
  const pola = /([^{}]*\.rec-edge[^{}]*)\{([^}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = pola.exec(css))) hasil.push({ sel: m[1].trim(), isi: m[2] });
  return hasil;
}

describe("tepi kartu rekomendasi", () => {
  const aturan = aturanRecEdge(CSS);

  it("tidak ada lagi pseudo-elemen pita di tepi kiri", () => {
    expect(aturan.filter((a) => a.sel.includes("::before"))).toEqual([]);
  });

  it("tidak ada warna status yang dipakai sebagai latar tepi kartu", () => {
    const berwarna = aturan
      .filter((a) => /background:\s*var\(--(status-|accent|warn|danger|ink-muted|line-strong)/.test(a.isi))
      .map((a) => `${a.sel} { ${a.isi.trim()} }`);
    expect(berwarna).toEqual([]);
  });

  it("kartu lewat tenggat tetap dibedakan lewat PERMUKAAN, bukan garis berwarna", () => {
    const lewat = aturan.find((a) => a.sel.includes(".edge-expired") && !a.sel.includes(":hover"));
    expect(lewat, "aturan .rec-edge.edge-expired hilang").toBeDefined();
    expect(lewat!.isi).toContain("background: var(--surface-sunken)");
    expect(lewat!.isi).toContain("border-color: var(--line)");
  });

  it("kontrak lib tetap: lima nada masih diputuskan dan masih dicetak di DOM", () => {
    // Tingkat urgensi tetap terbaca mesin/tes walau tampilannya netral.
    expect(cardEdge({ status: "PENDING_APPROVAL" })).toBe("edge-neutral");
    expect(cardEdge({ status: "VERIFIER_FLAGGED" })).toBe("edge-warning");
    expect(cardEdge({ status: "REJECTED" })).toBe("edge-danger");
    expect(cardEdge({ status: "PROPOSED", valid: true })).toBe("edge-primary");
    expect(cardEdge({ status: "PROPOSED", valid: false })).toBe("edge-expired");
    expect(KARTU).toContain("rec-edge ${edge}");
  });

  it("status tetap terbaca dari teks, bukan warna: kartu mencetak lencana status", () => {
    // Lencana status adalah satu-satunya pembawa keadaan sekarang, jadi ia wajib
    // ada di kartu — bukan opsional.
    expect(KARTU).toContain("<StatusBadge status={decision.status} />");
    expect(KARTU).toContain("validityBadge(decision)");
  });
});
