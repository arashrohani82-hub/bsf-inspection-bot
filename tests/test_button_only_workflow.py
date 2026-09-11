import os
import sys
import types
import unittest


os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

if "anthropic" not in sys.modules:
    anthropic_stub = types.ModuleType("anthropic")
    anthropic_stub.Anthropic = lambda **kwargs: object()
    sys.modules["anthropic"] = anthropic_stub

import project_workflow_runtime as workflow


class ButtonOnlyWorkflowTests(unittest.TestCase):
    def test_every_project_checklist_question_has_button_options(self):
        for profile, questions in workflow.CHECKLISTS.items():
            with self.subTest(profile=profile):
                self.assertTrue(questions)
                for key, _label, _prompt, options in questions:
                    self.assertTrue(options, f"{profile}.{key} has no buttons")
                    self.assertTrue(
                        all(isinstance(row, list) and row for row in options),
                        f"{profile}.{key} has an invalid keyboard row",
                    )

    def test_photo_controls_include_finish_and_restart(self):
        flattened = {
            value
            for row in workflow.PHOTO_CONTROL_BUTTONS
            for value in row
        }
        self.assertIn("✅ Finish inspection", flattened)
        self.assertIn("🏠 New inspection", flattened)


if __name__ == "__main__":
    unittest.main()
