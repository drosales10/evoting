"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import { adminFetch } from "@/lib/admin-api";
import { formatApiError } from "@/lib/api-error";
import { datetimeLocalToUtcIso, formatAppDateTime } from "@/lib/datetime";
import { notify } from "@/lib/notify";

type AdminOverview = {
  organization_slug: string;
  organization_name: string;
  roles: string[];
  member_count: number;
  active_member_count: number;
  inactive_member_count: number;
  member_type_counts: Array<{ member_type: string; count: number }>;
  eligible_voter_count: number;
  ineligible_voter_count: number;
  election_count: number;
  encrypted_ballot_count: number;
};

type AdminMember = {
  id: string;
  registry_code: string | null;
  email: string;
  full_name: string;
  dni: string;
  status: string;
  member_type: string | null;
  membership_months: number;
  decade: number | null;
  graduation_year: number | null;
  semester: string | null;
  sex: string | null;
  alive: boolean | null;
  section: string | null;
  location: string | null;
  region: string | null;
  mention: string | null;
  graduation_date: string | null;
  photo_filename: string | null;
  photo_content_type: string | null;
  photo_size_bytes: number | null;
  created_at: string;
};

type AdminMemberImportResult = {
  rows_read: number;
  created: number;
  updated: number;
  failed: number;
  dry_run: boolean;
  errors: Array<{ row_number: number; registry_code: string | null; message: string }>;
};

type AdminElection = {
  id: string;
  title: string;
  voting_type: string;
  start_time: string;
  end_time: string;
  quorum_threshold_pct: string;
  status: string;
  scope_level?: string;
  region_id?: string | null;
  state_id?: string | null;
  activated_at: string | null;
  created_at: string;
};

type AdminElectionActivationResponse = {
  election_id: string;
  election_status: string;
  activated_at: string;
  snapshot_member_count: number;
  eligible_member_count: number;
  position_count: number;
  slate_count: number;
  candidate_count: number;
  public_key_sha256: string;
};

type AdminElectionCloseResponse = {
  election_id: string;
  election_status: string;
  closed_at: string;
  eligible_member_count: number;
  voted_member_count: number;
  ballot_count: number;
  quorum_threshold_pct: string;
  quorum_required: number;
  quorum_met: boolean;
  pilot_override: boolean;
};

type AdminTallyPublishResponse = {
  tally_id?: string | null;
  proposal_id?: string | null;
  election_id: string;
  election_status: string;
  artifact_sha256: string;
  ballot_count: number;
  quorum_met: boolean;
  pilot_override: boolean;
  published_at?: string | null;
  approval_stage?: string;
  acta_sha256?: string | null;
};

type AdminElectionAudit = {
  id: string;
  event_type: "ELECTION_ACTIVATED" | "ELECTION_CLOSED" | "ELECTION_TALLIED";
  actor_id_hash: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

type AdminElectionEligibility = {
  election_id: string;
  election_status: string;
  snapshot_member_count: number;
  eligible_member_count: number;
  ineligible_member_count: number;
};

type AdminElectionEligibilityMember = {
  member_id: string;
  registry_code: string | null;
  full_name: string;
  dni: string;
  email: string;
  status: string;
  member_type?: string | null;
  alive: boolean | null;
  eligible: boolean;
  reason: string;
};

type EligibilityFilter = "all" | "eligible" | "ineligible";

type AdminSlate = {
  id: string;
  organization_id: string;
  election_id: string;
  name: string;
  slogan: string | null;
  proxy_member_id: string | null;
  status: string;
  candidate_count: number;
  created_at: string;
};

type AdminCandidate = {
  id: string;
  slate_id: string;
  position_id: string;
  position_code: string;
  position_title: string;
  member_id: string;
  member_registry_code: string | null;
  member_full_name: string;
  member_dni: string;
  bio: string | null;
  created_at: string;
};

type AdminPosition = {
  id: string;
  election_id: string;
  title: string;
  code: string;
  is_required: boolean;
  display_order: number;
  created_at: string;
};

type ApiError = { detail?: unknown };

async function requestApiJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await adminFetch(url, init);
  } catch {
    throw new Error(
      `No se pudo contactar la API administrativa en ${url}. ` +
      "Verifica que el backend esté ejecutándose y que CORS permita el origen del frontend.",
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    if (!response.ok) {
      throw new Error(
        `La API administrativa respondió HTTP ${response.status}, pero no devolvió JSON.`,
      );
    }
    throw new Error(
      `La API administrativa respondió con un formato inesperado (HTTP ${response.status}).`,
    );
  }

  if (!response.ok) {
    const detail = formatApiError(payload, "");
    if (response.status === 401) {
      throw new Error(
        detail
          ? `La sesión administrativa no está activa: ${detail}. Vuelve a iniciar sesión en /admin/login.`
          : "La sesión administrativa expiró (HTTP 401). Vuelve a iniciar sesión en /admin/login.",
      );
    }
    throw new Error(
      `La API administrativa respondió HTTP ${response.status}: ${detail || "sin detalle"}.`,
    );
  }

  return payload as T;
}

function formatDate(value: string) {
  return formatAppDateTime(value);
}

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

export type ElectionsTab =
  | "ciclo"
  | "procesos"
  | "crear"
  | "planchas"
  | "estructura"
  | "elegibles";

export type CicloSection =
  | "metricas"
  | "portal"
  | "ciclo"
  | "preview"
  | "archivada";

type AdminOverviewProps = {
  focus?: "all" | "elections" | "members";
  electionsTab?: ElectionsTab;
  cicloSection?: CicloSection;
  focusElectionId?: string | null;
  onNavigateTab?: (tab: ElectionsTab, electionId?: string) => void;
  onSelectCicloSection?: (section: CicloSection) => void;
};

