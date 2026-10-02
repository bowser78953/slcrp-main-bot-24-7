from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from discord_bot.bot.client import ConfigError, FarmersDiscordBot, load_all_config
else:
    from .bot.client import ConfigError, FarmersDiscordBot, load_all_config


def main() -> None:
    base_path = Path(__file__).resolve().parent

    try:
        settings, _, _, _ = load_all_config(base_path)
    except FileNotFoundError as exc:
        missing = exc.filename or "Unknown file"
        raise SystemExit(f"Missing required JSON file: {missing}") from exc
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc

    bot = FarmersDiscordBot(base_path=base_path)
    bot.run(settings["token"])


if __name__ == "__main__":
    main()
