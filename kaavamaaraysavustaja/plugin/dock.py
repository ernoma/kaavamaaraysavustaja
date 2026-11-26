"""The dock of the first testable version (vaihe 3a, ADR-0016, ADR-0017).

Tabs: 1 Syöte (input, mode, plan level, policies, language model), 2 Ehdotus (units with
status icons, proposal in the planner's language and technically, rationale, rule results,
interpretation questions with the user's answer and its scope) and 3 Vienti (project, report,
Ryhti JSON, optional Arho YAML, optional Syke validation).

All conversion logic is in ``core/workflow.py``; this module only builds widgets and runs the
work in ``QgsTask``s (``plugin/tasks.py``). The dock works without ``iface`` (tests).
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

from qgis.core import Qgis, QgsApplication, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
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
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from kaavamaaraysavustaja.core import workflow
from kaavamaaraysavustaja.core.model import ConversionProject
from kaavamaaraysavustaja.plugin.tasks import FunctionTask

SETTINGS = "kaavamaaraysavustaja/telakka/"
MODES = [("laadinta", "Uusi määräys (laadinta)"), ("vooka", "Voimassa oleva määräys (VOOKA)")]
LEVELS = [("yleiskaava", "Yleiskaava"), ("asemakaava", "Asemakaava"), ("maakuntakaava", "Maakuntakaava")]
LLMS = [("ei", "Ei kielimallia (sääntöpohjainen)"), ("claude", "Claude"), ("mistral", "Mistral")]
FILTERS = [
    ("kaikki", "Kaikki"),
    ("kysymys", "Avoimet kysymykset"),
    ("ongelma", "Virheet ja varoitukset"),
    ("valmis", "Valmiit"),
]
SCOPES = [("merkinta", "Vain tämä merkintä"), ("projekti", "Kaikki samankaltaiset tässä muunnoksessa")]


def _slug(text: str) -> str:
    text = re.sub(r"[^0-9A-Za-zÅÄÖåäö_-]+", "_", text.strip()).strip("_")
    return text[:60] or "muunnos"


class AvustajaDock(QDockWidget):
    def __init__(self, iface=None, parent=None):
        super().__init__("Kaavamääräysavustaja", parent)
        self.setObjectName("KaavamaaraysavustajaDock")
        self.iface = iface
        self.settings = QgsSettings()
        self.kb = None
        self.project: ConversionProject | None = None
        self.previous: ConversionProject | None = None  # model answers reused on re-runs
        self.decisions: list = []
        self.request: workflow.ConversionRequest | None = None
        self.tasks: list[FunctionTask] = []
        self.policy_boxes: dict[str, QComboBox] = {}
        self.option_group: QButtonGroup | None = None
        self.last_report = None
        self.last_notice = ""
        self._confirmed_budget = 2.0
        self.run_synchronously = False  # tests: run tasks in the calling thread

        root = QWidget()
        layout = QVBoxLayout(root)
        self.header = QLabel()
        self.header.setWordWrap(True)
        layout.addWidget(self.header)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.status = QLabel()
        self.status.setWordWrap(True)
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
        except Exception as error:  # noqa: BLE001 - shown to the user
            self.header.setText(f"<b>Tietopohjaa ei voitu ladata:</b> {error}")
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
        self.mode = QComboBox()
        for value, text in MODES:
            self.mode.addItem(text, value)
        self.mode.currentIndexChanged.connect(self._update_header)
        form.addRow("Tila", self.mode)
        self.level = QComboBox()
        for value, text in LEVELS:
            self.level.addItem(text, value)
        form.addRow("Kaavataso", self.level)
        self.input_kind = QComboBox()
        self.input_kind.addItem("Yksi määräys: otsikko ja teksti", "yksi")
        self.input_kind.addItem("Liitetty selite (useita merkintöjä, ADR-0009)", "selite")
        self.input_kind.currentIndexChanged.connect(self._update_input_fields)
        form.addRow("Syöte", self.input_kind)
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
        self.map_id = QLineEdit()
        self.map_id.setPlaceholderText("valinnainen: kartan tunnus tai osa nimestä")
        form.addRow("Kartta", self.map_id)
        layout.addLayout(form)
        layout.addWidget(QLabel("Määräysteksti (tyhjä rivi = kappaleraja):"))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText(
            "Kirjoita tai liitä määräyksen teksti. Voimassa olevan määräyksen teksti siirtyy "
            "merkki merkiltä; uuden määräyksen tekstiä ei muuteta."
        )
        self.text.setMinimumHeight(140)
        layout.addWidget(self.text, 1)
        files = QHBoxLayout()
        open_text = QPushButton("Avaa tekstitiedosto…")
        open_text.clicked.connect(self.open_text_file)
        files.addWidget(open_text)
        open_project = QPushButton("Avaa aiempi muunnos (*.kma.json)…")
        open_project.clicked.connect(self.open_project_file)
        files.addWidget(open_project)
        layout.addLayout(files)

        policies = QGroupBox("Linjausvalinnat (oletukset; lukitut linjaukset eivät ole muutettavissa)")
        policies.setCheckable(True)
        policies.setChecked(False)
        pform = QFormLayout()
        container = QWidget()
        container.setLayout(pform)
        for option in workflow.policy_options(self.kb):
            box = QComboBox()
            for value, description in option.options.items():
                suffix = " (oletus)" if value == option.default else ""
                box.addItem(value + suffix, value)
                box.setItemData(box.count() - 1, description, Qt.ItemDataRole.ToolTipRole)
            box.setCurrentIndex(max(0, box.findData(option.default)))
            box.setEnabled(not option.locked and len(option.options) > 1)
            box.setToolTip(f"{option.question}\n\n{option.basis}")
            self.policy_boxes[option.id] = box
            pform.addRow(f"{option.id} {option.title}" + (" 🔒" if option.locked else ""), box)
        policies.toggled.connect(container.setVisible)
        container.setVisible(False)
        pbox = QVBoxLayout(policies)
        pbox.addWidget(container)
        layout.addWidget(policies)

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

    def _update_input_fields(self) -> None:
        single = self.input_kind.currentData() == "yksi"
        for widget in (self.heading, self.letter_code, self.group_kind):
            widget.setEnabled(single)
        self.map_id.setEnabled(not single)

    def _update_header(self) -> None:
        if self.kb is None:
            return
        from kaavamaaraysavustaja.core.llm.prompts import PromptSet

        mode = "VOOKA" if self.mode.currentData() == "vooka" else "laadinta"
        self.header.setText(
            f"Tila: <b>{mode}</b> · Tietopohja {self.kb.version} ✓ · kehote {PromptSet.load(self.kb).label}"
        )

    def read_request(self) -> workflow.ConversionRequest:
        overrides = {pid: box.currentData() for pid, box in self.policy_boxes.items() if box.isEnabled()}
        legend = self.input_kind.currentData() == "selite"
        return workflow.ConversionRequest(
            text=self.text.toPlainText(),
            heading=None if legend else self.heading.text(),
            letter_code=None if legend else self.letter_code.text(),
            kind=self.group_kind.currentData(),
            legend=legend,
            map=self.map_id.text().strip() or None,
            mode=self.mode.currentData(),
            plan_level=self.level.currentData(),
            overrides=overrides,
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
        for choice in project.policy_choices:
            box = self.policy_boxes.get(choice.id)
            if box is not None and box.isEnabled():
                box.setCurrentIndex(max(0, box.findData(choice.option)))
        if len(project.units) == 1:
            unit = project.units[0]
            self.input_kind.setCurrentIndex(0)
            self.heading.setText(unit.heading_raw or unit.heading or "")
            self.letter_code.setText(unit.letter_code_raw or "")
            self.group_kind.setCurrentIndex(max(0, self.group_kind.findData(unit.kind)))
            self.text.setPlainText(unit.raw_text)
        else:
            self.input_kind.setCurrentIndex(1)
            self.notify(
                "Monen yksikön muunnos avattu. Liitä selitteen teksti uudelleen Syöte-välilehdelle, "
                "jos haluat ajaa sen uudelleen (ratkaisut ja kielimallin vastaukset säilyvät)."
            )
        self.set_project(project)

    def new_conversion(self) -> None:
        self.project = self.previous = None
        self.decisions = []
        self.heading.clear()
        self.letter_code.clear()
        self.text.clear()
        self.units.clear()
        self.detail.clear()
        self._show_questions(None)
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
        provider = self.llm.currentData()
        if provider == "ei":
            self.status.setText(self._summary(project) + " Sääntöpohjainen muunnos.")
            return
        self.run_model(project, provider)

    def run_model(self, project: ConversionProject, provider: str) -> None:
        from kaavamaaraysavustaja.core.llm.base import LLMError
        from kaavamaaraysavustaja.core.llm.providers import create_provider
        from kaavamaaraysavustaja.plugin import auth

        try:
            key = auth.load_api_key(provider)
        except auth.AuthError as error:
            key = None
            self.notify(str(error), warning=True)
        reason = workflow.llm_unavailable_reason(provider, key)
        if reason:
            self.notify(reason, warning=True)
            self.status.setText(self._summary(project) + " Sääntöpohjainen muunnos (kielimalli ei käytössä).")
            return
        plan = workflow.llm_plan(self.kb, project, provider, previous=self.previous)
        budget = self.budget.value()
        if plan.estimate.units:
            if not self.confirm_estimate(plan, project):
                self.status.setText(self._summary(project) + " Kielimallia ei kutsuttu.")
                return
            budget = self._confirmed_budget
        elif not plan.reuse:
            self.status.setText(
                self._summary(project)
                + " Kaikki yksiköt ratkesivat sääntöpohjaisesti; kielimallia ei tarvittu."
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
        self.status.setText(self._summary(project) + " " + ", ".join(parts) + ".")

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

    @staticmethod
    def _summary(project: ConversionProject) -> str:
        from kaavamaaraysavustaja.exporters.report import summary

        s = summary(project)
        open_q = sum(s["avoimet"].values())
        return (
            f"{s['yksikoita']} yksikköä, hyväksyttävissä sellaisenaan {s['automaatioehdokkaat']}, "
            f"avoimia kysymyksiä {open_q}."
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
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        splitter.addWidget(self.detail)
        questions = QGroupBox("Tulkintakysymykset")
        qlayout = QVBoxLayout(questions)
        self.question = QComboBox()
        self.question.currentIndexChanged.connect(self._question_selected)
        qlayout.addWidget(self.question)
        self.question_text = QLabel()
        self.question_text.setWordWrap(True)
        qlayout.addWidget(self.question_text)
        self.options_box = QVBoxLayout()
        qlayout.addLayout(self.options_box)
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
        splitter.addWidget(questions)
        splitter.setSizes([160, 360, 220])
        layout.addWidget(splitter, 1)
        self._show_questions(None)
        return page

    def set_project(self, project: ConversionProject) -> None:
        self.project = project
        self._fill_units()
        self.decision_count.setText(f"Ratkaisuja päätöslokissa: {len(self.decisions)}")
        if not self.export_stem.text():
            self.export_stem.setText(_slug(project.meta.title))
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

    def selected_unit(self):
        item = self.units.currentItem()
        if item is None or self.project is None:
            return None
        return self.project.unit(item.data(Qt.ItemDataRole.UserRole))

    def _unit_selected(self, *_args) -> None:
        unit = self.selected_unit()
        if unit is None:
            return
        self.detail.setHtml(workflow.detail_html(self.kb, unit))
        self._show_questions(unit)

    def _show_questions(self, unit) -> None:
        self.question.blockSignals(True)
        self.question.clear()
        questions = [] if unit is None or unit.proposal is None else unit.proposal.questions
        ordered = [q for q in questions if q.is_open] + [q for q in questions if not q.is_open]
        for q in ordered:
            state = "avoin" if q.is_open else f"ratkaistu: {q.answer} ({q.resolved_by})"
            self.question.addItem(f"{q.kind} {q.question} – {state}", q.id)
        self.question.blockSignals(False)
        if not ordered:
            self.question_text.setText("Ei tulkintakysymyksiä." if unit is not None else "")
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
        unit, q = self.current_question()
        if q is None:
            self._set_options(None)
            return
        policy = q.resolved_by.startswith("linjaus") if q.resolved_by else False
        text = f"<b>{q.question}</b><br>{q.basis}"
        if policy:
            text += f"<br><i>Ratkaistu linjauksella ({q.resolved_by}): muuta linjausvalintaa Syöte-välilehdellä.</i>"
        self.question_text.setText(text)
        self._set_options(q, editable=not policy)

    def _set_options(self, q, editable: bool = True) -> None:
        while self.options_box.count():
            widget = self.options_box.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
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
            button = QRadioButton(label)
            button.setProperty("option_id", option.id)
            button.setChecked(option.id == chosen)
            button.setEnabled(editable)
            self.option_group.addButton(button)
            self.options_box.addWidget(button)

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
        stem = _slug(self.export_stem.text() or self.project.meta.title)
        paths = workflow.export(
            self.kb,
            self.project,
            Path(directory),
            stem,
            formats,
            include_incomplete=self.include_incomplete.isChecked(),
        )
        self._save_settings()
        problems = workflow.schema_problems(self.kb, self.project)
        lines = ["<b>Viety:</b><ul>"]
        lines += [f'<li>{label}: <a href="{p.as_uri()}">{p}</a></li>' for label, p in paths.items()]
        lines.append("</ul>")
        if not problems:
            lines.append("<p>Ryhti-skeema: ei virheitä.</p>")
        elif "skeema" in problems:
            lines.append(
                f"<p>Ryhti-skeema: {problems['skeema'][0]}. Voit asentaa jsonschema-paketin kma_deps-kansioon "
                "tai validoida Syken testiympäristössä.</p>"
            )
        else:
            lines.append(
                "<p>Ryhti-skeema: " + "; ".join(f"{k}: {v[0]}" for k, v in problems.items()) + "</p>"
            )
        self.export_result.setHtml("".join(lines))

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
            found = "".join(f"<li>{f}</li>" for f in line.findings)
            lines.append(
                f"<li>{line.unit_id} {line.title}: {line.status}, määräystason havaintoja {len(line.findings)}"
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
        self.cancel_tasks()
