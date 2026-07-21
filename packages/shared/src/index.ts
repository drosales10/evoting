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
