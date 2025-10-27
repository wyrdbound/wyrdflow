"""Command Line Interface for Wyrdflow."""

import argparse
from collections.abc import Sequence
import sys
from typing import Optional


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

    return 1


if __name__ == "__main__":
    sys.exit(main())
