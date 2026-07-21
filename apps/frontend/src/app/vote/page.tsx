export default function VotePage() {
  return (
    <div className="page-shell narrow-shell">
      <span className="eyebrow">Realm VOTER</span>
      <h1>Espacio del elector</h1>
      <p className="lead">La autenticación de elector y MFA estarán aisladas de la comisión electoral.</p>
      <div className="notice">
        <strong>Próximo paso</strong>
        <p>Configurar request-otp, verify-otp y el token de emisión de un solo uso.</p>
      </div>
    </div>
  );
}
