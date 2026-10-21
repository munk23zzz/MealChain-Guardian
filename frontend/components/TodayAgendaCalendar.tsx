"use client";

// Agenda harian (desain ulang "Hari Ini", 2026-10-17 — permintaan pemilik:
// "hapus untuk kalender agenda yang yang bukan pop up namun untuk informasinya
// tetap di pakai ... supaya lebih mudah di gunakan oleh user").
//
// Yang BERUBAH: grid bulan 42 sel di kartu ini DIHAPUS. Kepala kartu menyisakan
// pemicu ikon kecil (membuka popup pemilih tanggal), tombol ‹ › yang kini
// memindahkan SATU HARI, dan "Hari ini".
//
// Kenapa arah ini (rujukan riset, docs/verification/hari-ini-desain-ulang.md):
// pola "Agenda hybrid" di uxpatterns.dev — kalender dipasangkan dengan daftar
// kejadian linear, dipakai saat gambaran umum DAN rincian sama-sama penting —
// plus Apple HIG "compact" date picker untuk kontrol tanggal ringkas. Grid bulan
// besar memakan tinggi layar untuk hal yang jarang dipakai (memilih tanggal jauh
// di depan), sementara yang dicari pengguna tiap hari adalah ISI hari itu.
// Tanggal jauh tetap terjangkau lewat popup yang punya dropdown bulan & tahun.
//
// Komponen ini TIDAK memanggil API dan tidak menyimpan hari terpilih: keduanya
// milik halaman (lib/hooks/useAgenda.ts). Kalau state disimpan di sini, rentang
// yang diminta ke server dan hari yang ditampilkan bisa berasal dari dua sumber
// berbeda.
//
// Aturan tampilan yang dipegang: bagian tanpa catatan menulis "tidak ada
// catatan", TIDAK PERNAH "0 porsi"/"0 kg" — angka nol yang tampak terukur padahal
// tidak ada datanya adalah hal yang dilarang di repo ini.
//
// Grid hari tetap hidup di dalam POPUP lewat `AgendaMonthGrid`: pemilih tanggal
// masih perlu melihat sebulan sekaligus untuk memilih tanggal, jadi bentuk
// selnya tidak boleh hilang.

import { useRef } from "react";

import {
  AGENDA_NO_DATA,
  agendaGroups,
  dayOf,
  formatDayLabel,
  monthOf,
  monthTitle,
  type AgendaPayload,
} from "../lib/agenda";
import AgendaDatePicker, { type AgendaPickerProps } from "./AgendaDatePicker";
import { CalendarIcon } from "./NavIcon";

type Props = {
  agenda: AgendaPayload;
  loading?: boolean;
  error?: string | null;
  /** Tanggal terpilih (`YYYY-MM-DD`) — milik halaman. */
  selected: string;
  onSelect: (date: string) => void;
  onShiftDay: (delta: number) => void;
  onRetry?: () => void;
  /** Tanggal "hari ini" menurut WIB (dari halaman) — dihindari dihitung di sini
   *  supaya HTML server dan render klien tidak berbeda. */
  today?: string;
  /** Langkah hari ‹ › dimatikan di tepi rentang data (`clampDayStep`) supaya
   *  pengguna tidak dibawa ke hari yang datanya memang tidak ada. */
  prevDisabled?: boolean;
  nextDisabled?: boolean;
  /** Popup pemilih tanggal: bulan draft, datanya, dan aksinya (dari halaman). */
  picker: AgendaPickerProps;
};

export default function TodayAgendaCalendar({
  agenda,
  loading = false,
  error = null,
  selected,
  onSelect,
  onShiftDay,
  onRetry,
  today,
  prevDisabled = false,
  nextDisabled = false,
  picker,
}: Props) {
  const hari = dayOf(agenda, selected);
  const kelompok = hari ? agendaGroups(hari) : [];
  const bulan = monthOf(selected);
  // Fokus dikembalikan ke tombol pemicu saat popup ditutup. Popup butuh ref
  // eksplisit: peramban yang tidak memfokuskan tombol saat diklik tidak bisa
  // diandalkan lewat document.activeElement.
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  return (
    <article className="card agenda-calendar" id="today-agenda" tabIndex={-1}>
      <header className="agenda-head">
        <div className="agenda-head-text">
          <h2>Agenda harian</h2>
          <p className="agenda-sub">
            Rencana menu, pasokan, limbah, dan keputusan pada hari terpilih.
          </p>
        </div>
        <div className="agenda-nav">
          <button
            type="button"
            className="agenda-nav-btn"
            aria-label="Hari sebelumnya"
            title="Hari sebelumnya"
            disabled={prevDisabled}
            onClick={() => onShiftDay(-1)}
          >
            ‹
          </button>
          <button
            ref={triggerRef}
            type="button"
            className="agenda-month-btn"
            aria-haspopup="dialog"
            aria-expanded={picker.open}
            aria-label={`Pilih tanggal — sekarang ${monthTitle(bulan.year, bulan.month)}`}
            title="Pilih tanggal"
            onClick={picker.onOpen}
          >
            <CalendarIcon />
            <span className="agenda-month">{monthTitle(bulan.year, bulan.month)}</span>
          </button>
          <button
            type="button"
            className="agenda-nav-btn"
            aria-label="Hari berikutnya"
            title="Hari berikutnya"
            disabled={nextDisabled}
            onClick={() => onShiftDay(1)}
          >
            ›
          </button>
          {today ? (
            <button
              type="button"
              className="agenda-today"
              disabled={selected === today}
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

      <section className="agenda-panel" aria-label={`Agenda ${formatDayLabel(selected)}`}>
        <h3 className="agenda-day-title">{formatDayLabel(selected)}</h3>
        {loading ? (
          <p className="agenda-muted">Memuat agenda…</p>
        ) : kelompok.length === 0 ? (
          <p className="agenda-muted">{AGENDA_NO_DATA}</p>
        ) : (
          <div className="agenda-groups">
            {kelompok.map((grup) => (
              <section className="agenda-group" key={grup.title}>
                <h4 className="agenda-group-title">{grup.title}</h4>
                <dl className="agenda-rows">
                  {grup.rows.map((row) => (
                    <div className="agenda-row" key={row.label}>
                      <dt>{row.label}</dt>
                      <dd className={row.available ? "" : "agenda-none"}>
                        {row.available ? row.value : AGENDA_NO_DATA}
                        {row.hint ? <small className="agenda-hint"> · {row.hint}</small> : null}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
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
