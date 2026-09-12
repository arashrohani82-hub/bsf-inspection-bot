"""Company routing and inspection-specific project-definition checklists."""

from __future__ import annotations

from datetime import datetime, timezone

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

import inspection_bot as bot


COMPANY_BUTTONS = [["🔷 Metra Consultation"], ["🟠 BSF Inspections"]]
METRA_SERVICES = [
    ["🏢 Loi 122"],
    ["📘 Loi 16"],
    ["🔩 Inspection des ancrages"],
]
LOI122_TYPES = [["Façades – Loi 122"], ["Stationnement – Loi 122"]]
ANCHOR_TYPES = [["Ancrages – Inspection annuelle"], ["Ancrages – Inspection 5 ans"]]
ACTION_BUTTONS = [["📁 Define new project"], ["📝 Write a report"]]
PHOTO_CONTROL_BUTTONS = [["🗑 Remove last photo", "✅ Finish inspection"], ["🏠 New inspection"]]
YES_NO_UNKNOWN = [["✅ Oui", "❌ Non"], ["❓ Inconnu", "⏭ Passer"]]
SKIP = [["⏭ Passer"]]

CLIENT_OPTIONS = [["🏢 Syndicat", "🏠 Propriétaire"], ["🧑‍💼 Gestionnaire", "❓ À confirmer"]]
CONTACT_OPTIONS = [["🧑‍💼 Gestionnaire", "👤 Administrateur"], ["🛠 Surintendant", "❓ À confirmer"]]
YEAR_OPTIONS = [["Avant 1980", "1980–1999"], ["2000–2009", "2010–2019"], ["2020 ou après", "❓ Inconnu"]]
STOREY_OPTIONS = [["1–3 étages", "4–6 étages"], ["7–12 étages", "13 étages ou plus"], ["❓ Inconnu"]]
DOCUMENT_OPTIONS = [["📐 Plans", "📄 Rapports antérieurs"], ["📚 Plans + rapports", "🚫 Aucun document"], ["❓ À confirmer"]]


COMMON_QUESTIONS = [
    ("client", "Client / syndicat", "Quel est le type de client?", CLIENT_OPTIONS),
    ("contact", "Personne-ressource", "Quel est le rôle de la personne-ressource?", CONTACT_OPTIONS),
    ("building_use", "Usage", "Usage principal du bâtiment?", [["Résidentiel", "Commercial"], ["Mixte", "⏭ Passer"]]),
    ("construction_year", "Année de construction", "Période de construction approximative?", YEAR_OPTIONS),
    ("storeys", "Étages", "Nombre d’étages hors sol?", STOREY_OPTIONS),
    ("documents", "Documents disponibles", "Quels documents principaux sont disponibles?", DOCUMENT_OPTIONS),
]

