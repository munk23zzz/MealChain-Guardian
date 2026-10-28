"""Smoke live AgentCore + kontrak EMPAT bukti yang tidak boleh digabung (butir 4).

Dua lapis:

A. Kontrak (selalu jalan, tanpa jaringan) — menguji
   `app/services/agentcore_evidence.py`, yaitu modul yang juga dipakai
   `scripts/probe_agentcore_gateway.py`:
   - empat bukti punya nama & status sendiri;
   - `integrasi_aktif` hanya True bila SEMUA bukti `VERIFIED`;
   - AccessDenied/`AccessDeniedException` → `UNVERIFIED` (bukan `FAIL`,
     bukan `WORKING`);
   - `AGENTCORE_GATEWAY_URL` terisi saja tidak menaikkan status apa pun;
   - `tool_invoked` tidak pernah bisa naik dari konfigurasi.

B. Live (opt-in `RUN_LIVE_AGENTCORE=1`) — panggilan BACA saja ke AWS:
   `ListGateways`, `GetMemory`, `ListEvents`. Tidak membuat resource, tidak
   memanggil tool, tidak menulis event. Yang dilaporkan adalah apa adanya:
   kalau izin belum ada, statusnya `UNVERIFIED`.
"""

from __future__ import annotations

import os

import pytest

from app.services.agentcore_evidence import (
    GATEWAY_PROOFS,
    MEMORY_PROOFS,
    STATUS_NOT_CONFIGURED,
    STATUS_OK,
    STATUS_UNVERIFIED,
    STATUS_VOCAB,
    app_uses_gateway,
    bukti_valid,
    error_code,
    ringkas,
    sanitasi_terbukti,
    status_from_error,
)

LIVE = os.environ.get("RUN_LIVE_AGENTCORE") == "1"


class _AccessDeniedError(Exception):
    response = {
        "Error": {
            "Code": "AccessDeniedException",
            "Message": "not authorized to perform bedrock-agentcore:CreateEvent",
        }
    }


class _ThrottledError(Exception):
    response = {"Error": {"Code": "ThrottlingException", "Message": "slow down"}}


# ---------------------------------------------------------------------------
# A. Kontrak empat bukti
# ---------------------------------------------------------------------------


def test_empat_bukti_didefinisikan_terpisah():
    assert GATEWAY_PROOFS == (
        "resource_exists",
        "target_ready",
        "tool_invoked",
        "app_uses_gateway",
    )
    assert MEMORY_PROOFS == ("resource_exists", "read_allowed", "write_allowed")


def test_kosakata_status_hanya_tiga():
    assert set(STATUS_VOCAB) == {STATUS_OK, STATUS_UNVERIFIED, STATUS_NOT_CONFIGURED}
    assert "FAIL" not in STATUS_VOCAB
    assert "WORKING" not in STATUS_VOCAB


def test_integrasi_tidak_aktif_bila_satu_bukti_belum_terbukti():
    proofs = {
        "resource_exists": {"status": STATUS_OK},
        "target_ready": {"status": STATUS_OK},
        "tool_invoked": {"status": STATUS_UNVERIFIED},
        "app_uses_gateway": {"status": STATUS_NOT_CONFIGURED},
    }
    hasil = ringkas(proofs)
    assert hasil["integrasi_aktif"] is False
    assert hasil["belum_terbukti"] == ["tool_invoked", "app_uses_gateway"]
    assert hasil["per_bukti"]["target_ready"] == STATUS_OK
    assert sum(hasil["hitung"].values()) == 4


def test_integrasi_aktif_hanya_bila_keempat_verified():
    sempurna = {nama: {"status": STATUS_OK} for nama in GATEWAY_PROOFS}
    assert ringkas(sempurna)["integrasi_aktif"] is True

    for nama in GATEWAY_PROOFS:
        rusak = dict(sempurna)
        rusak[nama] = {"status": STATUS_UNVERIFIED}
        assert ringkas(rusak)["integrasi_aktif"] is False, (
            f"integrasi tidak boleh aktif saat {nama} belum terbukti"
        )


def test_bukti_tanpa_status_dihitung_belum_terbukti():
    hasil = ringkas({"resource_exists": {"detail": "tidak diukur"}})
    assert hasil["per_bukti"]["resource_exists"] == STATUS_UNVERIFIED
    assert hasil["integrasi_aktif"] is False


def test_access_denied_unverified_bukan_fail():
    galat = _AccessDeniedError()
    assert error_code(galat) == "AccessDeniedException"
    assert status_from_error(galat) == STATUS_UNVERIFIED
    assert status_from_error(_ThrottledError()) == STATUS_UNVERIFIED
    # Error tanpa struktur boto3 pun tidak boleh jadi klaim positif.
    assert status_from_error(RuntimeError("jaringan putus")) == STATUS_UNVERIFIED


def test_gateway_url_terisi_tidak_menaikkan_status():
    kosong = app_uses_gateway("")
    terisi = app_uses_gateway("https://gateway.example/mcp")
    assert kosong["status"] == STATUS_NOT_CONFIGURED
    assert terisi["status"] == STATUS_UNVERIFIED
    assert "belum dibuktikan" in terisi["detail"]


