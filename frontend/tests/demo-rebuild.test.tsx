// Kontrak blok "Bangun ulang data" (21 Okt 2026).
//
// Yang dipaku:
// - blok ini HANYA muncul saat sesi berjalan (di luar sesi, "Muat Demo"
//   sudah membangun ulang dari awal — dua tombol untuk hal yang sama membingungkan);
// - teksnya menyebut biaya waktu yang sebenarnya (±70 detik), bukan "sebentar";
// - saat berjalan, yang tampil hanya hitungan detik — bukan bar progres palsu;
// - kalimat hasil memakai angka dari `hitung` (dibaca ulang server), bukan karangan.

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { DemoRebuild } from "../components/DemoControlPanel";
import { rebuildLine, rebuildWarning } from "../lib/demo-data";

function render(props: Partial<React.ComponentProps<typeof DemoRebuild>> = {}) {
  return renderToStaticMarkup(<DemoRebuild aktif onRebuild={() => {}} {...props} />);
}

describe("DemoRebuild — aksi destruktif yang jujur", () => {
  it("tidak dirender di luar sesi", () => {
    const html = renderToStaticMarkup(<DemoRebuild aktif={false} onRebuild={() => {}} />);
    expect(html).toBe("");
  });

  it("menyebut biaya waktu sebenarnya dan efeknya", () => {
    const html = render();
    expect(html).toContain("Bangun ulang data");
    expect(html).toContain("Terukur 41 detik");
    expect(html).toContain("sekitar 1 menit");
    expect(html).toContain("tanpa menutup sesi");
  });

  it("saat berjalan hanya menghitung detik, tanpa bar progres", () => {
    const html = render({ sibuk: true, detik: 12 });
    expect(html).toContain("Membangun ulang… 12 detik");
    expect(html).not.toContain("<progress");
    expect(html).not.toContain("Bangun ulang data");
  });

  it("konfirmasi dua langkah: tombol pertama tidak langsung memanggil aksi", () => {
    const onRebuild = vi.fn();
    const html = render({ onRebuild });
    expect(html).toContain("Bangun ulang data");
    expect(html).not.toContain("Ya, bangun ulang");
    expect(onRebuild).not.toHaveBeenCalled();
  });
});

describe("rebuildLine — angka dari server, bukan dari parameter", () => {
  it("merangkum hitungan yang dibaca ulang", () => {
    const baris = rebuildLine({
      ok: true,
      durasi_detik: 67.9,
      hitung: { batches: 120, decisions: 35, po: 16, ledger: 72 },
    });
    expect(baris).toBe(
      "Data demo dibangun ulang dalam 67.9 detik: 120 batch, 35 keputusan, 16 pesanan SAP, 72 blok ledger."
    );
  });

  it("tidak mengarang angka saat hitungan tidak dikirim", () => {
    expect(rebuildLine({ ok: true, durasi_detik: 3 })).toBe(
      "Data demo dibangun ulang dalam 3.0 detik."
    );
    expect(rebuildLine(null)).toBe("Bangun ulang belum dijalankan.");
  });
});

describe("rebuildWarning — menyebut yang hilang dan yang tidak", () => {
  it("menyebut yang diganti, yang tidak disentuh, dan waktu", () => {
    const teks = rebuildWarning();
    expect(teks).toContain("diganti dari template");
    expect(teks).toContain("tidak");
    expect(teks).toContain("terukur 41 detik");
    expect(teks).toContain("sekitar 1 menit");
  });
});
