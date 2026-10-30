"""Deterministic rules engine and action resolution for Dread Engine."""

from dread.engine.clock import advance_dread
from dread.engine.dice import DreadDice
from dread.engine.endings import evaluate_endings
from dread.engine.sanity import check_hallucination
from dread.engine.state import Action, Event, EventType, GameState, Verb
from dread.scenarios.schema import Scenario


def resolve(
    state: GameState,
    action: Action,
    scenario: Scenario,
    dice: DreadDice,
    allow_hallucinations: bool = True,
) -> list[Event]:
    """Resolve a player action deterministically against current game state and scenario rules."""
    if state.ended:
        return [
            Event(
                type=EventType.BLOCKED,
                message="The journey has already concluded. Start a new game or load a save.",
            )
        ]

    events: list[Event] = []
    current_loc = scenario.locations.get(state.location_id)
    if not current_loc:
        return [
            Event(
                type=EventType.BLOCKED,
                message=f"Corrupt state: current location '{state.location_id}' not found in scenario.",
            )
        ]

    # Handle system/meta actions
    if action.verb == Verb.HELP:
        events.append(
            Event(
                type=EventType.HELP_DISPLAYED,
                message="Available actions: LOOK, EXAMINE <obj>, GO <dir>, TAKE <item>, DROP <item>, USE <item> [ON <target>], TALK [TO <target>], HIDE, WAIT, REST, INVENTORY, SAVE, QUIT.",
            )
        )
        return events

    if action.verb == Verb.INVENTORY:
        items = [
            f"{scenario.items[item_id].name} ({scenario.items[item_id].description})"
            if item_id in scenario.items
            else item_id
            for item_id in state.inventory
        ]
        items_str = ", ".join(items) if items else "You carry nothing in your trembling hands."
        events.append(
            Event(
                type=EventType.INVENTORY_DISPLAYED,
                message=f"Inventory: {items_str}",
                payload={"inventory": list(state.inventory)},
            )
        )
        return events

    if action.verb == Verb.SAVE:
        events.append(
            Event(
                type=EventType.GAME_SAVED,
                message="Game state recorded to chronicle.",
                payload={"turn": state.turn},
            )
        )
        return events

    if action.verb == Verb.QUIT:
        state.ended = "quit"
        events.append(
            Event(
                type=EventType.ENDING,
                message="You step away from the shadows into the waking world.",
                payload={"ending_id": "quit", "title": "Left the Shadows", "is_win": False},
            )
        )
        return events

    # Resolve world-interacting verbs
    if action.verb == Verb.LOOK:
        events.extend(_resolve_look(state, scenario, current_loc))
    elif action.verb == Verb.EXAMINE:
        events.extend(_resolve_examine(state, action, scenario, current_loc))
    elif action.verb == Verb.GO:
        events.extend(_resolve_go(state, action, scenario, current_loc))
    elif action.verb == Verb.TAKE:
        events.extend(_resolve_take(state, action, scenario, current_loc))
    elif action.verb == Verb.DROP:
        events.extend(_resolve_drop(state, action, scenario, current_loc))
    elif action.verb in (Verb.USE, Verb.USE_ON):
        events.extend(_resolve_use(state, action, scenario, current_loc, dice))
    elif action.verb == Verb.TALK:
        events.extend(_resolve_talk(state, action, scenario, current_loc))
    elif action.verb == Verb.HIDE:
        events.extend(_resolve_hide(state, dice))
    elif action.verb == Verb.WAIT:
        events.append(
            Event(
                type=EventType.NOTHING_HAPPENS,
                message="You hold your breath in the quiet dark. Time slips away like ash.",
            )
        )
    elif action.verb == Verb.REST:
        events.extend(_resolve_rest(state, current_loc))
    else:
        events.append(
            Event(
                type=EventType.NOTHING_HAPPENS,
                message="You hesitate, uncertain of how to proceed.",
            )
        )

    # Post-action turn progression
    state.turn += 1

    # Dread progression (standard turn clock advance +1)
    dread_events = advance_dread(state, delta=1, scenario=scenario, dice=dice, source="turn")
    events.extend(dread_events)

    # Sanity hallucination check
    hints, hallu_events = check_hallucination(state, dice, allow_hallucinations)
    events.extend(hallu_events)

    # Endings check
    ending_events = evaluate_endings(state, scenario)
    events.extend(ending_events)

    return events


