"""
PP2 Layer 2 - Step 1: Bulk-download MaStR into a local SQLite database.

Downloads only the "solar", "storage", and "storage_units" bulk data groups
(not the full national dump of every technology) via open-mastr's bulk XML
method. "storage_units" is the Anlage/plant-level table - it's the only
place NutzbareSpeicherkapazitaet (kWh) is actually populated; the unit-level
"storage" table (storage_extended) only carries power (kW), not energy.
Everything lands under data/open-mastr/ (gitignored - several GB, national
scope, never committed).
"""

import os
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data" / "open-mastr"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Must be set before Mastr() is constructed - open-mastr reads this env var
# to decide where to place the sqlite db and raw XML (default: ~/.open-MaStR).
os.environ["OUTPUT_PATH"] = str(DATA_DIR)

from open_mastr import Mastr  # noqa: E402


def main():
    db = Mastr()
    print(f"SQLite DB will be written to: {db.engine.url}")
    db.download(method="bulk", data=["solar", "storage", "storage_units"])
    print("Bulk download + write-to-database complete.")


if __name__ == "__main__":
    main()
