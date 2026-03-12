"""Analyze commands -- context effectiveness and insights."""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from xpgraph.retrieve.effectiveness import analyze_effectiveness
from xpgraph_cli.stores import get_event_log

analyze_app = typer.Typer(no_args_is_help=True)
console = Console()

# Display thresholds for rate coloring
_RATE_GREEN = 0.7
_RATE_YELLOW = 0.4


@analyze_app.command("context-effectiveness")
def context_effectiveness(
    days: int = typer.Option(30, help="Days of history to analyze"),
    min_appearances: int = typer.Option(2, help="Minimum item appearances to include"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Analyze which context items correlate with task success."""
    event_log = get_event_log()
    try:
        report = analyze_effectiveness(
            event_log,
            days=days,
            min_appearances=min_appearances,
        )
    finally:
        event_log.close()

    if output_format == "json":
        console.print(json.dumps(report.to_dict()))
    else:
        console.print(f"[bold]Context Effectiveness Report[/bold] (last {days} days)")
        console.print(f"  Packs assembled: {report.total_packs}")
        console.print(f"  Feedback received: {report.total_feedback}")
        console.print(f"  Overall success rate: {report.success_rate:.1%}")

        if report.item_scores:
            console.print()
            table = Table(title="Item Effectiveness")
            table.add_column("Item ID", style="cyan", max_width=20)
            table.add_column("Appearances", justify="right")
            table.add_column("Successes", justify="right")
            table.add_column("Failures", justify="right")
            table.add_column("Rate", justify="right")

            for item in report.item_scores[:20]:
                rate_style = (
                    "green"
                    if item["success_rate"] >= _RATE_GREEN
                    else "yellow"
                    if item["success_rate"] >= _RATE_YELLOW
                    else "red"
                )
                table.add_row(
                    item["item_id"][:20],
                    str(item["appearances"]),
                    str(item["successes"]),
                    str(item["failures"]),
                    f"[{rate_style}]{item['success_rate']:.1%}[/{rate_style}]",
                )
            console.print(table)

        if report.noise_candidates:
            console.print()
            console.print(
                "[yellow]Noise Candidates[/yellow]"
                " (low success rate, consider removing):"
            )
            for item_id in report.noise_candidates:
                console.print(f"  - {item_id}")

        if report.total_feedback == 0:
            console.print()
            console.print(
                "[dim]No feedback recorded yet. Use 'xpg curate feedback' or"
                " POST /api/v1/packs/{pack_id}/feedback to record outcomes.[/dim]"
            )
