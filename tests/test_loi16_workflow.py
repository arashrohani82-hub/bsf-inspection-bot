import os
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import inspection_bot as bot
from loi16_workflow import install_loi16_workflow, BUTTON, BACK


class Loi16WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_values_persist_and_other_services_delegate(self):
        session = {"company": "metra", "inspection_type": "loi16", "project_id": "p1", "groups": []}
        database = {"projects": [{"id": "p1"}]}
        original = AsyncMock(return_value=bot.STATE_PHOTO)
        patches = [patch.object(bot, name, original, create=True) for name in
                   ("got_project_select", "got_photo_control", "got_group_caption_fr", "got_photo")]
        patches += [patch.object(bot, "load_session", side_effect=lambda _: deepcopy(session)),
                    patch.object(bot, "save_session", side_effect=lambda _, value: session.update(deepcopy(value))),
                    patch.object(bot, "load_db", return_value=database), patch.object(bot, "save_db")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        install_loi16_workflow()
        message = SimpleNamespace(text=BUTTON, reply_text=AsyncMock())
        update = SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=1))
        ctx = SimpleNamespace(user_data={})
        await bot.got_photo_control(update, ctx)
        message.text = "💰 Hypothèses financières"
        await bot.got_photo_control(update, ctx)
        for text in ("2026", "25", "2026-01-01", "40000", "8000", "2,5", "2", "2,5", "Taxes incluses"):
            message.text = text
            await bot.got_photo_control(update, ctx)
        self.assertEqual(session["reserve_fund"]["inflation"], "0.025")
        self.assertEqual(database["projects"][0]["reserve_fund"]["opening_balance"], "40000")
        message.text = BACK
        await bot.got_photo_control(update, ctx)
        self.assertNotIn("loi16_editor", ctx.user_data)
        session["inspection_type"] = "parking"
        message.text = BUTTON
        await bot.got_photo_control(update, ctx)
        original.assert_awaited_once()

    async def test_invalid_amount_does_not_advance_or_change_saved_value(self):
        session = {"company": "metra", "inspection_type": "loi16", "project_id": "p1",
                   "reserve_fund": {"opening_balance": "12500"}, "groups": []}
        names = ("got_project_select", "got_photo_control", "got_group_caption_fr", "got_photo")
        patches = [patch.object(bot, name, AsyncMock(), create=True) for name in names]
        patches += [patch.object(bot, "load_session", return_value=session), patch.object(bot, "save_session")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        install_loi16_workflow()
        ctx = SimpleNamespace(user_data={"loi16_editor": {"project_id": "p1", "stage": "finance", "index": 3}})
        update = SimpleNamespace(effective_chat=SimpleNamespace(id=1),
            message=SimpleNamespace(text="25–100 k$", reply_text=AsyncMock()))
        await bot.got_photo_control(update, ctx)
        self.assertEqual(ctx.user_data["loi16_editor"]["index"], 3)
        self.assertEqual(session["reserve_fund"]["opening_balance"], "12500")
