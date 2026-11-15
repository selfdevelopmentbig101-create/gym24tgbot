"""
The bot must start even when Pillow/matplotlib can't load (e.g. Windows
Smart App Control blocks their DLLs). Runs in a subprocess so the blocked
imports don't affect other tests.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = r"""
import sys
# None in sys.modules makes "import PIL" raise ImportError, like a blocked DLL.
for name in ("PIL", "PIL.Image", "matplotlib"):
    sys.modules[name] = None

import bot  # noqa: F401  (imports every handler and service)
from services import charts, exercise_media

assert exercise_media.Image is None
assert exercise_media.build_media("bench-press") is None
try:
    charts.line_chart("t", "kg", [])
except charts.ChartsUnavailable:
    print("OK")
"""


def test_bot_imports_without_pillow_and_matplotlib():
    result = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")
