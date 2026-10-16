"use client";

// Kalender agenda harian (langkah 2, permintaan pemilik 2026-10-16; popup
// pemilih tanggal 2026-10-17).
//
// Kenapa kalender ini ada: tab "Hari Ini" adalah halaman harian tanpa pemilih
// hari — seluruh kartunya dihitung dari "sekarang". Kalender ini memberi dimensi
// yang hilang: pilih tanggal → lihat rencana menu, kiriman, limbah, pasokan,
// harga, batch kedaluwarsa, dan keputusan hari itu (sumber: GET /agenda).
//
// Kepala kalender (2026-10-17): judul bulan bukan lagi teks mati, melainkan
// TOMBOL dengan ikon kalender kecil yang membuka popup pemilih tanggal (dropdown
// Bulan + Tahun + grid hari). Tombol ‹ › dan "Hari ini" tetap ada untuk langkah
// cepat. Bulan DRAFT popup dimiliki halaman, bukan komponen: rentang draft
// itulah yang diminta ke server.
//
// Komponen ini TIDAK memanggil API dan tidak menyimpan bulan/hari terpilih:
// keduanya milik halaman (lib/hooks/useAgenda.ts). Kalau state disimpan di sini,
// rentang yang diminta ke server dan penanda "hari aktif" bisa berasal dari dua
// sumber berbeda.
//
// Aturan tampilan yang dipegang: bagian tanpa catatan menulis "tidak ada
// catatan", TIDAK PERNAH "0 porsi"/"0 kg" — angka nol yang tampak terukur padahal
// tidak ada datanya adalah hal yang dilarang di repo ini.
//
// Grid hari dipakai bersama popup lewat `AgendaMonthGrid`, jadi bentuk sel
// (42 sel mulai Senin, `data-date`/`data-activity`, aria-label bertanggal
// lengkap) tidak bisa berbeda antara kartu dan popup.

import { useRef } from "react";

import {
  AGENDA_NO_DATA,
  agendaRows,
  dayOf,
  formatDayLabel,
  monthTitle,
  type AgendaPayload,
} from "../lib/agenda";
import AgendaDatePicker, { type AgendaPickerProps } from "./AgendaDatePicker";
import AgendaMonthGrid from "./AgendaMonthGrid";
import { CalendarIcon } from "./NavIcon";

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
  /** Popup pemilih tanggal: bulan draft, datanya, dan aksinya (dari halaman). */
  picker: AgendaPickerProps;
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
  picker,
}: Props) {
  const hari = dayOf(agenda, selected);
  const rows = hari ? agendaRows(hari) : [];
  // Fokus dikembalikan ke tombol pemicu saat popup ditutup. Popup butuh ref
  // eksplisit: peramban yang tidak memfokuskan tombol saat diklik tidak bisa
  // diandalkan lewat document.activeElement.
  const triggerRef = useRef<HTMLButtonElement | null>(null);

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
          <button
            ref={triggerRef}
            type="button"
            className="agenda-month-btn"
            aria-haspopup="dialog"
            aria-expanded={picker.open}
            aria-label={`Pilih bulan dan tahun — sekarang ${monthTitle(year, month)}`}
            title="Pilih bulan & tahun"
            onClick={picker.onOpen}
          >
            <CalendarIcon />
            <span className="agenda-month">{monthTitle(year, month)}</span>
          </button>
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

      <AgendaMonthGrid
        agenda={agenda}
        year={year}
        month={month}
        selected={selected}
        today={today}
        onSelect={onSelect}
        ariaLabel="Kalender agenda harian"
      />

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

      <AgendaDatePicker
        open={picker.open}
        month={picker.month}
        years={picker.years}
        agenda={picker.agenda}
        loading={picker.loading}
        error={picker.error}
        today={picker.today}
        selected={picker.selected}
        onClose={picker.onClose}
        onShiftMonth={picker.onShiftMonth}
        onSetMonth={picker.onSetMonth}
        onSelect={picker.onSelect}
        onToday={picker.onToday}
        onRetry={picker.onRetry}
        returnFocusRef={triggerRef}
      />
    </article>
  );
}