export function AdminOverview({
  focus = "all",
  electionsTab = "ciclo",
  cicloSection = "ciclo",
  focusElectionId = null,
  onNavigateTab,
  onSelectCicloSection,
}: AdminOverviewProps) {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [members, setMembers] = useState<AdminMember[]>([]);
  const [elections, setElections] = useState<AdminElection[]>([]);
  const [selectedElection, setSelectedElection] = useState<AdminElection | null>(null);
  const [positions, setPositions] = useState<AdminPosition[]>([]);
  const [eligibilityElection, setEligibilityElection] = useState<AdminElection | null>(null);
  const [eligibilityMembers, setEligibilityMembers] = useState<AdminElectionEligibilityMember[]>([]);
  const [eligibilityFilter, setEligibilityFilter] = useState<EligibilityFilter>("all");
  const [eligibilityBusy, setEligibilityBusy] = useState(false);
  const [eligibilityPage, setEligibilityPage] = useState(1);
  const [assignmentEligibleMembers, setAssignmentEligibleMembers] = useState<
    AdminElectionEligibilityMember[]
  >([]);
  const [slateElection, setSlateElection] = useState<AdminElection | null>(null);
  const [slates, setSlates] = useState<AdminSlate[]>([]);
  const [selectedSlate, setSelectedSlate] = useState<AdminSlate | null>(null);
  const [candidates, setCandidates] = useState<AdminCandidate[]>([]);
  const [slateBusy, setSlateBusy] = useState(false);
  const [candidateBusy, setCandidateBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [memberBusy, setMemberBusy] = useState(false);
  const [positionBusy, setPositionBusy] = useState(false);
  const [lifecycleBusyId, setLifecycleBusyId] = useState<string | null>(null);
  const [activationBusyId, setActivationBusyId] = useState<string | null>(null);
  const [tallyBusyId, setTallyBusyId] = useState<string | null>(null);
  const [tallyFeedback, setTallyFeedback] = useState<{
    electionId: string;
    kind: "ok" | "error";
    text: string;
  } | null>(null);
  const [auditElection, setAuditElection] = useState<AdminElection | null>(null);
  const [auditEvents, setAuditEvents] = useState<AdminElectionAudit[]>([]);
  const [auditBusy, setAuditBusy] = useState(false);
  const [photoBusyId, setPhotoBusyId] = useState<string | null>(null);
  const [copiedElectionId, setCopiedElectionId] = useState<string | null>(null);

  async function loadData() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const [overviewResponse, membersResponse, electionsResponse] = await Promise.all([
      fetch(`${apiUrl}/api/v1/admin/overview`, { credentials: "include", cache: "no-store" }),
      fetch(`${apiUrl}/api/v1/admin/members?limit=50`, { credentials: "include", cache: "no-store" }),
      fetch(`${apiUrl}/api/v1/admin/elections`, { credentials: "include", cache: "no-store" }),
    ]);
    const overviewPayload = (await overviewResponse.json()) as AdminOverview & ApiError;
    const membersPayload = (await membersResponse.json()) as
      | (AdminMember[] & ApiError)
      | ({ items: AdminMember[] } & ApiError);
    const electionsPayload = (await electionsResponse.json()) as AdminElection[] & ApiError;

    if (!overviewResponse.ok || !membersResponse.ok || !electionsResponse.ok) {
      const unauthorized = [overviewResponse, membersResponse, electionsResponse].some(
        (response) => response.status === 401,
      );
      const membersDetail =
        "detail" in membersPayload ? formatApiError(membersPayload, "") : "";
      throw new Error(
        unauthorized
          ? "Tu sesión administrativa no está activa. Accede para continuar."
          : formatApiError(overviewPayload, "") ||
              membersDetail ||
              formatApiError(electionsPayload, "") ||
              "No se pudo cargar el resumen administrativo.",
      );
    }
    setOverview(overviewPayload);
    setMembers(Array.isArray(membersPayload) ? membersPayload : membersPayload.items);
    setElections(electionsPayload);
    setLoadError(null);
  }

  useEffect(() => {
    void loadData().catch((error: unknown) => {
      const text =
        error instanceof Error ? error.message : "No se pudo cargar el resumen administrativo.";
      notify.error(text);
      setLoadError(text);
    });
  }, []);

  useEffect(() => {
    if (focus !== "elections" || !focusElectionId || elections.length === 0) return;
    const target = elections.find((item) => item.id === focusElectionId);
    if (!target) return;
    if (electionsTab === "estructura" && (target.status === "DRAFT" || target.status === "REGISTRATION")) {
      void loadPositions(target);
    }
    if (
      (electionsTab === "planchas" || electionsTab === "elegibles") &&
      (target.status === "REGISTRATION" || target.status === "FREEZE")
    ) {
      void loadSlates(target);
    }
    if (electionsTab === "elegibles" && (target.status === "REGISTRATION" || target.status === "FREEZE")) {
      void loadEligibility(target);
      void loadAssignmentEligibleMembers(target);
    }
    // Solo reaccionar a cambios de pestaña / elección enfocada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, focusElectionId, electionsTab, elections]);

  async function handleImportMembers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMemberBusy(true);
    const form = new FormData(event.currentTarget);
    const file = form.get("member_file");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    if (!(file instanceof File) || file.size === 0) {
      notify.error("Selecciona un archivo XLSX.");
      setMemberBusy(false);
      return;
    }
    form.set("dry_run", form.get("dry_run") === "on" ? "true" : "false");

    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/members/import`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      const payload = (await response.json()) as AdminMemberImportResult & ApiError;
      if (!response.ok) {
        notify.apiError(payload, "No se pudo importar el padrón.");
        return;
      }
      await loadData();
      notify.success(
        `${payload.dry_run ? "Validación" : "Importación"} terminada: ${payload.rows_read} filas, ` +
          `${payload.created} nuevas, ${payload.updated} actualizadas y ${payload.failed} con error.`,
      );
    } catch {
      notify.error("No se pudo contactar la API administrativa.");
    } finally {
      setMemberBusy(false);
    }
  }

  async function handleUploadPhoto(memberId: string, event: ChangeEvent<HTMLInputElement>) {
    const inputElement = event.currentTarget;
    const file = inputElement.files?.[0];
    if (!file) return;
    setPhotoBusyId(memberId);
    const form = new FormData();
    form.append("file", file);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/members/${memberId}/photo`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      const payload = (await response.json()) as AdminMember & ApiError;
      if (!response.ok) {
        notify.apiError(payload, "No se pudo cargar la foto.");
        return;
      }
      setMembers((current) => current.map((member) => member.id === memberId ? payload : member));
      notify.success("Foto guardada en PostgreSQL.");
    } catch {
      notify.error("No se pudo contactar la API administrativa.");
    } finally {
      setPhotoBusyId(null);
      inputElement.value = "";
    }
  }

  async function handleCreateMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMemberBusy(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/members`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(form.get("member_email") ?? "").trim(),
          full_name: String(form.get("member_full_name") ?? "").trim(),
          dni: String(form.get("member_dni") ?? "").trim(),
          membership_months: Number(form.get("membership_months") ?? 0),
        }),
      });
      const payload = (await response.json()) as AdminMember & ApiError;
      if (!response.ok) {
        notify.apiError(payload, "No se pudo crear el miembro.");
        return;
      }
      setMembers((current) => [...current, payload].sort((left, right) =>
        left.full_name.localeCompare(right.full_name, "es"),
      ));
      setOverview((current) =>
        current
          ? {
              ...current,
              member_count: current.member_count + 1,
              active_member_count: current.active_member_count + 1,
            }
          : current,
      );
      formElement.reset();
      notify.success("Miembro agregado al padrón activo.");
    } catch {
      notify.error("No se pudo contactar la API administrativa.");
    } finally {
      setMemberBusy(false);
    }
  }

  async function handleCreateElection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const startTime = String(form.get("start_time") ?? "");
    const endTime = String(form.get("end_time") ?? "");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/elections`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: String(form.get("title") ?? "").trim(),
          voting_type: "SLATE_PLURALITY",
          start_time: datetimeLocalToUtcIso(startTime),
          end_time: datetimeLocalToUtcIso(endTime),
          quorum_threshold_pct: Number(form.get("quorum_threshold_pct") ?? 30),
          scope_level: String(form.get("scope_level") ?? "NATIONAL"),
          region_id: String(form.get("region_id") ?? "").trim() || null,
          state_id: String(form.get("state_id") ?? "").trim() || null,
        }),
      });
      const payload = (await response.json()) as AdminElection & ApiError;
      if (!response.ok) {
        notify.apiError(payload, "No se pudo crear la elección.");
        return;
      }
      setElections((current) => [...current, payload].sort((left, right) =>
        new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
      ));
      setOverview((current) =>
        current ? { ...current, election_count: current.election_count + 1 } : current,
      );
      formElement.reset();
      notify.success("Elección creada en estado DRAFT.");
    } catch {
      notify.error("No se pudo contactar la API administrativa.");
    } finally {
      setBusy(false);
    }
  }

  async function handleElectionLifecycle(
    election: AdminElection,
    action: "open-registration" | "freeze",
  ) {
    setLifecycleBusyId(election.id);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const response = await fetch(
        `${apiUrl}/api/v1/admin/elections/${election.id}/${action}`,
        { method: "POST", credentials: "include" },
      );
      const payload = (await response.json()) as AdminElectionEligibility & ApiError;
      if (!response.ok) {
        notify.apiError(payload, "No se pudo cambiar el estado de la elección.");
        return;
      }
      setElections((current) => current.map((item) =>
        item.id === election.id ? { ...item, status: payload.election_status } : item,
      ));
      if (selectedElection?.id === election.id) {
        setSelectedElection({ ...selectedElection, status: payload.election_status });
      }
      if (slateElection?.id === election.id) {
        setSlateElection({ ...slateElection, status: payload.election_status });
      }
      notify.success(
        `${action === "open-registration" ? "Registro abierto" : "Padrón congelado"}. ` +
        `${payload.eligible_member_count} elegibles de ${payload.snapshot_member_count}.`,
      );
    } catch {
      notify.error("No se pudo contactar la API administrativa.");
    } finally {
      setLifecycleBusyId(null);
    }
  }

  async function handleCloseElection(election: AdminElection, forcePilot: boolean) {
    setLifecycleBusyId(election.id);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const csrfToken = window.sessionStorage.getItem("evoting_admin_csrf");
    if (!csrfToken) {
      notify.error("Sesión ADMIN sin CSRF. Inicia sesión nuevamente.");
      setLifecycleBusyId(null);
      return;
    }
    try {
      const payload = await requestApiJson<AdminElectionCloseResponse>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/close`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
          },
          body: JSON.stringify({
            force_pilot: forcePilot,
            reason: forcePilot
              ? "Cierre explícito del piloto local de desarrollo"
              : "Cierre oficial tras ventana electoral y verificación de quórum",
          }),
        },
      );
      setElections((current) => current.map((item) =>
        item.id === election.id ? { ...item, status: payload.election_status } : item,
      ));
      if (selectedElection?.id === election.id) {
        setSelectedElection({ ...selectedElection, status: payload.election_status });
      }
      notify.success(
        `${forcePilot ? "Piloto" : "Elección"} cerrada: ${payload.ballot_count} boletas y ${payload.voted_member_count} participaciones. ` +
        `Quórum: ${payload.quorum_met ? "cumplido" : `no cumplido (${payload.quorum_required} requeridos)`}. ` +
        "El escrutinio requiere la clave privada fuera de la API.",
      );
    } catch (error: unknown) {
      notify.error(error instanceof Error ? error.message : "No se pudo cerrar la elección.");
    } finally {
      setLifecycleBusyId(null);
    }
  }

  async function handleActivateElection(
    election: AdminElection,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setActivationBusyId(election.id);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const publicKey = String(form.get("election_public_key") ?? "").trim();
    const signingPublicKey = String(form.get("election_signing_public_key") ?? "").trim();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const csrfToken = window.sessionStorage.getItem("evoting_admin_csrf");
    if (!csrfToken) {
      notify.error("Sesión ADMIN sin CSRF. Inicia sesión nuevamente.");
      setActivationBusyId(null);
      return;
    }
    try {
      const payload = await requestApiJson<AdminElectionActivationResponse>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/activate`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
          },
          body: JSON.stringify({
            public_key: publicKey,
            ...(signingPublicKey ? { signing_public_key: signingPublicKey } : {}),
          }),
        },
      );
      setElections((current) => current.map((item) =>
        item.id === election.id
          ? { ...item, status: payload.election_status, activated_at: payload.activated_at }
          : item,
      ));
      if (selectedElection?.id === election.id) {
        setSelectedElection({
          ...selectedElection,
          status: payload.election_status,
          activated_at: payload.activated_at,
        });
      }
      if (slateElection?.id === election.id) {
        setSlateElection({
          ...slateElection,
          status: payload.election_status,
          activated_at: payload.activated_at,
        });
      }
      formElement.reset();
      notify.success(
        `Votación activa: ${payload.slate_count} planchas, ${payload.candidate_count} candidatos y ` +
        `${payload.eligible_member_count} electores elegibles. Huella de clave pública: ` +
        `${payload.public_key_sha256.slice(0, 16)}…`,
      );
    } catch (error: unknown) {
      notify.error(error instanceof Error ? error.message : "No se pudo activar la elección.");
    } finally {
      setActivationBusyId(null);
    }
  }

  async function handlePublishTally(
    election: AdminElection,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const formElement = event.currentTarget;
    if (!formElement) {
      setTallyFeedback({
        electionId: election.id,
        kind: "error",
        text: "No se pudo leer el formulario del tally. Recarga la página e inténtalo de nuevo.",
      });
      return;
    }
    const form = new FormData(formElement);
    const rawArtifact = String(form.get("tally_artifact") ?? "").trim();
    const pilotOverride = form.get("tally_pilot_override") === "on";
    setTallyBusyId(election.id);
    setTallyFeedback(null);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const csrfToken = window.sessionStorage.getItem("evoting_admin_csrf");
    if (!csrfToken) {
      const text = "Sesión ADMIN sin CSRF. Inicia sesión nuevamente.";
      notify.error(text);
      setTallyFeedback({ electionId: election.id, kind: "error", text });
      setTallyBusyId(null);
      return;
    }
    if (!rawArtifact) {
      const text = "Pega el JSON completo del script (debe incluir artifact y signature).";
      setTallyFeedback({ electionId: election.id, kind: "error", text });
      setTallyBusyId(null);
      return;
    }
    try {
      const readinessResponse = await fetch(
        `${apiUrl}/api/v1/admin/elections/${election.id}/tally-readiness`,
        { credentials: "include", cache: "no-store" },
      );
      if (readinessResponse.ok) {
        const readiness = (await readinessResponse.json()) as {
          key_compare_warning?: string | null;
          has_key_compare_milestone?: boolean;
        };
        if (readiness.key_compare_warning || readiness.has_key_compare_milestone === false) {
          const confirmed = window.confirm(
            `${readiness.key_compare_warning ?? "Falta el hito de comparación de claves en el live."}\n\n¿Publicar de todos modos?`,
          );
          if (!confirmed) {
            setTallyFeedback({
              electionId: election.id,
              kind: "error",
              text: "Publicación cancelada: falta confirmar la advertencia de comparación de claves.",
            });
            setTallyBusyId(null);
            return;
          }
        }
      }
      let parsed: {
        artifact?: Record<string, unknown>;
        signature?: string;
      };
      try {
        parsed = JSON.parse(rawArtifact) as {
          artifact?: Record<string, unknown>;
          signature?: string;
        };
      } catch {
        throw new Error(
          "El texto pegado no es JSON válido. Usa la salida completa de tally_encrypted_ballots.py (objeto con artifact + signature).",
        );
      }
      const artifact = parsed.artifact ?? parsed;
      const signature = parsed.signature;
      if (!signature || typeof signature !== "string") {
        throw new Error(
          "El JSON no contiene signature. Debe ser { \"artifact\": {...}, \"signature\": \"...\" }.",
        );
      }
      const payload = await requestApiJson<AdminTallyPublishResponse>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/tally`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
          },
          body: JSON.stringify({
            artifact,
            signature,
            pilot_override: pilotOverride,
            approval_stage: "publish",
            reason: pilotOverride
              ? "Publicación explícita del tally piloto firmado"
              : "Publicación del tally firmado tras verificación de quorum",
          }),
        },
      );
      setElections((current) => current.map((item) =>
        item.id === election.id ? { ...item, status: payload.election_status } : item,
      ));
      if (selectedElection?.id === election.id) {
        setSelectedElection({ ...selectedElection, status: payload.election_status });
      }
      formElement.reset();
      const okText =
        payload.approval_stage === "propose"
          ? `Tally propuesto (doble aprobación pendiente). Huella ${payload.artifact_sha256.slice(0, 16)}…`
          : `Tally verificado y publicado: ${payload.ballot_count} boletas. ` +
            `Resultado ${payload.pilot_override ? "de piloto" : "oficial"}; ` +
            `huella del artefacto ${payload.artifact_sha256.slice(0, 16)}…` +
            (payload.acta_sha256 ? ` Acta ${payload.acta_sha256.slice(0, 16)}…` : "");
      notify.success(okText);
      setTallyFeedback({ electionId: election.id, kind: "ok", text: okText });
    } catch (error: unknown) {
      const text =
        error instanceof Error ? error.message : "No se pudo publicar el tally.";
      notify.error(text);
      setTallyFeedback({ electionId: election.id, kind: "error", text });
    } finally {
      setTallyBusyId(null);
    }
  }

  async function loadAudit(election: AdminElection) {
    setAuditElection(election);
    setAuditBusy(true);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminElectionAudit[]>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/audit`,
        { credentials: "include", cache: "no-store" },
      );
      setAuditEvents(payload);
    } catch (error: unknown) {
      setAuditEvents([]);
      notify.error(error instanceof Error ? error.message : "No se pudo cargar la auditoría.");
    } finally {
      setAuditBusy(false);
    }
  }

  async function loadEligibility(
    election: AdminElection,
    filter: EligibilityFilter = eligibilityFilter,
  ) {
    setEligibilityElection(election);
    setEligibilityBusy(true);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const query = filter === "all" ? "" : `?eligible=${filter === "eligible"}`;
    try {
      const response = await fetch(
        `${apiUrl}/api/v1/admin/elections/${election.id}/eligibility/members${query}`,
        { credentials: "include", cache: "no-store" },
      );
      const payload = (await response.json()) as AdminElectionEligibilityMember[] & ApiError;
      if (!response.ok) {
        notify.apiError(payload, "No se pudo cargar el detalle de elegibilidad.");
        setEligibilityMembers([]);
        return;
      }
      setEligibilityMembers(payload);
      setEligibilityPage(1);
    } catch {
      notify.error("No se pudo contactar la API administrativa.");
      setEligibilityMembers([]);
      setEligibilityPage(1);
    } finally {
      setEligibilityBusy(false);
    }
  }

  async function loadAssignmentEligibleMembers(election: AdminElection) {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const response = await fetch(
        `${apiUrl}/api/v1/admin/elections/${election.id}/eligibility/members?eligible=true`,
        { credentials: "include", cache: "no-store" },
      );
      const payload = (await response.json()) as AdminElectionEligibilityMember[] & ApiError;
      if (!response.ok) {
        setAssignmentEligibleMembers([]);
        return;
      }
      setAssignmentEligibleMembers(payload);
    } catch {
      setAssignmentEligibleMembers([]);
    }
  }

  async function loadSlates(election: AdminElection) {
    setSlateElection(election);
    setSelectedSlate(null);
    setCandidates([]);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminSlate[]>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/slates`,
        { credentials: "include", cache: "no-store" },
      );
      setSlates(payload);
      void loadPositions(election);
    } catch (error: unknown) {
      notify.error(
        error instanceof Error ? error.message : "No se pudieron cargar las planchas.",
      );
      setSlates([]);
    }
  }

  async function loadCandidates(slate: AdminSlate) {
    setSelectedSlate(slate);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminCandidate[]>(
        `${apiUrl}/api/v1/admin/slates/${slate.id}/candidates`,
        { credentials: "include", cache: "no-store" },
      );
      setCandidates(payload);
    } catch (error: unknown) {
      notify.error(
        error instanceof Error ? error.message : "No se pudieron cargar los candidatos.",
      );
      setCandidates([]);
    }
  }

  async function handleCreateSlate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slateElection) return;
    setSlateBusy(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const proxyMemberId = String(form.get("proxy_member_id") ?? "").trim();
      const payload = await requestApiJson<AdminSlate>(
        `${apiUrl}/api/v1/admin/elections/${slateElection.id}/slates`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: String(form.get("slate_name") ?? "").trim(),
            slogan: String(form.get("slate_slogan") ?? "").trim() || null,
            proxy_member_id: proxyMemberId || null,
          }),
        },
      );
      setSlates((current) => [...current, payload]);
      formElement.reset();
      notify.success("Plancha creada en estado PENDING.");
    } catch (error: unknown) {
      notify.error(
        error instanceof Error ? error.message : "No se pudo crear la plancha.",
      );
    } finally {
      setSlateBusy(false);
    }
  }

  async function handleCreateCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSlate) return;
    setCandidateBusy(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminCandidate>(
        `${apiUrl}/api/v1/admin/slates/${selectedSlate.id}/candidates`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            position_id: String(form.get("candidate_position_id") ?? ""),
            member_id: String(form.get("candidate_member_id") ?? ""),
            bio: String(form.get("candidate_bio") ?? "").trim() || null,
          }),
        },
      );
      setCandidates((current) => [...current, payload]);
      setSlates((current) => current.map((slate) =>
        slate.id === selectedSlate.id
          ? { ...slate, candidate_count: slate.candidate_count + 1 }
          : slate,
      ));
      setSelectedSlate((current) => current ? { ...current, candidate_count: current.candidate_count + 1 } : current);
      formElement.reset();
      notify.success("Candidato registrado correctamente.");
    } catch (error: unknown) {
      notify.error(
        error instanceof Error ? error.message : "No se pudo registrar el candidato.",
      );
    } finally {
      setCandidateBusy(false);
    }
  }

  async function loadPositions(election: AdminElection) {
    setSelectedElection(election);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminPosition[]>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/positions`,
        { credentials: "include", cache: "no-store" },
      );
      setPositions(payload);
    } catch (error: unknown) {
      notify.error(
        error instanceof Error ? error.message : "No se pudieron cargar las posiciones.",
      );
    }
  }

  async function handleCreatePosition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedElection) return;
    setPositionBusy(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    try {
      const response = await fetch(
        `${apiUrl}/api/v1/admin/elections/${selectedElection.id}/positions`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: String(form.get("position_title") ?? "").trim(),
            code: String(form.get("position_code") ?? "").trim(),
            is_required: form.get("position_required") === "on",
            display_order: Number(form.get("position_order") ?? 0),
          }),
        },
      );
      const payload = (await response.json()) as AdminPosition & ApiError;
      if (!response.ok) {
        notify.apiError(payload, "No se pudo crear la posición.");
        return;
      }
      setPositions((current) => [...current, payload].sort(
        (left, right) => left.display_order - right.display_order,
      ));
      formElement.reset();
      notify.success("Posición creada correctamente.");
    } catch {
      notify.error("No se pudo contactar la API administrativa.");
    } finally {
      setPositionBusy(false);
    }
  }

  if (!overview) {
    return <div className="notice"><p>{loadError ?? "Cargando resumen administrativo…"}</p></div>;
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const isElectionsFocus = focus === "elections";
  const inCicloTab = isElectionsFocus && electionsTab === "ciclo";
  const showMetricsStrip =
    (isElectionsFocus && electionsTab !== "ciclo") ||
    (inCicloTab && cicloSection === "metricas");
  const showCiclo = !isElectionsFocus || (inCicloTab && cicloSection === "ciclo");
  const showArchivada = inCicloTab && cicloSection === "archivada";
  const showProcesos = !isElectionsFocus || electionsTab === "procesos";
  const showElectionList = showCiclo || showProcesos || showArchivada;
  const showLifecycleActions = !isElectionsFocus || (inCicloTab && cicloSection === "ciclo");
  const showPlanchas = !isElectionsFocus || electionsTab === "planchas" || electionsTab === "elegibles";
  const showEstructura = !isElectionsFocus || electionsTab === "estructura";
  const showElegiblesDetail = !isElectionsFocus || electionsTab === "elegibles";
  const showAudit =
    !isElectionsFocus || (inCicloTab && (cicloSection === "ciclo" || cicloSection === "archivada"));

  const structureElections = elections.filter(
    (e) => e.status === "DRAFT" || e.status === "REGISTRATION",
  );
  const canEditPositions =
    selectedElection?.status === "DRAFT" || selectedElection?.status === "REGISTRATION";
  const slateReadyElections = elections.filter(
    (e) => e.status === "REGISTRATION" || e.status === "FREEZE",
  );
  const ELIGIBILITY_PAGE_SIZE = 5;
  const eligibilityTotalPages = Math.max(
    1,
    Math.ceil(eligibilityMembers.length / ELIGIBILITY_PAGE_SIZE),
  );
  const eligibilityPageSafe = Math.min(eligibilityPage, eligibilityTotalPages);
  const eligibilityPageItems = eligibilityMembers.slice(
    (eligibilityPageSafe - 1) * ELIGIBILITY_PAGE_SIZE,
    eligibilityPageSafe * ELIGIBILITY_PAGE_SIZE,
  );
  const visibleElections = showArchivada
    ? elections.filter((e) => e.status === "TALLIED" || e.status === "CLOSED")
    : showCiclo && isElectionsFocus
      ? elections.filter((e) => e.status !== "TALLIED")
      : elections;

  return (
    <>
      {!isElectionsFocus ? (
        <div className="notice">
          <strong>{overview.organization_name}</strong>
          <p>Organización: {overview.organization_slug}</p>
          <p>Roles activos: {overview.roles.join(", ")}</p>
        </div>
      ) : showMetricsStrip ? (
        <div className="elections-compact-stats" aria-label="Indicadores electorales">
          <div className="surface-card">
            <span className="eyebrow">Elecciones</span>
            <h2>{overview.election_count}</h2>
          </div>
          <div className="surface-card">
            <span className="eyebrow">Urna</span>
            <h2>{overview.encrypted_ballot_count}</h2>
          </div>
          <div className="surface-card">
            <span className="eyebrow">Elegibles padrón</span>
            <h2 className="text-emerald-700 dark:text-emerald-300">{overview.eligible_voter_count}</h2>
          </div>
          {inCicloTab && cicloSection === "metricas" ? (
            <>
              <div className="surface-card">
                <span className="eyebrow">En ciclo</span>
                <h2>
                  {
                    elections.filter((e) =>
                      ["DRAFT", "REGISTRATION", "FREEZE", "ACTIVE", "CLOSED"].includes(e.status),
                    ).length
                  }
                </h2>
              </div>
              <div className="surface-card">
                <span className="eyebrow">Archivadas</span>
                <h2>{elections.filter((e) => e.status === "TALLIED").length}</h2>
              </div>
              <div className="surface-card">
                <span className="eyebrow">Activas</span>
                <h2 className="text-emerald-700 dark:text-emerald-300">
                  {elections.filter((e) => e.status === "ACTIVE").length}
                </h2>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
      {!isElectionsFocus ? (
      <div className="space-y-4" aria-label="Resumen administrativo">
        <div>
          <span className="eyebrow">Padrón · Estatus</span>
          <div className="surface-grid mt-2 !my-0 sm:!grid-cols-3 xl:!grid-cols-3">
            <div className="surface-card">
              <span className="eyebrow">Total</span>
              <h2>{overview.member_count}</h2>
              <p>Miembros registrados</p>
            </div>
            <div className="surface-card">
              <span className="eyebrow">Estatus activos</span>
              <h2 className="text-emerald-700 dark:text-emerald-300">{overview.active_member_count}</h2>
              <p>Columna Estatus = Activo</p>
            </div>
            <div className="surface-card">
              <span className="eyebrow">Estatus inactivos</span>
              <h2 className="text-amber-700 dark:text-amber-300">{overview.inactive_member_count}</h2>
              <p>Columna Estatus = Inactivo</p>
            </div>
          </div>
        </div>
        <div>
          <span className="eyebrow">Padrón · Tipo</span>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Categorías estatutarias S.V.I.F. (Cap. I): Activo, Temporal, Asociado, Aspirante,
            Colectivo, Correspondiente y Honorario.
          </p>
          <div className="surface-grid mt-2 !my-0 sm:!grid-cols-2 md:!grid-cols-3 xl:!grid-cols-4">
            {(overview.member_type_counts ?? []).map((item) => (
              <div className="surface-card" key={item.member_type}>
                <span className="eyebrow">{item.member_type}</span>
                <h2>{item.count}</h2>
              </div>
            ))}
          </div>
        </div>
        <div>
          <span className="eyebrow">Padrón · Elegibilidad electoral</span>
          <p className="mt-1 text-sm text-[var(--muted)]">
            ACTIVE + Vivo + Tipo con voto (Activo/Temporal/Fundador).
          </p>
          <div className="surface-grid mt-2 !my-0 sm:!grid-cols-2 xl:!grid-cols-2">
            <div className="surface-card">
              <span className="eyebrow">Elegibles para votar</span>
              <h2 className="text-emerald-700 dark:text-emerald-300">{overview.eligible_voter_count}</h2>
            </div>
            <div className="surface-card">
              <span className="eyebrow">No elegibles</span>
              <h2 className="text-amber-700 dark:text-amber-300">{overview.ineligible_voter_count}</h2>
            </div>
          </div>
        </div>
        <div className="surface-grid !my-0 sm:!grid-cols-2 xl:!grid-cols-2">
          <div className="surface-card"><span className="eyebrow">Elecciones</span><h2>{overview.election_count}</h2><p>Procesos de la organización</p></div>
          <div className="surface-card"><span className="eyebrow">Urna</span><h2>{overview.encrypted_ballot_count}</h2><p>Papeletas cifradas</p></div>
        </div>
      </div>
      ) : null}
      {focus !== "elections" ? (
      <section className="empty-state" aria-labelledby="member-title">
        <span className="eyebrow">Padrón administrativo</span>
        <h2 id="member-title">Importar y administrar padrón</h2>
        <p>El XLSX usa las columnas de Padron_Administrativo.xlsx (incluye Región). Las fotos se cargan por miembro y se almacenan en PostgreSQL.</p>
        <div className="hero-actions">
          <a className="button button-secondary" href={`${apiUrl}/api/v1/admin/members/export`} download="padron_administrativo.xlsx">
            Exportar XLSX
          </a>
        </div>
        <form className="auth-form" onSubmit={handleImportMembers}>
          <label htmlFor="member-file">Archivo XLSX</label>
          <input id="member-file" name="member_file" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required />
          <label>
            <input name="dry_run" type="checkbox" /> Solo validar, no guardar cambios
          </label>
          <button className="button button-primary" type="submit" disabled={memberBusy}>
            {memberBusy ? "Procesando…" : "Importar padrón"}
          </button>
        </form>
        <form className="auth-form" onSubmit={handleCreateMember}>
          <label htmlFor="member-full-name">Nombre completo</label>
          <input id="member-full-name" name="member_full_name" minLength={2} maxLength={255} required />
          <label htmlFor="member-email">Correo o identificador de contacto</label>
          <input id="member-email" name="member_email" type="text" maxLength={255} required />
          <label htmlFor="member-dni">Documento</label>
          <input id="member-dni" name="member_dni" minLength={3} maxLength={50} required />
          <label htmlFor="member-months">Meses de membresía</label>
          <input id="member-months" name="membership_months" type="number" min="0" max="1200" defaultValue="0" required />
          <button className="button button-primary" type="submit" disabled={memberBusy}>
            {memberBusy ? "Agregando…" : "Agregar al padrón"}
          </button>
        </form>
        {members.length === 0 ? (
          <div className="empty-state"><p>No hay miembros registrados.</p></div>
        ) : (
          <div className="election-list">
            {members.map((member) => (
              <article className="election-item" key={member.id}>
                <div>
                  <h3>{member.full_name}</h3>
                  <p>{member.registry_code ?? "Sin código"} · {member.email} · Documento {member.dni}</p>
                  <p>{member.status} · {member.member_type ?? "Sin tipo"} · Región {member.region ?? "—"} · {member.location ?? "Sin ubicación"}</p>
                  {member.photo_filename ? (
                    <a className="card-link" href={`${apiUrl}/api/v1/admin/members/${member.id}/photo`} target="_blank" rel="noreferrer">Ver foto: {member.photo_filename}</a>
                  ) : null}
                </div>
                <label className="button button-secondary">
                  {photoBusyId === member.id ? "Cargando…" : "Cargar foto"}
                  <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden onChange={(event) => void handleUploadPhoto(member.id, event)} disabled={photoBusyId !== null} />
                </label>
              </article>
            ))}
          </div>
        )}
      </section>
      ) : null}
      {focus !== "elections" ? (
      <section className="empty-state" aria-labelledby="election-form-title">
        <span className="eyebrow">Gestión electoral</span>
        <h2 id="election-form-title">Crear elección</h2>
        <p>Las nuevas elecciones se crean como DRAFT y permanecen aisladas a esta organización.</p>
        <form className="auth-form" onSubmit={handleCreateElection}>
          <label htmlFor="election-title">Título</label><input id="election-title" name="title" minLength={3} maxLength={255} required />
          <label htmlFor="election-start">Inicio</label><input id="election-start" name="start_time" type="datetime-local" required />
          <label htmlFor="election-end">Fin</label><input id="election-end" name="end_time" type="datetime-local" required />
          <label htmlFor="election-quorum">Quórum (%)</label><input id="election-quorum" name="quorum_threshold_pct" type="number" min="0" max="100" step="0.01" defaultValue="30" required />
          <label htmlFor="election-scope">Alcance territorial</label>
          <select id="election-scope" name="scope_level" defaultValue="NATIONAL" required>
            <option value="NATIONAL">Nacional (N1)</option>
            <option value="REGIONAL">Regional (N2)</option>
            <option value="STATE">Estatal / Seccional (N3)</option>
          </select>
          <label htmlFor="election-region-id">UUID región (si REGIONAL)</label>
          <input id="election-region-id" name="region_id" placeholder="Opcional salvo alcance regional" />
          <label htmlFor="election-state-id">UUID estado (si STATE)</label>
          <input id="election-state-id" name="state_id" placeholder="Opcional salvo alcance estatal" />
          <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Creando…" : "Crear elección DRAFT"}</button>
        </form>
      </section>
      ) : null}
      {showElectionList ? (
      <section aria-labelledby="election-list-title" className="mt-4">
        <span className="eyebrow">
          {showArchivada ? "Archivada" : showLifecycleActions ? "Ciclo electoral" : "Procesos"}
        </span>
        <h2 id="election-list-title" className="text-xl font-semibold">
          {showArchivada
            ? "Elecciones cerradas y escrutadas"
            : showLifecycleActions
              ? "Registro → escrutinio"
              : "Elecciones registradas"}
        </h2>
        {visibleElections.length === 0 ? (
          <div className="empty-state">
            <p>
              {showArchivada
                ? "No hay elecciones archivadas (cerradas o escrutadas)."
                : "No hay elecciones creadas para esta organización."}
            </p>
          </div>
        ) : (
          <div className="election-list">{visibleElections.map((election) => (
            <article className="election-item" key={election.id}>
              <div>
                <h3>{election.title}</h3>
                <p>{election.voting_type} · Quórum {election.quorum_threshold_pct}% · Alcance {election.scope_level ?? "NATIONAL"}</p>
                <p>Estado: {election.status}</p>
                <p className="mt-2 break-all font-mono text-xs text-[var(--muted)]">
                  ID: {election.id}
                </p>
                <button
                  type="button"
                  className="mt-1 text-xs font-bold text-[var(--primary)] underline"
                  onClick={() => {
                    void copyText(election.id).then((ok) => {
                      if (!ok) return;
                      setCopiedElectionId(election.id);
                      window.setTimeout(() => setCopiedElectionId(null), 2000);
                    });
                  }}
                >
                  {copiedElectionId === election.id ? "ID copiado" : "Copiar ID"}
                </button>
              </div>
              <div>
                <time dateTime={election.start_time}>{formatDate(election.start_time)}</time>
                <div className="hero-actions">
                  {showLifecycleActions && election.status === "DRAFT" ? (
                    <button
                      className="button button-primary inline-button"
                      type="button"
                      disabled={lifecycleBusyId === election.id}
                      onClick={() => void handleElectionLifecycle(election, "open-registration")}
                    >
                      {lifecycleBusyId === election.id ? "Abriendo…" : "Abrir registro"}
                    </button>
                  ) : null}
                  {showLifecycleActions && election.status === "REGISTRATION" ? (
                    <button
                      className="button button-primary inline-button"
                      type="button"
                      disabled={lifecycleBusyId === election.id}
                      onClick={() => void handleElectionLifecycle(election, "freeze")}
                    >
                      {lifecycleBusyId === election.id ? "Congelando…" : "Congelar padrón"}
                    </button>
                  ) : null}
                  {showLifecycleActions && election.status === "FREEZE" ? (
                    <form className="auth-form" onSubmit={(event) => void handleActivateElection(election, event)}>
                      <label htmlFor={`election-public-key-${election.id}`}>Clave pública de cifrado (urna)</label>
                      <textarea
                        id={`election-public-key-${election.id}`}
                        name="election_public_key"
                        minLength={16}
                        maxLength={8192}
                        rows={3}
                        placeholder="PEM SubjectPublicKeyInfo de cifrado"
                        required
                      />
                      <label htmlFor={`election-signing-key-${election.id}`}>
                        Clave pública de firma (opcional; recomendada en producción)
                      </label>
                      <textarea
                        id={`election-signing-key-${election.id}`}
                        name="election_signing_public_key"
                        minLength={16}
                        maxLength={8192}
                        rows={3}
                        placeholder="PEM distinta para firmar el acta; si se omite se reutiliza la de urna"
                      />
                      <button
                        className="button button-primary inline-button"
                        type="submit"
                        disabled={activationBusyId === election.id}
                      >
                        {activationBusyId === election.id ? "Activando…" : "Activar votación"}
                      </button>
                    </form>
                  ) : null}
                  {showLifecycleActions && election.status === "ACTIVE" ? (
                    <>
                      <span className="form-message">Votación activa</span>
                      <button
                        className="button button-primary inline-button"
                        type="button"
                        disabled={lifecycleBusyId === election.id}
                        onClick={() => void handleCloseElection(election, false)}
                      >
                        {lifecycleBusyId === election.id ? "Cerrando…" : "Cerrar oficial"}
                      </button>
                      <button
                        className="button button-secondary inline-button"
                        type="button"
                        disabled={lifecycleBusyId === election.id}
                        onClick={() => void handleCloseElection(election, true)}
                      >
                        {lifecycleBusyId === election.id ? "Cerrando…" : "Cerrar piloto (solo dev)"}
                      </button>
                    </>
                  ) : null}
                  {showLifecycleActions && election.status === "CLOSED" ? (
                    <form className="auth-form" onSubmit={(event) => void handlePublishTally(election, event)}>
                      <span className="form-message">Votación cerrada; escrutinio firmado pendiente</span>
                      <label htmlFor={`tally-artifact-${election.id}`}>Artefacto JSON firmado</label>
                      <textarea
                        id={`tally-artifact-${election.id}`}
                        name="tally_artifact"
                        rows={5}
                        placeholder='Pega el JSON completo: { "artifact": {...}, "signature": "..." }'
                        required
                      />
                      <label>
                        <input type="checkbox" name="tally_pilot_override" />
                        Publicar como resultado de piloto sin quórum oficial
                      </label>
                      <button
                        className="button button-primary inline-button"
                        type="submit"
                        disabled={tallyBusyId === election.id}
                      >
                        {tallyBusyId === election.id ? "Verificando…" : "Verificar y publicar tally"}
                      </button>
                      {tallyFeedback?.electionId === election.id ? (
                        <p
                          className={
                            tallyFeedback.kind === "error"
                              ? "form-message mt-2 text-amber-800 dark:text-amber-200"
                              : "form-message mt-2 text-emerald-800 dark:text-emerald-200"
                          }
                          role={tallyFeedback.kind === "error" ? "alert" : "status"}
                        >
                          {tallyFeedback.text}
                        </p>
                      ) : null}
                    </form>
                  ) : null}
                  {showLifecycleActions &&
                    (election.status === "ACTIVE" ||
                      election.status === "CLOSED" ||
                      election.status === "TALLIED" ||
                      election.status === "REGISTRATION" ||
                      election.status === "FREEZE") && (
                    onSelectCicloSection ? (
                      <button
                        className="button button-secondary inline-button"
                        type="button"
                        onClick={() => onSelectCicloSection("portal")}
                      >
                        Ir a Ceremonia YouTube
                      </button>
                    ) : (
                      <a
                        className="button button-secondary inline-button"
                        href="#ceremonia-escrutinio"
                      >
                        Ir a Ceremonia YouTube
                      </a>
                    )
                  )}
                  {showLifecycleActions && (election.status === "REGISTRATION" || election.status === "FREEZE") ? (
                    <button
                      className="button button-secondary inline-button"
                      type="button"
                      onClick={() => {
                        if (onNavigateTab) onNavigateTab("elegibles", election.id);
                        else void loadEligibility(election);
                      }}
                    >
                      Ver elegibilidad
                    </button>
                  ) : null}
                  {showLifecycleActions && (election.status === "REGISTRATION" || election.status === "FREEZE") ? (
                    <button
                      className="button button-secondary inline-button"
                      type="button"
                      onClick={() => {
                        if (onNavigateTab) onNavigateTab("planchas", election.id);
                        else void loadSlates(election);
                      }}
                    >
                      Gestionar planchas
                    </button>
                  ) : null}
                  {showLifecycleActions && (election.status === "DRAFT" || election.status === "REGISTRATION") ? (
                    <button
                      className="button button-secondary inline-button"
                      type="button"
                      onClick={() => {
                        if (onNavigateTab) onNavigateTab("estructura", election.id);
                        else void loadPositions(election);
                      }}
                    >
                      Configurar posiciones
                    </button>
                  ) : null}
                  {showLifecycleActions && (election.status === "CLOSED" || election.status === "TALLIED") ? (
                    <button
                      className="button button-secondary inline-button"
                      type="button"
                      onClick={() => void loadAudit(election)}
                    >
                      Ver auditoría
                    </button>
                  ) : null}
                  {showArchivada ? (
                    <>
                      <button
                        className="button button-secondary inline-button"
                        type="button"
                        onClick={() => void loadAudit(election)}
                      >
                        Ver auditoría
                      </button>
                      {election.status === "TALLIED" ? (
                        <a
                          className="button button-secondary inline-button"
                          href={`/admin/resultados/${election.id}`}
                        >
                          Ver resultados
                        </a>
                      ) : null}
                      <a
                        className="button button-secondary inline-button"
                        href={`/elections/${election.id}/results`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Vista pública
                      </a>
                    </>
                  ) : null}
                  {!showLifecycleActions && !showArchivada ? (
                    <>
                      <button
                        className="button button-secondary inline-button"
                        type="button"
                        onClick={() => onNavigateTab?.("ciclo", election.id)}
                      >
                        Abrir ciclo
                      </button>
                      {election.status === "DRAFT" || election.status === "REGISTRATION" ? (
                        <button
                          className="button button-secondary inline-button"
                          type="button"
                          onClick={() => onNavigateTab?.("estructura", election.id)}
                        >
                          Estructura
                        </button>
                      ) : null}
                      {election.status === "REGISTRATION" || election.status === "FREEZE" ? (
                        <>
                          <button
                            className="button button-secondary inline-button"
                            type="button"
                            onClick={() => onNavigateTab?.("planchas", election.id)}
                          >
                            Planchas
                          </button>
                          <button
                            className="button button-secondary inline-button"
                            type="button"
                            onClick={() => onNavigateTab?.("elegibles", election.id)}
                          >
                            Asignar elegibles
                          </button>
                        </>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </div>
            </article>
          ))}</div>
        )}
      </section>
      ) : null}
      {showAudit && auditElection ? (
        <section className="empty-state" aria-labelledby="audit-title">
          <span className="eyebrow">Auditoría electoral</span>
          <h2 id="audit-title">Eventos: {auditElection.title}</h2>
          <p>
            Se muestran únicamente eventos agregados de ciclo electoral y escrutinio de esta
            organización. El actor se representa por huella y no se incluyen boletas ni identidades.
          </p>
          {auditBusy ? <p className="form-message">Cargando auditoría…</p> : null}
          {!auditBusy && auditEvents.length === 0 ? (
            <p className="form-message">No hay eventos de auditoría para esta elección.</p>
          ) : (
            <div className="election-list" aria-live="polite">
              {auditEvents.map((event) => (
                <article className="election-item" key={event.id}>
                  <div>
                    <h3>{event.event_type}</h3>
                    <p>{formatDate(event.created_at)}</p>
                    <p>Actor (huella): <code>{event.actor_id_hash ?? "No disponible"}</code></p>
                    <details>
                      <summary>Ver detalles agregados</summary>
                      <pre>{JSON.stringify(event.details, null, 2)}</pre>
                    </details>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}
      {isElectionsFocus && (electionsTab === "estructura") ? (
        <section className="empty-state mt-4" aria-labelledby="estructura-picker-title">
          <span className="eyebrow">Estructura de elección</span>
          <h2 id="estructura-picker-title">Cargos y posiciones</h2>
          <p>
            Puedes definir o completar cargos en <strong>DRAFT</strong> o{" "}
            <strong>REGISTRATION</strong>. Tras congelar el padrón (FREEZE) la estructura queda
            bloqueada.
          </p>
          <label className="mt-3 block max-w-xl text-sm font-bold" htmlFor="estructura-election">
            Elección
            <select
              id="estructura-election"
              className="input-field mt-1"
              value={selectedElection?.id ?? ""}
              onChange={(event) => {
                const next = elections.find((item) => item.id === event.target.value);
                if (next) void loadPositions(next);
                else {
                  setSelectedElection(null);
                  setPositions([]);
                }
              }}
            >
              <option value="">Seleccionar elección (DRAFT o REGISTRATION)</option>
              {structureElections.map((election) => (
                <option key={election.id} value={election.id}>
                  {election.title} · {election.status}
                </option>
              ))}
            </select>
          </label>
          {structureElections.length === 0 ? (
            <p className="form-message">
              No hay elecciones editables. Crea una en DRAFT o usa una que aún no esté congelada.
            </p>
          ) : null}
        </section>
      ) : null}
      {isElectionsFocus && electionsTab === "planchas" ? (
        <section className="empty-state mt-4" aria-labelledby="plancha-picker-title">
          <span className="eyebrow">Gestionar planchas</span>
          <h2 id="plancha-picker-title">Planchas de la elección</h2>
          <p>Las planchas se crean en REGISTRATION. En FREEZE solo se revisan.</p>
          <label className="mt-3 block max-w-xl text-sm font-bold" htmlFor="slate-election-picker">
            Elección
            <select
              id="slate-election-picker"
              className="input-field mt-1"
              value={slateElection?.id ?? ""}
              onChange={(event) => {
                const next = elections.find((item) => item.id === event.target.value);
                if (next) {
                  void loadSlates(next);
                } else {
                  setSlateElection(null);
                  setSlates([]);
                  setSelectedSlate(null);
                  setCandidates([]);
                }
              }}
            >
              <option value="">Seleccionar elección en registro o congelada</option>
              {slateReadyElections.map((election) => (
                <option key={election.id} value={election.id}>
                  {election.title} · {election.status}
                </option>
              ))}
            </select>
          </label>
          {slateReadyElections.length === 0 ? (
            <p className="form-message">
              No hay elecciones en REGISTRATION o FREEZE. Abre el registro desde Ciclo electoral.
            </p>
          ) : null}
        </section>
      ) : null}

      {isElectionsFocus && electionsTab === "elegibles" ? (
        <section className="empty-state mt-4" aria-labelledby="asignar-elegibles-title">
          <span className="eyebrow">Asignar elegibles</span>
          <h2 id="asignar-elegibles-title">Candidatos por cargo</h2>
          <p>
            Asigna miembros elegibles a los cargos de cada plancha. La selección del voto sigue
            siendo por plancha (slate_id).
          </p>
          <label className="mt-3 block max-w-xl text-sm font-bold" htmlFor="elegibles-election-picker">
            Elección
            <select
              id="elegibles-election-picker"
              className="input-field mt-1"
              value={slateElection?.id ?? ""}
              onChange={(event) => {
                const next = elections.find((item) => item.id === event.target.value);
                if (next) {
                  void loadSlates(next);
                  void loadEligibility(next);
                  void loadAssignmentEligibleMembers(next);
                } else {
                  setSlateElection(null);
                  setSlates([]);
                  setSelectedSlate(null);
                  setCandidates([]);
                  setEligibilityElection(null);
                  setEligibilityMembers([]);
                  setAssignmentEligibleMembers([]);
                }
              }}
            >
              <option value="">Seleccionar elección en registro o congelada</option>
              {slateReadyElections.map((election) => (
                <option key={election.id} value={election.id}>
                  {election.title} · {election.status}
                </option>
              ))}
            </select>
          </label>
          {slateReadyElections.length === 0 ? (
            <p className="form-message">
              No hay elecciones en REGISTRATION o FREEZE. Abre el registro desde Ciclo electoral.
            </p>
          ) : null}

          {slateElection ? (
            <div className="mt-5 space-y-4">
              <label className="block max-w-xl text-sm font-bold" htmlFor="elegibles-slate-picker">
                Plancha a asignar
                <select
                  id="elegibles-slate-picker"
                  className="input-field mt-1"
                  value={selectedSlate?.id ?? ""}
                  onChange={(event) => {
                    const next = slates.find((item) => item.id === event.target.value);
                    if (next) void loadCandidates(next);
                    else {
                      setSelectedSlate(null);
                      setCandidates([]);
                    }
                  }}
                >
                  <option value="">Seleccionar plancha</option>
                  {slates.map((slate) => (
                    <option key={slate.id} value={slate.id}>
                      {slate.name} · {slate.candidate_count} candidatos
                    </option>
                  ))}
                </select>
              </label>

              {selectedSlate ? (
                <div className="rounded-xl border border-[var(--line)] bg-[var(--background)] p-4" aria-labelledby="candidate-title">
                  <h3 id="candidate-title" className="text-base font-semibold">
                    Candidatos: {selectedSlate.name}
                  </h3>
                  {candidates.length === 0 ? (
                    <p className="mt-2 text-sm text-[var(--muted)]">No hay candidatos registrados.</p>
                  ) : (
                    <div className="election-list mt-3">
                      {candidates.map((candidate) => (
                        <article className="election-item" key={candidate.id}>
                          <div>
                            <h4>
                              {candidate.position_code} · {candidate.position_title}
                            </h4>
                            <p>
                              {candidate.member_full_name} ·{" "}
                              {candidate.member_registry_code ?? candidate.member_dni}
                            </p>
                            <p>{candidate.bio ?? "Sin biografía"}</p>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                  {slateElection.status === "REGISTRATION" ? (
                    <form className="auth-form mt-4" onSubmit={handleCreateCandidate}>
                      <label htmlFor="candidate-position-input">Posición / cargo</label>
                      <select id="candidate-position-input" name="candidate_position_id" required>
                        <option value="">Selecciona una posición</option>
                        {positions.map((position) => (
                          <option value={position.id} key={position.id}>
                            {position.code} · {position.title}
                          </option>
                        ))}
                      </select>
                      <label htmlFor="candidate-member-input">
                        Miembro elegible
                        <span className="mt-0.5 block text-xs font-normal text-[var(--muted)]">
                          Solo el snapshot territorial de esta elección
                          {slateElection.scope_level
                            ? ` (${slateElection.scope_level})`
                            : ""}
                          : {assignmentEligibleMembers.length} elegible
                          {assignmentEligibleMembers.length === 1 ? "" : "s"}
                        </span>
                      </label>
                      <select
                        id="candidate-member-input"
                        name="candidate_member_id"
                        required
                        disabled={assignmentEligibleMembers.length === 0}
                      >
                        <option value="">
                          {assignmentEligibleMembers.length === 0
                            ? "No hay elegibles en este territorio"
                            : "Selecciona un miembro elegible"}
                        </option>
                        {assignmentEligibleMembers.map((member) => (
                          <option value={member.member_id} key={member.member_id}>
                            {member.full_name} · {member.registry_code ?? member.dni}
                          </option>
                        ))}
                      </select>
                      <label htmlFor="candidate-bio-input">Biografía</label>
                      <textarea id="candidate-bio-input" name="candidate_bio" maxLength={5000} rows={4} />
                      <button
                        className="button button-primary"
                        type="submit"
                        disabled={
                          candidateBusy ||
                          positions.length === 0 ||
                          assignmentEligibleMembers.length === 0
                        }
                      >
                        {candidateBusy ? "Registrando…" : "Asignar elegible al cargo"}
                      </button>
                    </form>
                  ) : (
                    <p className="mt-3 text-sm text-[var(--muted)]">
                      La elección está congelada: solo lectura de candidatos.
                    </p>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {showPlanchas && slateElection ? (
        <section className="empty-state mt-4" aria-labelledby="slate-title">
          <span className="eyebrow">Registro de planchas</span>
          <h2 id="slate-title">Planchas: {slateElection.title}</h2>
          <p>
            Las planchas se crean solo en REGISTRATION. En FREEZE se pueden revisar, pero no
            modificar.
          </p>
          {slates.length === 0 ? (
            <p className="form-message">No hay planchas registradas.</p>
          ) : (
            <div className="election-list">
              {slates.map((slate) => (
                <article className="election-item" key={slate.id}>
                  <div>
                    <h3>{slate.name}</h3>
                    <p>
                      {slate.slogan ?? "Sin lema"} · Estado {slate.status}
                    </p>
                    <p>Candidatos registrados: {slate.candidate_count}</p>
                  </div>
                  {electionsTab === "planchas" || !isElectionsFocus ? (
                    <button
                      className="button button-secondary"
                      type="button"
                      onClick={() => void loadCandidates(slate)}
                    >
                      Ver candidatos
                    </button>
                  ) : (
                    <button
                      className="button button-secondary"
                      type="button"
                      onClick={() => void loadCandidates(slate)}
                    >
                      Usar en asignación
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
          {(electionsTab === "planchas" ||
            electionsTab === "elegibles" ||
            !isElectionsFocus) &&
          slateElection.status === "REGISTRATION" ? (
            <form className="auth-form" onSubmit={handleCreateSlate}>
              <label htmlFor="slate-name-input">Nombre de plancha</label>
              <input id="slate-name-input" name="slate_name" minLength={2} maxLength={150} required />
              <label htmlFor="slate-slogan-input">Lema</label>
              <input id="slate-slogan-input" name="slate_slogan" maxLength={255} />
              <label htmlFor="proxy-member-input">Apoderado (opcional)</label>
              <select id="proxy-member-input" name="proxy_member_id" defaultValue="">
                <option value="">Sin apoderado vinculado</option>
                {members.map((member) => (
                  <option value={member.id} key={member.id}>
                    {member.full_name} · {member.registry_code ?? member.dni}
                  </option>
                ))}
              </select>
              <button className="button button-primary" type="submit" disabled={slateBusy}>
                {slateBusy ? "Creando…" : "Crear plancha"}
              </button>
            </form>
          ) : null}
          {selectedSlate && (electionsTab === "planchas" || !isElectionsFocus) ? (
            <div className="empty-state" aria-labelledby="candidate-title-planchas">
              <h3 id="candidate-title-planchas">Candidatos: {selectedSlate.name}</h3>
              {candidates.length === 0 ? (
                <p>No hay candidatos registrados.</p>
              ) : (
                <div className="election-list">
                  {candidates.map((candidate) => (
                    <article className="election-item" key={candidate.id}>
                      <div>
                        <h4>
                          {candidate.position_code} · {candidate.position_title}
                        </h4>
                        <p>
                          {candidate.member_full_name} ·{" "}
                          {candidate.member_registry_code ?? candidate.member_dni}
                        </p>
                        <p>{candidate.bio ?? "Sin biografía"}</p>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              {!isElectionsFocus && slateElection.status === "REGISTRATION" ? (
                <form className="auth-form" onSubmit={handleCreateCandidate}>
                  <label htmlFor="candidate-position-input-legacy">Posición / cargo</label>
                  <select id="candidate-position-input-legacy" name="candidate_position_id" required>
                    <option value="">Selecciona una posición</option>
                    {positions.map((position) => (
                      <option value={position.id} key={position.id}>
                        {position.code} · {position.title}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="candidate-member-input-legacy">Miembro elegible</label>
                  <select id="candidate-member-input-legacy" name="candidate_member_id" required>
                    <option value="">Selecciona un miembro</option>
                    {members.map((member) => (
                      <option value={member.id} key={member.id}>
                        {member.full_name} · {member.registry_code ?? member.dni}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="candidate-bio-input-legacy">Biografía</label>
                  <textarea
                    id="candidate-bio-input-legacy"
                    name="candidate_bio"
                    maxLength={5000}
                    rows={4}
                  />
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={candidateBusy || positions.length === 0}
                  >
                    {candidateBusy ? "Registrando…" : "Asignar elegible al cargo"}
                  </button>
                </form>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {showElegiblesDetail && eligibilityElection ? (
        <section className="empty-state mt-4" aria-labelledby="eligibility-title">
          <span className="eyebrow">Snapshot de elegibilidad</span>
          <h2 id="eligibility-title">Elegibilidad: {eligibilityElection.title}</h2>
          <p>
            Este detalle corresponde al snapshot creado al abrir el registro. No se muestran fotos
            ni datos de la urna.
          </p>
          <label htmlFor="eligibility-filter">Filtrar registros</label>
          <select
            id="eligibility-filter"
            value={eligibilityFilter}
            onChange={(event) => {
              const nextFilter = event.target.value as EligibilityFilter;
              setEligibilityFilter(nextFilter);
              setEligibilityPage(1);
              void loadEligibility(eligibilityElection, nextFilter);
            }}
            disabled={eligibilityBusy}
          >
            <option value="all">Todos</option>
            <option value="eligible">Solo elegibles</option>
            <option value="ineligible">Solo no elegibles</option>
          </select>
          {eligibilityBusy ? <p className="form-message">Cargando elegibilidad…</p> : null}
          {!eligibilityBusy && eligibilityMembers.length === 0 ? (
            <p className="form-message">No hay registros para este filtro.</p>
          ) : !eligibilityBusy ? (
            <>
              <p className="mt-3 text-xs text-[var(--muted)]">
                Mostrando {(eligibilityPageSafe - 1) * ELIGIBILITY_PAGE_SIZE + 1}–
                {Math.min(eligibilityPageSafe * ELIGIBILITY_PAGE_SIZE, eligibilityMembers.length)} de{" "}
                {eligibilityMembers.length}
              </p>
              <div className="election-list" aria-live="polite">
                {eligibilityPageItems.map((member) => (
                  <article className="election-item" key={member.member_id}>
                    <div>
                      <h3>{member.full_name}</h3>
                      <p>
                        {member.registry_code ?? "Sin código"} · Documento {member.dni}
                      </p>
                      <p>
                        Estado: {member.status} · Tipo: {member.member_type ?? "Sin tipo"} · Vivo:{" "}
                        {member.alive === true
                          ? "Sí"
                          : member.alive === false
                            ? "No"
                            : "No confirmado"}
                      </p>
                      <p>Motivo: {member.reason}</p>
                    </div>
                    <strong>{member.eligible ? "Elegible" : "No elegible"}</strong>
                  </article>
                ))}
              </div>
              {eligibilityMembers.length > ELIGIBILITY_PAGE_SIZE ? (
                <div className="eligibility-pager" role="navigation" aria-label="Paginación del snapshot">
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={eligibilityPageSafe <= 1}
                    onClick={() => setEligibilityPage((page) => Math.max(1, page - 1))}
                  >
                    Anterior
                  </button>
                  <span className="eligibility-pager__status">
                    Página {eligibilityPageSafe} de {eligibilityTotalPages}
                  </span>
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={eligibilityPageSafe >= eligibilityTotalPages}
                    onClick={() =>
                      setEligibilityPage((page) => Math.min(eligibilityTotalPages, page + 1))
                    }
                  >
                    Siguiente
                  </button>
                </div>
              ) : null}
            </>
          ) : null}
        </section>
      ) : null}

      {showEstructura && selectedElection ? (
        <section className="empty-state" aria-labelledby="position-title">
          <span className="eyebrow">Estructura de elección</span>
          <h2 id="position-title">Posiciones: {selectedElection.title}</h2>
          <p>
            Las posiciones definen los cargos de la papeleta. Estado actual:{" "}
            <strong>{selectedElection.status}</strong>
            {!canEditPositions
              ? ". Esta elección ya está congelada o activa; no se pueden agregar cargos."
              : ". Puedes agregar cargos hasta antes de congelar el padrón."}
          </p>
          <div className="election-list">{positions.length === 0 ? <p>No hay posiciones configuradas.</p> : positions.map((position) => (
            <article className="election-item" key={position.id}><div><h3>{position.title}</h3><p>{position.code} · {position.is_required ? "Obligatoria" : "Opcional"}</p></div><time>Orden {position.display_order}</time></article>
          ))}</div>
          {canEditPositions ? (
            <form className="auth-form" onSubmit={handleCreatePosition}>
              <label htmlFor="position-title-input">Título de posición</label><input id="position-title-input" name="position_title" minLength={2} maxLength={100} required />
              <label htmlFor="position-code-input">Código</label><input id="position-code-input" name="position_code" pattern="[A-Za-z][A-Za-z0-9_-]{1,49}" placeholder="PRESIDENTE" maxLength={50} required />
              <label htmlFor="position-order-input">Orden</label><input id="position-order-input" name="position_order" type="number" min="0" max="10000" defaultValue="0" required />
              <label><input name="position_required" type="checkbox" defaultChecked /> Posición obligatoria</label>
              <button className="button button-primary" type="submit" disabled={positionBusy}>{positionBusy ? "Creando…" : "Agregar posición"}</button>
            </form>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
