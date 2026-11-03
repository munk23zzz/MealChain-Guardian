"use client";

// EmptyState — keadaan kosong yang MENJELASKAN dan MENAWARKAN JALAN KELUAR
// (Tahap 6 redesign "Performance & Audit", 29 Okt 2026).
//
// Sebelumnya dua keadaan kosong di halaman ini diperlakukan berbeda dan
// keduanya salah: KPI tanpa payload `return null` (bagian berjudul tanpa isi,
// tanpa sebab, tanpa tombol), sedangkan mutu agen hanya satu kalimat tanpa
// tindakan. Bentuk ini dipakai bersama supaya keadaan kosong selalu punya tiga
// hal: APA yang kosong, KENAPA, dan APA yang bisa dilakukan pembaca.
//
// Tidak ada angka di sini — komponen ini tidak tahu apa pun soal KPI.

import type { ReactNode } from "react";

export default function EmptyState({
  kode,
  judul,
  sebab,
  saran,
  aksi,
}: {
  /** Penanda stabil untuk tes & analitik (mis. "kpi", "mutu"). */
  kode: string;
  judul: string;
  sebab: string;
  saran?: string;
  /** Tombol/tindakan lanjutan; tidak dirender bila tidak ada. */
  aksi?: ReactNode;
}) {
  return (
    <div className="empty-panel" data-empty-state={kode} role="status">
      <p className="empty-panel-title">{judul}</p>
      <p className="empty-panel-note">{sebab}</p>
      {saran ? <p className="empty-panel-note">{saran}</p> : null}
      {aksi ? <div className="empty-panel-action">{aksi}</div> : null}
    </div>
  );
}
