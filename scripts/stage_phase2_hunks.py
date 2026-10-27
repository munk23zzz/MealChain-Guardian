#!/usr/bin/env python3
"""Stage HANYA hunk Fase 2 dari berkas yang juga disunting sesi lain.

Kenapa perlu: working tree repo ini dipakai bersama. `git add <berkas>` akan
ikut membawa pekerjaan Fase 8/orang lain yang belum siap di-commit, dan
`git add -A` melanggar aturan kerja. Skrip ini membaca patch per berkas,
menyaring hunk yang memuat penanda Fase 2, lalu menerapkannya ke index
(`git apply --cached`) tanpa menyentuh working tree.

Pemakaian:
    python scripts/stage_phase2_hunks.py            # kering: tampilkan hunk
    python scripts/stage_phase2_hunks.py --apply      # terapkan ke index

Penanda dipilih dari ISI hunk, bukan nomor baris — nomor baris bergeser setiap
kali berkas tetangga berubah.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

#: (berkas, [penanda]) — hunk DIPILIH bila memuat salah satu penanda.
BERKAS_CAMPURAN: dict[str, list[str]] = {
    "backend/app/services/settlement.py": ["demo_session_id=decision.demo_session_id"],
    "backend/app/api/actions.py": [
        "price, decision_id, status, demo_session_id)",
        'VALUES (:po, :sup, :mat, :qty, :price, :dec, \'submitted\', :sesi)',
        '"sesi": decision.demo_session_id',
    ],
    # `api.ts` dipakai bersama beberapa fase. Penanda dipilih POSITIF dan
    # spesifik: `demoSession;` (dengan titik koma) membedakannya dari
    # `demoSessionId` milik jalur `/demo/event1` & `/balance/analyze`.
    "frontend/lib/api.ts": [
        "payload.mode = opsi.mode",
        "payload.demo_session = demoSession;",
        "labelModeSesi",
        "DemoSessionInfo",
    ],
}

#: (berkas, [penanda]) — hunk DIBUANG bila memuat salah satu penanda; sisanya
#: ikut. Dipakai bila mayoritas hunk milik fase ini dan hanya satu-dua hunk
#: milik fase lain (mis. `mode` pada `mulai_dengan_template` milik Fase 10).
BERKAS_KECUALI: dict[str, list[str]] = {
    "backend/app/services/demo_session.py": ["Fase 10 MG"],
}


def _pilih(berkas: str, patch: str, mode: str) -> tuple[str, list[str], list[str]]:
    """Kembalikan (header, hunk_dipilih, hunk_dibuang) untuk satu berkas."""
    bagian = _hunks(patch)
    header, hunks = bagian[0], bagian[1:]
    if mode == "kecuali":
        penanda = BERKAS_KECUALI[berkas]
        dibuang = [h for h in hunks if any(p in h for p in penanda)]
        dipilih = [h for h in hunks if not any(p in h for p in penanda)]
    else:
        penanda = BERKAS_CAMPURAN[berkas]
        dipilih = [h for h in hunks if any(p in h for p in penanda)]
        dibuang = [h for h in hunks if not any(p in h for p in penanda)]
    return header, dipilih, dibuang


def _hunks(patch: str) -> list[str]:
    """Pecah patch per hunk; header berkas dikembalikan sebagai elemen pertama."""
    bagian = re.split(r"(?m)^(?=@@ )", patch)
    return bagian


def _header(patch: str) -> str:
    return _hunks(patch)[0]


def main(apply: bool) -> int:
    akar = Path(__file__).resolve().parents[1]
    total = 0
    tugas = [(b, "pilih") for b in BERKAS_CAMPURAN] + [
        (b, "kecuali") for b in BERKAS_KECUALI
    ]
    for berkas, mode in tugas:
        patch = subprocess.run(
            ["git", "diff", "--", berkas],
            cwd=akar,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout
        if not patch.strip():
            print(f"{berkas}: tidak ada diff, dilewati")
            continue
        header, dipilih, dibuang = _pilih(berkas, patch, mode)
        print(
            f"{berkas} [{mode}]: {len(dipilih)} hunk ikut, {len(dibuang)} dibuang"
        )
        if not dipilih:
            continue
        for h in dipilih:
            print("   ikut  ", h.splitlines()[0])
        for h in dibuang:
            print("   buang ", h.splitlines()[0])
        total += len(dipilih)
        if apply:
            tambalan = header + "".join(dipilih)
            if not tambalan.endswith("\n"):
                tambalan += "\n"
            # Patch ditulis LF-only ke berkas (git apply menolak CRLF), lalu
            # diterapkan dengan `--recount`: header hunk yang tersisa masih
            # membawa nomor baris sisi-lama dari diff penuh, jadi hitungannya
            # harus diturunkan ulang oleh git, bukan dihitung tangan.
            slug = berkas.replace("/", "_")
            patch_path = akar / "_qa" / "f2" / f"stage-{slug}.patch"
            patch_path.parent.mkdir(parents=True, exist_ok=True)
            patch_path.write_bytes(tambalan.encode("utf-8"))
            if b"\r" in patch_path.read_bytes():
                print("   GAGAL: patch memuat CR")
                return 1
            hasil = subprocess.run(
                ["git", "apply", "--cached", "--recount", str(patch_path)],
                cwd=akar,
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
            if hasil.returncode != 0:
                print(f"   GAGAL: {hasil.stderr.strip()[:300]}")
                return 1
            print(f"    diterapkan ke index ({patch_path.name})")
    print(f"total hunk Fase 2: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
