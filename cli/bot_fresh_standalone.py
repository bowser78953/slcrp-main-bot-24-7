from pathlib import Path
import runpy
import sys

# Compatibility launcher when Render Root Directory is set to 'cli'.
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
runpy.run_path(str(repo_root / "bot_fresh_standalone.py"), run_name="__main__")
