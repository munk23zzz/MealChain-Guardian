"use client";

// Kalender agenda harian (langkah 2, permintaan pemilik 2026-10-16).
//
// Kenapa kalender ini ada: tab "Hari Ini" adalah halaman harian tanpa pemilih
// hari — seluruh kartunya dihitung dari "sekarang". Kalender ini memberi dimensi
// yang hilang: pilih tanggal → lihat rencana menu, kiriman, limbah, pasokan,
// harga, batch kedaluwarsa, dan keputusan hari itu (sumber: GET /agenda).
//
// Komponen ini TIDAK memanggil API dan tidak menyimpan bulan/hari terpilih:
// keduanya milik halaman (lib/hooks/useAgenda.ts). Kalau state disimpan di sini,
// rentang yang diminta ke server dan penanda "hari aktif" bisa berasal dari dua
// sumber berbeda.
//
// Aturan tampilan yang dipegang: bagian tanpa catatan menulis "tidak ada
// catatan", TIDAK PERNAH "0 porsi"/"0 kg" — angka nol yang tampak terukur padahal
// tidak ada datanya adalah hal yang dilarang di repo ini.

import {
  AGENDA_NO_DATA,
  AGENDA_WEEKDAY_HEADERS,
  activityOf,
  agendaRows,
  dayOf,
  formatDayLabel,
  monthGrid,
  monthTitle,
  type AgendaPayload,
} from "../lib/agenda";

type Props = {
  agenda: AgendaPayload;
  loading?: boolean;
  error?: string | null;
  year: number;
  month: number;
  selected: string;
  onSelect: (date: string) => void;
  onShiftMonth: (delta: number) => void;
  onRetry?: () => void;
  /** Tanggal "hari ini" menurut WIB (dari halaman) — dihindari dihitung di sini
   *  supaya HTML server dan render klien tidak berbeda. */
  today?: string;
};

export default function TodayAgendaCalendar({
  agenda,
  loading = false,
  error = null,
  year,
  month,
  selected,
  onSelect,
  onShiftMonth,
  onRetry,
  today,
}: Props) {
  const cells = monthGrid(year, month);
  const hari = dayOf(agenda, selected);
  const rows = hari ? agendaRows(hari) : [];

  return (
    <article className="card agenda-calendar">
      <header className="agenda-head">
        <div>
          <h2>Kalender agenda</h2>
          <p className="agenda-sub">
            Pilih tanggal untuk melihat rencana menu, kiriman, limbah, dan keputusan
            hari itu. Titik menandai hari yang punya catatan.
          </p>
        </div>
        <div className="agenda-nav">
          <button
            type="button"
            className="agenda-nav-btn"
            aria-label="Bulan sebelumnya"
            onClick={() => onShiftMonth(-1)}
          >
            ‹
          </button>
          <span className="agenda-month">{monthTitle(year, month)}</span>
          <button
            type="button"
            className="agenda-nav-btn"
            aria-label="Bulan berikutnya"
            onClick={() => onShiftMonth(1)}
          >
            ›
          </button>
          {today ? (
            <button
              type="button"
              className="agenda-today"
              onClick={() => onSelect(today)}
            >
              Hari ini
            </button>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="agenda-error" role="alert">
          <span>{error}</span>
          {onRetry ? (
            <button type="button" className="agenda-retry" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="agenda-grid" role="grid" aria-label="Kalender agenda harian">
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

      <section className="agenda-panel">
        <h3>{formatDayLabel(selected)}</h3>
        {loading ? (
          <p className="agenda-muted">Memuat agenda…</p>
        ) : rows.length === 0 ? (
          <p className="agenda-muted">{AGENDA_NO_DATA}</p>
        ) : (
          <dl className="agenda-rows">
            {rows.map((row) => (
              <div className="agenda-row" key={row.label}>
                <dt>{row.label}</dt>
                <dd className={row.available ? "" : "agenda-none"}>
                  {row.available ? row.value : AGENDA_NO_DATA}
                  {row.hint ? <small className="agenda-hint"> · {row.hint}</small> : null}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </article>
  );
}
