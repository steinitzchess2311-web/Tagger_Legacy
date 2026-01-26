"""Package entry point for ``python -m rule_tagger``."""

from .runner import main

if __name__ == "__main__":
    raise SystemExit(main())
