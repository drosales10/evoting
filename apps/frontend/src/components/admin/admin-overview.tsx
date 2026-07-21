"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

type AdminOverview = {
  organization_slug: string;
  organization_name: string;
  roles: string[];
  member_count: number;
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

type ApiError = { detail?: string };

type ApiValidationIssue = {
  loc?: unknown;
  msg?: unknown;
};

function apiErrorDetail(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return null;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (!Array.isArray(detail)) {
    return null;
  }
  const messages = detail.flatMap((issue: unknown) => {
    if (typeof issue === "string" && issue.trim()) {
      return [issue];
    }
    if (typeof issue !== "object" || issue === null) {
      return [];
    }
    const validationIssue = issue as ApiValidationIssue;
    const message = typeof validationIssue.msg === "string" ? validationIssue.msg : null;
    if (!message) {
      return [];
    }
    const location = Array.isArray(validationIssue.loc)
      ? validationIssue.loc.filter((part): part is string | number =>
          typeof part === "string" || typeof part === "number",
        ).join(".")
      : "respuesta";
    return [`${location}: ${message}`];
  });
  return messages.length > 0 ? messages.join("; ") : null;
}

async function requestApiJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
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
    const detail = apiErrorDetail(payload);
    if (response.status === 401) {
      throw new Error(
        detail
          ? `La sesión administrativa no está activa: ${detail}.`
          : "La sesión administrativa no está activa o expiró (HTTP 401). Inicia sesión nuevamente.",
      );
    }
    throw new Error(
      `La API administrativa respondió HTTP ${response.status}: ${detail ?? "sin detalle"}.`,
    );
  }

  return payload as T;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function AdminOverview() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [members, setMembers] = useState<AdminMember[]>([]);
  const [elections, setElections] = useState<AdminElection[]>([]);
  const [selectedElection, setSelectedElection] = useState<AdminElection | null>(null);
  const [positions, setPositions] = useState<AdminPosition[]>([]);
  const [eligibilityElection, setEligibilityElection] = useState<AdminElection | null>(null);
  const [eligibilityMembers, setEligibilityMembers] = useState<AdminElectionEligibilityMember[]>([]);
  const [eligibilityFilter, setEligibilityFilter] = useState<EligibilityFilter>("all");
  const [eligibilityBusy, setEligibilityBusy] = useState(false);
  const [slateElection, setSlateElection] = useState<AdminElection | null>(null);
  const [slates, setSlates] = useState<AdminSlate[]>([]);
  const [selectedSlate, setSelectedSlate] = useState<AdminSlate | null>(null);
  const [candidates, setCandidates] = useState<AdminCandidate[]>([]);
  const [slateBusy, setSlateBusy] = useState(false);
  const [candidateBusy, setCandidateBusy] = useState(false);
  const [slateMessage, setSlateMessage] = useState<string | null>(null);
  const [message, setMessage] = useState("Cargando resumen administrativo…");
  const [memberMessage, setMemberMessage] = useState<string | null>(null);
  const [positionMessage, setPositionMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [memberBusy, setMemberBusy] = useState(false);
  const [positionBusy, setPositionBusy] = useState(false);
  const [lifecycleBusyId, setLifecycleBusyId] = useState<string | null>(null);
  const [activationBusyId, setActivationBusyId] = useState<string | null>(null);
  const [photoBusyId, setPhotoBusyId] = useState<string | null>(null);

  async function loadData() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const [overviewResponse, membersResponse, electionsResponse] = await Promise.all([
      fetch(`${apiUrl}/api/v1/admin/overview`, { credentials: "include", cache: "no-store" }),
      fetch(`${apiUrl}/api/v1/admin/members`, { credentials: "include", cache: "no-store" }),
      fetch(`${apiUrl}/api/v1/admin/elections`, { credentials: "include", cache: "no-store" }),
    ]);
    const overviewPayload = (await overviewResponse.json()) as AdminOverview & ApiError;
    const membersPayload = (await membersResponse.json()) as AdminMember[] & ApiError;
    const electionsPayload = (await electionsResponse.json()) as AdminElection[] & ApiError;

    if (!overviewResponse.ok || !membersResponse.ok || !electionsResponse.ok) {
      const unauthorized = [overviewResponse, membersResponse, electionsResponse].some(
        (response) => response.status === 401,
      );
      throw new Error(
        unauthorized
          ? "Tu sesión administrativa no está activa. Accede para continuar."
          : overviewPayload.detail ?? membersPayload.detail ?? electionsPayload.detail ??
            "No se pudo cargar el resumen administrativo.",
      );
    }
    setOverview(overviewPayload);
    setMembers(membersPayload);
    setElections(electionsPayload);
    setMessage("");
  }

  useEffect(() => {
    void loadData().catch((error: unknown) => {
      setMessage(error instanceof Error ? error.message : "No se pudo cargar el resumen administrativo.");
    });
  }, []);

  async function handleImportMembers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMemberBusy(true);
    setMemberMessage(null);
    const form = new FormData(event.currentTarget);
    const file = form.get("member_file");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    if (!(file instanceof File) || file.size === 0) {
      setMemberMessage("Selecciona un archivo XLSX.");
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
        setMemberMessage(payload.detail ?? "No se pudo importar el padrón.");
        return;
      }
      await loadData();
      setMemberMessage(
        `${payload.dry_run ? "Validación" : "Importación"} terminada: ${payload.rows_read} filas, ` +
          `${payload.created} nuevas, ${payload.updated} actualizadas y ${payload.failed} con error.`,
      );
    } catch {
      setMemberMessage("No se pudo contactar la API administrativa.");
    } finally {
      setMemberBusy(false);
    }
  }

  async function handleUploadPhoto(memberId: string, event: ChangeEvent<HTMLInputElement>) {
    const inputElement = event.currentTarget;
    const file = inputElement.files?.[0];
    if (!file) return;
    setPhotoBusyId(memberId);
    setMemberMessage(null);
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
        setMemberMessage(payload.detail ?? "No se pudo cargar la foto.");
        return;
      }
      setMembers((current) => current.map((member) => member.id === memberId ? payload : member));
      setMemberMessage("Foto guardada en PostgreSQL.");
    } catch {
      setMemberMessage("No se pudo contactar la API administrativa.");
    } finally {
      setPhotoBusyId(null);
      inputElement.value = "";
    }
  }

  async function handleCreateMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMemberBusy(true);
    setMemberMessage(null);
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
        setMemberMessage(payload.detail ?? "No se pudo crear el miembro.");
        return;
      }
      setMembers((current) => [...current, payload].sort((left, right) =>
        left.full_name.localeCompare(right.full_name, "es"),
      ));
      setOverview((current) =>
        current ? { ...current, member_count: current.member_count + 1 } : current,
      );
      formElement.reset();
      setMemberMessage("Miembro agregado al padrón activo.");
    } catch {
      setMemberMessage("No se pudo contactar la API administrativa.");
    } finally {
      setMemberBusy(false);
    }
  }

  async function handleCreateElection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
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
          start_time: new Date(startTime).toISOString(),
          end_time: new Date(endTime).toISOString(),
          quorum_threshold_pct: Number(form.get("quorum_threshold_pct") ?? 30),
        }),
      });
      const payload = (await response.json()) as AdminElection & ApiError;
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo crear la elección.");
        return;
      }
      setElections((current) => [...current, payload].sort((left, right) =>
        new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
      ));
      setOverview((current) =>
        current ? { ...current, election_count: current.election_count + 1 } : current,
      );
      formElement.reset();
      setMessage("Elección creada en estado DRAFT.");
    } catch {
      setMessage("No se pudo contactar la API administrativa.");
    } finally {
      setBusy(false);
    }
  }

  async function handleElectionLifecycle(
    election: AdminElection,
    action: "open-registration" | "freeze",
  ) {
    setLifecycleBusyId(election.id);
    setMessage("");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const response = await fetch(
        `${apiUrl}/api/v1/admin/elections/${election.id}/${action}`,
        { method: "POST", credentials: "include" },
      );
      const payload = (await response.json()) as AdminElectionEligibility & ApiError;
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo cambiar el estado de la elección.");
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
      setMessage(
        `${action === "open-registration" ? "Registro abierto" : "Padrón congelado"}. ` +
        `${payload.eligible_member_count} elegibles de ${payload.snapshot_member_count}.`,
      );
    } catch {
      setMessage("No se pudo contactar la API administrativa.");
    } finally {
      setLifecycleBusyId(null);
    }
  }

  async function handleCloseElection(election: AdminElection) {
    setLifecycleBusyId(election.id);
    setMessage("");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminElectionCloseResponse>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/close`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            force_pilot: true,
            reason: "Cierre explícito del piloto local de ocho votos",
          }),
        },
      );
      setElections((current) => current.map((item) =>
        item.id === election.id ? { ...item, status: payload.election_status } : item,
      ));
      if (selectedElection?.id === election.id) {
        setSelectedElection({ ...selectedElection, status: payload.election_status });
      }
      setMessage(
        `Piloto cerrado: ${payload.ballot_count} boletas y ${payload.voted_member_count} participaciones. ` +
        `Quórum: ${payload.quorum_met ? "cumplido" : `no cumplido (${payload.quorum_required} requeridos)`}. ` +
        "El escrutinio requiere la clave privada fuera de la API.",
      );
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "No se pudo cerrar la elección.");
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
    setMessage("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const publicKey = String(form.get("election_public_key") ?? "").trim();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminElectionActivationResponse>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/activate`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ public_key: publicKey }),
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
      setMessage(
        `Votación activa: ${payload.slate_count} planchas, ${payload.candidate_count} candidatos y ` +
        `${payload.eligible_member_count} electores elegibles. Huella de clave pública: ` +
        `${payload.public_key_sha256.slice(0, 16)}…`,
      );
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "No se pudo activar la elección.");
    } finally {
      setActivationBusyId(null);
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
        setMessage(payload.detail ?? "No se pudo cargar el detalle de elegibilidad.");
        setEligibilityMembers([]);
        return;
      }
      setEligibilityMembers(payload);
    } catch {
      setMessage("No se pudo contactar la API administrativa.");
      setEligibilityMembers([]);
    } finally {
      setEligibilityBusy(false);
    }
  }

  async function loadSlates(election: AdminElection) {
    setSlateElection(election);
    setSelectedSlate(null);
    setCandidates([]);
    setSlateMessage(null);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminSlate[]>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/slates`,
        { credentials: "include", cache: "no-store" },
      );
      setSlates(payload);
      void loadPositions(election);
    } catch (error: unknown) {
      setSlateMessage(
        error instanceof Error ? error.message : "No se pudieron cargar las planchas.",
      );
      setSlates([]);
    }
  }

  async function loadCandidates(slate: AdminSlate) {
    setSelectedSlate(slate);
    setSlateMessage(null);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminCandidate[]>(
        `${apiUrl}/api/v1/admin/slates/${slate.id}/candidates`,
        { credentials: "include", cache: "no-store" },
      );
      setCandidates(payload);
    } catch (error: unknown) {
      setSlateMessage(
        error instanceof Error ? error.message : "No se pudieron cargar los candidatos.",
      );
      setCandidates([]);
    }
  }

  async function handleCreateSlate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slateElection) return;
    setSlateBusy(true);
    setSlateMessage(null);
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
      setSlateMessage("Plancha creada en estado PENDING.");
    } catch (error: unknown) {
      setSlateMessage(
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
    setSlateMessage(null);
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
      setSlateMessage("Candidato registrado correctamente.");
    } catch (error: unknown) {
      setSlateMessage(
        error instanceof Error ? error.message : "No se pudo registrar el candidato.",
      );
    } finally {
      setCandidateBusy(false);
    }
  }

  async function loadPositions(election: AdminElection) {
    setSelectedElection(election);
    setPositionMessage(null);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const payload = await requestApiJson<AdminPosition[]>(
        `${apiUrl}/api/v1/admin/elections/${election.id}/positions`,
        { credentials: "include", cache: "no-store" },
      );
      setPositions(payload);
    } catch (error: unknown) {
      setPositionMessage(
        error instanceof Error ? error.message : "No se pudieron cargar las posiciones.",
      );
    }
  }

  async function handleCreatePosition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedElection) return;
    setPositionBusy(true);
    setPositionMessage(null);
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
        setPositionMessage(payload.detail ?? "No se pudo crear la posición.");
        return;
      }
      setPositions((current) => [...current, payload].sort(
        (left, right) => left.display_order - right.display_order,
      ));
      formElement.reset();
      setPositionMessage("Posición creada correctamente.");
    } catch {
      setPositionMessage("No se pudo contactar la API administrativa.");
    } finally {
      setPositionBusy(false);
    }
  }

  if (!overview) {
    return <div className="notice"><p>{message}</p></div>;
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return (
    <>
      <div className="notice">
        <strong>{overview.organization_name}</strong>
        <p>Organización: {overview.organization_slug}</p>
        <p>Roles activos: {overview.roles.join(", ")}</p>
      </div>
      <div className="surface-grid" aria-label="Resumen administrativo">
        <div className="surface-card"><span className="eyebrow">Padrón</span><h2>{overview.member_count}</h2><p>Miembros registrados</p></div>
        <div className="surface-card"><span className="eyebrow">Elecciones</span><h2>{overview.election_count}</h2><p>Procesos de la organización</p></div>
        <div className="surface-card"><span className="eyebrow">Urna</span><h2>{overview.encrypted_ballot_count}</h2><p>Papeletas cifradas</p></div>
      </div>
      <section className="empty-state" aria-labelledby="member-title">
        <span className="eyebrow">Padrón administrativo</span>
        <h2 id="member-title">Importar y administrar padrón</h2>
        <p>El XLSX usa las 17 columnas de Padron_Administrativo.xlsx. Las fotos se cargan por miembro y se almacenan en PostgreSQL.</p>
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
        {memberMessage ? <p className="form-message" role="status">{memberMessage}</p> : null}
        {members.length === 0 ? (
          <div className="empty-state"><p>No hay miembros registrados.</p></div>
        ) : (
          <div className="election-list">
            {members.map((member) => (
              <article className="election-item" key={member.id}>
                <div>
                  <h3>{member.full_name}</h3>
                  <p>{member.registry_code ?? "Sin código"} · {member.email} · Documento {member.dni}</p>
                  <p>{member.status} · {member.member_type ?? "Sin tipo"} · {member.location ?? "Sin ubicación"}</p>
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
      <section className="empty-state" aria-labelledby="election-form-title">
        <span className="eyebrow">Gestión electoral</span>
        <h2 id="election-form-title">Crear elección</h2>
        <p>Las nuevas elecciones se crean como DRAFT y permanecen aisladas a esta organización.</p>
        <form className="auth-form" onSubmit={handleCreateElection}>
          <label htmlFor="election-title">Título</label><input id="election-title" name="title" minLength={3} maxLength={255} required />
          <label htmlFor="election-start">Inicio</label><input id="election-start" name="start_time" type="datetime-local" required />
          <label htmlFor="election-end">Fin</label><input id="election-end" name="end_time" type="datetime-local" required />
          <label htmlFor="election-quorum">Quórum (%)</label><input id="election-quorum" name="quorum_threshold_pct" type="number" min="0" max="100" step="0.01" defaultValue="30" required />
          <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Creando…" : "Crear elección DRAFT"}</button>
        </form>
        {message ? <p className="form-message" role="status">{message}</p> : null}
      </section>
      <section aria-labelledby="election-list-title">
        <span className="eyebrow">Procesos registrados</span><h2 id="election-list-title">Elecciones</h2>
        {elections.length === 0 ? <div className="empty-state"><p>No hay elecciones creadas para esta organización.</p></div> : (
          <div className="election-list">{elections.map((election) => (
            <article className="election-item" key={election.id}>
              <div>
                <h3>{election.title}</h3>
                <p>{election.voting_type} · Quórum {election.quorum_threshold_pct}%</p>
                <p>Estado: {election.status}</p>
              </div>
              <div>
                <time dateTime={election.start_time}>{formatDate(election.start_time)}</time>
                <div className="hero-actions">
                  {election.status === "DRAFT" ? (
                    <button
                      className="button button-primary inline-button"
                      type="button"
                      disabled={lifecycleBusyId === election.id}
                      onClick={() => void handleElectionLifecycle(election, "open-registration")}
                    >
                      {lifecycleBusyId === election.id ? "Abriendo…" : "Abrir registro"}
                    </button>
                  ) : election.status === "REGISTRATION" ? (
                    <button
                      className="button button-primary inline-button"
                      type="button"
                      disabled={lifecycleBusyId === election.id}
                      onClick={() => void handleElectionLifecycle(election, "freeze")}
                    >
                      {lifecycleBusyId === election.id ? "Congelando…" : "Congelar padrón"}
                    </button>
                  ) : election.status === "FREEZE" ? (
                    <form className="auth-form" onSubmit={(event) => void handleActivateElection(election, event)}>
                      <label htmlFor={`election-public-key-${election.id}`}>Clave pública de la elección</label>
                      <textarea
                        id={`election-public-key-${election.id}`}
                        name="election_public_key"
                        minLength={16}
                        maxLength={8192}
                        rows={3}
                        placeholder="Pega aquí la clave pública versionada de la urna"
                        required
                      />
                      <button
                        className="button button-primary inline-button"
                        type="submit"
                        disabled={activationBusyId === election.id}
                      >
                        {activationBusyId === election.id ? "Activando…" : "Activar votación"}
                      </button>
                    </form>
                  ) : election.status === "ACTIVE" ? (
                    <>
                      <span className="form-message">Votación activa</span>
                      <button
                        className="button button-secondary inline-button"
                        type="button"
                        disabled={lifecycleBusyId === election.id}
                        onClick={() => void handleCloseElection(election)}
                      >
                        {lifecycleBusyId === election.id ? "Cerrando…" : "Cerrar piloto local"}
                      </button>
                    </>
                  ) : election.status === "CLOSED" ? (
                    <span className="form-message">Votación cerrada; escrutinio local pendiente</span>
                  ) : null}
                  {election.status === "REGISTRATION" || election.status === "FREEZE" ? (
                    <button
                      className="button button-secondary inline-button"
                      type="button"
                      onClick={() => void loadEligibility(election)}
                    >
                      Ver elegibilidad
                    </button>
                  ) : null}
                  {election.status === "REGISTRATION" || election.status === "FREEZE" ? (
                    <button
                      className="button button-secondary inline-button"
                      type="button"
                      onClick={() => void loadSlates(election)}
                    >
                      Gestionar planchas
                    </button>
                  ) : null}
                  {election.status === "DRAFT" ? (
                    <button
                      className="button button-secondary inline-button"
                      type="button"
                      onClick={() => void loadPositions(election)}
                    >
                      Configurar posiciones
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}</div>
        )}
      </section>
      {eligibilityElection ? (
        <section className="empty-state" aria-labelledby="eligibility-title">
          <span className="eyebrow">Snapshot de elegibilidad</span>
          <h2 id="eligibility-title">Elegibilidad: {eligibilityElection.title}</h2>
          <p>
            Este detalle corresponde al snapshot creado al abrir el registro. No se muestran fotos ni
            datos de la urna.
          </p>
          <label htmlFor="eligibility-filter">Filtrar registros</label>
          <select
            id="eligibility-filter"
            value={eligibilityFilter}
            onChange={(event) => {
              const nextFilter = event.target.value as EligibilityFilter;
              setEligibilityFilter(nextFilter);
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
          ) : (
            <div className="election-list" aria-live="polite">
              {eligibilityMembers.map((member) => (
                <article className="election-item" key={member.member_id}>
                  <div>
                    <h3>{member.full_name}</h3>
                    <p>
                      {member.registry_code ?? "Sin código"} · Documento {member.dni}
                    </p>
                    <p>
                      Estado: {member.status} · Vivo: {member.alive === true ? "Sí" : member.alive === false ? "No" : "No confirmado"}
                    </p>
                    <p>Motivo: {member.reason}</p>
                  </div>
                  <strong>{member.eligible ? "Elegible" : "No elegible"}</strong>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}
      {slateElection ? (
        <section className="empty-state" aria-labelledby="slate-title">
          <span className="eyebrow">Registro de planchas</span>
          <h2 id="slate-title">Planchas: {slateElection.title}</h2>
          <p>
            Las planchas se crean solo en REGISTRATION. En FREEZE se pueden revisar, pero no modificar.
          </p>
          {slates.length === 0 ? <p className="form-message">No hay planchas registradas.</p> : (
            <div className="election-list">
              {slates.map((slate) => (
                <article className="election-item" key={slate.id}>
                  <div>
                    <h3>{slate.name}</h3>
                    <p>{slate.slogan ?? "Sin lema"} · Estado {slate.status}</p>
                    <p>Candidatos registrados: {slate.candidate_count}</p>
                  </div>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => void loadCandidates(slate)}
                  >
                    Ver candidatos
                  </button>
                </article>
              ))}
            </div>
          )}
          {slateElection.status === "REGISTRATION" ? (
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
          {selectedSlate ? (
            <div className="empty-state" aria-labelledby="candidate-title">
              <h3 id="candidate-title">Candidatos: {selectedSlate.name}</h3>
              {candidates.length === 0 ? <p>No hay candidatos registrados.</p> : (
                <div className="election-list">
                  {candidates.map((candidate) => (
                    <article className="election-item" key={candidate.id}>
                      <div>
                        <h4>{candidate.position_code} · {candidate.position_title}</h4>
                        <p>{candidate.member_full_name} · {candidate.member_registry_code ?? candidate.member_dni}</p>
                        <p>{candidate.bio ?? "Sin biografía"}</p>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              {slateElection.status === "REGISTRATION" ? (
                <form className="auth-form" onSubmit={handleCreateCandidate}>
                  <label htmlFor="candidate-position-input">Posición</label>
                  <select id="candidate-position-input" name="candidate_position_id" required>
                    <option value="">Selecciona una posición</option>
                    {positions.map((position) => (
                      <option value={position.id} key={position.id}>
                        {position.code} · {position.title}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="candidate-member-input">Miembro elegible</label>
                  <select id="candidate-member-input" name="candidate_member_id" required>
                    <option value="">Selecciona un miembro</option>
                    {members.map((member) => (
                      <option value={member.id} key={member.id}>
                        {member.full_name} · {member.registry_code ?? member.dni}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="candidate-bio-input">Biografía</label>
                  <textarea id="candidate-bio-input" name="candidate_bio" maxLength={5000} rows={4} />
                  <button className="button button-primary" type="submit" disabled={candidateBusy || positions.length === 0}>
                    {candidateBusy ? "Registrando…" : "Registrar candidato"}
                  </button>
                </form>
              ) : null}
            </div>
          ) : null}
          {slateMessage ? <p className="form-message" role="status">{slateMessage}</p> : null}
        </section>
      ) : null}
      {selectedElection ? (
        <section className="empty-state" aria-labelledby="position-title">
          <span className="eyebrow">Estructura de elección DRAFT</span><h2 id="position-title">Posiciones: {selectedElection.title}</h2>
          <p>Las posiciones definen los cargos antes de registrar planchas y candidatos.</p>
          <div className="election-list">{positions.length === 0 ? <p>No hay posiciones configuradas.</p> : positions.map((position) => (
            <article className="election-item" key={position.id}><div><h3>{position.title}</h3><p>{position.code} · {position.is_required ? "Obligatoria" : "Opcional"}</p></div><time>Orden {position.display_order}</time></article>
          ))}</div>
          <form className="auth-form" onSubmit={handleCreatePosition}>
            <label htmlFor="position-title-input">Título de posición</label><input id="position-title-input" name="position_title" minLength={2} maxLength={100} required />
            <label htmlFor="position-code-input">Código</label><input id="position-code-input" name="position_code" pattern="[A-Za-z][A-Za-z0-9_-]{1,49}" placeholder="PRESIDENTE" maxLength={50} required />
            <label htmlFor="position-order-input">Orden</label><input id="position-order-input" name="position_order" type="number" min="0" max="10000" defaultValue="0" required />
            <label><input name="position_required" type="checkbox" defaultChecked /> Posición obligatoria</label>
            <button className="button button-primary" type="submit" disabled={positionBusy}>{positionBusy ? "Creando…" : "Agregar posición"}</button>
          </form>
          {positionMessage ? <p className="form-message" role="status">{positionMessage}</p> : null}
        </section>
      ) : null}
    </>
  );
}
