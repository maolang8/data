from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
app_path = repo_root / ".2\ucc28 \ud504\ub85c\uc81d\ud2b8" / "temp" / "dashboard" / "app.py"
port = os.environ.get("PORT", "2718")

subprocess.run(
    [
        sys.executable,
        "-m",
        "marimo",
        "run",
        str(app_path),
        "--host",
        "0.0.0.0",
        "--port",
        port,
        "--no-token",
    ],
    check=True,
)
