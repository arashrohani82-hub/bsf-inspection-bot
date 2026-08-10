"""Facade-specific Telegram workflow for field and office capture."""

from __future__ import annotations

import copy
import uuid
from pathlib import Path

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

import inspection_bot as bot

FACADE_DIRECTIONS = [
    ["Façade nord", "Façade sud"],
    ["Façade est", "Façade ouest"],
]

SECTION_SETUP = [
    ["🏢 Bâtiment sans sous-sections"],
    ["🏨 Hôtel + Résidentiel"],
    ["✏️ Définir mes sections"],
]

MODE_SETUP = [
    ["🚧 Field Mode – Inspection sur place"],
    ["🗂 Office / Bulk Mode – Photos existantes"],
]

FACADE_ANOMALIES = [
    ["🪟 Bris de vitrage", "🧱 Joints de maçonnerie"],
    ["💧 Efflorescence", "🧴 Joints d’étanchéité"],
    ["🏗 Béton fissuré / éclaté", "⚠️ Autre anomalie"],
    ["✅ Aucune anomalie visible"],
]

ANOMALY_CANONICAL = {
    "🪟 Bris de vitrage": "Bris de vitrage",
    "🧱 Joints de maçonnerie": "Fissuration des joints de maçonnerie",
    "💧 Efflorescence": "Efflorescence / dépôts blanchâtres",
    "🧴 Joints d’étanchéité": "Déficience des joints d’étanchéité",
    "🏗 Béton fissuré / éclaté": "Béton fissuré ou éclaté",
    "⚠️ Autre anomalie": "Autre anomalie",
    "✅ Aucune anomalie visible": "Aucune anomalie visible",
}

ANOMALY_CAPTIONS = {
    "Bris de vitrage": "Bris ou fissuration du vitrage observé.",
    "Efflorescence / dépôts blanchâtres": "Présence d’efflorescence ou de dépôts blanchâtres sur le parement.",
    "Fissuration des joints de maçonnerie": "Fissuration ou détérioration des joints de mortier de la maçonnerie.",
    "Déficience des joints d’étanchéité": "Déficience, fissuration ou décollement des joints d’étanchéité entre les fenêtres, les panneaux vitrés ou les éléments adjacents.",
    "Béton fissuré ou éclaté": "Fissuration, éclatement ou détérioration localisée du béton.",
    "Autre anomalie": "Anomalie visible à préciser.",
    "Aucune anomalie visible": "Aucune anomalie apparente relevée sur la zone documentée.",
    "À classer – import bureau": "Photographies importées en mode bureau et à classer avant émission finale du rapport.",
}

DIRECTION_ORDER = {
    "Façade nord": 0,
    "Façade sud": 1,
    "Façade est": 2,
    "Façade ouest": 3,
}
ANOMALY_ORDER = {name: i for i, name in enumerate(list(ANOMALY_CAPTIONS))}


def _is_facade_session(session: dict) -> bool:
    return bot.report_profiles.profile_key(session.get("inspection_type")) == "facade"


def _section_keyboard(sections: list[str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[s] for s in sections], one_time_keyboard=True, resize_keyboard=True)


def _clean_sections(text: str) -> list[str]:
    values = text.replace(";", ",").replace("\n", ",").split(",")
    result: list[str] = []
    for item in values:
        item = item.strip()
        if item and item not in result:
            result.append(item)
    return result[:12]


def _zone_label(direction: str, section: str) -> str:
    return direction if section == "Bâtiment" else f"{direction} — {section}"


def _group_label(direction: str, section: str, anomaly: str) -> str:
    zone = _zone_label(direction, section)
    return f"{zone} — {anomaly}"


def _field_ready_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["📍 Change zone", "✅ Finish inspection"]],
        resize_keyboard=True,
    )


