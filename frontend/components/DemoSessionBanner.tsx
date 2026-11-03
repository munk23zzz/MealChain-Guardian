"use client";

// Banner sesi demo (024/025): satu-satunya petunjuk global bahwa data memang
// sengaja kosong. Tanpa ini, tab kosong terbaca sebagai aplikasi rusak.
//
// Aturan yang dipegang:
// - Hanya muncul bila backend MELAPOR mode sesi menyala (`enforced`) dan tidak
//   ada sesi aktif — di pengembangan (flag mati) banner tidak pernah tampil.
// - Tidak ada tombol yang memanggil API tulis dari sini: tombol hanya membawa
//   pengguna ke tab Demo Control, tempat tombol "Muat Demo" berada.
// - Status dibaca ulang tiap 10 detik, jadi sesi yang habis di tab lain ikut
//   menampilkan petunjuk tanpa memuat ulang halaman. 10 detik (bukan 30)
//   karena penyemaian sesi butuh ~30 detik: banner tidak boleh tertinggal jauh.
import { useCallback, useEffect, useState } from "react";

import { fetchDemoSession } from "../lib/api";
import { pesanSesi, type StatusSesiDemo } from "../lib/demo-session";

// Satu tipe untuk satu API: kalau banner punya bentuk sendiri, ia akan
// menyimpang dari `pesanSesi` yang membaca objek yang sama.
type Status = StatusSesiDemo;

export default function DemoSessionBanner({
  token,
  bolehBuka,
  onOpenDemoControl,
}: {
  token: string | null;
  bolehBuka: boolean;
  onOpenDemoControl: () => void;
}) {
  const [status, setStatus] = useState<Status | null>(null);

  const muat = useCallback(async () => {
    if (!token) return;
    try {
      setStatus((await fetchDemoSession(token)) as Status);
    } catch {
      setStatus(null);
    }
  }, [token]);

  useEffect(() => {
    void muat();
    const t = window.setInterval(() => void muat(), 10000);
    return () => window.clearInterval(t);
  }, [muat]);

  if (!status?.enforced || status.active) return null;


  return (
    <div className="demo-kosong" role="status" aria-live="polite">
      {/* Satu sumber kalimat: `pesanSesi` (lib/demo-session). Banner sempat punya
          salinan sendiri yang menjanjikan layar kosong — bertentangan dengan
          perilaku nyata (template tetap tampil setelah sesi berakhir). */}
      <p className="demo-kosong-teks">{pesanSesi(status)}</p>
      {bolehBuka ? (
        <button type="button" className="button button-secondary" onClick={onOpenDemoControl}>
          Buka Demo Control
        </button>
      ) : (
        <p className="demo-kosong-teks demo-kosong-muted">
          Minta Kepala SPPG menekan „Muat Demo” di Demo Control.
        </p>
      )}
    </div>
  );
}
