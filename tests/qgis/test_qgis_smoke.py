"""Runs ``qgis_smoke.py`` with QGIS's Python (marker ``qgis``; never in CI).

$env:KMA_QGIS_PYTHON = "C:\\OSGeo4W\\bin\\python-qgis.bat"
.\\.venv\\Scripts\\python -m pytest -m qgis
"""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("qgis_smoke.py")


@pytest.mark.qgis
def test_dock_smoke_in_qgis():
    python = os.environ.get("KMA_QGIS_PYTHON")
    if not python:
        pytest.skip("KMA_QGIS_PYTHON ei ole asetettu (esim. C:\\OSGeo4W\\bin\\python-qgis.bat)")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [python, str(SCRIPT)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Savutesti läpi" in result.stdout
