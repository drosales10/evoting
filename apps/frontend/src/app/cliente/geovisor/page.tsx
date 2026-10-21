import { ClienteGeovisorClient } from "./ClienteGeovisorClient";

export default function ClienteGeovisorPage() {
  // Lectura en Server Component: garantiza que el token del .env llegue al mapa.
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN?.trim() ?? "";

  return <ClienteGeovisorClient mapboxToken={mapboxToken} />;
}
