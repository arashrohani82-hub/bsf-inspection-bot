import unittest

import report_profiles


class ReportProfileTests(unittest.TestCase):
    def test_four_supported_types(self):
        cases = {
            "Façade – Inspection Loi 122": "facade",
            "Stationnement – Inspection Loi 122": "parking",
            "Ancrage – Inspection annuelle visuelle": "anchor_annual",
            "Ancrage – Inspection quinquennale (5 ans)": "anchor_5year",
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(report_profiles.profile_key(label), expected)

    def test_only_anchor_profiles_issue_certificates(self):
        self.assertFalse(report_profiles.is_anchor("Façade – Inspection Loi 122"))
        self.assertFalse(report_profiles.is_anchor("Stationnement – Inspection Loi 122"))
        self.assertTrue(report_profiles.is_anchor("Ancrage – Inspection annuelle visuelle"))
        self.assertTrue(report_profiles.is_anchor("Ancrage – Inspection quinquennale (5 ans)"))

    def test_nonacceptable_group_becomes_certificate_exclusion(self):
        groups = [
            {
                "element_type": "Base / Socket",
                "caption_fr": "Base no 3 inaccessible",
                "photos": [{"status": "🔧 Réparation requise"}],
            },
            {
                "element_type": "Anchor",
                "caption_fr": "Ancrages accessibles",
                "photos": [{"status": "✅ Acceptable"}],
            },
        ]
        self.assertEqual(
            report_profiles.certificate_exclusions(groups),
            ["Base no 3 inaccessible (🔧 Réparation requise)"],
        )


if __name__ == "__main__":
    unittest.main()
