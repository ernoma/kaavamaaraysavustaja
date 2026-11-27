"""The dock of the testable version (vaihe 3a, ADR-0016, ADR-0017; feedback round 1 in 0.3.1).

Tabs: 1 Syöte (input, mode, plan level, policy choices explained, language model), 2 Ehdotus
(units with status icons, the proposal in the planner's language and technically, its Ryhti
JSON, rationale, rule results, interpretation questions with who resolved them and how the
answer can be changed) and 3 Vienti (project, report, Ryhti JSON, optional Arho YAML,
optional Syke validation; existing files are kept unless overwriting is chosen).

All conversion logic is in ``core/workflow.py``; this module only builds widgets and runs the
work in ``QgsTask``s (``plugin/tasks.py``). The dock works without ``iface`` (tests).
"""

from __future__ import annotations

import copy
import html
from pathlib import Path

from qgis.core import Qgis, QgsApplication, QgsSettings
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QFontDatabase
from qgis.PyQt.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from kaavamaaraysavustaja.core import workflow
from kaavamaaraysavustaja.core.model import ConversionProject
from kaavamaaraysavustaja.plugin.tasks import FunctionTask

SETTINGS = "kaavamaaraysavustaja/telakka/"
MODES = [(value, text) for value, text in workflow.MODE_TEXT.items()]
LEVELS = [("yleiskaava", "Yleiskaava"), ("asemakaava", "Asemakaava"), ("maakuntakaava", "Maakuntakaava")]
LLMS = [("ei", "Ei kielimallia (sääntöpohjainen)"), ("claude", "Claude"), ("mistral", "Mistral")]
INPUT_KINDS = [
    ("yksi", "Yksi määräys: otsikko ja teksti erikseen"),
    ("selite", "Liitetty teksti: otsikko ja kirjaintunnus tekstissä (yksi tai useampi merkintä)"),
]
FILTERS = [
    ("kaikki", "Kaikki"),
    ("kysymys", "Avoimet kysymykset"),
    ("ongelma", "Virheet ja varoitukset"),
    ("valmis", "Valmiit"),
]
SCOPES = [("merkinta", "Vain tämä merkintä"), ("projekti", "Kaikki samankaltaiset tässä muunnoksessa")]
EXPORT_LABELS = {
    "projekti": "Muunnosprojekti",
    "markdown": "Muunnosraportti (Markdown)",
    "html": "Muunnosraportti (HTML)",
    "ryhti": "Ryhti-JSON",
    "arho": "Arho-kirjasto",
}
SINGLE_HELP = (
    "Kirjoita otsikko ja halutessasi kirjaintunnus omiin kenttiinsä ja määräysteksti alle. "
    "Tyhjä rivi erottaa kappaleet."
)
LEGEND_HELP = (
    "Liitä teksti, jossa merkinnän otsikko on omalla rivillään ISOIN KIRJAIMIN ja kirjaintunnus "
    "otsikon alussa; määräysteksti seuraa otsikkoa. Sopii yhdelle tai usealle merkinnälle: otsikko ja "
    "tunnus luetaan tekstistä, joten niille ei ole omia kenttiä. Yleismääräykset kirjoitetaan otsikon "
    "YLEISMÄÄRÄYKSET alle."
)
SINGLE_PLACEHOLDER = (
    "Kirjoita tai liitä määräyksen teksti. Voimassa olevan määräyksen teksti siirtyy merkki merkiltä; "
    "uuden määräyksen tekstiä ei muuteta."
)
POLICY_INTRO = (
    "Linjaukset ovat tulkintaperiaatteita, joita avustaja noudattaa koko muunnoksessa, esimerkiksi "
    "säilytetäänkö lähteen kirjaintunnus. Oletuksena on suositeltu vaihtoehto. Muuta valintaa vain, jos "
    "tämä muunnos tarvitsee toisen tulkinnan: valinta tallentuu muunnokseen ja raporttiin, ja se näkyy "
    "kysymyskorteissa. Lukittu 🔒 linjaus on Tampereen päätös, eikä sitä voi muuttaa."
)


