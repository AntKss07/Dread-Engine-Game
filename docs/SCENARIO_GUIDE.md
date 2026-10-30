# Authoring Scenarios for Dread Engine

Scenarios in Dread Engine are pure declarative YAML files stored in the `scenarios/` directory.
Because Dread Engine separates narrative prose from rules resolution, scenario authors only need to declare **world topology, items, entities, clues, and endings**. The rules engine handles mechanics, and the local LLM brings the world to life.

---

## 1. Scenario Structure

A scenario file contains 9 key sections:

```yaml
id: "the_last_ofrenda"
title: "The Last Ofrenda"
theme: "Dia de los Muertos / Gothic Horror"
intro: "Narrative briefing displayed on game start..."
start_location: "gate"

persona:
  tone: "warm, melancholic, respectful"
  vocabulary_cues: ["cempasúchil", "copal", "veladora"]
  forbidden_words: ["zombie", "slasher"]
  lore_primer: "Context to guide the LLM's stylistic boundaries..."

locations: { ... }
items: { ... }
entities: { ... }
clues: { ... }
dread_triggers: [ ... ]
sanity_events: [ ... ]
endings: { ... }
```

---

## 2. Defining Locations & Exits

Each location represents a distinct area:

```yaml
locations:
  chapel:
    id: "chapel"
    name: "The Family Chapel"
    description_seed: "Stained-glass windows cast pale moonlit patterns over dusty pews."
    danger_level: 3
    exits:
      south:
        target: "courtyard"
        direction: "south"
        description: "South into the courtyard."
      down:
        target: "crypt"
        direction: "down"
        description: "A stone staircase descending into the crypt."
        locked: true
        required_item: "iron_key"
        locked_message: "A heavy iron padlock secures the crypt trapdoor."
```

### Exit Attributes:
- `target`: The `id` of the destination location (must exist in `locations`).
- `direction`: Natural direction keyword (e.g. `north`, `south`, `up`, `down`, `ladder`).
- `locked`: Boolean (`true` / `false`).
- `required_item`: Item ID required in inventory to unlock the path.
- `lock_flag`: Flag name in `state.flags` that unlocks the path.
- `locked_message`: Message displayed if the player attempts to enter while locked.

---

## 3. Defining Items & Interactive Objects

```yaml
items:
  marigolds:
    id: "marigolds"
    name: "cempasúchil petals"
    description: "A radiant handful of fresh golden cempasúchil blossoms."
    location: "garden"          # Location ID, or null if starts in inventory
    usable_on: ["altar", "courtyard", "self"]
    tags: ["ofrenda", "floral"]
    consumable: false
    grants_flag: "placed_marigolds"
    grants_sanity: 5
    grants_hp: 0
```

### Item Attributes:
- `usable_on`: List of valid targets (item names, location IDs, `"self"`, or `"any"`).
- `consumable`: If `true`, the item is discarded from inventory upon use.
- `grants_flag`: Sets a key in `state.flags` to `true`.
- `grants_sanity` / `grants_hp`: Restores vitals upon use.

---

## 4. Defining Entities (Threats & Presences)

```yaml
entities:
  ancestor_spirit:
    id: "ancestor_spirit"
    name: "La Sombra"
    description: "A sorrowful silhouette formed of swirling copal smoke and autumn shadows."
    behavior: "stalker"
    appears_when:
      dread_gte: 6
    acts_when: "dread_max"       # Triggers when dread hits 10
    attack_hp: 1
    attack_sanity: 15
    active_message: "La Sombra reaches out with cold fingers."
```

---

## 5. Defining Clues

Clues reward investigative gameplay (`EXAMINE`):

```yaml
clues:
  clue_altar_levels:
    id: "clue_altar_levels"
    name: "the three tiers of the ofrenda"
    text_hint: "The three tiers represent earth, the journey between realms, and the heavens."
    location: "study"
    requires: null              # Optional item or flag needed to inspect
```

---

## 6. Defining Endings

Endings can be victories, tragic losses, or narrative escapes:

```yaml
endings:
  ending_reunion:
    id: "ending_reunion"
    title: "The Golden Bridge of Petals"
    is_win: true
    condition:
      location: "courtyard"
      placed_photo: true
      placed_candle: true
      placed_marigolds: true
      placed_bread: true
      placed_water: true
      spoken_remembrance: true
    text_seed: "The veladora flares with a serene amber flame..."
```

---

## 7. Best Practices & Design Tips

1. **Cultural Authenticity:** For themes like *Día de los Muertos*, treat the departed with dignity and love. Avoid generic Hollywood horror clichés (zombies, curses, slashers).
2. **Deterministic Solvability:** Never design a scenario where the player can permanently lock themselves out of victory. Provide hints via `clues`.
3. **Pacing with the Dread Clock:** Keep room counts focused (6–10 locations). The Dread Clock advances by +1 each turn, meaning tension naturally cycles every 6–10 turns.
4. **Validation Integrity:** Use distinct, specific item and entity names. The engine's Validator automatically ensures unencountered objects are never leaked.
