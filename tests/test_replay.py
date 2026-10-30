"""Tests for deterministic replay reproducibility."""

import tempfile
from pathlib import Path

from dread.engine.dice import DreadDice
from dread.engine.rules import resolve
from dread.engine.state import Action, GameState, Verb
from dread.replay import export_run_record, replay_run
from dread.scenarios.loader import load_scenario


def test_deterministic_replay_equality():
    """Verify that exporting and replaying a session reproduces identical state."""
    scenario = load_scenario("the_last_ofrenda")
    seed = 999
    dice = DreadDice(seed)

    state = GameState(
        seed=seed,
        turn=0,
        location_id=scenario.start_location,
        hp=10,
        sanity=100,
        dread=0,
    )
    state.record_visit(scenario.start_location)

    scripted_actions = [
        Action(verb=Verb.LOOK, raw_input="look"),
        Action(verb=Verb.GO, target="north", raw_input="go north"),
        Action(verb=Verb.GO, target="east", raw_input="go east"),
        Action(verb=Verb.TAKE, target="marigolds", raw_input="take marigolds"),
        Action(verb=Verb.TAKE, target="iron_key", raw_input="take iron_key"),
        Action(verb=Verb.GO, target="west", raw_input="go west"),
        Action(verb=Verb.WAIT, raw_input="wait"),
        Action(verb=Verb.HIDE, raw_input="hide"),
    ]

    for action in scripted_actions:
        events = resolve(state, action, scenario, dice, allow_hallucinations=True)
        # Store in log
        from dread.engine.state import TurnRecord

        state.log.append(
            TurnRecord(
                turn=state.turn,
                raw_input=action.raw_input,
                action=action,
                events=events,
                dread=state.dread,
                sanity=state.sanity,
                hp=state.hp,
                location_id=state.location_id,
            )
        )

    # Save to tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        run_file = Path(tmpdir) / "test_run.json"
        export_run_record(state, scenario.id, run_file)

        # Replay
        success, replayed_state, diffs = replay_run(run_file, verbose=False)

        assert success is True
        assert len(diffs) == 0
        assert replayed_state.turn == state.turn
        assert replayed_state.hp == state.hp
        assert replayed_state.sanity == state.sanity
        assert replayed_state.dread == state.dread
        assert replayed_state.location_id == state.location_id
        assert replayed_state.inventory == state.inventory
        assert replayed_state.flags == state.flags
