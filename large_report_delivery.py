"""Safe delivery path for very large facade inspections.

Facade reports with hundreds of photographs can exceed the memory available to
python-docx/Railway when assembled as one package. This module patches the
hardened sender so large facade inspections are built and delivered in bounded
parts while preserving the original inspection session until every part has
been sent successfully.

Figure metadata is assigned before splitting so Part 2, Part 3, etc. continue
the exact numbering of the complete inspection instead of restarting at 1a.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from pathlib import Path

import inspection_bot as bot
import hardened_runner as hard

log = logging.getLogger(__name__)

MAX_PHOTOS_PER_PART = 120
SPLIT_THRESHOLD = 150


def _photo_count(session: dict) -> int:
    return sum(len(group.get("photos", [])) for group in session.get("groups", []))


def _facade_zone(label: str) -> str:
    """Extract the physical zone from a facade group label."""
    parts = [part.strip() for part in str(label).split(" — ") if part.strip()]
    if not parts:
        return "Façade"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0]
    return " — ".join(parts[:-1])


def _number_complete_inspection(session: dict) -> dict:
    """Attach stable figure number and suffix index to every facade photo.

    Photos in the same physical zone share one figure number. Their letter index
    continues across all anomaly groups and, later, across all generated parts.
    """
    numbered = copy.deepcopy(session)
    zone_numbers: dict[str, int] = {}
    zone_offsets: dict[str, int] = {}
    next_figure = 1

    for group in numbered.get("groups", []):
        zone = _facade_zone(group.get("element_type", ""))
        if zone not in zone_numbers:
            zone_numbers[zone] = next_figure
            zone_offsets[zone] = 0
            next_figure += 1

        figure_number = zone_numbers[zone]
        for photo in group.get("photos", []):
            photo["_figure_number"] = figure_number
            photo["_figure_letter_index"] = zone_offsets[zone]
            zone_offsets[zone] += 1

    return numbered


def _split_facade_session(session: dict, limit: int = MAX_PHOTOS_PER_PART) -> list[dict]:
    """Split groups without losing order, captions, status, zone, or numbering."""
    source = _number_complete_inspection(session)
    parts: list[dict] = []
    current = copy.deepcopy(source)
    current["groups"] = []
    current_count = 0

    def flush() -> None:
        nonlocal current, current_count
        if not current["groups"]:
            return
        parts.append(current)
        current = copy.deepcopy(source)
        current["groups"] = []
        current_count = 0

    for group in source.get("groups", []):
        photos = list(group.get("photos", []))
        cursor = 0
        while cursor < len(photos):
            available = limit - current_count
            if available <= 0:
                flush()
                available = limit

            take = min(available, len(photos) - cursor)
            piece = copy.deepcopy(group)
            piece["photos"] = copy.deepcopy(photos[cursor : cursor + take])
            current["groups"].append(piece)
            current_count += take
            cursor += take

            if current_count >= limit:
                flush()

    flush()
    return parts


def _part_filename(path: Path, index: int, total: int) -> Path:
    return path.with_name(
        f"{path.stem}_Part_{index:02d}_of_{total:02d}{path.suffix}"
    )


async def _send_large_facade_report(chat_id: int, session_snapshot: dict, application) -> None:
    parts = _split_facade_session(session_snapshot)
    total_parts = len(parts)
    total_photos = _photo_count(session_snapshot)

    try:
        await application.bot.send_message(
            chat_id=chat_id,
            text=(
                f"📚 Rapport volumineux détecté : {total_photos} photos. "
                f"Le rapport sera envoyé en {total_parts} parties Word."
            ),
        )

        for index, part in enumerate(parts, 1):
            part_photos = _photo_count(part)
            await application.bot.send_message(
                chat_id=chat_id,
                text=f"⏳ Création de la partie {index}/{total_parts} ({part_photos} photos)…",
            )

            report_path = Path(
                await asyncio.to_thread(bot.build_report, part, "fr")
            )
            final_path = _part_filename(report_path, index, total_parts)
            if final_path.exists():
                final_path.unlink()
            report_path.replace(final_path)

            with open(final_path, "rb") as report_file:
                await application.bot.send_document(
                    chat_id=chat_id,
                    document=report_file,
                    filename=final_path.name,
                    caption=f"🇫🇷 Rapport Word — Partie {index}/{total_parts}",
                )

            # Avoid automatic PDF generation for hundreds of photos because it
            # duplicates memory use. The engineering Word deliverables remain.
            await asyncio.sleep(0)

        current = bot.load_session(chat_id)
        if current.get("inspection_id") == session_snapshot.get("inspection_id"):
            bot.clear_session(chat_id)

        await application.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ Rapport complet envoyé en {total_parts} parties "
                f"({total_photos} photos)."
            ),
        )

    except Exception as exc:
        log.exception("Large facade report generation failed for chat %s", chat_id)
        current = bot.load_session(chat_id) or session_snapshot
        current["report_status"] = "failed"
        current["report_error"] = str(exc)[:500]
        bot.save_session(chat_id, current)
        await application.bot.send_message(
            chat_id=chat_id,
            text=(
                "❌ La génération du rapport volumineux a échoué. "
                "L’inspection complète est conservée. Utilisez /done pour réessayer."
            ),
        )


_original_send_report = hard._send_report


async def _send_report(chat_id: int, session_snapshot: dict, application) -> None:
    is_facade = (
        bot.report_profiles.profile_key(session_snapshot.get("inspection_type"))
        == "facade"
    )
    if is_facade and _photo_count(session_snapshot) > SPLIT_THRESHOLD:
        return await _send_large_facade_report(chat_id, session_snapshot, application)
    return await _original_send_report(chat_id, session_snapshot, application)


def install_large_report_delivery() -> None:
    hard._send_report = _send_report
    log.info(
        "Large facade report delivery enabled (threshold=%s, part=%s)",
        SPLIT_THRESHOLD,
        MAX_PHOTOS_PER_PART,
    )
