// RoleHero — kepala konsol per role (arah Roy: UI role jangan polos).
// Konten deskriptif saja (tanpa angka karangan): judul, misi, dan
// langkah kerja yang membedakan tiap role.

type Profile = {
  title: string;
  mission: string;
  steps: string[];
  /** Batas domain peran (Fase 6 butir 6 & 7): apa yang TIDAK diperiksa konsol
   *  ini, supaya layar tidak mengesankan validasi menu/gizi yang tidak terjadi. */
  scopeNote?: string;
};

export const roleProfile: Record<string, Profile> = {
  sppg_head: {
    title: "Konsol Kepala SPPG",
    mission:
      "Pantau pasangan pasokan–permintaan, jalankan analisis agen, lalu setujui atau tolak rekomendasi dengan alasan yang jelas.",
    steps: [
      "Pilih lokasi & komoditas → muat kondisi terkini",
      "Jalankan analisis agen → tinjau kandidat + harga janggal",
      "Ajukan usulan → setujui/tolak di feed dengan alasan",
    ],
    scopeNote:
      "Konsol ini memutuskan BAHAN (kg) untuk rencana distribusi. Menu dan porsi sajian siswa tidak tercatat di sistem ini, jadi tidak ada pemeriksaan menu yang diklaim di sini.",
  },
  sppg_nutritionist: {
    title: "Konsol Nutritionist SPPG",
    mission:
      "Tinjau kesegaran dan kelayakan BAHAN pada setiap rekomendasi distribusi sebelum persetujuan diberikan.",
    steps: [
      "Muat kondisi lokasi & komoditas",
      "Periksa skor kesegaran pada kandidat analisis",
      "Setujui/tolak rekomendasi dengan catatan kesegaran bahan",
    ],
    scopeNote:
      "Persetujuan di sini adalah atas bahan yang dikirim, bukan validasi menu atau gizi porsi siswa — fakta menu/porsi tidak ada di sistem ini.",
  },
  bgn_monitor: {
    title: "Papan Pengawasan BGN",
    mission:
      "Akun hanya-baca: memantau seluruh keputusan, alasan penolakan, dan jejak audit agen tanpa dapat mengubah apa pun.",
    steps: [
      "Amati feed keputusan lintas SPPG",
      "Buka detail untuk jejak audit & iterasi",
      "Semua aksi perubahan memang dinonaktifkan untuk peran ini",
    ],
    // Fase 6 butir 7: status hanya-baca dinyatakan sebagai BATAS DOMAIN peran,
    // bukan hanya tersirat di misi. Server sudah menolak aksi peran ini (403);
    // kalimat ini yang membuat janji layar = janji endpoint.
    scopeNote:
      "Konsol ini hanya-baca: peran BGN monitor tidak dapat mengubah apa pun — tidak ada approval, eksekusi, tinjauan bukti, maupun karantina yang tersedia.",
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
        {/* Misi + langkah peran dilipat (17 Okt): blok ini tampil di SETIAP tab
            dan hanya dibaca sekali. Judul tetap terlihat; panduan satu klik lagi.
            Isi tetap ada di DOM, jadi pembaca layar & tes tetap menemukannya. */}
        <details className="role-hero-more">
          <summary>Panduan peran</summary>
          <p className="role-mission">{p.mission}</p>
          {p.steps.length > 0 && (
            <ol className="role-steps">
              {p.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          )}
        </details>
        {/* Batas domain peran (Fase 6 butir 7): dinyatakan TERBUKA, bukan di dalam
            panduan yang dilipat — layar tidak boleh membuat penyetuju merasa sudah
            memeriksa menu/gizi yang tidak pernah tercatat sistem. */}
        {p.scopeNote ? (
          <p className="role-mission role-scope-note" data-testid="role-scope-note">
            {p.scopeNote}
          </p>
        ) : null}
      </div>
    </section>
  );
}
