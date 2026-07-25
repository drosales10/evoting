"""Unit tests for election result dashboard summary helpers (mirrored in frontend)."""

from __future__ import annotations


def summarize_election_result(
    *,
    eligible: int,
    voted: int,
    ballots: int,
    counts: list[tuple[str, str, int]],
) -> dict:
    total_votes = sum(votes for _, _, votes in counts)
    denominator = ballots if ballots > 0 else total_votes
    sorted_counts = sorted(counts, key=lambda row: (-row[2], row[1].casefold()))
    top = sorted_counts[0][2] if sorted_counts else 0
    tied = [row for row in sorted_counts if row[2] == top and top > 0]
    is_tie = len(tied) > 1
    standings = []
    for index, (slate_id, name, votes) in enumerate(sorted_counts):
        standings.append(
            {
                "slate_id": slate_id,
                "slate_name": name,
                "votes": votes,
                "vote_pct": round((votes / denominator) * 100, 2) if denominator else 0,
                "rank": index + 1,
                "is_winner": not is_tie and votes == top and top > 0,
                "is_tie": is_tie and votes == top and top > 0,
            }
        )
    return {
        "participation_pct": round((voted / eligible) * 100, 2) if eligible else 0,
        "is_tie": is_tie,
        "winner": next((row for row in standings if row["is_winner"]), None),
        "standings": standings,
    }


def test_winner_and_participation() -> None:
    summary = summarize_election_result(
        eligible=200,
        voted=100,
        ballots=100,
        counts=[
            ("a", "Plancha A", 55),
            ("b", "Plancha B", 45),
        ],
    )
    assert summary["participation_pct"] == 50
    assert summary["winner"]["slate_name"] == "Plancha A"
    assert summary["winner"]["vote_pct"] == 55
    assert summary["is_tie"] is False


def test_tie_has_no_single_winner() -> None:
    summary = summarize_election_result(
        eligible=200,
        voted=80,
        ballots=80,
        counts=[
            ("a", "Plancha A", 40),
            ("b", "Plancha B", 40),
        ],
    )
    assert summary["is_tie"] is True
    assert summary["winner"] is None
    assert sum(1 for row in summary["standings"] if row["is_tie"]) == 2
