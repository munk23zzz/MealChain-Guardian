// @vitest-environment jsdom
//
// Satu rupa untuk SEMUA tombol tutup (permintaan pemilik, 29 Okt 2026:
// "untuk semua tombol keluar buat menjadi X bulat").
//
// Sebelumnya penutup muncul dalam tiga bentuk — tombol teks "Tutup" di kaki
// dialog dan di kepala kartu rincian, X berbingkai 4 px di kepala popup, dan X
// lingkaran di panel Governance. Yang dijaga tes di sini:
//   * tidak ada lagi penutup berbentuk tombol teks di permukaan yang diubah;
//   * setiap penutup adalah tombol ikon ber-label (`aria-label` + `title`),
//     karena ikon saja tidak terbaca pembaca layar;
//   * geometrinya satu kelas (`.tombol-x`), bukan angka yang disalin per
//     komponen.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import ApprovalMenu from "../components/ApprovalMenu";
import Popup from "../components/Popup";
import TombolTutup from "../components/TombolTutup";

const menuActions = {
  approve: false,
  verify: false,
  execute: false,
  propose: false,
  repropose: false,
  readOnly: false,
};

function menu(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <ApprovalMenu
      summary={{ status: "pending_approval" }}
      actions={menuActions}
      administrative={false}
      onApprove={async () => null}
      onReject={async () => null}
      onVerify={async () => null}
      onPropose={async () => null}
      onExecute={async () => null}
      onRepropose={async () => null}
      onClose={() => {}}
      {...props}
    />
  );
}

describe("TombolTutup — satu ikon untuk semua penutup", () => {
  it("mencetak X bulat ber-label, tanpa teks di layar", () => {
    const html = renderToStaticMarkup(<TombolTutup label="Tutup panel" />);
    expect(html).toContain("tombol-x");
    expect(html).toContain('aria-label="Tutup panel"');
    expect(html).toContain('title="Tutup panel"');
    // Ikon, bukan teks: <svg> tepat setelah tag pembuka.
    expect(html).toMatch(/<button[^>]*>\s*<svg/);
    expect(html).not.toMatch(/>\s*Tutup\s*</);
  });

  it("label bawaan tetap ada walau pemanggil lupa mengisi", () => {
    const html = renderToStaticMarkup(<TombolTutup />);
    expect(html).toContain('aria-label="Tutup"');
  });
});

describe("Popup — kepala memakai X bulat bersama", () => {
  it("kelas popup-close dipertahankan sebagai kait, bentuk dari tombol-x", async () => {
    // Popup merender lewat portal ke <body>, jadi cari di dokumen (dan tidak
    // bisa memakai `renderToStaticMarkup`).
    await pasang(
      <Popup open title="Rincian" onClose={() => {}}>
        isi
      </Popup>
    );
    const x = document.querySelector('[aria-label="Tutup jendela"]');
    expect(x).toBeTruthy();
    expect(x!.className).toContain("tombol-x");
    expect(x!.className).toContain("popup-close");
    expect(x!.querySelector("svg")).toBeTruthy();
  });
});

describe("ApprovalMenu — kaki dialog tidak lagi berbentuk tombol teks", () => {
  it("penutupnya X ber-label, bukan kata 'Tutup'", () => {
    const html = menu();
    expect(html).toContain('aria-label="Tutup jendela persetujuan"');
    expect(html).not.toMatch(/<button[^>]*>\s*Tutup\s*<\/button>/);
  });

  it("mode panel tidak menambah penutup kedua", () => {
    // Panel sudah punya X di kepalanya (DecisionActions); kaki menu tidak boleh
    // menawarkan penutup lain untuk hal yang sama.
    const html = menu({ dalamPanel: true });
    expect(html).not.toContain("Tutup jendela persetujuan");
  });
});

// ── Klik benar-benar menutup ───────────────────────────────────────────────
let host: HTMLDivElement | null = null;
let root: Root | null = null;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  host = null;
  root = null;
});

async function pasang(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(ui);
  });
  return host;
}

describe("TombolTutup — klik diteruskan ke induk", () => {
  it("onClick dipanggil dan tombolnya bisa dinonaktifkan", async () => {
    let dipanggil = 0;
    const el = await pasang(
      <>
        <TombolTutup label="Tutup panel" onClick={() => (dipanggil += 1)} />
        <TombolTutup label="Tutup lain" disabled onClick={() => (dipanggil += 100)} />
      </>
    );
    const [aktif, mati] = Array.from(el.querySelectorAll("button"));
    act(() => aktif.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    act(() => mati.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(dipanggil).toBe(1);
    expect(mati.disabled).toBe(true);
  });
});
