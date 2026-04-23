# Contributing to Serial MCP Server

Thank you for your interest in contributing to the Serial MCP Server! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- A GitHub account

### Setting Up the Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/serial-mcp.git
   cd serial-mcp
   ```

3. Install the package in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

## Development Workflow

### Running Tests

Run the test suite:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=serial_mcp --cov-report=html
```

### Code Style

This project uses [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.

Check code style:
```bash
ruff check
```

Auto-fix issues:
```bash
ruff check --fix
```

Format code:
```bash
ruff format
```

### Type Checking

Run type checker:
```bash
mypy src/serial_mcp
```

## Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-baud-rate-auto-detection`
- `fix/timeout-handling`
- `docs/update-readme`

### Commit Messages

Follow conventional commits:
- `feat: add support for custom flow control`
- `fix: handle serial port disconnection gracefully`
- `docs: update installation instructions`
- `test: add tests for signal reading`

### Pull Requests

1. Ensure your branch is up to date with the main branch
2. Run tests and ensure they pass
3. Run linting and fix any issues
4. Write a clear description of your changes
5. Link related issues (if any)

## Testing

- Write unit tests for new functionality
- Ensure existing tests still pass
- Test on multiple platforms if possible (Windows, Linux, macOS)

## Documentation

- Update README.md if you change the API
- Add docstrings to new functions and classes
- Update CHANGELOG.md for user-facing changes

## Questions?

Feel free to open an issue for questions or discussions about contributions.