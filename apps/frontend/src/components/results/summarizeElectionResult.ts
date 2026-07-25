import type { PublicElectionResult, PublicTallyCount } from "@evoting/shared";

export type SlateStanding = PublicTallyCount & {
  vote_pct: number;
  rank: number;
  is_winner: boolean;
  is_tie: boolean;
};

export type ResultsSummary = {
  eligible: number;
  voted: number;
  ballots: number;
  participation_pct: number;
  quorum_required: number;
  quorum_met: boolean;
  quorum_threshold_pct: string;
  standings: SlateStanding[];
  winner: SlateStanding | null;
  is_tie: boolean;
};

export function summarizeElectionResult(result: PublicElectionResult): ResultsSummary {
  const eligible = result.artifact.eligible_member_count;
  const voted = result.artifact.voted_member_count;
  const ballots = result.ballot_count || result.artifact.ballot_count;
  const totalVotes = result.counts.reduce((sum, row) => sum + row.votes, 0);
  const denominator = ballots > 0 ? ballots : totalVotes;

  const sorted = [...result.counts].sort((a, b) => b.votes - a.votes || a.slate_name.localeCompare(b.slate_name, "es"));
  const topVotes = sorted[0]?.votes ?? 0;
  const tiedAtTop = sorted.filter((row) => row.votes === topVotes && topVotes > 0);
  const is_tie = tiedAtTop.length > 1;

  const standings: SlateStanding[] = sorted.map((row, index) => ({
    ...row,
    vote_pct: denominator > 0 ? Math.round((row.votes / denominator) * 10000) / 100 : 0,
    rank: index + 1,
    is_winner: !is_tie && row.votes === topVotes && topVotes > 0,
    is_tie: is_tie && row.votes === topVotes && topVotes > 0,
  }));

  return {
    eligible,
    voted,
    ballots,
    participation_pct: eligible > 0 ? Math.round((voted / eligible) * 10000) / 100 : 0,
    quorum_required: result.artifact.quorum_required,
    quorum_met: result.artifact.quorum_met,
    quorum_threshold_pct: String(result.artifact.quorum_threshold_pct),
    standings,
    winner: standings.find((row) => row.is_winner) ?? null,
    is_tie,
  };
}
