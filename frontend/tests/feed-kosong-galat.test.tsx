// Tahap 5 redesign Recommendation Feed (30 Okt 2026): keadaan kosong = sebab +
// aksi utama + aksi sekunder, dan galat diumumkan (`role="alert"`).
//
// Kenapa komponennya dipisah: `app/page.tsx` adalah komponen klien 2.500+ baris
// yang butuh sesi login dan seluruh query hidup. Blok keadaan kosong dipindah ke
// `components/FeedEmptyState.tsx` supaya tiga syarat di atas bisa diuji sebagai
// RENDER, bukan hanya lewat grep sumber.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import fs from "node:fs";
import path from "node:path";

import FeedEmptyState from "../components/FeedEmptyState";

const AKAR = path.resolve(__dirname, "..");
const HALAMAN = fs.readFileSync(path.join(AKAR, "app/page.tsx"), "utf8");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8");

function render(props: Partial<Parameters<typeof FeedEmptyState>[0]> = {}) {
  return renderToStaticMarkup(
    <FeedEmptyState
      filterActive={false}
      windowKey="7d"
      windowLabel="7 hari terakhir"
      totalInWindow={17}
      onResetFilter={() => {}}
      onWidenWindow={() => {}}
      onRetry={() => {}}
      {...props}
    />
  );
}

describe("Tahap 5 — keadaan kosong & galat Recommendation Feed", () => {
  it("tiga bagian: sebab, aksi utama, aksi sekunder", () => {
    const html = render();
    expect(html).toContain('data-empty-state="feed"');
    expect(html).toContain('class="feed-empty-sebab"');
    expect((html.match(/class="feed-empty-aksi"/g) ?? []).length).toBe(1);
    expect(html).toContain('data-aksi="utama"');
    expect(html).toContain('data-aksi="sekunder"');
    // Aksi utama menyebut jalan keluar yang paling mungkin, sekunder yang kedua.
    expect(html).toContain("Lihat 1 bulan terakhir");
    expect(html).toContain("Muat ulang");
    // Urutan: utama sebelum sekunder (bukan dua tombol setara).
    expect(html.indexOf('data-aksi="utama"')).toBeLessThan(
      html.indexOf('data-aksi="sekunder"')
    );
  });

  it("saat filter aktif, aksi utama mengosongkan filter dan jumlah total disebut", () => {
    const html = render({ filterActive: true });
    expect(html).toContain("Tidak ada rekomendasi yang cocok");
    const utama = html.slice(html.indexOf('data-aksi="utama"'), html.indexOf('data-aksi="sekunder"'));
    expect(utama).toContain("Kosongkan filter");
    // 17 = jumlah rekomendasi pada jendela ini, dioper pemanggil (bukan dihitung ulang).
    expect(html).toContain("seluruh 17 rekomendasi");
    expect(html).toContain("7 hari terakhir");
  });

  it("sebab menyebut periode yang sedang dilihat, bukan kalimat kosong", () => {
    const html = render({ windowKey: "30d", windowLabel: "30 hari terakhir" });
    expect(html).toContain("Tidak ada rekomendasi pada periode");
    expect(html).toContain("30 hari terakhir");
    // Di jendela terlebar tidak ada tawaran "lihat 1 bulan lagi" yang tidak
    // mengubah apa pun: aksi utamanya "Muat ulang".
    const utama = html.slice(html.indexOf('data-aksi="utama"'), html.indexOf('</button>'));
    expect(utama).toContain("Muat ulang");
  });

  it("keadaan kosong diumumkan ke pembaca layar", () => {
    expect(render()).toMatch(/data-empty-state="feed"[^>]*role="status"/);
  });

  it("halaman memakai komponen ini; markup lama dan kotak kuning tidak tersisa", () => {
    expect(HALAMAN).toContain("<FeedEmptyState");
    expect(HALAMAN).not.toContain('className="empty-state feed-empty"');
    // Galat muat diumumkan sebagai alert, bukan hanya teks merah.
    expect(HALAMAN).toMatch(/role="alert"[\s\S]{0,300}Gagal memuat data/);
  });

  it("kotak kosong tidak lagi memakai warna peringatan", () => {
    const css = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
    const i = css.indexOf(".feed-empty {");
    expect(i, "aturan .feed-empty tidak ditemukan").toBeGreaterThan(-1);
    const blok = css.slice(css.indexOf("{", i) + 1, css.indexOf("}", i));
    expect(blok).not.toContain("--status-warning");
    expect(blok).toContain("--surface-sunken");
    expect(blok).toContain("var(--line)");
    // Tombol di dalamnya tetap memenuhi target sentuh di layar sentuh.
    expect(css).toContain(".feed-empty-aksi .button { min-height: 44px; }");
  });
});
