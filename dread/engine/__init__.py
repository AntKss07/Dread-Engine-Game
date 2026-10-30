"""Core game engine modules."""

from dread.engine.clock import advance_dread
from dread.engine.dice import DreadDice
from dread.engine.endings import evaluate_endings
from dread.engine.rules import resolve
from dread.engine.sanity import check_hallucination, evaluate_sanity_loss
from dread.engine.state import Action, Event, EventType, GameState, SanityTier, TurnRecord, Verb

__all__ = [
    "Action",
    "DreadDice",
    "Event",
    "EventType",
    "GameState",
    "SanityTier",
    "TurnRecord",
    "Verb",
    "advance_dread",
    "check_hallucination",
    "evaluate_endings",
    "evaluate_sanity_loss",
    "resolve",
]
