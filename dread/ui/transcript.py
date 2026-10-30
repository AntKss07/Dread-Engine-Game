"""Markdown transcript generation and 'What Was Real' hallucination debrief."""

from datetime import datetime
from pathlib import Path

from dread.engine.state import EventType, GameState
from dread.scenarios.schema import Scenario


def generate_markdown_transcript(
    state: GameState,
    scenario: Scenario,
    run_timestamp: str = "",
) -> str:
    """Format full playthrough log into clean, publication-ready Markdown."""
    timestamp = run_timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_str = (
        "VICTORY"
        if state.ended
        and "reunion" in state.ended
        or "rescue" in state.ended
        or "dawn" in state.ended
        else ("DEFEAT / CONCLUDED" if state.ended else "IN PROGRESS")
    )

    lines = [
        f"# Dread Engine Transcript: {scenario.title}",
        f"**Date:** {timestamp}  ",
        f"**Scenario:** `{scenario.id}` ({scenario.theme})  ",
        f"**RNG Seed:** `{state.seed}`  ",
        f"**Total Turns:** {state.turn}  ",
        f"**Outcome:** {status_str} (`{state.ended or 'Active'}`)  ",
        f"**Final Vitals:** HP: {state.hp}/10 | Sanity: {state.sanity}/100 | Dread: {state.dread}/10  ",
        f"**Clues Uncovered:** {len(state.clues_found)} / {len(scenario.clues)}  ",
        "",
        "---",
        "## Chronicle of Turns",
        "",
    ]

    for rec in state.log:
        lines.append(f"### Turn {rec.turn} — Location: `{rec.location_id}`")
        lines.append(f"> **Player Input:** `{rec.raw_input}`")
        lines.append(
            f"**Action Resolved:** `{rec.action.verb.value}` (Target: `{rec.action.target or 'none'}`, Instrument: `{rec.action.instrument or 'none'}`) [Conf: {rec.action.confidence:.2f}]"
        )
        lines.append("")
        lines.append(f"**Narration:**\n{rec.narration}\n")

        # Events list
        if rec.events:
            lines.append("<details><summary>Engine Facts & Events</summary>\n")
            for ev in rec.events:
                hallu_mark = " *(Hallucination)*" if ev.is_hallucination else ""
                lines.append(f"- **{ev.type.value}**: {ev.message}{hallu_mark}")
            lines.append("</details>\n")

        # Validator rejections if any
        if rec.validator_rejections:
            lines.append("<details><summary>Validator Debug (Rejections)</summary>\n")
            for rej in rec.validator_rejections:
                lines.append(f"- *Rejected candidate:* {rej}")
            lines.append("</details>\n")

        lines.append(f"*Vitals:* HP: {rec.hp} | Sanity: {rec.sanity} | Dread: {rec.dread}\n")
        lines.append("---")

    # What Was Real Section
    lines.append("\n## What Was Real (The Veil Pierced)")
    hallucinations = []
    for rec in state.log:
        for ev in rec.events:
            if ev.is_hallucination or ev.type == EventType.HALLUCINATION:
                hallucinations.append((rec.turn, ev.message, ev.payload.get("hint", "")))

    if hallucinations:
        lines.append(
            "During your ordeal, the creeping terror warped your senses. Here is what your mind invented:\n"
        )
        for turn_num, msg, hint in hallucinations:
            lines.append(f"- **Turn {turn_num}:** {hint or msg} *(Illusion caused by low sanity)*")
    else:
        lines.append(
            "Your mind remained fortified throughout the darkness. No phantom illusions clouded your vision.\n"
        )

    return "\n".join(lines)


def save_transcript(
    state: GameState,
    scenario: Scenario,
    output_dir: str | Path = "transcripts",
) -> Path:
    """Save markdown transcript to file."""
    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    filename = f"transcript_{scenario.id}_{state.seed}_turn{state.turn}.md"
    file_path = dir_path / filename

    content = generate_markdown_transcript(state, scenario)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path