CHECKLISTS = {
    "facade": COMMON_QUESTIONS + [
        ("facade_materials", "Revêtements", "Principaux matériaux des façades?", [["🧱 Maçonnerie", "🏗 Béton"], ["🪟 Mur-rideau", "🏢 Revêtement léger"], ["🔀 Système mixte", "❓ Inconnu"]]),
        ("last_detailed_inspection", "Inspection antérieure", "Quand a eu lieu la dernière inspection détaillée?", [["Moins de 1 an", "1–3 ans"], ["3–5 ans", "Plus de 5 ans"], ["🚫 Aucune", "❓ Inconnu"]]),
        ("repairs_since", "Travaux antérieurs", "Réparations depuis la dernière inspection?", [["🚫 Aucune", "🔧 Localisées"], ["🏗 Majeures", "⏳ En cours"], ["❓ Inconnu"]]),
        ("known_conditions", "Anomalies connues", "Quelle anomalie est déjà signalée?", [["✅ Aucune connue", "🧱 Fissuration"], ["💧 Infiltration", "⚠️ Chute de matériau"], ["🔀 Plusieurs anomalies", "❓ Inconnu"]]),
        ("dangerous_condition", "Condition dangereuse", "Une condition dangereuse est-elle présentement connue?", YES_NO_UNKNOWN),
        ("access_method", "Méthode d’accès", "Quelle méthode d’accès est prévue?", [["🚶 Depuis le sol", "🏠 Depuis la toiture"], ["🚜 Nacelle", "🪢 Plateforme suspendue"], ["🚁 Drone", "🔍 Ouvertures exploratoires"]]),
        ("public_exposure", "Exposition du public", "Niveau d’exposition au pied des façades?", [["🟢 Faible", "🟡 Moyenne"], ["🔴 Élevée", "❓ À confirmer"]]),
        ("inspection_scope", "Portée", "Quelle est la portée principale?", [["📋 Inspection quinquennale", "🔧 Suivi de travaux"], ["🚨 Vérification urgente", "❓ À confirmer"]]),
    ],
    "parking": COMMON_QUESTIONS + [
        ("parking_levels", "Niveaux", "Nombre de niveaux de stationnement?", [["1 niveau", "2 niveaux"], ["3–5 niveaux", "6 niveaux ou plus"], ["❓ Inconnu"]]),
        ("structural_system", "Système structural", "Quel est le système structural principal?", [["🏗 Béton coulé", "🧩 Béton préfabriqué"], ["↔️ Dalle post-tendue", "🔩 Acier"], ["🔀 Mixte", "❓ Inconnu"]]),
        ("environment", "Exposition", "Type d’exposition du stationnement?", [["🏠 Intérieur", "☀️ Extérieur"], ["🔀 Partiellement exposé", "❓ Inconnu"]]),
        ("last_detailed_inspection", "Inspection antérieure", "Quand a eu lieu la dernière vérification approfondie?", [["Moins de 1 an", "1–3 ans"], ["3–5 ans", "Plus de 5 ans"], ["🚫 Aucune", "❓ Inconnu"]]),
        ("annual_sheets", "Fiches annuelles", "Les fiches de vérification annuelle sont-elles disponibles?", YES_NO_UNKNOWN),
        ("known_conditions", "Anomalies connues", "Quelle condition est déjà connue?", [["✅ Aucune", "〰️ Fissuration"], ["🧱 Délamination / éclatement", "🧲 Corrosion"], ["💧 Infiltration / drainage", "🔀 Plusieurs"]]),
        ("temporary_measures", "Mesures temporaires", "Présence d’étaiement, fermeture ou mesure de sécurité temporaire?", YES_NO_UNKNOWN),
        ("repairs_since", "Travaux antérieurs", "Réparations depuis la dernière inspection?", [["🚫 Aucune", "🔧 Localisées"], ["🏗 Majeures", "⏳ En cours"], ["❓ Inconnu"]]),
    ],
    "anchor_annual": COMMON_QUESTIONS + [
        ("system_types", "Systèmes", "Quel système principal est présent?", [["⚓ Ancrages", "➖ Lignes de vie"], ["🏗 Bossoirs / socles", "🛤 Rails"], ["🔀 Système mixte", "❓ Inconnu"]]),
        ("component_count", "Quantité", "Nombre approximatif de composantes?", [["1–10", "11–25"], ["26–50", "51–100"], ["Plus de 100", "❓ Inconnu"]]),
        ("roof_access", "Accès toiture", "Quel est l’accès principal à la toiture?", [["🚪 Escalier intérieur", "🪜 Échelle fixe"], ["🔐 Trappe verrouillée", "🚜 Nacelle requise"], ["❓ À confirmer"]]),
        ("layout_available", "Plan de localisation", "Un plan numéroté des équipements est-il disponible?", YES_NO_UNKNOWN),
        ("manufacturer", "Fabricant", "Information du fabricant disponible?", [["✅ Plaque lisible", "📄 Dans les plans"], ["❌ Non disponible", "❓ À confirmer"]]),
        ("last_inspection", "Inspection antérieure", "Quand a eu lieu la dernière inspection?", [["Moins de 1 an", "1–3 ans"], ["3–5 ans", "Plus de 5 ans"], ["🚫 Aucune", "❓ Inconnu"]]),
        ("known_repairs", "Réparations", "État connu des équipements?", [["✅ Aucun problème", "🔧 Réparations connues"], ["⛔ Hors service", "🔀 Modifications"], ["❓ Inconnu"]]),
    ],
    "anchor_5year": COMMON_QUESTIONS + [
        ("system_types", "Systèmes", "Quel système principal est présent?", [["⚓ Ancrages", "➖ Lignes de vie"], ["🏗 Bossoirs / socles", "🛤 Rails"], ["🔀 Système mixte", "❓ Inconnu"]]),
        ("component_count", "Quantité", "Nombre approximatif de composantes?", [["1–10", "11–25"], ["26–50", "51–100"], ["Plus de 100", "❓ Inconnu"]]),
        ("roof_access", "Accès toiture", "Quel est l’accès principal à la toiture?", [["🚪 Escalier intérieur", "🪜 Échelle fixe"], ["🔐 Trappe verrouillée", "🚜 Nacelle requise"], ["❓ À confirmer"]]),
        ("layout_available", "Plan de localisation", "Un plan numéroté des équipements est-il disponible?", YES_NO_UNKNOWN),
        ("manufacturer", "Fabricant", "Information du fabricant disponible?", [["✅ Plaque lisible", "📄 Dans les plans"], ["❌ Non disponible", "❓ À confirmer"]]),
        ("previous_tests", "Essais antérieurs", "Rapports d’essais de traction/charge et valeurs obtenues disponibles?", YES_NO_UNKNOWN),
        ("test_method", "Méthode d’essai", "Quelle méthode d’essai est prévue?", [["↔️ Traction", "⬇️ Charge verticale"], ["🔀 Méthode combinée", "📄 Selon rapport antérieur"], ["❓ À confirmer"]]),
        ("known_repairs", "Réparations", "État connu des équipements?", [["✅ Aucun problème", "🔧 Réparations connues"], ["⛔ Hors service", "🔀 Modifications"], ["❓ Inconnu"]]),
    ],
    "loi16": COMMON_QUESTIONS + [
        ("divided_coownership", "Copropriété divise", "Confirmer qu’il s’agit d’une copropriété divise.", YES_NO_UNKNOWN),
        ("units", "Unités", "Nombre d’unités privatives?", [["1–8", "9–20"], ["21–50", "51–100"], ["Plus de 100", "❓ Inconnu"]]),
        ("buildings", "Bâtiments", "Nombre de bâtiments couverts?", [["1 bâtiment", "2 bâtiments"], ["3–5 bâtiments", "Plus de 5"], ["❓ Inconnu"]]),
        ("declaration", "Déclaration de copropriété", "La déclaration de copropriété et ses modifications sont-elles disponibles?", YES_NO_UNKNOWN),
        ("common_parts", "Parties communes", "Y a-t-il des parties communes à usage restreint?", YES_NO_UNKNOWN),
        ("roof", "Toiture", "État apparent / âge connu de la toiture?", [["🟢 Récente / bon état", "🟡 Mi-vie utile"], ["🔴 Fin de vie / déficiente", "❓ Inconnu"]]),
        ("envelope", "Enveloppe", "État apparent de l’enveloppe?", [["🟢 Bon", "🟡 Moyen"], ["🔴 Déficient", "🔀 Variable"], ["❓ Inconnu"]]),
        ("parking_elevator", "Équipements majeurs", "Quels équipements majeurs sont présents?", [["🅿️ Stationnement", "🛗 Ascenseur"], ["🅿️ + 🛗 Les deux", "🚫 Aucun"], ["❓ Inconnu"]]),
        ("mechanical", "Mécanique", "Type principal de systèmes communs?", [["🔥 Chauffage central", "❄️ CVCA central"], ["🚰 Plomberie commune", "🔀 Plusieurs systèmes"], ["🏠 Systèmes individuels", "❓ Inconnu"]]),
        ("major_repairs", "Travaux majeurs", "Situation des travaux majeurs?", [["✅ Aucun connu", "🔧 Réalisés récemment"], ["📅 Prévus", "⏳ En cours"], ["❓ Inconnu"]]),
        ("claims", "Sinistres", "Sinistres ou réclamations importants connus?", [["✅ Aucun", "💧 Infiltration"], ["🔥 Incendie", "🏗 Structure"], ["🔀 Plusieurs", "❓ Inconnu"]]),
        ("reserve_balance", "Solde du fonds", "Ordre de grandeur du fonds de prévoyance?", [["Moins de 25 k$", "25–100 k$"], ["100–500 k$", "Plus de 500 k$"], ["❓ Inconnu"]]),
        ("annual_contribution", "Contribution annuelle", "Ordre de grandeur de la contribution annuelle?", [["Moins de 10 k$", "10–25 k$"], ["25–100 k$", "Plus de 100 k$"], ["❓ Inconnu"]]),
        ("financial_records", "Données financières", "États financiers, budgets et placements du fonds disponibles?", YES_NO_UNKNOWN),
        ("previous_study", "Étude antérieure", "Carnet d’entretien ou étude du fonds antérieur disponible?", YES_NO_UNKNOWN),
        ("study_base_year", "Année de référence", "Quelle année monétaire doit servir de référence aux coûts?", [["Année courante", "Année précédente"], ["Selon étude antérieure", "❓ À confirmer"]]),
        ("planning_horizon", "Horizon de planification", "Quel horizon doit être présenté dans l’étude?", [["25 ans", "30 ans"], ["Plus de 30 ans", "❓ À confirmer"]]),
        ("interest_rate", "Rendement du fonds", "Quel taux de rendement annuel doit être analysé?", [["0 %", "1 %"], ["2 %", "3 %"], ["Scénarios multiples", "❓ À confirmer"]]),
        ("inflation_rate", "Inflation des travaux", "Quel taux annuel d’inflation des travaux doit être analysé?", [["2 %", "2,5 %"], ["3 %", "4 %"], ["Scénarios multiples", "❓ À confirmer"]]),
        ("contribution_growth", "Indexation des cotisations", "Quelle hausse annuelle des cotisations doit être évaluée?", [["0 %", "2,5 %"], ["5 %", "Hausse graduelle sur 5 ans"], ["Hausse graduelle sur 10 ans", "Scénarios multiples"], ["❓ À confirmer"]]),
        ("opening_balance_date", "Date du solde initial", "À quelle date correspond le solde initial du fonds?", [["Début d’exercice", "Fin d’exercice"], ["Date des états financiers", "❓ À confirmer"]]),
        ("special_assessments", "Cotisations spéciales", "Des cotisations spéciales sont-elles prévues ou en cours?", YES_NO_UNKNOWN),
        ("planned_expenses", "Dépenses planifiées", "Des dépenses majeures sont-elles déjà budgétées?", YES_NO_UNKNOWN),
        ("cost_basis", "Base des coûts", "Que doivent inclure les coûts de planification?", [["Travaux seulement", "Travaux + taxes"], ["Travaux + honoraires"], ["Travaux + taxes + honoraires + contingence"], ["❓ À confirmer"]]),
        ("scenario_count", "Scénarios financiers", "Combien de scénarios de financement faut-il présenter?", [["1 scénario", "2 scénarios"], ["3 scénarios", "❓ À confirmer"]]),
    ],
}


