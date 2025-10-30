# Wyrdflow

**Production-grade workflow orchestration for Agentic AI**

[![CI](https://github.com/wyrdbound/wyrdflow/workflows/CI/badge.svg)](https://github.com/wyrdbound/wyrdflow/actions)
[![Coverage](https://codecov.io/gh/wyrdbound/wyrdflow/branch/main/graph/badge.svg)](https://codecov.io/gh/wyrdbound/wyrdflow)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Wyrdflow is a Python library designed for ML engineers and AI developers who need to build complex, maintainable agentic AI workflows. Built on top of LangChain, LangGraph, and LangSmith, Wyrdflow provides a class-based node system with built-in validation, retry logic, observability, and production-grade reliability.

## Features

- **Class-based nodes** with full input/output validation using Pydantic v2
- **Declarative configuration** for retries, timeouts, and behavior
- **Advanced state management** with inspection, snapshots, and restore capabilities
- **Built-in observability** with LangSmith integration
- **Thread-safe** execution for concurrent environments
- **Type-safe by default** with comprehensive type hints
- **Production-ready** with comprehensive error handling

## Current Capabilities (Phase 1)

Wyrdflow currently provides a solid foundation for workflow orchestration:

### State Management

- **WorkflowState**: Type-safe state management with Pydantic validation
- **StateSnapshot**: Immutable snapshots for debugging and rollback
- **StateInspector**: Utilities for state visualization, comparison, and search

```python
from wyrdflow.core import WorkflowState, StateSnapshot, StateInspector

# Create and manage workflow state
state = WorkflowState.create_new()
state.set("user_data", {"name": "Alice", "role": "admin"})

# Create snapshots for debugging/rollback
snapshot = StateSnapshot.from_state(state, source_node_id="validation")
restored_state = snapshot.restore()  # Restore from snapshot

# Inspect and analyze state
formatted = StateInspector.format_state(state)
results = StateInspector.search_state(state, "alice")
diff = StateInspector.compare_states(state1, state2)
```

### Node System

- **BaseNode**: Abstract base class with retry logic and error handling
- **LangGraph Integration**: Seamless integration with LangGraph workflows
- **Type Safety**: Full input/output validation with Pydantic schemas

Run `python examples/state_management_demo.py` to see state management in action!

## Quick Start

### Installation

```bash
# Install from PyPI (when released)
pip install wyrdflow

# Or install from source for development
git clone https://github.com/wyrdbound/wyrdflow.git
cd wyrdflow
uv pip install -e ".[dev]"
```

### Basic Usage

```python
# Coming in Phase 1 - basic workflow example
from wyrdflow import BaseNode, WorkflowGraph

# Example will be added as components are implemented
```

## Development Setup

This project uses `uv` for dependency management and virtual environments.

### Prerequisites

- Python 3.9 or higher
- [uv](https://github.com/astral-sh/uv) for dependency management

### Setting up the development environment

```bash
# Clone the repository
git clone https://github.com/wyrdbound/wyrdflow.git
cd wyrdflow

# Install the package with development dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
uv run pre-commit install
```

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_basic.py

# Run tests with coverage report
uv run pytest --cov=wyrdflow --cov-report=html
```

### Quality Checks

This project enforces code quality through several tools:

```bash
# Format code with ruff
uv run ruff format .

# Lint code with ruff
uv run ruff check .

# Type check with mypy
uv run mypy src/wyrdflow

# Run all quality checks (same as pre-commit)
uv run ruff format . && uv run ruff check . && uv run mypy src/wyrdflow
```

### CLI Tools

Wyrdflow includes a command-line interface for workflow management:

```bash
# Show help
uv run wyrdflow --help

# Run a workflow (coming soon)
uv run wyrdflow run path/to/workflow.json

# Validate a workflow (coming soon)
uv run wyrdflow validate path/to/workflow.json

# Show workflow information (coming soon)
uv run wyrdflow info path/to/workflow.json
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

- `ruff format` - Code formatting
- `ruff check` - Code linting
- `mypy` - Type checking
- Standard hooks for trailing whitespace, file endings, etc.

Pre-commit hooks run automatically on every commit. To run them manually:

```bash
uv run pre-commit run --all-files
```

## Development Workflow

1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
2. **Make your changes**: Edit code, add tests, update documentation
3. **Run quality checks**: `uv run ruff format . && uv run ruff check . && uv run mypy src/wyrdflow`
4. **Run tests**: `uv run pytest`
5. **Commit your changes**: Pre-commit hooks will run automatically
6. **Push and create a PR**: Follow the project's contribution guidelines

## Project Structure

```
wyrdflow/
├── src/wyrdflow/           # Main package source
│   ├── __init__.py         # Package initialization
│   ├── cli.py              # Command-line interface
│   └── py.typed            # Type hint marker
├── tests/                  # Test suite
│   ├── conftest.py         # Test configuration
│   └── test_basic.py       # Basic tests
├── .github/workflows/      # GitHub Actions CI/CD
├── pyproject.toml          # Project configuration
├── .pre-commit-config.yaml # Pre-commit configuration
└── README.md               # This file
```

## Implementation Roadmap

Wyrdflow is being developed in phases:

- **Phase 1** (Current): Foundation & Core Architecture
- **Phase 2**: Human-in-the-Loop Nodes
- **Phase 3**: LLM Agent Node (Unified)
- **Phase 4**: Flow Control Nodes
- **Phase 5**: Observability & Debugging Foundation
- **Phase 6**: Vector Store & RAG Nodes
- **Phase 7**: Security & Sandboxing

See [WyrdflowImplementationPlan.md](WyrdflowImplementationPlan.md) for detailed information about each phase.

## Contributing

We welcome contributions! Please see our contributing guidelines for details.

### Code Quality Standards

- Maintain 80%+ test coverage
- All code must pass ruff formatting and linting
- Type hints are required for all public APIs
- Follow the architectural principles outlined in [AGENTS.md](AGENTS.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built on top of the excellent work by:

- [LangChain](https://github.com/langchain-ai/langchain)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [LangSmith](https://github.com/langchain-ai/langsmith-sdk)
- [Pydantic](https://github.com/pydantic/pydantic)
