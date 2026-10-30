"""Tests for structured action parsing, confidence gating, and synonym resolution."""

import json

from dread.engine.state import GameState, Verb
from dread.llm.client import MockLLM
from dread.llm.parser import ActionParser
from dread.scenarios.loader import load_scenario


def test_parser_structured_success():
    """Verify structured JSON from LLM is correctly decoded into an Action."""
    scenario = load_scenario("the_last_ofrenda")
    state = GameState(seed=1, location_id="courtyard")

    mock_llm = MockLLM()
    mock_llm.set_next_responses(
        [
            json.dumps(
                {
                    "verb": "TAKE",
                    "target": "cempasúchil petals",
                    "instrument": None,
                    "confidence": 0.95,
                }
            )
        ]
    )

    parser = ActionParser(mock_llm)
    action, options = parser.parse("gather the marigolds", state, scenario)

    assert action.verb == Verb.TAKE
    assert action.target == "cempasúchil petals"
    assert action.confidence == 0.95
    assert options is None


def test_parser_low_confidence_clarification():
    """Verify low confidence produces disambiguation options."""
    scenario = load_scenario("the_last_ofrenda")
    state = GameState(seed=1, location_id="courtyard")

    mock_llm = MockLLM()
    mock_llm.set_next_responses(
        [
            json.dumps(
                {
                    "verb": "LOOK",
                    "target": "something weird",
                    "instrument": None,
                    "confidence": 0.35,  # Low confidence!
                }
            )
        ]
    )

    parser = ActionParser(mock_llm)
    action, options = parser.parse("asdfghjkl blurgh", state, scenario)

    assert action.confidence == 0.35
    assert options is not None
    assert len(options) <= 3
    assert any("look" in opt or "go" in opt for opt in options)


def test_parser_fallback_on_invalid_json():
    """Verify malformed JSON falls back gracefully to keyword parser."""
    scenario = load_scenario("the_last_ofrenda")
    state = GameState(seed=1, location_id="courtyard")

    mock_llm = MockLLM()
    mock_llm.set_next_responses(["NOT VALID JSON AT ALL {[["])

    parser = ActionParser(mock_llm)
    action, _ = parser.parse("go north", state, scenario)

    assert parser.used_fallback is True
    assert action.verb == Verb.GO
    assert action.target == "north"
