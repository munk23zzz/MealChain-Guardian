"use client";

/**
 * Pemilih keputusan (redesign 19 Okt 2026) — pengganti <select> bawaan di
 * halaman Decision & Evidence dan Agent Activity Log.
 *
 * Kenapa diganti: `<select>` tidak bisa menampilkan dua baris per keputusan
 * (jenis + status + waktu + nomor), tidak bisa dicari, dan label panjangnya
 * terpotong di kepala halaman. Yang dipertahankan: kontrak pilihan (nilai =
 * `decision_id`) dan pengelompokan dari `lib/decision-picker.ts` — komponen ini
 * hanya mengubah cara memilih, bukan cara menyusun.
 *
 * Perilaku yang dipaku tes:
 *   1. pemicu menampilkan pilihan aktif (judul + meta), bukan "#id" telanjang;
 *   2. panel tertutup default, klik membuka, klik di luar menutup;
 *   3. kotak cari menyaring opsi; tanpa hasil → kalimat, bukan panel kosong;
 *   4. ArrowDown/ArrowUp/Home/End memindahkan sorotan, Enter memilih,
 *      Escape menutup tanpa mengubah pilihan;
 *   5. klik opsi memanggil `onChange(decision_id)` lalu menutup panel.
 *
 * Aturan tampilan: hanya token sistem (--surface, --line, --accent-strong,
 * --status-*, --fs-*, --radius) — tidak ada hex baru; status tetap dibaca dari
 * kata, bukan warna saja; target sentuh 44px.
 */

import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import {
  pecahLabel,
  saringGrup,
  type PickerGroup,
  type PickerOption,
} from "../lib/decision-picker";

/** Nomor keputusan (8 heksa) ditulis dengan huruf data; kata lain tetap sans. */
const NOMOR = /^[0-9a-f]{6,}$/i;

function BarisMeta({ meta }: { meta: string[] }) {
  if (meta.length === 0) return null;
  const akhir = meta[meta.length - 1];
  const adaNomor = meta.length > 1 && NOMOR.test(akhir);
  const sisa = adaNomor ? meta.slice(0, -1) : meta;
  return (
    <span className="dpick-meta">
      {sisa.join(" · ")}
      {adaNomor ? (
        <>
          {" · "}
          <span className="dpick-nomor">{akhir}</span>
        </>
      ) : null}
    </span>
  );
}

