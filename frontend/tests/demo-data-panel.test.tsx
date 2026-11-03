// Kontrak markup panel "Data & rentang waktu" (Fase 5, 2026-10-15).
//
// Yang dikunci di sini adalah KEHORMATAN tampilan, bukan detail kosmetik:
// - peringatan (hapus & segarkan) sudah terbaca SEBELUM tombol ditekan;
// - keadaan "belum dimuat" tidak disamarkan sebagai "tidak ada data";
// - peran di luar cakupan backend tidak melihat kontrol sama sekali.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DemoDataPanel from "../components/DemoDataPanel";
import { honestNote, purgeWarning, refreshWarning } from "../lib/demo-data";

function render(props: { token: string | null; role: string }) {
  return renderToStaticMarkup(<DemoDataPanel {...props} />);
}

describe("DemoDataPanel — cakupan peran", () => {
  it("kepala SPPG melihat kontrol lengkap: rentang, pratinjau, bangun, segarkan, bersihkan", () => {
    const html = render({ token: "t", role: "sppg_head" });
    expect(html).toContain('aria-label="Data &amp; rentang waktu"');
    expect(html).toContain('type="date"');
    expect(html).toContain("Pratinjau");
    expect(html).toContain("Buat/perbarui data");
    expect(html).toContain("Segarkan ke hari ini");
    expect(html).toContain("Bersihkan data demo");
    expect(html).toContain("Bangun ulang dari nol (hapus baris demo dulu)");
    expect(html).not.toContain("Mode baca");
  });

  it("memakai rentang default 1 Sep 2026 → 5 Nov 2026", () => {
    const html = render({ token: "t", role: "sppg_head" });
    expect(html).toContain('value="2026-09-01"');
    expect(html).toContain('value="2026-11-05"');
    expect(html).toContain("Rentang 66 hari");
  });

  it("ahli gizi SPPG juga boleh membangun data (cakupan backend sama)", () => {
    const html = render({ token: "t", role: "sppg_nutritionist" });
    expect(html).toContain("Buat/perbarui data");
  });

  it("pemantau BGN tidak melihat satu pun tombol aksi", () => {
    const html = render({ token: "t", role: "bgn_monitor" });
    expect(html).not.toContain("Buat/perbarui data");
    expect(html).not.toContain("Segarkan ke hari ini");
    expect(html).not.toContain("Bersihkan data demo");
    expect(html).not.toContain("Pratinjau");
    expect(html).toContain("Mode baca");
  });

  it("tanpa token: tidak ada aksi, tetapi catatan jujur tetap tampil", () => {
    const html = render({ token: null, role: "sppg_head" });
    expect(html).not.toContain("Buat/perbarui data");
    expect(html).toContain("Mode baca");
    expect(html).toContain(honestNote());
  });
});

describe("DemoDataPanel — peringatan tampil sebelum aksi", () => {
  it("peringatan hapus sudah terbaca tanpa menekan apa pun (dua langkah)", () => {
    const html = render({ token: "t", role: "sppg_head" });
    expect(html).toContain(purgeWarning());
    // Konfirmasi baru muncul SETELAH tombol bersihkan ditekan.
    expect(html).not.toContain("Ya, hapus baris demo");
    expect(html).toContain('aria-describedby="demo-data-purge-warning"');
  });

  it("peringatan seeder relatif tampil bersama tombol segarkan", () => {
    const html = render({ token: "t", role: "sppg_head" });
    expect(html).toContain(refreshWarning());
    expect(html).toContain('aria-describedby="demo-data-refresh-warning"');
  });

  it("catatan apa yang TIDAK dijanjikan selalu ada", () => {
    const html = render({ token: "t", role: "sppg_head" });
    expect(html).toContain("Aktual tidak pernah dikarang di masa depan");
  });
});

describe("DemoDataPanel — keadaan belum dimuat", () => {
  it("menampilkan keadaan memuat, bukan klaim 'tidak ada data'", () => {
    const html = render({ token: "t", role: "sppg_head" });
    expect(html).toContain("Memuat status data demo");
    expect(html).toContain('aria-busy="true"');
    // Angka status hanya boleh muncul setelah backend membalas.
    expect(html).not.toContain("Belum ada deret waktu demo");
    expect(html).not.toContain("Snapshot kanonik:");
  });
});
