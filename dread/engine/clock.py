"""Dread clock mechanics and supernatural entity activation."""

from dread.engine.dice import DreadDice
from dread.engine.state import Event, EventType, GameState
from dread.scenarios.schema import Scenario


def advance_dread(
    state: GameState,
    delta: int,
    scenario: Scenario,
    dice: DreadDice,
    source: str = "time",
) -> list[Event]:
    """Advance the dread clock by delta and evaluate threshold effects."""
    events: list[Event] = []
    old_dread = state.dread
    state.dread = min(10, max(0, state.dread + delta))

    if state.dread != old_dread:
        events.append(
            Event(
                type=EventType.DREAD_ADVANCED,
                message=f"Dread deepens ({old_dread} -> {state.dread}/10). The atmosphere thickens.",
                payload={"old": old_dread, "new": state.dread, "source": source},
            )
        )

    # If dread maxes out at 10, trigger supernatural entity intervention
    if state.dread >= 10:
        events.extend(trigger_entity_action(state, scenario, dice))

    return events


def trigger_entity_action(
    state: GameState,
    scenario: Scenario,
    dice: DreadDice,
) -> list[Event]:
    """When dread reaches 10, an entity in the scenario strikes or manifests."""
    events: list[Event] = []

    # Find candidate entities
    active_entity = None
    for ent in scenario.entities.values():
        if ent.acts_when == "dread_max" or not ent.appears_when:
            active_entity = ent
            break
        # Check condition if specified
        if "dread_gte" in ent.appears_when and state.dread >= ent.appears_when["dread_gte"]:
            active_entity = ent
            break

    if active_entity:
        # Entity attacks or manifests
        hp_damage = max(1, active_entity.attack_hp)
        sanity_damage = max(5, active_entity.attack_sanity)

        state.hp = max(0, state.hp - hp_damage)
        state.sanity = max(0, state.sanity - sanity_damage)

        events.append(
            Event(
                type=EventType.ENTITY_ACTS,
                message=(
                    f"A terrifying manifestation strikes! {active_entity.name} descends upon you. "
                    f"You suffer {hp_damage} injury and lose {sanity_damage} sanity."
                ),
                payload={
                    "entity_id": active_entity.id,
                    "entity_name": active_entity.name,
                    "hp_damage": hp_damage,
                    "sanity_damage": sanity_damage,
                },
            )
        )

        events.append(
            Event(
                type=EventType.HP_LOSS,
                message=f"You took {hp_damage} physical damage (HP: {state.hp}/10).",
                payload={"damage": hp_damage, "remaining": state.hp},
            )
        )
        events.append(
            Event(
                type=EventType.SANITY_LOSS,
                message=f"Your mind reels from the terror (-{sanity_damage} Sanity: {state.sanity}/100).",
                payload={"damage": sanity_damage, "remaining": state.sanity},
            )
        )

        # Reset clock partially so tension loops
        state.dread = 4
        events.append(
            Event(
                type=EventType.DREAD_ADVANCED,
                message="The entity recedes into the shadows for now (Dread resets to 4/10).",
                payload={"old": 10, "new": 4, "source": "entity_recede"},
            )
        )
    else:
        # Generic dread surge
        state.sanity = max(0, state.sanity - 10)
        state.dread = 5
        events.append(
            Event(
                type=EventType.SANITY_LOSS,
                message="The overwhelming dread reaches a fever pitch before subsiding into a cold silence.",
                payload={"damage": 10, "remaining": state.sanity},
            )
        )

    return events
