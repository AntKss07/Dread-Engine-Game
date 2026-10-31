This is a submission for the Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady

# Dread Engine: The AI Game Master That Never Owns Game State

## What I Built

**Dread Engine** is a deterministic, offline solo horror text game engine built from scratch in Python 3.12, where a local open-weight Large Language Model (served via Ollama or `llama.cpp`) acts as atmospheric game master but is **architecturally forbidden from mutating or owning game state**.

Every player coordinate, item pickup, door lock, sanity point (0–100), mortal hit point (0–10), seeded dice roll, and dread clock (0–10) belongs strictly to a deterministic Python rules engine. The LLM has exactly two jobs:
1. **Parser:** Translating messy, unconstrained player natural language into typed `Action` objects from a fixed 15-verb enum (`LOOK`, `EXAMINE`, `GO`, `TAKE`, `DROP`, `USE`, `USE_ON`, `TALK`, `HIDE`, `WAIT`, `REST`, `INVENTORY`, `HELP`, `SAVE`, `QUIT`).
2. **Narrator:** Converting the engine's structured event logs into sensory, second-person gothic prose.

Standing vigil between the narrator and the player's screen is an automated **Validator**. If the local model hallucinates an object not in the room, describes an unencountered phantom, leaks a locked room's secrets, or injects immersion-breaking meta text ("*As an AI, roll a d20*"), the validator rejects the output, logs the transgression, feeds corrective instructions back to the model for a second attempt, or gracefully yields to deterministic template narration.

The debut scenario, **"The Last Ofrenda"**, was designed specifically for Hacktoberfest Week 3's *Día de los Muertos* theme. The player explores the darkened Hacienda de la Luz on midnight of November 1st, assembling the five sacred elements of an authentic ofrenda (Elena's portrait, the copal veladora candle, golden cempasúchil petals, pan de muerto, and pure well water) and speaking a heartfelt remembrance to guide lingering ancestral memories into peace.

---

## Demo

Here is a live transcript excerpt recorded directly from a 24-turn victorious playthrough of *The Last Ofrenda* (RNG seed: `42`), demonstrating how the engine tracks facts while the narrator renders atmosphere:

```markdown
### Turn 1 — Location: `gate`
> Player Input: `look around`
Action Resolved: LOOK (Target: none, Instrument: none) [Conf: 1.00]

Narration:
You take a tentative step into the gloom. The damp stone floor chills your boots as shadows whisper around you.

Engine Facts & Events:
- NOTHING_HAPPENS: You survey The Wrought-Iron Gate. A high wrought-iron gate stands tall, shrouded in mist and creeping ivy. Cobblestones lead north toward the darkened courtyard. Exits: north -> courtyard.
- DREAD_ADVANCED: Dread deepens (0 -> 1/10). The atmosphere thickens.
Vitals: HP: 10 | Sanity: 100 | Dread: 1

---
### Turn 4 — Location: `garden`
> Player Input: `take marigolds`
Action Resolved: TAKE (Target: cempasúchil petals) [Conf: 0.95]

Narration:
Your fingers brush against the cold, dewy leaves as you gather the golden cempasúchil petals.
Their pungent, bittersweet aroma rises sharply into the midnight air, cutting through the damp chill.

Engine Facts & Events:
- ITEM_TAKEN: You pick up the cempasúchil petals.
- DREAD_ADVANCED: Dread deepens (3 -> 4/10). The atmosphere thickens.
Vitals: HP: 10 | Sanity: 100 | Dread: 4
```

### The "What Was Real" Debrief
When low sanity triggers hallucinations, the engine flags the event (`is_hallucination = True`). The validator permits the false sensory detail *only* for that turn, and upon completing the game, the veil is pierced:

```markdown
## What Was Real (The Veil Pierced)
During your ordeal, the creeping terror warped your senses. Here is what your mind invented:
- Turn 10: A distant grandfather clock chimes seven times in rapid succession. (Illusion caused by low sanity)
- Turn 16: You swear a faint whisper murmured your name from behind a closed door. (Illusion caused by low sanity)
```

---

## Code

The complete source code is released under the MIT License on GitHub:
- **Repository:** [Dread-Engine-Game](https://github.com/AntKss07/Dread-Engine-Game)
- **Key Modules:**
  - `dread/engine/rules.py` — Deterministic state transitions and action resolution
  - `dread/llm/validator.py` — Consistency validator preventing hallucinations and spoilers
  - `dread/llm/client.py` — Unified interface for Ollama, llama.cpp, and MockLLM
  - `dread/replay.py` — 100% bit-for-bit replay verifier from seed + action log
  - `dread/ui/tui.py` — Terminal user interface built with Textual

---

## How I Built It

### Architecture: Separating Facts from Prose
Most text adventures built with LLMs succumb to the "slop trap": players type *"I find a magical rocket launcher and blast through the wall"* and the model obliges because it treats storytelling as completion rather than simulation.

In Dread Engine, the LLM is physically decoupled from state:
```text
[Player Input] ──> [LLM Structured Parser] ──> [Deterministic Rules Engine]
                                                        │ (Emits Events)
                                                        ▼
[Player Display] <── [Validator Interceptor] <── [LLM Narrator]
```

### Real Validator Rejection Example
During integration testing with smaller models, we witnessed the exact failure mode that the Validator was designed to prevent.

When `qwen3:4b` was asked to narrate arriving at the Courtyard in Turn 2, it attempted to invent Elena's photograph lying on the pavement (which was actually locked away in the archivist's study):