def _resolve_look(state: GameState, scenario: Scenario, loc) -> list[Event]:
    """Examine current environment."""
    items_here = [
        it.name
        for it in scenario.items.values()
        if it.location == loc.id and it.id not in state.inventory
    ]
    exits_here = [
        f"{direction} -> {exit_info.target}" for direction, exit_info in loc.exits.items()
    ]

    msg = f"You survey {loc.name}. {loc.description_seed}"
    if items_here:
        msg += f" Visible objects: {', '.join(items_here)}."
    if exits_here:
        msg += f" Exits: {', '.join(exits_here)}."

    return [
        Event(
            type=EventType.NOTHING_HAPPENS,
            message=msg,
            payload={
                "location_id": loc.id,
                "location_name": loc.name,
                "items": items_here,
                "exits": list(loc.exits.keys()),
            },
        )
    ]


def _resolve_examine(
    state: GameState,
    action: Action,
    scenario: Scenario,
    loc,
) -> list[Event]:
    """Examine an object, entity, or environment feature."""
    target_raw = (action.target or "").strip().lower()
    if not target_raw:
        return _resolve_look(state, scenario, loc)

    # 1. Match inventory item
    for item_id in state.inventory:
        item = scenario.items.get(item_id)
        if item and (target_raw in item.name.lower() or target_raw in item.id.lower()):
            return [
                Event(
                    type=EventType.NOTHING_HAPPENS,
                    message=f"You inspect the {item.name}: {item.description}",
                    payload={"item_id": item.id},
                )
            ]

    # 2. Match item in room
    for item in scenario.items.values():
        if item.location == loc.id and (
            target_raw in item.name.lower() or target_raw in item.id.lower()
        ):
            return [
                Event(
                    type=EventType.NOTHING_HAPPENS,
                    message=f"You look closely at the {item.name}: {item.description}",
                    payload={"item_id": item.id},
                )
            ]

    # 3. Match clue
    for clue in scenario.clues.values():
        if clue.location == loc.id and (
            target_raw in clue.name.lower() or target_raw in clue.id.lower()
        ):
            # Check requirements
            if (
                clue.requires
                and clue.requires not in state.inventory
                and not state.flags.get(clue.requires)
            ):
                return [
                    Event(
                        type=EventType.BLOCKED,
                        message="There seems to be something obscured here, but you lack what is needed to decipher it.",
                    )
                ]
            if clue.id not in state.clues_found:
                state.clues_found.append(clue.id)
            return [
                Event(
                    type=EventType.CLUE_FOUND,
                    message=f"A revelation clicks into place: {clue.text_hint}",
                    payload={"clue_id": clue.id, "clue_text": clue.text_hint},
                )
            ]

    # 4. Match entity
    for entity in scenario.entities.values():
        if target_raw in entity.name.lower() or target_raw in entity.id.lower():
            state.sanity = max(0, state.sanity - 5)
            return [
                Event(
                    type=EventType.SANITY_LOSS,
                    message=f"Gazing upon {entity.name} makes your heart hammer in terror (-5 Sanity). {entity.description}",
                    payload={"entity_id": entity.id, "loss": 5},
                )
            ]

    return [
        Event(
            type=EventType.NOTHING_HAPPENS,
            message=f"You study '{action.target}', but find nothing extraordinary beyond the gloom.",
        )
    ]


def _resolve_go(
    state: GameState,
    action: Action,
    scenario: Scenario,
    loc,
) -> list[Event]:
    """Move to another location through an exit."""
    target_raw = (action.target or "").strip().lower()
    if not target_raw:
        return [
            Event(
                type=EventType.BLOCKED,
                message="Specify a direction or destination to go towards.",
            )
        ]

    # Find matching exit by direction key or target id
    matched_exit = None
    for direction, exit_info in loc.exits.items():
        if (
            target_raw == direction.lower()
            or target_raw in exit_info.direction.lower()
            or target_raw == exit_info.target.lower()
            or (
                exit_info.target in scenario.locations
                and target_raw in scenario.locations[exit_info.target].name.lower()
            )
        ):
            matched_exit = exit_info
            break

    if not matched_exit:
        return [
            Event(
                type=EventType.BLOCKED,
                message=f"There is no clear path '{action.target}' from {loc.name}.",
            )
        ]

    # Check lock status
    if matched_exit.locked:
        is_unlocked = False
        if (
            matched_exit.lock_flag
            and state.flags.get(matched_exit.lock_flag)
            or matched_exit.required_item
            and matched_exit.required_item in state.inventory
        ):
            is_unlocked = True

        if not is_unlocked:
            lock_msg = (
                matched_exit.locked_message
                or f"The way to {matched_exit.target} is barred and locked."
            )
            return [
                Event(
                    type=EventType.BLOCKED,
                    message=lock_msg,
                    payload={
                        "target": matched_exit.target,
                        "required_item": matched_exit.required_item,
                    },
                )
            ]

    # Movement successful
    from_id = state.location_id
    state.location_id = matched_exit.target
    state.record_visit(matched_exit.target)
    dest = scenario.locations[matched_exit.target]

    return [
        Event(
            type=EventType.MOVED,
            message=f"You move to {dest.name}. {dest.description_seed}",
            payload={"from": from_id, "to": dest.id, "name": dest.name},
        )
    ]


