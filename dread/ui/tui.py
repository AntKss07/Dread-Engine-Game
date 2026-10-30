"""Textual-based Terminal User Interface (TUI) for Dread Engine."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Input, Label, Static

from dread.config import AppConfig
from dread.engine.dice import DreadDice
from dread.engine.rules import resolve
from dread.engine.state import Action, EventType, GameState, SanityTier, TurnRecord
from dread.llm.client import BaseLLMClient, create_llm_client
from dread.llm.narrator import Narrator
from dread.llm.parser import ActionParser
from dread.llm.validator import NarrationValidator
from dread.scenarios.schema import Scenario
from dread.ui.transcript import save_transcript


class StatusBar(Static):
    """Dynamic status bar showing HP, Sanity (with flicker), Dread Clock, and Fallback state."""

    def update_status(
        self,
        hp: int,
        sanity: int,
        sanity_tier: SanityTier,
        dread: int,
        location_name: str,
        turn: int,
        offline_fallback: bool,
    ) -> None:
        """Render updated status indicators."""
        hp_hearts = "♥" * hp + "♡" * (10 - hp)
        dread_skulls = "💀" * dread + "·" * (10 - dread)

        # Sanity tier color & flicker
        tier_style = {
            SanityTier.STABLE: "bold green",
            SanityTier.UNEASY: "bold yellow",
            SanityTier.UNRAVELING: "bold dark_orange",
            SanityTier.BREAKING: "bold red blink",
        }.get(sanity_tier, "white")

        fallback_badge = (
            "[reverse red] ⚠ OFFLINE FALLBACK [/reverse red] "
            if offline_fallback
            else "[green]● LOCAL LLM[/green] "
        )

        text = (
            f"[bold cyan]Location:[/bold cyan] {location_name} | "
            f"[bold red]HP:[/bold red] [{hp_hearts}] ({hp}/10) | "
            f"[bold yellow]Sanity:[/bold yellow] [{tier_style}]{sanity}% ({sanity_tier.value.upper()})[/{tier_style}] | "
            f"[bold magenta]Dread:[/bold magenta] [{dread_skulls}] ({dread}/10) | "
            f"Turn: {turn} | {fallback_badge}"
        )
        self.update(text)


class DreadTUI(App):
    """Main Textual application for Dread Engine."""

    CSS = """
    Screen {
        background: #0d0f12;
        color: #e2e8f0;
    }

    #header-container {
        dock: top;
        height: 3;
        background: #1a202c;
        border-bottom: heavy #4a5568;
        padding: 0 1;
    }

    #status-bar {
        height: 1;
        content-align: center middle;
    }

    #main-container {
        height: 1fr;
        padding: 1 2;
    }

    #narration-scroll {
        height: 1fr;
        border: round #2d3748;
        background: #141820;
        padding: 1 2;
    }

    #narration-text {
        color: #f7fafc;
    }

    #clarification-container {
        height: auto;
        padding: 0 1;
        margin: 1 0;
        display: none;
    }

    .option-btn {
        margin: 0 1;
        background: #2b6cb0;
        color: white;
    }

    #input-container {
        dock: bottom;
        height: 4;
        background: #1a202c;
        padding: 0 1;
        border-top: heavy #4a5568;
    }

    #player-input {
        background: #0f141c;
        border: tall #4a5568;
        color: #edf2f7;
    }

    #player-input:focus {
        border: tall #63b3ed;
    }

    #debug-drawer {
        dock: right;
        width: 38;
        background: #0a0d14;
        border-left: heavy #2d3748;
        padding: 1;
        display: none;
    }

    .debug-title {
        color: #ed8936;
        text-style: bold;
        border-bottom: solid #4a5568;
        margin-bottom: 1;
    }

    #debug-text {
        color: #a0aec0;
    }
    """

    BINDINGS = [
        Binding("ctrl+d", "toggle_debug", "Toggle Debug Logs"),
        Binding("ctrl+s", "save_game", "Save Game"),
        Binding("ctrl+t", "export_transcript", "Export Transcript"),
        Binding("ctrl+q", "quit_game", "Quit"),
    ]

    def __init__(
        self,
        scenario: Scenario,
        config: AppConfig,
        llm_client: BaseLLMClient | None = None,
        seed: int = 42,
    ):
        super().__init__()
        self.scenario = scenario
        self.config = config
        self.client = llm_client or create_llm_client(config)
        self.dice = DreadDice(seed)
        self.validator = NarrationValidator(scenario)
        self.parser = ActionParser(self.client)
        self.narrator = Narrator(self.client, self.validator)

        # Initialize GameState
        self.state = GameState(
            seed=seed,
            turn=0,
            location_id=scenario.start_location,
            hp=10,
            sanity=100,
            dread=0,
        )
        self.state.record_visit(scenario.start_location)
        self.offline_fallback_active = False
        self._narration_history: list[str] = []
        self._debug_history: list[str] = []

    def compose(self) -> ComposeResult:
        """Compose layout widgets."""
        with Container(id="header-container"):
            yield StatusBar(id="status-bar")

        with Horizontal(id="main-container"):
            with Vertical(id="content-panel"):
                with VerticalScroll(id="narration-scroll"):
                    yield Static(id="narration-text")

                with Horizontal(id="clarification-container"):
                    yield Label("Did you mean: ", id="clarification-label")
                    yield Button("", id="btn-opt-1", classes="option-btn")
                    yield Button("", id="btn-opt-2", classes="option-btn")
                    yield Button("", id="btn-opt-3", classes="option-btn")

            with VerticalScroll(id="debug-drawer"):
                yield Label("Audit & Validator Log", classes="debug-title")
                yield Static(id="debug-text")

        with Container(id="input-container"):
            yield Input(
                placeholder="What will you do? (e.g. look around, go north, examine altar...)",
                id="player-input",
            )

        yield Footer()

    def on_mount(self) -> None:
        """Initial render on app start."""
        self._update_status_display()
        intro_text = (
            f"[bold gold1]{self.scenario.title}[/bold gold1]\n"
            f"[italic #a0aec0]{self.scenario.intro}[/italic #a0aec0]\n\n"
            f"[bold #63b3ed]Location:[/bold #63b3ed] {self.scenario.locations[self.state.location_id].name}\n"
            f"{self.scenario.locations[self.state.location_id].description_seed}\n\n"
            "Type [bold]HELP[/bold] for permitted actions, or simply type your intention."
        )
        self._narration_history.append(intro_text)
        self.query_one("#narration-text", Static).update(intro_text)
        self.query_one("#player-input", Input).focus()

    def _update_status_display(self) -> None:
        """Refresh status bar values."""
        loc = self.scenario.locations.get(self.state.location_id)
        loc_name = loc.name if loc else self.state.location_id
        bar = self.query_one("#status-bar", StatusBar)
        bar.update_status(
            hp=self.state.hp,
            sanity=self.state.sanity,
            sanity_tier=self.state.sanity_tier,
            dread=self.state.dread,
            location_name=loc_name,
            turn=self.state.turn,
            offline_fallback=self.offline_fallback_active,
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Process player command on Enter."""
        raw_input = event.value.strip()
        if not raw_input:
            return

        input_widget = self.query_one("#player-input", Input)
        input_widget.value = ""

        # Hide any prior clarification buttons
        self._hide_clarifications()

        # Step 1: Parse
        action, options = self.parser.parse(raw_input, self.state, self.scenario)
        if options and action.confidence < 0.5:
            self._show_clarifications(options)
            return

        await self._process_turn(action, raw_input)

    async def _process_turn(self, action: Action, raw_input: str) -> None:
        """Resolve engine rules and generate narrated response."""
        # Step 2: Engine resolves action deterministically
        events = resolve(
            state=self.state,
            action=action,
            scenario=self.scenario,
            dice=self.dice,
            allow_hallucinations=self.config.enable_hallucinations,
        )

        # Collect hallucination hints if any
        hallu_hints = [
            ev.payload.get("hint") for ev in events if ev.is_hallucination and "hint" in ev.payload
        ]

        # Step 3: Narrate
        meta_events = [
            ev
            for ev in events
            if ev.type
            in (
                EventType.HELP_DISPLAYED,
                EventType.INVENTORY_DISPLAYED,
                EventType.GAME_SAVED,
            )
        ]
        if meta_events:
            narration = "\n".join(ev.message for ev in meta_events)
        else:
            narration = self.narrator.narrate(
                events=events,
                state=self.state,
                scenario=self.scenario,
                hallucination_hints=hallu_hints,
            )

        self.offline_fallback_active = self.parser.used_fallback or self.narrator.used_fallback

        # Step 4: Record Turn
        record = TurnRecord(
            turn=self.state.turn,
            raw_input=raw_input,
            action=action,
            events=events,
            narration=narration,
            dread=self.state.dread,
            sanity=self.state.sanity,
            hp=self.state.hp,
            location_id=self.state.location_id,
            validator_rejections=list(self.narrator.last_rejections),
        )
        self.state.log.append(record)

        # Step 5: Render
        turn_display = f"[bold yellow]> {raw_input}[/bold yellow]\n{narration}"
        self._narration_history.append(turn_display)
        self.query_one("#narration-text", Static).update("\n\n".join(self._narration_history))
        self.query_one("#narration-scroll", VerticalScroll).scroll_end(animate=False)

        # Update status and debug drawer
        self._update_status_display()
        self._update_debug_drawer(record)

        # Check ending
        if self.state.ended:
            self.query_one("#player-input", Input).disabled = True
            save_transcript(self.state, self.scenario, self.config.transcript_dir)

    def _show_clarifications(self, options: list[str]) -> None:
        """Display clarification buttons."""
        container = self.query_one("#clarification-container", Horizontal)
        container.display = True
        btns = [
            self.query_one("#btn-opt-1", Button),
            self.query_one("#btn-opt-2", Button),
            self.query_one("#btn-opt-3", Button),
        ]
        for i, opt in enumerate(options):
            if i < len(btns):
                btns[i].label = opt
                btns[i].display = True
        for j in range(len(options), len(btns)):
            btns[j].display = False

    def _hide_clarifications(self) -> None:
        """Hide clarification buttons."""
        container = self.query_one("#clarification-container", Horizontal)
        container.display = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle clarification button clicks."""
        chosen = str(event.button.label)
        self._hide_clarifications()
        action, _ = self.parser.parse(chosen, self.state, self.scenario)
        await self._process_turn(action, chosen)

    def _update_debug_drawer(self, record: TurnRecord) -> None:
        """Append log to debug panel."""
        log_lines = [
            f"[bold cyan]Turn {record.turn}[/bold cyan] Action: {record.action.verb.value}"
        ]
        for ev in record.events:
            log_lines.append(f"  • {ev.type.value}: {ev.message}")
        if record.validator_rejections:
            log_lines.append("  [bold red]Validator Rejections:[/bold red]")
            for rej in record.validator_rejections:
                log_lines.append(f"    - {rej}")

        self._debug_history.extend(log_lines)
        debug_widget = self.query_one("#debug-text", Static)
        debug_widget.update("\n".join(self._debug_history))

    def action_toggle_debug(self) -> None:
        """Toggle debug sidebar visibility."""
        drawer = self.query_one("#debug-drawer", VerticalScroll)
        drawer.display = not drawer.display

    def action_save_game(self) -> None:
        """Export game state snapshot."""
        # Simple save
        p = save_transcript(self.state, self.scenario, self.config.transcript_dir)
        self.notify(f"Chronicle saved to {p.name}")

    def action_export_transcript(self) -> None:
        """Export full Markdown transcript."""
        p = save_transcript(self.state, self.scenario, self.config.transcript_dir)
        self.notify(f"Transcript exported: {p.name}")

    def action_quit_game(self) -> None:
        """Exit app."""
        self.exit()
