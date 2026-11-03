"""Kontrak artefak Joule (BTP side) — dikunci oleh tes, bukan oleh ingatan.

Latar: 18 Okt 2026 assistant Joule yang sudah dideploy tidak lagi muncul di tenant
(`joule list` kosong), sementara berkas capability di repo masih ada. Supaya kejadian
"artefaknya hilang / berubah tanpa ketahuan" tertangkap sebelum deploy, tes ini membaca
YAML apa adanya dan memeriksa hal-hal yang benar-benar ditolak Joule saat deploy:

* `schema_version` capability >= 3.28.0 (syarat action `agent-request`)
* `namespace: joule.ext` (namespace lain ditolak)
* `destination` = `SWZ_JOULE` (destination panitia; salah huruf -> "destination not found")
* fungsi yang dituju scenario benar-benar ada dan memakai `agent-request` + `result_variable`
* jalur SpEL artefak (`apiResponse.body.artifacts[0].parts[0].text`) tidak berubah, karena
  itulah satu-satunya cara jawaban jembatan sampai ke pengguna Joule.

Tes ini tidak butuh kredensial SAP dan tidak menyentuh tenant.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SAP_JOULE = Path(__file__).resolve().parents[2]
FOLDER = SAP_JOULE / "joule"
CAP = FOLDER / "mealchain_capability"
SPEL_ARTEFAK = "<? apiResponse.body.artifacts[0].parts[0].text ?>"


def _muat(path: Path) -> dict:
    with path.open(encoding="utf-8") as berkas:
        return yaml.safe_load(berkas)


def _versi(teks: str) -> tuple[int, ...]:
    return tuple(int(bagian) for bagian in str(teks).split("."))


@pytest.fixture(scope="module")
def da() -> dict:
    return _muat(FOLDER / "da.sapdas.yaml")


@pytest.fixture(scope="module")
def capability() -> dict:
    return _muat(CAP / "capability.sapdas.yaml")


@pytest.fixture(scope="module")
def fungsi() -> dict:
    return _muat(CAP / "functions" / "mealchain_query_function.yaml")


@pytest.fixture(scope="module")
def scenario() -> dict[str, dict]:
    berkas = sorted((CAP / "scenarios").glob("*.yaml"))
    return {path.stem: _muat(path) for path in berkas}


def test_da_menunjuk_folder_capability_yang_ada(da):
    assert _versi(da["schema_version"]) == (1, 4, 0)
    assert da["name"].endswith("_4sehat3trio"), "nama DA wajib ber-slug tim (tenant dipakai bersama)"
    kapabilitas = da["capabilities"]
    assert len(kapabilitas) == 1 and kapabilitas[0]["type"] == "local"
    folder = (FOLDER / kapabilitas[0]["folder"]).resolve()
    assert (folder / "capability.sapdas.yaml").is_file()


def test_capability_memenuhi_syarat_deploy(capability):
    assert _versi(capability["schema_version"]) >= (3, 28, 0), "agent-request butuh >= 3.28.0"
    assert capability["metadata"]["namespace"] == "joule.ext"
    assert capability["metadata"]["name"] == CAP.name
    assert _versi(capability["metadata"]["version"])
    assert capability["metadata"]["display_name"]
    deskripsi = capability["metadata"]["description"].lower()
    assert "baca-saja" in deskripsi or "read-only" in deskripsi
    assert "manusia" in deskripsi, "deskripsi harus menyatakan persetujuan tetap oleh manusia"


def test_alias_sistem_menunjuk_destination_jembatan(capability):
    alias = capability["system_aliases"]
    assert "MEALCHAIN_AGENT" in alias
    # SWZ_JOULE milik panitia dan BUKAN endpoint A2A (POST / -> 401). Kalau alias dikembalikan
    # ke sana, deploy berikutnya menghasilkan "Something went wrong" di chat.
    assert alias["MEALCHAIN_AGENT"]["destination"] == "MEALCHAIN_AGENT_01", (
        "destination kanonik = MEALCHAIN_AGENT_01 (menunjuk jembatan A2A); SWZ_JOULE bukan A2A"
    )


def test_fungsi_memakai_agent_request_ke_alias_yang_benar(fungsi, capability):
    aksi = fungsi["action_groups"][0]["actions"]
    jenis = [langkah["type"] for langkah in aksi]
    assert jenis == ["status-update", "agent-request", "message"]

    permintaan = aksi[1]
    assert permintaan["system_alias"] in capability["system_aliases"]
    assert permintaan["agent_type"] == "remote"
    assert permintaan["result_variable"] == "apiResponse"


def test_jalur_artefak_tidak_berubah(fungsi):
    pesan = fungsi["action_groups"][0]["actions"][2]["message"]
    assert pesan["type"] == "text"
    assert pesan["markdown"] is True
    assert pesan["content"] == SPEL_ARTEFAK


def test_semua_scenario_menargetkan_fungsi_yang_sama(scenario):
    assert set(scenario) == {
        "situasi_pasokan",
        "indikator_kinerja",
        "antrean_usulan",
        "detail_purchase_order",
        "harga_pemasok",
        "kebutuhan_prakiraan",
        "kehilangan_pangan",
        "risiko_pemasok",
        "bukti_keputusan",
        "status_sistem",
        # Ditambahkan 22 Okt 2026: tiga skill jembatan yang sebelumnya tidak punya
        # scenario, sehingga tidak bisa dipicu dari chat Joule sama sekali.
        "direktori_pemasok",
        "antrean_penerimaan",
        "status_karantina",
        # 29 Okt 2026: rincian keamanan satu batch (suhu, kebijakan, bukti) — sebelumnya
        # Joule hanya bisa melihat baris daftar `/batches`.
        "detail_batch",
        # 30 Okt 2026: surplus per wilayah + rencana alih antar SPPG.
        "surplus_wilayah",
    }
    for nama, isi in scenario.items():
        assert isi["target"] == {"name": "mealchain_query_function", "type": "function"}, nama
        assert len(isi["description"]) > 80, f"deskripsi {nama} terlalu pendek untuk NLU"


def test_setiap_skill_jembatan_punya_scenario(scenario):
    """Setiap skill yang bisa dipilih `resolve_skill` harus punya scenario Joule.

    `supply_situation` adalah DEFAULT (bisa dicapai tanpa scenario khusus) dan
    `unsupported_domain` sengaja TIDAK ditawarkan sebagai skill (tidak ada di `SKILLS`,
    tidak ada di agent card) karena jawabannya "belum tersedia", bukan data.

    Tanpa tes ini, menambah skill baru di jembatan tanpa scenario akan lolos tanpa gejala:
    pertanyaannya cuma jatuh ke default pasokan.
    """
    from server import _KEYWORDS, _PO_WORD, SKILLS, SKILL_GAP, SKILL_SUPPLY

    peta = {
        "kpi_snapshot": "indikator_kinerja",
        "approval_queue": "antrean_usulan",
        "purchase_order": "detail_purchase_order",
        "supplier_directory": "direktori_pemasok",
        "price_intelligence": "harga_pemasok",
        "demand_forecast": "kebutuhan_prakiraan",
        "food_loss": "kehilangan_pangan",
        "supplier_risk": "risiko_pemasok",
        "receipts_queue": "antrean_penerimaan",
        "quarantine_status": "status_karantina",
        "batch_detail": "detail_batch",
        "decision_evidence": "bukti_keputusan",
        "system_status": "status_sistem",
        "surplus_region": "surplus_wilayah",
    }
    assert set(SKILLS) - {SKILL_SUPPLY} == set(peta), (
        "skill jembatan dan peta scenario tidak sinkron"
    )
    assert SKILL_GAP not in SKILLS
    for skill, nama_scenario in peta.items():
        assert nama_scenario in scenario, f"skill {skill} tidak punya scenario"
        if skill == "purchase_order":
            # PO tidak ada di `_KEYWORDS`: bentuknya regex sendiri (`_PO_WORD`), dan
            # kesetiaan kata kuncinya sudah dikunci test_scenario_po_… di bawah.
            assert _PO_WORD.search(scenario[nama_scenario]["description"])
            continue
        deskripsi = scenario[nama_scenario]["description"].lower()
        kunci = {k for s, daftar in _KEYWORDS if s == skill for k in daftar}
        assert any(k in deskripsi for k in kunci), (
            f"scenario {nama_scenario} tidak memuat satu pun kata kunci {sorted(kunci)[:3]}"
        )


def test_scenario_antrean_menegaskan_persetujuan_manusia(scenario):
    deskripsi = scenario["antrean_usulan"]["description"].lower()
    assert "read-only" in deskripsi
    assert "human" in deskripsi and "never through joule" in deskripsi


def test_kata_kunci_scenario_cocok_dengan_skill_jembatan(scenario):
    """Scenario dan `resolve_skill` di jembatan harus memakai kata kunci yang sama.

    Kalau salah satu diubah tanpa yang lain, Joule akan mengirim pertanyaan ke skill yang
    salah tanpa error apa pun — kegagalan senyap yang paling mahal saat demo.

    `supply_situation` adalah DEFAULT di jembatan (tidak punya daftar kata kunci), jadi yang
    diperiksa untuknya adalah: deskripsinya memakai kosakata pasokan dan TIDAK memuat kata
    kunci milik skill lain (kalau tidak, pertanyaan pasokan akan direbut KPI/antrean).
    """
    from server import _KEYWORDS

    peta = {
        "kpi_snapshot": "indikator_kinerja",
        "approval_queue": "antrean_usulan",
        "price_intelligence": "harga_pemasok",
        "demand_forecast": "kebutuhan_prakiraan",
        "food_loss": "kehilangan_pangan",
        "supplier_risk": "risiko_pemasok",
        "decision_evidence": "bukti_keputusan",
        "system_status": "status_sistem",
        "surplus_region": "surplus_wilayah",
    }
    for skill, nama_scenario in peta.items():
        deskripsi = scenario[nama_scenario]["description"].lower()
        kata_kunci = next(k for s, k in _KEYWORDS if s == skill)
        cocok = [k for k in kata_kunci if k in deskripsi]
        assert cocok, f"scenario {nama_scenario} tidak memuat kata kunci {kata_kunci[:3]}"

    pasokan = scenario["situasi_pasokan"]["description"].lower()
    assert "pasokan" in pasokan and "surplus" in pasokan
    semua_kunci_lain = {k for _, kunci in _KEYWORDS for k in kunci}
    bentrok = sorted(k for k in semua_kunci_lain if k in pasokan)
    assert not bentrok, f"deskripsi pasokan memuat kata kunci skill lain: {bentrok}"


def test_scenario_po_memakai_kata_kunci_po_dan_tidak_direbut_scenario_lain(scenario):
    """Sama seperti KPI/antrean: kata kunci PO harus ada di scenario-nya, dan TIDAK di lain.

    Tanpa pemeriksaan ini, menambah scenario PO bisa membuat pertanyaan pasokan/KPI direbut
    scenario PO (atau sebaliknya) tanpa satu pun tes lama gagal — kegagalan senyap.
    """
    from server import _PO_WORD

    po = scenario["detail_purchase_order"]["description"]
    assert _PO_WORD.search(po), "deskripsi scenario PO tidak memuat kata kunci PO"
    assert "read-only" in po.lower()

    for nama in ("situasi_pasokan", "indikator_kinerja", "antrean_usulan"):
        assert not _PO_WORD.search(scenario[nama]["description"]), (
            f"deskripsi {nama} memuat kata kunci PO — pertanyaannya bisa direbut scenario PO"
        )


def test_agent_card_menawarkan_skill_yang_sama_dengan_jembatan():
    from fastapi.testclient import TestClient
    from server import SKILLS, app

    kartu = TestClient(app).get("/.well-known/agent-card.json").json()
    assert {skill["id"] for skill in kartu["skills"]} == set(SKILLS)


def test_templat_env_tidak_menyimpan_secret():
    """URL/ID boleh terisi (bukan rahasia); SECRET/PASSWORD/TOKEN wajib kosong."""
    baris = (FOLDER / "joule.env.example").read_text(encoding="utf-8").splitlines()
    rahasia = ("SECRET", "PASSWORD", "TOKEN")
    for b in baris:
        if not b.strip() or b.lstrip().startswith("#") or "=" not in b:
            continue
        kunci, _, nilai = b.partition("=")
        nama = kunci.strip().upper()
        if any(pola in nama for pola in rahasia):
            assert nilai.strip() == "", f"{nama} berisi nilai; templat tidak boleh memuat secret"
        assert "://" not in nilai or "@" not in nilai, f"{nama} tampak memuat kredensial di URL"
