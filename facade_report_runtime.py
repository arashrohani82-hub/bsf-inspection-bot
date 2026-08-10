"""Facade report presentation grouped by physical location/zone."""

from __future__ import annotations

import copy
from collections import OrderedDict

import inspection_bot as bot

NO_ANOMALY = "Aucune anomalie visible"
OFFICE_UNCLASSIFIED = "À classer – import bureau"

ANOMALY_PHRASES = {
    "Bris de vitrage": "bris ou fissuration du vitrage",
    "Efflorescence / dépôts blanchâtres": "efflorescence ou dépôts blanchâtres",
    "Fissuration des joints de maçonnerie": "fissuration ou détérioration des joints de maçonnerie",
    "Déficience des joints d’étanchéité": "déficiences des joints d’étanchéité",
    "Béton fissuré ou éclaté": "béton fissuré ou éclaté",
    "Autre anomalie": "autres anomalies documentées",
}


def _is_facade(session: dict) -> bool:
    return bot.report_profiles.profile_key(session.get("inspection_type")) == "facade"


def _parse_group_label(label: str) -> tuple[str, str]:
    """Return (zone, anomaly) from facade group label."""
    parts = [part.strip() for part in str(label).split(" — ") if part.strip()]
    if not parts:
        return "Façade", ""
    if len(parts) == 2:
        # Façade nord — anomaly
        return parts[0], parts[1]
    # Façade nord — Hôtel — anomaly (custom sections work the same way)
    return " — ".join(parts[:-1]), parts[-1]


def _join_french(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} et {items[1]}"
    return ", ".join(items[:-1]) + f" et {items[-1]}"


def _zone_caption(zone: str, anomalies: list[str]) -> str:
    classified = [a for a in anomalies if a not in {NO_ANOMALY, OFFICE_UNCLASSIFIED}]
    phrases = [ANOMALY_PHRASES.get(a, a.lower()) for a in classified]

    if phrases:
        return (
            f"Anomalies observées dans la zone {zone}, incluant "
            f"{_join_french(phrases)}."
        )
    if OFFICE_UNCLASSIFIED in anomalies:
        return (
            f"Photographies documentant la zone {zone}; les observations "
            "doivent être classées avant l’émission finale du rapport."
        )
    return (
        f"Aucune anomalie apparente observée dans la zone {zone} "
        "sur les éléments documentés."
    )


def _group_by_zone(groups: list[dict]) -> list[dict]:
    zones: OrderedDict[str, dict] = OrderedDict()

    for group in groups:
        zone, anomaly = _parse_group_label(group.get("element_type", ""))
        entry = zones.setdefault(
            zone,
            {
                "element_type": zone,
                "caption_fr": "",
                "caption_en": "",
                "severity": "ok",
                "photos": [],
                "facade_anomalies": [],
            },
        )
        if anomaly and anomaly not in entry["facade_anomalies"]:
            entry["facade_anomalies"].append(anomaly)
        entry["photos"].extend(copy.deepcopy(group.get("photos", [])))
        if any("Acceptable" not in str(p.get("status", "")) for p in group.get("photos", [])):
            entry["severity"] = "minor"

    for zone, entry in zones.items():
        entry["caption_fr"] = _zone_caption(zone, entry["facade_anomalies"])
        entry["caption_en"] = entry["caption_fr"]

    return list(zones.values())


def install_facade_report_runtime() -> None:
    original_build_report = bot.build_report

    def build_report(session: dict, lang: str):
        if not _is_facade(session):
            return original_build_report(session, lang)
        prepared = copy.deepcopy(session)
        prepared["groups"] = _group_by_zone(prepared.get("groups", []))
        return original_build_report(prepared, lang)

    bot.build_report = build_report
