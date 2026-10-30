"""Narration validator preventing game state leaks, invented items, and meta commentary."""

import re

from dread.engine.state import GameState
from dread.scenarios.schema import Scenario

FORBIDDEN_META_PATTERNS = [
    r"\bas an ai\b",
    r"\blanguage model\b",
    r"\bgame master\b",
    r"\broll a d\d+\b",
    r"\bhit points?\b",
    r"\bhp:\s*\d+\b",
    r"\bsanity:\s*\d+\b",
    r"\bdread:\s*\d+\b",
    r"\bstatus:\b",
    r"\bconfidence:\b",
]


class ValidationResult:
    """Result of validating LLM-generated narration prose."""

    def __init__(self, is_valid: bool, errors: list[str] | None = None):
        self.is_valid = is_valid
        self.errors = errors or []

    def __repr__(self) -> str:
        return f"ValidationResult(is_valid={self.is_valid}, errors={self.errors})"


class NarrationValidator:
    """Validates that narration strictly reflects verified game state and emits no spoilers."""

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        # Build comprehensive map of all items, exits, entities in the whole scenario
        self.all_items = {it.name.lower(): it.id for it in scenario.items.values()}
        self.all_entities = {ent.name.lower(): ent.id for ent in scenario.entities.values()}
        self.all_locations = {loc.name.lower(): loc.id for loc in scenario.locations.values()}

    def validate(
        self,
        narration: str,
        state: GameState,
        allowed_items: list[str],
        allowed_entities: list[str],
        allowed_exits: list[str],
        hallucination_hints: list[str] | None = None,
    ) -> ValidationResult:
        """Validate narration against active visible state."""
        errors: list[str] = []
        text = narration.strip()
        text_lower = text.lower()

        # 1. Length bounds
        words = text.split()
        if len(words) < 8:
            errors.append(f"Narration too brief ({len(words)} words, expected >= 8).")
        if len(words) > 350:
            errors.append(f"Narration too verbose ({len(words)} words, expected <= 350).")

        # 2. Meta text check
        for pattern in FORBIDDEN_META_PATTERNS:
            if re.search(pattern, text_lower):
                errors.append(f"Prohibited meta/AI phrase detected matching '{pattern}'.")

        # 3. Check for scenario leaks (unseen items mentioned)
        allowed_item_set = {name.lower() for name in allowed_items}
        for item_name in self.all_items:
            if len(item_name) > 3 and item_name in text_lower:
                if item_name not in allowed_item_set:
                    # Check if allowed in hallucination hint
                    if not self._in_hallucinations(item_name, hallucination_hints):
                        errors.append(f"Leaked unobtained/invisible item: '{item_name}'.")

        # 4. Check for scenario leaks (unseen entities mentioned)
        allowed_entity_set = {name.lower() for name in allowed_entities}
        for ent_name in self.all_entities:
            if len(ent_name) > 3 and ent_name in text_lower:
                if ent_name not in allowed_entity_set:
                    if not self._in_hallucinations(ent_name, hallucination_hints):
                        errors.append(f"Leaked unencountered entity: '{ent_name}'.")

        # 5. Check for scenario leaks (distant locations described as current)
        current_loc = self.scenario.locations.get(state.location_id)
        current_loc_name = current_loc.name.lower() if current_loc else ""
        allowed_loc_set = {current_loc_name}
        for exit_dir in allowed_exits:
            allowed_loc_set.add(exit_dir.lower())

        for loc_name in self.all_locations:
            if len(loc_name) > 4 and loc_name in text_lower:
                if loc_name not in allowed_loc_set:
                    # If mentioned in a context of travel or teleportation that didn't happen
                    if not any(
                        loc_name in e.lower() for e in allowed_exits
                    ) and not self._in_hallucinations(loc_name, hallucination_hints):
                        # Only flag if not an allowed exit
                        errors.append(f"Mentioned unvisited distant location: '{loc_name}'.")

        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors)

    def _in_hallucinations(self, term: str, hints: list[str] | None) -> bool:
        """Check if term appears inside an authorized hallucination hint."""
        if not hints:
            return False
        for hint in hints:
            if term in hint.lower():
                return True
        return False
