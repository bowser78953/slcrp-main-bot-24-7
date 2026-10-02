from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values


BOT_SPECS = (
    ("indiana-state", "discord_bot/main.py", "DISCORD_BOT_TOKEN"),
    ("vortex", "vortex_bot/main.py", "VORTEX_BOT_TOKEN"),
)


def _local_token(root: Path, directory: str, *keys: str) -> str:
    local_env = dotenv_values(root / directory / ".env")
    for key in keys:
        value = str(local_env.get(key) or "").strip()
        if value and not value.startswith("PUT_YOUR_"):
            return value
    return ""


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    tokens = {
        "indiana-state": os.getenv("DISCORD_BOT_TOKEN", "").strip()
        or _local_token(repo_root, "discord_bot", "DISCORD_BOT_TOKEN"),
        "vortex": os.getenv("VORTEX_BOT_TOKEN", "").strip()
        or _local_token(repo_root, "vortex_bot", "VORTEX_BOT_TOKEN", "DISCORD_BOT_TOKEN"),
    }
    if tokens["vortex"] and tokens["vortex"] == tokens["indiana-state"]:
        print("Skipping Vortex: configure a token for a separate Discord bot account.")
        tokens["vortex"] = ""

    processes: dict[str, subprocess.Popen] = {}
    restart_after: dict[str, float] = {}
    stopping = False

    def start_bot(name: str, script: str, token: str) -> None:
        if not token:
            token_name = "DISCORD_BOT_TOKEN" if name == "indiana-state" else "VORTEX_BOT_TOKEN"
            print(f"Skipping {name}: {token_name} is missing.")
            return
        child_env = os.environ.copy()
        child_env["DISCORD_BOT_TOKEN"] = token
        script_path = repo_root / script
        print(f"Starting {name} from {script}.")
        processes[name] = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(repo_root),
            env=child_env,
        )
        restart_after[name] = 0.0

    def stop_all() -> None:
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
        for process in processes.values():
            if process.poll() is None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()

    def request_stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    for name, script, _token_name in BOT_SPECS:
        start_bot(name, script, tokens[name])
    if not processes:
        print("No bot processes started. Configure one or both bot tokens.")
        return 1

    try:
        while not stopping:
            now = time.time()
            for name, script, _token_name in BOT_SPECS:
                process = processes.get(name)
                if process is None:
                    if tokens[name] and now >= restart_after.get(name, 0.0):
                        start_bot(name, script, tokens[name])
                    continue
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"{name} exited with code {exit_code}; restarting in 5 seconds.")
                    processes.pop(name, None)
                    restart_after[name] = now + 5
            time.sleep(2)
    finally:
        stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())