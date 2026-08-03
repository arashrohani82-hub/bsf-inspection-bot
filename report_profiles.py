"""Inspection-type profiles and deterministic French report language."""

from __future__ import annotations

from pathlib import Path


PROFILES = {
    "facade": {
        "label": "Façade – Inspection Loi 122",
        "aliases": ("façade", "facade", "enveloppe"),
        "template": "Template_Facade.docx",
        "certificate_template": None,
        "element_types": [
            ["Concrete / Masonry", "Sealant joint"],
            ["Window / Opening", "Metal component"],
            ["Roof edge", "Other"],
        ],
        "building": (
            "Le bâtiment visé est assujetti à une inspection de ses façades. "
            "La description détaillée de l’usage, du nombre d’étages et des "
            "principaux matériaux doit être confirmée à partir des documents "
            "disponibles et des observations effectuées sur place."
        ),
        "mandate": (
            "Le mandat consiste à inspecter visuellement les composantes "
            "accessibles des façades conformément aux exigences applicables de "
            "la Loi 122, à documenter les anomalies observées et à formuler les "
            "recommandations et priorités d’intervention appropriées."
        ),
        "ai_context": (
            "building facade and envelope inspection under Quebec Loi 122; "
            "evaluate visible concrete, masonry, sealants, openings, metal "
            "components and potential falling-object hazards"
        ),
    },
    "parking": {
        "label": "Stationnement – Inspection Loi 122",
        "aliases": ("stationnement", "parking"),
        "template": "Template_Parking.docx",
        "certificate_template": None,
        "element_types": [
            ["Slab", "Beam"],
            ["Column", "Wall"],
            ["Drain / Joint", "Other"],
        ],
        "building": (
            "Le stationnement visé comprend des éléments structuraux en béton "
            "armé, notamment des dalles, poutres, colonnes et murs. Le nombre de "
            "niveaux et les caractéristiques particulières doivent être "
            "confirmés à partir des plans et des observations sur place."
        ),
        "mandate": (
            "Le mandat consiste à réaliser l’inspection visuelle des éléments "
            "structuraux accessibles du stationnement conformément aux exigences "
            "applicables de la Loi 122, à relever les détériorations visibles et "
            "à établir les interventions et priorités recommandées."
        ),
        "ai_context": (
            "concrete parking structure inspection under Quebec Loi 122; "
            "evaluate slabs, beams, columns, walls, drains, joints, cracking, "
            "delamination, spalling, corrosion and water infiltration"
        ),
    },
    "anchor_annual": {
        "label": "Ancrage – Inspection annuelle visuelle",
        "aliases": ("ancrage 1 an", "annuelle", "annuel", "visual"),
        "template": "Template_Anchor_Annual.docx",
        "certificate_template": "Template_Certificate_Annual.docx",
        "element_types": [
            ["Anchor", "Davit"],
            ["Cable", "Base / Socket"],
            ["Roof", "Other"],
        ],
        "building": (
            "Le bâtiment est muni d’un système permanent d’accès suspendu en "
            "toiture comprenant, selon la configuration existante, des ancrages, "
            "des lignes de vie, des bossoirs et leurs bases ou socles."
        ),
        "mandate": (
            "Le mandat consiste à effectuer l’inspection visuelle annuelle des "
            "composantes accessibles du système d’accès suspendu. Aucun essai de "
            "charge ne fait partie de cette inspection annuelle, sauf indication "
            "expresse contraire au rapport."
        ),
        "ai_context": (
            "annual visual inspection of suspended access anchors, lifelines, "
            "davits and sockets under CSA Z271 and CSA Z91; do not infer that a "
            "load test was performed"
        ),
    },
    "anchor_5year": {
        "label": "Ancrage – Inspection quinquennale (5 ans)",
        "aliases": ("ancrage 5 ans", "quinquennale", "5 year", "5-year"),
        "template": "Template_Anchor_5Year.docx",
        "certificate_template": "Template_Certificate_5Year.docx",
        "element_types": [
            ["Anchor", "Davit"],
            ["Cable", "Base / Socket"],
            ["Roof", "Other"],
        ],
        "building": (
            "Le bâtiment est muni d’un système permanent d’accès suspendu en "
            "toiture comprenant, selon la configuration existante, des ancrages, "
            "des lignes de vie, des bossoirs et leurs bases ou socles."
        ),
        "mandate": (
            "Le mandat consiste à effectuer l’inspection quinquennale des "
            "composantes accessibles du système d’accès suspendu, incluant "
            "l’inspection visuelle et les essais applicables consignés dans le "
            "présent rapport."
        ),
        "ai_context": (
            "five-year inspection of suspended access anchors, lifelines, "
            "davits and sockets under CSA Z271, CSA Z91 and ASTM E3121; describe "
            "only visible conditions and recorded test evidence"
        ),
    },
}


