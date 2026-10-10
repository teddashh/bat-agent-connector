"""Windows equivalent of pytest-disktmp, with an explicit disk basetemp and cleanup."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.home() / "agent-work" / "tmp" / "pytest"
root.mkdir(parents=True, exist_ok=True)
temporary = Path(tempfile.mkdtemp(prefix="windows-central-", dir=root))
try:
    result = subprocess.run(  # noqa: S603 - fixed repository fixture selectors
        [sys.executable, "-m", "pytest", "-q", "--basetemp", str(temporary),
         "tests/test_platform_files.py", "tests/test_windows_central.py"],
        cwd=Path(__file__).resolve().parents[2],
    )
    raise SystemExit(result.returncode)
finally:
    shutil.rmtree(temporary)
