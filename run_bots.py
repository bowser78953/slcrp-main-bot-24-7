from pathlib import Path
import os
import signal
import subprocess
import sys
import time


def start_process(script_name: str) -> subprocess.Popen:
    repo_root = Path(__file__).resolve().parent
    script_path = repo_root / script_name
    return subprocess.Popen([sys.executable, str(script_path)], cwd=str(repo_root))


def main() -> int:
    bot_specs: list[tuple[str, str, str | None]] = [
        ("main", "bot_fresh_standalone.py", "NEW_BOT_TOKEN"),
        ("farmers", "cli/fas_farmers_bot.py", "FAS_FARMERS_BOT_TOKEN"),
        ("modmail", "modmail.py", "MODMAIL_TOKEN"),
        ("ycf", "ycf_bot.py", "YCF_BOT_TOKEN"),
        ("third", "bot_third.py", "THIRD_BOT_TOKEN"),
    ]
    processes: dict[str, subprocess.Popen] = {}
    next_restart_at: dict[str, float] = {}

    def can_start(token_env_var: str | None) -> bool:
        return token_env_var is None or bool(os.getenv(token_env_var))

    def start_named_process(name: str, script_name: str, token_env_var: str | None) -> None:
        if not can_start(token_env_var):
            if token_env_var:
                print(f"Skipping {script_name}: missing {token_env_var}")
            return
        print(f"Starting {script_name}...")
        processes[name] = start_process(script_name)
        next_restart_at[name] = 0.0

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
        processes.clear()

    def handle_signal(signum, _frame) -> None:
        print(f"Received signal {signum}. Stopping bots.")
        stop_all()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    print("Starting bot processes...")
    for name, script_name, token_env_var in bot_specs:
        start_named_process(name, script_name, token_env_var)

    if not processes:
        print("No bot processes started. Set at least one bot token.")
        return 1

    try:
        while True:
            now = time.time()
            for name, script_name, token_env_var in bot_specs:
                process = processes.get(name)
                if process is None:
                    if now >= next_restart_at.get(name, 0.0) and can_start(token_env_var):
                        start_named_process(name, script_name, token_env_var)
                    continue

                code = process.poll()
                if code is not None:
                    print(f"{script_name} exited with code {code}. Scheduling restart.")
                    processes.pop(name, None)
                    next_restart_at[name] = now + 5
            time.sleep(2)
    finally:
        stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
