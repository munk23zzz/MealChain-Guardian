// Kontrak StatusBadge: lencana TIDAK boleh menampilkan enum mentah berbahasa
// Inggris (temuan QA 17 Okt 2026: "PENDING APPROVAL" muncul 23x di feed).
// `data-status` tetap menyimpan nilai mentah — itu kontrak untuk CSS & tes lain.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import StatusBadge from "../components/StatusBadge";

describe("StatusBadge", () => {
  it("menampilkan status dalam bahasa Indonesia", () => {
    expect(renderToStaticMarkup(<StatusBadge status="PENDING_APPROVAL" />)).toContain(
      "Menunggu persetujuan"
    );
    expect(renderToStaticMarkup(<StatusBadge status="NEEDS_VERIFICATION" />)).toContain(
      "Perlu verifikasi"
    );
    expect(renderToStaticMarkup(<StatusBadge status="PROPOSED" />)).toContain("Diusulkan");
    expect(renderToStaticMarkup(<StatusBadge status="VERIFIER_FLAGGED" />)).toContain(
      "Ditandai verifikator"
    );
  });

  it("tidak lagi membocorkan enum Inggris yang dikenal", () => {
    const html = renderToStaticMarkup(<StatusBadge status="PENDING_APPROVAL" />);
    expect(html).not.toContain("PENDING APPROVAL");
  });

  it("nilai mentah tetap tersimpan di data-status (kontrak CSS)", () => {
    const html = renderToStaticMarkup(<StatusBadge status="pending_approval" />);
    expect(html).toContain('data-status="PENDING_APPROVAL"');
    // 29 Okt 2026: "menunggu persetujuan" memakai abu netral (permintaan
    // pemilik), bukan amber — amber kini hanya untuk yang perlu diperiksa.
    expect(html).toContain("status-neutral");
  });

  it("status tak dikenal tampil apa adanya (tanpa garis bawah), bukan dikarang", () => {
    expect(renderToStaticMarkup(<StatusBadge status="CUSTOM_STATE" />)).toContain("CUSTOM STATE");
  });
});
