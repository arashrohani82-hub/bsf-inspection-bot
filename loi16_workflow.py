"""Exact financial and component inputs from the existing photo-state keyboard."""
from datetime import date
from telegram import ReplyKeyboardMarkup
import inspection_bot as bot
import reserve_fund as rf

BUTTON = "📊 Données Loi 16"
BACK = "↩️ Retour aux photos"
SKIP = "⏭ À confirmer"
FINANCE = [
    ("base_year", "Année monétaire de référence (ex. 2026)", "year"),
    ("years", "Nombre d’années de projection, au moins 25", "horizon"),
    ("balance_date", "Date exacte du solde initial (AAAA-MM-JJ)", "date"),
    ("opening_balance", "Solde initial exact du fonds, en dollars", "money"),
    ("annual_contribution", "Cotisation annuelle actuelle totale, en dollars", "money"),
    ("inflation", "Inflation annuelle des coûts, en pourcentage (ex. 2,5)", "rate"),
    ("interest", "Rendement annuel net du fonds, en pourcentage", "rate"),
    ("growth", "Indexation annuelle des cotisations, en pourcentage", "rate"),
    ("cost_basis", "Base des coûts : préciser taxes, honoraires et contingence inclus ou exclus", "text"),
]
COMPONENT = [
    ("quantity", "Quantité et unité (ex. 180 m²)", "text"),
    ("installed", "Année d’installation ou mention Inconnue", "text"),
    ("useful_life", "Durée de vie utile et sa référence", "text"),
    ("remaining_life", "Vie résiduelle estimée et justification", "text"),
    ("action", "Réparation majeure ou remplacement prévu", "text"),
    ("year", "Année prévue des premiers travaux (pas avant l’année de référence)", "year"),
    ("cost", "Coût TOTAL à l’année de référence, selon la base des coûts déclarée", "money"),
    ("cost_source", "Source et date du coût (soumission, estimation, référence)", "text"),
    ("cycle", "Répétition des travaux, en années; 0 = intervention unique", "cycle"),
    ("restricted", "Partie commune à usage restreint?", "bool"),
    ("maintenance", "Tâche d’entretien courant, distincte des travaux majeurs", "text"),
    ("frequency", "Fréquence d’entretien (ex. annuelle, mensuelle)", "text"),
    ("responsible", "Responsable de l’entretien", "text"),
    ("due_date", "Prochaine échéance d’entretien", "text"),
]


def controls():
    return ReplyKeyboardMarkup([[BUTTON], ["🗑 Remove last photo", "✅ Finish inspection"], ["🏠 New inspection"]], resize_keyboard=True)


def parse(text, kind):
    if kind == "text":
        if not text or len(text) > 1500:
            raise ValueError("Texte requis (maximum 1500 caractères)")
        return text
    if kind == "bool":
        if text not in ("Oui", "Non"):
            raise ValueError("Choisir Oui ou Non")
        return text == "Oui"
    if kind == "date":
        return date.fromisoformat(text).isoformat()
    value = rf.number(text)
    if kind in ("year", "horizon", "cycle"):
        limits = {"year": (2000, 2200), "horizon": (25, 100), "cycle": (0, 200)}
        low, high = limits[kind]
        if value != int(value) or not low <= value <= high:
            raise ValueError(f"Entier entre {low} et {high} requis")
        return int(value)
    if kind == "rate":
        if not 0 <= value <= 25:
            raise ValueError("Taux entre 0 et 25 % requis")
        return str(value / 100)
    if value < 0:
        raise ValueError("Montant positif ou nul requis")
    return str(value)


