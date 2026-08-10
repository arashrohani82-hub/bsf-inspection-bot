"""Photo-state controls for facade field/office modes."""

from telegram import ReplyKeyboardMarkup
from telegram.ext import ContextTypes

import inspection_bot as bot

FACADE_DIRECTIONS = [
    ["Façade nord", "Façade sud"],
    ["Façade est", "Façade ouest"],
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
        if bot.report_profiles.profile_key(session.get("inspection_type")) != "facade":
            await update.message.reply_text("📸 Envoyez une photo ou utilisez /done.")
            return bot.STATE_PHOTO

        text = update.message.text.strip()
        if text == "📍 Change zone":
            return await _ask_zone(update, ctx)
        if text == "✅ Finish inspection":
            return await bot.cmd_done(update, ctx)

        await update.message.reply_text(
            "📸 Envoyez une photo, utilisez 📍 Change zone, ou /done pour terminer."
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
