"""Runtime hardening layer for the BSF inspection bot.

This module preserves the existing report-generation code while fixing the most
important operational risks: group selection, unique photo names, access
control, non-blocking AI/report work, and session recovery after failures.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

import inspection_bot as bot

log = logging.getLogger(__name__)


def _parse_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    values: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.add(int(item))
        except ValueError:
            log.warning("Ignoring invalid Telegram user ID: %s", item)
    return values


ALLOWED_USER_IDS = _parse_ids(os.getenv("ALLOWED_USER_IDS"))
ADMIN_USER_IDS = _parse_ids(os.getenv("ADMIN_USER_IDS"))


def _is_allowed(user_id: int | None) -> bool:
    # Backward-compatible default: when no allowlist is configured, do not lock
    # the owner out. Railway should still define ALLOWED_USER_IDS in production.
    return not ALLOWED_USER_IDS or (user_id is not None and user_id in ALLOWED_USER_IDS)


def _is_admin(user_id: int | None) -> bool:
    if ADMIN_USER_IDS:
        return user_id is not None and user_id in ADMIN_USER_IDS
    return _is_allowed(user_id)


async def _deny(update: Update, message: str) -> int:
    if update.effective_message:
        await update.effective_message.reply_text(message, reply_markup=ReplyKeyboardRemove())
    return bot.ConversationHandler.END


def _ensure_inspection_id(session: dict) -> str:
    inspection_id = session.get("inspection_id")
    if not inspection_id:
        inspection_id = uuid.uuid4().hex
        session["inspection_id"] = inspection_id
    return inspection_id


def _safe_project_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("._") or "inspection"


_original_cmd_start = bot.cmd_start
_original_got_element_status = bot.got_element_status
_original_cmd_status = bot.cmd_status


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_allowed(user_id):
        return await _deny(update, "⛔ You are not authorized to use this bot.")

    chat_id = update.effective_chat.id
    bot.clear_session(chat_id)
    session = {
        "inspection_id": uuid.uuid4().hex,
        "groups": [],
        "plans": [],
        "davit_detail": None,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "report_status": "draft",
    }
    bot.save_session(chat_id, session)

    buttons = [["📝 Write a report"]]
    if _is_admin(user_id):
        buttons.insert(0, ["📁 Define new project"])

    await update.message.reply_text(
        "👷 *BSF Inspections – Report Bot*\n\nWhat would you like to do?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return bot.STATE_MAIN_MENU


async def got_main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None

    if "Define" in choice or "project" in choice.lower() and "report" not in choice.lower():
        if not _is_admin(user_id):
            return await _deny(update, "⛔ Only an administrator can define projects.")
        await update.message.reply_text(
            "➕ *Add new project*\n\nWhat is the *project name*?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return bot.STATE_ADMIN_PROJECT_NAME

    chat_id = update.effective_chat.id
    session = bot.load_session(chat_id)
    _ensure_inspection_id(session)
    session.setdefault("groups", [])
    session.setdefault("plans", [])
    session.setdefault("davit_detail", None)
    session["report_status"] = "draft"
    bot.save_session(chat_id, session)

    inspection_types = bot.get_inspection_types()
    if inspection_types:
        labels = [item["name"] if isinstance(item, dict) else str(item) for item in inspection_types]
        buttons = [[label] for label in labels]
        await update.message.reply_text(
            "🔎 Which inspection type?",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_INSPECTION_TYPE

    # Keep old projects working even when projects.json has no inspection_types.
    projects = bot.get_projects()
    if not projects:
        await update.message.reply_text("⚠️ No projects found. Define a project first.")
        return bot.STATE_MAIN_MENU
    buttons = [[p["name"]] for p in projects]
    await update.message.reply_text(
        "📋 Which project?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return bot.STATE_PROJECT_SELECT


async def got_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = bot.load_session(chat_id)
    inspection_id = _ensure_inspection_id(session)
    bot.save_session(chat_id, session)

    inspection_dir = bot.PHOTOS_DIR / inspection_id
    inspection_dir.mkdir(parents=True, exist_ok=True)
    photo_path = inspection_dir / f"{uuid.uuid4().hex}.jpg"

    photo_file = await update.message.photo[-1].get_file()
    await photo_file.download_to_drive(str(photo_path))
    ctx.user_data["pending_photo_path"] = str(photo_path)

    groups = session.get("groups", [])
    if groups:
        buttons = [
            [f"[{i + 1}] {g.get('element_type', 'Group')} ({len(g.get('photos', []))} photos)"]
            for i, g in enumerate(groups)
        ]
        buttons.append(["🆕 New element type"])
        await update.message.reply_text(
            "📷 Photo received!\n\nAdd to which group?",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_GROUP_OR_ADD

    await update.message.reply_text(
        "📷 First photo!\n\n🔩 What *element type* is this?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(bot.ELEMENT_TYPES, one_time_keyboard=True, resize_keyboard=True),
    )
    return bot.STATE_ELEMENT_TYPE


async def got_group_or_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    chat_id = update.effective_chat.id
    session = bot.load_session(chat_id)

    if "New element" in choice or choice.startswith("🆕"):
        await update.message.reply_text(
            "🆕 New group!\n\n🔩 What *element type* is this?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(bot.ELEMENT_TYPES, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_ELEMENT_TYPE

    match = re.match(r"^\[(\d+)]", choice)
    if not match:
        await update.message.reply_text("❌ Please select one of the listed groups.")
        return bot.STATE_GROUP_OR_ADD

    index = int(match.group(1)) - 1
    groups = session.get("groups", [])
    if index < 0 or index >= len(groups):
        await update.message.reply_text("❌ That group no longer exists. Please select again.")
        return bot.STATE_GROUP_OR_ADD

    ctx.user_data["add_to_group_idx"] = index
    await update.message.reply_text(
        "What is the status of this element?",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["✅ Acceptable"],
                ["🔧 Réparation requise"],
                ["🔄 Remplacement requis"],
                ["❌ Rejeté"],
            ],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return bot.STATE_ELEMENT_STATUS


async def analyse_photo_async(image_bytes: bytes, element_type: str, location: str, problem: str):
    return await asyncio.to_thread(bot.analyse_photo, image_bytes, element_type, location, problem)


async def got_element_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Existing-group additions do not call AI, so the original handler is safe
    # and now receives the correct selected index from got_group_or_add.
    idx = ctx.user_data.get("add_to_group_idx")
    if idx is not None:
        return await _original_got_element_status(update, ctx)

    chat_id = update.effective_chat.id
    session = bot.load_session(chat_id)
    status = update.message.text.strip()
    ctx.user_data["pending_status"] = status
    await update.message.reply_text("🤖 Analysing photo with AI…")

    try:
        img_bytes = Path(ctx.user_data["pending_photo_path"]).read_bytes()
        ai = await analyse_photo_async(
            img_bytes,
            ctx.user_data.get("element_type", "Unknown"),
            ctx.user_data.get("location", "Unknown"),
            "",
        )
    except Exception:
        log.exception("AI photo analysis failed")
        ai = {
            "caption_fr": "Observation à compléter",
            "caption_en": "Observation to be completed",
            "severity": "minor",
        }

    ctx.user_data["pending_ai"] = ai
    inspection_type = session.get("inspection_type", "")
    element_type = ctx.user_data.get("element_type", "")
    auto_caption = bot.CAPTION_MAP.get(
        (inspection_type, element_type), ai.get("caption_fr", "Observation à compléter")
    )
    options = [["✅ " + auto_caption]]
    ai_caption = ai.get("caption_fr", "")
    if ai_caption and ai_caption != auto_caption:
        options.append(["✅ " + ai_caption])
    options.append(["✏️ Write my own"])
    ctx.user_data["auto_caption"] = auto_caption

    await update.message.reply_text(
        "Choose caption or write your own:",
        reply_markup=ReplyKeyboardMarkup(options, one_time_keyboard=True, resize_keyboard=True),
    )
    return bot.STATE_GROUP_CAPTION_FR


async def _send_report(chat_id: int, session_snapshot: dict, application) -> None:
    try:
        report_fr = await asyncio.to_thread(bot.build_report, session_snapshot, "fr")
        with open(report_fr, "rb") as report_file:
            await application.bot.send_document(
                chat_id=chat_id,
                document=report_file,
                filename=report_fr.name,
                caption="🇫🇷 Rapport Word",
            )

        try:
            pdf_out = report_fr.with_suffix(".pdf")
            await asyncio.to_thread(bot.docx_to_pdf, str(report_fr), str(pdf_out))
            if pdf_out.exists():
                with open(pdf_out, "rb") as pdf_file:
                    await application.bot.send_document(
                        chat_id=chat_id,
                        document=pdf_file,
                        filename=pdf_out.name,
                        caption="🇫🇷 Rapport PDF",
                    )
        except Exception:
            log.exception("PDF generation failed for chat %s", chat_id)
            await application.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Word report was created, but PDF conversion failed.",
            )

        current = bot.load_session(chat_id)
        if current.get("inspection_id") == session_snapshot.get("inspection_id"):
            bot.clear_session(chat_id)
        await application.bot.send_message(
            chat_id=chat_id,
            text="✅ Rapport envoyé!\nType /start for a new inspection.",
        )
    except Exception as exc:
        log.exception("Report generation failed for chat %s", chat_id)
        current = bot.load_session(chat_id) or session_snapshot
        current["report_status"] = "failed"
        current["report_error"] = str(exc)[:500]
        bot.save_session(chat_id, current)
        await application.bot.send_message(
            chat_id=chat_id,
            text="❌ Report generation failed. Your inspection was preserved. Use /done to retry.",
        )


async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = bot.load_session(chat_id)
    groups = session.get("groups", [])
    total = sum(len(g.get("photos", [])) for g in groups)
    if not groups:
        await update.message.reply_text("⚠️ No photos yet.")
        return bot.STATE_PHOTO
    if session.get("report_status") == "processing":
        await update.message.reply_text("⏳ This report is already being generated.")
        return bot.ConversationHandler.END

    session["report_status"] = "processing"
    session.pop("report_error", None)
    bot.save_session(chat_id, session)
    snapshot = copy.deepcopy(session)

    await update.message.reply_text(
        f"📝 Report queued for *{session.get('project_name', 'inspection')}*…\n"
        f"{len(groups)} group(s), {total} photo(s). You can continue using Telegram.",
        parse_mode="Markdown",
    )
    ctx.application.create_task(_send_report(chat_id, snapshot, ctx.application))
    return bot.ConversationHandler.END


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _original_cmd_status(update, ctx)
    session = bot.load_session(update.effective_chat.id)
    status = session.get("report_status")
    if status == "processing":
        await update.message.reply_text("⏳ Report generation is in progress.")
    elif status == "failed":
        await update.message.reply_text("⚠️ Last report attempt failed. Your data is preserved; use /done to retry.")


def install_patches() -> None:
    if not ALLOWED_USER_IDS:
        log.warning("ALLOWED_USER_IDS is not configured; all Telegram users are currently allowed.")
    if not ADMIN_USER_IDS:
        log.warning("ADMIN_USER_IDS is not configured; allowed users currently have admin access.")

    bot.cmd_start = cmd_start
    bot.got_main_menu = got_main_menu
    bot.got_photo = got_photo
    bot.got_group_or_add = got_group_or_add
    bot.got_element_status = got_element_status
    bot.cmd_done = cmd_done
    bot.cmd_status = cmd_status


if __name__ == "__main__":
    install_patches()
    bot.main()
