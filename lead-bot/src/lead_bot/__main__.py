from __future__ import annotations

import asyncio

from .bot import run
from .config import load_settings


def main() -> None:
    settings = load_settings()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