def test_tool_invoked_tidak_pernah_naik_dari_konfigurasi():
    # Status tool_invoked hanya bisa VERIFIED oleh pemanggilan nyata; di sini
    # kontraknya: konfigurasi terisi TIDAK membuat ringkasan jadi aktif.
    url_terisi = app_uses_gateway("https://gateway.example/mcp")
    proofs = {
        "resource_exists": {"status": STATUS_OK},
        "target_ready": {"status": STATUS_OK},
        "tool_invoked": {"status": STATUS_UNVERIFIED},
        "app_uses_gateway": url_terisi,
    }
    hasil = ringkas(proofs)
    assert hasil["integrasi_aktif"] is False
    assert "tool_invoked" in hasil["belum_terbukti"]
    assert "app_uses_gateway" in hasil["belum_terbukti"]


def test_status_di_luar_kosakata_dilaporkan_sebagai_galat():
    proofs = {nama: {"status": STATUS_OK} for nama in GATEWAY_PROOFS}
    proofs["tool_invoked"] = {"status": "DONE"}
    assert bukti_valid(proofs) == ["tool_invoked='DONE'"]


def test_sanitasi_payload_memory_terbukti():
    bersih = {"commodity": "telur", "safe_delivered_cost": 1}
    kotor = {"commodity": "telur", "credentials": {"aws_secret_access_key": "x"}}
    terlarang = ("password", "secret", "token", "credential")
    assert sanitasi_terbukti(bersih, terlarang) is True
    assert sanitasi_terbukti(kotor, terlarang) is False


# ---------------------------------------------------------------------------
# B. Live read-only
# ---------------------------------------------------------------------------


def _region() -> str:
    return (os.environ.get("AWS_REGION") or "us-west-2").strip()


def _klien(nama: str):
    boto3 = pytest.importorskip("boto3")
    return boto3.client(nama, region_name=_region())


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="live AWS: set RUN_LIVE_AGENTCORE=1 (baca-saja)")
def test_gateway_resource_read_only_dan_status_terpisah():
    from botocore.exceptions import ClientError

    bukti = {
        "resource_exists": {"status": STATUS_UNVERIFIED, "detail": None},
        "target_ready": {"status": STATUS_UNVERIFIED, "detail": "belum diperiksa"},
        "tool_invoked": {
            "status": STATUS_UNVERIFIED,
            "detail": "tes ini sengaja tidak memanggil tool",
        },
    }
    try:
        daftar = _klien("bedrock-agentcore-control").list_gateways(maxResults=50)
        gateways = daftar.get("gateways", [])
        bukti["resource_exists"] = {
            "status": STATUS_OK,
            "detail": f"{len(gateways)} gateway terlihat di {_region()}",
            "jumlah": len(gateways),
        }
        if gateways:
            gid = gateways[0]["gatewayId"]
            target = _klien("bedrock-agentcore-control").list_gateway_targets(
                gatewayIdentifier=gid, maxResults=50
            )
            targets = target.get("targets", [])
            bukti["target_ready"] = {
                "status": STATUS_OK if targets else STATUS_UNVERIFIED,
                "detail": f"{len(targets)} target",
            }
        else:
            bukti["target_ready"] = {
                "status": STATUS_UNVERIFIED,
                "detail": "tidak ada gateway untuk diperiksa targetnya",
            }
    except ClientError as exc:
        bukti["resource_exists"] = {
            "status": status_from_error(exc),
            "detail": f"ListGateways gagal: {error_code(exc)}",
        }

    bukti["app_uses_gateway"] = app_uses_gateway(os.environ.get("AGENTCORE_GATEWAY_URL"))

    assert bukti_valid(bukti) == [], f"status di luar kosakata: {bukti_valid(bukti)}"
    assert bukti["tool_invoked"]["status"] == STATUS_UNVERIFIED
    # Tidak ada klaim integrasi aktif dari tes yang tidak memanggil tool.
    assert ringkas(bukti)["integrasi_aktif"] is False


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="live AWS: set RUN_LIVE_AGENTCORE=1 (baca-saja)")
def test_memory_resource_dan_read_allowed():
    from botocore.exceptions import ClientError

    memory_id = (os.environ.get("AGENTCORE_MEMORY_ID") or "").strip()
    if not memory_id:
        pytest.skip("AGENTCORE_MEMORY_ID kosong")

    bukti = {"resource_exists": {"status": STATUS_UNVERIFIED}, "read_allowed": {}}
    try:
        r = _klien("bedrock-agentcore-control").get_memory(memoryId=memory_id)
        mem = r.get("memory", r)
        bukti["resource_exists"] = {
            "status": STATUS_OK,
            "resource_status": mem.get("status"),
            "nama": mem.get("name"),
        }
    except ClientError as exc:
        bukti["resource_exists"] = {"status": status_from_error(exc)}

    try:
        _klien("bedrock-agentcore").list_events(
            memoryId=memory_id,
            actorId="smoke-fase11",
            sessionId="smoke-fase11-" + "0" * 20,
            includePayloads=False,
            maxResults=1,
        )
        bukti["read_allowed"] = {"status": STATUS_OK}
    except ClientError as exc:
        bukti["read_allowed"] = {"status": status_from_error(exc)}

    assert bukti_valid(bukti, ("resource_exists", "read_allowed")) == []
    # Read-only: tidak ada CreateEvent/DeleteEvent di berkas ini.
    print(f"\n[agentcore smoke] memory={bukti}")