def matched_profile_key(value: str | None) -> str | None:
    """Return a profile only when the inspection type is explicitly recognized."""
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    for key, profile in PROFILES.items():
        if normalized == key:
            return key
        if normalized == profile["label"].lower():
            return key
        if any(alias in normalized for alias in profile["aliases"]):
            return key
    return None


def profile_key(value: str | None) -> str:
    # Unknown legacy sessions must never become anchor inspections implicitly.
    # Facade is the conservative report-only fallback.
    return matched_profile_key(value) or "facade"


def profile(value: str | None) -> dict:
    return PROFILES[profile_key(value)]


def template_path(base_dir: Path, inspection_type: str | None) -> Path:
    name = profile(inspection_type)["template"]
    candidates = [
        base_dir / "templates" / name,
        Path(__file__).parent / "templates" / name,
        base_dir / "Template.docx",
        Path(__file__).parent / "Template.docx",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Report template not found: {name}")


def certificate_template_path(base_dir: Path, inspection_type: str | None) -> Path | None:
    name = profile(inspection_type).get("certificate_template")
    if not name:
        return None
    candidates = [
        base_dir / "templates" / name,
        Path(__file__).parent / "templates" / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Certificate template not found: {name}")


def is_anchor(inspection_type: str | None) -> bool:
    return matched_profile_key(inspection_type) in {
        "anchor_annual",
        "anchor_5year",
    }


def element_types(inspection_type: str | None) -> list[list[str]]:
    return profile(inspection_type)["element_types"]


def ai_context(inspection_type: str | None) -> str:
    return profile(inspection_type)["ai_context"]


def _issues(groups: list[dict]) -> list[str]:
    results = []
    for group in groups:
        statuses = {
            photo.get("status", "✅ Acceptable")
            for photo in group.get("photos", [])
        }
        if all("Acceptable" in status for status in statuses):
            continue
        caption = group.get("caption_fr") or group.get("element_type") or "Élément inspecté"
        status_text = ", ".join(sorted(statuses))
        results.append(f"{caption} ({status_text})")
    return results


def report_replacements(inspection_type: str | None, groups: list[dict]) -> dict[str, str]:
    selected = profile(inspection_type)
    issues = _issues(groups)
    inspected = sum(len(group.get("photos", [])) for group in groups)

    if issues:
        issue_text = "; ".join(issues)
        observations = (
            f"L’inspection a permis de documenter {inspected} condition(s) au "
            f"moyen de photographies. Les éléments suivants nécessitent une "
            f"intervention ou un suivi : {issue_text}. Les autres éléments "
            "accessibles documentés présentaient un état visuel généralement "
            "acceptable au moment de la visite."
        )
        risk = (
            "Les conditions non acceptables doivent être corrigées selon leur "
            "niveau de priorité. Les éléments identifiés comme rejetés, devant "
            "être remplacés ou ne pouvant être inspectés adéquatement doivent "
            "demeurer hors service ou être sécurisés jusqu’à la réalisation des "
            "correctifs et, lorsque requis, d’une nouvelle inspection."
        )
        conclusion = (
            "Sous réserve des limitations du mandat, les composantes accessibles "
            "ont été inspectées. Le maintien en service demeure conditionnel à "
            "l’exécution des interventions indiquées au rapport. Les éléments "
            "expressément exclus ou hors service ne sont pas couverts par une "
            "conclusion d’acceptabilité."
        )
    else:
        observations = (
            f"L’inspection a permis de documenter {inspected} condition(s) au "
            "moyen de photographies. Aucune anomalie apparente nécessitant une "
            "intervention immédiate n’a été relevée sur les éléments accessibles "
            "et inspectés au moment de la visite."
        )
        risk = (
            "Sur la base des observations effectuées, aucun indice apparent de "
            "défaillance ou de condition présentant un risque immédiat n’a été "
            "mis en évidence sur les éléments accessibles et inspectés."
        )
        conclusion = (
            "Sous réserve des limitations du mandat, les éléments accessibles et "
            "inspectés présentaient un état généralement acceptable au moment de "
            "la visite. Les inspections, l’entretien et l’utilisation conformes "
            "aux exigences applicables doivent être poursuivis."
        )

    return {
        "{{Building_Description}}": selected["building"],
        "{{Mandate}}": selected["mandate"],
        "{{Observations_Summary}}": observations,
        "{{Risk_Analysis}}": risk,
        "{{Conclusion}}": conclusion,
    }


def certificate_exclusions(groups: list[dict]) -> list[str]:
    return _issues(groups)