def _resolve_take(
    state: GameState,
    action: Action,
    scenario: Scenario,
    loc,
) -> list[Event]:
    """Pick up an item from the current location."""
    target_raw = (action.target or "").strip().lower()
    if not target_raw:
        return [Event(type=EventType.BLOCKED, message="What would you like to take?")]

    for item in scenario.items.values():
        if item.location == loc.id and (
            target_raw in item.name.lower() or target_raw in item.id.lower()
        ):
            item.location = None  # in inventory
            state.inventory.append(item.id)
            return [
                Event(
                    type=EventType.ITEM_TAKEN,
                    message=f"You pick up the {item.name}.",
                    payload={"item_id": item.id, "item_name": item.name},
                )
            ]

    return [
        Event(
            type=EventType.BLOCKED,
            message=f"You search around, but cannot find '{action.target}' to pick up.",
        )
    ]


def _resolve_drop(
    state: GameState,
    action: Action,
    scenario: Scenario,
    loc,
) -> list[Event]:
    """Drop an item into the current room."""
    target_raw = (action.target or "").strip().lower()
    if not target_raw:
        return [Event(type=EventType.BLOCKED, message="What do you wish to drop?")]

    for item_id in list(state.inventory):
        item = scenario.items.get(item_id)
        if item and (target_raw in item.name.lower() or target_raw in item.id.lower()):
            state.inventory.remove(item_id)
            item.location = loc.id
            return [
                Event(
                    type=EventType.ITEM_DROPPED,
                    message=f"You place the {item.name} onto the floor.",
                    payload={"item_id": item.id, "location_id": loc.id},
                )
            ]

    return [
        Event(
            type=EventType.BLOCKED,
            message=f"You are not carrying '{action.target}'.",
        )
    ]


def _resolve_use(
    state: GameState,
    action: Action,
    scenario: Scenario,
    loc,
    dice: DreadDice,
) -> list[Event]:
    """Use an item on a target or the environment."""
    item_target_raw = (action.target or "").strip().lower()
    instr_target_raw = (action.instrument or "").strip().lower()

    # Determine which is the item and which is the target
    candidate_item_id: str | None = None
    applied_to: str = instr_target_raw or item_target_raw

    for item_id in state.inventory:
        item = scenario.items.get(item_id)
        if item:
            if item_target_raw in item.name.lower() or item_target_raw in item.id.lower():
                candidate_item_id = item_id
                applied_to = instr_target_raw
                break
            elif instr_target_raw and (
                instr_target_raw in item.name.lower() or instr_target_raw in item.id.lower()
            ):
                candidate_item_id = item_id
                applied_to = item_target_raw
                break

    if not candidate_item_id:
        return [
            Event(
                type=EventType.BLOCKED,
                message=f"You do not possess '{action.target or action.instrument}'.",
            )
        ]

    item = scenario.items[candidate_item_id]
    events: list[Event] = []

    # Check usability
    is_valid_use = False
    if (
        not item.usable_on
        or "any" in item.usable_on
        or any(u.lower() in applied_to for u in item.usable_on if applied_to)
        or "self" in item.usable_on
        and not applied_to
        or loc.id in item.usable_on
    ):
        is_valid_use = True

    if not is_valid_use and applied_to:
        return [
            Event(
                type=EventType.BLOCKED,
                message=f"Using the {item.name} on that yields no effect.",
            )
        ]

    # Effects of item
    if item.grants_flag:
        state.flags[item.grants_flag] = True

    if item.grants_hp > 0:
        state.hp = min(10, state.hp + item.grants_hp)
        events.append(
            Event(
                type=EventType.HP_GAIN,
                message=f"You feel vitality return (+{item.grants_hp} HP: {state.hp}/10).",
                payload={"gain": item.grants_hp, "hp": state.hp},
            )
        )

    if item.grants_sanity > 0:
        state.sanity = min(100, state.sanity + item.grants_sanity)
        events.append(
            Event(
                type=EventType.SANITY_GAIN,
                message=f"A warmth soothes your fraying nerves (+{item.grants_sanity} Sanity: {state.sanity}/100).",
                payload={"gain": item.grants_sanity, "sanity": state.sanity},
            )
        )

    # Check if unlocks any exit in current room
    for exit_info in loc.exits.values():
        if exit_info.locked and exit_info.required_item == item.id:
            exit_info.locked = False
            events.append(
                Event(
                    type=EventType.ITEM_USED,
                    message=f"You use the {item.name}. A lock clicks open, unbarring the path to {exit_info.target}!",
                    payload={"item_id": item.id, "unlocked": exit_info.target},
                )
            )

    if item.consumable:
        state.inventory.remove(item.id)

    events.insert(
        0,
        Event(
            type=EventType.ITEM_USED,
            message=f"You make use of the {item.name}.",
            payload={"item_id": item.id, "applied_to": applied_to},
        ),
    )
    return events


