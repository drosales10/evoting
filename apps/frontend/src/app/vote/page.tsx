import Link from "next/link";

import { VoterBallot } from "@/components/voter/voter-ballot";

export default function VotePage() {
  return (
    <div className="page-shell narrow-shell">
      <span className="eyebrow">Realm VOTER</span>
      <h1>Espacio del elector</h1>
      <p className="lead">La identidad del elector y la boleta cifrada permanecen en superficies separadas.</p>
      <VoterBallot />
      <Link className="button button-secondary inline-button" href="/vote/login">
        Cambiar de elector
      </Link>
    </div>
  );
}