def install_loi16_workflow():
    original_select = bot.got_project_select
    original_control = bot.got_photo_control
    original_caption = bot.got_group_caption_fr
    original_photo = bot.got_photo

    def eligible(session):
        return session.get("company") == "metra" and bot.report_profiles.profile_key(session.get("inspection_type")) == "loi16"

    def persist(chat_id, session):
        bot.save_session(chat_id, session)
        # Financial assumptions belong to the selected project; component plans
        # stay with the session's photo groups and must never follow group indexes
        # into a different inspection.
        db = bot.load_db()
        for project in db.get("projects", []):
            if project.get("id") == session.get("project_id"):
                project["reserve_fund"] = session.get("reserve_fund", {})
                bot.save_db(db)
                break

    async def menu(update, ctx, session):
        ctx.user_data["loi16_editor"] = {"stage": "menu", "project_id": session.get("project_id")}
        options = [["💰 Hypothèses financières"]] + [[f"A{i:03d} {g.get('element_type', 'Composante')}"] for i, g in enumerate(session.get("groups", []), 1)] + [[BACK]]
        await update.message.reply_text("Données exactes Loi 16\nChoisir les hypothèses ou une fiche de composante. Ajouter les photos avant les fiches. Les valeurs inconnues restent à confirmer.", reply_markup=ReplyKeyboardMarkup(options, resize_keyboard=True))
        return bot.STATE_PHOTO

    async def ask(update, ctx, session):
        edit = ctx.user_data["loi16_editor"]
        fields = FINANCE if edit["stage"] == "finance" else COMPONENT
        if edit["index"] >= len(fields):
            persist(update.effective_chat.id, session)
            await update.message.reply_text("✅ Données enregistrées.")
            return await menu(update, ctx, session)
        key, prompt, kind = fields[edit["index"]]
        target = session.get("reserve_fund", {}) if edit["stage"] == "finance" else session["groups"][edit["component"]].get("reserve_plan", {})
        current = target.get(key)
        rows = [["Oui", "Non"]] if kind == "bool" else []
        rows += [[SKIP], [BACK]]
        await update.message.reply_text(f"{edit['index'] + 1}/{len(fields)} - {prompt}\nValeur enregistrée : {current if current is not None else 'À confirmer'}\nSaisir la valeur exacte ou choisir À confirmer.", reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True))
        return bot.STATE_PHOTO

    async def selected(update, ctx):
        ctx.user_data.pop("loi16_editor", None)
        result = await original_select(update, ctx)
        session = bot.load_session(update.effective_chat.id)
        if result == bot.STATE_PHOTO and eligible(session):
            project = next((p for p in bot.get_projects() if p.get("id") == session.get("project_id")), {})
            session["reserve_fund"] = project.get("reserve_fund", {})
            bot.save_session(update.effective_chat.id, session)
            await update.message.reply_text("Le bouton Données Loi 16 permet de compléter les montants exacts et les fiches techniques.", reply_markup=controls())
        return result

    async def control(update, ctx):
        session = bot.load_session(update.effective_chat.id)
        if not eligible(session):
            ctx.user_data.pop("loi16_editor", None)
            return await original_control(update, ctx)
        text = update.message.text.strip()
        edit = ctx.user_data.get("loi16_editor")
        if text == BACK or (edit and edit.get("project_id") != session.get("project_id")):
            ctx.user_data.pop("loi16_editor", None)
            await update.message.reply_text("📸 Photos et génération du rapport", reply_markup=controls())
            return bot.STATE_PHOTO
        if text == BUTTON:
            return await menu(update, ctx, session)
        if not edit:
            result = await original_control(update, ctx)
            if result == bot.STATE_PHOTO:
                await update.message.reply_text("📊 Fiches et hypothèses accessibles ci-dessous.", reply_markup=controls())
            return result
        if edit["stage"] == "menu":
            if text == "💰 Hypothèses financières":
                edit.update(stage="finance", index=0)
            else:
                options = {f"A{i:03d} {g.get('element_type', 'Composante')}": i - 1 for i, g in enumerate(session.get("groups", []), 1)}
                if text not in options:
                    return await menu(update, ctx, session)
                edit.update(stage="component", component=options[text], index=0)
            return await ask(update, ctx, session)
        fields = FINANCE if edit["stage"] == "finance" else COMPONENT
        key, _, kind = fields[edit["index"]]
        try:
            value = None if text == SKIP else parse(text, kind)
        except ValueError as exc:
            await update.message.reply_text("⚠️ " + str(exc))
            return await ask(update, ctx, session)
        if edit["stage"] == "finance":
            target = session.setdefault("reserve_fund", {})
        else:
            target = session["groups"][edit["component"]].setdefault("reserve_plan", {})
        target[key] = value
        persist(update.effective_chat.id, session)
        edit["index"] += 1
        return await ask(update, ctx, session)

    async def caption(update, ctx):
        result = await original_caption(update, ctx)
        if result == bot.STATE_PHOTO and eligible(bot.load_session(update.effective_chat.id)):
            await update.message.reply_text("Compléter la fiche technique depuis Données Loi 16.", reply_markup=controls())
        return result

    async def photo(update, ctx):
        if ctx.user_data.get("loi16_editor"):
            await update.message.reply_text("Terminer la saisie ou choisir Retour aux photos avant d’ajouter une photo.")
            return bot.STATE_PHOTO
        return await original_photo(update, ctx)

    bot.got_project_select = selected
    bot.got_photo_control = control
    bot.got_group_caption_fr = caption
    bot.got_photo = photo
