"""Cek angka dokumen menyeluruh terhadap sumber yang bisa diukur ulang.

Dipakai:  python scripts/cek_dokumen_menyeluruh.py
Keluar 1 bila ada klaim dokumen yang tidak cocok dengan snapshot/kode.
Semua pemeriksaan baca-saja: tidak menulis ke DB, tidak memanggil endpoint tulis.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "MEALCHAIN_GUARDIAN_MENYELURUH.md"
SNAP = ROOT / "docs" / "state-snapshot.json"


def dot(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def count_files(pattern: str) -> int:
    return len(list(ROOT.glob(pattern)))


def line_count(*dirs: str) -> int:
    total = 0
    for d in dirs:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".ts", ".tsx"}:
                total += sum(1 for _ in p.open("rb"))
    return total


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    db = snap["db"]

    rows: list[tuple[str, str, str]] = []

    def check(label: str, claimed: str, actual: str) -> None:
        rows.append((label, claimed, actual))

    # 1. Volume tabel: nilai harus ada di dokumen DAN sama dengan snapshot.
    for key, val in db.items():
        if not isinstance(val, int):
            continue
        shown = dot(val) if val >= 1000 else str(val)
        check(f"tabel {key}", shown, shown if shown in doc else "TIDAK ADA DI DOKUMEN")

    # 2. Status keputusan
    for status, val in (db.get("decisions_per_status") or {}).items():
        check(f"status {status}", str(val), str(val) if str(val) in doc else "TIDAK ADA")

    # 3. Hitungan kode
    routers = len(
        [
            line
            for line in subprocess.run(
                ["grep", "-rn", "APIRouter(", str(ROOT / "backend" / "app" / "api")],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.splitlines()
            if "__init__" not in line
        ]
    )
    check("modul router", "35", str(routers))

    openapi = json.loads((ROOT / "backend" / "openapi.json").read_text(encoding="utf-8"))
    paths = len(openapi["paths"])
    ops = sum(
        1
        for p in openapi["paths"].values()
        for m in p
        if m in {"get", "post", "patch", "put", "delete"}
    )
    check("path openapi", "87", str(paths))
    check("operasi openapi", "89", str(ops))

    migrations = count_files("backend/alembic/versions/*.py")
    check("migrasi", "39", str(migrations))

    be_tests = count_files("backend/tests/test_*.py")
    check("berkas uji backend", "311", str(be_tests))

    fe_tests = len(list((ROOT / "frontend" / "tests").glob("*.test.*")))
    check("berkas uji frontend", "244", str(fe_tests))

    components = count_files("frontend/components/*.tsx")
    check("komponen frontend", "91", str(components))

    py_files = count_files("backend/app/**/*.py")
    check("berkas python backend", "187", str(py_files))

    be_lines = line_count("backend/app")
    check("baris backend app", "46.742", dot(be_lines) if be_lines >= 1000 else str(be_lines))

    fe_lines = line_count("frontend/app", "frontend/components", "frontend/lib")
    check("baris frontend", "47.504", dot(fe_lines))

    # 4. Tabel di schema public (butuh DB; dilewati bila tidak tersedia)
    try:
        out = subprocess.run(
            [
                "docker", "compose", "exec", "-T", "postgres", "psql",
                "-U", "mealchain", "-d", "mealchain", "-t", "-A", "-c",
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
        ).stdout.strip()
        check("tabel di schema public", "25", out.splitlines()[0].strip())
    except Exception as exc:  # pragma: no cover - lingkungan tanpa docker
        check("tabel di schema public", "25", f"tidak dapat diukur ({type(exc).__name__})")

    width = max(len(r[0]) for r in rows) + 2
    gagal = 0
    print(f"{'klaim'.ljust(width)} dokumen   terukur   hasil")
    print("-" * (width + 30))
    for label, claimed, actual in rows:
        ok = claimed == actual
        gagal += 0 if ok else 1
        print(f"{label.ljust(width)} {claimed:<10} {actual:<9} {'OK' if ok else 'BEDA'}")

    print()
    print(f"{len(rows) - gagal}/{len(rows)} klaim cocok; {gagal} beda.")
    if gagal:
        print("Perbaiki dokumen ATAU ukur ulang: angka yang bergerak (volume tabel) sah berubah,")
        print("tetapi harus disertai snapshot baru dari scripts/snapshot_state.py.")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
