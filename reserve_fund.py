"""Explicit reserve-fund inputs and deterministic annual cash-flow projections.

Rates are fractions, costs are base-year CAD including the stated cost basis.
Contributions occur at the start of each year; works are paid next; positive
remaining cash earns interest at year end. No interest is earned on deficits.
Routine maintenance is excluded from the reserve-fund expenditure schedule.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_CEILING


def number(value):
    if isinstance(value, bool):
        raise ValueError("Valeur numérique requise")
    try:
        result = Decimal(str(value).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Nombre exact requis, sans intervalle ni unité") from exc
    if not result.is_finite():
        raise ValueError("Nombre fini requis")
    return result


def money(value):
    return number(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate(data):
    """Reject incomplete estimates instead of silently replacing them with zeros."""
    if not isinstance(data, dict):
        raise ValueError("Données financières manquantes")
    for key in ("base_year", "years", "opening_balance", "annual_contribution", "inflation", "interest", "growth"):
        if data.get(key) is None:
            raise ValueError(f"Paramètre manquant : {key}")
        number(data[key])
    for key, low, high in (("base_year", 2000, 2200), ("years", 25, 100)):
        value = number(data[key])
        if value != int(value) or not low <= value <= high:
            raise ValueError(f"{key} : entier entre {low} et {high} requis")
    for key in ("opening_balance", "annual_contribution"):
        if number(data[key]) < 0:
            raise ValueError(f"{key} doit être positif ou nul")
    for key in ("inflation", "interest", "growth"):
        if not 0 <= number(data[key]) <= Decimal("0.25"):
            raise ValueError(f"{key} : taux entre 0 et 25 % requis")
    if not str(data.get("cost_basis", "")).strip():
        raise ValueError("Préciser les taxes, honoraires et contingences inclus dans les coûts")
    if not str(data.get("balance_date", "")).strip():
        raise ValueError("Date du solde initial requise")
    return data


def events(data, groups):
    validate(data)
    start, end = int(data["base_year"]), int(data["base_year"]) + int(data["years"])
    output = []
    if not groups:
        raise ValueError("Inventaire des composantes manquant")
    for index, group in enumerate(groups, 1):
        plan = group.get("reserve_plan", {})
        if plan.get("included") is False:
            if not plan.get("exclusion_reason"):
                raise ValueError(f"Composante {index} : motif d’exclusion requis")
            continue
        for field in ("year", "cost", "cycle", "action", "cost_source", "restricted"):
            if plan.get(field) is None or plan.get(field) == "":
                raise ValueError(f"Composante {index} : {field} à compléter")
        year, cycle = number(plan["year"]), number(plan["cycle"])
        if year != int(year) or cycle != int(cycle) or year < start or cycle < 0:
            raise ValueError(f"Composante {index} : année ou récurrence invalide")
        if not isinstance(plan["restricted"], bool):
            raise ValueError(f"Composante {index} : usage restreint à confirmer")
        if number(plan["cost"]) < 0:
            raise ValueError(f"Composante {index} : coût négatif")
        year, cycle = int(year), int(cycle)
        while year < end:
            cost = money(number(plan["cost"]) * (1 + number(data["inflation"])) ** (year - start))
            output.append({"id": index, "year": year, "cost": cost, "action": plan["action"],
                           "restricted": plan["restricted"], "component": group.get("element_type", "Composante")})
            if cycle == 0:
                break
            year += cycle
    return sorted(output, key=lambda e: (e["year"], e["id"]))


def project(data, groups, contribution=None):
    schedule = events(data, groups)
    balance = money(data["opening_balance"])
    annual = number(data["annual_contribution"] if contribution is None else contribution)
    rows = []
    for offset in range(int(data["years"])):
        year = int(data["base_year"]) + offset
        payment = money(annual * (1 + number(data["growth"])) ** offset)
        expense = sum((e["cost"] for e in schedule if e["year"] == year), Decimal(0))
        restricted = sum((e["cost"] for e in schedule if e["year"] == year and e["restricted"]), Decimal(0))
        cash = balance + payment - expense
        interest = money(max(cash, Decimal(0)) * number(data["interest"]))
        closing = cash + interest
        rows.append({"year": year, "opening": balance, "contribution": payment,
                     "expense": expense, "restricted": restricted, "interest": interest, "closing": closing})
        balance = closing
    return rows


def recommended_contribution(data, groups):
    """Minimum initial annual contribution keeping every year nonnegative.

    This is a mathematical cash-flow floor, not a professional recommendation
    or a contingency allowance. Bisection is performed to the next CAD cent.
    """
    if min(r["closing"] for r in project(data, groups, 0)) >= 0:
        return Decimal(0)
    low, high = 0, 100
    while min(r["closing"] for r in project(data, groups, Decimal(high) / 100)) < 0:
        high *= 2
    while low + 1 < high:
        mid = (low + high) // 2
        if min(r["closing"] for r in project(data, groups, Decimal(mid) / 100)) >= 0:
            high = mid
        else:
            low = mid
    return Decimal(high) / 100


def required_openings(rows, interest):
    """Backward reserve target for the given future contributions and expenses."""
    target = Decimal(0)
    output = []
    for row in reversed(rows):
        target = max(Decimal(0), row["expense"] - row["contribution"] + target / (1 + number(interest)))
        target = target.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        output.append(target)
    return list(reversed(output))
