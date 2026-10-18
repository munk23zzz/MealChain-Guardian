"""Registry tujuh worker agent yang dibaca dari `hierarchy.json`.

File JSON adalah sumber konfigurasi; kode ini hanya memvalidasi dan
mengekspos daftar agent, stage, lane, dan endpoint allowlist. P1 belum
memanggil endpoint apa pun.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import AgentName, Stage

HIERARCHY_PATH = Path(__file__).with_name("hierarchy.json")


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    role: str
    stage: Stage
    blocking_allowed: bool
    description: str
    endpoints: tuple[str, ...]


def load_hierarchy(
    path: Path = HIERARCHY_PATH,
) -> tuple[tuple[AgentSpec, ...], tuple[tuple[AgentName, ...], ...]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("hierarchy.json harus berupa object")
    if data.get("version") != 1:
        raise ValueError("hierarchy.json versi harus 1")
    if data.get("mode") != "advisory":
        raise ValueError("hierarchy.json mode harus 'advisory'")

    raw_agents = data.get("agents")
    if not isinstance(raw_agents, list) or len(raw_agents) != len(AgentName):
        raise ValueError("hierarchy.json harus berisi tepat tujuh agent")

    specs: list[AgentSpec] = []
    for item in raw_agents:
        if not isinstance(item, dict):
            raise ValueError("setiap agent harus berupa object")
        try:
            name = AgentName(item["name"])
            stage = Stage(item["stage"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"agent/stage tidak dikenal: {item!r}") from exc

        role = item.get("role")
        description = item.get("description")
        endpoints = item.get("endpoints")
        blocking_allowed = item.get("blocking_allowed")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"{name.value}: role wajib diisi")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{name.value}: description wajib diisi")
        if not isinstance(endpoints, list) or not endpoints:
            raise ValueError(f"{name.value}: endpoints wajib berisi minimal satu")
        if not all(isinstance(endpoint, str) and endpoint.strip() for endpoint in endpoints):
            raise ValueError(f"{name.value}: endpoint harus string tidak kosong")
        if not isinstance(blocking_allowed, bool):
            raise ValueError(f"{name.value}: blocking_allowed harus boolean")

        specs.append(
            AgentSpec(
                name=name,
                role=role,
                stage=stage,
                blocking_allowed=blocking_allowed,
                description=description,
                endpoints=tuple(endpoints),
            )
        )

    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        raise ValueError("hierarchy.json memuat agent duplikat")
    if set(names) != set(AgentName):
        missing = sorted(name.value for name in set(AgentName) - set(names))
        raise ValueError(f"hierarchy.json kehilangan agent: {missing}")

    raw_lanes = data.get("lanes")
    if not isinstance(raw_lanes, list) or not raw_lanes:
        raise ValueError("hierarchy.json lanes wajib berisi minimal satu lane")

    lanes: list[tuple[AgentName, ...]] = []
    for raw_lane in raw_lanes:
        if not isinstance(raw_lane, list) or len(raw_lane) != 2:
            raise ValueError("setiap lane harus berisi tepat dua agent")
        try:
            lane = tuple(AgentName(name) for name in raw_lane)
        except ValueError as exc:
            raise ValueError(f"lane memuat agent tidak dikenal: {raw_lane!r}") from exc
        if any(name not in names for name in lane):
            raise ValueError(f"lane memuat agent di luar registry: {raw_lane!r}")
        lanes.append(lane)

    flat_lanes = [name for lane in lanes for name in lane]
    if len(set(flat_lanes)) != len(flat_lanes):
        raise ValueError("agent tidak boleh muncul di dua lane")
    if set(flat_lanes) != set(AgentName) - {AgentName.EVIDENCE}:
        raise ValueError("lane harus mencakup enam agent; Evidence berjalan setelah lane")

    return tuple(specs), tuple(lanes)


AGENTS, LANES = load_hierarchy()
AGENTS_BY_NAME = {spec.name: spec for spec in AGENTS}


def get_spec(name: str | AgentName) -> AgentSpec:
    try:
        agent_name = name if isinstance(name, AgentName) else AgentName(name)
    except ValueError as exc:
        raise KeyError(f"agent tidak dikenal: {name!r}") from exc
    return AGENTS_BY_NAME[agent_name]


__all__ = [
    "AGENTS",
    "AGENTS_BY_NAME",
    "AgentSpec",
    "HIERARCHY_PATH",
    "LANES",
    "get_spec",
    "load_hierarchy",
]
