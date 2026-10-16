import type { Metadata } from "next";
import { Fira_Sans, Fira_Code } from "next/font/google";
import "./globals.css";

import Providers from "./providers";

/* Tipografi Bento Modern (Fase 0, 2026-10-16): Fira Sans (naratif) + Fira Code
   (data/telemetri). Sebelumnya Inter + JetBrains Mono — JetBrains Mono dimuat
   lewat --font-jetbrains tapi tidak pernah dipakai globals.css (mono datang dari
   --font-data = mono sistem). Sekarang --font-data menunjuk Fira Code. */
const firaSans = Fira_Sans({
  subsets: ["latin"],
  variable: "--font-fira-sans",
  weight: ["300", "400", "500", "600", "700"],
});
const firaCode = Fira_Code({
  subsets: ["latin"],
  variable: "--font-fira-code",
  weight: ["400", "500", "600"],
});

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
    <html lang="id" className={`${firaSans.variable} ${firaCode.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
