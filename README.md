# 🕯️ Dread Engine

> **A deterministic solo horror text engine where a local open-weight LLM acts as game master, but never owns game state.**

Built for the **Hacktoberfest Open-Source AI Challenge (Week 3 — Spooky / Día de los Muertos)**.

---

## 💀 Pitch & Vision

In traditional AI-assisted games, the LLM hallucinates game state: items materialize out of thin air, locked doors vanish upon request, health bars drift arbitrarily, and tension dissolves into conversational mush.

**Dread Engine solves this through strict separation of church and state:**
1. **The Python Rules Engine is the sole arbiter of reality.** Coordinates, inventory, physical hit points (0–10), psychological sanity (0–100), dread clocks (0–10), and seeded dice are 100% deterministic code.
2. **The Local LLM has exactly two jobs:**
   - **Parser:** Converts freeform player text into typed actions from a fixed verb enum (`LOOK`, `EXAMINE`, `GO`, `TAKE`, `USE`, etc.).
   - **Narrator:** Transforms structured engine event logs into atmospheric, sensory prose.
3. **The Validator guards the player's perception:** Every narration token is checked against verified visible state. Any prose that invents unencountered entities, leaks unseen items, mentions locked chambers, or injects out-of-character AI meta commentary is **instantly rejected and rewritten**.
4. **100% Offline & Private:** Zero cloud APIs, zero tracking. Runs locally on your machine via Ollama or `llama.cpp-server`. If the local model is unavailable or stalls, the engine smoothly degrades to deterministic keyword parsing and atmospheric templates without ever crashing.

---

## 📸 Interface Preview

```text
┌─ [Dread Engine] ────────────────────────────────────────────────────────────────────────┐
│ Location: The Central Courtyard | HP: [♥♥♥♥♥♥♥♡♡♡] (7/10) | Sanity: [85%] (STABLE)       │
│ Dread: [💀💀💀💀······] (4/10) | Turn: 12 | ● LOCAL LLM (qwen2.5:7b-instruct)           │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  > take cempasúchil petals                                                              │
│  Your fingers close around the velvety orange petals. Their pungent, earthy perfume      │
│  rises like incense into the cool night air, reminding you of Elena's quiet altar       │
│  at dusk. The courtyard fountain trickles softly in the shadows behind you.             │
│                                                                                         │
│  > examine altar                                                                        │
│  You approach the three-tiered wooden altar draped in papel picado. A hollow draft      │
│  whispers through the arches. A sense of quiet expectation fills the space, waiting     │
│  for the sacred offerings: the photo, the candle, the bread, the water, and petals.     │
│                                                                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ [ What will you do? (e.g. go north, take candle, examine altar)                       ] │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quickstart

### 1. Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) (recommended) or `llama.cpp-server`

Pull a compact instruct model (e.g. Qwen 2.5 7B, Qwen 3 4B, or Gemma 2 9B):
```bash
ollama pull qwen2.5:7b-instruct
```

### 2. Install
Clone the repository and install in editable mode:
```bash
git clone https://github.com/srisudharsanank/dread-engine.git
cd "dread-engine"
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. Launch the Game
```bash
# Start default scenario (The Last Ofrenda)
dread play

# Or play instantly without a model using MockLLM
dread play --mock

# Specify an alternate local model
dread play --model qwen3:4b

# Run with a specific deterministic RNG seed
dread play --seed 1337
```

---

## 🎮 CLI Reference

| Command | Description |
| :--- | :--- |
| `dread play` | Launch interactive Textual TUI session |
| `dread play --scenario <name>` | Launch a specific scenario (`the_last_ofrenda`, `signal_lost`, `night_shift`) |
| `dread play --mock` | Run in offline mock mode (ideal for testing or low-spec hardware) |
| `dread replay <run.json>` | Deterministically replay a recorded run file and verify state equality |
| `dread scenarios` | List all installed YAML scenarios |
| `dread version` | Display engine version |

---

## ⚙️ Configuration (`config.yaml`)

Configuration is fully dynamic and never hardcoded:

```yaml
backend: "ollama"               # "ollama" or "llamacpp"
endpoint: "http://127.0.0.1:11434"
model: "qwen2.5:7b-instruct"    # Model identifier served by local backend
temperature: 0.7
timeout_seconds: 15.0
max_tokens: 300

difficulty: "normal"            # "story", "normal", "nightmare"
default_scenario: "the_last_ofrenda"
enable_hallucinations: true

voice_enabled: false            # Feature flag for optional Piper TTS
save_dir: "saves"
transcript_dir: "transcripts"
```

---

## 📜 Included Scenarios

1. **`the_last_ofrenda` (Featured / Día de los Muertos):**
   *A warm, melancholic gothic mystery set in an ancestral Mexican hacienda on November 1st. Gather the five sacred offerings (Elena's portrait, the copal veladora, golden cempasúchil petals, pan de muerto, and pure well water) and speak the words of remembrance to guide wandering spirits home.*
2. **`signal_lost` (Polar Isolation Horror):**
   *Trapped in an Antarctic research station during a -90 knot blizzard. Repair the backup generator and decode a low-frequency radio carrier signal emerging from deep beneath the ice shelf.*
3. **`night_shift` (Urban Museum Mystery):**
   *Your first graveyard shift as sole custodian of the Blackwood Museum of Antiquities. When the magnetic locks trip at midnight, Victorian mourning mannequins start shifting across the mezzanine.*

---

## 🔁 Deterministic Replays & Transcripts

Every session is seeded by a single RNG. When saving a session or completing a run:
- A `.json` run record preserves the seed and exact sequence of parsed actions.
- Running `dread replay saves/my_run.json` executes the rules engine from scratch, asserting that every event, HP change, sanity loss, and ending matches bit-for-bit.
- Running `ctrl+t` in the TUI exports a full publication-ready Markdown transcript including a **"What Was Real"** debrief that unmasks every psychological hallucination your character suffered.

---

## 🧪 Testing

Run the full automated test suite:
```bash
pytest -v
```

Run code formatting and linting:
```bash
ruff check .
```

Run model benchmarks comparing accuracy, rejection rates, latency, and tokens/sec:
```bash
python scripts/compare_models.py --models mock qwen2.5:7b-instruct --turns 5
```

---

## ⚖️ Honest Limitations

- **Hardware Latency:** Local 7B models on CPU will take 2–5 seconds per turn to parse and narrate. A GPU with 6GB+ VRAM or a quantized 3B–4B model (`qwen3:4b`) is recommended for conversational pacing.
- **Strict Vocabulary:** The parser accepts 15 core verbs. While natural synonyms are mapped smoothly, highly abstract narrative roleplay ("I write a poem about the moon") will fall back to `EXAMINE` or prompt a clarification choice.
- **Validator Retries:** When a model hallucinates an unseen item, a single retry is performed with corrective feedback. If the second attempt fails, the engine falls back to template narration to prevent turn stalls.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
