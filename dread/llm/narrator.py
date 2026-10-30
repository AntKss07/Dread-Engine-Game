"""Atmospheric horror LLM narrator with streaming, validation retry, and template fallback."""

from collections.abc import Generator

from dread.engine.state import Event, GameState
from dread.llm.client import BaseLLMClient
from dread.llm.fallback import fallback_narrate
from dread.llm.prompts import build_narrator_system_prompt
from dread.llm.validator import NarrationValidator
from dread.scenarios.schema import Scenario


class Narrator:
    """Orchestrates LLM prose narration with strict validation and graceful fallback."""

    def __init__(self, llm_client: BaseLLMClient, validator: NarrationValidator):
        self.client = llm_client
        self.validator = validator
        self.recent_snippets: list[str] = []
        self.last_rejections: list[str] = []
        self.used_fallback: bool = False

    def narrate(
        self,
        events: list[Event],
        state: GameState,
        scenario: Scenario,
        hallucination_hints: list[str] | None = None,
    ) -> str:
        """Generate validated atmospheric prose narration for the latest turn events."""
        self.last_rejections = []
        self.used_fallback = False

        loc = scenario.locations.get(state.location_id)
        loc_name = loc.name if loc else state.location_id

        # Compile permitted items and exits currently visible
        allowed_items = [
            it.name for it in scenario.items.values() if it.location == state.location_id
        ]
        allowed_items.extend(
            [scenario.items[i].name for i in state.inventory if i in scenario.items]
        )

        allowed_entities = [
            ent.name
            for ent in scenario.entities.values()
            if ent.id in state.flags or state.dread >= 8
        ]
        allowed_exits = list(loc.exits.keys()) if loc else []

        system_prompt = build_narrator_system_prompt(
            persona_tone=scenario.persona.tone,
            vocabulary_cues=scenario.persona.vocabulary_cues,
            forbidden_words=scenario.persona.forbidden_words,
            lore_primer=scenario.persona.lore_primer,
            sanity_tier=state.sanity_tier.value,
        )

        event_summaries = [f"- {e.message}" for e in events]
        continuity_context = (
            "\n".join(self.recent_snippets[-3:]) if self.recent_snippets else "None"
        )

        user_prompt = f"""Current Turn Facts:
Location: {loc_name}
Permitted Visible Objects: {allowed_items}
Permitted Exits: {allowed_exits}
Permitted Entities: {allowed_entities}
Deterministic Events Emitted:
{chr(10).join(event_summaries)}

Authorized Hallucination Hints (if any): {hallucination_hints or "None"}

Recent Context (for continuity only):
{continuity_context}

Write 2 to 5 evocative, atmospheric sentences capturing these exact events in second-person present tense."""

        # Attempt 1: Generate prose
        candidate = ""
        try:
            candidate = self.client.generate(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.7,
            )
        except Exception as e:
            self.last_rejections.append(f"LLM connection error: {e}")

        # Validate candidate 1
        if candidate:
            val_result = self.validator.validate(
                narration=candidate,
                state=state,
                allowed_items=allowed_items,
                allowed_entities=allowed_entities,
                allowed_exits=allowed_exits,
                hallucination_hints=hallucination_hints,
            )
            if val_result.is_valid:
                self._record_snippet(candidate)
                return candidate
            else:
                self.last_rejections.extend(val_result.errors)

                # Attempt 2: Retry with corrective prompt listing violations
                corrective_prompt = f"""Your previous narration was rejected due to strict consistency violations:
{chr(10).join(f"- {err}" for err in val_result.errors)}

Original facts:
{chr(10).join(event_summaries)}
Permitted Visible Objects: {allowed_items}
Permitted Exits: {allowed_exits}

Please rewrite the narration, strictly eliminating all prohibited references and errors. Write 2-4 sentences."""
                try:
                    retry_candidate = self.client.generate(
                        prompt=corrective_prompt,
                        system=system_prompt,
                        temperature=0.5,
                    )
                    retry_val = self.validator.validate(
                        narration=retry_candidate,
                        state=state,
                        allowed_items=allowed_items,
                        allowed_entities=allowed_entities,
                        allowed_exits=allowed_exits,
                        hallucination_hints=hallucination_hints,
                    )
                    if retry_val.is_valid:
                        self._record_snippet(retry_candidate)
                        return retry_candidate
                    else:
                        self.last_rejections.extend(retry_val.errors)
                except Exception as retry_err:
                    self.last_rejections.append(f"LLM retry error: {retry_err}")

        # Fallback template narration
        self.used_fallback = True
        fb = fallback_narrate(
            events=events,
            state=state,
            scenario=scenario,
            hallucination_hints=hallucination_hints,
        )
        self._record_snippet(fb)
        return fb

    def stream_tokens(
        self,
        events: list[Event],
        state: GameState,
        scenario: Scenario,
        hallucination_hints: list[str] | None = None,
    ) -> Generator[str, None, None]:
        """Stream validated narration or yield full fallback if unavailable."""
        prose = self.narrate(
            events=events,
            state=state,
            scenario=scenario,
            hallucination_hints=hallucination_hints,
        )
        # Yield words with natural pacing for streaming presentation
        for word in prose.split(" "):
            yield word + " "

    def _record_snippet(self, text: str) -> None:
        """Keep last 3 snippets for local continuity."""
        self.recent_snippets.append(text)
        if len(self.recent_snippets) > 3:
            self.recent_snippets.pop(0)
