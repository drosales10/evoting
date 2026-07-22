"""Generate an official acta document from a signed tally wrapper JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tally_acta import build_official_acta  # noqa: E402
from app.services.tally_artifact import artifact_sha256  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.artifact.read_text(encoding="utf-8"))
    artifact = raw.get("artifact", raw)
    signature = raw.get("signature")
    if not signature:
        print("Missing signature in input")
        return 2
    sha = artifact_sha256(artifact)
    acta = build_official_acta(
        artifact=artifact,
        signature=signature,
        artifact_sha256_hex=sha,
        dual_approval=raw.get("dual_approval"),
    )
    args.out.write_text(json.dumps(acta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"acta_sha256": acta["acta_sha256"], "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