export default function DecisionPicker({
  id = "pilih-keputusan",
  label,
  ariaLabel,
  groups,
  value,
  onChange,
  placeholder = "Pilih keputusan",
  hint,
}: {
  id?: string;
  /** Label terlihat di atas pemicu (dipakai halaman bukti). */
  label?: string;
  /** Label untuk pembaca layar bila tidak ada label terlihat. */
  ariaLabel?: string;
  groups: PickerGroup[];
  value: string | null;
  onChange: (decisionId: string) => void;
  placeholder?: string;
  /** Kalimat bantuan di bawah pemicu (jumlah menunggu tindakan, dsb.). */
  hint?: React.ReactNode;
}) {
  const [terbuka, setTerbuka] = useState(false);
  const [kueri, setKueri] = useState("");
  const [sorot, setSorot] = useState(0);
  const akarRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const idPanel = `${id}-panel`;
  const idDaftar = `${id}-daftar`;
  const opsiId = (indeks: number) => `${id}-opsi-${indeks}`;

  const tersaring = useMemo(() => saringGrup(groups, kueri), [groups, kueri]);
  const datar = useMemo<PickerOption[]>(
    () => tersaring.flatMap((group) => group.options),
    [tersaring]
  );
  const terpilih = useMemo(
    () => groups.flatMap((group) => group.options).find((option) => option.value === value) ?? null,
    [groups, value]
  );
  const grupTerpilih = useMemo(
    () => groups.find((group) => group.options.some((option) => option.value === value)) ?? null,
    [groups, value]
  );

  // Buka/tutup: fokus ke kotak cari, sorot pilihan aktif.
  useEffect(() => {
    if (!terbuka) return;
    const indeks = datar.findIndex((option) => option.value === value);
    setSorot(indeks >= 0 ? indeks : 0);
    const fokus = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(fokus);
    // `datar` sengaja tidak jadi dependensi: sorotan hanya ditetapkan saat
    // panel dibuka, bukan setiap kali hasil saring berubah.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [terbuka]);

  // Klik di luar menutup panel; Escape global juga menutup.
  useEffect(() => {
    if (!terbuka) return;
    const klikLuar = (event: MouseEvent) => {
      if (!akarRef.current?.contains(event.target as Node)) setTerbuka(false);
    };
    document.addEventListener("mousedown", klikLuar);
    return () => document.removeEventListener("mousedown", klikLuar);
  }, [terbuka]);

  const tutup = (kembalikanFokus = true) => {
    setTerbuka(false);
    setKueri("");
    if (kembalikanFokus) {
      requestAnimationFrame(() => {
        document.getElementById(id)?.focus();
      });
    }
  };

  const pilih = (option: PickerOption | undefined) => {
    if (!option) return;
    onChange(option.value);
    tutup();
  };

  const geser = (langkah: number) => {
    if (datar.length === 0) return;
    const berikut = (sorot + langkah + datar.length) % datar.length;
    // Efek samping di luar updater state: updater harus murni, dan jsdom tidak
    // menyediakan scrollIntoView (opsional call menjaga tes & browser lama).
    setSorot(berikut);
    requestAnimationFrame(() => {
      document.getElementById(opsiId(berikut))?.scrollIntoView?.({ block: "nearest" });
    });
  };

  const diTombol = (event: React.KeyboardEvent<HTMLInputElement>) => {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        geser(1);
        break;
      case "ArrowUp":
        event.preventDefault();
        geser(-1);
        break;
      case "Home":
        event.preventDefault();
        setSorot(0);
        break;
      case "End":
        event.preventDefault();
        setSorot(Math.max(0, datar.length - 1));
        break;
      case "Enter":
        event.preventDefault();
        pilih(datar[sorot]);
        break;
      case "Escape":
        event.preventDefault();
        tutup();
        break;
      case "Tab":
        tutup(false);
        break;
      default:
        break;
    }
  };

  const judulTerpilih = terpilih ? pecahLabel(terpilih.label) : null;
  const nadaAktif = grupTerpilih?.id === "action" ? "dpick-dot-action" : "dpick-dot-rest";

  return (
    <div className="dpick" ref={akarRef}>
      {label ? (
        <label className="dpick-label" htmlFor={id}>
          {label}
        </label>
      ) : null}

      <div className="dpick-anchor">
      <button
        type="button"
        id={id}
        className="dpick-trigger"
        aria-haspopup="listbox"
        aria-expanded={terbuka}
        aria-controls={terbuka ? idPanel : undefined}
        aria-label={ariaLabel}
        onClick={() => setTerbuka((kini) => !kini)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !terbuka) {
            event.preventDefault();
            setTerbuka(true);
          }
        }}
      >
        {judulTerpilih ? (
          <span className="dpick-value">
            <span className={`dpick-dot ${nadaAktif}`} aria-hidden="true" />
            <span className="dpick-value-text">
              <span className="dpick-value-title">{judulTerpilih.judul}</span>
              {judulTerpilih.meta.length > 0 ? (
                <BarisMeta meta={judulTerpilih.meta} />
              ) : null}
            </span>
          </span>
        ) : (
          <span className="dpick-placeholder">{placeholder}</span>
        )}
        <span className="dpick-chevron" aria-hidden="true" />
      </button>

      {/* Panel selalu ada di DOM (atribut `hidden` saat tertutup) supaya
          `aria-controls` menunjuk elemen yang benar-benar ada dan daftar opsi
          bisa diperiksa tanpa membuka UI. */}
      <div
        className="dpick-panel"
        id={idPanel}
        hidden={!terbuka}
      >
          <div className="dpick-search-wrap">
            <input
              ref={inputRef}
              className="dpick-search"
              type="text"
              role="combobox"
              aria-expanded={terbuka}
              aria-controls={idDaftar}
              aria-autocomplete="list"
              aria-activedescendant={datar.length > 0 ? opsiId(sorot) : undefined}
              placeholder="Cari jenis, status, atau nomor…"
              value={kueri}
              onChange={(event) => {
                setKueri(event.target.value);
                setSorot(0);
              }}
              onKeyDown={diTombol}
            />
            {kueri ? (
              <button
                type="button"
                className="dpick-clear"
                onClick={() => {
                  setKueri("");
                  inputRef.current?.focus();
                }}
                aria-label="Hapus pencarian"
              >
                ×
              </button>
            ) : null}
          </div>

          {datar.length === 0 ? (
            <p className="dpick-empty">
              Tidak ada keputusan yang cocok dengan “{kueri.trim()}”.
            </p>
          ) : (
            <ul className="dpick-list" id={idDaftar} role="listbox" aria-label="Daftar keputusan">
              {tersaring.map((group) => (
                <Fragment key={group.id}>
                  <li role="presentation" className="dpick-group-label">
                    {/* Jumlah mengikuti hasil saring, bukan total awal: saat
                        mencari "alokasi", "Menunggu tindakan (4)" berubah jadi
                        "(2)" — angka yang salah lebih buruk daripada tanpa angka. */}
                    {group.label.replace(/\s*\(\d+\)$/, "")} ({group.options.length})
                  </li>
                  {group.options.map((option) => {
                    const indeks = datar.indexOf(option);
                    const bagian = pecahLabel(option.label);
                    const disorot = indeks === sorot;
                    const aktif = option.value === value;
                    return (
                      <li
                        key={option.value}
                        id={opsiId(indeks)}
                        role="option"
                        aria-selected={disorot}
                        className={`dpick-option${aktif ? " dpick-option-active" : ""}${
                          disorot ? " dpick-option-focus" : ""
                        }`}
                        data-value={option.value}
                        onClick={() => pilih(option)}
                        onMouseEnter={() => setSorot(indeks)}
                      >
                        <span className="dpick-option-text">
                          <span className="dpick-option-title">{bagian.judul}</span>
                          {bagian.meta.length > 0 ? (
                            <BarisMeta meta={bagian.meta} />
                          ) : null}
                        </span>
                        {aktif ? (
                          <span className="dpick-option-check" aria-hidden="true">
                            ✓
                          </span>
                        ) : null}
                      </li>
                    );
                  })}
                </Fragment>
              ))}
            </ul>
          )}

          <p className="dpick-foot" aria-hidden="true">
            <span>↑↓ pilih</span>
            <span>Enter buka</span>
            <span>Esc tutup</span>
          </p>
      </div>
      </div>

      {hint ? <span className="dpick-hint">{hint}</span> : null}
    </div>
  );
}
