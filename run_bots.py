from pathlib import Path
import signal
import subprocess
import sys
import time


def start_process(script_name: str) -> subprocess.Popen:
    repo_root = Path(__file__).resolve().parent
    script_path = repo_root / script_name
    return subprocess.Popen([sys.executable, str(script_path)], cwd=str(repo_root))


def main() -> int:
    processes: list[subprocess.Popen] = []

    def stop_all() -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            if process.poll() is None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()

    def handle_signal(signum, _frame) -> None:
        print(f"Received signal {signum}. Stopping bots.")
        stop_all()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    print("Starting main bot and modmail bot...")
    processes.append(start_process("bot_fresh_standalone.py"))
    processes.append(start_process("modmail.py"))

    try:
        while True:
            for process in processes:
                code = process.poll()
                if code is not None:
                    print(f"Child process exited with code {code}. Restarting worker process.")
                    stop_all()
                    return 1
            time.sleep(2)
    finally:
        stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