def _action_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(ACTION_BUTTONS, resize_keyboard=True, is_persistent=True)


def _type_label(type_id: str) -> str:
    return bot.report_profiles.profile(type_id)["label"]


def _project_type(project: dict) -> str:
    return bot.report_profiles.profile_key(project.get("inspection_type"))


def _matching_projects(company: str, type_id: str) -> list[dict]:
    results = []
    for project in bot.get_projects():
        project_company = project.get("company", "bsf")
        if project_company != company:
            continue
        if company == "metra" and _project_type(project) != type_id:
            continue
        results.append(project)
    return results


def _project_button(project: dict, duplicate_names: set[str]) -> str:
    name = project.get("name", "Projet")
    if name not in duplicate_names:
        return name
    return f"{name} — {project.get('address', 'Adresse inconnue')}"


def _set_metra_type(session: dict, type_id: str, service: str) -> None:
    session["company"] = "metra"
    session["service"] = service
    session["inspection_type"] = type_id


async def _show_actions(update, session: dict) -> int:
    company = "Metra Consultation" if session.get("company") == "metra" else "BSF Inspections"
    selected = session.get("inspection_type")
    subtitle = f"\nService: {_type_label(selected)}" if selected else ""
    await update.message.reply_text(
        f"✅ {company}{subtitle}\n\nWhat would you like to do?",
        reply_markup=_action_keyboard(),
    )
    return bot.STATE_MAIN_MENU


