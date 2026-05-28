"""
BSF Inspections – Telegram Report Bot
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
import anthropic
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

(
    STATE_PROJECT_NAME,
    STATE_ADDRESS,
    STATE_PHOTO,
    STATE_ELEMENT_TYPE,
    STATE_LOCATION,
    STATE_PROBLEM,
    STATE_CONFIRM_CAPTION,
) = range(7)

ELEMENT_TYPES = [
    ["Anchor", "Davit"],
    ["Cable", "Base / Socket"],
    ["Facade", "Roof"],
    ["Other"],
]

SEVERITY_MAP = {
    "critical": "🔴 Critical",
    "major":    "🟠 Major",
    "moderate": "🟡 Moderate",
    "minor":    "🟢 Minor",
    "ok":       "✅ OK / Acceptable",
}

BASE_DIR      = Path("/app")
SESSIONS_DIR  = BASE_DIR / "sessions";  SESSIONS_DIR.mkdir(exist_ok=True)
PHOTOS_DIR    = BASE_DIR / "photos";    PHOTOS_DIR.mkdir(exist_ok=True)
REPORTS_DIR   = BASE_DIR / "reports";   REPORTS_DIR.mkdir(exist_ok=True)
TEMPLATE_PATH = BASE_DIR / "Template.docx"


# ── Session helpers ────────────────────────────────────────────────────────
def session_path(chat_id): return SESSIONS_DIR / f"{chat_id}.json"
def load_session(chat_id):
    p = session_path(chat_id)
    return json.loads(p.read_text()) if p.exists() else {}
def save_session(chat_id, data):
    session_path(chat_id).write_text(json.dumps(data, ensure_ascii=False, indent=2))
def clear_session(chat_id):
    p = session_path(chat_id)
    if p.exists(): p.unlink()


# ── Claude Vision ──────────────────────────────────────────────────────────
def analyse_photo(image_bytes, element_type, location, problem):
    import base64
    b64 = base64.standard_b64encode(image_bytes).decode()
    prompt = f"""You are a structural engineer assistant specialized in suspended access systems
(anchors, davits, lifelines, cables) inspected to CSA Z271 / CSA Z91 / ASTM E3121.

Context:
- Element type : {element_type}
- Location     : {location}
- Problem noted: {problem if problem else "Not specified — infer from image"}

Tasks:
1. Analyse the photo carefully.
2. Identify the defect or condition.
3. Assign severity: critical | major | moderate | minor | ok
4. Write a SHORT professional caption in French (≤ 25 words).
5. Write the SAME caption in English (≤ 25 words).
6. Write one technical detail sentence in French.
7. Write the same detail in English.

