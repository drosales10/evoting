"use client";

import { useEffect, useState } from "react";

import { clientApiBase as apiUrl } from "@/lib/api-origin";
import {
  CeremonyPlayer,
  type CeremonyBroadcast,
} from "@/components/ceremony/CeremonyPlayer";


export function CeremonyPublicSection({ electionId }: { electionId: string }) {
  const [broadcast, setBroadcast] = useState<CeremonyBroadcast | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetch(`${apiUrl()}/api/v1/public/elections/${electionId}/broadcast`, {
      cache: "no-store",
    })
      .then(async (response) => {
        if (cancelled || !response.ok) return;
        setBroadcast((await response.json()) as CeremonyBroadcast);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [electionId]);

  if (!broadcast) return null;

  return (
    <section className="card-panel">
      <CeremonyPlayer broadcast={broadcast} />
    </section>
  );
}
