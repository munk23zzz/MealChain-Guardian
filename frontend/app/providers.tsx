"use client";

/**
 * Provider React Query (Rules.md §3). Client dibuat sekali per sesi browser
 * dengan useState — bukan di module scope — supaya tidak dibagi antar pengguna
 * saat server-render dan tidak dibuat ulang setiap render.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { makeQueryClient } from "../lib/query";
import { daftarkanPenyegar } from "../lib/refresh";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(makeQueryClient);
  // Setiap permintaan TULIS yang berhasil menyegarkan SEMUA query data (lihat
  // `lib/refresh.ts`). Didaftarkan di sini karena hanya provider yang memegang
  // QueryClient; komponen tidak perlu (dan tidak boleh) mengurusnya sendiri.
  useEffect(() => {
    daftarkanPenyegar(() => {
      void client.invalidateQueries();
    });
    return () => daftarkanPenyegar(null);
  }, [client]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
