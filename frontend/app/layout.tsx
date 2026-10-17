import type { Metadata } from "next";
import "./globals.css";

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
