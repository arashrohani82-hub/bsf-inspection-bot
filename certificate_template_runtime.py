"""Generate certificates from the original BSF one-page DOCX samples.

The sample documents use positioned text boxes rather than ordinary paragraphs.
This module edits all WordprocessingML paragraphs, including text boxes, so the
original background, logo, colours, signature and page layout remain intact.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

import inspection_bot as bot

log = logging.getLogger(__name__)


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("._") or "inspection"


def _french_long_date(value: str) -> str:
    months = (
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value)
    return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"


def _paragraph_text(paragraph_element) -> tuple[str, list]:
    text_nodes = list(paragraph_element.iter(qn("w:t")))
    return "".join(node.text or "" for node in text_nodes), text_nodes


def _replace_matching_paragraphs(doc: Document, replacements) -> set[str]:
    """Replace complete visible paragraphs, including text inside text boxes."""
    matched: set[str] = set()
    for paragraph in doc.element.body.iter(qn("w:p")):
        full_text, text_nodes = _paragraph_text(paragraph)
        normalized = " ".join(full_text.split())
        if not normalized or not text_nodes:
            continue
        for key, predicate, replacement in replacements:
            if key in matched:
                continue
            if predicate(normalized):
                text_nodes[0].text = replacement
                for node in text_nodes[1:]:
                    node.text = ""
                matched.add(key)
                break
    return matched


def _build_from_original_template(session: dict) -> Path | None:
    inspection_type = session.get("inspection_type", "")
    mode = session.get("certificate_mode", "none")
    if mode == "none" or not bot.report_profiles.is_anchor(inspection_type):
        return None

    profile_name = bot.report_profiles.profile_key(inspection_type)
    template = bot.report_profiles.certificate_template_path(
        bot.BASE_DIR, inspection_type
    )
    if template is None:
        return None

    project = str(session.get("project_name", "Inspection"))
    address = str(session.get("address", "—"))
    date = str(session.get("date", datetime.today().strftime("%Y-%m-%d")))
    exclusions = bot.report_profiles.certificate_exclusions(
        session.get("groups", [])
    )

    if profile_name == "anchor_annual":
        heading = (
            "Inspection annuelle des systèmes d’ancrage et de ligne de vie "
            "et des bossoirs"
        )
        body = (
            "a fait l’objet d’une inspection annuelle complète ainsi que des "
            "travaux d’entretien requis, réalisés conformément aux articles "
            "11.8 et 12 de la norme CAN/CSA Z271, par un technicien qualifié de "
            "BSF Inspections, en référence au rapport d’inspection correspondant."
        )
        validity = (
            f"VALIDITÉ DU CERTIFICAT : Certificat valide du {date} se terminant "
            "dans les douze (12) mois suivant"
        )
    else:
        heading = "Inspection quinquennale des systèmes d’ancrage et des bossoirs"
        body = (
            "La présente attestation confirme que l’unité d’accès suspendu visée "
            "a fait l’objet d’une inspection quinquennale comprenant l’examen "
            "visuel des systèmes d’ancrage, des bossoirs ainsi que la réalisation "
            "des essais applicables, conformément aux exigences pertinentes des "
            "normes CAN/CSA Z271, CSA Z91 et ASTM E3121 / E3121M, en référence au "
            "rapport d’inspection correspondant."
        )
        validity = (
            "VALIDITÉ DU CERTIFICAT :\n"
            "Le présent certificat confirme la réalisation de l’inspection "
            f"quinquennale en date du {_french_long_date(date)}. Il demeure "
            "entendu que les inspections annuelles requises doivent continuer "
            "d’être effectuées indépendamment de la présente attestation."
        )

    if mode == "with_exclusions":
        exclusion_text = "; ".join(exclusions) or (
            "les éléments expressément identifiés au rapport"
        )
        body += (
            " Sont exclus du présent certificat : " + exclusion_text + ". "
            "Ces éléments doivent demeurer hors service jusqu’à la réalisation "
            "des correctifs et, lorsque requis, d’une nouvelle inspection."
        )

    doc = Document(template)
    replacements = [
        (
            "heading",
            lambda text: (
                "Inspection annuelle des systèmes" in text
                or "Inspection quinquennale" in text
            ),
            heading,
        ),
        (
            "address",
            lambda text: "ADRESSE D’INSTALLATION" in text.upper(),
            f"ADRESSE D’INSTALLATION : {address}",
        ),
        (
            "body",
            lambda text: (
                "a fait l’objet d’une inspection annuelle" in text
                or "La présente attestation confirme que l’unité d’accès suspendu" in text
            ),
            body,
        ),
        (
            "validity",
            lambda text: "VALIDITÉ DU CERTIFICAT" in text.upper(),
            validity,
        ),
    ]
    matched = _replace_matching_paragraphs(doc, replacements)
    required = {"heading", "address", "body", "validity"}
    missing = required - matched
    if missing:
        raise ValueError(
            "Original certificate template fields not found: "
            + ", ".join(sorted(missing))
        )

    bot.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = bot.REPORTS_DIR / (
        f"{_safe_name(project)}_Certificate_{profile_name}_{_safe_name(date)}.docx"
    )
    doc.save(output)
    log.info("Certificate generated from original BSF template: %s", template)
    return output


def install_original_certificate_templates() -> None:
    """Make the original BSF samples the primary certificate generator."""
    fallback_builder = bot.build_certificate

    def build_certificate(session: dict):
        try:
            return _build_from_original_template(session)
        except Exception:
            log.exception(
                "Original BSF certificate template generation failed; "
                "delegating to safety fallback"
            )
            return fallback_builder(session)

    bot.build_certificate = build_certificate
