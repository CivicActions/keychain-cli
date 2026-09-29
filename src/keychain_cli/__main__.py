"""Allow ``python -m keychain_cli``."""

import sys

from keychain_cli.cli import main

if __name__ == "__main__":
    sys.exit(main())
