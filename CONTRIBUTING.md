# Contributing

Thanks for your interest in contributing to claude-hub.

## Setup

    git clone https://github.com/jleal52/claude-hub.git
    cd claude-hub
    python -m venv .venv
    source .venv/bin/activate  # or .venv\Scripts\activate on Windows
    pip install -e ".[dev]"

## Running tests

    pytest -v

## Pull requests

- Open an issue first for non-trivial changes.
- Keep commits focused; conventional commit style (`feat:`, `fix:`, `docs:`, `chore:`) preferred.
- Add tests for new behavior.
- By contributing you agree your work is licensed under AGPL-3.0.
