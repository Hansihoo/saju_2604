"""CLI entry point. Run --help for independent prepare/task/execute/evaluate/run commands."""

from .agent_verification.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
