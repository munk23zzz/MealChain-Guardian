import type { Metadata } from "next";

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
      <body>{children}</body>
    </html>
  );
}
