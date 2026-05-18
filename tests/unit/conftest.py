import sys
from pathlib import Path

# Ensure the worktree root is on sys.path so `from core.xxx import ...` works
# when pytest is invoked from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
