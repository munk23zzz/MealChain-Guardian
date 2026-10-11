// Pembungkus tes: halaman kini memakai React Query (Rules.md §3), dan
// renderToStaticMarkup menjalankan badan komponen — jadi provider WAJIB ada.
// Client dibuat baru per pemanggilan supaya cache tidak bocor antar tes.
import { QueryClientProvider } from "@tanstack/react-query";

import { makeQueryClient } from "../lib/query";

export function withProviders(node: React.ReactNode) {
  return (
    <QueryClientProvider client={makeQueryClient()}>{node}</QueryClientProvider>
  );
}
