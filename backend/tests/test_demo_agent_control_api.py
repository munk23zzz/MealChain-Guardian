"""Kontrak endpoint Demo Control sederhana: `POST /demo/agent/run` + `GET /demo/agent/last-run`.

Konteks: tab Demo Control disederhanakan (keputusan Roy 2026-10-19) — tanpa
Event 2/3, satu tombol "Jalankan agent" yang memakai lokasi SPPG akun sendiri,
dan satu blok bukti yang dibaca dari DB (bukan dari ingatan klien).

Yang diuji di sini adalah KONTRAK endpoint (guard peran, pemakaian lokasi akun,
pemetaan galat, bentuk bukti). Sejak keputusan pemilik 2026-10-19 endpoint ini
menilai PEMASOK yang memasok SPPG akun sendiri (`supplier_procurement`), jadi
yang diganti fake adalah `run_supplier_procurement` — provider nyata tidak
dipanggil dan tidak ada baris DB uji yang ditulis.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC
from tests.test_actions import _drop_user, _login, _mk_user

#: Status keputusan yang sah — cermin CHECK `decisions_status_check` di DB.
STATUS_KEPUTUSAN = {
    "proposed",
    "verifier_flagged",
    "pending_approval",
    "approved",
    "rejected",
    "executed",
    "review_only",
}


def _status_keputusan(decision_id: str) -> str:
    """Status baris DB untuk satu keputusan (pembanding `last-run`, bukan angka karangan)."""
    engine = create_engine(DSN_SYNC)
    try:
        with engine.connect() as conn:
            return str(
                conn.execute(
                    text("SELECT status FROM decisions WHERE id = CAST(:id AS uuid)"),
                    {"id": decision_id},
                ).scalar_one()
            )
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def pemakai():
    dibuat: list[str] = []

    def _buat(role: str, lokasi: str | None):
        user = _mk_user(role, lokasi)
        dibuat.append(user["email"])
        return user

    yield _buat
    for email in dibuat:
        _drop_user(email)


def _fake_outcome(**kwargs) -> dict:
    return {
        "decision_id": "00000000-0000-0000-0000-000000000002",
        "detect": {"commodity": kwargs.get("commodity")},
        "verifier": {"verdict": "PASS"},
        "forecast": {"forecast_qty_kg": 360.5},
        "supervisor": {
            "status": "narrated",
            "summary": "ringkasan uji",
            "provider": "primary:sap_ai_core",
            "fallback_used": False,
            "attempts": [],
        },
        "mode": "supplier_procurement",
        "suppliers": {"candidates": [], "ranked": [], "chosen": None},
        "decision_snapshot": {"status": "proposed", "approved": False},
        "trace_steps": ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE",
                        "DECIDE", "SUPERVISE"],
    }


# --- guard peran -----------------------------------------------------------


def test_run_tanpa_token_ditolak_401(client):
    assert client.post("/demo/agent/run", json={}).status_code == 401


def test_run_bgn_monitor_ditolak_403(client, monitor_headers):
    resp = client.post("/demo/agent/run", json={}, headers=monitor_headers)
    assert resp.status_code == 403


def test_run_ahli_gizi_ditolak_403(client, pemakai):
    """Jalankan agent membuat keputusan operasional -> kepala SPPG saja."""
    gizi = pemakai("sppg_nutritionist", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, gizi))
    assert resp.status_code == 403


# Catatan: "kepala SPPG tanpa lokasi" TIDAK bisa diuji lewat API karena constraint
# `check_user_role_location_scope` menolak baris seperti itu (sppg_head wajib
# punya location_id). Guard 400 di endpoint tetap dipertahankan sebagai
# pertahanan berlapis bila aturan peran itu berubah; yang dipaku tes adalah
# perilaku yang bisa terjadi di domain.


# --- jalur sukses ----------------------------------------------------------


def test_run_tanpa_payload_menjalankan_semua_komoditas(client, monkeypatch, pemakai):
    dipanggil: dict = {}

    def _fake(commodity, target_location, **kwargs):
        dipanggil.update(commodity=commodity, target_location=target_location, **kwargs)
        return _fake_outcome(commodity=commodity)

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, head))

    assert resp.status_code == 201, resp.text
    # Tanpa payload (28 Okt 2026): SEMUA komoditas, lokasi akun sendiri. Bawaan
    # `beras` dihapus karena lokasi yang tidak kekurangan beras membuat setiap
    # klik berakhir 409. `demo_session_id` = sesi yang sedang berjalan (bila ada),
    # supaya keputusan hasil agent ikut terhapus saat sesi berakhir.
    dipanggil.pop("demo_session_id", None)
    assert dipanggil["target_location"] == "Jakarta"
    assert dipanggil["ttl_minutes"] == 30
    # satu putaran per komoditas; nama datang dari DB, bukan dipaku
    assert dipanggil["commodity"]
    body = resp.json()
    assert body["scope"] == "semua"
    assert body["target_location"] == "Jakarta"
    assert body["supervisor"]["status"] == "narrated"
    assert body["agent_review"]["status"] in {
        "disabled",
        "unavailable",
        "failed",
        "completed",
        "partial",
    }


def test_run_komoditas_dan_ttl_bisa_diubah(client, monkeypatch, pemakai):
    dipanggil: dict = {}

    def _fake(commodity, target_location, **kwargs):
        dipanggil.update(commodity=commodity, target_location=target_location, **kwargs)
        return _fake_outcome(commodity=commodity)

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post(
        "/demo/agent/run",
        json={"commodity": "telur", "ttl_minutes": 45},
        headers=_login(client, head),
    )
    assert resp.status_code == 201, resp.text
    dipanggil.pop("demo_session_id", None)
    assert dipanggil == {"commodity": "telur", "target_location": "Jakarta", "ttl_minutes": 45}


def test_run_ttl_di_luar_batas_422(client, pemakai):
    head = pemakai("sppg_head", "Jakarta")
    resp = client.post(
        "/demo/agent/run", json={"ttl_minutes": 0}, headers=_login(client, head)
    )
    assert resp.status_code == 422


def test_run_tanpa_pemasok_layak_dijawab_409(client, monkeypatch, pemakai):
    def _fake(commodity, target_location, **kwargs):
        raise ValueError(
            f"tidak ada pemasok yang memasok {target_location} untuk {commodity}"
        )

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, head))
    assert resp.status_code == 409
    assert "pemasok" in resp.json()["detail"].lower()


# --- pilihan komoditas ------------------------------------------------------


def test_commodities_tanpa_token_ditolak_401(client):
    assert client.get("/demo/agent/commodities").status_code == 401


def test_commodities_bgn_monitor_ditolak_403(client, monitor_headers):
    assert (
        client.get("/demo/agent/commodities", headers=monitor_headers).status_code
        == 403
    )


def test_commodities_daftar_dari_database(client, pemakai):
    """Dropdown hanya boleh menawarkan komoditas yang punya data di DB."""
    kepala = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/commodities", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    daftar = resp.json()["commodities"]
    assert isinstance(daftar, list) and daftar, "seed wajib menyediakan komoditas"
    assert daftar == sorted(daftar)
    assert "beras" in daftar


def test_commodities_membawa_kasus_neraca_hari_ini(client, pemakai):
    """Balasan `/demo/agent/commodities` menyebut KASUS tiap komoditas.

    Panel demo memakai `bisa_dijalankan` untuk melabeli pilihan: menjalankan agent
    pada komoditas yang justru surplus selalu berakhir 409, jadi statusnya harus
    terbaca SEBELUM tombol ditekan (keputusan 29 Okt 2026 — demo bervariasi per
    kasus, tanpa jalan buntu).
    """
    kepala = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/commodities", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    isi = resp.json()
    assert isi["location"] == "Jakarta"
    kasus = {k["commodity"]: k for k in isi["kasus"]}
    assert set(kasus) == set(isi["commodities"]), "tiap komoditas wajib punya baris kasus"
    for k in kasus.values():
        assert k["status"] in {"shortage", "surplus", "balanced", "tanpa_data"}
        assert k["bisa_dijalankan"] is (k["status"] == "shortage")
        if k["status"] == "shortage":
            assert k["shortage_kg"] > 0
        elif k["status"] == "surplus":
            assert k["sebab"], "surplus wajib menjelaskan kenapa agent tidak dijalankan"


def test_kasus_komoditas_sepakat_dengan_balance(client, pemakai):
    """Label kasus di panel demo = angka `/balance` untuk pasangan yang sama.

    Dua tempat menghitung sendiri adalah dua kebenaran; tes ini menutup celah itu:
    status dan kg kekurangan/surplus harus identik dengan halaman balance.
    """
    kepala = pemakai("sppg_head", "Jakarta")
    headers = _login(client, kepala)
    isi = client.get("/demo/agent/commodities", headers=headers).json()
    for k in isi["kasus"]:
        if k["status"] == "tanpa_data":
            continue
        bal = client.get(f"/balance/{isi['location']}/{k['commodity']}", headers=headers)
        assert bal.status_code == 200, bal.text
        assert bal.json()["status"] == k["status"]
        assert bal.json()["shortage_kg"] == k["shortage_kg"]
        assert bal.json()["surplus_kg"] == k["surplus_kg"]


# --- bukti (last run) ------------------------------------------------------


def test_last_run_tanpa_token_ditolak_401(client):
    assert client.get("/demo/agent/last-run").status_code == 401


def test_last_run_bgn_monitor_ditolak_403(client, monitor_headers):
    assert client.get("/demo/agent/last-run", headers=monitor_headers).status_code == 403


def test_last_run_memakai_keepala_sppg(client, pemakai):
    head = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/last-run", headers=_login(client, head))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "found" in body
    if body["found"]:
        # Semua angka di blok bukti berasal dari DB: id keputusan nyata, langkah
        # nyata, dan narasi/provider yang benar-benar tercatat.
        uuid.UUID(body["decision_id"])
        assert body["steps"], "bukti tanpa langkah bukan bukti"
        assert "DETECT" in [s["step_name"] for s in body["steps"]]
        assert body["supervisor"]["status"] in {"narrated", "unavailable", "error", "missing"}
        # Status TIDAK dipaku `proposed`: putaran yang sama bisa sudah disetujui
        # sesudah dibuat (suite ini memang menyetujui beberapa putaran), dan
        # endpoint wajib melaporkan status TERKINI. Yang diuji: angkanya sama
        # dengan baris DB-nya — bukan angka karangan.
        assert body["status"] == _status_keputusan(body["decision_id"])
        assert body["status"] in STATUS_KEPUTUSAN
        # Delapan kartu agen di panel "Bukti agent" (tujuh analitik + verifier):
        # kunci tetap dan status hanya dari baris review yang tersimpan.
        assert [a["key"] for a in body["agents"]] == [
            "supply",
            "demand",
            "freshness",
            "safety",
            "price",
            "logistics",
            "evidence",
            "verifier",
        ]
        for agen in body["agents"]:
            assert agen["status"] in {
                "ok",
                "degraded",
                "error",
                "missing",
            }
            if agen["status"] == "missing":
                assert agen["duration_ms"] is None
    else:
        assert body.get("steps", []) == []
        assert body["agents"] == []

def test_last_run_memuat_bukti_pemasok(client, pemakai):
    """Bukti pengadaan: pemasok yang dinilai + kekurangan yang dipenuhi.

    Bentuknya wajib stabil walau belum ada putaran (`found: false`), supaya UI
    tidak perlu menebak kunci yang hilang.
    """
    kepala = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/last-run", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "supplier" in body and "supply_gap" in body and "mode" in body
    if not body["found"]:
        assert body["supplier"] is None
        return
    if body["mode"] == "supplier_procurement":
        # Angka bukti berasal dari trace DB, bukan dihitung ulang endpoint.
        assert body["supplier"]["name"], "keputusan pengadaan wajib punya pemasok"
        assert body["supply_gap"]["gap_kg"] is not None
        assert body["source_location"] is None


def test_last_run_hanya_putaran_pipeline(client, pemakai):
    """Bukti "putaran agent" wajib berasal dari pipeline penuh, bukan baris seed.

    Regresi (gerbang 21 Okt 2026): endpoint jatuh ke "keputusan dengan DETECT
    terakhir", sehingga keputusan hasil template/seed — yang juga menulis
    DETECT/DECIDE/ACT — dilaporkan sebagai putaran agent. Akibatnya `status`
    bukan `proposed` dan `supply_gap.gap_kg` kosong padahal `mode` pengadaan.

    Ciri putaran NYATA: ada langkah pipeline penuh (PREDICT/OPTIMIZE/SUPERVISE)
    yang ditulis tanpa `agent_name` (baris review worker memakai nama agen).
    """
    kepala = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/last-run", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    if not body["found"]:
        return
    nama = {langkah["step_name"] for langkah in body["steps"]}
    assert {"DETECT", "DECIDE"} <= nama, (
        "bukti putaran agent tanpa DETECT+DECIDE: " + ", ".join(sorted(nama))
    )
    assert nama & {"PREDICT", "OPTIMIZE", "SUPERVISE"}, (
        "bukti putaran agent tanpa satu pun langkah pipeline: "
        + ", ".join(sorted(nama))
    )
    # Catatan: pengecualian salinan 4 kasus skrip (`decisions.demo_case` terisi)
    # diuji lewat kode endpoint (filter `demo_case IS NULL`), bukan lewat payload —
    # payload sengaja tidak membuka kolom penyemai ke UI.


def test_last_run_memetakan_review_walau_tiap_baris_punya_run_id_sendiri(
    client, pemakai
) -> None:
    """Regresi 27 Okt 2026: kartu agen "missing" padahal baris review tersimpan.

    Bentuk yang direproduksi = runtime yang menjalankan tiap agen sebagai
    invokasi sendiri: setiap baris worker membawa `run_id` BERBEDA, sedangkan
    baris ringkasan SUPERVISE membawa `run_id` putaran. Versi lama memetakan
    hanya baris yang `run_id`-nya sama dengan run putaran itu, sehingga kedelapan
    kartu tampak "belum tercatat".

    Yang diuji: bila `agent_traces` untuk putaran itu ADA, kartu agen wajib
    menampilkan statusnya — bukan "missing" — dan status review dibaca dari
    baris `agent.review*` yang tersimpan.
    """
    kunci = uuid.uuid5(uuid.NAMESPACE_URL, "mealchain:uji-last-run-review-run-ids")
    putaran = uuid.uuid5(uuid.NAMESPACE_URL, "mealchain:uji-putaran-review")
    langkah = ("DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE", "SUPERVISE")
    agen = (
        "supply",
        "demand",
        "freshness",
        "safety",
        "price",
        "logistics",
        "evidence",
        "verifier",
    )
    engine = create_engine(DSN_SYNC)

    def _bersihkan(conn) -> None:
        conn.execute(
            text("DELETE FROM decisions WHERE id = CAST(:id AS uuid)"), {"id": str(kunci)}
        )

    try:
        with engine.begin() as conn:
            _bersihkan(conn)
            conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                    "expires_at, created_at, origin) VALUES (CAST(:id AS uuid), "
                    "'supplier_procurement', 'proposed', 'supervisor_agent', "
                    "now() + interval '1 hour', now(), 'demo')"
                ),
                {"id": str(kunci)},
            )
            for nama in langkah:
                conn.execute(
                    text(
                        "INSERT INTO agent_traces (decision_id, step_name, tool_called, step_at) "
                        "VALUES (CAST(:id AS uuid), :step, :tool, now())"
                    ),
                    {"id": str(kunci), "step": nama, "tool": f"uji.{nama.lower()}"},
                )
            # Baris review: tiap agen punya run_id sendiri (invokasi terpisah).
            for nama in agen:
                status = "degraded" if nama == "verifier" else "ok"
                conn.execute(
                    text(
                        "INSERT INTO agent_traces (decision_id, step_name, agent_name, "
                        "tool_called, run_id, output_summary, step_at) VALUES ("
                        "CAST(:id AS uuid), :step, :agen, :tool, CAST(:run AS uuid), "
                        "CAST(:out AS jsonb), now())"
                    ),
                    {
                        "id": str(kunci),
                        "step": "VERIFY" if nama == "verifier" else "DETECT",
                        "agen": nama,
                        "tool": f"agent.{nama}",
                        "run": str(uuid.uuid5(uuid.NAMESPACE_URL, f"mealchain:run:{nama}")),
                        "out": json.dumps({"status": status, "summary": f"{nama} uji"}),
                    },
                )
            # Ringkasan SUPERVISE membawa run putaran (bukan run tiap agen).
            conn.execute(
                text(
                    "INSERT INTO agent_traces (decision_id, step_name, agent_name, "
                    "tool_called, run_id, output_summary, step_at) VALUES ("
                    "CAST(:id AS uuid), 'SUPERVISE', 'supervisor', "
                    "'agent.review_summary', CAST(:run AS uuid), CAST(:out AS jsonb), now())"
                ),
                {
                    "id": str(kunci),
                    "run": str(putaran),
                    "out": json.dumps(
                        {"status": "completed", "narrative": "status run: completed"}
                    ),
                },
            )

        kepala = pemakai("sppg_head", "Jakarta")
        resp = client.get("/demo/agent/last-run", headers=_login(client, kepala))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["found"] is True
        assert body["decision_id"] == str(kunci)
        assert body["agents_run_id"] == str(putaran)
        status_per_agen = {a["key"]: a["status"] for a in body["agents"]}
        assert status_per_agen == {
            "supply": "ok",
            "demand": "ok",
            "freshness": "ok",
            "safety": "ok",
            "price": "ok",
            "logistics": "ok",
            "evidence": "ok",
            "verifier": "degraded",
        }, status_per_agen
        assert "missing" not in status_per_agen.values()
        assert body["agent_review"]["status"] == "completed"
    finally:
        with engine.begin() as conn:
            _bersihkan(conn)
        engine.dispose()


def test_last_run_memilih_putaran_pipeline_penuh(client, pemakai) -> None:
    """Kasus POSITIF: putaran pipeline lengkap benar-benar terpilih.

    Tanpa tes ini, filter "jejak pipeline lengkap" bisa lolos hanya karena
    endpoint selalu menjawab `found: false` (baris semai tidak memenuhi syarat) —
    panel Demo Control lalu diam-diam tidak pernah menampilkan bukti.
    """
    kunci = uuid.uuid5(uuid.NAMESPACE_URL, "mealchain:uji-last-run-pipeline")
    langkah = ("DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE", "SUPERVISE")
    engine = create_engine(DSN_SYNC)

    def _bersihkan(conn) -> None:
        # FK agent_traces → decisions ON DELETE CASCADE, jadi satu DELETE cukup.
        conn.execute(
            text("DELETE FROM decisions WHERE id = CAST(:id AS uuid)"), {"id": str(kunci)}
        )

    try:
        with engine.begin() as conn:
            _bersihkan(conn)
            conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                    "expires_at, created_at, origin) VALUES (CAST(:id AS uuid), "
                    "'supplier_procurement', 'proposed', 'supervisor_agent', "
                    "now() + interval '1 hour', now(), 'demo')"
                ),
                {"id": str(kunci)},
            )
            for nama in langkah:
                conn.execute(
                    text(
                        "INSERT INTO agent_traces (decision_id, step_name, tool_called, step_at) "
                        "VALUES (CAST(:id AS uuid), :step, :tool, now())"
                    ),
                    {"id": str(kunci), "step": nama, "tool": f"uji.{nama.lower()}"},
                )

        kepala = pemakai("sppg_head", "Jakarta")
        resp = client.get("/demo/agent/last-run", headers=_login(client, kepala))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["found"] is True, "putaran pipeline lengkap tidak terdeteksi"
        assert body["decision_id"] == str(kunci), "putaran pipeline terbaru wajib menang"
        assert body["mode"] == "supplier_procurement"
        assert {s["step_name"] for s in body["steps"]} == set(langkah)
    finally:
        with engine.begin() as conn:
            _bersihkan(conn)
        engine.dispose()


# --- putaran SEMUA komoditas (28 Okt 2026) ----------------------------------
#
# Kenapa ada: bawaan `beras` membuat tombol "Jalankan agent" selalu 409 di
# lokasi yang tidak kekurangan beras, padahal komoditas lain punya celah
# pasokan. Sekarang satu klik menjalankan satu putaran per komoditas, dan
# komoditas yang tidak punya celah DILEWATI (dilaporkan di `skipped`) bukan
# menggagalkan seluruh permintaan.


def test_run_semua_komoditas_satu_gagal_tidak_membatalkan_lain(
    client, monkeypatch, pemakai
):
    dipanggil: list[str] = []

    def _fake(commodity, target_location, **kwargs):
        dipanggil.append(commodity)
        if commodity == "beras":
            raise ValueError("tidak ada pemasok yang memasok Jakarta untuk beras")
        return _fake_outcome(commodity=commodity)

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, head))

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(dipanggil) > 1, "tanpa payload: satu putaran per komoditas"
    dibuat = {c["commodity"] for c in body["created"]}
    dilewati = {s["commodity"]: s["reason"] for s in body["skipped"]}
    assert "beras" not in dibuat
    assert "pemasok" in dilewati["beras"].lower()
    assert dibuat, "komoditas lain tetap menghasilkan keputusan"
    assert body["primary_decision_id"] == body["decision_id"]
    assert body["scope"] == "semua"


def test_run_semua_komoditas_gagal_semua_dijawab_409(client, monkeypatch, pemakai):
    def _fake(commodity, target_location, **kwargs):
        raise ValueError(
            f"tidak ada pemasok yang memasok {target_location} untuk {commodity}"
        )

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, head))

    assert resp.status_code == 409
    detail = resp.json()["detail"].lower()
    assert "tidak ada komoditas" in detail
    assert "pemasok" in detail, "alasan per komoditas ikut dilaporkan"


class _SesiPalsu:
    """Bentuk minimal yang dibaca `blok_sesi` (id, mode, jangkar, dataset)."""

    id = uuid.uuid4()
    mode = "realtime"
    evaluation_anchor = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)
    dataset_version = "uji"


def test_run_terikat_sesi_demo_yang_sedang_berjalan(client, monkeypatch, pemakai):
    """Keputusan hasil agent WAJIB berstempel sesi. Tanpa stempel, "Akhiri sesi"
    tidak pernah menghapusnya, jadi data demo tidak hilang saat waktu demo habis.
    """
    diterima: dict = {}
    ditandai: list[uuid.UUID] = []

    def _fake(commodity, target_location, **kwargs):
        diterima.update(kwargs)
        return _fake_outcome(commodity=commodity)

    async def _aktif(db):
        return _SesiPalsu()

    async def _tandai(db, sesi_id):
        ditandai.append(sesi_id)
        return 0

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)
    monkeypatch.setattr("app.services.demo_session.aktif", _aktif)
    monkeypatch.setattr("app.services.demo_session.tandai_sesi", _tandai)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post(
        "/demo/agent/run",
        json={"commodity": "telur"},
        headers=_login(client, head),
    )

    assert resp.status_code == 201, resp.text
    assert diterima["demo_session_id"] == _SesiPalsu.id
    assert ditandai == [_SesiPalsu.id], "baris Core/bulk ikut distempel sesi"


def test_run_tanpa_sesi_saat_penjaga_menyala_dijawab_409(
    client, monkeypatch, pemakai
):
    """Penjaga sesi menyala + tidak ada sesi aktif = tolak, bukan menulis baris
    kanonik yang tidak akan pernah terhapus."""
    async def _aktif(db):
        return None

    monkeypatch.setattr(
        "app.api.demo.run_supplier_procurement",
        lambda commodity, target_location, **kwargs: _fake_outcome(commodity=commodity),
    )
    monkeypatch.setattr("app.services.demo_session.aktif", _aktif)

    from app.core.config import settings

    monkeypatch.setattr(settings, "demo_session_enforce", True, raising=False)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post(
        "/demo/agent/run",
        json={"commodity": "telur"},
        headers=_login(client, head),
    )

    assert resp.status_code == 409
    assert "sesi demo" in resp.json()["detail"].lower()

