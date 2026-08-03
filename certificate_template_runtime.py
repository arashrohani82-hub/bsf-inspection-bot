"""Generate certificates by patching the original BSF DOCX packages directly.

The original samples rely on positioned text boxes and drawing-layer content.
Editing them through python-docx can miss those runs or rebuild the document.
This module instead copies the original DOCX package and replaces text directly
inside its XML parts, preserving the exact background, logo, signature, colours,
fonts, shapes and one-page layout.
"""

from __future__ import annotations

import html
import logging
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

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


def _xml_text(value: str) -> str:
    return html.escape(str(value), quote=False)


def _replace_visible_text(xml: str, old: str, new: str) -> tuple[str, bool]:
    """Replace text even when Word split it across multiple w:t nodes."""
    old_normalized = re.sub(r"\s+", " ", old).strip()
    # Fast path: literal text exists in one XML text node.
    for candidate in {old, _xml_text(old)}:
        if candidate in xml:
            return xml.replace(candidate, _xml_text(new), 1), True

    # Tolerant path: flatten the XML's visible text while retaining character
    # offsets back to the original XML. This handles text split across runs.
    text_matches = list(re.finditer(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", xml, re.DOTALL))
    if not text_matches:
        return xml, False

    visible_parts: list[str] = []
    mapping: list[tuple[int, int]] = []
    for match in text_matches:
        decoded = html.unescape(match.group(1))
        for index, char in enumerate(decoded):
            visible_parts.append(char)
            mapping.append((match.start(1) + index, match.start(1) + index + 1))
    visible = "".join(visible_parts)
    compact = re.sub(r"\s+", " ", visible)
    position = compact.lower().find(old_normalized.lower())
    if position < 0:
        return xml, False

    # The compacted string cannot be mapped safely character-by-character when
    # whitespace collapsed, so locate a robust start/end using key fragments.
    first_words = " ".join(old_normalized.split()[:4])
    last_words = " ".join(old_normalized.split()[-4:])
    start_vis = visible.lower().find(first_words.lower())
    end_anchor = visible.lower().find(last_words.lower(), max(start_vis, 0))
    if start_vis < 0 or end_anchor < 0:
        return xml, False
    end_vis = end_anchor + len(last_words)

    start_xml = mapping[start_vis][0]
    end_xml = mapping[min(end_vis - 1, len(mapping) - 1)][1]
    # Remove any intervening tags only within the matched visible region and
    # insert the replacement into the first text node's content.
    prefix = xml[:start_xml]
    segment = xml[start_xml:end_xml]
    suffix = xml[end_xml:]
    segment = re.sub(r">[^<]*<", "><", segment)
    segment = re.sub(r"^[^<]*", _xml_text(new), segment, count=1)
    return prefix + segment + suffix, True


def _patch_docx(template: Path, output: Path, replacements: list[tuple[str, str]]) -> set[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    matched: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="bsf_certificate_") as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(template, "r") as source:
            source.extractall(temp_root)

        for xml_path in temp_root.rglob("*.xml"):
            try:
                xml = xml_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            changed = False
            for key, (old, new) in enumerate(replacements):
                marker = str(key)
                if marker in matched:
                    continue
                xml, did_replace = _replace_visible_text(xml, old, new)
                if did_replace:
                    matched.add(marker)
                    changed = True
            if changed:
                xml_path.write_text(xml, encoding="utf-8")

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
        old_heading = "Inspection annuelle des systèmes d’ancrage et de ligne de vie et des bossoirs"
        new_heading = "Inspection annuelle des systèmes d’ancrage et de ligne de vie et des bossoirs"
        old_address = "ADRESSE D’INSTALLATION : 198 Rue Ann Le sud-Ouest Montréal, Québec , H3C 0T2"
        new_address = f"ADRESSE D’INSTALLATION : {address}"
        old_body = (
            "a fait l’objet d’une inspection annuelle complète ainsi que des travaux d’entretien requis, "
            "réalisés conformément aux articles 11.8 et 12 de la norme CAN/CSA Z271, par un technicien "
            "qualifié de BSF Inspections, en référence au rapport d’inspection correspondant."
        )
        new_body = old_body
        old_validity = "VALIDITÉ DU CERTIFICAT : Certificat valide du 2026-06-01 se terminant dans les douze (12) mois suivant"
        new_validity = (
            "VALIDITÉ DU CERTIFICAT : Certificat valide du "
            f"{date} se terminant dans les douze (12) mois suivant"
        )
    else:
        old_heading = "Inspection quinquennale de des systèmes d’ancrage et des bossoirs"
        new_heading = "Inspection quinquennale des systèmes d’ancrage et des bossoirs"
        old_address = "ADRESSE D’INSTALLATION : au 200 Av. des Sommets, Montréal, QC H3E 2B4"
        new_address = f"ADRESSE D’INSTALLATION : {address}"
        old_body = (
            "La présente attestation confirme que l’unité d’accès suspendu visée a fait l’objet d’une inspection "
            "quinquennale comprenant l’examen visuel des systèmes d’ancrage, des bossoirs ainsi que la réalisation "
            "des essais applicables, conformément aux exigences pertinentes des normes CAN/CSA Z271, CSA Z91 et ASTM "
            "E3121 / E3121M, en référence au rapport d’inspection correspondant."
        )
        new_body = old_body
        old_validity = (
            "Le présent certificat confirme la réalisation de l’inspection quinquennale en date du 22 juillet 2026. "
            "Il demeure entendu que les inspections annuelles requises doivent continuer d’être effectuées "
            "indépendamment de la présente attestation."
        )
        new_validity = (
            "Le présent certificat confirme la réalisation de l’inspection quinquennale en date du "
            f"{_french_long_date(date)}. Il demeure entendu que les inspections annuelles requises doivent "
            "continuer d’être effectuées indépendamment de la présente attestation."
        )

    if mode == "with_exclusions":
        exclusion_text = "; ".join(exclusions) or "les éléments expressément identifiés au rapport"
        new_body += (
            " Sont exclus du présent certificat : " + exclusion_text + ". Ces éléments doivent demeurer "
            "hors service jusqu’à la réalisation des correctifs et, lorsque requis, d’une nouvelle inspection."
        )

    replacements = [
        (old_heading, new_heading),
        (old_address, new_address),
        (old_body, new_body),
        (old_validity, new_validity),
    ]

    bot.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = bot.REPORTS_DIR / (
        f"{_safe_name(project)}_BSF_ORIGINAL_Certificate_{profile_name}_{_safe_name(date)}.docx"
    )
    matched = _patch_docx(template, output, replacements)
    if len(matched) < 2:
        output.unlink(missing_ok=True)
        raise ValueError(
            f"Original BSF template could not be patched reliably; matched {len(matched)} of 4 fields"
        )

    log.info(
        "Original BSF certificate generated from %s; patched %s field(s)",
        template,
        len(matched),
    )
    return output


def install_original_certificate_templates() -> None:
    """Use only the user's original BSF certificate samples in production."""
    def build_certificate(session: dict):
        return _build_from_original_template(session)

    bot.build_certificate = build_certificate
