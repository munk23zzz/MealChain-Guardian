/** @type {import('next').NextConfig} */
// Proxy API — mengapa ada:
// backend/app/main.py hanya mengizinkan origin localhost:3000, sehingga UI
// yang dibuka dari origin lain (mis. GitHub Codespaces,
// https://<codespace>-3000.app.github.dev) akan diblokir CORS oleh browser.
// Solusinya: UI memanggil API lewat origin-nya sendiri, lalu Next meneruskan
// ke kontainer `backend` di jaringan compose (nama host `backend`).
// Aktif hanya kalau NEXT_PUBLIC_API_URL kosong (lihat docker-compose.override.yml);
// kalau diisi URL absolut, jalur ini tidak terpakai dan perilaku lama tetap sama.
const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

// Root endpoint API backend (lihat frontend/lib/api.ts) — didaftarkan eksplisit
// supaya tidak menabrak aset Next (/_next) atau halaman aplikasi.
// WAJIB sinkron dengan prefix path di frontend/lib/api.ts; ada tes kontrak
// (tests/proxy-roots.test.ts) yang gagal kalau ada root terlewat — dulu "admin"
// tidak terdaftar sehingga tab Pengaturan membalas 404 HTML dari Next sendiri.
const API_ROOTS = [
  "admin",
  "auth",
  "decisions",
  "actions",
  "balance",
  "events",
  "price",
  "kpi",
  "ledger",
  "demo",
  "batches",
  "supplier-exclusions",
  "suppliers",
];

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return API_ROOTS.map((root) => ({
      source: `/${root}/:path*`,
      destination: `${BACKEND_INTERNAL_URL}/${root}/:path*`,
    }));
  },
};

module.exports = nextConfig;
