"""Build local, fictional participants independently of source graph facts."""

import unicodedata

from ..utils.locale import t
from .zep_entity_reader import EntityNode, FilteredEntities

SCENARIO_PARTICIPANT_TYPE = "ScenarioParticipant"
MAX_PARTICIPANT_ROLES = 12
MAX_ROLE_LENGTH = 120


def _role_key(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def normalize_participant_roles(roles: object) -> list[str]:
    """Clean and bound the planner's optional list before saving it."""
    if not isinstance(roles, list):
        return []
    seen = set()
    result = []
    for role in roles:
        if not isinstance(role, str):
            continue
        name = " ".join(role.split())
        key = _role_key(name)
        if not key or len(name) > MAX_ROLE_LENGTH or key in seen:
            continue
        seen.add(key)
        result.append(name)
        if len(result) == MAX_PARTICIPANT_ROLES:
            break
    return result


def parse_manual_participant_roles(value: str) -> list[str]:
    names = [line.strip() for line in value.splitlines() if line.strip()]
    if len(names) > MAX_PARTICIPANT_ROLES or any(len(name) > MAX_ROLE_LENGTH for name in names):
        raise ValueError("Too many or overly long participant roles")
    return normalize_participant_roles(names)


def include_scenario_participants(
    filtered: FilteredEntities,
    roles: list[str],
    simulation_requirement: str,
    defined_entity_types: list[str] | None = None,
) -> FilteredEntities:
    """Use one ordered roster for profiles and the configuration that indexes them."""
    if defined_entity_types and SCENARIO_PARTICIPANT_TYPE not in defined_entity_types:
        return filtered

    seen = {_role_key(entity.name) for entity in filtered.entities}
    additions = []
    for name in normalize_participant_roles(roles):
        if _role_key(name) in seen:
            continue
        additions.append(EntityNode(
            uuid=f"scenario-participant-{len(additions) + 1}",
            name=name,
            labels=[SCENARIO_PARTICIPANT_TYPE],
            summary=(
                t("participants.roleContext", role=name)
                + "\n\n"
                + simulation_requirement[:2000]
            ),
            attributes={},
        ))
    if not additions:
        return filtered
    entities = [*filtered.entities, *additions]
    return FilteredEntities(
        entities=entities,
        entity_types=filtered.entity_types | {SCENARIO_PARTICIPANT_TYPE},
        total_count=filtered.total_count + len(additions),
        filtered_count=len(entities),
    )
