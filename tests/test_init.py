"""Tests for main package functionality."""

from wyrdflow import hello


def test_hello_function():
    """Test the hello function from the main package."""
    result = hello()
    assert result == "Hello from wyrdflow!"
    assert isinstance(result, str)
