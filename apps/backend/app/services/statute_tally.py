"""Offline statute tally artifact. Names travel with each response after decryption."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class StatuteArticleView:
    article_id: str
    number: int
    content: str
    title_number: int
    title_description: str
    chapter_number: int
    chapter_description: str


@dataclass(frozen=True, slots=True)
class DecodedStatuteBallot:
    member_id: str
    full_name: str
    registry_code: str | None
    receipt_hash: str
    decisions: list[dict[str, Any]]


def required_quorum_votes(eligible_member_count: int, threshold_pct: Decimal) -> int:
    if eligible_member_count <= 0 or threshold_pct <= 0:
        return 0
    required = (Decimal(eligible_member_count) * threshold_pct / Decimal("100")).to_integral_value(
        rounding=ROUND_CEILING
    )
    return int(required)


def article_meets_threshold(
    approved_count: int,
    rejected_count: int,
    approval_threshold_pct: Decimal,
) -> bool:
    total = approved_count + rejected_count
    if total <= 0:
        return False
    ratio = Decimal(approved_count) * Decimal(100) / Decimal(total)
    return ratio >= approval_threshold_pct


def build_statute_tally_artifact(
    *,
    consultation_id: str,
    public_key_sha256: str,
    generated_at: datetime | None = None,
    eligible_member_count: int,
    voted_member_count: int,
    quorum_threshold_pct: Decimal,
    approval_threshold_pct: Decimal,
    quorum_required: int,
    articles: Sequence[StatuteArticleView],
    ballots: Sequence[DecodedStatuteBallot],
) -> dict[str, Any]:
    by_article: dict[str, list[dict[str, Any]]] = {
        article.article_id.lower(): [] for article in articles
    }
    for ballot in ballots:
        for decision in ballot.decisions:
            article_id = str(decision["article_id"]).lower()
            if article_id not in by_article:
                raise ValueError(f"La boleta cita un artículo desconocido: {article_id}")
            by_article[article_id].append(
                {
                    "member_id": ballot.member_id,
                    "full_name": ballot.full_name,
                    "registry_code": ballot.registry_code,
                    "approved": bool(decision["approved"]),
                    "comment": decision.get("comment"),
                }
            )

    article_rows: list[dict[str, Any]] = []
    ordered = sorted(
        articles,
        key=lambda article: (article.title_number, article.chapter_number, article.number),
    )
    for article in ordered:
        responses = sorted(
            by_article[article.article_id.lower()],
            key=lambda row: (row["full_name"].casefold(), row["member_id"]),
        )
        approved_count = sum(1 for row in responses if row["approved"])
        rejected_count = sum(1 for row in responses if not row["approved"])
        article_rows.append(
            {
                "article_id": article.article_id.lower(),
                "number": article.number,
                "content": article.content,
                "title_number": article.title_number,
                "title_description": article.title_description,
                "chapter_number": article.chapter_number,
                "chapter_description": article.chapter_description,
                "approved_count": approved_count,
                "rejected_count": rejected_count,
                "meets_threshold": article_meets_threshold(
                    approved_count, rejected_count, approval_threshold_pct
                ),
                "responses": responses,
            }
        )

    stamp = generated_at or datetime.now(UTC)
    return {
        "artifact_version": "statute-tally-v1",
        "consultation_id": consultation_id,
        "public_key_sha256": public_key_sha256,
        "generated_at": stamp.isoformat(),
        "eligible_member_count": eligible_member_count,
        "voted_member_count": voted_member_count,
        "quorum_threshold_pct": str(quorum_threshold_pct),
        "approval_threshold_pct": str(approval_threshold_pct),
        "quorum_required": quorum_required,
        "quorum_met": voted_member_count >= quorum_required,
        "ballot_count": len(ballots),
        "receipt_hashes": sorted(ballot.receipt_hash.lower() for ballot in ballots),
        "articles": article_rows,
    }


def build_statute_acta(
    *,
    artifact: Mapping[str, Any],
    signature: str,
    artifact_sha256_hex: str,
    dual_approval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    acta = {
        "acta_version": "statute-acta-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "artifact_sha256": artifact_sha256_hex,
        "signature": signature,
        "consultation_id": artifact.get("consultation_id"),
        "eligible_member_count": artifact.get("eligible_member_count"),
        "voted_member_count": artifact.get("voted_member_count"),
        "ballot_count": artifact.get("ballot_count"),
        "quorum_required": artifact.get("quorum_required"),
        "quorum_met": artifact.get("quorum_met"),
        "approval_threshold_pct": artifact.get("approval_threshold_pct"),
        "articles": [
            {
                "article_id": article.get("article_id"),
                "number": article.get("number"),
                "approved_count": article.get("approved_count"),
                "rejected_count": article.get("rejected_count"),
                "meets_threshold": article.get("meets_threshold"),
                "responses": article.get("responses"),
            }
            for article in artifact.get("articles") or []
            if isinstance(article, dict)
        ],
        "dual_approval": dict(dual_approval or {}),
    }
    canonical = json.dumps(acta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    acta["acta_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return acta
