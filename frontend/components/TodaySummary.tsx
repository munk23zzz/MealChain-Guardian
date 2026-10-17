"use client";

// Strip ringkasan "Hari Ini" (desain ulang 2026-10-17, permintaan pemilik:
// "1 page hari ini harus di desain ulang ui ux nya ... supaya lebih mudah di
// gunakan oleh user").
//
// Strip ini jawaban untuk keluhan "semua kartu sama pentingnya": lima kartu lama
// berbobot sama sehingga tidak ada yang bisa dipastikan dalam satu detik. Di
// sini lima tile berdiri paling atas (status dulu), dan tiap tile adalah TOMBOL
// yang membawa pengguna ke kartunya — jadi ia jalan pintas, bukan hiasan.
//
// Kenapa tombol, bukan <a href="#id">: lompatan ini juga harus MEMINDAHKAN
// FOKUS. Tautan anchor hanya menggulir; pengguna papan tik lalu tertinggal di
// strip dan harus menekan Tab berkali-kali untuk sampai ke baris yang tadi ia
// lihat. Tombol + `jumpToSection` melakukan gulir DAN fokus.
//
// Angka tidak dihitung di sini: tile datang dari `summaryTiles` (lib/today.ts,
// diuji tanpa DOM) supaya aturan "—" jangan sampai ditulis ulang di JSX.

import type { SummaryTile } from "../lib/today";
import { nilaiAngka } from "../lib/today";

/**
 * Gulir ke kartu ber-id `target` lalu pindahkan fokus ke kartu itu.
 * Gulir halus dihormati hanya bila pengguna tidak meminta gerak minimal.
 */
export function jumpToSection(target: string): void {
  if (typeof document === "undefined") return;
  const el = document.getElementById(target);
  if (!el) return;
  const kurangiGerak =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: kurangiGerak ? "auto" : "smooth", block: "start" });
  // Kartu perlu bisa menerima fokus: tanpa tabindex, `focus()` tidak melakukan
  // apa pun dan pengguna papan tik tetap tertinggal di strip.
  if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
}

export default function TodaySummary({
  tiles,
  onJump,
}: {
  tiles: SummaryTile[];
  onJump: (target: string) => void;
}) {
  return (
    <nav className="today-summary" aria-label="Ringkasan hari ini">
      <ul className="today-summary-list">
        {tiles.map((tile) => (
          <li key={tile.key}>
            <button
              type="button"
              className={`today-tile today-tile-${tile.tone}`}
              data-today-target={tile.target}
              aria-label={`${tile.label}: ${tile.value}${
                tile.note ? ` — ${tile.note}` : ""
              }. Lihat kartu ${tile.label}`}
              onClick={() => onJump(tile.target)}
            >
              <span className="today-tile-label">{tile.label}</span>
              <span
                className={`today-tile-value${
                  nilaiAngka(tile.value) ? "" : " today-tile-value--teks"
                }`}
              >
                {tile.value}
              </span>
              {tile.note ? <span className="today-tile-note">{tile.note}</span> : null}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
