"""Facade-specific Telegram workflow and deterministic report ordering."""

from __future__ import annotations

import copy

from telegram import ReplyKeyboardMarkup
from telegram.ext import ContextTypes

import inspection_bot as bot

FACADE_DIRECTIONS = [
    ["Façade nord", "Façade sud"],
    ["Façade est", "Façade ouest"],
]

FACADE_ANOMALIES = [
    ["Bris de vitrage"],
    ["Efflorescence / dépôts blanchâtres"],
    ["Fissuration des joints de maçonnerie"],
    ["Déficience des joints d’étanchéité"],
    ["Béton fissuré ou éclaté"],
    ["Autre anomalie"],
    ["Aucune anomalie visible"],
]

ANOMALY_CAPTIONS = {
    "Bris de vitrage": "Bris ou fissuration du vitrage observé.",
    "Efflorescence / dépôts blanchâtres": (
        "Présence d’efflorescence ou de dépôts blanchâtres sur le parement."
    ),
    "Fissuration des joints de maçonnerie": (
        "Fissuration ou détérioration des joints de mortier de la maçonnerie."
    ),
    "Déficience des joints d’étanchéité": (
        "Déficience, fissuration ou décollement des joints d’étanchéité entre les fenêtres, les panneaux vitrés ou les éléments adjacents."
    ),
    "Béton fissuré ou éclaté": (
        "Fissuration, éclatement ou détérioration localisée du béton."
    ),
    "Autre anomalie": "Anomalie visible à préciser.",
    "Aucune anomalie visible": "Aucune anomalie apparente relevée sur la zone documentée.",
}

DIRECTION_ORDER = {
    "Façade nord": 0,
    "Façade sud": 1,
    "Façade est": 2,
    "Façade ouest": 3,
}

ANOMALY_ORDER = {name: index for index, row in enumerate(FACADE_ANOMALIES) for name in row}


def _is_facade_session(session: dict) -> bool:
    return bot.report_profiles.profile_key(session.get("inspection_type")) == "facade"


def _status_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["✅ Acceptable"],
            ["🔧 Réparation requise"],
            ["🔄 Remplacement requis"],
            ["❌ Rejeté"],
        ],
        one_time_keyboard=True,
        resize_keyboard=True,
    )


def install_facade_workflow() -> None:
    original_got_group_or_add = bot.got_group_or_add
    original_got_element_type = bot.got_element_type
    original_got_problem = bot.got_problem
    original_got_element_status = bot.got_element_status
    original_build_report = bot.build_report

    async def got_group_or_add(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        choice = update.message.text.strip()
        if _is_facade_session(session) and (
            "New element" in choice or choice.startswith("🆕")
        ):
            ctx.user_data.pop("facade_direction", None)
            ctx.user_data.pop("facade_anomaly", None)
            ctx.user_data.pop("add_to_group_idx", None)
            await update.message.reply_text(
                "🆕 Nouvelle observation\n\nSur quelle façade se trouve-t-elle?",
                reply_markup=ReplyKeyboardMarkup(
                    FACADE_DIRECTIONS,
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return bot.STATE_ELEMENT_TYPE
        return await original_got_group_or_add(update, ctx)

    async def got_element_type(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session):
            return await original_got_element_type(update, ctx)

        direction = update.message.text.strip()
        valid_directions = {item for row in FACADE_DIRECTIONS for item in row}
        if direction not in valid_directions:
            await update.message.reply_text(
                "Veuillez sélectionner l’orientation de la façade.",
                reply_markup=ReplyKeyboardMarkup(
                    FACADE_DIRECTIONS,
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return bot.STATE_ELEMENT_TYPE

        ctx.user_data["facade_direction"] = direction
        ctx.user_data["location"] = direction
        ctx.user_data.pop("add_to_group_idx", None)
        await update.message.reply_text(
            f"🏢 {direction}\n\nQuel type d’anomalie est visible?",
            reply_markup=ReplyKeyboardMarkup(
                FACADE_ANOMALIES,
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
        return bot.STATE_PROBLEM

    async def got_problem(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session) or not ctx.user_data.get("facade_direction"):
            return await original_got_problem(update, ctx)

        anomaly = update.message.text.strip()
        valid_anomalies = {item for row in FACADE_ANOMALIES for item in row}
        if anomaly not in valid_anomalies:
            await update.message.reply_text(
                "Veuillez sélectionner une anomalie dans la liste.",
                reply_markup=ReplyKeyboardMarkup(
                    FACADE_ANOMALIES,
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return bot.STATE_PROBLEM

        direction = ctx.user_data["facade_direction"]
        group_label = f"{direction} — {anomaly}"
        ctx.user_data["facade_anomaly"] = anomaly
        ctx.user_data["element_type"] = group_label
        ctx.user_data["location"] = direction
        ctx.user_data["facade_caption"] = ANOMALY_CAPTIONS[anomaly]

        for index, group in enumerate(session.get("groups", [])):
            if group.get("element_type", "").strip() == group_label:
                ctx.user_data["add_to_group_idx"] = index
                break
        else:
            ctx.user_data.pop("add_to_group_idx", None)

        prompt = (
            "Quel est le statut de cet élément?"
            if anomaly == "Aucune anomalie visible"
            else "Quel niveau d’intervention doit être attribué à cette observation?"
        )
        await update.message.reply_text(prompt, reply_markup=_status_keyboard())
        return bot.STATE_ELEMENT_STATUS

    async def got_element_status(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session) or not ctx.user_data.get("facade_anomaly"):
            return await original_got_element_status(update, ctx)

        idx = ctx.user_data.get("add_to_group_idx")
        if idx is not None:
            return await original_got_element_status(update, ctx)

        ctx.user_data["auto_caption"] = ctx.user_data["facade_caption"]
        ctx.user_data["pending_ai"] = {
            "caption_fr": ctx.user_data["facade_caption"],
            "caption_en": "",
            "severity": "ok",
        }
        ctx.user_data["pending_status"] = update.message.text.strip()
        await update.message.reply_text(
            "Choisissez la légende proposée ou rédigez une observation plus précise :",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ["✅ " + ctx.user_data["facade_caption"]],
                    ["✏️ Write my own"],
                ],
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
        return bot.STATE_GROUP_CAPTION_FR

    def build_report(session: dict, lang: str):
        if not _is_facade_session(session):
            return original_build_report(session, lang)

        ordered = copy.deepcopy(session)

        def sort_key(group: dict):
            label = group.get("element_type", "")
            direction, _, anomaly = label.partition(" — ")
            return (
                DIRECTION_ORDER.get(direction, 99),
                ANOMALY_ORDER.get(anomaly, 99),
            )

        ordered["groups"] = sorted(ordered.get("groups", []), key=sort_key)
        return original_build_report(ordered, lang)

    original_get_element_types = bot.get_element_types_for_session

    def get_element_types_for_session(session: dict):
        if _is_facade_session(session):
            return FACADE_DIRECTIONS
        return original_get_element_types(session)

    bot.get_element_types_for_session = get_element_types_for_session
    bot.got_group_or_add = got_group_or_add
    bot.got_element_type = got_element_type
    bot.got_problem = got_problem
    bot.got_element_status = got_element_status
    bot.build_report = build_report
