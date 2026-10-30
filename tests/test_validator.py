"""Unit tests for the NarrationValidator."""

from dread.engine.state import GameState
from dread.llm.validator import NarrationValidator
from dread.scenarios.loader import load_scenario


def test_validator_accepts_valid_prose():
    """Validator accepts compliant second-person prose referencing only visible facts."""
    scenario = load_scenario("the_last_ofrenda")
    validator = NarrationValidator(scenario)
    state = GameState(seed=1, location_id="courtyard")

    good_prose = (
        "You step into the cool air of the central courtyard. "
        "The arches loom quietly above you, draped with faded papel picado that rustles in the breeze. "
        "You look down at the stone floor and steady your breathing."
    )

    res = validator.validate(
        narration=good_prose,
        state=state,
        allowed_items=["three-tiered altar"],
        allowed_entities=[],
        allowed_exits=["north", "south", "east", "west"],
    )

    assert res.is_valid is True
    assert len(res.errors) == 0


def test_validator_catches_meta_phrases():
    """Validator rejects AI meta statements, dice rolls, or stats."""
    scenario = load_scenario("the_last_ofrenda")
    validator = NarrationValidator(scenario)
    state = GameState(seed=1, location_id="courtyard")

    meta_prose = "As an AI, I describe you rolling a d20. Your HP: 8 is dropping rapidly."
    res = validator.validate(
        narration=meta_prose,
        state=state,
        allowed_items=[],
        allowed_entities=[],
        allowed_exits=["north"],
    )

    assert res.is_valid is False
    assert any("Prohibited meta/AI phrase" in err for err in res.errors)


def test_validator_catches_unseen_item_leaks():
    """Validator rejects prose that mentions items located in other undiscovered rooms."""
    scenario = load_scenario("the_last_ofrenda")
    validator = NarrationValidator(scenario)
    state = GameState(seed=1, location_id="courtyard")

    # Elena's photograph is in the study, NOT in the courtyard!
    leaking_prose = (
        "You glance around the courtyard and spot the framed photograph of Elena lying across the pavers. "
        "The silver frame gleams under the moonlight."
    )

    res = validator.validate(
        narration=leaking_prose,
        state=state,
        allowed_items=["cempasúchil petals"],  # photo NOT allowed
        allowed_entities=[],
        allowed_exits=["north"],
    )

    assert res.is_valid is False
    assert any("Leaked unobtained/invisible item" in err for err in res.errors)


def test_validator_catches_unseen_entity_leaks():
    """Validator rejects unencountered entity mentions."""
    scenario = load_scenario("the_last_ofrenda")
    validator = NarrationValidator(scenario)
    state = GameState(seed=1, location_id="gate")

    entity_leaking_prose = (
        "At the iron gate, La Sombra watches you with hollow eyes, preparing to freeze your heart."
    )

    res = validator.validate(
        narration=entity_leaking_prose,
        state=state,
        allowed_items=[],
        allowed_entities=[],  # La Sombra not visible yet
        allowed_exits=["north"],
    )

    assert res.is_valid is False
    assert any("Leaked unencountered entity" in err for err in res.errors)


def test_validator_authorizes_hallucinations():
    """Validator permits details that match authorized hallucination hints."""
    scenario = load_scenario("the_last_ofrenda")
    validator = NarrationValidator(scenario)
    state = GameState(seed=1, location_id="gate")

    hint = "You swear La Sombra whispered your name from the gate."
    hallu_prose = (
        "You grip the gate tightly. You swear La Sombra whispered your name from the gate, "
        "making the hair on your arms stand on end."
    )

    res = validator.validate(
        narration=hallu_prose,
        state=state,
        allowed_items=[],
        allowed_entities=[],
        allowed_exits=["north"],
        hallucination_hints=[hint],
    )

    # Allowed because La Sombra was in the authorized hallucination hint!
    assert res.is_valid is True