def _resolve_talk(
    state: GameState,
    action: Action,
    scenario: Scenario,
    loc,
) -> list[Event]:
    """Commune or speak aloud."""
    target_raw = (action.target or "").strip().lower()

    # Check entities
    for entity in scenario.entities.values():
        if target_raw in entity.name.lower() or target_raw in entity.id.lower():
            state.flags[f"spoken_to_{entity.id}"] = True
            return [
                Event(
                    type=EventType.ENTITY_ACTS,
                    message=f"You speak toward {entity.name}. An icy murmur answers from the void: '{entity.description}'.",
                    payload={"entity_id": entity.id},
                )
            ]

    # Speaking in ofrenda courtyard / shrine
    if (
        "altar" in target_raw
        or "remembrance" in target_raw
        or "ofrenda" in target_raw
        or loc.id == "courtyard"
    ):
        state.flags["spoken_remembrance"] = True
        return [
            Event(
                type=EventType.NOTHING_HAPPENS,
                message="You speak words of love and remembrance into the quiet air. The cempasúchil petals tremble softly.",
                payload={"flag": "spoken_remembrance"},
            )
        ]

    return [
        Event(
            type=EventType.NOTHING_HAPPENS,
            message=f"Your voice echoes against the damp stone: '{action.raw_input}'. Only the silence replies.",
        )
    ]


def _resolve_hide(state: GameState, dice: DreadDice) -> list[Event]:
    """Attempt to conceal oneself in cover."""
    success, total, outcome = dice.skill_check(target=11)
    if success:
        state.dread = max(0, state.dread - 1)
        return [
            Event(
                type=EventType.NOTHING_HAPPENS,
                message="You slip into the deep shadows and regulate your breathing. The oppressive presence passes by.",
                payload={"dread": state.dread, "roll": total, "outcome": outcome},
            )
        ]
    else:
        state.sanity = max(0, state.sanity - 5)
        return [
            Event(
                type=EventType.SANITY_LOSS,
                message="You scramble for cover, but a scraping sound betrays your position. Shivers run down your spine.",
                payload={"loss": 5, "roll": total, "outcome": outcome},
            )
        ]


def _resolve_rest(state: GameState, loc) -> list[Event]:
    """Catch breath at the expense of time and dread."""
    events: list[Event] = []
    if loc.danger_level > 3:
        state.sanity = max(0, state.sanity - 5)
        events.append(
            Event(
                type=EventType.BLOCKED,
                message="It is too dangerous to rest here. Paranoia keeps your eyelids peeled.",
            )
        )
    else:
        state.hp = min(10, state.hp + 1)
        state.sanity = min(100, state.sanity + 10)
        events.append(
            Event(
                type=EventType.HP_GAIN,
                message="You pause and gather your strength (+1 HP, +10 Sanity).",
                payload={"hp": state.hp, "sanity": state.sanity},
            )
        )
    return events
