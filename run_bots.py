from pathlib import Path
import os
import signal
import subprocess
import sys
import time


def start_process(script_name: str, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    repo_root = Path(__file__).resolve().parent
    script_path = repo_root / script_name
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen([sys.executable, str(script_path)], cwd=str(repo_root), env=env)


def main() -> int:
    bot_specs: list[tuple[str, str, str | None, dict[str, str] | None]] = [
        ("main", "bot_fresh_standalone.py", "NEW_BOT_TOKEN", None),
        ("farmers", "cli/fas_farmers_bot.py", "FAS_FARMERS_BOT_TOKEN", {"FAS_BOT_MODE": "farmers"}),
        ("seed", "cli/fas_farmers_bot.py", "FAS_SEED_BOT_TOKEN", {"FAS_BOT_MODE": "seed"}),
        ("modmail", "modmail.py", "MODMAIL_TOKEN", None),
        ("ycf", "ycf_bot.py", "YCF_BOT_TOKEN", None),
        ("third", "bot_third.py", "THIRD_BOT_TOKEN", None),
    ]
    processes: dict[str, subprocess.Popen] = {}
    next_restart_at: dict[str, float] = {}

    def can_start(token_env_var: str | None) -> bool:
        return token_env_var is None or bool(os.getenv(token_env_var))

    def start_named_process(name: str, script_name: str, token_env_var: str | None, extra_env: dict[str, str] | None) -> None:
        if not can_start(token_env_var):
            if token_env_var:
                print(f"Skipping {script_name}: missing {token_env_var}")
            return
        print(f"Starting {script_name}...")
        processes[name] = start_process(script_name, extra_env=extra_env)
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
    for name, script_name, token_env_var, extra_env in bot_specs:
        start_named_process(name, script_name, token_env_var, extra_env)

    if not processes:
        print("No bot processes started. Set at least one bot token.")
        return 1

    try:
        while True:
            now = time.time()
            for name, script_name, token_env_var, extra_env in bot_specs:
                process = processes.get(name)
                if process is None:
                    if now >= next_restart_at.get(name, 0.0) and can_start(token_env_var):
                        start_named_process(name, script_name, token_env_var, extra_env)
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
