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
}) {
  const [cara, setCara] = useState<BoardSort>("mendesak");
  const semua = supplierRoutes(routes);
  const cakupan = hanya ? semua.filter((row) => hanya(row)) : semua;
  const rows = boardSort(cakupan, cara);
  if (!rows.length && empty === undefined) return null;

  return (
    <section className="card shipment-board" aria-label={title}>
      <div className="card-header">
        <h2>{title}</h2>
        {rows.length > 0 && <span className="shipment-count">{boardCounts(rows)}</span>}
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
                onClick={() => setCara(pilihan.id)}
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
                {rows.map((row) => {
                  const keadaan = boardKeadaan(row);
                  const layak = boardLayakNote(row);
                  const sumber = boardSumber(row);
                  return (
                    <tr key={shipmentKey(row)}>
                      <th scope="row" className="shipment-cell-name">
                        {row.supplierName}
                      </th>
                      <td>{row.destinationName}</td>
                      <td>{boardMuatan(row)}</td>
                      <td className="route-cell">
                        {boardJalur(row)}
                        {/* Jejak sumber geometri tetap ditulis (angka jalur harus bisa
                            ditelusuri), tetapi rasio jalur↔garis lurus dibuang: 16 Okt 2026
                            pemilik memutuskan info itu tidak diperlukan pembaca. */}
                        {sumber ? (
                          <span
                            className="cell-meta"
                            title="Jarak & waktu tempuh jalur jalan dihitung OSRM saat sinkronisasi rute, bukan saat papan ini dibuka."
                          >
                            {sumber}
                          </span>
                        ) : null}
                      </td>
                      {/* Sel waktu memakai bentuk ringkas; waktu LENGKAP tetap
                          tersedia sebagai tooltip — tidak ada informasi hilang. */}
                      <td title={boardBerangkatPenuh(row)}>{boardBerangkat(row)}</td>
                      <td className="num" title={boardEtaPenuh(row)}>
                        {boardEta(row)}
                      </td>
                      <td className="num">{boardSisa(row)}</td>
                      <td>
                        {boardMasaLayak(row)}
                        {layak ? (
                          <span className={`cell-tone cell-tone-${layak.tone}`}>{layak.text}</span>
                        ) : null}
                      </td>
                      <td>{boardMutu(row)}</td>
                      <td>
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
        </>
      )}

      {note && <p className="evidence-note">{note}</p>}
    </section>
  );
}
