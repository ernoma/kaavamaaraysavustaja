"""Background tasks of the dock (``QgsTask``, plan 6.13): conversion, model run, Syke validation.

The work itself is a QGIS-free function from ``core/workflow.py``; the task only runs it in a
worker thread. ``run`` must not touch widgets: messages go through the ``message`` signal and
the result is handed to ``on_done`` in the main thread (``finished``). Keys are read in the main
thread before the task starts (the QGIS master password dialog).
"""

from __future__ import annotations

import re
import traceback
from collections.abc import Callable
from typing import Any

from qgis.core import QgsTask
from qgis.PyQt.QtCore import pyqtSignal

PROGRESS = re.compile(r"^(\d+)/(\d+)\b")


class FunctionTask(QgsTask):
    """Runs ``function(task)`` in the background; ``on_done(task)`` in the main thread."""

    message = pyqtSignal(str)

    def __init__(self, description: str, function: Callable[[FunctionTask], Any], on_done: Callable):
        super().__init__(description, QgsTask.Flag.CanCancel)
        self.function = function
        self.on_done = on_done
        self.result: Any = None
        self.error: BaseException | None = None
        self.error_text = ""

    # -- helpers for the function ---------------------------------------------------------

    def stopped(self) -> bool:
        return self.isCanceled()

    def say(self, text: str) -> None:
        """Progress line from the core (``n/m …``) → progress bar and message."""
        found = PROGRESS.match(text)
        if found and int(found.group(2)):
            self.setProgress(100.0 * int(found.group(1)) / int(found.group(2)))
        self.message.emit(text)

    # -- QgsTask ----------------------------------------------------------------------------

    def run(self) -> bool:  # worker thread
        try:
            self.result = self.function(self)
            return True
        except Exception as error:  # noqa: BLE001 - shown to the user in finished()
            self.error = error
            self.error_text = traceback.format_exc()
            return False

    def finished(self, result: bool) -> None:  # main thread
        self.on_done(self)
