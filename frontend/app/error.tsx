"use client";

/**
 * Error boundary root (audit 2026-10-29, AUD-029).
 *
 * Sebelum ini repo tidak punya `app/error.tsx`, `app/global-error.tsx`, maupun
 * `app/not-found.tsx`: kegagalan render atau route yang tidak dikenal berakhir
 * sebagai layar kosong Next.js bawaan tanpa jalan pulih.
 */

import { useEffect } from "react";

export default function Galat({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Simpan ke console agar bisa ditelusuri; JANGAN tampilkan detail internal
    // (stack, pesan mentah) ke pengguna.
    console.error("[mealchain] render gagal", error.digest ?? "", error.message);
  }, [error]);

  return (
    <main
      style={{
        minHeight: "60vh",
        display: "grid",
        placeItems: "center",
        padding: "48px 24px",
        background: "var(--bg-page, #f6f7f9)",
        color: "var(--ink, #14181f)",
      }}
    >
      <div
        style={{
          maxWidth: 560,
          background: "var(--surface, #fff)",
          border: "1px solid var(--line, #e3e6eb)",
          borderRadius: 16,
          padding: 28,
        }}
      >
        <h1 style={{ fontSize: 20, margin: "0 0 8px" }}>Halaman ini gagal dimuat</h1>
        <p style={{ margin: "0 0 6px", color: "var(--ink-muted, #5b6472)" }}>
          Data yang tampil di layar tidak bisa dipastikan benar, jadi kami
          menghentikan render daripada menampilkan angka yang salah.
        </p>
        <p style={{ margin: "0 0 18px", color: "var(--ink-muted, #5b6472)", fontSize: 13 }}>
          Kode kejadian: <code>{error.digest ?? "tidak tersedia"}</code>
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              padding: "10px 16px",
              borderRadius: 10,
              border: "1px solid var(--primary, #1f4ed8)",
              background: "var(--primary, #1f4ed8)",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Coba lagi
          </button>
          <a
            href="/"
            style={{
              padding: "10px 16px",
              borderRadius: 10,
              border: "1px solid var(--line-strong, #c9cfd8)",
              color: "inherit",
              textDecoration: "none",
            }}
          >
            Kembali ke dasbor
          </a>
        </div>
      </div>
    </main>
  );
}
