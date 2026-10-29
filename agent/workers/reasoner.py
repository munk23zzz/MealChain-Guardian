"""Lapisan penalaran model untuk tujuh worker Agent (27 Okt 2026).

Sejarah singkat. Sampai 26 Okt 2026 ketujuh worker (`supply`, `demand`,
`freshness`, `safety`, `price`, `logistics`, `evidence`) murni deterministik:
membaca API, menghitung, lalu menyusun ringkasan template. Permintaan pemilik
27 Okt 2026: jadikan ketujuhnya **agent** — boleh menalar dengan model — tanpa
mengorbankan jaminan keselamatan yang sudah diuji.

Karena itu lapisan ini sengaja dibuat sebagai *advisory reasoning*, bukan
pengganti pemeriksa:

- Fakta, status, dan `blocking` tetap milik kode deterministik. Model tidak bisa
  melonggarkan blokir, menurunkan status, atau menghapus warning.
- Model hanya boleh memperkaya `summary`, menambah warning, dan mengisi
  `rationale` + `confidence`.
- Model tidak boleh menambah angka yang tidak ada di fakta. Ringkasan yang
  memuat angka baru ditolak utuh (`status="rejected"`) — anti-karang.
- Model gagal/timeout/JSON rusak → temuan deterministik dipertahankan dan
  alasannya dicatat (`unavailable` / `invalid`). Tidak pernah jadi error 500.

Saklar: `WORKER_AGENT_MODE=off|advisory` (default `advisory`) dan `WORKER_AGENT_MODEL`
(model id; kosong → lapisan ini tidak pernah aktif).

Sembilan agent, satu pintu resolusi (27 Okt 2026). Lapisan ini melayani tujuh
worker analitik **plus supervisor** (narasi) dan **verifier** (audit), dengan
urutan jalur model yang SAMA:

1. `provider_chain` — rantai provider backend (`build_default_callers("supervisor")`
   dari `backend/app/ai_providers`), dipakai lebih dulu supaya konfigurasi env
   yang sudah tersertifikasi tidak diduplikasi di sini. Hanya tersedia saat modul
   ini berjalan DI DALAM backend (`AGENT_REVIEW_MODE=local`).
2. `bedrock_converse` — boto3 `bedrock-runtime.converse`, untuk runtime yang
   punya kredensial AWS tetapi tanpa SDK `strands` (image backend).
3. `strands` — SDK Strands, jalur lama untuk image runtime AgentCore.
4. `none` — tidak ada model; pemanggil menandai `unavailable`, temuan
   deterministik tetap dipakai.

Alasan urutan ini: `strands` TIDAK terpasang di image backend, sehingga
sebelumnya jalur in-process selalu `unavailable` — lapisan penalaran mati bukan
karena tidak ada model, tetapi karena satu-satunya pintu butuh SDK yang tidak
ada. Kredensial tidak pernah dicetak/dilog modul ini; yang dilaporkan hanya
nama jalur dan pesan error provider.

Prompt sistem tidak boleh saling pinjam (`prompt_sistem`): supervisor memakai
`prompts/supervisor_system_prompt.md`, verifier memakai
`prompts/verifier_system_prompt.md` — independensi verifier (AUD-9A-03).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from time import monotonic

from ..contracts import AgentFinding, AgentName, WorkerStatus

ModelCallable = Callable[[str], str]

ENV_MODE = "WORKER_AGENT_MODE"
ENV_MODEL = "WORKER_AGENT_MODEL"
#: Model per-agent — TIDAK ada cadangan lintas agent. Verifier adalah pemeriksa
#: independen: ia hanya menalar bila `VERIFIER_AGENT_MODEL` diset eksplisit,
#: bukan meminjam model supervisor (pernah terjadi dan memveto semua putaran).
ENV_MODEL_SUPERVISOR = "SUPERVISOR_MODEL_PRIMARY"
ENV_MODEL_VERIFIER = "VERIFIER_AGENT_MODEL"
ENV_REGION = "AWS_REGION"
ENV_REGION_CADANGAN = "AWS_DEFAULT_REGION"

MODE_OFF = "off"
MODE_ADVISORY = "advisory"
MODE_SAH = {MODE_OFF, MODE_ADVISORY}

#: Sembilan agent yang memakai lapisan ini: tujuh worker analitik + supervisor
#: (narasi) + verifier (audit).
AGENT_WORKER: tuple[str, ...] = (
    "supply",
    "demand",
    "freshness",
    "safety",
    "price",
    "logistics",
    "evidence",
)
AGENT_SUPERVISOR = "supervisor"
AGENT_VERIFIER = "verifier"
AGENT_PENALARAN: tuple[str, ...] = (*AGENT_WORKER, AGENT_SUPERVISOR, AGENT_VERIFIER)

#: Nama jalur model yang dilaporkan apa adanya (tidak pernah menebak).
JALUR_PROVIDER_CHAIN = "provider_chain"
JALUR_BEDROCK = "bedrock_converse"
JALUR_STRANDS = "strands"
JALUR_NONE = "none"

PROMPT_AGENT_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_DIR = PROMPT_AGENT_DIR / "workers"
PROMPT_SUPERVISOR = PROMPT_AGENT_DIR / "supervisor_system_prompt.md"
PROMPT_VERIFIER = PROMPT_AGENT_DIR / "verifier_system_prompt.md"

#: Prefix model id yang BUKAN milik Bedrock (SAP AI Core, Inferhub, ARN).
#: Jangan pernah dikirim ke `bedrock-runtime`: pasti ditolak, dan galatnya
#: menyamarkan salah konfigurasi sebagai provider yang mati.
_NON_BEDROCK_PREFIX = ("sap-ai-core:", "cc/", "cb/", "cbcn/", "cx/", "ali/", "arn:")

DEFAULT_REGION = "us-west-2"
MAKS_TOKEN = 1600
#: Instruksi dasar untuk jalur yang tidak membawa system prompt sendiri
#: (worker membawa prompt Markdown-nya di badan prompt).
SISTEM_WORKER = (
    "Anda pengulas rantai pasok pangan institusional. Anda HANYA boleh "
    "menjelaskan fakta yang diberikan. Jangan menambah angka, jangan "
    "menyarankan eksekusi otomatis, dan jawab dalam JSON."
)

#: Angka apa pun yang muncul di teks (termasuk desimal gaya 1.234,56 / 1234.56).
_POLA_ANGKA = re.compile(r"\d+(?:[.,]\d+)*")
#: Angka bergaya Indonesia: titik = pemisah ribuan, koma = desimal (1.080,0).
_POLA_ANGKA_RIBUAN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")


def prompt_sistem(agent: str) -> str:
    """Prompt agent penalaran: SATU berkas per agent, tanpa saling pinjam.

    Supervisor dan verifier sengaja punya berkas sendiri; verifier mengaudit
    supervisor (AUD-9A-03), jadi memakai prompt supervisor di sana akan
    menghapus independensinya. Nama agent tak dikenal ditolak, bukan
    dipetakan diam-diam ke prompt agent lain.
    """
    if agent == AGENT_SUPERVISOR:
        berkas = PROMPT_SUPERVISOR
    elif agent == AGENT_VERIFIER:
        berkas = PROMPT_VERIFIER
    elif agent in AGENT_WORKER:
        berkas = PROMPT_DIR / f"{agent}.md"
    else:
        raise ValueError(f"agent penalaran tidak dikenal: {agent}")
    if not berkas.is_file():
        raise FileNotFoundError(f"prompt agent tidak ada: {berkas}")
    return berkas.read_text(encoding="utf-8")


def _system_untuk(agent: str | None) -> str | None:
    """System prompt yang ditempel di titik resolusi, sekali saja.

    Worker TIDAK dapat system tambahan: prompt Markdown-nya sudah menjadi
    bagian badan prompt (`PromptWorker.bangun_prompt`), jadi menempelkannya
    lagi hanya menggandakan instruksi. Supervisor/verifier sebaliknya: prompt
    mereka tidak ikut di badan prompt pemanggil, jadi harus ditempel di sini.
    """
    if agent in (AGENT_SUPERVISOR, AGENT_VERIFIER):
        return prompt_sistem(agent)
    return None


def _region_dari_env(env: Mapping[str, str] | None = None) -> str:
    sumber: Mapping[str, str] = os.environ if env is None else env
    for kunci in (ENV_REGION, ENV_REGION_CADANGAN):
        nilai = (sumber.get(kunci) or "").strip()
        if nilai:
            return nilai
    return DEFAULT_REGION


def mode_dari_env(env: Mapping[str, str] | None = None) -> str:
    """Mode lapisan penalaran. Default `advisory` (otomatis untuk 9 agent);
    `off` eksplisit mematikan, nilai asing juga jatuh ke default."""
    sumber: Mapping[str, str] = os.environ if env is None else env
    nilai = (sumber.get(ENV_MODE) or "").strip().lower()
    return nilai if nilai in MODE_SAH else MODE_ADVISORY


def kunci_model_untuk(agent: str | None) -> str:
    """Kunci env model milik satu agent (tanpa cadangan lintas agent)."""
    nama = (agent or "").strip().lower()
    if nama == "supervisor":
        return ENV_MODEL_SUPERVISOR
    if nama == "verifier":
        return ENV_MODEL_VERIFIER
    return ENV_MODEL


def model_id_dari_env(
    env: Mapping[str, str] | None = None, *, agent: str | None = None
) -> str:
    """Model id milik agent itu sendiri; kosong = lapisan penalaran tidak aktif."""
    sumber: Mapping[str, str] = os.environ if env is None else env
    return (sumber.get(kunci_model_untuk(agent)) or "").strip()


# ---------------------------------------------------------------------------
# Jalur 1-3: rantai provider backend, boto3 converse, strands
# ---------------------------------------------------------------------------


def _impor_boto3():
    """Modul boto3 atau `None` (opsional: tidak semua image punya AWS SDK)."""
    try:
        import boto3  # noqa: PLC0415 - impor lambat: dependensi opsional
    except Exception:  # noqa: BLE001 - tanpa SDK, jalur ini dilewati jujur
        return None
    return boto3


def _impor_strands():
    """Modul strands atau `None` (TIDAK terpasang di image backend)."""
    try:
        import strands  # noqa: PLC0415 - impor lambat: dependensi opsional
    except Exception:  # noqa: BLE001
        return None
    return strands


def _klien_bedrock(region: str):
    """Klien `bedrock-runtime`; retry 0 karena retry/fallback milik rantai."""
    boto3 = _impor_boto3()
    if boto3 is None:
        raise RuntimeError("boto3 tidak tersedia; jalur bedrock-converse dilewati")
    from botocore.config import Config  # noqa: PLC0415

    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(retries={"max_attempts": 0}, read_timeout=120),
    )


def panggil_bedrock_converse(
    prompt: str,
    *,
    model_id: str,
    region: str,
    client,
    system: str | None = None,
) -> str:
    """Satu panggilan `converse` ke Bedrock; kembalikan teks jawaban model.

    `client` disuntikkan (bukan dibuat di sini) supaya bisa diuji dengan klien
    palsu: tes tidak boleh memanggil AWS. Galat klien TIDAK ditangkap —
    pemanggil (`terapkan_penalaran`, supervisor, verifier) yang menandai
    `unavailable`, lengkap dengan pesan aslinya.
    """
    permintaan: dict = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": str(prompt)}]}],
        # Suhu 0.0: lapisan advisory tidak berimprovisasi di atas fakta.
        "inferenceConfig": {"maxTokens": MAKS_TOKEN, "temperature": 0.0},
    }
    if system:
        permintaan["system"] = [{"text": system}]

    respons = client.converse(**permintaan)
    try:
        bagian = respons["output"]["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f"struktur converse tidak dikenal ({region}): {type(exc).__name__}"
        ) from exc
    teks = "".join(
        blok.get("text", "") for blok in bagian if isinstance(blok, dict)
    )
    if not teks.strip():
        raise RuntimeError(f"jawaban bedrock kosong ({model_id})")
    return teks


def _id_bedrock_sah(model_id: str) -> bool:
    """True bila id ini milik Bedrock (bukan SAP AI Core/Inferhub/ARN)."""
    nilai = (model_id or "").strip()
    return bool(nilai) and not nilai.startswith(_NON_BEDROCK_PREFIX)


def _rantai_provider_supervisor() -> list[tuple[str, ModelCallable, str]] | None:
    """Rantai provider backend (`build_default_callers("supervisor")`).

    `None` bila modul ini berjalan di luar backend (image runtime AgentCore
    tidak punya paket `app`). Impor lambat: `agent/` tidak boleh bergantung
    pada `app/` saat diimpor sebagai runtime terpisah.
    """
    try:
        from app.ai_providers.ai_provider_chain import (  # noqa: PLC0415
            build_default_callers,
        )
    except Exception:  # noqa: BLE001 - di luar backend, paket `app` tidak ada
        return None
    try:
        return build_default_callers(AGENT_SUPERVISOR)
    except Exception:  # noqa: BLE001 - env rusak ≠ worker gagal
        return None


def _caller_dari_rantai(
    slots: list[tuple[str, ModelCallable, str]], system: str | None
) -> ModelCallable | None:
    """Bungkus rantai provider jadi satu callable `(prompt) -> str`.

    Slot `agentcore` DILEWATI: ARN itu runtime SUPERVISOR yang memanggil worker
    yang sama — memanggilnya dari dalam worker = rekursi, bukan penalaran.
    Slot yang gagal dilewati (jejak error terakhir dibawa ke pesan akhir),
    sama seperti rantai provider lain di repo ini.
    """
    hidup = [(label, fn) for label, fn, kind in slots if kind != "agentcore"]
    if not hidup:
        return None

    def _panggil(prompt: str) -> str:
        # System prompt ditempel ke prompt: callable rantai hanya menerima teks.
        teks_masuk = f"{system}\n\n{prompt}" if system else prompt
        galat: str | None = None
        for label, fn in hidup:
            try:
                hasil = fn(teks_masuk)
            except Exception as exc:  # noqa: BLE001 - lanjut slot berikutnya
                galat = f"{label}: {type(exc).__name__}: {exc}"
                continue
            if isinstance(hasil, str) and hasil.strip():
                return hasil
            galat = f"{label}: jawaban kosong"
        raise RuntimeError(f"semua slot rantai provider gagal — {galat or 'tanpa slot'}")

    return _panggil


def _dari_bedrock(model_id: str, region: str, system: str | None) -> ModelCallable | None:
    """Jalur boto3 `bedrock-runtime.converse`; `None` bila tidak memungkinkan."""
    if not _id_bedrock_sah(model_id):
        return None
    if _impor_boto3() is None:
        return None
    try:
        client = _klien_bedrock(region)
    except Exception:  # noqa: BLE001 - kredensial/region salah ≠ crash
        return None

    def _panggil(prompt: str) -> str:
        return panggil_bedrock_converse(
            prompt,
            model_id=model_id,
            region=region,
            client=client,
            system=system,
        )

    return _panggil


def _dari_strands(model_id: str, region: str, system: str | None) -> ModelCallable | None:
    """Jalur lama SDK Strands; `None` bila SDK tidak ada/gagal dibangun."""
    strands = _impor_strands()
    if strands is None:
        return None
    model_kwargs: dict[str, object] = {"model_id": model_id}
    region = (region or "").strip()
    if region:
        model_kwargs["region_name"] = region
    try:
        agent = strands.Agent(
            model=strands.models.BedrockModel(**model_kwargs),
            tools=[],
            system_prompt=system or SISTEM_WORKER,
        )
    except Exception:  # noqa: BLE001 - kredensial tidak ada ≠ worker gagal
        return None

    def _panggil(prompt: str) -> str:
        return str(agent(prompt))

    return _panggil


def reasoner_dan_jalur_dari_env(
    env: Mapping[str, str] | None = None,
    *,
    agent: str | None = None,
) -> tuple[str, ModelCallable | None]:
    """`(jalur, callable)` — jalur dilaporkan apa adanya untuk jejak/audit.

    Urutan: rantai provider backend → boto3 converse → strands → `none`.
    `agent` menentukan system prompt yang ditempel (supervisor/verifier);
    `None`/worker memakai perilaku lama (prompt membawa instruksinya sendiri).
    """
    sumber: Mapping[str, str] = os.environ if env is None else env
    model_id = model_id_dari_env(sumber, agent=agent)
    if not model_id:
        # Kontrak lama: tanpa env model, lapisan ini TIDAK aktif.
        return JALUR_NONE, None

    system = _system_untuk(agent)
    slots = _rantai_provider_supervisor()
    if slots:
        panggil = _caller_dari_rantai(slots, system)
        if panggil is not None:
            return JALUR_PROVIDER_CHAIN, panggil

    region = _region_dari_env(sumber)
    panggil = _dari_bedrock(model_id, region, system)
    if panggil is not None:
        return JALUR_BEDROCK, panggil

    panggil = _dari_strands(model_id, region, system)
    if panggil is not None:
        return JALUR_STRANDS, panggil

    return JALUR_NONE, None


def reasoner_dari_env(
    env: Mapping[str, str] | None = None,
    *,
    agent: str | None = None,
) -> ModelCallable | None:
    """Bangun callable model dari environment; `None` bila tidak memungkinkan."""
    return reasoner_dan_jalur_dari_env(env, agent=agent)[1]


class PromptWorker:
    """Prompt per agent: satu berkas Markdown per worker, dimuat saat dipakai."""

    @staticmethod
    def muat_prompt(nama: AgentName) -> str:
        berkas = PROMPT_DIR / f"{nama.value}.md"
        if not berkas.is_file():
            raise FileNotFoundError(f"prompt worker tidak ada: {berkas}")
        return berkas.read_text(encoding="utf-8")

    @staticmethod
    def bangun_prompt(nama: AgentName, *, facts: dict, summary: str) -> str:
        fakta = json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str)
        return (
            f"{PromptWorker.muat_prompt(nama)}\n\n"
            "## Fakta terukur (satu-satunya sumber kebenaran)\n"
            f"```json\n{fakta}\n```\n\n"
            "## Ringkasan deterministik saat ini\n"
            f"{summary}\n\n"
            "## Tugas\n"
            "Periksa fakta di atas. Balas HANYA JSON dengan bentuk:\n"
            '{"summary": "<ringkasan 1-2 kalimat, tanpa angka baru>", '
            '"rationale": "<alasan singkat>", "confidence": 0.0-1.0}\n'
            "Jangan menyalin token/kata sandi. Jangan mengusulkan approve/execute."
        )


def _desimal(mentah: str) -> Decimal | None:
    """Satu token angka → nilai desimal, atau `None` bila tidak terbaca.

    Dua gaya penulisan harus dibaca sebagai NILAI, bukan sebagai string:

    - `1.080,0` (gaya Indonesia: titik ribuan, koma desimal) → 1080.0
    - `1080.00` / `1080` / `1,080.00` → 1080

    Tanpa ini, model yang menulis fakta `1080.00` sebagai "1.080,0" dianggap
    MENGARANG angka baru (terukur 27 Okt 2026: worker `supply` ditolak padahal
    angkanya persis sama dengan fakta). Guard tetap menolak angka yang benar-benar
    berbeda nilainya.
    """
    teks = (mentah or "").strip()
    if not teks:
        return None
    if _POLA_ANGKA_RIBUAN.fullmatch(teks):
        bersih = teks.replace(".", "").replace(",", ".")
    else:
        # Gaya internasional: koma ribuan dibuang, titik desimal dipertahankan.
        if _POLA_ANGKA_RIBUAN.fullmatch(teks.replace(",", ".")):
            bersih = teks.replace(",", "")
        else:
            bersih = teks.replace(",", ".")
    try:
        return Decimal(bersih)
    except (InvalidOperation, ValueError):
        return None


def _angka(teks: str) -> set[Decimal]:
    """Himpunan NILAI angka di teks (bukan token string)."""
    hasil: set[Decimal] = set()
    for mentah in _POLA_ANGKA.findall(teks or ""):
        nilai = _desimal(mentah)
        if nilai is not None:
            hasil.add(nilai)
    return hasil


def _angka_fakta(facts: dict, ringkasan: str) -> set[Decimal]:
    mentah = json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str)
    return _angka(mentah) | _angka(ringkasan)


#: Presisi pembulatan yang masih dianggap "angka yang sama" dengan fakta.
#: Model bahasa membulatkan: fakta `-5.708053…` wajar ditulis "5,7%". Tanpa
#: toleransi ini satu-satunya agent yang fakta-nya berdesimal panjang (`price`)
#: selalu ditolak `model_angka_baru` dan tampak deterministik, padahal modelnya
#: dipanggil dan menjawab benar (terukur 29 Okt 2026).
_PRESISI_PEMBULATAN: tuple[Decimal, ...] = (Decimal("1"), Decimal("0.1"), Decimal("0.01"))


def _dikenal(nilai: Decimal, dikenal: set[Decimal]) -> bool:
    """`True` bila `nilai` sama dengan fakta, termasuk versi bulatnya (≤2 desimal)."""
    if nilai in dikenal:
        return True
    for presisi in _PRESISI_PEMBULATAN:
        for fakta in dikenal:
            try:
                if nilai == fakta.quantize(presisi, rounding=ROUND_HALF_UP):
                    return True
            except InvalidOperation:  # angka terlalu besar untuk presisi ini
                continue
    return False


def _hasil_reasoning(
    finding: AgentFinding,
    *,
    status: str,
    role: str,
    latency_ms: int | None = None,
    rationale: str | None = None,
    provider: str | None = None,
    warnings: list[str] | None = None,
    summary: str | None = None,
    confidence: float | None = None,
    deterministic_latency_ms: int | None = None,
) -> AgentFinding:
    facts = dict(finding.facts)
    facts["reasoning"] = {
        "status": status,
        "role": role,
        "provider": provider,
        "rationale": rationale,
        # Latensi model adalah METADATA, bukan fakta yang bisa disitasi. Kontrak
        # `AgentFinding` menolak angka telanjang di `facts` tanpa sitasi, jadi
        # nilainya disimpan sebagai teks bersatuan ("5645 ms").
        "latency": None if latency_ms is None else f"{latency_ms} ms",
        # Waktu pemeriksa deterministik, dipisah dari waktu model supaya jejak
        # bisa menjawab "berapa yang dihitung kode, berapa yang ditunggu model".
        "deterministic_latency": (
            None
            if deterministic_latency_ms is None
            else f"{deterministic_latency_ms} ms"
        ),
    }
    gabungan = list(finding.warnings) + list(warnings or [])
    perubahan: dict[str, object] = {"facts": facts, "warnings": gabungan}
    if summary is not None:
        perubahan["summary"] = summary
    if confidence is not None:
        perubahan["confidence"] = confidence
    # `status`, `blocking`, `citations`, dan `latency_ms` deterministik TIDAK
    # pernah masuk `perubahan` — itu inti jaminan modul ini.
    return finding.model_copy(update=perubahan)


def terapkan_penalaran(
    finding: AgentFinding,
    *,
    prompt: str,
    mode: str,
    model: ModelCallable | None,
    role: str,
    provider: str | None = None,
    deterministic_latency_ms: int | None = None,
) -> AgentFinding:
    """Terapkan penalaran model pada satu temuan; gagal apa pun tetap aman.

    `provider` adalah nama jalur model NYATA (`provider_chain`, `bedrock_converse`,
    `strands`, `injected`) — dicatat di `facts.reasoning.provider` supaya jejak
    audit bisa menyebut siapa yang menjawab, bukan menebak. `deterministic_latency_ms`
    adalah waktu pemeriksa deterministik, disimpan terpisah dari waktu model.
    """
    jejak = {
        "provider": provider,
        "deterministic_latency_ms": deterministic_latency_ms,
    }
    if mode != MODE_ADVISORY:
        return _hasil_reasoning(finding, status=MODE_OFF, role=role, **jejak)
    if finding.status is WorkerStatus.ERROR:
        # Temuan ERROR berarti fakta tidak terbaca: tidak ada dasar untuk
        # menalar, dan menempelkan `facts.reasoning` pada temuan error membuat
        # kontrak "error = tanpa fakta" (dikunci tes worker lama) bocor.
        return finding
    if model is None:
        return _hasil_reasoning(
            finding,
            status="unavailable",
            role=role,
            warnings=[
                "model_tidak_tersedia: lapisan penalaran dilewati, temuan "
                "deterministik dipakai"
            ],
            **jejak,
        )

    started = monotonic()
    try:
        mentah = model(prompt)
    except Exception as exc:  # noqa: BLE001 - provider mati bukan alasan menggagalkan putaran
        return _hasil_reasoning(
            finding,
            status="unavailable",
            role=role,
            latency_ms=max(1, round((monotonic() - started) * 1000)),
            warnings=[f"model_gagal: {type(exc).__name__}: {exc}"],
            **jejak,
        )

    latency = max(1, round((monotonic() - started) * 1000))
    try:
        data = json.loads(_ambil_json(mentah))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _hasil_reasoning(
            finding,
            status="invalid",
            role=role,
            latency_ms=latency,
            warnings=["model_json_rusak: jawaban model tidak dipakai"],
            **jejak,
        )

    if not isinstance(data, dict):
        return _hasil_reasoning(
            finding,
            status="invalid",
            role=role,
            latency_ms=latency,
            warnings=["model_json_rusak: bentuk jawaban bukan objek"],
            **jejak,
        )

    # Guard 1 — jangan pernah melonggarkan blokir atau menaikkan status.
    usul_blocking = data.get("blocking")
    usul_status = data.get("status")
    melonggarkan = (
        (usul_blocking is False and finding.blocking)
        or (
            isinstance(usul_status, str)
            and usul_status.strip().lower() != finding.status.value
        )
    )
    if melonggarkan:
        return _hasil_reasoning(
            finding,
            status="guarded",
            role=role,
            latency_ms=latency,
            warnings=[
                "reasoning_guard: model mencoba mengubah status/blokir — usulan "
                "ditolak, keputusan tetap milik pemeriksa deterministik"
            ],
            **jejak,
        )

    ringkasan = data.get("summary")
    ringkasan = ringkasan.strip() if isinstance(ringkasan, str) else ""
    if ringkasan:
        # Guard 2 — anti-karang angka. Angka dianggap "baru" hanya bila tidak
        # sama dengan fakta MANA PUN, termasuk versi bulatnya (≤2 desimal):
        # menulis "5,7%" untuk fakta -5.708053… bukan mengarang.
        fakta_angka = _angka_fakta(finding.facts, finding.summary)
        baru = {nilai for nilai in _angka(ringkasan) if not _dikenal(nilai, fakta_angka)}
        if baru:
            return _hasil_reasoning(
                finding,
                status="rejected",
                role=role,
                latency_ms=latency,
                warnings=[
                    f"model_angka_baru: ringkasan memuat angka di luar fakta "
                    f"({', '.join(str(v) for v in sorted(baru))}) — ditolak"
                ],
                **jejak,
            )

    rationale = data.get("rationale")
    rationale = rationale.strip()[:400] if isinstance(rationale, str) else None
    percaya = data.get("confidence")
    confidence = None
    if isinstance(percaya, (int, float)) and not isinstance(percaya, bool):
        confidence = min(1.0, max(0.0, float(percaya)))

    return _hasil_reasoning(
        finding,
        status="applied",
        role=role,
        latency_ms=latency,
        rationale=rationale,
        summary=ringkasan or None,
        confidence=confidence,
        **jejak,
    )


def _ambil_json(teks: str) -> str:
    """Ambil objek JSON pertama dari jawaban model (boleh dibungkus ```)."""
    if not isinstance(teks, str):
        raise TypeError("jawaban model bukan teks")
    bersih = teks.strip()
    if "```" in bersih:
        bagian = bersih.split("```")
        for blok in bagian:
            isi = blok.strip()
            if isi.startswith("{"):
                return isi
            if isi.startswith("json"):
                calon = isi[4:].strip()
                if calon.startswith("{"):
                    return calon
    awal, akhir = bersih.find("{"), bersih.rfind("}")
    if awal == -1 or akhir == -1 or akhir <= awal:
        return bersih
    return bersih[awal : akhir + 1]


__all__ = [
    "AGENT_PENALARAN",
    "AGENT_SUPERVISOR",
    "AGENT_VERIFIER",
    "AGENT_WORKER",
    "JALUR_BEDROCK",
    "JALUR_NONE",
    "JALUR_PROVIDER_CHAIN",
    "JALUR_STRANDS",
    "MODE_ADVISORY",
    "MODE_OFF",
    "PromptWorker",
    "WorkerStatus",
    "mode_dari_env",
    "model_id_dari_env",
    "panggil_bedrock_converse",
    "prompt_sistem",
    "reasoner_dan_jalur_dari_env",
    "reasoner_dari_env",
    "terapkan_penalaran",
]
