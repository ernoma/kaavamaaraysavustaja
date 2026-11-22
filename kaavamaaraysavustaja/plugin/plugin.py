"""Minimal QGIS plugin: adds a menu action that shows the active knowledge base version."""

from __future__ import annotations

from qgis.PyQt.QtWidgets import QAction, QMessageBox

from kaavamaaraysavustaja import __version__

MENU = "&Kaavamääräysavustaja"


class KaavamaaraysavustajaPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action: QAction | None = None

    def initGui(self) -> None:  # noqa: N802 (QGIS API name)
        self.action = QAction("Tietoja Kaavamääräysavustajasta", self.iface.mainWindow())
        self.action.triggered.connect(self.show_about)
        self.iface.addPluginToMenu(MENU, self.action)

    def unload(self) -> None:
        if self.action is not None:
            self.iface.removePluginMenu(MENU, self.action)
            self.action.deleteLater()
            self.action = None

    def show_about(self) -> None:
        try:
            from kaavamaaraysavustaja.knowledge import load_manifest

            manifest = load_manifest()
            knowledge_text = f"Tietopohja {manifest['tietopohja']}"
        except Exception as exc:  # pragma: no cover - shown to the user
            knowledge_text = f"Tietopohjaa ei voitu ladata: {exc}"
        QMessageBox.information(
            self.iface.mainWindow(),
            "Kaavamääräysavustaja",
            f"Kaavamääräysavustaja {__version__} (kehitysversio)\n{knowledge_text}",
        )
