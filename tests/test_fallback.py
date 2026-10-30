"""Tests for graceful degradation, offline keyword parser, and template narrator."""

from dread.engine.state import Event, EventType, GameState, Verb
from dread.llm.client import BaseLLMClient
from dread.llm.fallback import fallback_parse_action
from dread.llm.narrator import Narrator
from dread.llm.validator import NarrationValidator
from dread.scenarios.loader import load_scenario


class AlwaysFailingLLM(BaseLLMClient):
    """LLM client that simulates network connection timeouts and server drops."""

    def is_available(self) -> bool:
        return False

    def generate(self, prompt: str, system: str = "", json_schema=None, temperature=None) -> str:
        raise TimeoutError("Connection timed out after 15.0s (mock offline)")

    def stream(self, prompt: str, system: str = "", temperature=None):
        raise TimeoutError("Stream connection failed")


def test_keyword_fallback_parser_variants():
    """Verify keyword parser maps natural language variations accurately."""
    # Directions
    a1 = fallback_parse_action("n")
    assert a1.verb == Verb.GO and a1.target == "north"

    a2 = fallback_parse_action("walk north")
    assert a2.verb == Verb.GO and a2.target == "north"

    # Examination
    a3 = fallback_parse_action("inspect the silver altar")
    assert a3.verb == Verb.EXAMINE and "altar" in a3.target

    # Taking items
    a4 = fallback_parse_action("pick up the cempasúchil petals")
    assert a4.verb == Verb.TAKE and "cempasúchil petals" in a4.target

    # Compound Use
    a5 = fallback_parse_action("use iron key on crypt door")
    assert a5.verb == Verb.USE_ON
    assert a5.instrument == "iron key"
    assert a5.target == "crypt door"

    # Inventory & Help
    assert fallback_parse_action("i").verb == Verb.INVENTORY
    assert fallback_parse_action("?").verb == Verb.HELP


def test_keyword_fallback_garbage_input():
    """Verify keyword parser does not crash on arbitrary garbage or punctuation."""
    a = fallback_parse_action("!@#$%^&*()_+ 12345 ??!!")
    assert a.verb in (Verb.LOOK, Verb.HELP)
    assert a.confidence < 0.5


def test_narrator_graceful_degradation_on_unreachable_llm():
    """Narrator smoothly falls back to template prose when LLM times out."""
    scenario = load_scenario("the_last_ofrenda")
    validator = NarrationValidator(scenario)
    offline_client = AlwaysFailingLLM()

    narrator = Narrator(offline_client, validator)
    state = GameState(seed=1, location_id="courtyard")

    events = [
        Event(
            type=EventType.MOVED,
            message="You move to The Central Courtyard.",
            payload={"name": "The Central Courtyard"},
        ),
        Event(
            type=EventType.SANITY_LOSS,
            message="A cold chill settles in your chest.",
        ),
    ]

    prose = narrator.narrate(events, state, scenario)

    # Must produce valid fallback prose without crashing
    assert narrator.used_fallback is True
    assert "Central Courtyard" in prose
    assert len(prose.split()) >= 8
    assert len(narrator.last_rejections) > 0  # Rejections logged connection error
