"""Command Line Interface for Wyrdflow."""

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys
from typing import Any, Optional
from uuid import UUID

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

console = Console()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="wyrdflow",
        description="Production-grade workflow orchestration for Agentic AI",
    )

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a workflow")
    run_parser.add_argument("workflow", help="Path to workflow file")
    run_parser.add_argument("--config", help="Configuration file path")
    run_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a workflow")
    validate_parser.add_argument("workflow", help="Path to workflow file")

    # Info command
    info_parser = subparsers.add_parser("info", help="Show workflow information")
    info_parser.add_argument("workflow", help="Path to workflow file")

    # Inspect command
    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect workflow execution history"
    )
    inspect_parser.add_argument("run_id", help="Workflow run ID to inspect (UUID)")
    inspect_parser.add_argument(
        "--node",
        help="Filter by specific node ID",
    )
    inspect_parser.add_argument(
        "--format",
        choices=["table", "json", "tree"],
        default="table",
        help="Output format (default: table)",
    )
    inspect_parser.add_argument(
        "--show-data",
        action="store_true",
        help="Show input/output data (can be large)",
    )
    inspect_parser.add_argument(
        "--from-file",
        help="Load execution history from JSON file",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        print(f"Running workflow: {args.workflow}")
        if args.config:
            print(f"Using config: {args.config}")
        # TODO: Implement workflow execution
        print("Workflow execution not yet implemented")
        return 0

    elif args.command == "validate":
        print(f"Validating workflow: {args.workflow}")
        # TODO: Implement workflow validation
        print("Workflow validation not yet implemented")
        return 0

    elif args.command == "info":
        print(f"Workflow info: {args.workflow}")
        # TODO: Implement workflow info display
        print("Workflow info display not yet implemented")
        return 0

    elif args.command == "inspect":
        return inspect_execution(
            args.run_id, args.node, args.format, args.show_data, args.from_file
        )

    return 1


def inspect_execution(  # noqa: PLR0911
    run_id: str,
    node_filter: Optional[str],
    output_format: str,
    show_data: bool,
    from_file: Optional[str] = None,
) -> int:
    """Inspect workflow execution history.

    Args:
        run_id: Workflow run ID (UUID)
        node_filter: Optional node ID to filter by
        output_format: Output format (table, json, tree)
        show_data: Whether to show input/output data
        from_file: Optional path to JSON file with execution history

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from wyrdflow import get_execution_log  # noqa: PLC0415
        from wyrdflow.observability.execution_log import (  # noqa: PLC0415
            NodeExecutionRecord,
        )

        # Parse run ID
        try:
            workflow_run_id = UUID(run_id)
        except ValueError:
            console.print(f"[red]Error: Invalid UUID: {run_id}[/red]")
            return 1

        # Load records from file or execution log
        if from_file:
            try:
                file_path = Path(from_file)
                with file_path.open() as f:
                    data = json.load(f)
                # Convert JSON data back to NodeExecutionRecord objects
                records = [NodeExecutionRecord(**record) for record in data]
            except FileNotFoundError:
                console.print(f"[red]Error: File not found: {from_file}[/red]")
                return 1
            except json.JSONDecodeError as e:
                console.print(f"[red]Error: Invalid JSON in file: {e}[/red]")
                return 1
        else:
            # Get execution log from memory
            exec_log = get_execution_log()
            records = exec_log.get_records_by_run(workflow_run_id)

        if not records:
            console.print(
                f"[yellow]No execution records found for run: {run_id}[/yellow]"
            )
            return 1

        # Filter by node if specified
        if node_filter:
            records = [r for r in records if r.node_id == node_filter]
            if not records:
                console.print(
                    f"[yellow]No records found for node: {node_filter}[/yellow]"
                )
                return 1

        # Display based on format
        if output_format == "json":
            output = [r.model_dump() for r in records]
            print(json.dumps(output, indent=2, default=str))

        elif output_format == "tree":
            _display_execution_tree(records, show_data)

        else:  # table format (default)
            _display_execution_table(records, show_data)

        return 0

    except ImportError as e:
        console.print(f"[red]Error: Failed to import observability module: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error inspecting execution: {e}[/red]")
        return 1


def _display_execution_table(records: list[Any], show_data: bool) -> None:
    """Display execution records in table format."""
    table = Table(title="Workflow Execution History")

    table.add_column("Node ID", style="cyan")
    table.add_column("Node Type", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Retries", justify="center", style="bright_yellow")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Start Time", style="blue")

    if show_data:
        table.add_column("Input", style="dim")
        table.add_column("Output", style="dim")

    for record in records:
        # Format duration
        duration_str = (
            f"{record.duration_ms:.2f}ms" if record.duration_ms is not None else "N/A"
        )

        # Format status with color
        status_color = {
            "SUCCESS": "green",
            "FAILED": "red",
            "TIMEOUT": "red",
            "RUNNING": "yellow",
            "PENDING": "blue",
            "RETRY": "orange",
        }.get(record.status.value.upper(), "white")

        status_str = f"[{status_color}]{record.status.value}[/{status_color}]"

        # Format retries - highlight if retries occurred
        retries = record.retry_attempt
        if retries > 0:
            retries_str = f"[bold bright_yellow]{retries}[/bold bright_yellow]"
        else:
            retries_str = "[dim]-[/dim]"

        row_data = [
            record.node_id,
            record.node_type or "unknown",
            status_str,
            retries_str,
            duration_str,
            record.start_time.strftime("%Y-%m-%d %H:%M:%S"),
        ]

        if show_data:
            input_preview = (
                json.dumps(record.input_data, indent=2)[:100]
                if record.input_data
                else "None"
            )
            output_preview = (
                json.dumps(record.output_data, indent=2)[:100]
                if record.output_data
                else "None"
            )
            row_data.extend([input_preview, output_preview])

        table.add_row(*row_data)

    console.print(table)

    # Show summary statistics
    success_count = sum(1 for r in records if r.status.value == "success")
    failed_count = sum(1 for r in records if r.status.value == "failed")
    retry_count = sum(1 for r in records if r.retry_attempt > 0)
    total_retries = sum(r.retry_attempt for r in records)
    total_duration = sum(r.duration_ms for r in records if r.duration_ms)

    summary = "\n[bold]Summary:[/bold] "
    summary += f"Total: {len(records)} | "
    summary += f"Success: [green]{success_count}[/green] | "
    summary += f"Failed: [red]{failed_count}[/red] | "
    if retry_count > 0:
        summary += f"Retried: [bright_yellow]{retry_count}[/bright_yellow] ({total_retries} attempts) | "
    summary += f"Total Duration: {total_duration:.2f}ms"

    console.print(summary)


def _display_execution_tree(records: list[Any], show_data: bool) -> None:
    """Display execution records in tree format."""
    tree = Tree(
        "[bold]Workflow Execution[/bold]",
        guide_style="dim",
    )

    for record in records:
        # Create node branch
        status_emoji = {
            "success": "✅",
            "failed": "❌",
            "timeout": "⏱️",
            "running": "🔄",
            "pending": "⏳",
            "retry": "🔁",
        }.get(record.status.value, "❓")

        duration_str = (
            f"({record.duration_ms:.2f}ms)" if record.duration_ms is not None else ""
        )

        # Add retry indicator to node label if retries occurred
        retry_indicator = ""
        if record.retry_attempt > 0:
            retry_indicator = f" [bold bright_yellow](retried {record.retry_attempt}x)[/bold bright_yellow]"

        node_label = (
            f"{status_emoji} {record.node_id} "
            f"[{record.node_type or 'unknown'}] {duration_str}{retry_indicator}"
        )
        node_branch = tree.add(node_label)

        # Add details
        node_branch.add(f"Status: {record.status.value}")
        if record.retry_attempt > 0:
            node_branch.add(
                f"[bright_yellow]Retries: {record.retry_attempt}[/bright_yellow]"
            )
        node_branch.add(f"Start: {record.start_time}")
        if record.end_time:
            node_branch.add(f"End: {record.end_time}")

        if record.error_message:
            error_branch = node_branch.add("[red]Error[/red]")
            error_branch.add(f"Type: {record.error_type}")
            error_branch.add(f"Message: {record.error_message}")

        if show_data:
            if record.input_data:
                input_branch = node_branch.add("Input")
                input_json = json.dumps(record.input_data, indent=2)
                input_branch.add(Syntax(input_json, "json", theme="monokai"))

            if record.output_data:
                output_branch = node_branch.add("Output")
                output_json = json.dumps(record.output_data, indent=2)
                output_branch.add(Syntax(output_json, "json", theme="monokai"))

    console.print(tree)


if __name__ == "__main__":
    sys.exit(main())
