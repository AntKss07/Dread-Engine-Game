"""State definitions and Pydantic models for Dread Engine."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Verb(StrEnum):
    """Allowed player action verbs."""

    LOOK = "LOOK"
    EXAMINE = "EXAMINE"
    GO = "GO"
    TAKE = "TAKE"
    DROP = "DROP"
    USE = "USE"
    USE_ON = "USE_ON"
    TALK = "TALK"
    HIDE = "HIDE"
    WAIT = "WAIT"
    REST = "REST"
    INVENTORY = "INVENTORY"
    HELP = "HELP"
    SAVE = "SAVE"
    QUIT = "QUIT"


class EventType(StrEnum):
    """Event types produced by deterministic rules engine."""

    MOVED = "MOVED"
    ITEM_TAKEN = "ITEM_TAKEN"
    ITEM_DROPPED = "ITEM_DROPPED"
    ITEM_USED = "ITEM_USED"
    CLUE_FOUND = "CLUE_FOUND"
    SANITY_LOSS = "SANITY_LOSS"
    SANITY_GAIN = "SANITY_GAIN"
    HP_LOSS = "HP_LOSS"
    HP_GAIN = "HP_GAIN"
    ENTITY_APPEARS = "ENTITY_APPEARS"
    ENTITY_ACTS = "ENTITY_ACTS"
    DREAD_ADVANCED = "DREAD_ADVANCED"
    BLOCKED = "BLOCKED"
    NOTHING_HAPPENS = "NOTHING_HAPPENS"
    HALLUCINATION = "HALLUCINATION"
    ENDING = "ENDING"
    HELP_DISPLAYED = "HELP_DISPLAYED"
    INVENTORY_DISPLAYED = "INVENTORY_DISPLAYED"
    GAME_SAVED = "GAME_SAVED"


class SanityTier(StrEnum):
    """Player psychological state tiers."""

    STABLE = "stable"  # >= 70
    UNEASY = "uneasy"  # 40 - 69
    UNRAVELING = "unraveling"  # 15 - 39
    BREAKING = "breaking"  # < 15


class Action(BaseModel):
    """Structured action parsed from player input."""

    verb: Verb
    target: str | None = None
    instrument: str | None = None
    raw_input: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Event(BaseModel):
    """Atomic event emitted during turn resolution."""

    type: EventType
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    is_hallucination: bool = False


class TurnRecord(BaseModel):
    """Audit log of a completed turn."""

    turn: int
    raw_input: str
    action: Action
    events: list[Event]
    narration: str = ""
    dread: int
    sanity: int
    hp: int
    location_id: str
    validator_rejections: list[str] = Field(default_factory=list)


class GameState(BaseModel):
    """Full deterministic state of the active game session."""

    seed: int
    turn: int = 0
    location_id: str
    hp: int = Field(default=10, ge=0, le=10)
    sanity: int = Field(default=100, ge=0, le=100)
    inventory: list[str] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)
    clues_found: list[str] = Field(default_factory=list)
    dread: int = Field(default=0, ge=0, le=10)
    visited: list[str] = Field(default_factory=list)
    ended: str | None = None
    log: list[TurnRecord] = Field(default_factory=list)

    @property
    def sanity_tier(self) -> SanityTier:
        """Derive the current psychological tier from numerical sanity."""
        if self.sanity >= 70:
            return SanityTier.STABLE
        if self.sanity >= 40:
            return SanityTier.UNEASY
        if self.sanity >= 15:
            return SanityTier.UNRAVELING
        return SanityTier.BREAKING

    def record_visit(self, loc_id: str) -> None:
        """Mark a location as visited if not already present."""
        if loc_id not in self.visited:
            self.visited.append(loc_id)
