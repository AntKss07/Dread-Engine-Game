"""Structured JSON LLM action parser with schema enforcement and clarification."""

import json
from typing import Any

from dread.engine.state import Action, GameState, Verb
from dread.llm.client import BaseLLMClient
from dread.llm.fallback import fallback_parse_action
from dread.llm.prompts import PARSER_SYSTEM_PROMPT
from dread.scenarios.schema import Scenario

ACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verb": {
            "type": "string",
            "enum": [v.value for v in Verb],
        },
        "target": {"type": ["string", "null"]},
        "instrument": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["verb", "confidence"],
}


class ActionParser:
    """Parses player freeform natural language text into a structured deterministic Action."""

    def __init__(self, llm_client: BaseLLMClient):
        self.client = llm_client
        self.used_fallback = False

    def parse(
        self,
        raw_input: str,
        state: GameState,
        scenario: Scenario,
    ) -> tuple[Action, list[str] | None]:
        """Parse raw input into (Action, disambiguation_options).

        Returns:
            (Action, None) on clean parse.
            (Action, [opt1, opt2, opt3]) if confidence is low and needs clarification.
        """
        self.used_fallback = False
        text = raw_input.strip()
        if not text:
            return Action(verb=Verb.LOOK, raw_input=raw_input, confidence=1.0), None

        # Build context info for prompt
        current_loc = scenario.locations.get(state.location_id)
        visible_items = [
            it.name for it in scenario.items.values() if it.location == state.location_id
        ]
        inventory_items = [
            scenario.items[item_id].name for item_id in state.inventory if item_id in scenario.items
        ]
        exits = list(current_loc.exits.keys()) if current_loc else []

        user_prompt = f"""Current Context:
Location: {current_loc.name if current_loc else state.location_id}
Available Exits/Directions: {exits}
Visible Items: {visible_items}
Inventory Held: {inventory_items}

Player Input: "{text}"

Parse into JSON matching the schema."""

        # Attempt LLM parse
        try:
            raw_response = self.client.generate(
                prompt=user_prompt,
                system=PARSER_SYSTEM_PROMPT,
                json_schema=ACTION_JSON_SCHEMA,
                temperature=0.1,
            )
            parsed_dict = json.loads(raw_response)
            verb_str = parsed_dict.get("verb", "LOOK").upper()
            verb = Verb(verb_str) if verb_str in Verb._value2member_map_ else Verb.LOOK
            target = parsed_dict.get("target")
            instrument = parsed_dict.get("instrument")
            confidence = float(parsed_dict.get("confidence", 0.9))

            action = Action(
                verb=verb,
                target=target,
                instrument=instrument,
                raw_input=raw_input,
                confidence=confidence,
            )

            # If confidence is low, build clarification suggestions
            if confidence < 0.5:
                options = self._build_clarifications(text, visible_items, exits)
                return action, options

            return action, None

        except Exception:
            # First retry or fallback to deterministic keyword parser
            self.used_fallback = True
            action = fallback_parse_action(raw_input)
            if action.confidence < 0.5:
                options = self._build_clarifications(text, visible_items, exits)
                return action, options
            return action, None

    def _build_clarifications(
        self,
        raw_text: str,
        visible_items: list[str],
        exits: list[str],
    ) -> list[str]:
        """Generate up to 3 candidate suggestions for ambiguous player input."""
        options: list[str] = []
        if exits:
            options.append(f"go {exits[0]}")
        if visible_items:
            options.append(f"examine {visible_items[0]}")
        options.append("look around")
        return options[:3]
