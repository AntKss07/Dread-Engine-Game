"""Pydantic schema definitions for Dread Engine Scenarios."""

from typing import Any

from pydantic import BaseModel, Field


class Exit(BaseModel):
    """An exit leading from one location to another."""

    target: str
    direction: str  # e.g. "north", "doorway", "path"
    description: str = ""
    locked: bool = False
    lock_flag: str | None = None
    required_item: str | None = None
    locked_message: str | None = None


class Location(BaseModel):
    """A distinct room, chamber, or area in the game world."""

    id: str
    name: str
    description_seed: str
    exits: dict[str, Exit] = Field(default_factory=dict)  # direction or target -> Exit
    danger_level: int = Field(default=0, ge=0, le=10)


class Item(BaseModel):
    """An interactable object or tool."""

    id: str
    name: str
    description: str
    location: str | None = None  # None if starts in inventory or spawn-only
    usable_on: list[str] = Field(default_factory=list)  # target ids / tags / "self"
    tags: list[str] = Field(default_factory=list)
    consumable: bool = False
    grants_flag: str | None = None
    grants_sanity: int = 0
    grants_hp: int = 0


class Entity(BaseModel):
    """A supernatural presence, phantom, creature, or pursuer."""

    id: str
    name: str
    description: str
    behavior: str  # "stalker", "ambient", "guardian", "passive"
    appears_when: dict[str, Any] = Field(default_factory=dict)  # e.g. {"dread_gte": 5}
    acts_when: str = "dread_max"  # or specific condition
    attack_hp: int = 1
    attack_sanity: int = 15
    active_message: str = ""


class Clue(BaseModel):
    """A narrative revelation or crucial piece of lore."""

    id: str
    name: str
    text_hint: str
    location: str
    requires: str | None = None  # item or flag required to discover


class DreadTrigger(BaseModel):
    """Rule determining how dread increases automatically or conditionally."""

    event: str  # "turn", "examine_relic", "failed_check", "location_danger"
    delta: int = 1
    condition: dict[str, Any] = Field(default_factory=dict)


class SanityEvent(BaseModel):
    """Trigger causing sanity degradation or horror shock."""

    trigger: str  # e.g. "encounter_spirit", "read_journal", "enter_crypt"
    delta: int = -10
    message: str = ""


class Ending(BaseModel):
    """A terminal outcome for the scenario."""

    id: str
    title: str
    condition: dict[str, Any]  # e.g. {"assembled_ofrenda": True, "location": "courtyard"}
    text_seed: str
    is_win: bool = False


class Persona(BaseModel):
    """Stylistic and thematic guidelines for the LLM narrator."""

    tone: str
    vocabulary_cues: list[str] = Field(default_factory=list)
    forbidden_words: list[str] = Field(default_factory=list)
    lore_primer: str = ""


class Scenario(BaseModel):
    """Complete horror scenario bundle."""

    id: str
    title: str
    theme: str = "horror"
    intro: str
    start_location: str
    persona: Persona
    locations: dict[str, Location]
    items: dict[str, Item]
    entities: dict[str, Entity] = Field(default_factory=dict)
    clues: dict[str, Clue] = Field(default_factory=dict)
    dread_triggers: list[DreadTrigger] = Field(default_factory=list)
    sanity_events: list[SanityEvent] = Field(default_factory=list)
    endings: dict[str, Ending] = Field(default_factory=dict)
