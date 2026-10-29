"use client";

// Donat komposisi komoditas — SATU diagram untuk kedua kartu Overview
// (31 Okt 2026, permintaan pemilik: "beda komoditas beda warna, 1 diagram").
//
// Kenapa donat dan bukan satu cincin per komoditas: cincin terpisah memaksa
// pembaca membandingkan sudut di empat tempat berbeda; satu donat menjawab
// "kartu ini terdiri dari apa" sekali pandang, dan warna komoditas yang sama
// dipakai di peta, chip, dan legenda — satu warna = satu komoditas.
//
// Kenapa tiap irisan tetap membawa catatannya sendiri (cakupan %, selisih kg):
// donat hanya menunjukkan porsi. Status "cukup/kurang" tidak boleh hanya
// diwakili warna, jadi angkanya dicetak di baris legenda.

/** Keliling lingkaran donat (r=38 pada viewBox 100×100). */
const R = 38;
const C = 2 * Math.PI * R;
/** Celah antar-irisan dalam satuan viewBox, supaya batas warna terbaca. */
const CELAH = 2.2;

export type DonutSlice = {
  key: string;
  label: string;
  /** Nilai penentu besar irisan (kg). */
  kg: number;
  /** Kelas warna identitas komoditas (.sr-komod-*). */
  toneClass: string;
  /** Catatan di kanan baris legenda, mis. "28% · −780 kg" atau "1.580 kg". */
  note: string;
  /** Kalimat lengkap untuk pembaca layar. */
  aria: string;
};

export type CompositionDonutProps = {
  slices: readonly DonutSlice[];
  /** Angka di tengah donat, sudah diformat pemanggil. */
  totalValue: string;
  /** Satuan kecil di bawah angka tengah. */
  totalUnit: string;
  /** Satu kalimat yang merangkum seluruh diagram. */
  aria: string;
  /** Keterangan kaki yang menjelaskan arti warna. */
  caption: string;
  /** Bila diisi, tiap baris legenda menjadi tombol (mis. pilih di peta). */
  onPick?: (label: string) => void;
};

export default function CompositionDonut({
  slices,
  totalValue,
  totalUnit,
  aria,
  caption,
  onPick,
}: CompositionDonutProps) {
  const total = slices.reduce((jumlah, s) => jumlah + (Number.isFinite(s.kg) ? s.kg : 0), 0);
  if (total <= 0) return null;

  let berjalan = 0;
  const busur = slices
    .filter((iris) => iris.kg > 0)
    .map((iris) => {
      const panjang = (iris.kg / total) * C;
      const mulai = berjalan;
      berjalan += panjang;
      // Celah dikurangi dari tiap irisan; irisan sangat kecil tetap dapat garis
      // minimum supaya tidak hilang sama sekali.
      const tebal = Math.max(1.2, panjang - CELAH);
      return { iris, panjang: tebal, offset: -mulai };
    });

  return (
    <div className="cd-wrap">
      <div className="cd-body">
        <div className="cd-donut" role="img" aria-label={aria} title={aria}>
          <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
            <circle className="cd-track" cx="50" cy="50" r={R} />
            <g transform="rotate(-90 50 50)">
              {busur.map(({ iris, panjang, offset }) => (
                <circle
                  key={iris.key}
                  className={`cd-arc ${iris.toneClass}`}
                  cx="50"
                  cy="50"
                  r={R}
                  strokeDasharray={`${panjang} ${C - panjang}`}
                  strokeDashoffset={offset}
                />
              ))}
            </g>
          </svg>
          <span className="cd-total">
            <span className="cd-total-angka">{totalValue}</span>
            <span className="cd-total-unit">{totalUnit}</span>
          </span>
        </div>

        <ul className="cd-legend">
          {slices.map((iris) => {
            const isi = (
              <>
                <span className="cd-dot" aria-hidden="true" />
                <span className="cd-name">{iris.label}</span>
                <span className="cd-note">{iris.note}</span>
              </>
            );
            return (
              <li key={iris.key} className={`cd-row ${iris.toneClass}`} title={iris.aria}>
                {onPick && iris.kg > 0 ? (
                  <button
                    type="button"
                    className="cd-pick"
                    aria-label={`${iris.aria}. Tampilkan di peta`}
                    onClick={() => onPick(iris.label)}
                  >
                    {isi}
                  </button>
                ) : (
                  isi
                )}
              </li>
            );
          })}
        </ul>
      </div>
      <p className="cd-caption">{caption}</p>
    </div>
  );
}

/** Dipakai tes kontrak: keliling donat harus sama dengan yang dipakai CSS/SVG. */
export const DONUT_CIRCUMFERENCE = C;
