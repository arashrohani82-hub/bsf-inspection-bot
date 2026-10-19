import unittest
from decimal import Decimal
from reserve_fund import project, events, recommended_contribution, required_openings


def data(**kw):
    return dict(base_year=2026, years=25, opening_balance=0, annual_contribution=100,
                balance_date="2026-01-01", cost_basis="Coûts totaux taxes incluses",
                inflation=0, interest=0, growth=0, **kw)


def component(**kw):
    return {"element_type": "Toiture", "reserve_plan": dict(year=2026, cost=1000,
            cycle=0, action="Remplacement", restricted=False, cost_source="Devis test", **kw)}


class ReserveFundTests(unittest.TestCase):
    def test_hand_calculated_year_and_deficit_no_interest(self):
        d = data()
        d.update(opening_balance=1000, annual_contribution=100, inflation="0.10", interest="0.05")
        g = component()
        rows = project(d, [g])
        self.assertEqual(rows[0]["closing"], Decimal("105.00"))
        d["opening_balance"] = 0
        rows = project(d, [g])
        self.assertEqual(rows[0]["closing"], Decimal("-900.00"))
        self.assertEqual(rows[0]["interest"], 0)

    def test_inclusive_25_year_horizon_and_recurrence(self):
        d, g = data(), component()
        d["inflation"] = ".10"
        g["reserve_plan"].update(year=2027, cycle=12)
        schedule = events(d, [g])
        self.assertEqual([e["year"] for e in schedule], [2027, 2039])
        self.assertEqual(schedule[0]["cost"], Decimal("1100.00"))
        self.assertEqual(len(project(d, [g])), 25)
        self.assertEqual(project(d, [g])[-1]["year"], 2050)

    def test_solver_matches_known_immediate_cash_need(self):
        d, g = data(), component()
        self.assertEqual(recommended_contribution(d, [g]), Decimal("1000.00"))
        d["opening_balance"] = 500
        self.assertEqual(recommended_contribution(d, [g]), Decimal("500.00"))
        d["opening_balance"] = 2000
        self.assertEqual(recommended_contribution(d, [g]), 0)

    def test_required_opening_reserve_known_backward_case(self):
        rows = [{"expense": Decimal(1000), "contribution": Decimal(100)},
                {"expense": Decimal(1000), "contribution": Decimal(100)}]
        self.assertEqual(required_openings(rows, 0), [Decimal(1800), Decimal(900)])

    def test_missing_cost_and_approximate_balance_are_rejected(self):
        d, g = data(), component()
        g["reserve_plan"]["cost"] = None
        with self.assertRaises(ValueError):
            project(d, [g])
        d["opening_balance"] = "25–100 k$"
        with self.assertRaises(ValueError):
            project(d, [component()])

    def test_restricted_cost_tracked_and_current_maintenance_not_included(self):
        d, g = data(), component()
        g["reserve_plan"].update(restricted=True, maintenance="Inspection annuelle", maintenance_cost=500)
        rows = project(d, [g])
        self.assertEqual(rows[0]["restricted"], Decimal(1000))
        self.assertEqual(rows[0]["expense"], Decimal(1000))


if __name__ == "__main__":
    unittest.main()
