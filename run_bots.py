from __future__ import annotations

import sys
from pathlib import Path


VORTEX_DIRECTORY = Path(__file__).resolve().parent / "vortex_bot"
sys.path.insert(0, str(VORTEX_DIRECTORY))

from main import main


if __name__ == "__main__":
    main()
