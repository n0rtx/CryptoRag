import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging

from backend import market


def main() -> None:
    """Force a refresh of all tracked coins and write the snapshot file.

    Intended for use as a PythonAnywhere scheduled task, so that data stays fresh even when the web app is idle.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    market.load()
    ok = market.refresh_all(force=True)
    print("OK" if ok else "PARTIAL: some coins could not be refreshed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
