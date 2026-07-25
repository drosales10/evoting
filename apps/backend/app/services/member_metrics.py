"""Aggregate roster metrics and statutory voting eligibility (estatus vs tipo).

Tipos canónicos alineados al Capítulo I de los Estatutos S.V.I.F.:
Activo (Art. 6), Temporal (Art. 6 § único), Asociado (Art. 10),
Aspirante (Art. 13), Colectivo (Art. 16), Correspondiente (Art. 19),
Honorario (Art. 22).

Derecho a votar en elección de órganos (Art. 7h / 8h): Activo y Temporal
(mismos derechos). Fundador se trata como Activo (Art. 6). Asociado tiene
voz y voto en deliberaciones/comisiones, pero no el deber específico de
votar órganos de la Sociedad. Aspirante, Colectivo, Correspondiente y
Honorario intervienen con voz (sin voto electoral de órganos).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Categorías estatutarias de membresía (columna Tipo). Distintas del estatus ACTIVE/INACTIVE.
KNOWN_MEMBER_TYPES: tuple[str, ...] = (
    "Activo",
    "Temporal",
    "Asociado",
    "Aspirante",
    "Colectivo",
    "Correspondiente",
    "Honorario",
)

UNTITLED_MEMBER_TYPE = "Sin tipo"

# Tipos con derecho a voto en elección de órganos (casefold).
VOTING_MEMBER_TYPE_KEYS: frozenset[str] = frozenset(
    {
        "activo",
        "temporal",
        "fundador",
    }
)


def normalize_member_type_label(raw: str | None) -> str:
    text = (raw or "").strip()
    return text if text else UNTITLED_MEMBER_TYPE


def member_type_grants_vote(member_type: str | None) -> bool:
    """Return whether Tipo confers electoral vote for organ elections.

    Blank/null Tipo defaults to Activo (Art. 5: profesionales inscritos son
    miembros activos) so legacy padrón rows remain votable.
    """
    label = normalize_member_type_label(member_type)
    if label == UNTITLED_MEMBER_TYPE:
        return True
    return label.casefold() in VOTING_MEMBER_TYPE_KEYS


@dataclass(frozen=True, slots=True)
class VoterEligibilityDecision:
    eligible: bool
    reason: str


def evaluate_voter_eligibility(
    *,
    status: str,
    alive: bool | None,
    member_type: str | None,
) -> VoterEligibilityDecision:
    """Decide snapshot eligibility: ACTIVE + vivo + tipo con derecho a voto."""
    status_value = (status or "").strip().upper()
    type_label = normalize_member_type_label(member_type)
    type_ok = member_type_grants_vote(member_type)

    if status_value != "ACTIVE":
        return VoterEligibilityDecision(
            eligible=False,
            reason="Miembro INACTIVE",
        )
    if alive is False:
        return VoterEligibilityDecision(
            eligible=False,
            reason="Vivo marcado como 0",
        )
    if alive is not True:
        return VoterEligibilityDecision(
            eligible=False,
            reason="Vivo no confirmado",
        )
    if not type_ok:
        return VoterEligibilityDecision(
            eligible=False,
            reason=(
                f"Tipo '{type_label}' sin derecho a voto electoral "
                "(solo Activo/Temporal/Fundador)"
            ),
        )
    return VoterEligibilityDecision(
        eligible=True,
        reason=(
            f"Cumple: miembro ACTIVE, Vivo confirmado y Tipo '{type_label}' "
            "con derecho a voto"
        ),
    )


def build_member_type_counts(
    rows: Iterable[tuple[str | None, int]],
    *,
    known_types: Sequence[str] = KNOWN_MEMBER_TYPES,
) -> list[tuple[str, int]]:
    """Merge DB group-by rows into ordered (label, count) pairs.

    Always includes known types (even at 0). Unknown labels from data follow,
    sorted by descending count then name. Null/blank become \"Sin tipo\".
    Case variants of the same label are merged.
    """
    aggregates: dict[str, tuple[str, int]] = {}
    for raw, count in rows:
        label = normalize_member_type_label(raw)
        key = label.casefold()
        if key in aggregates:
            display, previous = aggregates[key]
            aggregates[key] = (display, previous + int(count))
        else:
            aggregates[key] = (label, int(count))

    result: list[tuple[str, int]] = []
    for known in known_types:
        key = known.casefold()
        if key in aggregates:
            _, count = aggregates.pop(key)
            result.append((known, count))
        else:
            result.append((known, 0))

    extras = sorted(
        aggregates.values(),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    result.extend(extras)
    return result
