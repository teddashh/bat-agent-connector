"""A10: the Dashboard's bilingual start note follows the server's account effect."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Dashboard rendering test requires Node")
def test_a10_dashboard_start_note_matches_account_effect_in_both_languages():
    result = subprocess.run(["node", "--test", str(Path(__file__).with_name("dashboard_confinement_note.mjs"))],
                            capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
