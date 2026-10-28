"use client";

// ProcurementToday — tile pengadaan di Overview.
//
// Kenapa ada (laporan pemilik 27 Okt 2026: "setelah pengadaan dieksekusi,
// Overview tidak berubah"): diukur pada basis data demo, eksekusi memang
// menerbitkan PO, menulis jejak ACT, dan memberangkatkan batch — tetapi tiga
// kartu Overview lama hanya membaca pasokan/kebutuhan, yang TIDAK berubah saat
// execute (stok baru bertambah ketika penerimaan disetujui). Satu-satunya angka
// lama yang bergerak adalah hitungan antrean keputusan.
//
// Panel ini menampilkan tiga angka yang benar-benar bergerak pada eksekusi,
// semuanya dari `/procurement/summary` (server yang menghitung periode WIB dan
// cakupan lokasi). Nilai tak diketahui ditulis "—" dan periode kosong ditulis
// "belum ada" — tidak pernah "0" palsu (lihat lib/procurement-today.ts).

import type { ProcurementTile, ProcurementSummary } from "../lib/procurement-today";
import { procurementTiles } from "../lib/procurement-today";

/** "Asia/Jakarta" → "WIB" (label zona yang dibaca orang, bukan id IANA). */
function zonaSingkat(timezone?: string | null): string {
  if (!timezone) return "WIB";
  if (timezone === "Asia/Jakarta") return "WIB";
  if (timezone === "Asia/Makassar") return "WITA";
  if (timezone === "Asia/Jayapura") return "WIT";
  return timezone;
}

export default function ProcurementToday({
  data,
  loading,
  error,
}: {
  data: ProcurementSummary | null;
  loading?: boolean;
  error?: string | null;
}) {
  const tiles = procurementTiles(data, { loading, error });
  const zona = zonaSingkat(data?.period?.timezone);
  // "belum ada" pada keempat tile = SATU keadaan, bukan empat. Ditulis sekali di
  // bawah rel supaya kalimat yang sama tidak diulang empat kali.
  const semuaKosong =
    !loading &&
    !error &&
    data !== null &&
    tiles.every((t: ProcurementTile) => t.value === "belum ada");
  const rentang = tiles[0]?.label.split("·")[1]?.trim() ?? zona;

  return (
    <section
      className="procurement-today"
      aria-label="Pengadaan dan eksekusi"
      aria-busy={Boolean(loading) && !data}
      data-procurement="1"
    >
      {/* Rel bernomor: urutan PO → eksekusi → truk → penerimaan itu nyata,
          jadi penomoran menyampaikan informasi, bukan hiasan. Pil periode
          dihapus 28 Okt 2026; konteks periode tetap dibawa label penuh
          (title) dan kalimat foot tiap kartu. */}
      <ol className="procurement-rail">
        {tiles.map((tile: ProcurementTile, i: number) => (
          <li
            key={tile.id}
            className={`kpi-card procurement-card is-${tile.tone}`}
            data-procurement-tile={tile.id}
          >
            <span className="procurement-card-top">
              <span className="procurement-step" aria-hidden="true">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="kpi-card-label" title={tile.label}>
                {tile.label.split("·")[0].trim()}
              </span>
            </span>
            <span
              className={`kpi-card-value${
                tile.value === "belum ada" || tile.value === "—" ? " is-unknown" : ""
              }`}
            >
              {tile.value}
              <span className="kpi-card-unit">{tile.unit}</span>
            </span>
            {/* Satu kalimat per kartu (permintaan pemilik 29 Okt 2026: "di buat
                lebih pendek hanya kalimat baris 1 saja"). Detail baris kedua
                tidak dihapus dari data — ia menempel sebagai tooltip pada
                kalimat pertama, jadi tetap bisa dibaca tanpa menambah tinggi. */}
            <span className="kpi-card-foot" title={`${tile.foot} · ${tile.mini}`}>
              {tile.foot}
            </span>
          </li>
        ))}
      </ol>

      {semuaKosong ? (
        <p className="procurement-empty">
          Belum ada eksekusi pada {rentang} — angka muncul setelah keputusan
          dieksekusi, bukan saat rekomendasi dibuat.
        </p>
      ) : null}

      {error ? (
        <p className="procurement-note status-danger" role="alert">
          Angka pengadaan gagal dimuat: {error}
        </p>
      ) : null}
    </section>
  );
}
