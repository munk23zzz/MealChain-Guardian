"use client";

// Popup pemilih tanggal (permintaan pemilik 2026-10-17).
//
// Kenapa ada: kalender agenda sebelumnya hanya punya tombol ‹ › dan judul bulan
// yang MATI, jadi melompat dari Okt 2026 ke Okt 2025 berarti 12 klik — keluhan
// paling umum pada date picker (judul bulan/tahun harus bisa diklik, bukan
// dipaksa lewat chevron). Popup ini menambah dimensi yang hilang: pilih BULAN
// dan TAHUN langsung, lalu klik tanggalnya.
//
// Yang dijaga:
// - memakai cangkang `Popup` yang sudah ada (role="dialog", jebakan fokus,
//   Escape, portal, fokus kembali ke pemicu) — tidak ada bahasa visual baru;
// - grid hari memakai `AgendaMonthGrid` yang sama dengan kartu, jadi penanda
//   "hari yang punya catatan" (`data-activity`) tidak bisa berbeda;
// - saat bulan draft masih dimuat, yang tampil adalah status MEMUAT, bukan grid
//   kosong yang akan terbaca sebagai "bulan ini tidak punya catatan";
// - komponen ini tidak memuat data sendiri: bulan draft, payload, dan tahun
//   yang tersedia semuanya milik halaman (`useAgenda` di app/page.tsx);
// - memilih tanggal hanya MEMBERI TAHU halaman (`onSelect`); yang menutup popup
//   adalah halaman, supaya bulan & hari terpilih tetap satu sumber.

import type { RefObject } from "react";

import { monthChoices, type AgendaPayload } from "../lib/agenda";
import AgendaMonthGrid from "./AgendaMonthGrid";
import { LoadingState } from "./LoadingState";
import Popup from "./Popup";

export type AgendaPickerProps = {
  open: boolean;
  /** Bulan DRAFT yang sedang dipilih di popup (bukan bulan grid di kartu). */
  month: { year: number; month: number };
  /** Tahun yang boleh dipilih — dihitung halaman dari rentang data. */
  years: number[];
  /** Payload `GET /agenda` untuk bulan draft. */
  agenda: AgendaPayload;
  loading: boolean;
  error: string | null;
  /** Tanggal "hari ini" menurut WIB (dari halaman); kosong = tombol disembunyikan. */
  today?: string;
  /** Hari terpilih menurut halaman — dipakai menandai sel aktif. */
  selected: string;
  onOpen: () => void;
  onClose: () => void;
  onShiftMonth: (delta: number) => void;
  onSetMonth: (bulan: { year: number; month: number }) => void;
  onSelect: (date: string) => void;
  onToday: () => void;
  onRetry: () => void;
  /** Tombol pemicu di header kartu — tujuan fokus saat popup ditutup. */
  returnFocusRef?: RefObject<HTMLElement | null>;
};

export default function AgendaDatePicker({
  open,
  onClose,
  month,
  years,
  agenda,
  loading,
  error,
  today,
  selected,
  onShiftMonth,
  onSetMonth,
  onSelect,
  onToday,
  onRetry,
  returnFocusRef,
}: Omit<AgendaPickerProps, "onOpen">) {
  const tahunTersedia = years.length ? `${years[0]}–${years[years.length - 1]}` : "—";

  return (
    <Popup
      open={open}
      onClose={onClose}
      title="Pilih tanggal"
      labelledBy="agenda-picker-title"
      description={`Pilih bulan dan tahun, lalu klik tanggalnya. Tahun yang tersedia ${tahunTersedia}.`}
      returnFocusRef={returnFocusRef}
    >
      <div className="agenda-picker">
        <div className="agenda-picker-nav">
          <button
            type="button"
            className="agenda-nav-btn"
            aria-label="Bulan sebelumnya"
            onClick={() => onShiftMonth(-1)}
          >
            ‹
          </button>
          <label className="agenda-picker-field">
            <span>Bulan</span>
            <select
              aria-label="Bulan"
              value={month.month}
              onChange={(e) => onSetMonth({ year: month.year, month: Number(e.target.value) })}
            >
              {monthChoices().map((pilihan) => (
                <option key={pilihan.value} value={pilihan.value}>
                  {pilihan.label}
                </option>
              ))}
            </select>
          </label>
          <label className="agenda-picker-field">
            <span>Tahun</span>
            <select
              aria-label="Tahun"
              value={month.year}
              onChange={(e) => onSetMonth({ year: Number(e.target.value), month: month.month })}
            >
              {years.map((tahun) => (
                <option key={tahun} value={tahun}>
                  {tahun}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="agenda-nav-btn"
            aria-label="Bulan berikutnya"
            onClick={() => onShiftMonth(1)}
          >
            ›
          </button>
        </div>

        {error ? (
          <div className="agenda-error" role="alert">
            <span>{error}</span>
            <button type="button" className="agenda-retry" onClick={onRetry}>
              Coba lagi
            </button>
          </div>
        ) : null}

        {agenda ? (
          <AgendaMonthGrid
            agenda={agenda}
            year={month.year}
            month={month.month}
            selected={selected}
            today={today}
            onSelect={onSelect}
            ariaLabel="Pilih tanggal pada kalender"
            variant="popup"
          />
        ) : loading ? (
          <p className="agenda-muted">
            <LoadingState label="Memuat agenda bulan ini" /> Memuat agenda bulan ini…
          </p>
        ) : null}

        <p className="agenda-picker-note">
          Titik menandai hari yang punya catatan — hari kosong dibiarkan tanpa titik,
          bukan diisi angka nol yang bisa terbaca sebagai hasil pengukuran.
        </p>

        <div className="agenda-picker-actions">
          {today ? (
            <button
              type="button"
              className="button button-secondary agenda-picker-today"
              onClick={onToday}
            >
              Hari ini
            </button>
          ) : null}
          <button
            type="button"
            className="button button-secondary agenda-picker-close"
            onClick={onClose}
          >
            Tutup
          </button>
        </div>
      </div>
    </Popup>
  );
}
