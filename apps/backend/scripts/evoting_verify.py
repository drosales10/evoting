"""Offline verification of a signed tally artifact (no database required)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

# Allow running from apps/backend
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tally_artifact import artifact_sha256, verify_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True, help="JSON file with artifact or wrapper")
    parser.add_argument("--signature", default=None, help="Override signature if not in file")
    parser.add_argument("--public-key", type=Path, required=True)
    args = parser.parse_args()

    raw = json.loads(args.artifact.read_text(encoding="utf-8"))
    if "artifact" in raw and isinstance(raw["artifact"], dict):
        artifact = raw["artifact"]
        signature = args.signature or raw.get("signature")
    else:
        artifact = raw
        signature = args.signature
    if not signature:
        print("Missing signature")
        return 2

    public_key = load_pem_public_key(args.public_key.read_bytes())
    if not isinstance(public_key, RSAPublicKey):
        print("Public key must be RSA")
        return 2

    sha = artifact_sha256(artifact)
    ok = verify_artifact(artifact, signature, public_key)
    print(
        json.dumps(
            {
                "artifact_sha256": sha,
                "signature_valid": ok,
                "ballot_count": artifact.get("ballot_count"),
                "quorum_met": artifact.get("quorum_met"),
                "counts": artifact.get("counts"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
