// RoleHero — kepala konsol per role (arah Roy: UI role jangan polos).
// Konten deskriptif saja (tanpa angka karangan): judul, misi, dan
// langkah kerja yang membedakan tiap role.

type Profile = {
  title: string;
  mission: string;
  steps: string[];
};

export const roleProfile: Record<string, Profile> = {
  sppg_head: {
    title: "Konsol Kepala SPPG",
    mission:
      "Pantau pasangan pasokan–permintaan, jalankan analisis agent, lalu setujui atau tolak rekomendasi dengan alasan yang jelas.",
    steps: [
      "Pilih lokasi & komoditas → muat kondisi terkini",
      "Jalankan analisis agent → tinjau kandidat + harga janggal",
      "Ajukan usulan → approve/reject di feed dengan alasan",
    ],
  },
  sppg_nutritionist: {
    title: "Konsol Nutritionist SPPG",
    mission:
      "Tinjau aspek kesegaran dan kecocokan gizi pada setiap rekomendasi distribusi sebelum persetujuan diberikan.",
    steps: [
      "Muat kondisi lokasi & komoditas",
      "Periksa freshness score pada kandidat analisis",
      "Approve/reject rekomendasi dengan catatan gizi",
    ],
  },
  bgn_monitor: {
    title: "Papan Pengawasan BGN",
    mission:
      "Akun read-only: memantau seluruh keputusan, alasan penolakan, dan jejak audit agent tanpa dapat mengubah apa pun.",
    steps: [
      "Amati feed keputusan lintas SPPG",
      "Buka detail untuk jejak audit & iterasi",
      "Semua aksi mutasi dinonaktifkan by design",
    ],
  },
};

export default function RoleHero({ role }: { role: string }) {
  const p = roleProfile[role] ?? {
    title: "Konsol MealChain",
    mission: "Memantau keputusan distribusi pangan antar SPPG.",
    steps: [],
  };
  return (
    <section className="role-hero" aria-label={p.title}>
      <div className="role-hero-text">
        <h2>{p.title}</h2>
        <p className="role-mission">{p.mission}</p>
      </div>
      {p.steps.length > 0 && (
        <ol className="role-steps">
          {p.steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}
    </section>
  );
}