def install_project_workflow() -> None:
    original_main_menu = bot.got_main_menu
    original_project_select = bot.got_project_select
    original_admin_got_name = bot.admin_got_name

    async def got_company(update, ctx: ContextTypes.DEFAULT_TYPE):
        choice = update.message.text.strip()
        session = bot.load_session(update.effective_chat.id)
        if "Metra" in choice:
            session["company"] = "metra"
            bot.save_session(update.effective_chat.id, session)
            await update.message.reply_text(
                "🔷 *Metra Consultation*\n\nSelect the service:",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(METRA_SERVICES, one_time_keyboard=True, resize_keyboard=True),
            )
            return bot.STATE_METRA_SERVICE
        if "BSF" in choice:
            ctx.user_data.pop("project_meta", None)
            session["company"] = "bsf"
            session.pop("service", None)
            session.pop("inspection_type", None)
            bot.save_session(update.effective_chat.id, session)
            return await _show_actions(update, session)
        await update.message.reply_text("Please select Metra Consultation or BSF Inspections.", reply_markup=ReplyKeyboardMarkup(COMPANY_BUTTONS, resize_keyboard=True))
        return bot.STATE_COMPANY

    async def got_metra_service(update, ctx: ContextTypes.DEFAULT_TYPE):
        choice = update.message.text.strip()
        session = bot.load_session(update.effective_chat.id)
        if "Loi 122" in choice:
            session["service"] = "loi122"
            bot.save_session(update.effective_chat.id, session)
            await update.message.reply_text("Select the Loi 122 inspection:", reply_markup=ReplyKeyboardMarkup(LOI122_TYPES, one_time_keyboard=True, resize_keyboard=True))
            return bot.STATE_METRA_SUBTYPE
        if "Loi 16" in choice:
            _set_metra_type(session, "loi16", "loi16")
            bot.save_session(update.effective_chat.id, session)
            return await _show_actions(update, session)
        if "ancrages" in choice.lower():
            session["service"] = "anchors"
            bot.save_session(update.effective_chat.id, session)
            await update.message.reply_text("Select the anchor inspection:", reply_markup=ReplyKeyboardMarkup(ANCHOR_TYPES, one_time_keyboard=True, resize_keyboard=True))
            return bot.STATE_METRA_SUBTYPE
        await update.message.reply_text("Please select one of the listed services.", reply_markup=ReplyKeyboardMarkup(METRA_SERVICES, resize_keyboard=True))
        return bot.STATE_METRA_SERVICE

    async def got_metra_subtype(update, ctx: ContextTypes.DEFAULT_TYPE):
        choice = update.message.text.strip()
        session = bot.load_session(update.effective_chat.id)
        mapping = {
            "Façades – Loi 122": ("facade", "loi122"),
            "Stationnement – Loi 122": ("parking", "loi122"),
            "Ancrages – Inspection annuelle": ("anchor_annual", "anchors"),
            "Ancrages – Inspection 5 ans": ("anchor_5year", "anchors"),
        }
        selected = mapping.get(choice)
        if selected is None:
            keyboard = LOI122_TYPES if session.get("service") == "loi122" else ANCHOR_TYPES
            await update.message.reply_text("Please select one of the listed inspection types.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return bot.STATE_METRA_SUBTYPE
        _set_metra_type(session, selected[0], selected[1])
        bot.save_session(update.effective_chat.id, session)
        return await _show_actions(update, session)

    async def got_main_menu(update, ctx: ContextTypes.DEFAULT_TYPE):
        session = bot.load_session(update.effective_chat.id)
        if session.get("company") != "metra":
            return await original_main_menu(update, ctx)

        choice = update.message.text.strip()
        if "Define" in choice or ("project" in choice.lower() and "report" not in choice.lower()):
            ctx.user_data["project_meta"] = {
                "company": "metra",
                "service": session.get("service"),
                "inspection_type": session.get("inspection_type"),
            }
            return await original_main_menu(update, ctx)

        projects = _matching_projects("metra", session.get("inspection_type", ""))
        if not projects:
            await update.message.reply_text(
                "⚠️ No matching Metra project exists yet. Define the project first.",
                reply_markup=_action_keyboard(),
            )
            return bot.STATE_MAIN_MENU
        counts = {}
        for project in projects:
            counts[project.get("name", "Projet")] = counts.get(project.get("name", "Projet"), 0) + 1
        duplicates = {name for name, count in counts.items() if count > 1}
        choices = {}
        for project in projects:
            label = _project_button(project, duplicates)
            choices[label] = project.get("id")
        ctx.user_data["metra_project_choices"] = choices
        await update.message.reply_text(
            "📋 Select the project:",
            reply_markup=ReplyKeyboardMarkup([[label] for label in choices], one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_PROJECT_SELECT

    async def admin_got_name(update, ctx: ContextTypes.DEFAULT_TYPE):
        result = await original_admin_got_name(update, ctx)
        project = ctx.user_data.get("new_project", {})
        project.update(ctx.user_data.get("project_meta", {}))
        return result

    async def admin_got_address(update, ctx: ContextTypes.DEFAULT_TYPE):
        project = ctx.user_data.get("new_project")
        if not isinstance(project, dict):
            await update.message.reply_text("⚠️ Project setup expired. Type /start.")
            return bot.STATE_MAIN_MENU
        project["address"] = update.message.text.strip()
        project.setdefault("plans", [])
        project.setdefault("davit_detail", None)
        type_id = bot.report_profiles.profile_key(project.get("inspection_type"))
        ctx.user_data["checklist"] = CHECKLISTS.get(type_id, COMMON_QUESTIONS)
        ctx.user_data["checklist_index"] = 0
        project["project_fields"] = {}
        return await _ask_checklist_question(update, ctx)

    async def _ask_checklist_question(update, ctx):
        questions = ctx.user_data.get("checklist", [])
        index = int(ctx.user_data.get("checklist_index", 0))
        if index >= len(questions):
            return await _save_project(update, ctx)
        _, label, prompt, options = questions[index]
        keyboard = options or SKIP
        await update.message.reply_text(
            f"📋 *Project checklist {index + 1}/{len(questions)}*\n*{label}*\n{prompt}\n\nSelect one option:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_PROJECT_CHECKLIST

    async def got_project_checklist(update, ctx: ContextTypes.DEFAULT_TYPE):
        questions = ctx.user_data.get("checklist", [])
        index = int(ctx.user_data.get("checklist_index", 0))
        if index >= len(questions):
            return await _save_project(update, ctx)
        key, label, _, options = questions[index]
        answer = update.message.text.strip()
        valid_answers = {item for row in (options or SKIP) for item in row}
        if answer not in valid_answers:
            await update.message.reply_text(
                "⚠️ Please use one of the buttons below.",
                reply_markup=ReplyKeyboardMarkup(options or SKIP, resize_keyboard=True),
            )
            return bot.STATE_PROJECT_CHECKLIST
        if answer == "⏭ Passer":
            answer = "Non fourni"
        project = ctx.user_data["new_project"]
        project.setdefault("project_fields", {})[key] = {"label": label, "value": answer}
        ctx.user_data["checklist_index"] = index + 1
        return await _ask_checklist_question(update, ctx)

    async def _save_project(update, ctx):
        project = ctx.user_data.get("new_project")
        if not isinstance(project, dict):
            await update.message.reply_text("⚠️ Project setup expired. Type /start.")
            return bot.STATE_MAIN_MENU
        project["created_at"] = datetime.now(timezone.utc).isoformat()
        database = bot.load_db()
        database.setdefault("projects", []).append(project)
        bot.save_db(database)
        ctx.user_data.pop("new_project", None)
        ctx.user_data.pop("checklist", None)
        ctx.user_data.pop("checklist_index", None)
        await update.message.reply_text(
            f"✅ Project *{project['name']}* saved with its {_type_label(project['inspection_type'])} checklist.\n\nSelect “Write a report” to open it and begin taking photos.",
            parse_mode="Markdown",
            reply_markup=_action_keyboard(),
        )
        return bot.STATE_MAIN_MENU

    async def got_project_select(update, ctx: ContextTypes.DEFAULT_TYPE):
        session_before = bot.load_session(update.effective_chat.id)
        if session_before.get("company") != "metra":
            return await original_project_select(update, ctx)

        selected_label = update.message.text.strip()
        project_id = ctx.user_data.get("metra_project_choices", {}).get(selected_label)
        project = next((p for p in bot.get_projects() if p.get("id") == project_id), None)
        if not project:
            await update.message.reply_text("❌ Project not found. Please select it again.")
            return bot.STATE_PROJECT_SELECT

        session = bot.load_session(update.effective_chat.id)
        session["project_name"] = project.get("name", "Projet")
        session["address"] = project.get("address", "—")
        session["plans"] = project.get("plans", [])
        session["davit_detail"] = project.get("davit_detail")
        session["company"] = "metra"
        session["service"] = project.get("service")
        session["inspection_type"] = project.get("inspection_type")
        session["project_fields"] = project.get("project_fields", {})
        session["project_id"] = project.get("id")
        bot.save_session(update.effective_chat.id, session)
        await update.message.reply_text(
            f"✅ *{project.get('name', 'Projet')}*\n"
            f"📍 {project.get('address', '—')}\n"
            f"📋 {_type_label(project.get('inspection_type'))}\n\n"
            "📸 Send the first inspection photo, or use the buttons below.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                PHOTO_CONTROL_BUTTONS,
                resize_keyboard=True,
                is_persistent=True,
            ),
        )
        return bot.STATE_PHOTO

    async def got_project_action(update, ctx: ContextTypes.DEFAULT_TYPE):
        return await got_main_menu(update, ctx)

    bot.got_company = got_company
    bot.got_metra_service = got_metra_service
    bot.got_metra_subtype = got_metra_subtype
    bot.got_main_menu = got_main_menu
    bot.admin_got_name = admin_got_name
    bot.admin_got_address = admin_got_address
    bot.got_project_checklist = got_project_checklist
    bot.got_project_select = got_project_select
    bot.got_project_action = got_project_action
