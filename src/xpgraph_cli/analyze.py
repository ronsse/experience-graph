"""Analyze commands -- context effectiveness and insights."""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from xpgraph.retrieve.effectiveness import analyze_effectiveness
from xpgraph.retrieve.token_usage import analyze_token_usage
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


@analyze_app.command("token-usage")
def token_usage(
    days: int = typer.Option(7, help="Days of history to analyze"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Analyze token usage across CLI, MCP, and SDK layers."""
    event_log = get_event_log()
    try:
        report = analyze_token_usage(event_log, days=days)
    finally:
        event_log.close()

    if output_format == "json":
        console.print(json.dumps(report.to_dict()))
        return

    console.print(f"[bold]Token Usage Report[/bold] (last {days} days)")
    console.print(f"  Total responses: {report.total_responses}")
    console.print(f"  Total tokens: {report.total_tokens:,}")
    console.print(f"  Avg tokens/response: {report.avg_tokens_per_response:.1f}")

    if report.by_layer:
        console.print()
        layer_table = Table(title="By Layer")
        layer_table.add_column("Layer", style="cyan")
        layer_table.add_column("Responses", justify="right")
        layer_table.add_column("Total Tokens", justify="right")
        layer_table.add_column("Avg Tokens", justify="right")

        for layer, stats in sorted(report.by_layer.items()):
            layer_table.add_row(
                layer.upper(),
                str(stats["count"]),
                f"{stats['total_tokens']:,}",
                f"{stats['avg_tokens']:.1f}",
            )
        console.print(layer_table)

    if report.by_operation:
        console.print()
        op_table = Table(title="Top Operations by Token Usage")
        op_table.add_column("Operation", style="cyan")
        op_table.add_column("Layer", style="dim")
        op_table.add_column("Calls", justify="right")
        op_table.add_column("Total Tokens", justify="right")
        op_table.add_column("Avg Tokens", justify="right")

        for op in report.by_operation:
            op_table.add_row(
                op["operation"],
                op["layer"],
                str(op["count"]),
                f"{op['total_tokens']:,}",
                f"{op['avg_tokens']:.1f}",
            )
        console.print(op_table)

    if report.over_budget:
        console.print()
        console.print(
            f"[yellow]Over-Budget Responses ({len(report.over_budget)})[/yellow]"
        )
        budget_table = Table()
        budget_table.add_column("Operation", style="cyan")
        budget_table.add_column("Layer")
        budget_table.add_column("Response Tokens", justify="right")
        budget_table.add_column("Budget", justify="right")
        budget_table.add_column("When")

        for item in report.over_budget[:20]:
            budget_table.add_row(
                item["operation"],
                item["layer"],
                str(item["response_tokens"]),
                str(item["budget_tokens"]),
                item["occurred_at"][:16],
            )
        console.print(budget_table)

    if report.total_responses == 0:
        console.print()
        console.print(
            "[dim]No token usage recorded yet. Token tracking is enabled"
            " on MCP macro tools automatically.[/dim]"
        )
