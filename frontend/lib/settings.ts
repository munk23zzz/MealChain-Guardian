// Logika murni layar Pengaturan (S4-11) — diuji di tests/settings.test.ts.
//
// Aturan yang dipertahankan: perubahan HANYA dikirim untuk field yang benar
// berubah, dan lokasi TIDAK dikirim saat peran baru adalah monitor (backend
// memaksa location_id null untuk bgn_monitor — lihat app/core/admin_rules.py).

export const MANAGE_ROLES = ["bgn_monitor"] as const;

export const ROLE_LABELS: Record<string, string> = {
  sppg_head: "Kepala SPPG",
  sppg_nutritionist: "Ahli Gizi SPPG",
  bgn_monitor: "Monitor BGN",
};

export function canManageSettings(role: string | null | undefined): boolean {
  return role !== null && role !== undefined && MANAGE_ROLES.includes(role as any);
}

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

/** Payload PATCH: hanya field yang berubah (kontrak unset vs null backend). */
export function draftUserUpdate(
  user: { role: string; locationId: string | null },
  nextRole: string,
  nextLocationId: string | null,
): Record<string, string | null> {
  const payload: Record<string, string | null> = {};
  if (nextRole !== user.role) {
    payload.role = nextRole;
  }
  const bolehLokasi = nextRole !== "bgn_monitor";
  if (bolehLokasi && nextLocationId !== user.locationId) {
    payload.location_id = nextLocationId;
  }
  return payload;
}
