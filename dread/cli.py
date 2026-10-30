"""Command-line interface (CLI) for Dread Engine."""

import argparse
import random
import sys

from dread import __version__
from dread.config import load_config
from dread.llm.client import MockLLM, create_llm_client
from dread.replay import replay_run
from dread.scenarios.loader import list_available_scenarios, load_scenario
from dread.ui.tui import DreadTUI


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="dread",
        description="Dread Engine: Deterministic Solo Horror Text Game powered by Local LLMs",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: play
    play_parser = subparsers.add_parser("play", help="Launch a new interactive game session")
    play_parser.add_argument(
        "--scenario",
        "-s",
        type=str,
        default=None,
        help="Scenario ID or YAML path (default from config: the_last_ofrenda)",
    )
    play_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for deterministic dice and state evolution",
    )
    play_parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Override local LLM model name (e.g. qwen2.5:7b-instruct, qwen3:4b)",
    )
    play_parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with MockLLM for headless testing and instant offline play",
    )
    play_parser.add_argument(
        "--voice",
        action="store_true",
        help="Enable optional Piper TTS narration (P2 feature flag)",
    )

    # Command: replay
    replay_parser = subparsers.add_parser("replay", help="Replay a previously recorded run file")
    replay_parser.add_argument("run_file", type=str, help="Path to run record JSON file")

    # Command: scenarios
    subparsers.add_parser("scenarios", help="List all available scenario modules")

    # Command: version
    subparsers.add_parser("version", help="Display engine version")

    args = parser.parse_args()

    if args.command == "version":
        print(f"Dread Engine v{__version__}")
        sys.exit(0)

    if args.command == "scenarios":
        scenarios = list_available_scenarios()
        print("Available Dread Engine Scenarios:")
        for s in sorted(scenarios):
            print(f"  • {s}")
        sys.exit(0)

    if args.command == "replay":
        try:
            success, state, diffs = replay_run(args.run_file, verbose=True)
            if success:
                print(
                    f"\nReplay completed successfully. Final turn: {state.turn}, Ended: {state.ended}"
                )
                sys.exit(0)
            else:
                print(f"\nReplay failed due to state discrepancies: {diffs}")
                sys.exit(1)
        except Exception as e:
            print(f"Error executing replay: {e}", file=sys.stderr)
            sys.exit(1)

    # Default command: play
    if args.command == "play" or args.command is None:
        config = load_config()

        scenario_name = getattr(args, "scenario", None) or config.default_scenario
        seed = getattr(args, "seed", None)
        if seed is None:
            seed = random.randint(1000, 999999)

        if getattr(args, "model", None):
            config.model = args.model
        if getattr(args, "voice", False):
            config.voice_enabled = True

        try:
            scenario = load_scenario(scenario_name)
        except Exception as e:
            print(f"Error loading scenario '{scenario_name}': {e}", file=sys.stderr)
            sys.exit(1)

        llm_client = MockLLM() if getattr(args, "mock", False) else create_llm_client(config)

        app = DreadTUI(
            scenario=scenario,
            config=config,
            llm_client=llm_client,
            seed=seed,
        )
        app.run()


if __name__ == "__main__":
    main()
