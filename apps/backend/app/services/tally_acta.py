"""Official tally acta generation from a signed artifact."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any


def build_official_acta(
    *,
    artifact: Mapping[str, Any],
    signature: str,
    artifact_sha256_hex: str,
    dual_approval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    acta = {
        "acta_version": "official-acta-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "artifact_sha256": artifact_sha256_hex,
        "signature": signature,
        "election_id": artifact.get("election_id"),
        "eligible_member_count": artifact.get("eligible_member_count"),
        "voted_member_count": artifact.get("voted_member_count"),
        "ballot_count": artifact.get("ballot_count"),
        "quorum_required": artifact.get("quorum_required"),
        "quorum_met": artifact.get("quorum_met"),
        "counts": artifact.get("counts"),
        "dual_approval": dual_approval or {},
    }
    canonical = json.dumps(acta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    acta["acta_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return acta
