"use client";

// PeriodPicker — penyaring periode 1/7/30 hari (dokumen 06 §1).
//
// Memakai `FEED_WINDOWS` yang sama dengan pemilih periode di tab Rekomendasi,
// supaya "7 hari" tidak pernah berarti dua hal berbeda di aplikasi ini. Nilai
// yang dipilih diteruskan ke `GET /decisions?window=…` lewat hook pemanggil —
// komponen ini tidak memotong data sendiri.

import { FEED_WINDOWS, feedWindowHint, type FeedWindowKey } from "../lib/decisions-window";

export default function PeriodPicker({
  value,
  onChange,
}: {
  value: FeedWindowKey;
  onChange: (value: FeedWindowKey) => void;
}) {
  return (
    <div
      className="kpi-period aa-period"
      role="group"
      aria-label="Periode keputusan"
    >
      <span className="kpi-period-label">Periode:</span>
      {FEED_WINDOWS.map((w) => {
        const aktif = w.key === value;
        return (
          <button
            key={w.key}
            type="button"
            className={`commodity-pill kpi-period-pill${aktif ? " is-active" : ""}`}
            data-window={w.key}
            aria-pressed={aktif}
            title={w.hint}
            onClick={() => onChange(w.key)}
          >
            {w.label}
          </button>
        );
      })}
      <span className="feed-period-hint">{feedWindowHint(value)}</span>
    </div>
  );
}
