"use client";

/**
 * Agenda harian (GET /agenda) lewat React Query (Rules.md §3) — kalender di tab
 * "Hari Ini".
 *
 * Kenapa hook terpisah dari `useToday`: jadwal hidupnya berbeda. `useToday`
 * memantau keadaan SEKARANG (batch mendekati kedaluwarsa, rantai audit) dan
 * menyegarkan tiap 60 detik; agenda adalah potret HISTORIS satu bulan, jadi ia
 * hanya diambil saat rentangnya berubah — tidak ada polling yang membakar
 * jaringan untuk data yang tak berubah.
 *
 * Pemuatannya dibatasi `shouldLoadKpi` (tab "Hari Ini" dan tab KPI) supaya
 * membuka tab lain tidak memanggil endpoint ini tanpa alasan.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchAgenda } from "../api";
import { shouldLoadKpi } from "../kpi";
import { errorMessage, queryKeys } from "../query";

export function useAgenda(
  token: string | null,
  scope: string,
  tab: string,
  range: { start: string; end: string },
  /**
   * Saklar tambahan dari halaman. Dipakai popup pemilih tanggal: rentang bulan
   * DRAFT hanya diminta saat popup terbuka, jadi membuka tab "Hari Ini" tidak
   * memuat dua bulan sekaligus.
   */
  enabled: boolean = true,
) {
  const aktif = shouldLoadKpi(tab);
  return useQuery({
    queryKey: queryKeys.agenda(scope, range.start, range.end),
    queryFn: () => fetchAgenda(token as string, range.start, range.end),
    enabled: Boolean(token) && aktif && enabled && Boolean(range.start),
    // Data historis: tahan lama, tapi tetap disegarkan saat jendela fokus.
    staleTime: 5 * 60_000,
  });
}

export function agendaErrorText(error: unknown): string | null {
  const pesan = errorMessage(error);
  return pesan ?? (error ? "gagal memuat agenda harian" : null);
}
