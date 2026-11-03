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
 *
 * Sejak 20 Okt 2026 daftar ini bisa DILIPAT: begitu pil memakan lebih dari satu
 * baris, hanya satu baris yang tampil dan sebuah segitiga membuka sisanya
 * (permintaan pemilik). Keputusan "perlu dilipat" diukur dari tata letak
 * sungguhan lewat elemen probe — bukan dari jumlah pil, karena satu baris
 * bergantung lebar panel, bukan banyaknya kiriman.
 */
import { useEffect, useRef, useState } from "react";
import { FOCUS_ALL, type FocusOption } from "../lib/route-focus";
import { perluTombolTutup } from "../lib/route-focus-lines";

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
  const [terbuka, setTerbuka] = useState(false);
  const [perluTutup, setPerluTutup] = useState(false);
  const probe = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = probe.current;
    if (!el) return;
    const ukur = () => {
      const tops = Array.from(el.children).map((anak) => (anak as HTMLElement).offsetTop);
      setPerluTutup(perluTombolTutup(tops));
    };
    ukur();
    if (typeof ResizeObserver === "undefined") return;
    // Lebar panel berubah (sidebar dilipat, jendela menyempit) bisa mengubah
    // satu baris menjadi dua — ukuran diulang, bukan dihitung sekali.
    const pantau = new ResizeObserver(ukur);
    pantau.observe(el);
    return () => pantau.disconnect();
  }, [options]);

  if (options.length === 0) return null;

  const tampil = !perluTutup || terbuka;
  const disorot = options.find((option) => option.id === focused)?.label ?? null;

  return (
    <div className="route-focus" role="group" aria-label="Pilih kiriman yang disorot di peta">
      <span className="route-focus-label">Pilih kiriman:</span>
      {perluTutup && (
        <button
          type="button"
          className="route-focus-toggle"
          aria-expanded={terbuka}
          aria-controls="route-focus-list"
          onClick={() => setTerbuka((nilai) => !nilai)}
        >
          {/* Segitiga: mengarah ke kanan saat terlipat, ke bawah saat terbuka.
              Teks tombol ikut berubah, jadi keadaan tidak dibawa ikon saja. */}
          <svg
            className={`route-focus-caret${terbuka ? " is-open" : ""}`}
            viewBox="0 0 12 12"
            aria-hidden="true"
            focusable="false"
          >
            <path
              d="M3 4.5 6 8l3-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {terbuka ? "Ringkas" : disorot ? `Disorot: ${disorot}` : `Tampilkan ${total} kiriman`}
        </button>
      )}
      <div
        id="route-focus-list"
        className={`route-focus-list${tampil ? "" : " is-collapsed"}`}
      >
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
      {/* Probe ukur: salinan pil yang sama, tak terlihat dan tak bisa difokus,
          dirender SELALU (termasuk saat daftar terlipat) supaya pengukuran tetap
          sah setelah dilipat dan saat lebar panel berubah. */}
      <span className="route-focus-probe" aria-hidden="true" ref={probe}>
        <span className="commodity-pill route-focus-pill">Semua ({total})</span>
        {options.map((option) => (
          <span
            key={option.batchId ? `p-${option.id}#${option.batchId}` : `p-${option.id}`}
            className="commodity-pill route-focus-pill"
          >
            <span className="route-focus-name">{option.label}</span>
            <span className="route-focus-state">{option.state}</span>
          </span>
        ))}
      </span>
    </div>
  );
}
