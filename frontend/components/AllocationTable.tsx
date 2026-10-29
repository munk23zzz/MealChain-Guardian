"use client";

// Blok "Rencana alih" untuk halaman Location Network.
//
// Sumber: GET /surplus/allocations (dihitung SERVER lintas lokasi). Komponen ini
// tidak memasangkan lokasi sendiri — untuk peran SPPG `GET /balance/map` hanya
// memuat satu lokasi, sehingga hitungan klien selalu berakhir "tidak ada
// pasangan" di atas rencana yang sebenarnya punya sumber.
//
// Aturan tampilan (29 Okt 2026): satu tabel, tanpa paragraf penjelas. Ambang
// surplus ditulis SEKALI di kepala kartu (dipasok pemanggil lewat planRingkas),
// dan istilah kolom dibuat pendek karena kartu ini bersebelahan dengan tabel
// lokasi.

import { formatKg } from "../lib/overview-format";
import { alasanTanpaRencana, planFromServer } from "../lib/surplus";
import ScrollHint from "./ScrollHint";

export default function AllocationTable({
  plan,
  loading = false,
  error = null,
  highlight = null,
}: {
  /** Respons GET /surplus/allocations apa adanya. */
  plan: unknown;
  loading?: boolean;
  error?: string | null;
  /** Lokasi yang rinciannya sedang dibuka — baris tujuannya ditandai. */
  highlight?: string | null;
}) {
  const dariServer = planFromServer(plan, 6);
  const rows = dariServer?.rows ?? [];

  if (error) {
    return <p className="evidence-note">Rencana alih tidak bisa dimuat: {error}</p>;
  }
  if (loading && rows.length === 0) {
    return <p className="evidence-note">Memuat rencana alih…</p>;
  }
  if (rows.length === 0) {
    return <p className="evidence-note">{alasanTanpaRencana(dariServer?.reason)}</p>;
  }

  return (
    <>
      <div className="board-table-wrap allocation-table-wrap">
        <table className="location-table allocation-table" data-testid="allocation-table">
          <thead>
            <tr>
              <th scope="col">Dari</th>
              <th scope="col">Tujuan</th>
              <th scope="col" className="num">
                Jumlah
              </th>
              <th scope="col" className="num">
                Jarak
              </th>
              <th scope="col" className="num" title="Angkut + penanganan ÷ nilai barang">
                Biaya
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const aktif = highlight !== null && row.to === highlight;
              return (
                <tr
                  key={`${row.from}-${row.to}-${row.kg}`}
                  data-open={aktif ? "true" : undefined}
                >
                  <td data-label="Dari">{row.from}</td>
                  <td data-label="Tujuan">
                    {row.to}
                    {/* L5: penanda teks, bukan hanya latar — warna sendirian tidak
                        boleh jadi satu-satunya pembeda (Color Only). */}
                    {aktif ? <span className="alih-open-note"> · sedang dibuka</span> : null}
                  </td>
                  <td className="num" data-label="Jumlah">{formatKg(row.kg)}</td>
                  <td className="num" data-label="Jarak">
                    {row.distanceKm === null ? "—" : `${row.distanceKm} km`}
                  </td>
                  <td className="num" data-label="Biaya">
                    {row.costSharePct === null || row.costSharePct === undefined
                      ? "—"
                      : `${row.costSharePct.toLocaleString("id-ID", {
                          maximumFractionDigits: 1,
                        })}%`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ScrollHint />
      {/* Kalimat ambang pindah ke kepala kartu (L5, 29 Okt 2026) supaya dua
          kartu bawah berbagi urutan baca yang sama. Nilainya dibaca pemanggil
          lewat `planRingkas()` di lib/surplus.ts, bukan digandakan di sini. */}
    </>
  );
}
