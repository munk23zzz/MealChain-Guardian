// ProviderPanel — status provider model per agent, tampil JUJUR dari
// payload backend (design.md: tidak ada klaim sukses tanpa evidence).
// - status "ok" → badge hijau (provider-live) + label slot:kind
// - "fallback" → badge kuning + keterangan fallback
// - "unavailable"/"error"/absen → badge netral, BUKAN hijau
// Backend tetap sumber konfigurasi; panel ini display-only.

type ProviderInfo = {
  status?: string;
  provider?: string | null;
  fallback_used?: boolean;
  attempts?: number;
};

const AGENT_LABELS: Record<string, string> = {
  verifier: "Verifier",
  forecast: "Forecast",
  supervisor: "Supervisor",
};

function providerClass(info: ProviderInfo): string {
  switch (info.status) {
    case "ok":
      return "provider-live";
    case "fallback":
      return "provider-fallback";
    default:
      return "provider-unavailable";
  }
}

function providerText(agent: string, info: ProviderInfo): string {
  if (agent === "forecast" && info.provider === "statistical_fallback") {
    return "Fallback statistik (0.5/0.3/0.2)";
  }
  const base = info.provider ?? "UNAVAILABLE";
  return info.fallback_used ? `${base} (fallback)` : base;
}

export default function ProviderPanel({
  providers,
}: {
  providers: Record<string, ProviderInfo>;
}) {
  const agents = Object.keys(AGENT_LABELS);
  return (
    <section className="provider-panel" aria-label="Status provider model">
      <h3>Status Model Agent</h3>
      <ul className="provider-list">
        {agents.map((agent) => {
          const info: ProviderInfo = providers?.[agent] ?? {};
          return (
            <li key={agent} className={`provider-row ${providerClass(info)}`}>
              <span className="provider-agent">{AGENT_LABELS[agent]}</span>
              <span className="provider-value">
                {providerText(agent, info)}
              </span>
              {typeof info.attempts === "number" && info.attempts > 0 && (
                <span className="provider-attempts">{info.attempts} attempt</span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
