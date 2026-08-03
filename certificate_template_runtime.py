"""Generate certificates from the original BSF DOCX samples.

The certificate samples contain positioned Word text boxes.  This module edits
text nodes inside the DOCX XML package while preserving every drawing, image,
logo, signature, colour, font and page-layout element from the original file.
"""

from __future__ import annotations

import logging
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from lxml import etree

import inspection_bot as bot

log = logging.getLogger(__name__)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


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


def _normalize(value: str) -> str:
    value = (
        value.replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
        .replace("\u00a0", " ")
    )
    return " ".join(value.lower().split())


def _paragraph_text(paragraph) -> tuple[str, list]:
    nodes = paragraph.xpath(".//w:t", namespaces=NS)
    return "".join(node.text or "" for node in nodes), nodes


def _replace_paragraph(paragraph, replacement: str) -> bool:
    _, nodes = _paragraph_text(paragraph)
    if not nodes:
        return False
    nodes[0].text = replacement
    # Preserve the run and drawing structure; clear only surplus visible text.
    for node in nodes[1:]:
        node.text = ""
    return True


def _matches(text: str, token_sets: tuple[tuple[str, ...], ...]) -> bool:
    normalized = _normalize(text)
    return any(all(_normalize(token) in normalized for token in tokens) for tokens in token_sets)


def _patch_xml_part(xml_bytes: bytes, fields: dict[str, dict]) -> tuple[bytes, set[str]]:
    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    root = etree.fromstring(xml_bytes, parser)
    matched: set[str] = set()

    for paragraph in root.xpath(".//w:p", namespaces=NS):
        visible, _ = _paragraph_text(paragraph)
        if not visible.strip():
            continue
        for key, field in fields.items():
            if key in matched:
                continue
            if _matches(visible, field["tokens"]):
                if _replace_paragraph(paragraph, field["value"]):
                    matched.add(key)
                break

    return (
        etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=None,
        ),
        matched,
    )


def _patch_docx(template: Path, output: Path, fields: dict[str, dict]) -> set[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    matched: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="bsf_certificate_") as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(template, "r") as source:
            source.extractall(temp_root)

        # Text boxes may appear in document.xml, headers or footers.
        candidate_parts = [
            path
            for path in temp_root.rglob("*.xml")
            if path.name == "document.xml"
            or path.name.startswith("header")
            or path.name.startswith("footer")
        ]

        for xml_path in candidate_parts:
            remaining = {k: v for k, v in fields.items() if k not in matched}
            if not remaining:
                break
            try:
                patched, part_matches = _patch_xml_part(xml_path.read_bytes(), remaining)
            except etree.XMLSyntaxError:
                log.exception("Invalid Word XML part: %s", xml_path)
                continue
            if part_matches:
                xml_path.write_bytes(patched)
                matched.update(part_matches)

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for path in temp_root.rglob("*"):
                if path.is_file():
                    target.write(path, path.relative_to(temp_root).as_posix())

    return matched


def _build_from_original_template(session: dict) -> Path | None:
    inspection_type = session.get("inspection_type", "")
    mode = session.get("certificate_mode", "none")
    if mode == "none" or not bot.report_profiles.is_anchor(inspection_type):
        return None

    profile_name = bot.report_profiles.profile_key(inspection_type)
    template = bot.report_profiles.certificate_template_path(bot.BASE_DIR, inspection_type)
    if template is None:
        return None

    project = str(session.get("project_name", "Inspection"))
    address = str(session.get("address", "—"))
    date = str(session.get("date", datetime.today().strftime("%Y-%m-%d")))
    exclusions = bot.report_profiles.certificate_exclusions(session.get("groups", []))

    if profile_name == "anchor_annual":
        heading = "Inspection annuelle des systèmes d’ancrage, des lignes de vie et des bossoirs"
        body = (
            "Le système visé a fait l’objet d’une inspection annuelle complète ainsi que des "
            "travaux d’entretien requis, réalisés conformément aux articles 11.8 et 12 de la "
            "norme CAN/CSA Z271, par un technicien qualifié de BSF Inspections, en référence "
            "au rapport d’inspection correspondant."
        )
        validity = (
            f"VALIDITÉ DU CERTIFICAT : Certificat valide à compter du "
            f"{_french_long_date(date)} pour une période maximale de douze (12) mois."
        )
        heading_tokens = (("inspection annuelle", "systèmes d'ancrage"),)
        body_tokens = (
            ("inspection annuelle", "can/csa z271"),
            ("inspection annuelle complète", "bsf inspections"),
        )
        validity_tokens = (
            ("validité du certificat",),
            ("certificat valide", "douze"),
        )
    else:
        heading = "Inspection quinquennale des systèmes d’ancrage et des bossoirs"
        body = (
            "La présente attestation confirme que l’unité d’accès suspendu visée a fait "
            "l’objet d’une inspection quinquennale comprenant l’examen visuel des systèmes "
            "d’ancrage et des bossoirs ainsi que la réalisation des essais applicables, "
            "conformément aux exigences pertinentes des normes CAN/CSA Z271, CSA Z91 et "
            "ASTM E3121/E3121M, en référence au rapport d’inspection correspondant."
        )
        validity = (
            "VALIDITÉ DU CERTIFICAT : Le présent certificat confirme la réalisation de "
            f"l’inspection quinquennale en date du {_french_long_date(date)}. Les inspections "
            "annuelles requises doivent continuer d’être effectuées."
        )
        heading_tokens = (("inspection quinquennale", "systèmes d'ancrage"),)
        body_tokens = (
            ("présente attestation", "inspection quinquennale"),
            ("inspection quinquennale", "astm e3121"),
        )
        validity_tokens = (
            ("validité du certificat",),
            ("présent certificat", "inspections annuelles"),
        )

    if mode == "with_exclusions":
        exclusion_text = "; ".join(exclusions) or "les éléments expressément identifiés au rapport"
        body += (
            " Sont exclus du présent certificat : " + exclusion_text + ". Ces éléments doivent "
            "demeurer hors service jusqu’à la réalisation des correctifs et, lorsque requis, "
            "d’une nouvelle inspection."
        )

    fields = {
        "heading": {"tokens": heading_tokens, "value": heading},
        "address": {
            "tokens": (
                ("adresse d'installation",),
                ("adresse de l'installation",),
            ),
            "value": f"ADRESSE D’INSTALLATION : {address}",
        },
        "body": {"tokens": body_tokens, "value": body},
        "validity": {"tokens": validity_tokens, "value": validity},
    }

    bot.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = bot.REPORTS_DIR / (
        f"{_safe_name(project)}_BSF_ORIGINAL_Certificate_{profile_name}_{_safe_name(date)}.docx"
    )
    matched = _patch_docx(template, output, fields)

    # Address and validity must be dynamic. Heading/body may already be correct
    # in the original sample, so their absence is not a reason to discard it.
    required = {"address", "validity"}
    missing = required - matched
    if missing:
        output.unlink(missing_ok=True)
        raise ValueError(
            "Original certificate fields not found: " + ", ".join(sorted(missing))
        )

    log.info(
        "Original BSF certificate generated from %s; patched fields: %s",
        template,
        ", ".join(sorted(matched)),
    )
    return output


def install_original_certificate_templates() -> None:
    """Use only the user's original BSF certificate samples in production."""

    def build_certificate(session: dict):
        return _build_from_original_template(session)

    bot.build_certificate = build_certificate