def install_facade_workflow() -> None:
    original_got_project_select = bot.got_project_select
    original_got_photo = bot.got_photo
    original_got_group_or_add = bot.got_group_or_add
    original_got_element_type = bot.got_element_type
    original_got_element_id = bot.got_element_id
    original_got_problem = bot.got_problem
    original_got_element_status = bot.got_element_status
    original_build_report = bot.build_report
    original_cmd_done = bot.cmd_done

    async def _ask_mode(update, ctx, session):
        ctx.user_data["facade_stage"] = "select_mode"
        await update.message.reply_text(
            "📋 *Mode de saisie*\n\nComment voulez-vous travailler?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(MODE_SETUP, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_ELEMENT_ID

    async def _ask_zone_direction(update, ctx):
        ctx.user_data["facade_stage"] = "select_direction"
        await update.message.reply_text(
            "📍 Sélectionnez la façade active :",
            reply_markup=ReplyKeyboardMarkup(FACADE_DIRECTIONS, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_ELEMENT_TYPE

    async def got_project_select(update, ctx: ContextTypes.DEFAULT_TYPE):
        result = await original_got_project_select(update, ctx)
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session) or result != bot.STATE_PHOTO:
            return result
        session.pop("facade_sections", None)
        session.pop("facade_mode", None)
        session.pop("facade_active_direction", None)
        session.pop("facade_active_section", None)
        bot.save_session(update.effective_chat.id, session)
        ctx.user_data["facade_stage"] = "configure_sections"
        await update.message.reply_text(
            "🏢 *Configuration du rapport de façade*\n\nQuelles sections du bâtiment doivent être distinguées?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(SECTION_SETUP, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_ELEMENT_ID

    async def got_photo(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session) or not session.get("facade_mode"):
            return await original_got_photo(update, ctx)

        direction = session.get("facade_active_direction")
        section = session.get("facade_active_section")
        if not direction or not section:
            await update.message.reply_text("📍 Choisissez d’abord la zone active.")
            return await _ask_zone_direction(update, ctx)

        inspection_id = session.get("inspection_id") or uuid.uuid4().hex
        session["inspection_id"] = inspection_id
        photo_dir = bot.PHOTOS_DIR / inspection_id
        photo_dir.mkdir(parents=True, exist_ok=True)
        photo_path = photo_dir / f"{uuid.uuid4().hex}.jpg"
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(str(photo_path))

        if session.get("facade_mode") == "field":
            ctx.user_data["pending_photo_path"] = str(photo_path)
            ctx.user_data["facade_direction"] = direction
            ctx.user_data["facade_section"] = section
            ctx.user_data["facade_stage"] = "field_anomaly"
            await update.message.reply_text(
                f"📸 {_zone_label(direction, section)}\nQuel type d’anomalie?",
                reply_markup=ReplyKeyboardMarkup(FACADE_ANOMALIES, one_time_keyboard=True, resize_keyboard=True),
            )
            return bot.STATE_PROBLEM

        # Office/Bulk: capture without asking anything between photos.
        group_label = _group_label(direction, section, "À classer – import bureau")
        groups = session.setdefault("groups", [])
        group = next((g for g in groups if g.get("element_type") == group_label), None)
        if group is None:
            group = {
                "element_type": group_label,
                "caption_fr": ANOMALY_CAPTIONS["À classer – import bureau"],
                "caption_en": "Office-import photos pending classification.",
                "severity": "minor",
                "photos": [],
            }
            groups.append(group)
        group["photos"].append({"path": str(photo_path), "status": "À classer"})
        bot.save_session(update.effective_chat.id, session)
        count = len(group["photos"])
        await update.message.reply_text(
            f"✅ {count} photo(s) enregistrée(s) dans {_zone_label(direction, section)}.\n"
            "Envoyez la suivante, /zone pour changer de zone, ou /done pour terminer.",
        )
        return bot.STATE_PHOTO

    async def got_group_or_add(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        choice = update.message.text.strip()
        if _is_facade_session(session) and ("New element" in choice or choice.startswith("🆕")):
            return await _ask_zone_direction(update, ctx)
        return await original_got_group_or_add(update, ctx)

    async def got_element_type(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session):
            return await original_got_element_type(update, ctx)
        direction = update.message.text.strip()
        valid = {x for row in FACADE_DIRECTIONS for x in row}
        if direction not in valid:
            return await _ask_zone_direction(update, ctx)
        ctx.user_data["facade_direction"] = direction
        sections = session.get("facade_sections") or ["Bâtiment"]
        if len(sections) == 1:
            session["facade_active_direction"] = direction
            session["facade_active_section"] = sections[0]
            bot.save_session(update.effective_chat.id, session)
            await update.message.reply_text(
                f"✅ Zone active : {_zone_label(direction, sections[0])}\n\n📸 Envoyez une photo.",
                reply_markup=_field_ready_keyboard() if session.get("facade_mode") == "field" else ReplyKeyboardRemove(),
            )
            return bot.STATE_PHOTO
        ctx.user_data["facade_stage"] = "select_section"
        await update.message.reply_text(
            f"🏢 {direction}\nDans quelle section?",
            reply_markup=_section_keyboard(sections),
        )
        return bot.STATE_ELEMENT_ID

    async def got_element_id(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session):
            return await original_got_element_id(update, ctx)
        stage = ctx.user_data.get("facade_stage")
        choice = update.message.text.strip()

        if stage == "configure_sections":
            if choice == "🏢 Bâtiment sans sous-sections":
                sections = ["Bâtiment"]
            elif choice == "🏨 Hôtel + Résidentiel":
                sections = ["Hôtel", "Résidentiel"]
            elif choice == "✏️ Définir mes sections":
                ctx.user_data["facade_stage"] = "custom_sections"
                await update.message.reply_text(
                    "Écrivez les sections séparées par des virgules. Exemple : Hôtel, Résidentiel, Basilaire",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return bot.STATE_ELEMENT_ID
            else:
                await update.message.reply_text("Veuillez choisir une option.", reply_markup=ReplyKeyboardMarkup(SECTION_SETUP, resize_keyboard=True))
                return bot.STATE_ELEMENT_ID
            session["facade_sections"] = sections
            bot.save_session(update.effective_chat.id, session)
            return await _ask_mode(update, ctx, session)

        if stage == "custom_sections":
            sections = _clean_sections(choice)
            if not sections:
                await update.message.reply_text("Aucune section valide. Exemple : Hôtel, Résidentiel")
                return bot.STATE_ELEMENT_ID
            session["facade_sections"] = sections
            bot.save_session(update.effective_chat.id, session)
            return await _ask_mode(update, ctx, session)

        if stage == "select_mode":
            if choice.startswith("🚧"):
                session["facade_mode"] = "field"
            elif choice.startswith("🗂"):
                session["facade_mode"] = "office"
            else:
                await update.message.reply_text("Veuillez choisir Field Mode ou Office / Bulk Mode.", reply_markup=ReplyKeyboardMarkup(MODE_SETUP, resize_keyboard=True))
                return bot.STATE_ELEMENT_ID
            bot.save_session(update.effective_chat.id, session)
            return await _ask_zone_direction(update, ctx)

        if stage == "select_section":
            sections = session.get("facade_sections") or ["Bâtiment"]
            if choice not in sections:
                await update.message.reply_text("Veuillez sélectionner une section.", reply_markup=_section_keyboard(sections))
                return bot.STATE_ELEMENT_ID
            direction = ctx.user_data.get("facade_direction", "Façade")
            session["facade_active_direction"] = direction
            session["facade_active_section"] = choice
            bot.save_session(update.effective_chat.id, session)
            ctx.user_data.pop("facade_stage", None)
            await update.message.reply_text(
                f"✅ Zone active : {_zone_label(direction, choice)}\n\n📸 Envoyez une photo.",
                reply_markup=_field_ready_keyboard() if session.get("facade_mode") == "field" else ReplyKeyboardRemove(),
            )
            return bot.STATE_PHOTO

        return await original_got_element_id(update, ctx)

    async def got_problem(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session) or ctx.user_data.get("facade_stage") != "field_anomaly":
            return await original_got_problem(update, ctx)

        choice = update.message.text.strip()
        anomaly = ANOMALY_CANONICAL.get(choice)
        if not anomaly:
            await update.message.reply_text("Choisissez une catégorie.", reply_markup=ReplyKeyboardMarkup(FACADE_ANOMALIES, resize_keyboard=True))
            return bot.STATE_PROBLEM

        direction = session.get("facade_active_direction")
        section = session.get("facade_active_section") or "Bâtiment"
        label = _group_label(direction, section, anomaly)
        groups = session.setdefault("groups", [])
        group = next((g for g in groups if g.get("element_type") == label), None)
        if group is None:
            group = {
                "element_type": label,
                "caption_fr": ANOMALY_CAPTIONS[anomaly],
                "caption_en": "",
                "severity": "ok" if anomaly == "Aucune anomalie visible" else "minor",
                "photos": [],
            }
            groups.append(group)
        status = "✅ Acceptable" if anomaly == "Aucune anomalie visible" else "🔧 Réparation requise"
        group["photos"].append({"path": ctx.user_data["pending_photo_path"], "status": status})
        bot.save_session(update.effective_chat.id, session)
        ctx.user_data.pop("facade_stage", None)
        await update.message.reply_text(
            f"✅ Enregistré : {anomaly}\n📍 {_zone_label(direction, section)}\n\n📸 Photo suivante ou changez de zone.",
            reply_markup=_field_ready_keyboard(),
        )
        return bot.STATE_PHOTO

    async def cmd_done(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session):
            return await original_cmd_done(update, ctx)
        return await original_cmd_done(update, ctx)

    async def cmd_zone(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session):
            await update.message.reply_text("Cette commande est réservée aux inspections de façade.")
            return bot.STATE_PHOTO
        return await _ask_zone_direction(update, ctx)

    def build_report(session: dict, lang: str):
        if not _is_facade_session(session):
            return original_build_report(session, lang)
        ordered = copy.deepcopy(session)
        sections = ordered.get("facade_sections") or ["Bâtiment"]
        section_order = {name: i for i, name in enumerate(sections)}

        def sort_key(group: dict):
            parts = [p.strip() for p in group.get("element_type", "").split(" — ")]
            direction = parts[0] if parts else ""
            if len(parts) >= 3:
                section, anomaly = parts[1], " — ".join(parts[2:])
            else:
                section, anomaly = "Bâtiment", parts[1] if len(parts) > 1 else ""
            return (DIRECTION_ORDER.get(direction, 99), section_order.get(section, 99), ANOMALY_ORDER.get(anomaly, 99))

        ordered["groups"] = sorted(ordered.get("groups", []), key=sort_key)
        return original_build_report(ordered, lang)

    original_get_element_types = bot.get_element_types_for_session

    def get_element_types_for_session(session: dict):
        if _is_facade_session(session):
            return FACADE_DIRECTIONS
        return original_get_element_types(session)

    bot.get_element_types_for_session = get_element_types_for_session
    bot.got_project_select = got_project_select
    bot.got_photo = got_photo
    bot.got_group_or_add = got_group_or_add
    bot.got_element_type = got_element_type
    bot.got_element_id = got_element_id
    bot.got_problem = got_problem
    bot.got_element_status = original_got_element_status
    bot.cmd_done = cmd_done
    bot.cmd_zone = cmd_zone
    bot.build_report = build_report
