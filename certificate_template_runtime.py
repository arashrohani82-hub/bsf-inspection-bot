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


def _normalize(text: str) -> str:
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return " ".join(text.split()).strip().lower()


def _paragraph_text(paragraph_element) -> tuple[str, list]:
    text_nodes = list(paragraph_element.iter(qn("w:t")))
    return "".join(node.text or "" for node in text_nodes), text_nodes


def _replace_paragraph(paragraph_element, replacement: str) -> bool:
    _, text_nodes = _paragraph_text(paragraph_element)
    if not text_nodes:
        return False
    text_nodes[0].text = replacement
    for node in text_nodes[1:]:
        node.text = ""
    return True


def _replace_best_matches(doc: Document, replacements) -> set[str]:
    """Replace text in normal paragraphs and positioned Word text boxes.

    Matching is intentionally tolerant because the original Word samples split
    text across many runs and can contain non-breaking spaces and smart quotes.
    """
    matched: set[str] = set()
    paragraphs = list(doc.element.body.iter(qn("w:p")))

    for paragraph in paragraphs:
        full_text, _ = _paragraph_text(paragraph)
        normalized = _normalize(full_text)
        if not normalized:
            continue

        for key, tokens, replacement in replacements:
            if key in matched:
                continue
            if any(token in normalized for token in tokens):
                if _replace_paragraph(paragraph, replacement):
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
            "Inspection annuelle des systèmes d’ancrage, des lignes de vie "
            "et des bossoirs"
        )
        body = (
            "Le système visé a fait l’objet d’une inspection annuelle complète "
            "ainsi que des travaux d’entretien requis, réalisés conformément aux "
            "articles 11.8 et 12 de la norme CAN/CSA Z271, par un technicien "
            "qualifié de BSF Inspections, en référence au rapport d’inspection "
            "correspondant."
        )
        validity = (
            "VALIDITÉ DU CERTIFICAT : "
            f"Certificat valide à compter du {_french_long_date(date)} pour une "
            "période maximale de douze (12) mois."
        )
    else:
        heading = "Inspection quinquennale des systèmes d’ancrage et des bossoirs"
        body = (
            "La présente attestation confirme que l’unité d’accès suspendu visée "
            "a fait l’objet d’une inspection quinquennale comprenant l’examen "
            "visuel des systèmes d’ancrage et des bossoirs ainsi que la réalisation "
            "des essais applicables, conformément aux exigences pertinentes des "
            "normes CAN/CSA Z271, CSA Z91 et ASTM E3121/E3121M, en référence au "
            "rapport d’inspection correspondant."
        )
        validity = (
            "VALIDITÉ DU CERTIFICAT : "
            "Le présent certificat confirme la réalisation de l’inspection "
            f"quinquennale en date du {_french_long_date(date)}. Les inspections "
            "annuelles requises doivent continuer d’être effectuées."
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
            (
                "inspection annuelle des systemes",
                "inspection annuelle des systèmes",
                "inspection quinquennale",
            ),
            heading,
        ),
        (
            "address",
            (
                "adresse d'installation",
                "adresse d’installation",
                "adresse de l'installation",
                "adresse de l’installation",
            ),
            f"ADRESSE D’INSTALLATION : {address}",
        ),
        (
            "body",
            (
                "fait l'objet d'une inspection annuelle",
                "fait l’objet d’une inspection annuelle",
                "presente attestation confirme",
                "présente attestation confirme",
                "inspection quinquennale comprenant",
            ),
            body,
        ),
        (
            "validity",
            (
                "validite du certificat",
                "validité du certificat",
                "certificat valide",
            ),
            validity,
        ),
    ]
    matched = _replace_best_matches(doc, replacements)

    # Do not discard the original BSF sample merely because one text box uses
    # unexpected wording. Preserve its layout and replace every field found.
    if not matched:
        raise ValueError("No editable text was found in the original certificate template")
    missing = {"heading", "address", "body", "validity"} - matched
    if missing:
        log.warning(
            "Original certificate created with unmatched fields left intact: %s",
            ", ".join(sorted(missing)),
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
