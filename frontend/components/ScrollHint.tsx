"use client";

import { useEffect, useRef, useState } from "react";

import { perluGeser } from "../lib/scroll-hint";

/**
 * Petunjuk geser tabel yang MENGUKUR wadah tabel di kartunya, bukan menebak dari
 * lebar layar (lihat `lib/scroll-hint.ts` untuk alasannya).
 *
 * Dipasang sebagai anak kartu yang sama dengan `.board-table-wrap`, jadi posisinya
 * tidak perlu diberi tahu: wadahnya dicari dari orang tua elemen ini.
 */
export const TEKS_PETUNJUK = "Geser tabel ke samping untuk melihat kolom lain.";

export const KELAS_WADAH_TABEL = "board-table-wrap";

export default function ScrollHint({ teks = TEKS_PETUNJUK }: { teks?: string }) {
  const ref = useRef<HTMLParagraphElement | null>(null);
  const [tampil, setTampil] = useState(false);

  useEffect(() => {
    const el = ref.current;
    const wadah = el?.parentElement?.querySelector<HTMLElement>(`.${KELAS_WADAH_TABEL}`) ?? null;
    if (!el || !wadah) return;

    const ukur = () => setTampil(perluGeser(wadah));
    ukur();

    // Diukur ulang saat wadah ATAU isinya berubah ukuran: data yang baru dimuat bisa
    // mengubah lebar tabel tanpa mengubah ukuran layar.
    const pengamat =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => ukur()) : null;
    if (pengamat) {
      pengamat.observe(wadah);
      if (wadah.firstElementChild) pengamat.observe(wadah.firstElementChild);
    }
    window.addEventListener("resize", ukur);

    return () => {
      pengamat?.disconnect();
      window.removeEventListener("resize", ukur);
    };
  }, []);

  return (
    <p ref={ref} className="board-scroll-hint" data-tampil={tampil ? "true" : "false"}>
      {teks}
    </p>
  );
}
