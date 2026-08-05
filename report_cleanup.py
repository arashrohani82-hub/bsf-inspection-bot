"""Final report cleanup for facade inspections."""

from __future__ import annotations

import logging
from pathlib import Path

from docx import Document

import inspection_bot as bot

log = logging.getLogger(__name__)

NO_ANOMALY_LABEL = "Aucune anomalie visible"


def _facade_issues(groups: list[dict]) -> list[str]:
    """Treat every recorded facade anomaly as an issue, regardless of status."""
    results: list[str] = []
    for group in groups:
        label = str(group.get("element_type", "")).strip()
        statuses = {
            str(photo.get("status", "✅ Acceptable"))
            for photo in group.get("photos", [])
        }

        is_facade_group = label.startswith("Façade ")
        has_recorded_anomaly = is_facade_group and NO_ANOMALY_LABEL not in label
        has_nonacceptable_status = any(
            "Acceptable" not in status for status in statuses
        )

        if not has_recorded_anomaly and not has_nonacceptable_status:
            continue

        caption = (
            group.get("caption_fr")
            or label
            or "Élément inspecté"
        )
        status_text = ", ".join(sorted(statuses))
        results.append(f"{caption} ({status_text})")
    return results


def _renumber_facade_headings(path: Path) -> None:
    """Correct the skipped section number in the generated facade DOCX."""
    doc = Document(path)
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

    if changed:
        doc.save(path)
        log.info("Corrected facade report section numbering in %s", path)


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
            _renumber_facade_headings(Path(output))
        return output

    bot.report_profiles._issues = issues
    bot.build_report = build_report