def _e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _wrapped(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


def _narrow(combo: QComboBox) -> QComboBox:
    """Long items must not make the dock wide: the combo shrinks, the full text is in the list."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(16)
    return combo


class _OptionRow(QWidget):
    """A radio button with a wrapping label (QRadioButton does not wrap long texts)."""

    def __init__(self, text: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.button = QRadioButton()
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignTop)
        self.label = _wrapped(_e(text))
        layout.addWidget(self.label, 1)

    def mousePressEvent(self, event):  # noqa: N802 (Qt API name)
        if self.button.isEnabled():
            self.button.setChecked(True)
        super().mousePressEvent(event)


class AvustajaDock(QDockWidget):
    def __init__(self, iface=None, parent=None):
        super().__init__("Kaavamääräysavustaja", parent)
        self.setObjectName("KaavamaaraysavustajaDock")
        self.iface = iface
        self.settings = QgsSettings()
        self.kb = None
        self.glossary = None
        self.policy_opts: list[workflow.PolicyOption] = []
        self.project: ConversionProject | None = None
        self.previous: ConversionProject | None = None  # model answers reused on re-runs
        self.decisions: list = []
        self.request: workflow.ConversionRequest | None = None
        self.tasks: list[FunctionTask] = []
        self.policy_boxes: dict[str, QComboBox] = {}
        self.policy_effects: dict[str, QLabel] = {}
        self.option_group: QButtonGroup | None = None
        self.view: workflow.QuestionView | None = None  # the question card shown
        self.last_report = None
        self.last_notice = ""
        self.last_export: workflow.ExportResult | None = None
        self._confirmed_budget = 2.0
        self._stem_suggestion: str | None = None
        self._texts: dict[str, str] = {}  # input type -> its text while the other type is shown
        self._shown_kind = INPUT_KINDS[0][0]
        self.run_synchronously = False  # tests: run tasks in the calling thread
        self._map_timer = QTimer(self)
        self._map_timer.setSingleShot(True)
        self._map_timer.setInterval(500)
        self._map_timer.timeout.connect(self._refresh_maps)

        root = QWidget()
        layout = QVBoxLayout(root)
        self.header = _wrapped()
        layout.addWidget(self.header)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.status = _wrapped()
        row = QHBoxLayout()
        row.addWidget(self.progress, 1)
        self.cancel_button = QPushButton("Keskeytä")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_tasks)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        layout.addWidget(self.status)
        self.setWidget(root)

        try:
            from kaavamaaraysavustaja.knowledge.base import KnowledgeBase

            self.kb = KnowledgeBase.load()
            self.policy_opts = workflow.policy_options(self.kb)
            self.glossary = workflow.glossary(self.kb)
        except Exception as error:  # noqa: BLE001 - shown to the user
            self.kb = None
            self.header.setText(f"<b>Tietopohjaa ei voitu ladata:</b> {_e(error)}")
            return
        self.tabs.addTab(self._input_tab(), "1 Syöte")
        self.tabs.addTab(self._review_tab(), "2 Ehdotus")
        self.tabs.addTab(self._export_tab(), "3 Vienti")
        self._restore_settings()
        self._update_header()

    # ==================================================================================
    # 1 Syöte

    def _input_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        form = QFormLayout()
        self.input_form = form
        self.mode = QComboBox()
        for value, text in MODES:
            self.mode.addItem(text, value)
        self.mode.setToolTip(
            "Uusi määräys: avustaja ehdottaa rakenteen eikä muuta tekstiä. Voimassa oleva määräys: "
            "teksti siirtyy merkki merkiltä lähteen mukaisena (VOOKA = voimassa olevan kaavan muunnos)."
        )
        self.mode.currentIndexChanged.connect(self._update_header)
        form.addRow("Tila", self.mode)
        self.level = QComboBox()
        for value, text in LEVELS:
            self.level.addItem(text, value)
        form.addRow("Kaavataso", self.level)
        self.input_kind = _narrow(QComboBox())
        for value, text in INPUT_KINDS:
            self.input_kind.addItem(text, value)
        self.input_kind.currentIndexChanged.connect(self._update_input_fields)
        form.addRow("Syöte", self.input_kind)
        self.input_help = _wrapped()
        self.input_help.setTextFormat(Qt.TextFormat.RichText)
        form.addRow(self.input_help)
        # The format example in a marked box so that it is not mistaken for input (P2-01).
        lines = "<br>".join(_e(line) for line in workflow.LEGEND_EXAMPLE.splitlines())
        self.legend_example = _wrapped(
            f"<i>Esimerkki yhdestä merkinnästä (malli, ei syötettä):</i><br><tt>{lines}</tt>"
        )
        self.legend_example.setTextFormat(Qt.TextFormat.RichText)
        self.legend_example.setStyleSheet("QLabel { border: 1px dashed gray; padding: 4px; }")
        form.addRow(self.legend_example)
        self.group_kind = QComboBox()
        self.group_kind.addItem("Kaavakohteen määräys (merkintä)", "merkinta")
        self.group_kind.addItem("Yleismääräys (koko kaava-alue)", "yleismaarays")
        form.addRow("Ryhmän tyyppi", self.group_kind)
        self.heading = QLineEdit()
        self.heading.setPlaceholderText("esim. Kerrostalovaltainen asuntoalue")
        form.addRow("Otsikko", self.heading)
        self.letter_code = QLineEdit()
        self.letter_code.setPlaceholderText("valinnainen, esim. AK")
        form.addRow("Kirjaintunnus", self.letter_code)
        self.map_choice = _narrow(QComboBox())
        self.map_choice.setToolTip(
            "Rajaa muunnoksen valitun kartan merkintöihin. Kartan nimi kirjataan muunnosraporttiin ja "
            "Arho-kirjaston kuvaukseen, ja merkinnät ryhmitellään kirjastossa kartan mukaan."
        )
        form.addRow("Kartta", self.map_choice)
        self.map_help = _wrapped()
        form.addRow(self.map_help)
        layout.addLayout(form)
        layout.addWidget(QLabel("Määräysteksti (tyhjä rivi = kappaleraja):"))
        self.text = QPlainTextEdit()
        self.text.setMinimumHeight(140)
        self.text.textChanged.connect(self._text_changed)
        layout.addWidget(self.text, 1)
        files = QHBoxLayout()
        open_text = QPushButton("Avaa tekstitiedosto…")
        open_text.clicked.connect(self.open_text_file)
        files.addWidget(open_text)
        open_project = QPushButton("Avaa aiempi muunnos (*.kma.json)…")
        open_project.clicked.connect(self.open_project_file)
        files.addWidget(open_project)
        layout.addLayout(files)
        layout.addWidget(self._policy_section())

        llm = QGroupBox("Kielimalli (valinnainen)")
        lform = QFormLayout(llm)
        self.llm = QComboBox()
        for value, text in LLMS:
            self.llm.addItem(text, value)
        lform.addRow("Kielimalli", self.llm)
        self.budget = QDoubleSpinBox()
        self.budget.setRange(0.01, 100.0)
        self.budget.setDecimals(2)
        self.budget.setSuffix(" $")
        self.budget.setValue(2.0)
        lform.addRow("Budjettiraja ajoa kohden", self.budget)
        self.show_content = QCheckBox("Näytä lähetettävä sisältö ennen lähetystä")
        lform.addRow(self.show_content)
        keys = QPushButton("Avaimet…")
        keys.clicked.connect(self.open_keys)
        lform.addRow(keys)
        layout.addWidget(llm)

        buttons = QHBoxLayout()
        self.convert_button = QPushButton("Muunna")
        self.convert_button.setDefault(True)
        self.convert_button.clicked.connect(self.convert)
        buttons.addWidget(self.convert_button)
        clear = QPushButton("Uusi muunnos")
        clear.setToolTip("Tyhjentää syötteen, ratkaisut ja tuloksen.")
        clear.clicked.connect(self.new_conversion)
        buttons.addWidget(clear)
        outer.addLayout(buttons)
        self._update_input_fields()
        return page

    def _set_row_visible(self, field: QWidget, visible: bool) -> None:
        """Qt 5 has no QFormLayout.setRowVisible: hide the label and the field."""
        label = self.input_form.labelForField(field)
        if label is not None:
            label.setVisible(visible)
        field.setVisible(visible)

    def _update_input_fields(self) -> None:
        kind = self.input_kind.currentData()
        single = kind == "yksi"
        if kind != self._shown_kind:  # each input type keeps its own text (P2-01)
            self._texts[self._shown_kind] = self.text.toPlainText()
            self.text.setPlainText(self._texts.get(kind, ""))
            self._shown_kind = kind
        for widget in (self.group_kind, self.heading, self.letter_code):
            self._set_row_visible(widget, single)
        self.legend_example.setVisible(not single)
        if single:
            self.input_help.setText(_e(SINGLE_HELP))
            self.text.setPlaceholderText(SINGLE_PLACEHOLDER)
        else:
            self.input_help.setText(_e(LEGEND_HELP))
            self.text.setPlaceholderText("Liitä teksti tähän. Muoto: ks. esimerkki yllä.")
        self._refresh_maps()

    def _text_changed(self) -> None:
        if self.input_kind.currentData() == "selite":
            self._map_timer.start()

    def _refresh_maps(self) -> None:
        """The map choice is shown only when the pasted text has several maps (P1-02, P1-03)."""
        legend = self.input_kind.currentData() == "selite"
        maps = workflow.legend_maps(self.text.toPlainText()) if legend else []
        current = self.map_choice.currentData()
        self.map_choice.blockSignals(True)
        self.map_choice.clear()
        self.map_choice.addItem("Kaikki kartat", None)
        for title in maps:
            self.map_choice.addItem(title, title)
        self.map_choice.setCurrentIndex(max(0, self.map_choice.findData(current)) if current else 0)
        self.map_choice.blockSignals(False)
        hint = workflow.map_hint(maps)
        self._set_row_visible(self.map_choice, bool(hint))
        self.map_help.setText(hint)
        self.map_help.setVisible(bool(hint))

    # -- policy choices (P1-04) ------------------------------------------------------------

    def _policy_section(self) -> QWidget:
        box = QGroupBox()
        layout = QVBoxLayout(box)
        self.policy_toggle = QToolButton()
        self.policy_toggle.setCheckable(True)
        self.policy_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.policy_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.policy_toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self.policy_toggle.toggled.connect(self._toggle_policies)
        layout.addWidget(self.policy_toggle)
        layout.addWidget(_wrapped(POLICY_INTRO))
        self.policy_body = QWidget()
        body = QVBoxLayout(self.policy_body)
        body.setContentsMargins(0, 0, 0, 0)
        for option in self.policy_opts:
            body.addWidget(self._policy_row(option))
        self.policy_body.setVisible(False)
        layout.addWidget(self.policy_body)
        self._update_policy_summary()
        return box

    def _policy_row(self, option: workflow.PolicyOption) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 0)
        title = QLabel(f"<b>{_e(option.title)}</b>" + (" 🔒" if option.locked else ""))
        title.setToolTip(f"Linjaus {option.id}: {option.question}")
        layout.addWidget(title)
        if option.explanation:
            layout.addWidget(_wrapped(_e(option.explanation)))
        combo = _narrow(QComboBox())
        for value in option.options:
            combo.addItem(
                _capital(option.label(value)) + (" (suositus)" if value == option.default else ""), value
            )
            combo.setItemData(combo.count() - 1, option.effect(value), Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentIndex(max(0, combo.findData(option.default)))
        combo.setEnabled(option.changeable)
        combo.setToolTip(f"Linjaus {option.id}")
        layout.addWidget(combo)
        effect = _wrapped()
        layout.addWidget(effect)
        if option.locked:
            layout.addWidget(_wrapped("🔒 " + _e(option.lock_reason)))
        elif len(option.options) < 2:
            layout.addWidget(
                _wrapped("<i>Muita vaihtoehtoja ei ole vielä käytettävissä tässä versiossa.</i>")
            )
        self.policy_boxes[option.id] = combo
        self.policy_effects[option.id] = effect
        combo.currentIndexChanged.connect(lambda _=0, o=option: self._policy_changed(o))
        self._policy_changed(option, summary=False)
        return row

    def _policy_changed(self, option: workflow.PolicyOption, summary: bool = True) -> None:
        value = self.policy_boxes[option.id].currentData()
        self.policy_effects[option.id].setText(f"<i>Vaikutus:</i> {_e(option.effect(value))}")
        if summary:
            self._update_policy_summary()

    def _update_policy_summary(self) -> None:
        self.policy_toggle.setText(
            "Linjausvalinnat – " + workflow.policy_summary(self.policy_opts, self._overrides())
        )

    def _toggle_policies(self, checked: bool) -> None:
        self.policy_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.policy_body.setVisible(checked)

    def _overrides(self) -> dict[str, str]:
        selected = {pid: box.currentData() for pid, box in self.policy_boxes.items()}
        return workflow.policy_overrides(self.policy_opts, selected)

    def _update_header(self) -> None:
        if self.kb is None:
            return
        text, details = workflow.header(self.kb, self.mode.currentData())
        self.header.setText(text)
        self.header.setToolTip(details)

    def read_request(self) -> workflow.ConversionRequest:
        legend = self.input_kind.currentData() == "selite"
        if legend:
            self._refresh_maps()  # the text may have changed just before Muunna
        return workflow.ConversionRequest(
            text=self.text.toPlainText(),
            heading=None if legend else self.heading.text(),
            letter_code=None if legend else self.letter_code.text(),
            kind=self.group_kind.currentData(),
            legend=legend,
            map=self.map_choice.currentData() if legend else None,
            mode=self.mode.currentData(),
            plan_level=self.level.currentData(),
            overrides=self._overrides(),
            decisions=list(self.decisions),
        )

    def open_text_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Avaa tekstitiedosto", "", "Teksti (*.txt *.md);;Kaikki (*)"
        )
        if path:
            self.text.setPlainText(Path(path).read_text(encoding="utf-8-sig"))

    def open_project_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Avaa muunnosprojekti", "", "Muunnosprojekti (*.kma.json)"
        )
        if path:
            self.load_project(ConversionProject.load(Path(path)))

    def load_project(self, project: ConversionProject) -> None:
        """An earlier conversion: its decisions and model answers are kept on re-runs."""
        self.previous = project
        self.decisions = list(project.decisions)
        self.mode.setCurrentIndex(max(0, self.mode.findData(project.meta.mode)))
        self.level.setCurrentIndex(max(0, self.level.findData(project.meta.plan_level)))
        changeable = {o.id for o in self.policy_opts if o.changeable}
        for choice in project.policy_choices:
            box = self.policy_boxes.get(choice.id)
            if box is not None and choice.id in changeable:
                box.setCurrentIndex(max(0, box.findData(choice.option)))
        if len(project.units) == 1:
            unit = project.units[0]
            self.input_kind.setCurrentIndex(self.input_kind.findData("yksi"))
            self.heading.setText(unit.heading_raw or unit.heading or "")
            self.letter_code.setText(unit.letter_code_raw or "")
            self.group_kind.setCurrentIndex(max(0, self.group_kind.findData(unit.kind)))
            self.text.setPlainText(unit.raw_text)
        else:
            self.input_kind.setCurrentIndex(self.input_kind.findData("selite"))
            self.notify(
                "Monen yksikön muunnos avattu. Liitä teksti uudelleen Syöte-välilehdelle, jos haluat ajaa "
                "sen uudelleen (ratkaisut ja kielimallin vastaukset säilyvät)."
            )
        self.set_project(project)

    def new_conversion(self) -> None:
        self.project = self.previous = None
        self.decisions = []
        self.heading.clear()
        self.letter_code.clear()
        self.text.clear()
        self._texts = {}
        self.units.clear()
        self.detail.clear()
        self._show_questions(None)
        self._show_json()
        if self.export_stem.text() == (self._stem_suggestion or ""):
            self.export_stem.clear()
        self._stem_suggestion = None
        self.status.setText("")

    # ==================================================================================
    # Conversion (QgsTask)

    def convert(self) -> None:
        """Rule-based conversion; then, if chosen, the cost estimate and the model run."""
        try:
            request = self.read_request()
            workflow.build_units(request)
        except workflow.InputError as error:
            self.notify(str(error), warning=True)
            return
        self.request = request
        if self.project is not None:
            self.previous = self.project
        self._save_settings()
        kb = self.kb

        def work(task: FunctionTask):
            return workflow.rule_based(kb, request)

        self.start_task("Kaavamääräysavustaja: sääntöpohjainen muunnos", work, self._rule_based_done)

    def _rule_based_done(self, task: FunctionTask) -> None:
        if task.error is not None:
            self.notify(f"Muunnos epäonnistui: {task.error}", warning=True, details=task.error_text)
            return
        project = task.result
        self.set_project(project)
        skipped = workflow.input_warnings(project)
        note = ""
        if skipped:
            self.notify(
                "Liitetystä tekstistä ohitettiin rivejä, joita ei tunnistettu merkinnöiksi: "
                + "; ".join(skipped[:3])
                + (" …" if len(skipped) > 3 else ""),
                warning=True,
            )
            note = f" Tekstistä ohitettiin {len(skipped)} riviä (otsikkoa ei tunnistettu)."
        provider = self.llm.currentData()
        if provider == "ei":
            self.status.setText(workflow.summary_text(project) + " Sääntöpohjainen muunnos." + note)
            return
        self.run_model(project, provider)

    def run_model(self, project: ConversionProject, provider: str) -> None:
        from kaavamaaraysavustaja.core.llm.base import LLMError
        from kaavamaaraysavustaja.core.llm.providers import create_provider
        from kaavamaaraysavustaja.plugin import auth

        summary = workflow.summary_text(project)
        try:
            key = auth.load_api_key(provider)
        except auth.AuthError as error:
            key = None
            self.notify(str(error), warning=True)
        reason = workflow.llm_unavailable_reason(provider, key)
        if reason:
            self.notify(reason, warning=True)
            self.status.setText(summary + " Sääntöpohjainen muunnos (kielimalli ei käytössä).")
            return
        plan = workflow.llm_plan(self.kb, project, provider, previous=self.previous)
        budget = self.budget.value()
        if plan.estimate.units:
            if not self.confirm_estimate(plan, project):
                self.status.setText(summary + " Kielimallia ei kutsuttu.")
                return
            budget = self._confirmed_budget
        elif not plan.reuse:
            self.status.setText(
                summary + " Kaikki yksiköt ratkesivat sääntöpohjaisesti; kielimallia ei tarvittu."
            )
            return
        try:
            model_provider = create_provider(provider, plan.model, api_key=key)
        except LLMError as error:
            self.notify(str(error), warning=True)
            return
        working = copy.deepcopy(project)
        kb, decisions = self.kb, list(self.decisions)

        def work(task: FunctionTask):
            report = workflow.run_llm(
                kb,
                working,
                model_provider,
                plan.model,
                budget=budget,
                reuse=plan.reuse,
                decisions=decisions,
                should_stop=task.stopped,
                progress=task.say,
            )
            return working, report

        self.start_task(f"Kaavamääräysavustaja: kielimalli {provider}", work, self._model_done)

    def confirm_estimate(self, plan, project) -> bool:
        from kaavamaaraysavustaja.plugin.dialogs import EstimateDialog

        dialog = EstimateDialog(
            plan,
            self.budget.value(),
            lambda: workflow.request_preview(self.kb, project, reuse=plan.reuse),
            self.show_content.isChecked(),
            self,
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        self._confirmed_budget = dialog.budget.value()
        return accepted

    def _model_done(self, task: FunctionTask) -> None:
        if task.error is not None:
            self.notify(f"Kielimalliajo epäonnistui: {task.error}", warning=True, details=task.error_text)
            return
        project, report = task.result
        self.last_report = report
        self.set_project(project)
        t = report.totals()
        parts = [
            f"Kielimalli: {t['kutsuja']} kutsua, {t['kustannus_usd']:.2f} $",
            f"uudelleenkäytetty {t['uudelleenkaytettyja']}",
        ]
        if t["budjetin_takia_ohitettuja"]:
            parts.append(f"budjettirajan takia sääntöpohjaisiksi {t['budjetin_takia_ohitettuja']}")
        if t["keskeytettyja"]:
            parts.append(f"keskeytetty {t['keskeytettyja']}")
        if t["virheita"]:
            parts.append(f"virheitä {t['virheita']}")
        self.status.setText(workflow.summary_text(project) + " " + ", ".join(parts) + ".")

    def start_task(self, description: str, function, on_done) -> None:
        task = FunctionTask(description, function, lambda t: self._task_done(t, on_done))
        task.message.connect(self.status.setText)
        task.progressChanged.connect(lambda value: self.progress.setValue(int(value)))
        self.tasks.append(task)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.convert_button.setEnabled(False)
        self.status.setText(description + " …")
        if self.run_synchronously:
            ok = task.run()
            task.finished(ok)
        else:
            QgsApplication.taskManager().addTask(task)

    def _task_done(self, task: FunctionTask, on_done) -> None:
        if task in self.tasks:
            self.tasks.remove(task)
        if not self.tasks:
            self.progress.setVisible(False)
            self.cancel_button.setEnabled(False)
            self.convert_button.setEnabled(True)
        on_done(task)

    def cancel_tasks(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        self.status.setText(
            "Keskeytetään: käsittelyssä oleva kutsu valmistuu, loput jäävät sääntöpohjaisiksi."
        )

    # ==================================================================================
    # 2 Ehdotus

    def _review_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        top.addWidget(QLabel("Suodata:"))
        self.filter = QComboBox()
        for value, text in FILTERS:
            self.filter.addItem(text, value)
        self.filter.currentIndexChanged.connect(self._fill_units)
        top.addWidget(self.filter, 1)
        layout.addLayout(top)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.units = QListWidget()
        self.units.currentItemChanged.connect(self._unit_selected)
        splitter.addWidget(self.units)
        self.detail_tabs = QTabWidget()
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        self.detail_tabs.addTab(self.detail, "Ehdotus")
        self.detail_tabs.addTab(self._json_page(), "Ryhti-JSON")
        splitter.addWidget(self.detail_tabs)
        questions = QScrollArea()
        questions.setWidgetResizable(True)
        questions.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # texts wrap
        questions.setWidget(self._questions_box())
        splitter.addWidget(questions)
        splitter.setSizes([140, 340, 300])
        layout.addWidget(splitter, 1)
        self._show_questions(None)
        return page

    def _json_page(self) -> QWidget:
        """Ryhti JSON of the selected unit or the whole conversion, as exported (P1-07)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("Näytä:"))
        self.json_scope = QComboBox()
        self.json_scope.addItem("Valittu yksikkö", "yksikko")
        self.json_scope.addItem("Koko muunnos", "kaikki")
        self.json_scope.currentIndexChanged.connect(self._show_json)
        row.addWidget(self.json_scope, 1)
        copy_button = QPushButton("Kopioi")
        copy_button.setToolTip("Kopioi näkyvä Ryhti-JSON leikepöydälle.")
        copy_button.clicked.connect(self.copy_json)
        row.addWidget(copy_button)
        layout.addLayout(row)
        self.json_notes = _wrapped()
        layout.addWidget(self.json_notes)
        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.json_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout.addWidget(self.json_view, 1)
        return page

    def _questions_box(self) -> QWidget:
        questions = QGroupBox("Tulkintakysymykset")
        qlayout = QVBoxLayout(questions)
        self.question = _narrow(QComboBox())
        self.question.currentIndexChanged.connect(self._question_selected)
        qlayout.addWidget(self.question)
        self.question_text = _wrapped()
        qlayout.addWidget(self.question_text)
        self.resolution = _wrapped()
        qlayout.addWidget(self.resolution)
        self.options_box = QVBoxLayout()
        qlayout.addLayout(self.options_box)
        self.policy_switch_row = QWidget()
        switch = QHBoxLayout(self.policy_switch_row)
        switch.setContentsMargins(0, 0, 0, 0)
        self.policy_switch = _narrow(QComboBox())
        switch.addWidget(self.policy_switch, 1)
        self.policy_switch_button = QPushButton("Vaihda linjaus ja aja uudelleen")
        self.policy_switch_button.setToolTip(
            "Vaihtaa linjausvalinnan tälle muunnokselle (sama kuin Syöte-välilehden linjausvalinnoissa) ja "
            "ajaa muunnoksen uudelleen."
        )
        self.policy_switch_button.clicked.connect(self.switch_policy)
        switch.addWidget(self.policy_switch_button)
        qlayout.addWidget(self.policy_switch_row)
        # K5: a regulation type chosen by the user from the national code list (P3-01).
        self.code_row = QWidget()
        code = QVBoxLayout(self.code_row)
        code.setContentsMargins(0, 4, 0, 0)
        code.addWidget(
            _wrapped(
                "<i>Tai valitse kaavamääräyslaji itse kansallisesta koodistosta (RY_Kaavamaarayslaji):</i>"
            )
        )
        self.code_search = _narrow(QComboBox())
        self.code_search.setEditable(True)
        self.code_search.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.code_search.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.code_search.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.code_search.lineEdit().setPlaceholderText("hae nimellä, esim. työpaikka")
        self.code_search.currentIndexChanged.connect(self._code_selected)
        code.addWidget(self.code_search)
        self.code_info = _wrapped()
        code.addWidget(self.code_info)
        self.code_button = QPushButton("Tallenna koodi ratkaisuksi")
        self.code_button.setToolTip(
            "Ryhmän rakenne tehdään valitusta kaavamääräyslajista, kun ajat muunnoksen uudelleen. "
            "Laajuus ja perustelu otetaan alta."
        )
        self.code_button.clicked.connect(self.save_code_decision)
        code.addWidget(self.code_button)
        self._codes_level: str | None = None
        qlayout.addWidget(self.code_row)
        form = QFormLayout()
        self.scope = QComboBox()
        for value, text in SCOPES:
            self.scope.addItem(text, value)
        form.addRow("Laajuus", self.scope)
        self.basis = QLineEdit()
        self.basis.setPlaceholderText("valinnainen perustelu päätöslokiin")
        form.addRow("Perustelu", self.basis)
        qlayout.addLayout(form)
        buttons = QHBoxLayout()
        self.save_answer = QPushButton("Tallenna ratkaisu")
        self.save_answer.clicked.connect(self.save_decision)
        buttons.addWidget(self.save_answer)
        self.remove_answer = QPushButton("Poista oma ratkaisu")
        self.remove_answer.setToolTip("Kysymys palaa avoimeksi, kun ajat muunnoksen uudelleen.")
        self.remove_answer.clicked.connect(self.remove_own_decision)
        buttons.addWidget(self.remove_answer)
        self.rerun = QPushButton("Aja uudelleen ratkaisuin")
        self.rerun.setToolTip(
            "Sääntöpohjainen muunnos uudelleen ratkaisujen kanssa; aiemmat kielimallin vastaukset "
            "käytetään uudelleen ilman kustannusta."
        )
        self.rerun.clicked.connect(self.convert)
        buttons.addWidget(self.rerun)
        qlayout.addLayout(buttons)
        self.decision_count = QLabel()
        qlayout.addWidget(self.decision_count)
        return questions

    def set_project(self, project: ConversionProject) -> None:
        self.project = project
        self._fill_units()
        self.decision_count.setText(f"Ratkaisuja päätöslokissa: {len(self.decisions)}")
        stem, self._stem_suggestion = workflow.stem_after_conversion(
            self.export_stem.text(), self._stem_suggestion, project
        )
        self.export_stem.setText(stem)
        self._show_json()
        self.tabs.setCurrentIndex(1)

    def _fill_units(self) -> None:
        current = (
            self.units.currentItem().data(Qt.ItemDataRole.UserRole) if self.units.currentItem() else None
        )
        self.units.clear()
        if self.project is None:
            return
        wanted = self.filter.currentData()
        select = None
        for unit in self.project.units:
            status = workflow.unit_status(unit)
            if wanted == "kysymys" and status != "kysymys":
                continue
            if wanted == "ongelma" and status not in ("virhe", "varoitus"):
                continue
            if wanted == "valmis" and status != "valmis":
                continue
            item = QListWidgetItem(workflow.unit_label(unit))
            item.setData(Qt.ItemDataRole.UserRole, unit.id)
            item.setToolTip(workflow.STATUS_TEXT[status])
            self.units.addItem(item)
            if select is None or unit.id == current:
                select = item
        if select is not None:
            self.units.setCurrentItem(select)
        else:
            self.detail.clear()
            self._show_questions(None)
            self._show_json()

    def selected_unit(self):
        item = self.units.currentItem()
        if item is None or self.project is None:
            return None
        return self.project.unit(item.data(Qt.ItemDataRole.UserRole))

    def _unit_selected(self, *_args) -> None:
        unit = self.selected_unit()
        if unit is None:
            return
        self.detail.setHtml(workflow.detail_html(self.kb, unit, self.glossary))
        self._show_questions(unit)
        self._show_json()

    def _question_view(self, unit, q) -> workflow.QuestionView:
        return workflow.question_view(
            self.kb,
            self.project,
            unit,
            q,
            decisions=self.decisions,
            options=self.policy_opts,
            g=self.glossary,
        )

    def _show_questions(self, unit) -> None:
        self.question.blockSignals(True)
        self.question.clear()
        questions = [] if unit is None or unit.proposal is None else unit.proposal.questions
        ordered = [q for q in questions if q.is_open] + [q for q in questions if not q.is_open]
        for q in ordered:
            view = self._question_view(unit, q)
            self.question.addItem(f"{view.title} – {view.status}", q.id)
            self.question.setItemData(self.question.count() - 1, view.tooltip, Qt.ItemDataRole.ToolTipRole)
        self.question.blockSignals(False)
        if not ordered:
            self.view = None
            self.question_text.setText("Ei tulkintakysymyksiä." if unit is not None else "")
            self.resolution.setText("")
            self.policy_switch_row.setVisible(False)
            self.code_row.setVisible(False)
            self.remove_answer.setEnabled(False)
            self._set_options(None)
            return
        self.question.setCurrentIndex(0)
        self._question_selected()

    def current_question(self):
        unit = self.selected_unit()
        qid = self.question.currentData()
        if unit is None or qid is None:
            return unit, None
        return unit, next((q for q in unit.proposal.questions if q.id == qid), None)

    def _question_selected(self, *_args) -> None:
        """The card: the question, who resolved it and how the answer can be changed (P1-06)."""
        unit, q = self.current_question()
        if q is None:
            self.view = None
            self._set_options(None)
            self.code_row.setVisible(False)
            return
        view = self._question_view(unit, q)
        self.view = view
        self.question.setToolTip(view.tooltip)
        self.question_text.setText(
            f"<b>{_e(view.title)}</b>" + (f"<br>{_e(view.basis)}" if view.basis else "")
        )
        text = f"<b>{_e(workflow.RESOLVER_TEXT[view.resolver])}</b> – {_e(view.explanation)}"
        if view.how_to_change:
            text += f"<br><i>Muuttaminen:</i> {_e(view.how_to_change)}"
        if view.pending:
            text += f"<br>⏳ {_e(view.pending)}"
        self.resolution.setText(text)
        self._set_options(q, editable=view.editable)
        self.policy_switch_row.setVisible(view.policy_switchable)
        if view.policy_switchable:
            self.policy_switch.clear()
            for value, label in view.policy_choices:
                self.policy_switch.addItem(_capital(label), value)
            self.policy_switch.setCurrentIndex(max(0, self.policy_switch.findData(view.policy_value)))
        self.remove_answer.setEnabled(view.own_decision)
        self.code_row.setVisible(view.code_choice)
        if view.code_choice:
            self._fill_codes(self.project.meta.plan_level)
            index = self.code_search.findData(view.chosen_code) if view.chosen_code else -1
            self.code_search.setCurrentIndex(index)
            if index < 0:
                self.code_search.setEditText("")
            self._code_selected()

    def _fill_codes(self, plan_level: str) -> None:
        if self._codes_level == plan_level:
            return
        self.code_search.blockSignals(True)
        self.code_search.clear()
        for choice in workflow.code_choices(self.kb, plan_level):
            self.code_search.addItem(choice.label, choice.value)
            self.code_search.setItemData(
                self.code_search.count() - 1, choice.description, Qt.ItemDataRole.ToolTipRole
            )
        self.code_search.blockSignals(False)
        self._codes_level = plan_level

    def _code_selected(self, *_args) -> None:
        index = self.code_search.currentIndex()
        if index < 0:
            self.code_info.setText("")
            return
        description = self.code_search.itemData(index, Qt.ItemDataRole.ToolTipRole) or ""
        reservation = self.code_search.itemText(index).endswith("– aluevaraus")
        self.code_info.setText(
            f"<small>{_e(description)}"
            + (" Aluevarauksena ryhmä saa lisätiedon pääkäyttötarkoitus." if reservation else "")
            + "</small>"
        )

    def save_code_decision(self) -> None:
        unit, q = self.current_question()
        index = self.code_search.findText(self.code_search.currentText())
        if q is None or index < 0:
            self.notify("Valitse kaavamääräyslaji listasta.", warning=True)
            return
        option = workflow.code_option(self.code_search.itemData(index))
        decision = workflow.decision_for(
            unit, q, option, scope=self.scope.currentData(), basis=self.basis.text().strip()
        )
        self.decisions = workflow.add_decision(self.decisions, decision)
        self.basis.clear()
        self.decision_count.setText(
            f"Ratkaisuja päätöslokissa: {len(self.decisions)}. Aja uudelleen, jotta koodi vaikuttaa rakenteeseen."
        )
        self._question_selected()
        self._show_json()

    def _set_options(self, q, editable: bool = True) -> None:
        while self.options_box.count():
            widget = self.options_box.takeAt(0).widget()
            if widget is not None:  # hidden and detached at once, not only when the event loop runs
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        if self.option_group is not None:
            self.option_group.deleteLater()
        self.option_group = QButtonGroup(self)
        enabled = bool(q is not None and q.options and editable)
        for widget in (self.save_answer, self.scope, self.basis):
            widget.setEnabled(enabled)
        if q is None:
            return
        chosen = q.answer or q.recommendation
        for option in q.options:
            label = option.description + (" (suositus)" if option.id == q.recommendation else "")
            if option.consequence:
                label += f" – {option.consequence}"
            row = _OptionRow(label)
            row.button.setProperty("option_id", option.id)
            row.button.setChecked(option.id == chosen)
            row.setEnabled(editable)
            self.option_group.addButton(row.button)
            self.options_box.addWidget(row)

    def save_decision(self) -> None:
        unit, q = self.current_question()
        if q is None or self.option_group is None or self.option_group.checkedButton() is None:
            self.notify("Valitse vaihtoehto.", warning=True)
            return
        option = self.option_group.checkedButton().property("option_id")
        decision = workflow.decision_for(
            unit, q, option, scope=self.scope.currentData(), basis=self.basis.text().strip()
        )
        self.decisions = workflow.add_decision(self.decisions, decision)
        self.basis.clear()
        self.decision_count.setText(
            f"Ratkaisuja päätöslokissa: {len(self.decisions)}. Aja uudelleen, jotta ratkaisu vaikuttaa rakenteeseen."
        )
        self._question_selected()
        self._show_json()

    def remove_own_decision(self) -> None:
        unit, q = self.current_question()
        if q is None:
            return
        self.decisions = workflow.remove_decision(self.decisions, unit, q.kind)
        self.decision_count.setText(
            f"Ratkaisuja päätöslokissa: {len(self.decisions)}. Aja uudelleen, jotta kysymys palaa avoimeksi."
        )
        self._question_selected()
        self._show_json()

    def switch_policy(self) -> None:
        """Change the policy of the shown question for this conversion and re-run (ADR-0008)."""
        view = self.view
        if view is None or not view.policy_switchable:
            return
        value = self.policy_switch.currentData()
        try:
            workflow.set_policy(self.policy_opts, self._overrides(), view.policy_id, value)
        except workflow.InputError as error:
            self.notify(str(error), warning=True)
            return
        box = self.policy_boxes[view.policy_id]
        box.setCurrentIndex(max(0, box.findData(value)))
        self.convert()

    def _show_json(self, *_args) -> None:
        if self.project is None:
            self.json_notes.setText("Muunna ensin määräys.")
            self.json_view.clear()
            return
        unit = self.selected_unit() if self.json_scope.currentData() == "yksikko" else None
        if self.json_scope.currentData() == "yksikko" and unit is None:
            self.json_notes.setText("Valitse yksikkö listalta.")
            self.json_view.clear()
            return
        view = workflow.ryhti_view(self.project, unit.id if unit else None, decisions=self.decisions)
        icon = "⚠ " if view.open_questions or not view.included else "✔ "
        self.json_notes.setText(icon + "<br>".join(_e(note) for note in view.notes))
        self.json_view.setPlainText(view.text or "(Tätä yksikköä ei viedä Ryhti-JSONiin; syy yllä.)")

    def copy_json(self) -> None:
        if self.json_view.toPlainText():
            QApplication.clipboard().setText(self.json_view.toPlainText())
            self.status.setText("Ryhti-JSON kopioitu leikepöydälle.")

    # ==================================================================================
    # 3 Vienti

    def _export_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        row = QHBoxLayout()
        self.export_dir = QLineEdit()
        row.addWidget(self.export_dir, 1)
        choose = QPushButton("Valitse…")
        choose.clicked.connect(self.choose_export_dir)
        row.addWidget(choose)
        form.addRow("Kansio", row)
        self.export_stem = QLineEdit()
        self.export_stem.setToolTip(
            "Ehdotus tulee ehdotuksen ensimmäisen kaavamääräysryhmän otsikosta (tai kirjaintunnuksesta) ja "
            "päivittyy jokaisen muunnoksen jälkeen, ellet ole muuttanut nimeä itse."
        )
        form.addRow("Tiedostonimen alku", self.export_stem)
        layout.addLayout(form)
        self.export_checks: dict[str, QCheckBox] = {}
        for key, text, checked in [
            (
                "projekti",
                "Muunnosprojekti (*.kma.json): ratkaisut, perustelut ja kielimallin vastaukset",
                True,
            ),
            ("markdown", "Muunnosraportti (Markdown)", True),
            ("html", "Muunnosraportti (HTML)", False),
            ("ryhti", "Ryhti-JSON (kaavamääräysryhmät ja yleismääräysryhmät)", True),
            ("arho", "Arhon kaavamääräysryhmäkirjasto (YAML, valinnainen; Arhoa ei tarvita)", False),
        ]:
            box = QCheckBox(text)
            box.setChecked(checked)
            self.export_checks[key] = box
            layout.addWidget(box)
        self.include_incomplete = QCheckBox("Vie Arho-kirjastoon myös ryhmät, joissa on sääntövirheitä")
        layout.addWidget(self.include_incomplete)
        self.overwrite = QCheckBox("Korvaa samannimiset tiedostot (kysytään ensin)")
        layout.addWidget(self.overwrite)
        layout.addWidget(
            _wrapped(
                "<small>Jos kansiossa on jo samannimisiä tiedostoja, niitä ei korvata: nimeen lisätään "
                "juokseva numero (esim. _2), ellei korvaamista ole valittu.</small>"
            )
        )
        export = QPushButton("Vie")
        export.clicked.connect(self.export)
        layout.addWidget(export)
        syke = QGroupBox("Syken validointirajapinta (testiympäristö, valinnainen)")
        sform = QFormLayout(syke)
        self.syke_limit = QSpinBox()
        self.syke_limit.setRange(1, 50)
        self.syke_limit.setValue(5)
        sform.addRow("Validoitavia ryhmiä enintään", self.syke_limit)
        validate = QPushButton("Validoi Syken testiympäristössä")
        validate.clicked.connect(self.validate_syke)
        sform.addRow(validate)
        layout.addWidget(syke)
        self.export_result = QTextBrowser()
        self.export_result.setOpenExternalLinks(True)
        layout.addWidget(self.export_result, 1)
        return page

    def choose_export_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Vientikansio", self.export_dir.text())
        if path:
            self.export_dir.setText(path)

    def confirm_overwrite(self, paths: list[Path]) -> bool:
        names = "\n".join(f"• {p.name}" for p in paths)
        answer = QMessageBox.question(
            self,
            "Korvataanko tiedostot?",
            f"Kansiossa on jo nämä tiedostot:\n{names}\n\nKorvataanko ne? Ei peruu viennin.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def export(self) -> None:
        if self.project is None:
            self.notify("Muunna ensin määräys.", warning=True)
            return
        directory = self.export_dir.text().strip()
        if not directory:
            self.choose_export_dir()
            directory = self.export_dir.text().strip()
            if not directory:
                return
        formats = [key for key, box in self.export_checks.items() if box.isChecked()]
        if not formats:
            self.notify("Valitse vähintään yksi vietävä tiedosto.", warning=True)
            return
        stem = workflow.file_stem(self.export_stem.text() or workflow.suggested_stem(self.project))
        overwrite = False
        if self.overwrite.isChecked():
            existing = workflow.existing_exports(Path(directory), stem, formats)
            if existing:
                if not self.confirm_overwrite(existing):
                    self.status.setText("Vienti peruttu: tiedostoja ei korvattu.")
                    return
                overwrite = True
        try:
            result = workflow.export(
                self.kb,
                self.project,
                Path(directory),
                stem,
                formats,
                include_incomplete=self.include_incomplete.isChecked(),
                overwrite=overwrite,
            )
        except (workflow.InputError, OSError) as error:
            self.notify(f"Vienti epäonnistui: {error}", warning=True)
            return
        self.last_export = result
        self._save_settings()
        problems = workflow.schema_problems(self.kb, self.project)
        lines = ["<b>Viety:</b><ul>"]
        lines += [
            f'<li>{_e(EXPORT_LABELS.get(label, label))}: <a href="{p.as_uri()}">{_e(p)}</a></li>'
            for label, p in result.paths.items()
        ]
        lines.append("</ul>")
        if result.renamed:
            lines.append(
                f"<p>Kansiossa oli jo tiedostoja nimellä <b>{_e(result.requested_stem)}</b>, joten niitä ei "
                f"korvattu: nimeen lisättiin numero (<b>{_e(result.stem)}</b>). Jos haluat korvata tiedostot, "
                "valitse Korvaa samannimiset tiedostot.</p>"
            )
        if result.replaced:
            lines.append(f"<p>Korvattiin {len(result.replaced)} aiempaa tiedostoa.</p>")
        if not problems:
            lines.append("<p>Ryhti-skeema: ei virheitä.</p>")
        elif "skeema" in problems:
            lines.append(
                "<p>Ryhti-skeema: paikallista skeematarkistusta ei tehty, koska QGISista puuttuu "
                "jsonschema-paketti. Tämä ei ole virhe. Ryhdin oman tarkistuksen saat painikkeella "
                f"<i>Validoi Syken testiympäristössä</i>.<br><small>{_e(problems['skeema'][0])}</small></p>"
            )
        else:
            lines.append(
                "<p>Ryhti-skeema: " + _e("; ".join(f"{k}: {v[0]}" for k, v in problems.items())) + "</p>"
            )
        self.export_result.setHtml("".join(lines))
        self.status.setText(f"Viety {len(result.paths)} tiedostoa nimellä {result.stem}.")

    def validate_syke(self) -> None:
        if self.project is None:
            self.notify("Muunna ensin määräys.", warning=True)
            return
        from kaavamaaraysavustaja.plugin import auth
        from kaavamaaraysavustaja.validation.syke_public_api import api_key

        try:
            key = auth.load_api_key("syke") or api_key()
        except auth.AuthError as error:
            self.notify(str(error), warning=True)
            return
        if not key:
            self.notify("Syken API-avain puuttuu: tallenna se kohdassa Avaimet…", warning=True)
            return
        kb, project, limit = self.kb, self.project, self.syke_limit.value()

        def work(task: FunctionTask):
            return workflow.syke_validate(kb, project, key, limit=limit, should_stop=task.stopped)

        self.start_task("Kaavamääräysavustaja: Syke-validointi", work, self._syke_done)

    def _syke_done(self, task: FunctionTask) -> None:
        if task.error is not None:
            self.notify(f"Syke-validointi epäonnistui: {task.error}", warning=True)
            return
        lines = ["<b>Syke (testiympäristö):</b><ul>"]
        for line in task.result:
            if line.status == "OK" and not line.findings:
                lines.append(
                    f"<li>✔ {_e(line.title or line.unit_id)}: Ryhti hyväksyi ryhmän, ei havaintoja.</li>"
                )
                continue
            found = "".join(f"<li>{_e(f)}</li>" for f in line.findings)
            lines.append(
                f"<li>{_e(line.title or line.unit_id)}: {_e(line.status)}, määräystason havaintoja {len(line.findings)}"
                + (f"<ul>{found}</ul>" if found else "")
                + "</li>"
            )
        lines.append(
            "</ul><p><small>Kaavatason havainnot (synteettinen testikaava) on suodatettu pois.</small></p>"
        )
        self.export_result.setHtml("".join(lines))
        self.status.setText("Syke-validointi valmis.")

    # ==================================================================================
    # Helpers

    def open_keys(self) -> None:
        from kaavamaaraysavustaja.plugin.dialogs import KeysDialog

        KeysDialog(self).exec()

    def notify(self, text: str, warning: bool = False, details: str = "") -> None:
        if self.iface is not None:
            level = Qgis.MessageLevel.Warning if warning else Qgis.MessageLevel.Info
            self.iface.messageBar().pushMessage("Kaavamääräysavustaja", text, level=level, duration=8)
            if details:
                QgsApplication.messageLog().logMessage(
                    details, "Kaavamääräysavustaja", Qgis.MessageLevel.Warning
                )
        else:
            self.status.setText(text)
        self.last_notice = text

    def _restore_settings(self) -> None:
        s = self.settings
        self.mode.setCurrentIndex(max(0, self.mode.findData(s.value(SETTINGS + "tila", "laadinta"))))
        self.level.setCurrentIndex(max(0, self.level.findData(s.value(SETTINGS + "kaavataso", "yleiskaava"))))
        self.llm.setCurrentIndex(max(0, self.llm.findData(s.value(SETTINGS + "kielimalli", "ei"))))
        self.budget.setValue(float(s.value(SETTINGS + "budjetti", 2.0)))
        self.show_content.setChecked(s.value(SETTINGS + "nayta_sisalto", "false") in (True, "true"))
        self.export_dir.setText(s.value(SETTINGS + "vientikansio", ""))

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue(SETTINGS + "tila", self.mode.currentData())
        s.setValue(SETTINGS + "kaavataso", self.level.currentData())
        s.setValue(SETTINGS + "kielimalli", self.llm.currentData())
        s.setValue(SETTINGS + "budjetti", self.budget.value())
        s.setValue(SETTINGS + "nayta_sisalto", "true" if self.show_content.isChecked() else "false")
        s.setValue(SETTINGS + "vientikansio", self.export_dir.text())

    def shutdown(self) -> None:
        """Plugin unload: running tasks are cancelled (a call in progress finishes)."""
        self._map_timer.stop()
        self.cancel_tasks()
