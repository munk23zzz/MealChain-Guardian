"use client";

/**
 * Pager daftar (19 Okt 2026) — dipakai "Daftar pemasok" dan "Papan kiriman".
 *
 * Aturan yang dipaku:
 *   1. `<nav>` berlabel + `aria-current="page"` pada halaman aktif — keadaan
 *      aktif tidak boleh hanya dibedakan warna;
 *   2. rentang "1–10 dari 60" selalu tertulis dan diumumkan (`aria-live`),
 *      jadi pembaca layar tahu potongan mana yang sedang dilihat;
 *   3. tombol Sebelumnya/Berikutnya dinonaktifkan di ujung, bukan disembunyikan
 *      (posisi tombol tidak melompat antar halaman);
 *   4. satu halaman saja → hanya baris rentang, tanpa deretan tombol.
 *
 * Gaya memakai token sistem (tanpa hex baru); target sentuh 44 px di perangkat
 * sentuh/lebar sempit (lihat `.pager-btn` di globals.css).
 */

import { pageSlots, rangeLabel, type Page } from "../lib/pagination";

export default function Pager({
  page,
  onChange,
  label,
}: {
  page: Page<unknown>;
  onChange: (halaman: number) => void;
  /** Nama bagian yang dipaginasi, untuk label navigasi & pembaca layar. */
  label: string;
}) {
  const rentang = rangeLabel(page);

  if (page.pageCount <= 1) {
    return <p className="pager-range pager-range-solo">{rentang}</p>;
  }

  const nomor = pageSlots(page.page, page.pageCount);

  return (
    <nav className="pager" aria-label={`Halaman ${label}`}>
      <p className="pager-range" aria-live="polite">
        {rentang}
      </p>
      <div className="pager-controls">
        <button
          type="button"
          className="pager-btn pager-step"
          onClick={() => onChange(page.page - 1)}
          disabled={!page.hasPrev}
          aria-label="Halaman sebelumnya"
        >
          <span aria-hidden="true">‹</span> Sebelumnya
        </button>
        <ul className="pager-list">
          {nomor.map((n, i) =>
            n === "…" ? (
              <li key={`gap-${i}`} className="pager-gap" aria-hidden="true">
                …
              </li>
            ) : (
              <li key={n}>
                <button
                  type="button"
                  className="pager-btn"
                  onClick={() => onChange(n)}
                  aria-label={`Halaman ${n}`}
                  aria-current={n === page.page ? "page" : undefined}
                >
                  {n}
                </button>
              </li>
            )
          )}
        </ul>
        <button
          type="button"
          className="pager-btn pager-step"
          onClick={() => onChange(page.page + 1)}
          disabled={!page.hasNext}
          aria-label="Halaman berikutnya"
        >
          Berikutnya <span aria-hidden="true">›</span>
        </button>
      </div>
    </nav>
  );
}
