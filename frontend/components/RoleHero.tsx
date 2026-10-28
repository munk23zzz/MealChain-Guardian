// RoleHero — kepala konsol per role (arah Roy: UI role jangan polos).
// Konten deskriptif saja (tanpa angka karangan): judul + batas domain peran.
// Panduan peran (misi + langkah kerja) DIHAPUS 27 Okt 2026 atas permintaan
// pemilik: blok itu hanya dibaca sekali dan memakan ruang di setiap tab.

type Profile = {
  title: string;
  /** Batas domain peran (Fase 6 butir 6 & 7): apa yang TIDAK diperiksa konsol
   *  ini, supaya layar tidak mengesankan validasi menu/gizi yang tidak terjadi. */
  scopeNote?: string;
};

export const roleProfile: Record<string, Profile> = {
  sppg_head: {
    title: "Konsol Kepala SPPG",
    scopeNote:
      "Konsol ini memutuskan BAHAN (kg) untuk rencana distribusi. Menu dan porsi sajian siswa tidak tercatat di sistem ini, jadi tidak ada pemeriksaan menu yang diklaim di sini.",
  },
  sppg_nutritionist: {
    title: "Konsol Nutritionist SPPG",
    scopeNote:
      "Persetujuan di sini adalah atas bahan yang dikirim, bukan validasi menu atau gizi porsi siswa — fakta menu/porsi tidak ada di sistem ini.",
  },
  bgn_monitor: {
    title: "Papan Pengawasan BGN",
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
  };
  return (
    <section className="role-hero" aria-label={p.title}>
      <div className="role-hero-text">
        <h2>{p.title}</h2>
        {/* Batas domain peran (Fase 6 butir 7): dinyatakan TERBUKA — layar tidak
            boleh membuat penyetuju merasa sudah memeriksa menu/gizi yang tidak
            pernah tercatat sistem. */}
        {p.scopeNote ? (
          <p className="role-mission role-scope-note" data-testid="role-scope-note">
            {p.scopeNote}
          </p>
        ) : null}
      </div>
    </section>
  );
}
