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
  // Langkah 2 kalender (2026-10-16): agenda harian tab "Hari Ini". Tanpa akar
  // ini, /agenda jatuh ke router Next sendiri → 404 HTML, bukan JSON.
  "agenda",
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
  // Fase 10: rute JALAN kiriman pemasok → tujuan (dipakai peta untuk garis).
  "supplier-routes",
  // Fase 11: dua hitung-ulang dari halaman Keamanan Pangan. Tanpa dua akar ini
  // tombol "Periksa kiriman"/"Uji ulang" membalas 404 HTML dari Next sendiri
  // (terukur: "Tidak bisa memeriksa: HTTP 404: /freshness/evaluate").
  "freshness",
  "safety",
  // Fase 11 lanjutan: catatan penerimaan barang (opsi "Lainnya" yang tersimpan,
  // migrasi 016) — jalur tulis kedua dari kartu "Penerimaan barang".
  "receipts",
  // W-3 (2026-10-17): papan status integrasi per komponen. Tanpa akar ini
  // panel di tab Agent Log menerima 404 HTML dari router Next sendiri.
  "integrations",
  // W-5 (2026-10-17): purchase order mock SAP (baca saja). Tanpa akar ini panel
  // PO di tab Decision & Evidence menerima 404 HTML dari router Next sendiri.
  "sap",
];

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  experimental: {
    // Proxy dev (rewrites di bawah) memutus koneksi ke backend pada 30 detik
    // (bawaan Next: node_modules/next/dist/server/lib/router-utils/
    // proxy-request.js → `proxyTimeout || 30000`). Itu memutus
    // POST /demo/event1 yang menjalankan alur penuh DETECT→…→SUPERVISE:
    // terukur 27,9–30 dtk di stack lokal, dan klien menerima
    // "socket hang up" walau keputusan SUDAH ditulis di backend.
    // 3 menit memberi ruang untuk rantai provider yang lambat; batas keras
    // per provider tetap berlaku di backend.
    proxyTimeout: 180000,
  },
  async rewrites() {
    return API_ROOTS.map((root) => ({
      source: `/${root}/:path*`,
      destination: `${BACKEND_INTERNAL_URL}/${root}/:path*`,
    }));
  },
};

module.exports = nextConfig;
