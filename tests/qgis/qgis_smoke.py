"""Light UI smoke test with QGIS's own Python, without the QGIS window (not run in CI).

Run locally (OSGeo4W)::

    C:\\OSGeo4W\\bin\\python-qgis.bat tests\\qgis\\qgis_smoke.py

or through pytest: ``KMA_QGIS_PYTHON=C:\\OSGeo4W\\bin\\python-qgis.bat pytest -m qgis``.
The script loads the plugin with a minimal ``iface``, opens the dock and goes through the
first-version path: a new regulation (drafting mode) and a regulation in force (VOOKA, pasted
legend), an interpretation question answered and re-run, export, the model path with a test
adapter (cost estimate before the call, no network) and one real ``QgsTask`` run. Feedback
round 1 (0.3.1): plain-language header and policy choices, map choice only for a text with
several maps, one pasted marking, who resolved a question and the policy switch in the card,
the Ryhti JSON view, the file name suggestion and export without overwriting.
No API key is used; settings go to a separate organisation (``KMA-savutesti``).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from qgis.core import QgsApplication  # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication  # noqa: E402
from qgis.PyQt.QtWidgets import QMainWindow  # noqa: E402

NEW_TEXT = (
    "Alueelle saa rakentaa enintään 6 000 k-m² pientaloja.\n\nPihoille suositellaan hulevesien viivyttämistä."
)
LEGEND = """\
@kartta Kartta 1 - Yhdyskuntarakenne
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille. Alueen suunnittelussa tulee kiinnittää huomiota kulttuuriympäristön arvoihin.
c-1 TÄYDENTYVÄ KESKUSTA
Aluetta kehitetään täydennettävänä keskustatoimintojen alueena.
"""
ONE_MARKING = "c-1 TÄYDENTYVÄ KESKUSTA\nAluetta kehitetään täydennettävänä keskustatoimintojen alueena.\n"
TWO_MAPS = """\
@kartta Kartta 1 - Yhdyskuntarakenne
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille.
@kartta Kartta 2 - Liikenne
RAITIOTIE
Raitiotie on ohjeellinen.
"""


class MessageBar:
    def __init__(self):
        self.messages: list[str] = []

    def pushMessage(self, title, text, level=None, duration=None):  # noqa: N802
        self.messages.append(text)


class Iface:
    """The part of QgisInterface the plugin uses."""

    def __init__(self):
        self.window = QMainWindow()
        self.bar = MessageBar()
        self.docks = []
        self.menu = []

    def mainWindow(self):  # noqa: N802
        return self.window

    def messageBar(self):  # noqa: N802
        return self.bar

    def addPluginToMenu(self, menu, action):  # noqa: N802
        self.menu.append(action.text())

    def removePluginMenu(self, menu, action):  # noqa: N802
        self.menu.remove(action.text())

    def addToolBarIcon(self, action):  # noqa: N802
        pass

    def removeToolBarIcon(self, action):  # noqa: N802
        pass

    def addDockWidget(self, area, dock):  # noqa: N802
        self.docks.append(dock)

    def removeDockWidget(self, dock):  # noqa: N802
        self.docks.remove(dock)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"  ok: {message}")


def select_question(dock, kind: str) -> None:
    index = next(i for i in range(dock.question.count()) if dock.question.itemData(i).endswith(kind))
    dock.question.setCurrentIndex(index)


def choose(dock, kind: str, option: str, scope: str = "merkinta") -> None:
    select_question(dock, kind)
    button = next(b for b in dock.option_group.buttons() if b.property("option_id") == option)
    button.setChecked(True)
    dock.scope.setCurrentIndex(dock.scope.findData(scope))
    dock.save_decision()


def run() -> None:
    from qgis.core import Qgis

    from kaavamaaraysavustaja import classFactory
    from kaavamaaraysavustaja.core import workflow
    from kaavamaaraysavustaja.core.model import ConversionProject
    from kaavamaaraysavustaja.plugin import dock as dock_module

    print(f"QGIS {Qgis.QGIS_VERSION}")
    iface = Iface()
    plugin = classFactory(iface)
    plugin.initGui()
    check(
        iface.menu == ["Kaavamääräysavustaja", "API-avaimet…", "Tietoja Kaavamääräysavustajasta"], "valikko"
    )
    plugin.dock_action.setChecked(True)
    dock = plugin.dock
    check(dock is not None and dock in iface.docks, "telakka avautuu")
    header = dock.header.text()
    check(
        "Koodistot ja säännöt" in header and "TP-" not in header and "prompts/" not in header,
        "otsikkorivi selkokielinen (P1-01)",
    )
    check(
        "TP-" in dock.header.toolTip() and "kehotteen versio" in dock.header.toolTip(),
        "tunnisteet työkaluvihjeessä",
    )
    check(
        "kaikki suositellussa oletuksessa" in dock.policy_toggle.text()
        and "L-0" not in dock.policy_toggle.text(),
        "linjausvalinnat: yhteenveto ilman tunnisteita (P1-04)",
    )
    dock.policy_toggle.setChecked(True)
    check(
        not dock.policy_body.isHidden() and dock.read_request().overrides == {},
        "linjaukset auki, oletukset ei ohituksia",
    )
    check(
        dock.policy_effects["L-06"].text().startswith("<i>Vaikutus:</i>")
        and dock.policy_boxes["L-06"].currentText() == "Lähteen tunnus (suositus)",
        "linjauksen vaikutus näkyvissä",
    )
    dock.run_synchronously = True
    out = Path(tempfile.mkdtemp(prefix="kma_savutesti_"))

    # -- 1. New regulation (drafting mode), rule-based ------------------------------------
    dock.mode.setCurrentIndex(dock.mode.findData("laadinta"))
    dock.llm.setCurrentIndex(dock.llm.findData("ei"))
    dock.input_kind.setCurrentIndex(dock.input_kind.findData("yksi"))
    check(
        dock.map_choice.isHidden() and not dock.heading.isHidden(), "yksi määräys: ei karttavalintaa (P1-03)"
    )
    dock.heading.setText("Pientalovaltainen asuntoalue")
    dock.text.setPlainText(NEW_TEXT)
    dock.input_kind.setCurrentIndex(dock.input_kind.findData("selite"))
    check(
        dock.text.toPlainText() == "" and not dock.legend_example.isHidden() and dock.heading.isHidden(),
        "liitetty teksti: oma tyhjä teksti, esimerkki merkittynä mallina (P2-01)",
    )
    dock.input_kind.setCurrentIndex(dock.input_kind.findData("yksi"))
    check(
        dock.text.toPlainText() == NEW_TEXT and dock.legend_example.isHidden(),
        "yksi määräys: oma teksti palaa",
    )
    dock.convert()
    project = dock.project
    check(project is not None and project.meta.mode == "laadinta", "uusi määräys muunnettu (laadinta)")
    check(dock.export_stem.text() == "Pientalovaltainen_asuntoalue", "tiedostonimi ryhmän otsikosta (P1-08)")
    p = project.units[0].proposal
    check(any(r.type.value == "sallittuKerrosala" and r.value.number == 6000 for r in p.regulations), "suure")
    check(
        dock.units.count() == 1 and dock.units.item(0).text()[0] in "✔?⚠✖–", "yksikkölista tilakuvakkeineen"
    )
    html = dock.detail.toHtml()
    check("Rakenne" in html and "Tekninen näkymä" in html and "Perustelut" in html, "tarkastelunäkymä")
    check("RY_Kaavamaarayslaji/code/asuinpientaloalue" in html, "tekninen näkymä URIneen")
    check(any(dock.question.itemData(i).endswith("K13") for i in range(dock.question.count())), "K13 näkyy")
    check(
        not any("K1" in dock.question.itemText(i) for i in range(dock.question.count())),
        "kysymyslista ilman K-tunnisteita",
    )
    select_question(dock, "K13")
    check(
        dock.view.resolver == "avoin" and dock.save_answer.isEnabled(),
        "avoin kysymys: oma ratkaisu mahdollinen",
    )
    check(
        "Ryhti-JSONiin" not in dock.json_notes.text()
        and "Avoimia tulkintakysymyksiä 1" in dock.json_notes.text(),
        "Ryhti-JSON: avoin kysymys kerrotaan (P1-07)",
    )
    choose(dock, "K13", "suositus")
    check(len(dock.decisions) == 1 and dock.decisions[0].kind == "K13", "ratkaisu päätöslokiin")
    check(
        "⏳" in dock.resolution.text() and "Aja uudelleen ratkaisuin" in dock.json_notes.text(),
        "tallennettu ratkaisu odottaa uudelleenajoa",
    )
    dock.convert()  # re-run with the decision
    p = dock.project.units[0].proposal
    check(len(p.recommendations) == 1, "uudelleenajo: kappale kaavasuositukseksi")
    k13 = next(q for q in p.questions if q.kind == "K13")
    check(k13.resolved_by == "kayttaja", "ratkaisu säilyy uudelleenajossa")
    select_question(dock, "K13")
    check(
        dock.view.resolver == "kayttaja" and dock.save_answer.isEnabled() and dock.remove_answer.isEnabled(),
        "oma ratkaisu aina muutettavissa (P1-06)",
    )
    check("Ratkaisija: sinä" in dock.resolution.text(), "kortti kertoo ratkaisijan")
    select_question(dock, "K14")
    check(
        dock.view.resolver == "linjaus"
        and not dock.save_answer.isEnabled()
        and not dock.policy_switch_row.isHidden(),
        "linjauksella ratkaistu: vaihto kortista",
    )
    check("Ei avoimia tulkintakysymyksiä" in dock.json_notes.text(), "Ryhti-JSON: ei avoimia kysymyksiä")
    unit_json = json.loads(dock.json_view.toPlainText())
    check(
        unit_json["planRegulationGroupKey"] == p.key and unit_json.get("planRecommendations"),
        "Ryhti-JSON valitusta yksiköstä",
    )
    dock.export_dir.setText(str(out))
    dock.export_stem.setText("uusi")
    for key in dock.export_checks:
        dock.export_checks[key].setChecked(True)
    dock.export()
    for suffix in (".kma.json", "_raportti.md", "_raportti.html", ".ryhti.json", ".arho.yaml"):
        check((out / f"uusi{suffix}").exists(), f"vienti uusi{suffix}")
    saved = ConversionProject.load(out / "uusi.kma.json")
    check([d.kind for d in saved.decisions] == ["K13"], "päätösloki tallessa projektissa")
    result = dock.export_result.toHtml()
    check(
        "Ryhti-skeema: ei virheitä" in result or "paikallista skeematarkistusta ei tehty" in result,
        "Ryhti-skeema",
    )
    check(
        "Avustajan tarkistussäännöt: ei virheitä" in dock.json_notes.text(),
        "Ryhti-JSON: ei estäviä virheitä (P2-02)",
    )
    check(
        not json.loads((out / "uusi.ryhti.json").read_text(encoding="utf-8")).get("plan"), "Ryhti-fragmentit"
    )
    dock.json_scope.setCurrentIndex(dock.json_scope.findData("kaikki"))
    check(
        dock.json_view.toPlainText() == (out / "uusi.ryhti.json").read_text(encoding="utf-8"),
        "Ryhti-JSON-näkymä = viety tiedosto",
    )
    dock.json_scope.setCurrentIndex(dock.json_scope.findData("yksikko"))
    # -- export does not overwrite without asking (P1-09) ------------------------------------
    (out / "uusi_raportti.md").write_text("oma muokkaus", encoding="utf-8")
    dock.export()
    check(
        (out / "uusi_2.kma.json").exists()
        and dock.last_export.renamed
        and "uusi_2" in dock.export_result.toHtml(),
        "toinen vienti: juokseva numero",
    )
    check(
        (out / "uusi_raportti.md").read_text(encoding="utf-8") == "oma muokkaus",
        "olemassa olevaa ei korvattu",
    )
    dock.overwrite.setChecked(True)
    asked = []
    dock.confirm_overwrite = lambda paths: asked.append(paths) and False
    dock.export()
    check(
        asked and (out / "uusi_raportti.md").read_text(encoding="utf-8") == "oma muokkaus",
        "korvaus kysytään; Ei peruu",
    )
    dock.confirm_overwrite = lambda paths: True
    dock.export()
    check(
        "Muunnosraportti" in (out / "uusi_raportti.md").read_text(encoding="utf-8")
        and dock.last_export.replaced,
        "korvaus erillisenä valintana",
    )
    dock.overwrite.setChecked(False)

    # -- 2. Regulation in force (VOOKA), pasted legend ------------------------------------
    dock.new_conversion()
    dock.export_stem.clear()
    dock.mode.setCurrentIndex(dock.mode.findData("vooka"))
    dock.input_kind.setCurrentIndex(dock.input_kind.findData("selite"))
    check(
        dock.heading.isHidden()
        and dock.letter_code.isHidden()
        and "ISOIN KIRJAIMIN" in dock.input_help.text(),
        "liitetty teksti: otsikko tekstistä, ohje ja esimerkki näkyvissä (P1-05)",
    )
    dock.text.setPlainText(LEGEND)
    dock._refresh_maps()
    check(dock.map_choice.isHidden(), "yksi kartta: ei karttavalintaa")
    dock.convert()
    project = dock.project
    check(project.meta.mode == "vooka" and len(project.units) == 2, "voimassa oleva selite muunnettu (VOOKA)")
    check(project.meta.map == "Kartta 1 - Yhdyskuntarakenne", "tekstin kartta kirjattu")
    check(
        dock.export_stem.text() == "Keskustatoimintojen_alue",
        "tiedostonimi päivittyy muunnoksen mukaan (P1-08)",
    )
    for unit in project.units:
        verbal = [r for r in unit.proposal.regulations if r.value and r.value.data_type == "LocalizedText"]
        check("\n\n".join(r.value.text["fin"] for r in verbal) == unit.normalized_text, f"R-19 {unit.id}")
        check(
            not [r for r in unit.proposal.rule_results if r.rule_id == "R-19"], f"ei R-19-virhettä {unit.id}"
        )
    dock.filter.setCurrentIndex(dock.filter.findData("kysymys"))
    dock.filter.setCurrentIndex(dock.filter.findData("kaikki"))
    dock.units.setCurrentRow(1)
    if any(dock.question.itemData(i).endswith("K1") for i in range(dock.question.count())):
        choose(dock, "K1", "osa_alue", scope="projekti")
        dock.convert()
        k1 = next(q for q in dock.project.units[1].proposal.questions if q.kind == "K1")
        check(k1.answer == "osa_alue" and k1.resolved_by == "kayttaja", "K1 ratkaistu (laajuus projekti)")
    dock.export_stem.setText("voimassa")
    dock.export()
    check((out / "voimassa.ryhti.json").exists(), "VOOKA-vienti")

    # -- 2b. One pasted marking, map choice and a policy changed from the card ---------------
    dock.new_conversion()
    dock.input_kind.setCurrentIndex(dock.input_kind.findData("selite"))
    dock.text.setPlainText(ONE_MARKING)
    dock.convert()
    check(
        len(dock.project.units) == 1 and dock.project.units[0].letter_code == "c-1",
        "liitetty teksti, yksi merkintä (P1-05)",
    )
    select_question(dock, "K14")
    check(
        dock.view.policy_id == "L-06" and dock.view.policy_switchable, "K14: linjaus vaihdettavissa kortista"
    )
    dock.policy_switch.setCurrentIndex(dock.policy_switch.findData("katja"))
    dock.switch_policy()
    unit = dock.project.units[0]
    choice = next(c for c in dock.project.policy_choices if c.id == "L-06")
    check(
        unit.proposal.letter_code == "cka"
        and choice.source == "kayttaja"
        and dock.policy_boxes["L-06"].currentData() == "katja"
        and "muutettu 1" in dock.policy_toggle.text(),
        "linjaus vaihdettu kortista: muunnoskohtainen valinta (P1-06)",
    )
    dock.policy_boxes["L-06"].setCurrentIndex(dock.policy_boxes["L-06"].findData("alkuperaiset"))
    dock.text.setPlainText(TWO_MAPS)
    dock._refresh_maps()
    check(
        not dock.map_choice.isHidden()
        and dock.map_choice.count() == 3
        and "2 karttaa" in dock.map_help.text(),
        "useita karttoja: karttavalinta näkyy (P1-02)",
    )
    dock.map_choice.setCurrentIndex(dock.map_choice.findData("Kartta 2 - Liikenne"))
    dock.convert()
    check(
        [u.heading for u in dock.project.units] == ["RAITIOTIE"]
        and dock.project.meta.map == "Kartta 2 - Liikenne",
        "valittu kartta muunnettu",
    )

    # -- 3. Model path with a test adapter: estimate before the call, no network ------------
    from kaavamaaraysavustaja.core.llm.fake import FakeProvider
    from kaavamaaraysavustaja.plugin import auth

    shown = []

    def respond(request):
        task = json.loads(request.task_input)
        return {
            "ryhmat": [
                {
                    "otsikko": "Pientalovaltainen asuntoalue",
                    "kirjaintunnus": "AP",
                    "ryhmatyyppi": "kaavakohde",
                    "geometria": ["alue"],
                    "maaraykset": [
                        {
                            "laji": "asuinpientaloalue",
                            "arvo": None,
                            "lisatiedot": [{"laji": "paakayttotarkoitus", "arvo": None}],
                            "sanallisen_lajit": [],
                            "tekstiviitteet": [],
                        },
                        {
                            "laji": "sanallinenMaarays",
                            "arvo": task["yksikko"]["teksti"],
                            "lisatiedot": [],
                            "sanallisen_lajit": ["rakennusoikeus"],
                            "tekstiviitteet": [],
                        },
                    ],
                    "suositukset": [],
                }
            ],
            "perustelut": [],
            "vaihtoehdot": [],
            "tulkintakysymykset": [],
            "ratkaistut_kysymykset": [],
            "kokonaisvarmuus": "keskitaso",
        }

    fake = FakeProvider(respond)
    original = (auth.load_api_key, workflow.llm_unavailable_reason)
    import kaavamaaraysavustaja.core.llm.providers as providers

    original_create = providers.create_provider
    auth.load_api_key = lambda name: "testiavain"
    workflow.llm_unavailable_reason = lambda name, key: None
    providers.create_provider = lambda name, model=None, api_key=None: fake
    dock_module.AvustajaDock.confirm_estimate = lambda self, plan, project: (
        shown.append(plan.estimate.usd) or setattr(self, "_confirmed_budget", 1.0) or True
    )
    try:
        dock.new_conversion()
        dock.mode.setCurrentIndex(dock.mode.findData("laadinta"))
        dock.input_kind.setCurrentIndex(dock.input_kind.findData("yksi"))
        dock.heading.setText("Pientalovaltainen asuntoalue")
        dock.text.setPlainText("Alueen rakennukset tulee sovittaa maisemaan.")
        dock.llm.setCurrentIndex(dock.llm.findData("claude"))
        dock.convert()
        check(shown and shown[0] > 0, "kustannusarvio näytetään ennen kutsua")
        check(len(fake.requests) == 1 and dock.last_report.totals()["kutsuja"] == 1, "kielimallikutsu")
        check(dock.project.units[0].proposal.model_check is not None, "hybridiehdotus telakassa")
        dock.convert()  # re-run: the earlier answer is reused, no new call
        check(len(fake.requests) == 1, "uudelleenajo käyttää aiemman vastauksen")
        preview = workflow.request_preview(dock.kb, dock.project)
        check("Järjestelmäohje" in preview and "PDF" in preview, "lähetettävän sisällön esikatselu")
    finally:
        auth.load_api_key, workflow.llm_unavailable_reason = original
        providers.create_provider = original_create

    from kaavamaaraysavustaja.plugin.dialogs import EstimateDialog, KeysDialog

    plan = workflow.llm_plan(dock.kb, dock.project, "claude")
    EstimateDialog(plan, 2.0, lambda: "sisältö", True).toggle_content()
    KeysDialog()
    check(True, "dialogit rakentuvat")

    # -- 4. One real QgsTask through the task manager ----------------------------------------
    dock.llm.setCurrentIndex(dock.llm.findData("ei"))
    dock.run_synchronously = False
    dock.convert()
    deadline = time.monotonic() + 60
    while dock.tasks and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.05)
    check(not dock.tasks and dock.project.units[0].proposal.model_check is None, "QgsTask-ajo valmistuu")

    plugin.unload()
    check(not iface.docks and not iface.menu, "lisäosa poistuu siististi")
    print(f"Savutesti läpi. Viedyt tiedostot: {out}")


def main() -> int:
    QCoreApplication.setOrganizationName("KMA-savutesti")
    QCoreApplication.setApplicationName("KMA-savutesti")
    os.environ.setdefault("QGIS_AUTH_DB_DIR_PATH", tempfile.mkdtemp(prefix="kma_auth_"))
    app = QgsApplication([], True)  # GUI-enabled widgets, no main window shown
    app.initQgis()
    try:
        run()
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    finally:
        app.exitQgis()
    return 0


if __name__ == "__main__":
    sys.exit(main())
