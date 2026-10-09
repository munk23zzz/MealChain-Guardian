"""P3 ECDSA secp256k1 signing (paket 1-6, keputusan Roy 2026-10-09).

Kunci privat hex di env SIGNING_KEY_HEX (secrets hanya di .env — Rules.md).
TANPA kunci → hasil `unsigned` jujur; TIDAK ada tanda tangan palsu.
"""

import hashlib
import os

import ecdsa


def _load_key() -> ecdsa.SigningKey | None:
    raw = os.environ.get("SIGNING_KEY_HEX", "").strip()
    if not raw:
        return None
    try:
        return ecdsa.SigningKey.from_string(
            bytes.fromhex(raw), curve=ecdsa.SECP256k1
        )
    except ValueError:
        return None


def public_key_hex() -> str | None:
    key = _load_key()
    if key is None:
        return None
    return key.get_verifying_key().to_string().hex()


def sign_payload(payload_bytes: bytes) -> dict:
    """Tanda tangan ECDSA atas sha256(payload). Tanpa kunci → unsigned."""
    key = _load_key()
    digest = hashlib.sha256(payload_bytes).digest()
    if key is None:
        return {"state": "unsigned", "reason": "SIGNING_KEY_HEX tidak diset (.env)"}
    sig = key.sign_digest_deterministic(digest, hashfunc=hashlib.sha256)
    return {
        "state": "signed",
        "algorithm": "ECDSA-secp256k1-sha256 (deterministic RFC6979)",
        "signature": sig.hex(),
        "public_key": key.get_verifying_key().to_string().hex(),
    }


def verify_signature(payload_bytes: bytes, signature_hex: str, public_key_hex: str) -> bool:
    """Verifikasi mandiri — dipakai endpoint untuk menunjukkan ke juri."""
    try:
        vk = ecdsa.VerifyingKey.from_string(
            bytes.fromhex(public_key_hex), curve=ecdsa.SECP256k1
        )
        digest = hashlib.sha256(payload_bytes).digest()
        return vk.verify_digest(bytes.fromhex(signature_hex), digest)
    except Exception:
        return False
