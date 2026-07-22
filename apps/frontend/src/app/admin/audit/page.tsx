"use client";

import { DashboardShell } from "@/components/admin/DashboardShell";

export default function AdminAuditPage() {
  return (
    <DashboardShell>
      <div className="space-y-3">
        <h2 className="text-xl font-semibold">Auditoría</h2>
        <p className="text-sm text-[var(--muted)]">
          Consulta y exporta eventos por elección desde el módulo de Elecciones (panel de auditoría
          por UUID) o vía{" "}
          <code className="rounded bg-[var(--accent)] px-1">
            GET /api/v1/admin/elections/&#123;id&#125;/audit/export
          </code>
          .
        </p>
      </div>
    </DashboardShell>
  );
}
