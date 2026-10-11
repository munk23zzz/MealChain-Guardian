"use client";

/**
 * Provider React Query (Rules.md §3). Client dibuat sekali per sesi browser
 * dengan useState — bukan di module scope — supaya tidak dibagi antar pengguna
 * saat server-render dan tidak dibuat ulang setiap render.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { makeQueryClient } from "../lib/query";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(makeQueryClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
