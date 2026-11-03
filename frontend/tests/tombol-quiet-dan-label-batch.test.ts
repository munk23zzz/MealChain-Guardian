import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Dua cacat konsistensi halaman "Pasokan & Kebutuhan" (29 Okt 2026).
 *
 * 1) `button-quiet` dipakai empat kali (Tutup rincian lokasi, tiga kontrol Demo
 *    Control) tetapi TIDAK PERNAH dideklarasikan di stylesheet. Akibatnya kelas
 *    itu tidak berefek dan tombolnya mewarisi `.button` — pil biru penuh. Di
 *    halaman Pasokan & Kebutuhan, "Tutup" jadi elemen paling berteriak di kartu
 *    padahal tugasnya hanya menutup rincian. Karena itu kontraknya diuji dari
 *    CSS: selama kelas ini tidak ada, cacat yang sama bisa muncul lagi tanpa
 *    satu pun tes merah.
 *
 * 2) Judul sub-bagian "Batch" memakai ukuran judul kartu (16 px) dan bobot
 *    bawaan h4 (700), sehingga ia lebih besar daripada judul kartu induknya
 *    ("Jakarta · telur", 14 px/600). Label sub-bagian di konsol ini selalu
 *    berbentuk label mikro: 12 px, 700, KAPITAL, tinta redup — pola yang sama
 *    dengan `agenda-group-title` dan kepala panel Governance.
 */
const AKAR = join(__dirname, "..");

function blok(berkas: string, selektor: string): string {
  const isi = readFileSync(join(AKAR, berkas), "utf8");
  // Blok pertama yang cocok; deklarasi di dalamnya tidak boleh memuat `}`.
  const pola = new RegExp(
    `${selektor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`
  );
  const cocok = pola.exec(isi);
  expect(cocok, `blok ${selektor} tidak ada di ${berkas}`).toBeTruthy();
  return cocok![1];
}

describe("kelas button-quiet benar-benar dideklarasikan", () => {
  it("ada sebagai kontrol tenang: permukaan putih, garis, tinta biasa", () => {
    const isi = blok("app/globals.css", ".button-quiet");
    expect(isi).toContain("background: var(--surface)");
    expect(isi).toContain("color: var(--ink)");
    expect(isi).toContain("border-color: var(--line)");
  });

  it("tidak mengisi warna aksen — itu tugas tombol utama", () => {
    const isi = blok("app/globals.css", ".button-quiet");
    expect(isi).not.toContain("var(--accent-strong)");
    expect(isi).not.toContain("var(--accent)");
  });
});

describe("label sub-bagian Batch memakai bahasa label mikro", () => {
  const isi = () => blok("components/SupplyDemandPanel.module.css", ".batches h4");

  it("turun ke lantai label (12 px), bukan ukuran judul kartu", () => {
    const deklarasi = isi();
    expect(deklarasi).toContain("font-size: var(--fs-1)");
    expect(deklarasi).not.toContain("var(--fs-4)");
  });

  it("kapital, tebal, dan tinta redup seperti label kelompok lain", () => {
    const deklarasi = isi();
    expect(deklarasi).toContain("text-transform: uppercase");
    expect(deklarasi).toContain("font-weight: 700");
    expect(deklarasi).toContain("color: var(--ink-muted)");
  });
});
