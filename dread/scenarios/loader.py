"""YAML scenario loader and validator."""

from pathlib import Path

import yaml

from dread.scenarios.schema import Scenario


def get_scenarios_dir() -> Path:
    """Return the absolute path to the scenarios directory."""
    # Check project root scenarios/ or package scenarios
    candidate = Path("scenarios").resolve()
    if candidate.is_dir():
        return candidate
    candidate = Path(__file__).resolve().parent.parent.parent / "scenarios"
    return candidate


def list_available_scenarios(scenarios_dir: Path | None = None) -> list[str]:
    """List scenario IDs/filenames available in the scenarios directory."""
    s_dir = scenarios_dir or get_scenarios_dir()
    if not s_dir.exists():
        return []
    return [p.stem for p in s_dir.glob("*.yaml")]


def load_scenario(scenario_identifier: str, scenarios_dir: Path | None = None) -> Scenario:
    """Load and validate a scenario by name or file path."""
    path = Path(scenario_identifier)
    if not path.is_file():
        s_dir = scenarios_dir or get_scenarios_dir()
        if not scenario_identifier.endswith(".yaml"):
            candidate = s_dir / f"{scenario_identifier}.yaml"
        else:
            candidate = s_dir / scenario_identifier

        if candidate.is_file():
            path = candidate
        else:
            raise FileNotFoundError(f"Scenario '{scenario_identifier}' not found in {s_dir}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    scenario = Scenario(**data)
    _validate_scenario_integrity(scenario)
    return scenario


def _validate_scenario_integrity(scenario: Scenario) -> None:
    """Validate referential integrity within the scenario."""
    if scenario.start_location not in scenario.locations:
        raise ValueError(
            f"Scenario '{scenario.id}' start_location '{scenario.start_location}' does not exist in locations."
        )

    for loc_id, loc in scenario.locations.items():
        for exit_dir, exit_info in loc.exits.items():
            if exit_info.target not in scenario.locations:
                raise ValueError(
                    f"Location '{loc_id}' exit '{exit_dir}' points to unknown target '{exit_info.target}'."
                )

    for item_id, item in scenario.items.items():
        if item.location and item.location not in scenario.locations:
            raise ValueError(f"Item '{item_id}' placed at nonexistent location '{item.location}'.")

    for clue_id, clue in scenario.clues.items():
        if clue.location not in scenario.locations:
            raise ValueError(f"Clue '{clue_id}' placed at nonexistent location '{clue.location}'.")
