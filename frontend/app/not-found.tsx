/**
 * Route tidak dikenal (audit 2026-10-29, AUD-029).
 *
 * Server component: tidak butuh state, cukup jalan pulih yang jelas.
 */

export default function TidakDitemukan() {
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
          maxWidth: 520,
          background: "var(--surface, #fff)",
          border: "1px solid var(--line, #e3e6eb)",
          borderRadius: 16,
          padding: 28,
        }}
      >
        <h1 style={{ fontSize: 20, margin: "0 0 8px" }}>Halaman tidak ditemukan</h1>
        <p style={{ margin: "0 0 18px", color: "var(--ink-muted, #5b6472)" }}>
          Alamat ini bukan bagian dari MealChain Guardian. Periksa tautannya, atau
          kembali ke dasbor.
        </p>
        <a
          href="/"
          style={{
            display: "inline-block",
            padding: "10px 16px",
            borderRadius: 10,
            border: "1px solid var(--primary, #1f4ed8)",
            background: "var(--primary, #1f4ed8)",
            color: "#fff",
            textDecoration: "none",
            fontWeight: 600,
          }}
        >
          Kembali ke dasbor
        </a>
      </div>
    </main>
  );
}
