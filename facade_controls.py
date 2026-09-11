"""Photo-state controls for facade field/office modes."""

from telegram import ReplyKeyboardMarkup
from telegram.ext import ContextTypes

import inspection_bot as bot

FACADE_DIRECTIONS = [
    ["Façade nord", "Façade sud"],
    ["Façade est", "Façade ouest"],
]

GENERIC_PHOTO_CONTROLS = [
    ["🗑 Remove last photo", "✅ Finish inspection"],
    ["🏠 New inspection"],
]


def install_facade_controls() -> None:
    async def _ask_zone(update, ctx):
        ctx.user_data["facade_stage"] = "select_direction"
        await update.message.reply_text(
            "📍 Sélectionnez la nouvelle façade active :",
            reply_markup=ReplyKeyboardMarkup(
                FACADE_DIRECTIONS,
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
        return bot.STATE_ELEMENT_TYPE

    async def got_photo_control(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        text = update.message.text.strip()
        if text == "🏠 New inspection":
            return await bot.cmd_start(update, ctx)
        if text == "🗑 Remove last photo":
            await bot.cmd_remove_last(update, ctx)
            await update.message.reply_text(
                "📸 Send the next photo, or use the buttons below.",
                reply_markup=ReplyKeyboardMarkup(
                    GENERIC_PHOTO_CONTROLS,
                    resize_keyboard=True,
                    is_persistent=True,
                ),
            )
            return bot.STATE_PHOTO
        if text == "✅ Finish inspection":
            return await bot.cmd_done(update, ctx)

        if bot.report_profiles.profile_key(session.get("inspection_type")) != "facade":
            await update.message.reply_text(
                "📸 Send a photo, or use one of the buttons below.",
                reply_markup=ReplyKeyboardMarkup(
                    GENERIC_PHOTO_CONTROLS,
                    resize_keyboard=True,
                    is_persistent=True,
                ),
            )
            return bot.STATE_PHOTO

        if text == "📍 Change zone":
            return await _ask_zone(update, ctx)

        await update.message.reply_text(
            "📸 Envoyez une photo, utilisez 📍 Change zone, ou ✅ Finish inspection."
        )
        return bot.STATE_PHOTO

    async def cmd_zone(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if bot.report_profiles.profile_key(session.get("inspection_type")) != "facade":
            await update.message.reply_text("/zone est disponible pendant une inspection de façade.")
            return bot.STATE_PHOTO
        return await _ask_zone(update, ctx)

    bot.got_photo_control = got_photo_control
    bot.cmd_zone = cmd_zone
