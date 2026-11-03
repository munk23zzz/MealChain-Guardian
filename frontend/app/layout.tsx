import type { Metadata } from "next";
import "./globals.css";
import "./theme-ext.css";
// Chrome gelap di dalam kartu peta (2026-10-19). Diimpor TERAKHIR supaya
// menang atas globals.css tanpa menyunting berkas yang dipakai bersama.
import "./map-console.css";
// "Dossier keputusan" — desain ulang halaman Decision & Evidence (20 Okt 2026).
// Diimpor PALING AKHIR dengan alasan yang sama: menang urutan tanpa !important
// dan tanpa menyunting globals.css yang dipakai sesi lain.
import "./evidence-dossier.css";
// Overview P0 (21 Okt 2026): chip provenance, aksi alert, dan baris antrean
// yang bisa diklik. Berkas terpisah agar tidak menambah hunk di globals.css.
import "./overview-p0.css";
// Grafik kecukupan: aturan .supply-adequacy/.sa-* dipisah dari globals.css
// supaya lapisan grafik dapat di-commit tanpa hunk stylesheet bersama.
import "./supply-adequacy.css";
// Overview 28 Okt 2026: "Kecukupan pasokan" (setengah halaman) berdampingan
// dengan panel "Surplus wilayah lain". Diimpor setelah supply-adequacy.css
// karena ia menyusun ulang baris `sa-*` pada kartu yang sempit.
import "./surplus-regions.css";
import "./adequacy-columns.css";
// Cincin Overview: bentuk bagian-dari-acuan untuk kedua kartu (29 Okt 2026).
import "./radial-charts.css";
// Donat komposisi komoditas: satu diagram, satu warna per komoditas.
import "./commodity-donut.css";
import "./agent-activity.css";
// Tombol pil/oval di seluruh halaman (27 Okt 2026, permintaan pemilik).
// Diimpor terakhir dengan alasan yang sama: menang urutan tanpa !important.
import "./tombol-pil.css";
// Riwayat penerimaan barang di halaman Pemasok (Dok 05 §8.5, 29 Okt 2026).
// Berkas terpisah supaya lapisan ini tidak menambah hunk di globals.css.
import "./supplier-receipts.css";
// Ringkasan Pemasok: satu baris KPI (29 Okt 2026) — juga berkas sendiri.
import "./supplier-summary.css";

import Providers from "./providers";

/* Tipografi Bento Modern (Fase 0, 2026-10-16): Fira Sans (naratif) + Fira Code
   (data/telemetri). FONT SELF-HOST (17 Okt 2026): berkas woff2 di /public/fonts.
   next/font/google TIDAK dipakai karena build tanpa jaringan hanya menghasilkan
   fallback Arial.

   @font-face ditulis di sini, bukan di globals.css (3 Nov 2026): url() absolut
   tidak ikut basePath Next, jadi di GitHub Pages (situs di /<repo>/) semua woff2
   404. Dengan prefiks NEXT_PUBLIC_BASE_PATH, jalur font benar di akar maupun di
   sub-path, tanpa mengubah deploy normal. */
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

const FONT_FACES = [
  ["Fira Sans", 400, "fira-sans-latin-400-normal.woff2"],
  ["Fira Sans", 500, "fira-sans-latin-500-normal.woff2"],
  ["Fira Sans", 600, "fira-sans-latin-600-normal.woff2"],
  ["Fira Sans", 700, "fira-sans-latin-700-normal.woff2"],
  ["Fira Code", 400, "fira-code-latin-400-normal.woff2"],
  ["Fira Code", 500, "fira-code-latin-500-normal.woff2"],
  ["Fira Code", 600, "fira-code-latin-600-normal.woff2"],
]
  .map(
    ([famili, bobot, berkas]) =>
      `@font-face{font-family:"${famili}";font-style:normal;font-weight:${bobot};font-display:swap;` +
      `src:url("${BASE_PATH}/fonts/${berkas}") format("woff2")}`
  )
  .join("\n");

export const metadata: Metadata = {
  title: "MealChain Guardian",
  description: "Agentic AI untuk cross-regional food supply balancing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <head>
        <style dangerouslySetInnerHTML={{ __html: FONT_FACES }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
