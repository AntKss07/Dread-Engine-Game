"""Comprehensive unit tests for Dread Engine core rules, dice, sanity, and dread clock."""

import pytest

from dread.engine.clock import advance_dread
from dread.engine.dice import DreadDice
from dread.engine.rules import resolve
from dread.engine.state import Action, EventType, GameState, SanityTier, Verb
from dread.scenarios.loader import load_scenario


@pytest.fixture
def ofrenda_scenario():
    return load_scenario("the_last_ofrenda")


@pytest.fixture
def initial_state(ofrenda_scenario):
    state = GameState(
        seed=12345,
        turn=0,
        location_id=ofrenda_scenario.start_location,
        hp=10,
        sanity=100,
        dread=0,
    )
    state.record_visit(ofrenda_scenario.start_location)
    return state


def test_dice_determinism():
    """Verify that identical seeds produce identical random sequences."""
    d1 = DreadDice(42)
    d2 = DreadDice(42)

    rolls1 = [d1.d20() for _ in range(50)]
    rolls2 = [d2.d20() for _ in range(50)]
    assert rolls1 == rolls2


def test_sanity_tiers():
    """Verify sanity tier boundaries."""
    state = GameState(seed=1, location_id="gate", sanity=100)
    assert state.sanity_tier == SanityTier.STABLE

    state.sanity = 70
    assert state.sanity_tier == SanityTier.STABLE

    state.sanity = 69
    assert state.sanity_tier == SanityTier.UNEASY

    state.sanity = 40
    assert state.sanity_tier == SanityTier.UNEASY

    state.sanity = 39
    assert state.sanity_tier == SanityTier.UNRAVELING

    state.sanity = 15
    assert state.sanity_tier == SanityTier.UNRAVELING

    state.sanity = 14
    assert state.sanity_tier == SanityTier.BREAKING

    state.sanity = 0
    assert state.sanity_tier == SanityTier.BREAKING


def test_dread_clock_and_entity_strike(ofrenda_scenario):
    """Verify dread clock advances and entity strikes at dread 10."""
    dice = DreadDice(100)
    state = GameState(seed=100, location_id="courtyard", hp=10, sanity=100, dread=8)

    # Advance +1 -> 9
    events1 = advance_dread(state, delta=1, scenario=ofrenda_scenario, dice=dice)
    assert state.dread == 9
    assert any(e.type == EventType.DREAD_ADVANCED for e in events1)
    assert not any(e.type == EventType.ENTITY_ACTS for e in events1)

    # Advance +1 -> 10 -> Entity strikes!
    events2 = advance_dread(state, delta=1, scenario=ofrenda_scenario, dice=dice)
    assert any(e.type == EventType.ENTITY_ACTS for e in events2)
    assert state.hp < 10
    assert state.sanity < 100
    # Dread recedes to 4
    assert state.dread == 4


def test_verb_look(ofrenda_scenario, initial_state):
    """LOOK action returns location details and visible objects."""
    dice = DreadDice(1)
    action = Action(verb=Verb.LOOK, raw_input="look")
    events = resolve(initial_state, action, ofrenda_scenario, dice)

    assert any(e.type == EventType.NOTHING_HAPPENS and "Gate" in e.message for e in events)
    assert initial_state.turn == 1


def test_verb_go_and_locks(ofrenda_scenario, initial_state):
    """GO moves to adjacent locations, respecting locked doors."""
    dice = DreadDice(1)

    # Move from gate to courtyard
    go_north = Action(verb=Verb.GO, target="north", raw_input="go north")
    events = resolve(initial_state, go_north, ofrenda_scenario, dice)
    assert initial_state.location_id == "courtyard"
    assert any(e.type == EventType.MOVED for e in events)

    # Move from courtyard to chapel
    go_chapel = Action(verb=Verb.GO, target="chapel", raw_input="go chapel")
    resolve(initial_state, go_chapel, ofrenda_scenario, dice)
    assert initial_state.location_id == "chapel"

    # Try to go down into locked crypt without key
    go_down = Action(verb=Verb.GO, target="down", raw_input="go down")
    down_events = resolve(initial_state, go_down, ofrenda_scenario, dice)
    assert initial_state.location_id == "chapel"  # Blocked!
    assert any(e.type == EventType.BLOCKED for e in down_events)

    # Give player key and try again
    initial_state.inventory.append("iron_key")
    unlocked_events = resolve(initial_state, go_down, ofrenda_scenario, dice)
    assert initial_state.location_id == "crypt"
    assert any(e.type == EventType.MOVED for e in unlocked_events)


def test_verb_take_drop_and_inventory(ofrenda_scenario, initial_state):
    """TAKE adds item to inventory, DROP returns it to room, INVENTORY lists items."""
    dice = DreadDice(1)
    # Move to garden
    initial_state.location_id = "garden"

    take_action = Action(verb=Verb.TAKE, target="marigolds", raw_input="take marigolds")
    events = resolve(initial_state, take_action, ofrenda_scenario, dice)
    assert "marigolds" in initial_state.inventory
    assert any(e.type == EventType.ITEM_TAKEN for e in events)

    # Inventory display
    inv_action = Action(verb=Verb.INVENTORY, raw_input="inventory")
    inv_events = resolve(initial_state, inv_action, ofrenda_scenario, dice)
    assert any(e.type == EventType.INVENTORY_DISPLAYED for e in inv_events)

    # Drop item
    drop_action = Action(verb=Verb.DROP, target="marigolds", raw_input="drop marigolds")
    drop_events = resolve(initial_state, drop_action, ofrenda_scenario, dice)
    assert "marigolds" not in initial_state.inventory
    assert any(e.type == EventType.ITEM_DROPPED for e in drop_events)


def test_clue_discovery(ofrenda_scenario, initial_state):
    """EXAMINE on a clue discovers it and records in clues_found."""
    dice = DreadDice(1)
    initial_state.location_id = "study"

    examine_clue = Action(
        verb=Verb.EXAMINE, target="the three tiers of the ofrenda", raw_input="examine tiers"
    )
    events = resolve(initial_state, examine_clue, ofrenda_scenario, dice)
    assert "clue_altar_levels" in initial_state.clues_found
    assert any(e.type == EventType.CLUE_FOUND for e in events)


def test_full_winning_conditions(ofrenda_scenario, initial_state):
    """Placing all 5 ofrenda offerings and speaking remembrance triggers victory ending."""
    dice = DreadDice(1)
    initial_state.location_id = "courtyard"

    # Assemble offerings
    initial_state.flags["placed_photo"] = True
    initial_state.flags["placed_candle"] = True
    initial_state.flags["placed_marigolds"] = True
    initial_state.flags["placed_bread"] = True
    initial_state.flags["placed_water"] = True

    # Speak remembrance
    talk_action = Action(verb=Verb.TALK, target="remembrance", raw_input="speak remembrance")
    events = resolve(initial_state, talk_action, ofrenda_scenario, dice)

    assert initial_state.ended == "ending_reunion"
    assert any(e.type == EventType.ENDING and e.payload.get("is_win") is True for e in events)
