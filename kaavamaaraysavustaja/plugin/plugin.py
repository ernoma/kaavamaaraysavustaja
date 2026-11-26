"""QGIS plugin: the Kaavamääräysavustaja dock, API keys and the about dialog.

``kma_deps`` (language model SDKs installed with ``pip install --target``, ADR-0002) is added to
the end of ``sys.path`` so that QGIS's own packages keep precedence.
"""

from __future__ import annotations

import sys
from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from kaavamaaraysavustaja import __version__

MENU = "&Kaavamääräysavustaja"


def add_dependency_path() -> Path | None:
    """``<profile>/python/kma_deps`` to the end of ``sys.path`` (ADR-0002, option C)."""
    path = Path(QgsApplication.qgisSettingsDirPath()) / "python" / "kma_deps"
    if path.is_dir() and str(path) not in sys.path:
        sys.path.append(str(path))
    return path if path.is_dir() else None


class KaavamaaraysavustajaPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions: list[QAction] = []
        self.dock = None
        self.dock_action: QAction | None = None
        add_dependency_path()

    def initGui(self) -> None:  # noqa: N802 (QGIS API name)
        main = self.iface.mainWindow()
        self.dock_action = QAction(
            QgsApplication.getThemeIcon("/mActionOpenTable.svg"), "Kaavamääräysavustaja", main
        )
        self.dock_action.setCheckable(True)
        self.dock_action.toggled.connect(self.toggle_dock)
        keys = QAction("API-avaimet…", main)
        keys.triggered.connect(self.show_keys)
        about = QAction("Tietoja Kaavamääräysavustajasta", main)
        about.triggered.connect(self.show_about)
        for action in (self.dock_action, keys, about):
            self.iface.addPluginToMenu(MENU, action)
            self.actions.append(action)
        self.iface.addToolBarIcon(self.dock_action)

    def unload(self) -> None:
        if self.dock is not None:
            self.dock.shutdown()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.dock_action is not None:
            self.iface.removeToolBarIcon(self.dock_action)
        for action in self.actions:
            self.iface.removePluginMenu(MENU, action)
            action.deleteLater()
        self.actions = []
        self.dock_action = None

    def toggle_dock(self, visible: bool) -> None:
        if self.dock is None:
            from kaavamaaraysavustaja.plugin.dock import AvustajaDock

            self.dock = AvustajaDock(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
            self.dock.visibilityChanged.connect(self._dock_visibility)
        self.dock.setVisible(visible)

    def _dock_visibility(self, visible: bool) -> None:
        if self.dock_action is not None and self.dock_action.isChecked() != visible:
            self.dock_action.blockSignals(True)
            self.dock_action.setChecked(visible)
            self.dock_action.blockSignals(False)

    def show_keys(self) -> None:
        from kaavamaaraysavustaja.plugin.dialogs import KeysDialog

        KeysDialog(self.iface.mainWindow()).exec()

    def show_about(self) -> None:
        try:
            from kaavamaaraysavustaja.knowledge import load_manifest

            manifest = load_manifest()
            knowledge_text = f"Tietopohja {manifest['tietopohja']}"
        except Exception as exc:  # pragma: no cover - shown to the user
            knowledge_text = f"Tietopohjaa ei voitu ladata: {exc}"
        from kaavamaaraysavustaja.core.llm.providers import sdk_available

        sdks = ", ".join(f"{n} {'✓' if sdk_available(n) else 'puuttuu'}" for n in ("claude", "mistral"))
        QMessageBox.information(
            self.iface.mainWindow(),
            "Kaavamääräysavustaja",
            f"Kaavamääräysavustaja {__version__} (kokeiluversio, vaihe 3a)\n{knowledge_text}\n"
            f"Kielimallien SDK:t: {sdks}\nkma_deps: {add_dependency_path() or 'ei asennettu'}",
        )
