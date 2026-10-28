// Jejak agen untuk SATU keputusan — dirender DI DALAM dossier.
//
// Rencana: docs/plans/decision-evidence-rebuild.md §3 & §4 bagian 5. Dulu jejak
// ini hanya bisa dilihat dengan melompat ke tab Agent Log (`onOpenTraces`),
// artinya dossier bergantung pada halaman lain. Data jejak per keputusan sudah
// tersedia di `GET /decisions/{id}/traces` dan sudah diambil halaman ini, jadi
// yang perlu dibuat hanya permukaannya.
//
// Komponen ini MURNI (tanpa fetch): daftar langkah, keadaan memuat, keadaan
// kosong yang menyebut sebabnya, dan galat yang menyebut pesannya.

export type TraceStep = {
  step_name?: string | null;
  agent_name?: string | null;
  tool_called?: string | null;
  duration_ms?: number | string | null;
  step_at?: string | null;
};

function langkahDari(traces: unknown): TraceStep[] {
  if (Array.isArray(traces)) return traces.filter((s) => s && typeof s === "object") as TraceStep[];
  const isi = (traces as { steps?: unknown } | null)?.steps;
  return Array.isArray(isi) ? (isi.filter((s) => s && typeof s === "object") as TraceStep[]) : [];
}

function waktu(nilai: string | null | undefined): string | null {
  if (!nilai) return null;
  const tanggal = new Date(nilai);
  if (Number.isNaN(tanggal.getTime())) return null;
  return tanggal.toLocaleString("id-ID", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DecisionTraceList({
  traces,
  loading = false,
  error = null,
}: {
  traces: unknown;
  loading?: boolean;
  error?: string | null;
}) {
  const langkah = langkahDari(traces);

  if (error) {
    return (
      <p className="evidence-note" role="status" data-testid="trace-list">
        Jejak agen gagal dimuat: {error}
      </p>
    );
  }
  if (loading) {
    return (
      <p className="evidence-note" role="status" data-testid="trace-list">
        Memuat jejak agen keputusan ini…
      </p>
    );
  }
  if (langkah.length === 0) {
    return (
      <p className="evidence-note" data-testid="trace-list">
        Belum ada langkah agen yang terekam untuk keputusan ini.
      </p>
    );
  }

  return (
    <ol className="trace-list" data-testid="trace-list">
      {langkah.map((s, i) => {
        const jam = waktu(s.step_at);
        return (
          <li className="trace-item" key={`${s.step_name ?? "langkah"}-${i}`}>
            <span className="trace-mark" aria-hidden="true">
              {i + 1}
            </span>
            <div className="trace-body">
              <p className="trace-head">
                <strong className="trace-title">{s.step_name ?? "Langkah tanpa nama"}</strong>
                {jam && <span className="trace-time">{jam}</span>}
              </p>
              <p className="trace-meta">
                {s.agent_name ?? "agen tidak tercatat"}
                {s.tool_called ? ` · alat ${s.tool_called}` : " · tanpa alat"}
                {s.duration_ms != null ? ` · ${Math.round(Number(s.duration_ms))} ms` : ""}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
