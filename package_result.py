import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

INFO = b"chatgpt-doorbell-artifact-v1"


def derive_key(ephemeral_private, recipient_public):
    shared = ephemeral_private.exchange(recipient_public)
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO).derive(shared)


def seal_bytes(plaintext: bytes, recipient_public_b64: str, request_id: str):
    recipient_raw = base64.b64decode(recipient_public_b64, validate=True)
    if len(recipient_raw) != 32:
        raise ValueError("reply_public_key_b64 must decode to 32 bytes")
    recipient_public = X25519PublicKey.from_public_bytes(recipient_raw)
    ephemeral_private = X25519PrivateKey.generate()
    ephemeral_public_raw = ephemeral_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    key = derive_key(ephemeral_private, recipient_public)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, request_id.encode("utf-8"))
    return {
        "version": 1,
        "algorithm": "X25519-HKDF-SHA256-AES256-GCM",
        "request_id": request_id,
        "ephemeral_public_key_b64": base64.b64encode(ephemeral_public_raw).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
        "plaintext_bytes": len(plaintext),
    }


def sanitize_result(result):
    cleaned = json.loads(json.dumps(result))
    capture = cleaned.get("capture")
    if isinstance(capture, dict):
        capture.pop("image_path", None)
    return cleaned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--image")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    request_id = request["request_id"]
    if result.get("request_id") != request_id:
        raise SystemExit("request/result correlation failed")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_result = sanitize_result(result)
    safe_result["transport"] = {
        "encrypted_image": bool(args.image and Path(args.image).exists()),
        "request_id": request_id,
    }
    (out_dir / f"{request_id}.result.json").write_text(
        json.dumps(safe_result, indent=2), encoding="utf-8"
    )

    if args.image:
        image_path = Path(args.image)
        if image_path.exists():
            plaintext = image_path.read_bytes()
            envelope = seal_bytes(plaintext, request["reply_public_key_b64"], request_id)
            envelope["mime_type"] = "image/png"
            (out_dir / f"{request_id}.image.json").write_text(
                json.dumps(envelope), encoding="utf-8"
            )


if __name__ == "__main__":
    main()
