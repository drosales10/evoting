import Link from "next/link";

import { VoterBallot } from "@/components/voter/voter-ballot";

export default function VotePage() {
  return (
    <div className="page-shell max-w-4xl">
      <VoterBallot />
      <div className="mt-4 flex justify-center">
        <Link className="button button-secondary inline-button" href="/vote/login">
          Cambiar de elector
        </Link>
      </div>
    </div>
  );
}
