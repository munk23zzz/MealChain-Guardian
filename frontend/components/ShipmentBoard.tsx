"use client";

import { useState } from "react";

import {
  BOARD_SORTS,
  boardBerangkat,
  boardBerangkatPenuh,
  boardCounts,
  boardEta,
  boardEtaPenuh,
  boardJalur,
  boardKeadaan,
  boardLayakNote,
  boardMasaLayak,
  boardMuatan,
  boardMutu,
  boardSisa,
  boardSort,
  boardSumber,
  type BoardSort,
} from "../lib/shipment-board";
import {
  shipmentKey,
  supplierRoutes,
  type SupplierRoute,
} from "../lib/supplier-routes";
import Pager from "./Pager";
import { paginate } from "../lib/pagination";

/** Baris per halaman — permintaan pemilik 19 Okt 2026 (10 per halaman). */
const KIRIMAN_PER_HALAMAN = 10;

/**
 * "Papan kiriman" (Arah B riset 16 Okt 2026).
 *
 * Satu baris per KIRIMAN (bukan per pemasok): Pemasok · Tujuan · Muatan · Jalur ·
 * Berangkat · ETA · Sisa · Masa layak · Mutu · Keadaan, dengan pilihan urutan
 * "Paling mendesak / Estimasi tiba / Batas layak".
 *
 * Dipakai di halaman Pemasok MENGGANTIKAN peran kolom teks "Jalur kirim" dan
 * kartu ringkas: papan ini memuat semua angka yang sama, per kiriman, jadi
 * menampilkan keduanya hanya akan menjadi dua penyaji data yang sama.
 *
 * Pilihan urutan memakai bentuk pil yang sudah ada (pola `.kpi-period`) supaya
 * tidak lahir bahasa visual baru; pilihan aktif ditandai warna primer +
 * `aria-pressed` untuk pembaca layar.
 */
export default function ShipmentBoard({
  routes,
  title = "Papan kiriman",
  hanya,
  note,
  empty,
  tautan,
}: {
  /** Payload `GET /supplier-routes` (amplop `{routes}` atau array). */
  routes: unknown;
  title?: string;
  /** Saring dulu (mis. hanya kiriman menuju satu lokasi). */
  hanya?: (row: SupplierRoute) => boolean;
  /** Keterangan kecil di bawah papan. */
  note?: string;
  /** Pesan pengganti saat tidak ada kiriman; tanpanya papan tidak dirender. */
  empty?: string;
  /** Tautan kecil di kepala papan (mis. "Ke daftar pemasok"). */
  tautan?: { href: string; label: string };
}) {
  const [cara, setCara] = useState<BoardSort>("mendesak");
  const semua = supplierRoutes(routes);
  const cakupan = hanya ? semua.filter((row) => hanya(row)) : semua;
  const rows = boardSort(cakupan, cara);
  // Halaman papan kiriman: urutan berubah → kembali ke halaman 1 supaya baris
  // paling mendesak tidak tersembunyi di halaman lain.
  const [halaman, setHalaman] = useState(1);
  const halamanKiriman = paginate(rows, halaman, KIRIMAN_PER_HALAMAN);
  if (!rows.length && empty === undefined) return null;

  return (
    <section className="card shipment-board" aria-label={title}>
      <div className="card-header shipment-head">
        <h2>{title}</h2>
        {rows.length > 0 && <span className="shipment-count">{boardCounts(rows)}</span>}
        {/* S3 (29 Okt 2026): papan berdiri di atas daftar pemasok, jadi kepala
            kartunya menawarkan jalan ke sana — pembaca yang ingin melihat
            pemasoknya tidak perlu menggulir sendiri. */}
        {tautan ? (
          <a className="shipment-head-link" href={tautan.href}>
            {tautan.label}
          </a>
        ) : null}
      </div>

      {rows.length === 0 ? (
        <p className="evidence-note">{empty}</p>
      ) : (
        <>
          <div className="board-sort" role="group" aria-label="Urutkan kiriman">
            <span className="board-sort-label">Urutkan:</span>
            {BOARD_SORTS.map((pilihan) => (
              <button
                key={pilihan.id}
                type="button"
                className={`board-sort-pill${cara === pilihan.id ? " is-active" : ""}`}
                aria-pressed={cara === pilihan.id}
                onClick={() => {
                  setCara(pilihan.id);
                  setHalaman(1);
                }}
              >
                {pilihan.label}
              </button>
            ))}
          </div>

          <div className="board-table-wrap">
            <table className="location-table shipment-table">
              <thead>
                <tr>
                  <th scope="col">Pemasok</th>
                  <th scope="col">Tujuan</th>
                  <th scope="col">Muatan</th>
                  <th scope="col">Jalur</th>
                  <th scope="col">Berangkat</th>
                  <th scope="col" className="num">
                    Estimasi tiba
                  </th>
                  <th scope="col" className="num">
                    Sisa
                  </th>
                  <th scope="col">Masa layak</th>
                  <th scope="col">Mutu</th>
                  <th scope="col">Keadaan</th>
                </tr>
              </thead>
              <tbody>
                {halamanKiriman.items.map((row) => {
                  const keadaan = boardKeadaan(row);
                  const layak = boardLayakNote(row);
                  const sumber = boardSumber(row);
                  return (
                    <tr key={shipmentKey(row)}>
                      <th scope="row" className="shipment-cell-name">
                        {row.supplierName}
                      </th>
                      <td data-label="Tujuan">{row.destinationName}</td>
                      <td data-label="Muatan">{boardMuatan(row)}</td>
                      <td className="route-cell" data-label="Jalur">
                        {boardJalur(row)}
                        {/* Jejak sumber geometri tetap ditulis (angka jalur harus bisa
                            ditelusuri), tetapi rasio jalur↔garis lurus dibuang: 16 Okt 2026
                            pemilik memutuskan info itu tidak diperlukan pembaca. */}
                        {sumber ? (
                          <span
                            className="cell-meta"
                            title="Jarak & waktu tempuh dihitung dari jalur jalan yang tersimpan untuk kiriman ini."
                          >
                            {sumber}
                          </span>
                        ) : null}
                      </td>
                      {/* Sel waktu memakai bentuk ringkas; waktu LENGKAP tetap
                          tersedia sebagai tooltip — tidak ada informasi hilang. */}
                      <td data-label="Berangkat" title={boardBerangkatPenuh(row)}>{boardBerangkat(row)}</td>
                      <td className="num" data-label="Estimasi tiba" title={boardEtaPenuh(row)}>
                        {boardEta(row)}
                      </td>
                      <td className="num" data-label="Sisa">{boardSisa(row)}</td>
                      <td data-label="Masa layak">
                        {boardMasaLayak(row)}
                        {layak ? (
                          <span className={`cell-tone cell-tone-${layak.tone}`}>{layak.text}</span>
                        ) : null}
                      </td>
                      <td data-label="Mutu">{boardMutu(row)}</td>
                      <td data-label="Keadaan">
                        <span className={`shipment-pill shipment-pill-${keadaan.tone}`}>
                          {keadaan.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pager page={halamanKiriman} onChange={setHalaman} label={title.toLowerCase()} />
        </>
      )}

      {note && <p className="evidence-note">{note}</p>}
    </section>
  );
}
