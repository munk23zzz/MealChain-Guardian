// Helper auth display-only: role dibaca dari payload JWT untuk UI
// (sumber kebenaran tetap RBAC backend — decode ini BUKAN otorisasi).

export function decodeRole(token: string | null): string | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    let b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4) b64 += "=";
    const payload = JSON.parse(atob(b64));
    return typeof payload.role === "string" ? payload.role : null;
  } catch {
    return null;
  }
}

export function formatIDR(value: string | number | null | undefined): string {
  // "—" (bukan "-") untuk nilai yang tidak diketahui: aturan repo
  // (lib/today.ts) melarang nilai kosong ditulis seperti angka/hyphen biasa.
  // Terukur 26 Okt 2026: kartu "Pemulihan status pemasok" mencetak "SDC -"
  // karena keputusan itu memang tidak punya biaya.
  if (value === null || value === undefined) return "—";
  const num = Number(value);
  if (Number.isNaN(num)) return "—";
  return `Rp${num.toLocaleString("id-ID", { maximumFractionDigits: 0 })}`;
}
