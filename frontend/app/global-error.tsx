"use client";

/**
 * Penangkap terakhir untuk kegagalan di root layout (audit 2026-10-29, AUD-029).
 * `app/error.tsx` tidak menangkap error di layout akar, jadi file ini wajib ada
 * agar kegagalan paling atas pun tetap punya layar yang bisa dibaca.
 */

export default function GalatGlobal({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="id">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          background: "#f6f7f9",
          color: "#14181f",
        }}
      >
        <main style={{ maxWidth: 560, padding: 28 }}>
          <h1 style={{ fontSize: 20, margin: "0 0 8px" }}>
            Aplikasi gagal dimuat
          </h1>
          <p style={{ margin: "0 0 6px", color: "#5b6472" }}>
            Kerangka halaman tidak bisa dirender. Muat ulang halaman; bila tetap
            gagal, sertakan kode kejadian di bawah saat melapor.
          </p>
          <p style={{ margin: "0 0 18px", color: "#5b6472", fontSize: 13 }}>
            Kode kejadian: <code>{error.digest ?? "tidak tersedia"}</code>
          </p>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              padding: "10px 16px",
              borderRadius: 10,
              border: "1px solid #1f4ed8",
              background: "#1f4ed8",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Muat ulang
          </button>
        </main>
      </body>
    </html>
  );
}
