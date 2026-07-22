"""Generate separate RSA keypairs for ballot encryption and tally signing."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _write_keypair(out_dir: Path, prefix: str) -> dict[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path = out_dir / f"{prefix}-private.pem"
    public_path = out_dir / f"{prefix}-public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    return {
        "private_path": str(private_path),
        "public_path": str(public_path),
        "public_sha256": hashlib.sha256(public_pem).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--election-label", default="election")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    encryption = _write_keypair(args.out_dir, "encryption")
    signing = _write_keypair(args.out_dir, "signing")
    manifest = {
        "election_label": args.election_label,
        "generated_at": datetime.now(UTC).isoformat(),
        "encryption": encryption,
        "signing": signing,
        "note": "Keep private PEMs offline; never upload private keys to the API.",
    }
    manifest_path = args.out_dir / "ceremony-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
