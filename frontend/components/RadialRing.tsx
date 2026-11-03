"use client";

// Satu cincin (ring) untuk grafik Overview: busur = bagian dari acuan,
// lingkaran putus-putus = acuan penuh (100%). Dipakai oleh dua kartu Overview
// supaya "kecukupan pasokan" (per komoditas) dan "surplus wilayah lain"
// (per wilayah) tampil dengan satu bahasa bentuk yang sama.
//
// Aturan yang dijaga di sini:
// - Angka yang tercetak di tengah cincin datang dari pemanggil apa adanya
//   (tidak diformat ulang di sini) — server tetap satu-satunya sumber angka.
// - Busur dibatasi 0–100%: nilai >100% digambar mentok di lingkaran penuh dan
//   ditandai cincin tipis di luarnya, bukan melampaui kotak.
// - Warna busur memakai `--ac-bar` dari kelas tone yang sama dengan grafik
//   batang (`ac-tone-*`), jadi kontras grafik tetap 3:1 dan teks tetap 4,5:1.
import type { CSSProperties, ReactNode } from "react";

/** Keliling lingkaran r=40 di viewBox 100×100 — dipakai untuk dasharray. */
const R = 40;
export const RING_CIRCUMFERENCE = 2 * Math.PI * R;

const clampPct = (pct: number): number => {
  if (!Number.isFinite(pct)) return 0;
  return Math.max(0, Math.min(100, pct));
};

export type RadialRingProps = {
  /** Panjang busur 0–100. Nilai >100 digambar penuh + penanda luber. */
  pct: number;
  /** Suffix kelas tone: aman | tinjau | bahaya | netral. */
  tone?: string;
  /** Angka utama di tengah cincin, sudah diformat pemanggil (tanpa satuan). */
  value: string;
  /** Satuan kecil di bawah angka (mis. "kg"). */
  unit?: string;
  label: string;
  note?: string;
  badge?: string;
  /** Kalimat penuh untuk pembaca layar + tooltip. */
  aria: string;
  /** true bila angka melebihi acuan (mis. cakupan 260%). */
  over?: boolean;
  /** Cincin kecil untuk kartu padat (lebih dari 6 cincin). */
  small?: boolean;
  /** Cincin besar untuk kartu yang hanya punya 1–2 wilayah. */
  hero?: boolean;
  /** Wilayah di bawah ambang: busur dipucatkan, bukan disembunyikan. */
  muted?: boolean;
  /** Bila diisi, cincin menjadi tombol (mis. pilih komoditas di peta). */
  action?: { label: string; title: string; onClick: () => void };
  /** Indeks untuk animasi masuk berurutan. */
  index: number;
  children?: ReactNode;
};

export default function RadialRing({
  pct,
  tone = "netral",
  value,
  unit,
  label,
  note,
  badge,
  aria,
  over = false,
  small = false,
  hero = false,
  muted = false,
  action,
  index,
}: RadialRingProps) {
  const busur = (clampPct(pct) / 100) * RING_CIRCUMFERENCE;
  const kelas = [
    "rc-item",
    `ac-tone-${tone}`,
    over ? "is-over" : "",
    small ? "is-small" : "",
    hero ? "is-hero" : "",
    muted ? "is-muted" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const gambar = (
    <>
      <span className="rc-fig">
        <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
          {/* Acuan penuh: satu lingkaran putus-putus, padanan "garis acuan"
              pada grafik batang. */}
          <circle className="rc-track" cx="50" cy="50" r={R} />
          {busur > 0 && (
            <circle
              className="rc-arc"
              cx="50"
              cy="50"
              r={R}
              strokeDasharray={`${busur} ${RING_CIRCUMFERENCE - busur}`}
            />
          )}
          {over && <circle className="rc-over" cx="50" cy="50" r={R + 6} />}
        </svg>
        <span className="rc-value">
          <span className="rc-value-angka">{value}</span>
          {unit ? <span className="rc-unit">{unit}</span> : null}
        </span>
      </span>
      <span className="rc-label">
        <span className="rc-name">
          {label}
          {badge ? <span className="sr-badge">{badge}</span> : null}
        </span>
        {note ? <span className="rc-note">{note}</span> : null}
      </span>
    </>
  );

  return (
    <li
      className={kelas}
      style={{ "--i": index } as CSSProperties}
      title={aria}
    >
      {action ? (
        <button
          type="button"
          className="rc-btn"
          aria-label={`${aria}. ${action.label}`}
          title={action.title}
          onClick={action.onClick}
        >
          {gambar}
        </button>
      ) : (
        <div className="rc-static" role="img" aria-label={aria}>
          {gambar}
        </div>
      )}
    </li>
  );
}
