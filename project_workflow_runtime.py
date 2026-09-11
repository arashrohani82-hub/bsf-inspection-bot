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
YES_NO_UNKNOWN = [["✅ Oui", "❌ Non"], ["❓ Inconnu", "⏭ Passer"]]
SKIP = [["⏭ Passer"]]


COMMON_QUESTIONS = [
    ("client", "Client / syndicat", "Nom du client ou du syndicat de copropriété?", None),
    ("contact", "Personne-ressource", "Nom et coordonnées de la personne-ressource?", None),
    ("building_use", "Usage", "Usage principal du bâtiment?", [["Résidentiel", "Commercial"], ["Mixte", "⏭ Passer"]]),
    ("construction_year", "Année de construction", "Année de construction approximative?", None),
    ("storeys", "Étages", "Nombre d’étages hors sol?", None),
    ("documents", "Documents disponibles", "Quels documents sont disponibles (plans, rapports, factures, registre, etc.)?", None),
]

CHECKLISTS = {
    "facade": COMMON_QUESTIONS + [
        ("facade_materials", "Revêtements", "Principaux matériaux des façades?", None),
        ("last_detailed_inspection", "Inspection antérieure", "Date et auteur de la dernière inspection détaillée?", None),
        ("repairs_since", "Travaux antérieurs", "Réparations réalisées depuis la dernière inspection?", None),
        ("known_conditions", "Anomalies connues", "Déficiences, chutes de matériaux ou infiltrations déjà signalées?", None),
        ("dangerous_condition", "Condition dangereuse", "Une condition dangereuse est-elle présentement connue?", YES_NO_UNKNOWN),
        ("access_method", "Méthode d’accès", "Accès prévu: sol, toiture, nacelle, plateforme, drone ou ouvertures exploratoires?", None),
        ("public_exposure", "Exposition du public", "Décrire les trottoirs, entrées, terrasses ou zones publiques au pied des façades.", None),
        ("inspection_scope", "Portée", "Inspection quinquennale complète, suivi de travaux ou autre portée?", None),
    ],
    "parking": COMMON_QUESTIONS + [
        ("parking_levels", "Niveaux", "Nombre de niveaux de stationnement?", None),
        ("structural_system", "Système structural", "Type de structure (béton coulé, préfabriqué, dalle post-tendue, acier, etc.)?", None),
        ("environment", "Exposition", "Stationnement intérieur, extérieur ou partiellement exposé?", None),
        ("last_detailed_inspection", "Inspection antérieure", "Date et auteur de la dernière vérification approfondie?", None),
        ("annual_sheets", "Fiches annuelles", "Les fiches de vérification annuelle sont-elles disponibles?", YES_NO_UNKNOWN),
        ("known_conditions", "Anomalies connues", "Fissures, délamination, éclatement, corrosion, infiltration ou drainage déficient connus?", None),
        ("temporary_measures", "Mesures temporaires", "Présence d’étaiement, fermeture ou mesure de sécurité temporaire?", YES_NO_UNKNOWN),
        ("repairs_since", "Travaux antérieurs", "Réparations réalisées depuis la dernière inspection?", None),
    ],
    "anchor_annual": COMMON_QUESTIONS + [
        ("system_types", "Systèmes", "Systèmes présents: ancrages, lignes de vie, bossoirs, socles ou rails?", None),
        ("component_count", "Quantité", "Nombre approximatif de chaque composante?", None),
        ("roof_access", "Accès toiture", "Décrire l’accès sécuritaire à la toiture.", None),
        ("layout_available", "Plan de localisation", "Un plan numéroté des équipements est-il disponible?", YES_NO_UNKNOWN),
        ("manufacturer", "Fabricant", "Fabricant, modèle et année d’installation, si connus?", None),
        ("last_inspection", "Inspection antérieure", "Date du dernier rapport annuel et du dernier rapport quinquennal?", None),
        ("known_repairs", "Réparations", "Réparations, modifications ou équipements hors service connus?", None),
    ],
    "anchor_5year": COMMON_QUESTIONS + [
        ("system_types", "Systèmes", "Systèmes présents: ancrages, lignes de vie, bossoirs, socles ou rails?", None),
        ("component_count", "Quantité", "Nombre approximatif de chaque composante?", None),
        ("roof_access", "Accès toiture", "Décrire l’accès sécuritaire à la toiture.", None),
        ("layout_available", "Plan de localisation", "Un plan numéroté des équipements est-il disponible?", YES_NO_UNKNOWN),
        ("manufacturer", "Fabricant", "Fabricant, modèle et année d’installation, si connus?", None),
        ("previous_tests", "Essais antérieurs", "Rapports d’essais de traction/charge et valeurs obtenues disponibles?", YES_NO_UNKNOWN),
        ("test_method", "Méthode d’essai", "Méthode, charge cible et équipement d’essai prévus?", None),
        ("known_repairs", "Réparations", "Réparations, modifications ou équipements hors service connus?", None),
    ],
    "loi16": COMMON_QUESTIONS + [
        ("divided_coownership", "Copropriété divise", "Confirmer qu’il s’agit d’une copropriété divise.", YES_NO_UNKNOWN),
        ("units", "Unités", "Nombre d’unités privatives?", None),
        ("buildings", "Bâtiments", "Nombre de bâtiments couverts par le syndicat?", None),
        ("declaration", "Déclaration de copropriété", "La déclaration de copropriété et ses modifications sont-elles disponibles?", YES_NO_UNKNOWN),
        ("common_parts", "Parties communes", "Responsabilités particulières ou parties communes à usage restreint à considérer?", None),
        ("roof", "Toiture", "Type, âge approximatif et derniers travaux de toiture?", None),
        ("envelope", "Enveloppe", "Revêtements, fenêtres/balcons et répartition des responsabilités?", None),
        ("parking_elevator", "Équipements majeurs", "Stationnement étagé, ascenseur ou autres équipements majeurs présents?", None),
        ("mechanical", "Mécanique", "Principaux systèmes communs de plomberie, chauffage, ventilation et climatisation?", None),
        ("major_repairs", "Travaux majeurs", "Travaux majeurs réalisés ou prévus et leurs coûts, si connus?", None),
        ("claims", "Sinistres", "Sinistres, infiltrations ou réclamations importants connus?", None),
        ("reserve_balance", "Solde du fonds", "Solde actuel du fonds de prévoyance?", None),
        ("annual_contribution", "Contribution annuelle", "Contribution annuelle actuelle au fonds?", None),
        ("financial_records", "Données financières", "États financiers, budgets et placements du fonds disponibles?", YES_NO_UNKNOWN),
        ("previous_study", "Étude antérieure", "Carnet d’entretien ou étude du fonds antérieur disponible?", YES_NO_UNKNOWN),
    ],
}


def _action_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(ACTION_BUTTONS, one_time_keyboard=True, resize_keyboard=True)


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
            f"📋 *Project checklist {index + 1}/{len(questions)}*\n*{label}*\n{prompt}\n\nYou may type a detailed answer or skip.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return bot.STATE_PROJECT_CHECKLIST

    async def got_project_checklist(update, ctx: ContextTypes.DEFAULT_TYPE):
        questions = ctx.user_data.get("checklist", [])
        index = int(ctx.user_data.get("checklist_index", 0))
        if index >= len(questions):
            return await _save_project(update, ctx)
        key, label, _, _ = questions[index]
        answer = update.message.text.strip()
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
            "📸 Send the first inspection photo.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
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