Respond ONLY with valid JSON, no markdown, no preamble:
{{
  "caption_fr": "...",
  "caption_en": "...",
  "severity": "critical|major|moderate|minor|ok",
  "detail_fr": "...",
  "detail_en": "..."
}}"""
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    raw = response.content[0].text.strip().replace("```json","").replace("```","").strip()
    return json.loads(raw)


# ── Report builder ─────────────────────────────────────────────────────────
def add_paragraph_after(doc, ref_paragraph, text="", style=None):
    """Insert a new paragraph after ref_paragraph and return it."""
    new_para = OxmlElement("w:p")
    ref_paragraph._element.addnext(new_para)
    # Find the newly inserted paragraph object
    for i, p in enumerate(doc.paragraphs):
        if p._element is new_para:
            if style:
                p.style = style
            if text:
                p.add_run(text)
            return p
    # Fallback: just append
    p = doc.add_paragraph(text)
    if style:
        p.style = style
    return p


def build_report(session, lang):
    doc     = Document(TEMPLATE_PATH)
    project = session.get("project_name", "—")
    address = session.get("address", "—")
    date    = session.get("date", datetime.today().strftime("%Y-%m-%d"))
    photos  = session.get("photos", [])

    replacements = {
        "{{Project_Name}}":          project,
        "{{Address_of _project }}":  address,
        "{{Address_of_project}}":    address,
        "{{Date }}":                 date,
        "{{Date}}":                  date,
    }

    def replace_para(para):
        for key, val in replacements.items():
            if key in para.text:
                for run in para.runs:
                    if key in run.text:
                        run.text = run.text.replace(key, val)

    for para in doc.paragraphs:
        replace_para(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    replace_para(para)

    # Find {{Photos}} placeholder paragraph
    photos_para = None
    for para in doc.paragraphs:
        if "{{Photos" in para.text:
            photos_para = para
            break

    if photos_para is None:
        # Append at end if placeholder not found
        photos_para = doc.add_paragraph()

    # Clear placeholder text
    for run in photos_para.runs:
        run.text = ""

    # Insert photos in reverse order (each addnext goes after the anchor)
    for idx, photo in enumerate(reversed(photos), start=1):
        real_idx  = len(photos) - idx + 1
        caption_k = "caption_fr" if lang == "fr" else "caption_en"
        detail_k  = "detail_fr"  if lang == "fr" else "detail_en"
        ai        = photo.get("ai", {})
        caption   = ai.get(caption_k, "")
        detail    = ai.get(detail_k, "")
        severity  = SEVERITY_MAP.get(ai.get("severity", "ok"), "")

        # 3. Severity line
        sev_p = OxmlElement("w:p")
        photos_para._element.addnext(sev_p)
        # find it and add text
        for p in doc.paragraphs:
            if p._element is sev_p:
                r = p.add_run(f"Severity: {severity}   |   {detail}")
                r.font.size = Pt(9)
                break

        # 2. Caption line
        cap_p = OxmlElement("w:p")
        photos_para._element.addnext(cap_p)
        for p in doc.paragraphs:
            if p._element is cap_p:
                r = p.add_run(f"Fig. {real_idx} – {caption}")
                r.italic = True
                r.font.size = Pt(10)
                break

        # 1. Image
        img_p = OxmlElement("w:p")
        photos_para._element.addnext(img_p)
        for p in doc.paragraphs:
            if p._element is img_p:
                img_path = photo.get("path")
                if img_path and Path(img_path).exists():
                    try:
                        p.add_run().add_picture(img_path, width=Inches(5.5))
                    except Exception as e:
                        p.add_run(f"[image error: {e}]")
                else:
                    p.add_run("[image not available]")
                break

    suffix = "FR" if lang == "fr" else "EN"
    fname  = f"{project.replace(' ','_')}_{date}_{suffix}.docx"
    out    = REPORTS_DIR / fname
    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    clear_session(chat_id)
    save_session(chat_id, {"photos": [], "date": datetime.today().strftime("%Y-%m-%d")})
    await update.message.reply_text(
        "👷 *BSF Inspections – Report Bot*\n\n"
        "Welcome! Let's start a new inspection.\n\n"
        "What is the *project name*?",
        parse_mode="Markdown",
    )
    return STATE_PROJECT_NAME


async def got_project_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    session["project_name"] = update.message.text.strip()
    save_session(chat_id, session)
    await update.message.reply_text("📍 What is the *site address*?", parse_mode="Markdown")
    return STATE_ADDRESS


async def got_address(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    session["address"] = update.message.text.strip()
    save_session(chat_id, session)
    await update.message.reply_text("✅ Project info saved!\n\n📸 Send the *first photo*.", parse_mode="Markdown")
    return STATE_PHOTO


async def got_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    session    = load_session(chat_id)
    photo_file = await update.message.photo[-1].get_file()
    photo_idx  = len(session["photos"]) + 1
    photo_path = str(PHOTOS_DIR / f"{chat_id}_photo_{photo_idx}.jpg")
    await photo_file.download_to_drive(photo_path)
    ctx.user_data["current_photo_path"] = photo_path
    await update.message.reply_text(
        "📷 Photo received!\n\n🔩 What *element type* is this?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(ELEMENT_TYPES, one_time_keyboard=True, resize_keyboard=True),
    )
    return STATE_ELEMENT_TYPE


async def got_element_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["element_type"] = update.message.text.strip()
    await update.message.reply_text(
        "📌 Where exactly in the structure?\n\n"
        "_e.g. Roof NE corner · Anchor #5 · Level 12 · South facade…_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_LOCATION


async def got_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["location"] = update.message.text.strip()
    await update.message.reply_text(
        "🔍 Describe the problem observed.\n\n_Type *skip* if there is no visible issue._",
        parse_mode="Markdown",
    )
    return STATE_PROBLEM


async def got_problem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    problem = update.message.text.strip()
    if problem.lower() == "skip":
        problem = ""

    await update.message.reply_text("🤖 Analysing photo with AI…")

    try:
        img_bytes = Path(ctx.user_data["current_photo_path"]).read_bytes()
        ai = analyse_photo(
            img_bytes,
            ctx.user_data.get("element_type", "Unknown"),
            ctx.user_data.get("location", "Unknown"),
            problem,
        )
    except Exception as e:
        log.error(f"Claude API error: {e}")
        ai = {
            "caption_fr": "Observation à compléter",
            "caption_en": "Observation to be completed",
            "severity":   "minor",
            "detail_fr":  "Détail à préciser.",
            "detail_en":  "Detail to be specified.",
        }

    sev = SEVERITY_MAP.get(ai.get("severity", "ok"), "")
    msg = (
        f"*Caption (FR):* {ai.get('caption_fr')}\n"
        f"*Caption (EN):* {ai.get('caption_en')}\n"
        f"*Severity:* {sev}\n"
        f"*Detail (FR):* {ai.get('detail_fr')}\n"
        f"*Detail (EN):* {ai.get('detail_en')}\n\n"
        "Do you accept this caption?"
    )
    await update.message.reply_text(
        msg, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["✅ Accept", "✏️ Edit"]], one_time_keyboard=True, resize_keyboard=True),
    )
    ctx.user_data["pending_ai"]      = ai
    ctx.user_data["pending_problem"] = problem
    return STATE_CONFIRM_CAPTION


async def got_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    choice  = update.message.text.strip()

    if "Edit" in choice:
        await update.message.reply_text(
            "✏️ Type the corrected *French caption*:", parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        ctx.user_data["editing"] = "caption_fr"
        return STATE_CONFIRM_CAPTION

    editing = ctx.user_data.pop("editing", None)
    if editing == "caption_fr":
        ctx.user_data["pending_ai"]["caption_fr"] = choice
        await update.message.reply_text("✏️ Now type the *English caption*:", parse_mode="Markdown")
        ctx.user_data["editing"] = "caption_en"
        return STATE_CONFIRM_CAPTION
    if editing == "caption_en":
        ctx.user_data["pending_ai"]["caption_en"] = choice

    session["photos"].append({
        "path":         ctx.user_data["current_photo_path"],
        "element_type": ctx.user_data.get("element_type"),
        "location":     ctx.user_data.get("location"),
        "problem":      ctx.user_data.get("pending_problem"),
        "ai":           ctx.user_data.get("pending_ai"),
    })
    save_session(chat_id, session)
    count = len(session["photos"])

    await update.message.reply_text(
        f"✅ Photo {count} saved!\n\n📸 Send the next photo, or type */done* to generate reports.",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_PHOTO


async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    photos  = session.get("photos", [])

    if not photos:
        await update.message.reply_text("⚠️ No photos yet. Send at least one photo first.")
        return STATE_PHOTO

    await update.message.reply_text(
        f"📝 Building reports for *{session.get('project_name')}*…\n{len(photos)} photo(s) — please wait…",
        parse_mode="Markdown",
    )

    try:
        report_fr = build_report(session, "fr")
        report_en = build_report(session, "en")
        await update.message.reply_document(open(report_fr,"rb"), filename=report_fr.name, caption="🇫🇷 French Report")
        await update.message.reply_document(open(report_en,"rb"), filename=report_en.name, caption="🇬🇧 English Report")
        await update.message.reply_text("✅ Done! Both reports sent.\nType /start for a new inspection.")
    except Exception as e:
        log.error(f"Report error: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

    clear_session(chat_id)
    return ConversationHandler.END


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    clear_session(update.effective_chat.id)
    await update.message.reply_text("❌ Inspection cancelled. Type /start to begin again.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    if not session:
        await update.message.reply_text("No active inspection. Type /start.")
        return
    count = len(session.get("photos", []))
    await update.message.reply_text(
        f"📊 *Status*\nProject : {session.get('project_name','—')}\nAddress : {session.get('address','—')}\nPhotos  : {count}\n\nSend more photos or type /done.",
        parse_mode="Markdown",
    )


def main():
    app  = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            STATE_PROJECT_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_project_name)],
            STATE_ADDRESS:         [MessageHandler(filters.TEXT & ~filters.COMMAND, got_address)],
            STATE_PHOTO:           [MessageHandler(filters.PHOTO, got_photo), CommandHandler("done", cmd_done)],
            STATE_ELEMENT_TYPE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_element_type)],
            STATE_LOCATION:        [MessageHandler(filters.TEXT & ~filters.COMMAND, got_location)],
            STATE_PROBLEM:         [MessageHandler(filters.TEXT & ~filters.COMMAND, got_problem)],
            STATE_CONFIRM_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel), CommandHandler("done", cmd_done)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("status", cmd_status))
    log.info("🚀 BSF Inspection Bot running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
