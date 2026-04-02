"""Modular entrypoint for the fast simulation runner."""

import sys

sys.dont_write_bytecode = True

from fast_runner import main


if __name__ == "__main__":
    main()
