/**
 * Catatan teknis — satu tempat untuk kalimat PENJELAS METODE (29 Okt 2026).
 *
 * Sebelumnya kalimat-kalimat ini menempel di kartu masing-masing sebagai
 * paragraf abu-abu, dan bersama-sama memakan ±100 px di halaman bukti padahal
 * dibaca sekali lalu dilewati. Kartu tetap menyajikan angka dan keadaan;
 * penjelasan cara membacanya dikumpulkan di sini, satu lipatan di dasar halaman.
 *
 * Aturan yang dipegang: tidak ada satu angka pun di dalam blok ini. Kalau suatu
 * hari sebuah kalimat memuat angka yang juga tidak tampil di kartu, kalimat itu
 * HARUS kembali ke kartunya — melipat bukti bukan merapikan.
 */
const CATATAN: { label: string; text: string }[] = [
  {
    label: "Pemulihan administratif",
    text: "Pemulihan administratif tidak mengubah status keamanan batch. Batch yang gagal pemeriksaan tetap tidak bisa dipakai.",
  },
  {
    label: "Usulan exclusion",
    text: "Usulan hanya masuk approval. Tidak ada auto execute.",
  },
  {
    label: "Review bukti batch",
    text: "Reviewer menambah bukti; status dihitung dari bukti.",
  },
];

export function CatatanTeknis() {
  return (
    <details className="card catatan-teknis" data-testid="catatan-teknis">
      <summary className="catatan-teknis-summary">
        Catatan teknis
        <span className="catatan-teknis-hint">{CATATAN.length} cara membaca bukti</span>
      </summary>
      <dl className="catatan-teknis-list">
        {CATATAN.map((item) => (
          <div className="catatan-teknis-row" key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
