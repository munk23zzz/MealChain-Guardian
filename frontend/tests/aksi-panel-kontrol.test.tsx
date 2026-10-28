// @vitest-environment jsdom
//
// Kontrol di bagian "Governance & persetujuan" (mode panel inline, 29 Okt 2026).
//
// Arahan pemilik: "Tutup panel" dibuat X bulat saja, tombol lain di situ
// diperbaiki UI/UX-nya, dan animasinya halus. Yang dijaga tes di sini:
//   * penutup panel adalah tombol IKON (aria-label + title, ada <svg>) dan tidak
//     lagi mencetak teks "Tutup panel" — teks di tombol kepala memakan lebar
//     yang dibutuhkan judul;
//   * aksi destruktif (Tolak, Kirim penolakan) punya penanda bahaya sendiri,
//     sehingga tidak lagi sebentuk dengan langkah netral (Verifikasi);
//   * X benar-benar menutup panel (state lokal), bukan sekadar hiasan.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import DecisionActions from "../components/DecisionActions";

const dasar = {
  decisionId: "3860992a-0000-0000-0000-000000000000",
  role: "sppg_head",
  token: "t",
};

function ringkas(over: Record<string, unknown> = {}) {
  return {
    status: "pending_approval",
    decision_type: "reallocation",
    approval_requirement: {
      verdict: "consistent",
      min_approvals: 2,
      required_roles: [["sppg_head"], ["sppg_nutritionist"]],
    },
    approval_state: {
      satisfied: false,
      rejected: false,
      missing: [["sppg_nutritionist"]],
      approved_roles: [],
    },
    can_approve: true,
    can_reject: true,
    can_execute: false,
    blocking_reasons: ["approval belum lengkap"],
    expiry: { valid: true, seconds_left: 7200 },
    ...over,
  };
}

function panelHtml(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <DecisionActions
      {...dasar}
      status="pending_approval"
      summary={ringkas(over)}
      tampil="panel"
      terbukaAwal
    />
  );
}

/** Tag <button> yang memuat `needle` (atribut), bukan elemen <li> di sekitarnya. */
function tombolDengan(html: string, needle: string): string {
  const semua = Array.from(html.matchAll(/<button\b[^>]*>/g), (m) => m[0]);
  const found = semua.find((tag) => tag.includes(needle));
  expect(found, `tidak ada <button> dengan ${needle}`).toBeTruthy();
  return found!;
}

describe("Panel Governance — penutup berupa ikon", () => {
  it("tombol tutup adalah X bulat ber-label, tanpa teks di layar", () => {
    const html = panelHtml();
    const tombol = tombolDengan(html, 'aria-label="Tutup panel"');
    // 29 Okt 2026: semua penutup memakai komponen bersama `TombolTutup`, jadi
    // kelasnya kini `tombol-x aksi-panel-close` — geometri dari `tombol-x`,
    // kait lama tetap ada supaya tes/CSS lain tidak putus.
    expect(tombol).toContain("tombol-x");
    expect(tombol).toContain("aksi-panel-close");
    expect(tombol).toContain('title="Tutup panel"');
    // Ikon, bukan teks: <svg> tepat setelah tag pembuka.
    expect(html).toMatch(/aria-label="Tutup panel"[^>]*>\s*<svg/);
    // Label tetap ada untuk pembaca layar, tetapi tidak tercetak sebagai tombol teks.
    expect(html).not.toMatch(/>\s*Tutup panel\s*</);
  });

  it("X berada di kepala panel, bukan di kaki", () => {
    const html = panelHtml();
    const kepala = html.slice(html.indexOf("aksi-panel-head"), html.indexOf("approval-menu-block"));
    expect(kepala).toContain('aria-label="Tutup panel"');
  });
});

