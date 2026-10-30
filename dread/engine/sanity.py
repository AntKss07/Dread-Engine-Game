"""Sanity tracking, tier evaluation, and hallucination hints."""

from dread.engine.dice import DreadDice
from dread.engine.state import Event, EventType, GameState, SanityTier

HALLUCINATION_SEEDS = [
    "A fleeting shadow flits across the ceiling, shaped like outstretched arms.",
    "The air smells strongly of burnt sugar and wax, though nothing is burning.",
    "A distant grandfather clock chimes seven times in rapid succession.",
    "You swear a faint whisper murmured your name from behind a closed door.",
    "The portrait on the wall seems to be watching your fingers with weeping eyes.",
    "The floorboards beneath your boots feel soft, as if stepping on moist soil.",
    "A moth with skull-patterned wings brushes against your cheek and dissolves into vapor.",
    "A sudden draft carries the laughter of young children who aren't there.",
]


def evaluate_sanity_loss(
    state: GameState,
    delta: int,
    reason: str = "",
) -> list[Event]:
    """Apply sanity delta (negative for loss, positive for recovery) and return events."""
    events: list[Event] = []
    old_sanity = state.sanity
    state.sanity = min(100, max(0, state.sanity + delta))

    if delta < 0:
        events.append(
            Event(
                type=EventType.SANITY_LOSS,
                message=f"A chill grips your thoughts ({reason}) (-{abs(delta)} Sanity: {state.sanity}/100).",
                payload={
                    "loss": abs(delta),
                    "old": old_sanity,
                    "new": state.sanity,
                    "tier": state.sanity_tier.value,
                },
            )
        )
    elif delta > 0:
        events.append(
            Event(
                type=EventType.SANITY_GAIN,
                message=f"A momentary sense of grounding restores your focus (+{delta} Sanity: {state.sanity}/100).",
                payload={
                    "gain": delta,
                    "old": old_sanity,
                    "new": state.sanity,
                    "tier": state.sanity_tier.value,
                },
            )
        )

    return events


def check_hallucination(
    state: GameState,
    dice: DreadDice,
    allow_hallucinations: bool = True,
) -> tuple[list[str], list[Event]]:
    """Determine if a hallucination occurs based on the current sanity tier."""
    if not allow_hallucinations or state.sanity_tier == SanityTier.STABLE:
        return [], []

    # Probability based on tier
    threshold = 0
    if state.sanity_tier == SanityTier.UNEASY:
        threshold = 15  # 15% chance
    elif state.sanity_tier == SanityTier.UNRAVELING:
        threshold = 45  # 45% chance
    elif state.sanity_tier == SanityTier.BREAKING:
        threshold = 80  # 80% chance

    roll = dice.d20() * 5  # 5-100
    if roll <= threshold:
        hint = dice.choose(HALLUCINATION_SEEDS)
        event = Event(
            type=EventType.HALLUCINATION,
            message=f"[Hallucination: {hint}]",
            payload={"hint": hint, "tier": state.sanity_tier.value},
            is_hallucination=True,
        )
        return [hint], [event]

    return [], []
