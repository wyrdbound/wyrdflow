"""Tests for the CLI module."""

import sys
from unittest.mock import patch

from wyrdflow.cli import main


def test_cli_help() -> None:
    """Test that CLI help works."""
    with patch.object(sys, "argv", ["wyrdflow", "--help"]):
        try:
            main()
        except SystemExit as e:
            # argparse exits with code 0 for help
            assert e.code == 0


def test_cli_version() -> None:
    """Test that CLI version works."""
    with patch.object(sys, "argv", ["wyrdflow", "--version"]):
        try:
            main()
        except SystemExit as e:
            # argparse exits with code 0 for version
            assert e.code == 0


def test_cli_no_command() -> None:
    """Test CLI behavior with no command."""
    result = main([])
    assert result == 1


def test_cli_run_command() -> None:
    """Test CLI run command."""
    result = main(["run", "test_workflow.json"])
    assert result == 0


def test_cli_validate_command() -> None:
    """Test CLI validate command."""
    result = main(["validate", "test_workflow.json"])
    assert result == 0


def test_cli_info_command() -> None:
    """Test CLI info command."""
    result = main(["info", "test_workflow.json"])
    assert result == 0


def test_cli_run_with_config() -> None:
    """Test CLI run command with config."""
    result = main(["run", "test_workflow.json", "--config", "config.json"])
    assert result == 0


def test_cli_run_verbose() -> None:
    """Test CLI run command with verbose flag."""
    result = main(["run", "test_workflow.json", "--verbose"])
    assert result == 0
