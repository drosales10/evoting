export type ElectionStatus =
  | "REGISTRATION"
  | "FREEZE"
  | "ACTIVE"
  | "CLOSED"
  | "TALLIED";

export type PublicElection = {
  id: string;
  title: string;
  voting_type: string;
  start_time: string;
  end_time: string;
  status: ElectionStatus;
};

export type PublicTallyCount = {
  slate_id: string;
  slate_name: string;
  votes: number;
};

export type PublicTallyArtifact = {
  artifact_version: "pilot-tally-v1";
  election_id: string;
  public_key_sha256: string;
  generated_at: string;
  eligible_member_count: number;
  voted_member_count: number;
  quorum_threshold_pct: string;
  quorum_required: number;
  quorum_met: boolean;
  ballot_count: number;
  receipt_hashes: string[];
  counts: PublicTallyCount[];
};

export type PublicTallyVerification = {
  artifact_sha256_matches: boolean;
  signature_valid: boolean;
};

export type PublicElectionResult = {
  election_id: string;
  title: string;
  voting_type: string;
  ballot_count: number;
  published_at: string;
  artifact_sha256: string;
  public_key_sha256: string;
  artifact: PublicTallyArtifact;
  signature: string;
  public_key: string;
  verification: PublicTallyVerification;
  counts: PublicTallyCount[];
};
