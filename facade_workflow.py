"""Facade-specific Telegram workflow and deterministic report ordering."""

from __future__ import annotations

import copy

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

ANOMALY_ORDER = {
    name: index
    for index, row in enumerate(FACADE_ANOMALIES)
    for name in row
}


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


def _section_keyboard(sections: list[str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[section] for section in sections],
        one_time_keyboard=True,
        resize_keyboard=True,
    )


def _clean_sections(text: str) -> list[str]:
    raw_items = text.replace(";", ",").replace("\n", ",").split(",")
    sections: list[str] = []
    for item in raw_items:
        value = item.strip()
        if value and value not in sections:
            sections.append(value)
    return sections[:12]


def install_facade_workflow() -> None:
    original_got_project_select = bot.got_project_select
    original_got_group_or_add = bot.got_group_or_add
    original_got_element_type = bot.got_element_type
    original_got_element_id = bot.got_element_id
    original_got_problem = bot.got_problem
    original_got_element_status = bot.got_element_status
    original_build_report = bot.build_report

    async def got_project_select(update, ctx: ContextTypes.DEFAULT_TYPE):
        result = await original_got_project_select(update, ctx)
        session = bot.load_session(update.effective_chat.id)
        if not _is_facade_session(session) or result != bot.STATE_PHOTO:
            return result

        # The configuration belongs to this inspection session, not permanently
        # to the project, because the same project may be divided differently in
        # a future mandate.
        session.pop("facade_sections", None)
        bot.save_session(update.effective_chat.id, session)
        ctx.user_data["facade_stage"] = "configure_sections"
        await update.message.reply_text(
            "🏢 *Configuration du rapport de façade*\n\n"
            "Quelles sections du bâtiment doivent être distinguées dans ce rapport?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                SECTION_SETUP,
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
        return bot.STATE_ELEMENT_ID

    async def got_group_or_add(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        choice = update.message.text.strip()
        if _is_facade_session(session) and (
            "New element" in choice or choice.startswith("🆕")
        ):
            for key in (
                "facade_direction",
                "facade_section",
                "facade_anomaly",
                "add_to_group_idx",
            ):
                ctx.user_data.pop(key, None)
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

        sections = session.get("facade_sections") or ["Bâtiment"]
        if len(sections) == 1:
            ctx.user_data["facade_section"] = sections[0]
            await update.message.reply_text(
                f"🏢 {direction}\n\nQuel type d’anomalie est visible?",
                reply_markup=ReplyKeyboardMarkup(
                    FACADE_ANOMALIES,
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return bot.STATE_PROBLEM

        ctx.user_data["facade_stage"] = "select_section"
        await update.message.reply_text(
            f"🏢 {direction}\n\nDans quelle section du bâtiment?",
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
                    "Écrivez les sections séparées par des virgules.\n"
                    "Exemple : Hôtel, Résidentiel, Basilaire",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return bot.STATE_ELEMENT_ID
            else:
                await update.message.reply_text(
                    "Veuillez choisir une option de configuration.",
                    reply_markup=ReplyKeyboardMarkup(
                        SECTION_SETUP,
                        one_time_keyboard=True,
                        resize_keyboard=True,
                    ),
                )
                return bot.STATE_ELEMENT_ID

            session["facade_sections"] = sections
            bot.save_session(update.effective_chat.id, session)
            ctx.user_data.pop("facade_stage", None)
            await update.message.reply_text(
                "✅ Sections du rapport : " + ", ".join(sections) +
                "\n\n📸 Envoyez la première photo d’inspection.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return bot.STATE_PHOTO

        if stage == "custom_sections":
            sections = _clean_sections(choice)
            if not sections:
                await update.message.reply_text(
                    "Aucune section valide détectée. Exemple : Hôtel, Résidentiel"
                )
                return bot.STATE_ELEMENT_ID
            session["facade_sections"] = sections
            bot.save_session(update.effective_chat.id, session)
            ctx.user_data.pop("facade_stage", None)
            await update.message.reply_text(
                "✅ Sections du rapport : " + ", ".join(sections) +
                "\n\n📸 Envoyez la première photo d’inspection.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return bot.STATE_PHOTO

        if stage == "select_section":
            sections = session.get("facade_sections") or ["Bâtiment"]
            if choice not in sections:
                await update.message.reply_text(
                    "Veuillez sélectionner une section du bâtiment.",
                    reply_markup=_section_keyboard(sections),
                )
                return bot.STATE_ELEMENT_ID
            ctx.user_data["facade_section"] = choice
            ctx.user_data.pop("facade_stage", None)
            direction = ctx.user_data.get("facade_direction", "Façade")
            await update.message.reply_text(
                f"🏢 {direction} — {choice}\n\nQuel type d’anomalie est visible?",
                reply_markup=ReplyKeyboardMarkup(
                    FACADE_ANOMALIES,
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return bot.STATE_PROBLEM

        return await original_got_element_id(update, ctx)

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
        section = ctx.user_data.get("facade_section", "Bâtiment")
        if section == "Bâtiment":
            group_label = f"{direction} — {anomaly}"
            location = direction
        else:
            group_label = f"{direction} — {section} — {anomaly}"
            location = f"{direction} — {section}"

        ctx.user_data["facade_anomaly"] = anomaly
        ctx.user_data["element_type"] = group_label
        ctx.user_data["location"] = location
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
        sections = ordered.get("facade_sections") or ["Bâtiment"]
        section_order = {name: index for index, name in enumerate(sections)}

        def sort_key(group: dict):
            parts = [part.strip() for part in group.get("element_type", "").split(" — ")]
            direction = parts[0] if parts else ""
            if len(parts) >= 3:
                section, anomaly = parts[1], parts[2]
            else:
                section, anomaly = "Bâtiment", parts[1] if len(parts) > 1 else ""
            return (
                DIRECTION_ORDER.get(direction, 99),
                section_order.get(section, 99),
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
    bot.got_project_select = got_project_select
    bot.got_group_or_add = got_group_or_add
    bot.got_element_type = got_element_type
    bot.got_element_id = got_element_id
    bot.got_problem = got_problem
    bot.got_element_status = got_element_status
    bot.build_report = build_report
