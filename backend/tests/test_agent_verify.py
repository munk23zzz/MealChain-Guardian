"""Gerbang verifikasi deterministik atas hasil supervisor (flag-only).

Verifikasi berjalan SESUDAH supervisor menyusun rangkuman, dan hanya boleh
menandai (`flag`), tidak memveto: keputusan tetap `proposed` dan menunggu
manusia. Semua pemeriksaan di sini deterministik — tidak memanggil model.
"""

from uuid import uuid4

from agent.contracts import (
    AgentFinding,
    AgentName,
    AgentRun,
    RunStatus,
    WorkerStatus,
)
from agent.registry import get_spec
from agent.verify import verify_run


def _finding(
    agent: AgentName,
    *,
    status: WorkerStatus = WorkerStatus.OK,
    facts: dict | None = None,
    blocking: bool = False,
) -> AgentFinding:
    return AgentFinding(
        agent=agent,
        stage=get_spec(agent).stage,
        status=status,
        summary=f"{agent.value} finding",
        facts=facts or {},
        citations=[],
        blocking=blocking,
    )


def _run(
    *,
    status: RunStatus = RunStatus.COMPLETED,
    findings: list[AgentFinding] | None = None,
    narrative: str | None = "Review 7 agen selesai; keputusan menunggu approval manusia.",
    safety_veto: bool = False,
) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        decision_id="decision-1",
        mode="advisory",
        status=status,
        findings=findings or [_finding(name) for name in AgentName],
        narrative=narrative,
        safety_veto=safety_veto,
    )


def test_semua_ok_dan_status_konsisten_lolos() -> None:
    hasil = verify_run(_run())

    assert hasil.verdict == "pass"
    assert hasil.reasons == []


def test_safety_veto_aktif_tapi_status_completed_ditandai() -> None:
    """Veto keamanan aktif tidak boleh dilaporkan sebagai putaran selesai."""
    findings = [_finding(name) for name in AgentName]
    idx = next(i for i, f in enumerate(findings) if f.agent is AgentName.SAFETY)
    findings[idx] = _finding(AgentName.SAFETY, blocking=True)

    hasil = verify_run(_run(status=RunStatus.COMPLETED, findings=findings, safety_veto=True))

    assert hasil.verdict == "flag"
    assert any("safety_veto" in r for r in hasil.reasons), hasil.reasons


def test_narasi_menghaluskan_temuan_degraded_ditandai() -> None:
    """Worker degraded tetapi narasi bilang 'semua aman' harus ditandai."""
    findings = [_finding(name) for name in AgentName]
    idx = next(i for i, f in enumerate(findings) if f.agent is AgentName.PRICE)
    findings[idx] = _finding(AgentName.PRICE, status=WorkerStatus.DEGRADED)

    hasil = verify_run(
        _run(
            status=RunStatus.PARTIAL,
            findings=findings,
            narrative="Review selesai; semua temuan aman dan siap dieksekusi.",
        )
    )

    assert hasil.verdict == "flag"
    assert any("narasi" in r for r in hasil.reasons), hasil.reasons


def test_semua_modul_runtime_ikut_di_copy_oleh_dockerfile() -> None:
    """Modul yang diimpor runtime harus masuk image; kalau tidak, `No module`."""
    import re
    from pathlib import Path

    agent_dir = Path(__file__).resolve().parents[2] / "agent"
    dockerfile = (agent_dir / "Dockerfile").read_text(encoding="utf-8")

    # Telusuri graf impor relatif mulai dari entrypoint runtime, bukan sekadar
    # daftar semua .py: skrip operator (deploy, watchdog) tidak ikut image.
    belum = ["runtime_server"]
    terlihat: set[str] = set()
    pola = re.compile(r"from \.(\w+)(?: \.| import)|from \.(\w+)\.\w+ import")
    while belum:
        modul = belum.pop()
        if modul in terlihat or modul in {"workers", "prompts"}:
            continue
        terlihat.add(modul)
        berkas = agent_dir / f"{modul}.py"
        if not berkas.exists():
            continue
        for a, b in pola.findall(berkas.read_text(encoding="utf-8")):
            nama = a or b
            if nama and (agent_dir / f"{nama}.py").exists():
                belum.append(nama)

    hilang = sorted(m for m in terlihat if f"{m}.py" not in dockerfile)
    assert hilang == [], f"modul tidak di-COPY ke image: {hilang}"
