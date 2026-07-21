import { getPublicElections } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ElectionsPage() {
  const elections = await getPublicElections();

  return (
    <div className="page-shell narrow-shell">
      <span className="eyebrow">Portal público</span>
      <h1>Elecciones</h1>
      <p className="lead">Solo se muestran convocatorias y estados aprobados para publicación.</p>
      {elections.length === 0 ? (
        <div className="empty-state">
          <h2>No hay elecciones publicadas</h2>
          <p>
            La API aún no está conectada o no existen elecciones en un estado publicable. Esta vista
            no modifica la base de datos.
          </p>
        </div>
      ) : (
        <div className="election-list">
          {elections.map((election) => (
            <article className="election-item" key={election.id}>
              <div>
                <span className="eyebrow">{election.status}</span>
                <h2>{election.title}</h2>
                <p>{election.voting_type}</p>
              </div>
              <time dateTime={election.start_time}>
                Inicio: {new Date(election.start_time).toLocaleString("es-ES")}
              </time>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
