"""Application entrypoint with global recovery commands."""

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import inspection_bot as bot
from hardened_runner import install_patches
from runtime_config import install_runtime_config


def main() -> None:
    install_runtime_config()
    install_patches()
    app = Application.builder().token(bot.TELEGRAM_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", bot.cmd_start)],
        states={
            bot.STATE_MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_main_menu)],
            bot.STATE_ADMIN_PROJECT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.admin_got_name)],
            bot.STATE_ADMIN_PROJECT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.admin_got_address)],
            bot.STATE_ADMIN_PROJECT_PLANS: [
                MessageHandler(filters.PHOTO, bot.admin_got_plan),
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.admin_skip_plans),
            ],
            bot.STATE_ADMIN_PROJECT_DAVIT: [
                MessageHandler(filters.PHOTO, bot.admin_got_davit),
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.admin_skip_davit),
            ],
            bot.STATE_INSPECTION_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_inspection_type)],
            bot.STATE_PROJECT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_project_select)],
            bot.STATE_PHOTO: [
                MessageHandler(filters.PHOTO, bot.got_photo),
                CommandHandler("done", bot.cmd_done),
            ],
            bot.STATE_GROUP_OR_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_group_or_add)],
            bot.STATE_ELEMENT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_element_type)],
            bot.STATE_ELEMENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_element_id)],
            bot.STATE_ELEMENT_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_element_status)],
            bot.STATE_PROBLEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_problem)],
            bot.STATE_GROUP_CAPTION_FR: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.got_group_caption_fr)],
        },
        fallbacks=[
            CommandHandler("cancel", bot.cmd_cancel),
            CommandHandler("done", bot.cmd_done),
            CommandHandler("retry", bot.cmd_done),
            CommandHandler("remove", bot.cmd_remove_last),
        ],
        allow_reentry=True,
    )

    app.add_handler(conversation)
    app.add_handler(CommandHandler("projects", bot.cmd_projects))
    app.add_handler(CommandHandler("status", bot.cmd_status))
    app.add_handler(CommandHandler("remove", bot.cmd_remove_last))
    # These global handlers make report retry possible even after a restart or
    # after the ConversationHandler has ended.
    app.add_handler(CommandHandler("done", bot.cmd_done))
    app.add_handler(CommandHandler("retry", bot.cmd_done))

    bot.log.info("🚀 BSF Inspection Bot running with hardening layer…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
