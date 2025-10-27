# Developer Guide & AI Guidance

This document provides guidance for both human developers and AI assistants working on the Wyrdflow codebase.

## AI Guidance

Always remember the following points when working on this codebase:

1. **Use `uv` for dependency management**: This ensures consistent environments and helps avoid package version issues.

2. **Prefer explicit errors over fallbacks**: The goal is to fix issues, not mask errors.

3. **Follow SOLID principles**: Write clean, maintainable code following good software development practices.

4. **Simpler is better**: Choose the most straightforward solution that meets requirements.

5. **Maintain clean architecture**: Provide functionality in a clear and maintainable manner. NEVER add special-cases or hack fixes simply to get around issues.

6. **Respect architectural boundaries**: Do NOT make band-aid fixes that break clean architecture guidelines. Always respect the architectural boundaries to limit coupling between components.

7. **Run quality checks after changes**: After all code changes, run `ruff format`, `ruff check`, and `mypy` to ensure code quality is retained in an iterative manner.

8. **Line length limit**: Avoid making lines longer than 88 characters (E501 ruff check).

9. **Thread safety is critical**: All public APIs must be thread-safe and work correctly in concurrent environments.

10. **No git operations**: Do not perform any git operations as the developer will handle those.

## Developer Setup & Operations

### Environment Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup the project
git clone <repository-url>
cd wyrdflow
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=wyrdflow --cov-report=html

# Run specific test file
uv run pytest tests/test_basic.py

# Run tests in verbose mode
uv run pytest -v
```

### Quality Checks

The project enforces strict code quality standards:

```bash
# Format code (required before commit)
uv run ruff format .

# Check code quality (required before commit)
uv run ruff check .

# Type checking (required before commit)
uv run mypy src/wyrdflow

# Run all quality checks at once
uv run ruff format . && uv run ruff check . && uv run mypy src/wyrdflow
```

### CLI Tools

```bash
# Show CLI help
uv run wyrdflow --help

# Run workflow (when implemented)
uv run wyrdflow run path/to/workflow.json

# Validate workflow (when implemented)
uv run wyrdflow validate path/to/workflow.json

# Show workflow info (when implemented)
uv run wyrdflow info path/to/workflow.json
```

### Pre-commit Hooks

Pre-commit hooks automatically run on every commit:

- **ruff format**: Code formatting
- **ruff check**: Linting and code quality
- **mypy**: Static type checking
- **Standard hooks**: Trailing whitespace, file endings, YAML validation, etc.

To run pre-commit hooks manually:

```bash
# Run on all files
uv run pre-commit run --all-files

# Run on staged files only
uv run pre-commit run
```

### Development Workflow

1. **Create feature branch**: `git checkout -b feature/your-feature`
2. **Make changes**: Edit code, add tests, update docs
3. **Run quality checks**: `uv run ruff format . && uv run ruff check . && uv run mypy src/wyrdflow`
4. **Run tests**: `uv run pytest`
5. **Commit**: Pre-commit hooks run automatically
6. **Push and PR**: Follow contribution guidelines

### Project Standards

- **Test Coverage**: Maintain 80%+ test coverage (enforced in CI)
- **Type Hints**: Required for all public APIs
- **Documentation**: Comprehensive docstrings and README updates
- **Threading**: All public APIs must be thread-safe
- **Error Handling**: Explicit error handling, no silent failures

### Continuous Integration

GitHub Actions CI runs on every push and PR:

- **Matrix testing**: Python 3.9 and 3.12
- **Quality checks**: ruff format, ruff check, mypy
- **Test suite**: Full test suite with coverage reporting
- **Pre-commit**: All pre-commit hooks

### Troubleshooting

#### Common Issues

1. **Import errors**: Ensure you're using the virtual environment (`uv run`)
2. **Type checking failures**: Add type hints or use `# type: ignore` sparingly
3. **Formatting issues**: Run `uv run ruff format .` to auto-fix
4. **Test failures**: Check test isolation and mock usage

#### Getting Help

- Check the implementation plan: `WyrdflowImplementationPlan.md`
- Review existing tests for patterns
- Follow the architectural principles above
- Ask for clarification on unclear requirements
