"""Automated tests for Textual TUI input submission and rendering."""

import pytest
from textual.widgets import Input

from dread.config import AppConfig
from dread.llm.client import MockLLM
from dread.scenarios.loader import load_scenario
from dread.ui.tui import DreadTUI


@pytest.mark.anyio
async def test_tui_turn_pipeline():
    """Verify player commands submit, resolve through rules, and render in TUI."""
    scenario = load_scenario("the_last_ofrenda")
    app = DreadTUI(scenario=scenario, config=AppConfig(), llm_client=MockLLM())

    async with app.run_test() as pilot:
        inp = app.query_one("#player-input", Input)

        # 1. Test HELP command
        inp.value = "HELP"
        await app.on_input_submitted(Input.Submitted(inp, "HELP"))
        await pilot.pause()
        assert len(app._narration_history) >= 2
        assert "Available actions:" in app._narration_history[-1]

        # 2. Test LOOK command
        inp.value = "look around"
        await app.on_input_submitted(Input.Submitted(inp, "look around"))
        await pilot.pause()
        assert app.state.turn == 1

        # 3. Test GO command
        inp.value = "go north"
        await app.on_input_submitted(Input.Submitted(inp, "go north"))
        await pilot.pause()
        assert app.state.turn == 2
        assert app.state.location_id == "courtyard"