```text
[VALIDATOR REJECTION LOG]
Candidate: "You step into the moonlit courtyard and spot the framed photograph of Elena resting beside the fountain."
Errors Detected:
- Leaked unobtained/invisible item: 'framed photograph of Elena'
Action: REJECTED candidate. Corrective prompt dispatched with error list.
```
On retry, the model corrected itself:
```text
Retry: "You step into the central courtyard. The dry stone fountain stands silent beneath arches draped in fading papel picado."
Result: APPROVED (0 errors).
```

### Real Model Benchmark Measurements
We benchmarked the exact same 3-turn playthrough script across models served locally via Ollama on an NVIDIA GPU workstation. These are real, measured numbers:

| Model | Parameter Size | Quantization | Turns | Parse Accuracy (%) | Validator Rejections | Rejection Rate (%) | Avg Latency (s) | Tokens/sec |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `MockLLM` | 0B | N/A | 3 | 33.3% | 0 | 0.0% | 0.00s | 186,424.5 |
| `qwen2.5:7b-instruct` | 7.6B | Q4_K_M | 3 | **100.0%** | **0** | **0.0%** | **11.53s** | **5.9** |
| `qwen3:4b` | 4.0B | Q4_K_M | 3 | **66.7%** | **3** | **100.0%** | **51.64s** | **0.6** |

#### Analysis of Findings:
- **`qwen2.5:7b-instruct` is the sweet spot:** It achieved flawless 100% intent parsing and generated zero validator rejections. Its steady-state latency was ~2.3 seconds per turn after a 29-second initial model load.
- **Smaller reasoning models (`qwen3:4b`) struggled with latency and strict boundaries:** Because `qwen3:4b` employs internal reasoning tokens (`<think>`), latency inflated to over 50 seconds per turn, and it suffered 3 validator rejections across 3 turns due to over-eager world-building.
- **Graceful degradation saved the game:** When the validator caught `qwen3:4b`'s embellishments, the retry loop and offline fallback ensured that gameplay never halted.

---

## Why Does Open Innovation Matter?

Open-weight models represent a seismic democratization of creative software. When your game relies on closed commercial APIs, your game has a silent expiration date:
- Pricing changes can make your game economically unviable.
- Model deprecations will alter the narrator's tone and invalidate prompts without warning.
- Remote telemetry violates player privacy in narrative-rich, personal games.
- Internet outages render single-player software useless.

By building on open-weight models served locally through Ollama, Dread Engine is completely self-sovereign. You can download the weights, disconnect your Ethernet cable, board a cabin in the mountains, and play indefinitely. The weights you run today will produce the exact same creative atmosphere ten years from now.

---

## My Agent Session

This entire engine was pair-programmed autonomously with Google Antigravity IDE and Gemini 3.8.

### What Went Smoothly:
1. **Schema-first design:** Defining the Pydantic v2 schemas (`GameState`, `Action`, `Event`, `Scenario`) early provided an unshakeable contract.
2. **Deterministic replay architecture:** Because random rolls were encapsulated in a single seeded `DreadDice` instance, reproducing an identical 24-turn game state from a JSON action log succeeded on the very first try.
3. **Automated test suite:** 20 test cases covering dice determinism, sanity tier transitions, locked doors, clue discovery, validator leak detection, and offline degradation ran in 0.35 seconds.

### The Struggles & Bugs Fixed:
1. **Unicode regex stripping in the keyword parser:** Initially, `re.findall(r"\b[a-zA-Z0-9_\-']+\b")` was used in the fallback parser. When testing with *"take cempasúchil petals"*, the accented `ú` caused the word to be chopped into `cempas` and `chil`, failing the item match. We refactored to unicode-aware word boundaries and phrasal verb normalization (`pick up` $\to$ `take`).
2. **Terminal buffering in background subprocesses:** During model benchmarking, Python's default stdout buffering withheld console output until the process exited. Ensuring proper logging and status queries kept execution visible.
3. **Ruff Modernization:** Python 3.11's `StrEnum` replaced legacy `(str, Enum)` tuples, bringing the codebase to zero lint errors across `ruff check .`.

---

## What I Learned

The biggest lesson from building Dread Engine is that **constraints liberate LLMs**.
When you give an LLM unconstrained control over a game world, it acts like an overeager improvisational actor who never says "no", destroying pacing and stakes.

When you restrict the model to being a sensory lens over an unyielding mathematical engine:
- The game feels genuinely terrifying because the danger is real: when the Dread Clock hits 10, the entity *will* strike, your HP *will* decrease, and the LLM cannot lie to protect you.
- Sanity loss becomes mechanical rather than aesthetic: when your sanity dips below 15, the engine deliberately feeds false sensory cues into the narrator's prompt, making the player doubt their own eyes.

---

## Prize Categories

- **Primary Track:** Hacktoberfest Open-Source AI Challenge (Week 3: Slow and Steady / Spooky / Día de los Muertos)
- **Local AI & Edge Computing:** 100% offline local inference via Ollama / llama.cpp
- **Deterministic Game Engineering:** Zero state hallucinations via Pydantic v2 rules verification and replayable seed logging
