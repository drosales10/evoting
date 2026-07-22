import type { PublicElection, PublicElectionResult } from "@evoting/shared";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getPublicElections(): Promise<PublicElection[]> {
  try {
    const response = await fetch(`${apiUrl}/api/v1/public/elections`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return [];
    }

    return (await response.json()) as PublicElection[];
  } catch {
    // The UI remains usable while the backend or existing DB is not configured.
    return [];
  }
}

export async function getPublicElectionResult(
  electionId: string,
): Promise<PublicElectionResult | null> {
  try {
    const response = await fetch(`${apiUrl}/api/v1/public/elections/${electionId}/results`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as PublicElectionResult;
  } catch {
    return null;
  }
}
