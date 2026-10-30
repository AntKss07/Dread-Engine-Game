"""Evaluation and resolution of game endings."""

from typing import Any

from dread.engine.state import Event, EventType, GameState
from dread.scenarios.schema import Scenario


def evaluate_endings(state: GameState, scenario: Scenario) -> list[Event]:
    """Check if the player has met any game-ending condition."""
    if state.ended:
        return []

    events: list[Event] = []

    # 1. Physical death
    if state.hp <= 0:
        ending_id = "death_hp"
        state.ended = ending_id
        events.append(
            Event(
                type=EventType.ENDING,
                message="Your strength fails you. The cold darkness overtakes your mortal body.",
                payload={
                    "ending_id": ending_id,
                    "title": "Flesh Surrenders",
                    "is_win": False,
                    "reason": "hp_zero",
                },
            )
        )
        return events

    # 2. Total mental collapse
    if state.sanity <= 0:
        ending_id = "death_sanity"
        state.ended = ending_id
        events.append(
            Event(
                type=EventType.ENDING,
                message="Your mind shatters beyond recovery, wandering forever in the twilight realm of phantoms.",
                payload={
                    "ending_id": ending_id,
                    "title": "Mind Shattered",
                    "is_win": False,
                    "reason": "sanity_zero",
                },
            )
        )
        return events

    # 3. Scenario-defined endings
    for end_id, ending in scenario.endings.items():
        if _matches_condition(state, ending.condition):
            state.ended = end_id
            events.append(
                Event(
                    type=EventType.ENDING,
                    message=ending.text_seed,
                    payload={
                        "ending_id": end_id,
                        "title": ending.title,
                        "is_win": ending.is_win,
                        "condition": ending.condition,
                    },
                )
            )
            return events

    return events


def _matches_condition(state: GameState, condition: dict[str, Any]) -> bool:
    """Helper to check if all clauses in a condition dictionary are satisfied."""
    for key, expected in condition.items():
        if key == "location":
            if state.location_id != expected:
                return False
        elif key == "has_item":
            if isinstance(expected, list):
                if not all(item in state.inventory for item in expected):
                    return False
            elif expected not in state.inventory:
                return False
        elif key == "clues_count_gte":
            if len(state.clues_found) < expected:
                return False
        elif key.startswith("flag_"):
            flag_name = key[len("flag_") :]
            if state.flags.get(flag_name) != expected:
                return False
        elif key in state.flags:
            if state.flags.get(key) != expected:
                return False
        else:
            # Default lookup in flags
            if state.flags.get(key) != expected:
                return False
    return True
