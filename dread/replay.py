"""Deterministic run recording and state replay engine."""

import json
from pathlib import Path
from typing import Any

from dread.engine.dice import DreadDice
from dread.engine.rules import resolve
from dread.engine.state import Action, GameState, Verb
from dread.scenarios.loader import load_scenario


def export_run_record(
    state: GameState,
    scenario_id: str,
    output_path: str | Path,
) -> Path:
    """Save run seed and parsed action sequence to JSON for deterministic replay."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    actions_data = []
    for turn in state.log:
        actions_data.append(
            {
                "turn": turn.turn,
                "verb": turn.action.verb.value,
                "target": turn.action.target,
                "instrument": turn.action.instrument,
                "raw_input": turn.action.raw_input,
                "confidence": turn.action.confidence,
            }
        )

    record = {
        "scenario_id": scenario_id,
        "seed": state.seed,
        "total_turns": state.turn,
        "ended": state.ended,
        "actions": actions_data,
        "expected_final_state": {
            "hp": state.hp,
            "sanity": state.sanity,
            "dread": state.dread,
            "location_id": state.location_id,
            "inventory": list(state.inventory),
            "clues_found": list(state.clues_found),
            "flags": dict(state.flags),
            "ended": state.ended,
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    return path


def replay_run(
    run_file_path: str | Path,
    verbose: bool = True,
) -> tuple[bool, GameState, dict[str, Any]]:
    """Replay a recorded run from a JSON file and assert identical state evolution."""
    path = Path(run_file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Run file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    scenario_id = data["scenario_id"]
    seed = data["seed"]
    actions_list = data["actions"]
    expected = data.get("expected_final_state", {})

    scenario = load_scenario(scenario_id)
    dice = DreadDice(seed)

    replayed_state = GameState(
        seed=seed,
        turn=0,
        location_id=scenario.start_location,
        hp=10,
        sanity=100,
        dread=0,
    )
    replayed_state.record_visit(scenario.start_location)

    if verbose:
        print(f"Replaying '{scenario.title}' (Seed: {seed}, Actions: {len(actions_list)})...")

    for act_data in actions_list:
        verb = Verb(act_data["verb"])
        action = Action(
            verb=verb,
            target=act_data.get("target"),
            instrument=act_data.get("instrument"),
            raw_input=act_data.get("raw_input", ""),
            confidence=float(act_data.get("confidence", 1.0)),
        )

        events = resolve(
            state=replayed_state,
            action=action,
            scenario=scenario,
            dice=dice,
            allow_hallucinations=True,
        )

        if verbose:
            print(
                f"  [Turn {replayed_state.turn}] {action.verb.value} {action.target or ''} -> {len(events)} events | HP:{replayed_state.hp} Sanity:{replayed_state.sanity} Dread:{replayed_state.dread}"
            )

    # Compare replayed final state to expected
    diffs: dict[str, Any] = {}
    if expected:
        for key, expected_val in expected.items():
            actual_val = getattr(replayed_state, key)
            if actual_val != expected_val:
                diffs[key] = {"expected": expected_val, "actual": actual_val}

    success = len(diffs) == 0
    if verbose:
        if success:
            print("Deterministic replay verified: 100% state match.")
        else:
            print(f"Replay divergence detected in fields: {list(diffs.keys())}")

    return success, replayed_state, diffs
