"""Dialogs of the dock: cost estimate before a model call, content preview, API keys."""

from __future__ import annotations

import os
from collections.abc import Callable

from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from kaavamaaraysavustaja.plugin import auth


class TextDialog(QDialog):
    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 700)
        layout = QVBoxLayout(self)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class EstimateDialog(QDialog):
    """Shown before every model run (ADR-0013): estimate, budget limit and, on request, the content."""

    def __init__(self, plan, budget: float, preview: Callable[[], str], show_content: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kielimallin kustannusarvio")
        self.preview = preview
        layout = QVBoxLayout(self)
        e = plan.estimate
        lines = [
            f"<b>Kielimalli:</b> {plan.provider} ({plan.model})",
            f"<b>Kutsuja:</b> {e.units} (yksiköt, joita sääntöpohjainen vaihe ei ratkaissut)",
            f"<b>Arvio:</b> noin {e.usd:.2f} $" + ("" if e.verified_prices else " (hinta vahvistamaton)"),
            f"<small>{e.describe()}</small>",
        ]
        if plan.reuse:
            lines.append(f"Aiempia vastauksia käytetään uudelleen ilman kustannusta: {len(plan.reuse)}.")
        lines.append(
            "Mallille lähetetään vain määräysteksti ja tietopohjan konteksti (ei PDF:iä, kuvia eikä avaimia)."
        )
        info = QLabel("<br>".join(lines))
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self.budget = QDoubleSpinBox()
        self.budget.setRange(0.01, 100.0)
        self.budget.setDecimals(2)
        self.budget.setSuffix(" $")
        self.budget.setValue(budget)
        form.addRow("Budjettiraja tälle ajolle", self.budget)
        layout.addLayout(form)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        self.budget.valueChanged.connect(lambda _: self._update_warning(e.usd))
        self._update_warning(e.usd)
        self.content = QPlainTextEdit()
        self.content.setReadOnly(True)
        self.content.setVisible(False)
        layout.addWidget(self.content, 1)
        toggle = QPushButton("Näytä lähetettävä sisältö")
        toggle.clicked.connect(self.toggle_content)
        layout.addWidget(toggle)
        buttons = QDialogButtonBox()
        buttons.addButton("Lähetä kielimallille", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Peruuta (vain sääntöpohjainen)", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if show_content:
            self.toggle_content()
        self.resize(760, 520 if show_content else 300)

    def _update_warning(self, usd: float) -> None:
        if usd > self.budget.value():
            self.warning.setText(
                "⚠ Arvio ylittää budjettirajan: kun raja tulee vastaan, loput yksiköt jäävät sääntöpohjaisiksi."
            )
        else:
            self.warning.setText("")

    def toggle_content(self) -> None:
        if not self.content.toPlainText():
            self.content.setPlainText(self.preview())
        self.content.setVisible(not self.content.isVisible())
        if self.content.isVisible():
            self.resize(max(self.width(), 900), max(self.height(), 650))


class KeysDialog(QDialog):
    """API keys in the QGIS authentication database (ADR-0004). Keys are never shown."""

    SERVICES = [("claude", "Claude (Anthropic)"), ("mistral", "Mistral"), ("syke", "Syke Ryhti (validointi)")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kaavamääräysavustaja – API-avaimet")
        layout = QVBoxLayout(self)
        note = QLabel(
            "Avaimet tallennetaan QGISin salattuun tunnistetietovarastoon (pääsalasana). Niitä ei "
            "kirjoiteta projektiin, muunnokseen eikä lokiin. Kehityksessä käytetään ympäristömuuttujaa, "
            "jos varastossa ei ole avainta."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        grid = QGridLayout()
        self.status: dict[str, QLabel] = {}
        self.fields: dict[str, QLineEdit] = {}
        for row, (service, title) in enumerate(self.SERVICES):
            grid.addWidget(QLabel(f"<b>{title}</b>"), row, 0)
            status = QLabel()
            self.status[service] = status
            grid.addWidget(status, row, 1)
            field = QLineEdit()
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText("uusi avain")
            self.fields[service] = field
            grid.addWidget(field, row, 2)
            save = QPushButton("Tallenna")
            save.clicked.connect(lambda _=False, s=service: self.save(s))
            grid.addWidget(save, row, 3)
            remove = QPushButton("Poista")
            remove.clicked.connect(lambda _=False, s=service: self.remove(s))
            grid.addWidget(remove, row, 4)
        layout.addLayout(grid)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    @staticmethod
    def describe(service: str) -> str:
        if auth.stored_authcfg_id(service):
            return "tallennettu tunnistetietovarastoon"
        if os.environ.get(auth.KEYS[service].env_var):
            return f"ympäristömuuttuja {auth.KEYS[service].env_var} (kehitys)"
        return "puuttuu"

    def refresh(self) -> None:
        for service, label in self.status.items():
            label.setText(self.describe(service))

    def save(self, service: str) -> None:
        value = self.fields[service].text().strip()
        if not value:
            return
        try:
            auth.store_api_key(service, value)
        except auth.AuthError as error:
            QMessageBox.warning(self, "API-avaimet", str(error))
        self.fields[service].clear()
        self.refresh()

    def remove(self, service: str) -> None:
        try:
            auth.remove_api_key(service)
        except auth.AuthError as error:
            QMessageBox.warning(self, "API-avaimet", str(error))
        self.refresh()
