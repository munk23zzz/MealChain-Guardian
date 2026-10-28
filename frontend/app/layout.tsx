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
import "./agent-activity.css";
// Tombol pil/oval di seluruh halaman (27 Okt 2026, permintaan pemilik).
// Diimpor terakhir dengan alasan yang sama: menang urutan tanpa !important.
import "./tombol-pil.css";

import Providers from "./providers";

/* Tipografi Bento Modern (Fase 0, 2026-10-16): Fira Sans (naratif) + Fira Code
   (data/telemetri). FONT SELF-HOST (17 Okt 2026): @font-face ada di globals.css
   dan berkas woff2 di /public/fonts. next/font/google TIDAK dipakai lagi karena
   build tanpa jaringan hanya menghasilkan fallback Arial — terukur di
   .next/static/css: tidak ada __Fira_Sans_<hash>, hanya __Fira_*_Fallback_*. */

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
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
