"use client";

/**
 * Pemilih kiriman untuk disorot di peta (Arah C riset 16 Okt 2026).
 *
 * Kenapa ada tombol pemilih padahal peta bisa diklik: garis di kanvas MapLibre
 * TIDAK bisa dicapai keyboard maupun pembaca layar. Pemilih ini jalur setara
 * untuk keduanya — pilihan aktif dibawa `aria-pressed`, dan teksnya memuat nama
 * kiriman + keadaannya, bukan ikon tanpa nama.
 *
 * Tidak ada penyaji angka baru di sini: tombol hanya menyebut nama dan keadaan
 * (angka panjangnya milik kartu kiriman di bawah peta).
 */
import { FOCUS_ALL, type FocusOption } from "../lib/route-focus";

export default function RouteFocusPicker({
  options,
  focused,
  total,
  onFocus,
}: {
  options: readonly FocusOption[];
  /** Id yang sedang disorot, atau `null` untuk "semua kiriman". */
  focused: string | null;
  /** Jumlah seluruh kiriman (dipakai pada tombol "Semua", bukan kata tanpa angka). */
  total: number;
  onFocus: (id: string) => void;
}) {
  if (options.length === 0) return null;
  return (
    <div className="route-focus" role="group" aria-label="Pilih kiriman yang disorot di peta">
      <span className="route-focus-label">Pilih kiriman:</span>
      <button
        type="button"
        className={`commodity-pill route-focus-pill${focused ? "" : " is-active"}`}
        aria-pressed={focused === null}
        onClick={() => onFocus(FOCUS_ALL)}
      >
        Semua ({total})
      </button>
      {options.map((option) => {
        const aktif = option.id === focused;
        return (
          <button
            key={option.batchId ? `${option.id}#${option.batchId}` : option.id}
            type="button"
            className={`commodity-pill route-focus-pill route-focus-pill-${option.tone}${aktif ? " is-active" : ""}`}
            aria-pressed={aktif}
            onClick={() => onFocus(option.id)}
          >
            <span className="route-focus-name">{option.label}</span>
            <span className="route-focus-state">{option.state}</span>
          </button>
        );
      })}
    </div>
  );
}
