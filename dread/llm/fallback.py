"""Robust offline fallback parser and template narrator."""

import re

from dread.engine.state import Action, Event, EventType, GameState, Verb
from dread.scenarios.schema import Scenario

VERB_SYNONYMS: dict[Verb, list[str]] = {
    Verb.LOOK: ["look", "see", "l", "survey", "view", "glance", "peer"],
    Verb.EXAMINE: ["examine", "inspect", "check", "read", "study", "search", "x"],
    Verb.GO: [
        "go",
        "walk",
        "move",
        "run",
        "head",
        "travel",
        "climb",
        "step",
        "enter",
        "leave",
        "n",
        "s",
        "e",
        "w",
        "north",
        "south",
        "east",
        "west",
        "up",
        "down",
    ],
    Verb.TAKE: ["take", "get", "grab", "pickup", "pick", "collect", "acquire"],
    Verb.DROP: ["drop", "discard", "putdown", "leave"],
    Verb.USE_ON: ["use", "apply", "ignite", "light", "unlock", "pour", "place", "burn"],
    Verb.USE: ["use", "apply", "ignite", "light", "eat", "drink", "consume"],
    Verb.TALK: ["talk", "speak", "ask", "whisper", "shout", "pray", "chant", "say"],
    Verb.HIDE: ["hide", "crouch", "duck", "conceal", "cover"],
    Verb.WAIT: ["wait", "listen", "z", "pause", "stay"],
    Verb.REST: ["rest", "sleep", "nap", "breathe"],
    Verb.INVENTORY: ["inventory", "inv", "i", "items", "bag", "backpack"],
    Verb.HELP: ["help", "commands", "h", "?"],
    Verb.SAVE: ["save"],
    Verb.QUIT: ["quit", "exit"],
}

DIRECTION_ABBREVIATIONS = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "u": "up",
    "d": "down",
}


def fallback_parse_action(raw_input: str) -> Action:
    """Deterministic keyword-based parser when LLM is unavailable or unconfident."""
    text = raw_input.strip()
    if not text:
        return Action(verb=Verb.LOOK, raw_input=raw_input, confidence=1.0)

    lower = text.lower()

    # Pre-clean multi-word verb phrases
    lower = re.sub(r"^pick\s+up\b", "take", lower)
    lower = re.sub(r"^put\s+down\b", "drop", lower)
    lower = re.sub(r"^look\s+at\b", "examine", lower)
    lower = re.sub(r"^look\s+around\b", "look", lower)
    lower = re.sub(r"^go\s+to\b", "go", lower)
    lower = re.sub(r"^talk\s+to\b", "talk", lower)
    lower = re.sub(r"^speak\s+to\b", "talk", lower)

    # Unicode aware word splitting
    words = lower.split()
    if not words:
        return Action(verb=Verb.LOOK, raw_input=raw_input, confidence=0.3)

    first_word = words[0].strip(".,!?:;\"'")

    # Check for direct single-word directions
    if first_word in DIRECTION_ABBREVIATIONS:
        return Action(
            verb=Verb.GO,
            target=DIRECTION_ABBREVIATIONS[first_word],
            raw_input=raw_input,
            confidence=1.0,
        )
    if first_word in ["north", "south", "east", "west", "up", "down"]:
        return Action(verb=Verb.GO, target=first_word, raw_input=raw_input, confidence=1.0)

    # Check for matching verbs
    matched_verb: Verb | None = None
    for verb, syns in VERB_SYNONYMS.items():
        if first_word in syns:
            matched_verb = verb
            break

    # If first word is "use" and contains "on" or "with"
    if matched_verb == Verb.USE_ON or matched_verb == Verb.USE:
        # Check pattern: use X on Y / use X with Y
        match = re.search(r"^(?:use|apply)\s+(.+?)\s+(?:on|with|in|to)\s+(.+)$", lower)
        if match:
            item_name = match.group(1).strip()
            target_name = match.group(2).strip()
            return Action(
                verb=Verb.USE_ON,
                target=target_name,
                instrument=item_name,
                raw_input=raw_input,
                confidence=0.9,
            )
        else:
            remaining = " ".join(words[1:]) if len(words) > 1 else None
            return Action(
                verb=Verb.USE,
                target=remaining,
                raw_input=raw_input,
                confidence=0.8 if remaining else 0.4,
            )

    if matched_verb:
        # Remaining words are target
        remaining = " ".join(words[1:]).strip() if len(words) > 1 else None
        # Clean articles: "the", "a", "an"
        if remaining:
            remaining = re.sub(r"^(the|a|an|at|to)\s+", "", remaining).strip()

        return Action(
            verb=matched_verb,
            target=remaining,
            raw_input=raw_input,
            confidence=0.85
            if remaining
            or matched_verb
            in (
                Verb.LOOK,
                Verb.WAIT,
                Verb.REST,
                Verb.HIDE,
                Verb.INVENTORY,
                Verb.HELP,
                Verb.SAVE,
                Verb.QUIT,
            )
            else 0.5,
        )

    # If no verb matched, try searching if any verb is present
    for verb, syns in VERB_SYNONYMS.items():
        for syn in syns:
            if syn in words:
                idx = words.index(syn)
                target = " ".join(words[idx + 1 :]) if idx + 1 < len(words) else None
                return Action(verb=verb, target=target, raw_input=raw_input, confidence=0.6)

    # Default fallback: unknown input
    return Action(verb=Verb.LOOK, target=text, raw_input=raw_input, confidence=0.2)


def fallback_narrate(
    events: list[Event],
    state: GameState,
    scenario: Scenario,
    hallucination_hints: list[str] | None = None,
) -> str:
    """Template-based atmospheric fallback narrator."""
    loc = scenario.locations.get(state.location_id)
    loc_name = loc.name if loc else state.location_id

    sentences: list[str] = []

    # Describe primary event
    for ev in events:
        if ev.is_hallucination:
            continue
        if ev.type == EventType.MOVED:
            dest_name = ev.payload.get("name", loc_name)
            sentences.append(f"You cross into {dest_name}.")
            if loc:
                sentences.append(loc.description_seed)
        elif ev.type == EventType.ITEM_TAKEN:
            sentences.append(f"You take the {ev.payload.get('item_name', 'item')} and secure it.")
        elif ev.type == EventType.ITEM_USED:
            sentences.append(ev.message)
        elif ev.type == EventType.CLUE_FOUND:
            sentences.append(f"A realization chills your blood: {ev.payload.get('clue_text', '')}")
        elif ev.type == EventType.ENTITY_ACTS:
            sentences.append(f"A horrifying presence strikes from the gloom! {ev.message}")
        elif ev.type == EventType.SANITY_LOSS:
            sentences.append("A cold tremor runs through your mind as reality wavers.")
        elif ev.type == EventType.HP_LOSS:
            sentences.append("Pain shoots through your limbs.")
        elif (
            ev.type == EventType.BLOCKED
            or ev.type == EventType.NOTHING_HAPPENS
            or ev.type == EventType.ENDING
        ):
            sentences.append(ev.message)

    if not sentences and loc:
        sentences.append(f"You find yourself in {loc.name}. {loc.description_seed}")

    # Add hallucination hint if present
    if hallucination_hints:
        for hint in hallucination_hints:
            sentences.append(hint)

    # Atmosphere sentence based on sanity
    if state.sanity < 15:
        sentences.append(
            "The walls seem to bend inward, whispering in a tongue you cannot quite decipher."
        )
    elif state.sanity < 40:
        sentences.append("A persistent dread pricks at the edge of your thoughts.")

    # Combine into 2-4 sentences
    res = " ".join(sentences[:4])
    return res
