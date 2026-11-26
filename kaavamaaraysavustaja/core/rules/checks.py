"""Checks of rule engine v1. Each check yields :class:`Finding` objects; the severity and the
rule id come from the rule metadata (``knowledge/rules/rules_v1.yaml``).

Messages are in Finnish (shown to the user); code is in English (CLAUDE.md).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from kaavamaaraysavustaja.core import match
from kaavamaaraysavustaja.core.ingest import normalization_preserves_content
from kaavamaaraysavustaja.core.model import CodeRef, GroupProposal, Regulation, SourceUnit
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase
from kaavamaaraysavustaja.knowledge.codelists import ADDITIONAL_INFO_TYPE, REGULATION_TYPE

VERBAL_PARENT = "sanallinenMaarays"
MAIN_USE = "paakayttotarkoitus"
SUB_AREA = "osaAlue"
QUANTITY_INFOS = {"ehdottomastiNoudatettava", "kayttotarkoituskohdistus"}
USE_CLASS_INFOS = {"kayttotarkoituskohdistus", "poisluettavaKayttotarkoitus"}
TEMPORARY_TYPES = {"maaraAikainenRakentamisrajoitus", "maaraAikainenKieltoRakennuksenRakentamiseksi"}
COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass
class Finding:
    message: str
    target: str = ""
    case: str = ""


@dataclass
class CheckContext:
    kb: KnowledgeBase
    unit: SourceUnit
    proposal: GroupProposal
    plan_level: str
    mode: str

    def is_verbal(self, regulation: Regulation) -> bool:
        if regulation.type.value == VERBAL_PARENT:
            return True
        code = self.kb.index.by_uri(regulation.type.uri)
        return bool(code and code.parent == VERBAL_PARENT)

    def is_quantity(self, regulation: Regulation) -> bool:
        code = self.kb.index.by_uri(regulation.type.uri)
        return bool(code and code.in_extension(match.QUANTITY, self.kb.valid_on))

    def in_reservation(self, regulation: Regulation) -> bool:
        code = self.kb.index.by_uri(regulation.type.uri)
        return bool(code and code.in_extension(match.AREA_RESERVATION, self.kb.valid_on))

    def non_verbal(self) -> list[tuple[int, Regulation]]:
        return [(n, r) for n, r in enumerate(self.proposal.regulations) if not self.is_verbal(r)]


Check = Callable[[CheckContext], Iterator[Finding]]
CHECKS: dict[str, Check] = {}


def check(function: Check) -> Check:
    CHECKS[function.__name__] = function
    return function


def info_values(regulation: Regulation) -> list[str]:
    return [info.type.value for info in regulation.additional_infos]


def all_codes(proposal: GroupProposal) -> Iterator[tuple[str, CodeRef, str]]:
    """(target, code, role) for every code in the proposal."""
    for n, reg in enumerate(proposal.regulations):
        yield f"määräys {n + 1}", reg.type, "laji"
        for m, info in enumerate(reg.additional_infos):
            yield f"määräys {n + 1}, lisätieto {m + 1}", info.type, "lisatieto"
            if info.value and info.value.code:
                yield f"määräys {n + 1}, lisätieto {m + 1} (arvo)", info.value.code, "arvo"
        for m, verbal in enumerate(reg.verbal_types):
            yield f"määräys {n + 1}, sanallisen laji {m + 1}", verbal, "sanallinen"


# --------------------------------------------------------------------------------------
# R-01, R-02 code lists


@check
def codes_valid(ctx: CheckContext) -> Iterator[Finding]:
    known = set(ctx.kb.index.codelists())
    for target, ref, role in all_codes(ctx.proposal):
        if ref.codelist not in known:
            yield Finding(
                f"Koodiston {ref.codelist} koodia {ref.value} ei voi tarkistaa: koodisto ei ole tietopohjassa.",
                target,
                "koodisto_ei_tietopohjassa",
            )
            continue
        code = ctx.kb.index.by_uri(ref.uri)
        if code is None:
            yield Finding(f"Koodia {ref.value} ei ole koodistossa {ref.codelist}.", target, "tuntematon")
            continue
        if not code.is_valid:
            yield Finding(
                f"Koodi {ref.value} on poistunut ({code.status}, päättynyt {code.end_date}).",
                target,
                "poistunut",
            )
            continue
        if role in ("laji", "lisatieto") and ref.codelist in (REGULATION_TYPE, ADDITIONAL_INFO_TYPE):
            if not code.in_extension(ctx.plan_level, ctx.kb.valid_on):
                yield Finding(
                    f"Koodi {ref.value} ei kuulu kaavatason {ctx.plan_level} määrityshierarkiaan "
                    "(Ryhti sallii, mutta suosittaa kaavalajin mukaista koodia).",
                    target,
                    "laajennuksen_ulkopuolella",
                )


@check
def no_header_codes(ctx: CheckContext) -> Iterator[Finding]:
    for target, ref, _role in all_codes(ctx.proposal):
        code = ctx.kb.index.by_uri(ref.uri)
        if code and code.header_level:
            yield Finding(f"{ref.value} on otsikkotason koodi, jota ei käytetä kaavamääräyksissä.", target)


# --------------------------------------------------------------------------------------
# R-03 – R-11


@check
def verbal_types(ctx: CheckContext) -> Iterator[Finding]:
    for n, reg in enumerate(ctx.proposal.regulations):
        if ctx.is_verbal(reg) and not reg.verbal_types:
            yield Finding("Sanallisella määräyksellä ei ole sanallisen määräyksen lajia.", f"määräys {n + 1}")
        if not ctx.is_verbal(reg) and reg.verbal_types:
            yield Finding(
                f"Sanallisen määräyksen laji on sallittu vain sanallisella määräyksellä ({reg.type.value}).",
                f"määräys {n + 1}",
            )


@check
def quantity_values(ctx: CheckContext) -> Iterator[Finding]:
    quantities = [(n, r) for n, r in enumerate(ctx.proposal.regulations) if ctx.is_quantity(r)]
    for n, reg in quantities:
        value = reg.value
        if value is None or value.number is None:
            yield Finding(f"Suureella {reg.type.value} ei ole numeroarvoa.", f"määräys {n + 1}")
        elif value.number <= 0:
            yield Finding(f"Suureen {reg.type.value} arvon on oltava suurempi kuin 0.", f"määräys {n + 1}")
    if len(quantities) > 1:
        yield Finding("Ryhmässä on useampi kuin yksi suureellinen määräys.")


@check
def quantity_additional_infos(ctx: CheckContext) -> Iterator[Finding]:
    for n, reg in enumerate(ctx.proposal.regulations):
        if ctx.is_quantity(reg):
            extra = [v for v in info_values(reg) if v not in QUANTITY_INFOS]
            if extra:
                yield Finding(
                    f"Suureen lisätiedoiksi sallitaan vain {', '.join(sorted(QUANTITY_INFOS))}; nyt {', '.join(extra)}.",
                    f"määräys {n + 1}",
                )


@check
def use_class_target_values(ctx: CheckContext) -> Iterator[Finding]:
    for n, reg in enumerate(ctx.proposal.regulations):
        for m, info in enumerate(reg.additional_infos):
            if info.type.value in USE_CLASS_INFOS:
                code = info.value.code if info.value else None
                if code is None or code.codelist != REGULATION_TYPE:
                    yield Finding(
                        f"Lisätiedon {info.type.value} arvoksi tarvitaan kaavamääräyslaji-koodi.",
                        f"määräys {n + 1}, lisätieto {m + 1}",
                    )


@check
def main_use_area_reservation(ctx: CheckContext) -> Iterator[Finding]:
    for n, reg in enumerate(ctx.proposal.regulations):
        count = info_values(reg).count(MAIN_USE)
        if count and not ctx.in_reservation(reg):
            yield Finding(
                f"Pääkäyttötarkoituksen voi antaa vain Aluevaraus-hierarkian koodille; {reg.type.value} ei kuulu siihen.",
                f"määräys {n + 1}",
            )
        if count > 1:
            yield Finding("Määräyksellä on useampi pääkäyttötarkoitus-lisätieto.", f"määräys {n + 1}")


@check
def same_main_use_or_sub_area(ctx: CheckContext) -> Iterator[Finding]:
    if ctx.proposal.kind != "kaavakohde":
        return
    geometry = set(ctx.proposal.geometry_types)
    regs = ctx.non_verbal()
    kinds = [{MAIN_USE, SUB_AREA} & set(info_values(r)) for _, r in regs]
    if not geometry:
        if regs and any(kinds):
            yield Finding(
                "Geometriatyyppi puuttuu: pääkäyttötarkoitus ja osa-alue edellyttävät aluemaista kohdetta.",
                case="geometria_tuntematon",
            )
        elif regs:
            yield Finding(
                "Geometriatyyppi puuttuu: jos kohde on aluemainen, ryhmään tarvitaan pääkäyttötarkoitus tai osa-alue.",
                case="geometria_tuntematon",
            )
        return
    if "alue" in geometry:
        if not regs:
            return
        if any(len(k) != 1 for k in kinds) or len({frozenset(k) for k in kinds}) > 1:
            yield Finding(
                "Aluemaisen ryhmän muilla kuin sanallisilla määräyksillä on oltava sama lisätieto: "
                "pääkäyttötarkoitus tai osa-alue."
            )
    if geometry & {"piste", "viiva"} and "alue" not in geometry and any(kinds):
        yield Finding("Piste- tai viivamaisella kohteella ei saa olla pääkäyttötarkoitusta eikä osa-aluetta.")


@check
def not_only_verbal_or_quantity(ctx: CheckContext) -> Iterator[Finding]:
    if ctx.proposal.kind != "kaavakohde":
        return
    if not any(not ctx.is_verbal(r) and not ctx.is_quantity(r) for r in ctx.proposal.regulations):
        yield Finding("Kaavakohteen ryhmässä on oltava muukin kuin sanallinen tai suureellinen määräys.")


@check
def general_group(ctx: CheckContext) -> Iterator[Finding]:
    if ctx.proposal.kind != "yleismaarays":
        return
    if not ctx.proposal.regulations and not ctx.proposal.recommendations:
        yield Finding("Yleismääräysryhmä on tyhjä.")
    for n, reg in enumerate(ctx.proposal.regulations):
        if {MAIN_USE, SUB_AREA} & set(info_values(reg)):
            yield Finding(
                "Yleismääräyksellä ei saa olla pääkäyttötarkoitusta eikä osa-aluetta.", f"määräys {n + 1}"
            )


@check
def letter_code_with_main_use(ctx: CheckContext) -> Iterator[Finding]:
    if any(MAIN_USE in info_values(r) for r in ctx.proposal.regulations) and not ctx.proposal.letter_code:
        yield Finding("Kirjaintunnus puuttuu ryhmästä, jossa on pääkäyttötarkoitus.")


# --------------------------------------------------------------------------------------
# R-12 – R-14


@check
def development_zone(ctx: CheckContext) -> Iterator[Finding]:
    zones = [n for n, r in enumerate(ctx.proposal.regulations) if r.type.value == "kehittamisvyohyke"]
    if not zones:
        return
    geometry = ctx.proposal.geometry_types
    if geometry and geometry != ["alue"]:
        yield Finding("Kehittämisvyöhyke on aina aluemainen.", f"määräys {zones[0] + 1}")
    verbal = [r for r in ctx.proposal.regulations if ctx.is_verbal(r)]
    if not verbal:
        yield Finding("Kehittämisvyöhykkeeseen liittyy aina sanallinen määräys.", f"määräys {zones[0] + 1}")
    elif not any(r.type.value == "suunnittelumaarays" for r in verbal):
        yield Finding(
            "Opas 3.3.3.1 edellyttää sanallista suunnittelumääräystä; ryhmässä on "
            f"{verbal[0].type.value} (linjaus L-04; vaihtoehto kehittamisvyohyke_suunnittelumaarays noudattaa opasta).",
            case="ei_suunnittelumaaraysta",
        )


@check
def connection_need_line(ctx: CheckContext) -> Iterator[Finding]:
    geometry = ctx.proposal.geometry_types
    for n, reg in enumerate(ctx.proposal.regulations):
        if "yhteystarve" in info_values(reg) and geometry and "viiva" not in geometry:
            yield Finding("Yhteystarve osoitetaan käytännössä aina viivamaisena.", f"määräys {n + 1}")


@check
def temporary_restriction(ctx: CheckContext) -> Iterator[Finding]:
    for n, reg in enumerate(ctx.proposal.regulations):
        if reg.type.value in TEMPORARY_TYPES and "valiaikainenMaarays" not in info_values(reg):
            yield Finding(f"{reg.type.value} edellyttää lisätietoa väliaikainen määräys.", f"määräys {n + 1}")


# --------------------------------------------------------------------------------------
# R-15 – R-20


def signature_of_regulations(ctx: CheckContext) -> frozenset:
    items = set()
    for _, reg in ctx.non_verbal():
        items.add(("laji", reg.type.value))
        for info in reg.additional_infos:
            items.add(
                (
                    "lisatieto",
                    info.type.value,
                    info.value.code.value if info.value and info.value.code else None,
                )
            )
    return frozenset(items)


def signature_of_row(row: dict) -> frozenset:
    from kaavamaaraysavustaja.core.convert import VERBAL_TYPES, code_from_annex

    items = set()
    for value in row.get("kaavamaarayslajit", []):
        code = code_from_annex(value, REGULATION_TYPE)
        if code and code[1] not in VERBAL_TYPES:
            items.add(("laji", code[1]))
    for info in row.get("lisatiedot", []):
        laji = code_from_annex(info.get("laji"), ADDITIONAL_INFO_TYPE)
        if not laji:
            continue
        value = code_from_annex(info["arvo"], REGULATION_TYPE) if "arvo" in info else None
        items.add(("lisatieto", laji[1], value[1] if value else None))
    return frozenset(items)


@check
def annex_title(ctx: CheckContext) -> Iterator[Finding]:
    if ctx.proposal.kind != "kaavakohde" or not ctx.non_verbal():
        return
    rows = ctx.kb.annex.get(ctx.plan_level, [])
    title = match.fold(ctx.proposal.title.get("fin", ""))
    signature = signature_of_regulations(ctx)
    same = [r for r in rows if r.get("otsikko") and signature_of_row(r) == signature]
    has_verbal = any(ctx.is_verbal(r) for r in ctx.proposal.regulations)
    if same:
        if title not in {match.fold(r["otsikko"]) for r in same}:
            yield Finding(
                f'Koodiyhdistelmä vastaa liitteen 4 määräystä "{same[0]["otsikko"]}" (rivi {same[0]["rivi"]}); '
                "opas 3.1.1: käytetään liitteen otsikkoa"
                + (", ellei tietosisältö ole laajempi (Katja 2 §; linjaus L-15)." if has_verbal else "."),
                case="laajempi_tietosisalto" if has_verbal else "",
            )
    else:
        clash = [r for r in rows if r.get("otsikko") and match.fold(r["otsikko"]) == title]
        if clash:
            yield Finding(
                f'Omassa koodiyhdistelmässä ei saa käyttää liitteen 4 otsikkoa "{clash[0]["otsikko"]}".'
            )


@check
def general_targets_markings(ctx: CheckContext) -> Iterator[Finding]:
    if ctx.proposal.kind != "yleismaarays":
        return
    for hint in match.find_general_targets(ctx.unit.normalized_text):
        yield Finding(
            f'Yleismääräys koskee vain merkintöjä {", ".join(hint.letter_codes)}: "{hint.sentence}" '
            "(opas 3.2.1; linjaus L-05)."
        )


@check
def recommendation_obligation(ctx: CheckContext) -> Iterator[Finding]:
    for n, rec in enumerate(ctx.proposal.recommendations):
        found = match.obligation_words(ctx.kb, rec.text.get("fin", ""))
        if found:
            yield Finding(
                f"Kaavasuosituksessa on velvoittavia ilmauksia: {', '.join(found)}.", f"suositus {n + 1}"
            )


@check
def number_in_text(ctx: CheckContext) -> Iterator[Finding]:
    for n, reg in enumerate(ctx.proposal.regulations):
        if not ctx.is_verbal(reg) or not reg.value or not reg.value.text:
            continue
        text = reg.value.text.get("fin", "")
        quantities = {
            (r.type.value, float(r.value.number))
            for r in ctx.proposal.regulations
            if ctx.is_quantity(r) and r.value and r.value.number is not None
        }
        for hit in match.find_numbers(ctx.kb, text):
            if (hit.quantity_code, hit.value) in quantities:
                yield Finding(
                    f'Numeroarvo "{text[hit.span[0] : hit.span[1]]}" on sanallisessa tekstissä ja myös suureena '
                    f"{hit.quantity_code}; poista se tarvittaessa tekstistä (teksti on laatijan).",
                    f"määräys {n + 1}",
                )
                continue
            where = f" ({hit.place}: paikkasidonnainen, linjaus L-07)" if hit.place else ""
            yield Finding(
                f'Numeroarvo "{text[hit.span[0] : hit.span[1]]}" on sanallisena; suure {hit.quantity_code} '
                f"olisi mahdollinen{where}.",
                f"määräys {n + 1}",
            )


@check
def source_text_intact(ctx: CheckContext) -> Iterator[Finding]:
    unit = ctx.unit
    verbal = [r for r in ctx.proposal.regulations if ctx.is_verbal(r)]
    if not unit.normalized_text:
        if verbal:
            yield Finding("Sanallinen määräys ilman lähdetekstiä.")
        return
    if ctx.proposal.kind == "ei_maarays":
        return
    texts = []
    for n, reg in enumerate(verbal):
        text = (reg.value.text or {}).get("fin", "") if reg.value else ""
        span = reg.text_span
        if span is None or unit.normalized_text[span[0] : span[1]] != text:
            yield Finding(
                "Sanallinen teksti ei ole merkki merkiltä lähdetekstin mukainen.",
                f"sanallinen määräys {n + 1}",
            )
        texts.append(text)
    if texts and "\n\n".join(texts) != unit.normalized_text:
        yield Finding("Sanalliset määräykset eivät kata lähdetekstiä kokonaan ja samassa järjestyksessä.")
    if not normalization_preserves_content(unit.raw_text, unit.normalized_text, unit.normalization_diff):
        yield Finding(
            "Normalisoitu teksti poikkeaa lähteestä muutenkin kuin asettelultaan ja erolistan korjauksilta."
        )
    pending = [c for c in unit.normalization_diff if c.needs_confirmation and c.part == "teksti"]
    if pending:
        yield Finding(
            f"Normalisoinnin erolistassa on {len(pending)} vahvistettavaa kohtaa: "
            + "; ".join(f"{c.raw} → {c.normalized}" for c in pending[:3]),
            case="vahvistettavat_muutokset",
        )


@check
def color_code_form(ctx: CheckContext) -> Iterator[Finding]:
    color = ctx.proposal.color_code
    if color is not None and not COLOR.match(color):
        yield Finding(f"Värikoodin on oltava muotoa #123456, nyt {color!r}.")
