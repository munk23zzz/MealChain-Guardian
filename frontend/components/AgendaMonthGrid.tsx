"use client";

// Grid bulan kalender agenda — dipakai DUA tempat: kartu "Kalender agenda" di
// tab "Hari Ini" dan popup pemilih tanggal (permintaan pemilik 2026-10-17).
// Dipisah supaya bentuk grid tidak bisa berbeda antara keduanya: 42 sel mulai
// Senin, `data-date` + `data-activity` sebagai penanda hari bercatatan, dan
// `aria-label` bertanggal lengkap ("Sabtu, 17 Oktober 2026, 2 catatan").
//
// Komponen ini TIDAK memanggil API dan tidak menyimpan state: data + bulan
// masuk lewat props dari halaman (lihat tests/agenda-wiring.test.ts).

import {
  AGENDA_WEEKDAY_HEADERS,
  activityOf,
  formatDayLabel,
  monthGrid,
  type AgendaPayload,
} from "../lib/agenda";

export default function AgendaMonthGrid({
  agenda,
  year,
  month,
  selected,
  today,
  onSelect,
  ariaLabel,
  variant = "card",
}: {
  agenda: AgendaPayload;
  year: number;
  month: number;
  selected: string;
  today?: string;
  onSelect: (date: string) => void;
  ariaLabel: string;
  /** "popup" = versi di dalam jendela pemilih tanggal (sel lebih rapat). */
  variant?: "card" | "popup";
}) {
  const cells = monthGrid(year, month);

  return (
    <div
      className={variant === "popup" ? "agenda-grid agenda-grid-popup" : "agenda-grid"}
      role="grid"
      aria-label={ariaLabel}
    >
      {AGENDA_WEEKDAY_HEADERS.map((nama) => (
        <span key={nama} className="agenda-weekday" aria-hidden="true">
          {nama}
        </span>
      ))}
      {cells.map((sel) => {
        const activity = activityOf(agenda, sel.date);
        const aktif = sel.date === selected;
        const kelas = [
          "agenda-cell",
          sel.inMonth ? "" : "agenda-cell-outer",
          aktif ? "agenda-cell-active" : "",
          sel.date === today ? "agenda-cell-today" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <button
            key={sel.date}
            type="button"
            role="gridcell"
            className={kelas}
            data-date={sel.date}
            data-activity={activity}
            aria-current={aktif}
            aria-label={`${formatDayLabel(sel.date)}${
              activity ? `, ${activity} catatan` : ", tidak ada catatan"
            }`}
            onClick={() => onSelect(sel.date)}
          >
            <span className="agenda-day">{sel.day}</span>
            <span className="agenda-dots" aria-hidden="true">
              {Array.from({ length: Math.min(activity, 4) }, (_, i) => (
                <i key={i} className="agenda-dot" />
              ))}
            </span>
          </button>
        );
      })}
    </div>
  );
}
