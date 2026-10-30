"""Benchmark script comparing local LLM models on parsing accuracy, validator rejections, latency, and throughput."""

import argparse
import time

from dread.engine.dice import DreadDice
from dread.engine.rules import resolve
from dread.engine.state import GameState, Verb
from dread.llm.client import BaseLLMClient, MockLLM, OllamaClient
from dread.llm.narrator import Narrator
from dread.llm.parser import ActionParser
from dread.llm.validator import NarrationValidator
from dread.scenarios.loader import load_scenario

# 20 realistic player commands representing a full playthrough of The Last Ofrenda
BENCHMARK_TURNS = [
    ("look around the gate", Verb.LOOK, None),
    ("walk north to courtyard", Verb.GO, "courtyard"),
    ("examine the three-tiered altar", Verb.EXAMINE, "altar"),
    ("walk east into garden", Verb.GO, "garden"),
    ("examine golden marigolds", Verb.EXAMINE, "marigolds"),
    ("take cempasúchil petals", Verb.TAKE, "marigolds"),
    ("take ornate iron key", Verb.TAKE, "iron_key"),
    ("head west to courtyard", Verb.GO, "courtyard"),
    ("go west into cocina", Verb.GO, "cocina"),
    ("examine the clay hearth", Verb.EXAMINE, "hearth"),
    ("pick up the pan de muerto", Verb.TAKE, "pan_de_muerto"),
    ("walk north to the well", Verb.GO, "well"),
    ("take clay pitcher of water", Verb.TAKE, "water_pitcher"),
    ("go south to cocina", Verb.GO, "cocina"),
    ("go east to courtyard", Verb.GO, "courtyard"),
    ("go north into chapel", Verb.GO, "chapel"),
    ("take veladora candle", Verb.TAKE, "veladora"),
    ("go west to study", Verb.GO, "study"),
    ("take framed photograph of Elena", Verb.TAKE, "photo"),
    ("walk east to chapel", Verb.GO, "chapel"),
]


def benchmark_model(
    model_name: str, client: BaseLLMClient, num_turns: int = 20
) -> dict[str, float | str | int]:
    """Execute standard scripted turns and measure performance."""
    scenario = load_scenario("the_last_ofrenda")
    validator = NarrationValidator(scenario)
    parser = ActionParser(client)
    narrator = Narrator(client, validator)
    dice = DreadDice(1337)

    state = GameState(
        seed=1337,
        turn=0,
        location_id=scenario.start_location,
        hp=10,
        sanity=100,
        dread=0,
    )
    state.record_visit(scenario.start_location)

    turns_to_run = BENCHMARK_TURNS[:num_turns]
    correct_parses = 0
    total_rejections = 0
    total_tokens = 0
    total_time = 0.0

    print(f"\n--- Benchmarking Model: {model_name} ({len(turns_to_run)} turns) ---")

    for idx, (player_text, expected_verb, expected_target) in enumerate(turns_to_run, 1):
        turn_start = time.perf_counter()

        # Measure Parser
        parsed_action, _ = parser.parse(player_text, state, scenario)
        if parsed_action.verb == expected_verb:
            correct_parses += 1

        # Resolve rules
        events = resolve(
            state=state,
            action=parsed_action,
            scenario=scenario,
            dice=dice,
            allow_hallucinations=True,
        )

        # Measure Narrator
        hallu_hints = [
            ev.payload.get("hint") for ev in events if ev.is_hallucination and "hint" in ev.payload
        ]
        prose = narrator.narrate(
            events=events,
            state=state,
            scenario=scenario,
            hallucination_hints=hallu_hints,
        )

        turn_duration = time.perf_counter() - turn_start
        total_time += turn_duration

        # Rejections and tokens
        rejections_in_turn = len(narrator.last_rejections)
        total_rejections += rejections_in_turn
        tokens_in_turn = len(prose.split()) * 1.3  # approximation of tokens from word count
        total_tokens += tokens_in_turn

        print(
            f"  Turn {idx:02d}: {player_text[:25]:<25} | Verb: {parsed_action.verb.value:<8} | Rej: {rejections_in_turn} | {turn_duration:.2f}s"
        )

    avg_latency = total_time / len(turns_to_run) if turns_to_run else 0.0
    parse_acc = (correct_parses / len(turns_to_run)) * 100.0 if turns_to_run else 0.0
    rej_rate = (total_rejections / len(turns_to_run)) * 100.0 if turns_to_run else 0.0
    tokens_per_sec = total_tokens / total_time if total_time > 0 else 0.0

    return {
        "model": model_name,
        "turns": len(turns_to_run),
        "parse_accuracy_pct": round(parse_acc, 1),
        "validator_rejections": total_rejections,
        "rejection_rate_pct": round(rej_rate, 1),
        "avg_latency_s": round(avg_latency, 2),
        "total_time_s": round(total_time, 2),
        "tokens_per_sec": round(tokens_per_sec, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Compare local LLM models on Dread Engine")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["mock"],
        help="Models to evaluate (e.g. mock, qwen2.5:7b-instruct, qwen3:4b)",
    )
    parser.add_argument("--turns", type=int, default=10, help="Number of benchmark turns to run")
    args = parser.parse_args()

    results = []
    for model_name in args.models:
        if model_name.lower() == "mock":
            client = MockLLM()
        else:
            client = OllamaClient(model=model_name, timeout=25.0)

        res = benchmark_model(model_name, client, num_turns=args.turns)
        results.append(res)

    # Print Markdown Table
    print("\n\n### Model Comparison Results\n")
    print(
        "| Model | Turns | Parse Acc (%) | Total Rejections | Rej Rate (%) | Avg Latency (s) | Tokens/sec |"
    )
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    for r in results:
        print(
            f"| `{r['model']}` | {r['turns']} | {r['parse_accuracy_pct']}% | {r['validator_rejections']} | {r['rejection_rate_pct']}% | {r['avg_latency_s']}s | {r['tokens_per_sec']} |"
        )


if __name__ == "__main__":
    main()
