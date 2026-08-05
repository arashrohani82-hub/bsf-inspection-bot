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
from ai_runtime import install_ai_runtime
from certificate_fallback import install_certificate_fallback
from certificate_template_runtime import install_original_certificate_templates
from facade_workflow import install_facade_workflow
from hardened_runner import install_patches
from runtime_config import install_runtime_config


def install_inspection_type_compatibility() -> None:
    """Normalize legacy project JSON inspection-type records to display labels."""
    original_get_inspection_types = bot.get_inspection_types

    def normalized_inspection_types():
        normalized = []
        for item in original_get_inspection_types() or []:
            if isinstance(item, str):
                label = item.strip()
            elif isinstance(item, dict):
                label = ""
                for key in ("name", "label", "title", "type", "inspection_type"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        label = value.strip()
                        break
                if not label and len(item) == 1:
                    value = next(iter(item.values()))
                    if isinstance(value, str):
                        label = value.strip()
                if not label:
                    bot.log.warning("Ignoring invalid inspection type record: %r", item)
                    continue
            else:
                label = str(item).strip()

            if label and label not in normalized:
                normalized.append(label)
        return normalized

    bot.get_inspection_types = normalized_inspection_types


def main() -> None:
    install_runtime_config()
    install_inspection_type_compatibility()
    install_ai_runtime()
    install_certificate_fallback()
    install_original_certificate_templates()
    install_patches()
    # Install last so the facade-specific direction/anomaly flow wraps the
    # hardened generic handlers without changing parking or anchor inspections.
    install_facade_workflow()
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
            bot.STATE_CERTIFICATE_DECISION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    bot.got_certificate_decision,
                )
            ],
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
    app.add_handler(CommandHandler("done", bot.cmd_done))
    app.add_handler(CommandHandler("retry", bot.cmd_done))

    bot.log.info("🚀 BSF Inspection Bot running with hardening layer…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
