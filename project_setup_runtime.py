"""Simplify generic project creation to name and address only.

Floor plans and davit details are inspection-specific documents and must not be
requested for every project. They can be collected later by the workflow that
actually needs them.
"""

from telegram.ext import ContextTypes

import inspection_bot as bot


def install_simple_project_setup() -> None:
    async def admin_got_address(update, ctx: ContextTypes.DEFAULT_TYPE):
        project = ctx.user_data.get("new_project")
        if not isinstance(project, dict):
            await update.message.reply_text(
                "⚠️ Project setup expired. Please start again with /start."
            )
            return bot.STATE_MAIN_MENU

        project["address"] = update.message.text.strip()
        project.setdefault("plans", [])
        project.setdefault("davit_detail", None)
        return await bot.admin_save_project(update, ctx)

    bot.admin_got_address = admin_got_address
