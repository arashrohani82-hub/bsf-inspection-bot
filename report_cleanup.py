"""Final report cleanup for facade inspections."""

from __future__ import annotations

import logging
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches

import inspection_bot as bot

log = logging.getLogger(__name__)

NO_ANOMALY_LABEL = "Aucune anomalie visible"
OFFICE_UNCLASSIFIED = "À classer – import bureau"


def _facade_issues(groups: list[dict]) -> list[str]:
    """Treat recorded facade anomalies as issues, including zone-grouped reports."""
    results: list[str] = []
    for group in groups:
        label = str(group.get("element_type", "")).strip()
        statuses = {
            str(photo.get("status", "✅ Acceptable"))
            for photo in group.get("photos", [])
        }

        recorded = [
            str(item)
            for item in group.get("facade_anomalies", [])
            if str(item) not in {NO_ANOMALY_LABEL, OFFICE_UNCLASSIFIED}
        ]
        if group.get("facade_anomalies") is not None:
            has_recorded_anomaly = bool(recorded)
        else:
            is_facade_group = label.startswith("Façade ")
            has_recorded_anomaly = is_facade_group and NO_ANOMALY_LABEL not in label

        has_nonacceptable_status = any(
            "Acceptable" not in status and "À classer" not in status
            for status in statuses
        )

        if not has_recorded_anomaly and not has_nonacceptable_status:
            continue

        caption = group.get("caption_fr") or label or "Élément inspecté"
        status_text = ", ".join(sorted(statuses))
        results.append(f"{caption} ({status_text})")
    return results


def _renumber_facade_headings(doc: Document) -> bool:
    changed = False
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text.startswith("10. Limitations et réserves"):
            replacement = text.replace(
                "10. Limitations et réserves",
                "9. Limitations et réserves",
                1,
            )
            if paragraph.runs:
                paragraph.runs[0].text = replacement
                for run in paragraph.runs[1:]:
                    run.text = ""
            else:
                paragraph.text = replacement
            changed = True
    return changed


def _table_contains_picture(table_element) -> bool:
    return bool(table_element.xpath(".//a:blip"))


def _insert_page_break_before_first_photo_table(doc: Document) -> bool:
    body = doc._body._body
    first_photo_table = None
    for child in body.iterchildren():
        if child.tag == qn("w:tbl") and _table_contains_picture(child):
            first_photo_table = child
            break

    if first_photo_table is None:
        return False

    previous = first_photo_table.getprevious()
    if previous is not None and previous.tag == qn("w:p"):
        if previous.xpath(".//w:br[@w:type='page']") or previous.xpath(
            ".//w:pageBreakBefore"
        ):
            return False

    page_paragraph = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    page_before = OxmlElement("w:pageBreakBefore")
    ppr.append(page_before)
    page_paragraph.append(ppr)
    first_photo_table.addprevious(page_paragraph)
    return True


def _protect_header_clearance(doc: Document) -> bool:
    changed = False
    for section in doc.sections:
        if section.top_margin is None or section.top_margin < Inches(1.15):
            section.top_margin = Inches(1.15)
            changed = True
        if section.header_distance is None or section.header_distance > Inches(0.45):
            section.header_distance = Inches(0.35)
            changed = True
    return changed


def _cleanup_facade_report(path: Path) -> None:
    doc = Document(path)
    changed = False
    changed = _renumber_facade_headings(doc) or changed
    changed = _insert_page_break_before_first_photo_table(doc) or changed
    changed = _protect_header_clearance(doc) or changed

    if changed:
        doc.save(path)
        log.info("Applied final facade layout cleanup to %s", path)


def install_report_cleanup() -> None:
    original_issues = bot.report_profiles._issues
    original_build_report = bot.build_report

    def issues(groups: list[dict]) -> list[str]:
        if any(
            str(group.get("element_type", "")).startswith("Façade ")
            for group in groups
        ):
            return _facade_issues(groups)
        return original_issues(groups)

    def build_report(session: dict, lang: str):
        output = original_build_report(session, lang)
        if bot.report_profiles.profile_key(
            session.get("inspection_type")
        ) == "facade":
            _cleanup_facade_report(Path(output))
        return output

    bot.report_profiles._issues = issues
    bot.build_report = build_report