describe("Panel Governance — penanda aksi", () => {
  it("Tolak bertanda bahaya, Verifikasi tetap netral", () => {
    const html = panelHtml();
    expect(tombolDengan(html, 'data-action="reject"')).toContain('data-tone="danger"');
    expect(tombolDengan(html, 'data-action="verify"')).not.toContain('data-tone="danger"');
  });

  it("setiap tombol baris memakai satu kelas geometri yang sama", () => {
    const html = panelHtml();
    // Lebar minimum + transisi datang dari kelas ini; tombol tanpa kelas itu
    // kembali menjadi pil selebar teksnya dan tepi kanannya jadi bergerigi.
    expect(tombolDengan(html, 'data-action="reject"')).toContain("action-menu-button");
    expect(tombolDengan(html, 'data-action="verify"')).toContain("action-menu-button");
  });
});

let host: HTMLDivElement | null = null;
let root: Root | null = null;

async function pasang(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(ui);
  });
  return host;
}

function klik(el: Element) {
  el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
}

afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});

describe("Panel Governance — interaksi", () => {
  beforeEach(() => {
    // React 18: `act` hanya sah bila lingkungan menyatakannya (pola yang sama
    // dipakai tests/decision-drawer.test.tsx).
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    // jsdom tidak punya scrollIntoView; komponen sudah menjaganya, ini jaring aman.
    Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
  });

  it("X menutup panel (panel hilang dari DOM)", async () => {
    const wadah = await pasang(
      <DecisionActions
        {...dasar}
        status="pending_approval"
        summary={ringkas()}
        tampil="panel"
        terbukaAwal
      />
    );
    expect(wadah.querySelector(".aksi-panel")).not.toBeNull();
    const x = wadah.querySelector('button[aria-label="Tutup panel"]')!;
    await act(async () => {
      klik(x);
    });
    expect(wadah.querySelector(".aksi-panel")).toBeNull();
  });

  it("kotak alasan penolakan memakai tombol bahaya untuk mengirim", async () => {
    const wadah = await pasang(
      <DecisionActions
        {...dasar}
        status="pending_approval"
        summary={ringkas()}
        tampil="panel"
        terbukaAwal
      />
    );
    const tolak = Array.from(wadah.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Tolak"
    )!;
    await act(async () => {
      klik(tolak);
    });
    const kirim = Array.from(wadah.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Kirim penolakan"
    )!;
    expect(kirim.className).toContain("button-danger");
    const batal = Array.from(wadah.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Batal menolak"
    )!;
    expect(batal.className).not.toContain("button-danger");
  });
});

describe("Panel Governance — dokumen PO tetap bisa diunduh setelah eksekusi", () => {
  // Laporan pemilik 29 Okt 2026: "harusnya setelah eksekusi bisa dapat download
  // PDF PO". Dokumennya memang ada (GET /sap/purchase-orders/{po}/pdf melayani
  // status approved & executed), tetapi satu-satunya tombolnya hidup di
  // Decision & Evidence — panel yang dipakai saat mengeksekusi justru tidak
  // menawarkannya, dan keputusan yang sudah dieksekusi hilang dari feed.
  const denganPo = { purchase_order: { po_number: "MC-BEF077A8A935", status: "submitted" } };

  it("keputusan executed dengan PO menawarkan Unduh PDF di panel", () => {
    const html = renderToStaticMarkup(
      <DecisionActions {...dasar} status="executed" summary={ringkas(denganPo)} tampil="panel" terbukaAwal />
    );
    expect(html).toContain('data-action="unduh-po"');
    expect(html).toContain("Unduh PDF");
    expect(html).toContain("MC-BEF077A8A935");
  });

  it("keputusan yang belum disetujui tidak menawarkan dokumen", () => {
    // PO draft lahir dari eksekusi, jadi PDF baru sah setelah kuorum penuh.
    const html = panelHtml(denganPo);
    expect(html).not.toContain('data-action="unduh-po"');
  });

  it("tanpa PO tidak ada baris dokumen kosong", () => {
    const html = renderToStaticMarkup(
      <DecisionActions {...dasar} status="executed" summary={ringkas()} tampil="panel" terbukaAwal />
    );
    expect(html).not.toContain('data-action="unduh-po"');
  });
});
