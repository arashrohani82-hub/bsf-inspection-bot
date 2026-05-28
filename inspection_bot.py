"""
BSF Inspections – Telegram Report Bot
Photos layout: 2-column grid, 4 photos per page
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
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

(
    STATE_PROJECT_NAME,
    STATE_ADDRESS,
    STATE_PLANS,
    STATE_DAVIT_DETAIL,
    STATE_PHOTO,
    STATE_ELEMENT_TYPE,
    STATE_LOCATION,
    STATE_PROBLEM,
    STATE_CONFIRM_CAPTION,
) = range(9)

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


# ── Replace placeholders (handles split runs) ──────────────────────────────
def replace_in_paragraph(para, replacements):
    full_text = para.text
    new_text  = full_text
    for key, val in replacements.items():
        new_text = new_text.replace(key, val)
    if new_text == full_text:
        return
    if para.runs:
        para.runs[0].text = new_text
        for run in para.runs[1:]:
            run.text = ""
    else:
        para.add_run(new_text)

def apply_replacements(doc, replacements):
    for para in doc.paragraphs:
        replace_in_paragraph(para, replacements)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    replace_in_paragraph(para, replacements)


# ── Insert single image at a paragraph ────────────────────────────────────
def insert_single_image(doc, anchor_para, img_path, width_inches=4.5, caption_fr="", caption_en="", lang="fr"):
    caption = caption_fr if lang == "fr" else caption_en
    insert_after = anchor_para._element

    # Caption paragraph
    cap_elem = OxmlElement("w:p")
    insert_after.addnext(cap_elem)
    for p in doc.paragraphs:
        if p._element is cap_elem:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(caption)
            r.italic = True
            r.font.size = Pt(9)
            break

    # Image paragraph (inserted before caption via addnext on anchor)
    img_elem = OxmlElement("w:p")
    insert_after.addnext(img_elem)
    for p in doc.paragraphs:
        if p._element is img_elem:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if img_path and Path(img_path).exists():
                try:
                    p.add_run().add_picture(img_path, width=Inches(width_inches))
                except Exception as e:
                    p.add_run(f"[image error: {e}]")
            break


# ── Photo grid (2 columns, 4 per page) ────────────────────────────────────
def insert_photo_grid(doc, anchor_elem, photos, lang, img_width=2.7):
    caption_k = "caption_fr" if lang == "fr" else "caption_en"
    detail_k  = "detail_fr"  if lang == "fr" else "detail_en"

    chunks = [photos[i:i+4] for i in range(0, len(photos), 4)]
    insert_after = anchor_elem
    fig_num = 1

    for chunk_idx, chunk in enumerate(chunks):
        if len(chunk) % 2 != 0:
            chunk = chunk + [None]
        pairs = [(chunk[i], chunk[i+1]) for i in range(0, len(chunk), 2)]

        for left_photo, right_photo in pairs:
            tbl = doc.add_table(rows=1, cols=2)

            tblPr = tbl._tbl.tblPr
            if tblPr is None:
                tblPr = OxmlElement("w:tblPr")
                tbl._tbl.insert(0, tblPr)
            tblBorders = OxmlElement("w:tblBorders")
            for bn in ["top","left","bottom","right","insideH","insideV"]:
                b = OxmlElement(f"w:{bn}")
                b.set(qn("w:val"), "none")
                tblBorders.append(b)
            tblPr.append(tblBorders)
            tblW = OxmlElement("w:tblW")
            tblW.set(qn("w:w"), "9360")
            tblW.set(qn("w:type"), "dxa")
            tblPr.append(tblW)

            def fill_cell(cell, photo, fn):
                if photo is None:
                    return
                ai       = photo.get("ai", {})
                caption  = ai.get(caption_k, "")
                detail   = ai.get(detail_k, "")
                severity = SEVERITY_MAP.get(ai.get("severity","ok"), "")
                img_path = photo.get("path")

                img_para = cell.paragraphs[0]
                img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = img_para.add_run()
                if img_path and Path(img_path).exists():
                    try:
                        run.add_picture(img_path, width=Inches(img_width))
                    except:
                        run.text = "[image error]"

                cap_p = cell.add_paragraph()
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = cap_p.add_run(f"Fig. {fn} – {caption}")
                r.italic = True
                r.font.size = Pt(8)

                sev_p = cell.add_paragraph()
                sev_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r2 = sev_p.add_run(f"{severity}  |  {detail}")
                r2.font.size = Pt(7)

            fill_cell(tbl.rows[0].cells[0], left_photo,  fig_num)
            fill_cell(tbl.rows[0].cells[1], right_photo, fig_num + 1)
            fig_num += 2

            tbl_el = tbl._tbl
            doc._body._body.remove(tbl_el)
            insert_after.addnext(tbl_el)
            insert_after = tbl_el

            spacer = OxmlElement("w:p")
            insert_after.addnext(spacer)
            insert_after = spacer

        if chunk_idx < len(chunks) - 1:
            pb_p  = OxmlElement("w:p")
            pb_r  = OxmlElement("w:r")
            pb_br = OxmlElement("w:br")
            pb_br.set(qn("w:type"), "page")
            pb_r.append(pb_br)
            pb_p.append(pb_r)
            insert_after.addnext(pb_p)
            insert_after = pb_p


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
4. Write a SHORT professional caption in French (≤ 20 words).
5. Write the SAME caption in English (≤ 20 words).
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
def build_report(session, lang):
    doc          = Document(TEMPLATE_PATH)
    project      = session.get("project_name", "—")
    address      = session.get("address", "—")
    date         = session.get("date", datetime.today().strftime("%Y-%m-%d"))
    photos       = session.get("photos", [])
    plans        = session.get("plans", [])
    davit_detail = session.get("davit_detail")

    replacements = {
        "{{Project_Name}}":          project,
        "{{Address_of _project }}":  address,
        "{{Address_of_project}}":    address,
        "{{Date }}":                 date,
        "{{Date}}":                  date,
        "{{caption}}":               "",
    }
    apply_replacements(doc, replacements)

    # ── {{Plans}} ──────────────────────────────────────────────────────────
    for para in doc.paragraphs:
        if "{{Plans}}" in para.text:
            for run in para.runs:
                run.text = ""
            if plans:
                insert_photo_grid(doc, para._element, plans, lang, img_width=4.5)
            break

    # ── {{Detail_davit}} ───────────────────────────────────────────────────
    for para in doc.paragraphs:
        if "{{Detail_davit" in para.text:
            for run in para.runs:
                run.text = ""
            if davit_detail:
                cap_fr = "Fig. 2 : Détail de configuration des bossoirs"
                cap_en = "Fig. 2 : Davit configuration detail"
                insert_single_image(doc, para, davit_detail, width_inches=4.5,
                                    caption_fr=cap_fr, caption_en=cap_en, lang=lang)
            break

    # ── {{Photos}} ─────────────────────────────────────────────────────────
    photos_para = None
    for para in doc.paragraphs:
        if "{{Photos" in para.text:
            photos_para = para
            break
    if photos_para is None:
        photos_para = doc.add_paragraph()
    for run in photos_para.runs:
        run.text = ""
    if photos:
        insert_photo_grid(doc, photos_para._element, photos, lang, img_width=2.7)

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
    save_session(chat_id, {"photos": [], "plans": [], "davit_detail": None,
                           "date": datetime.today().strftime("%Y-%m-%d")})
    await update.message.reply_text(
        "👷 *BSF Inspections – Report Bot*\n\nWelcome! Let's start a new inspection.\n\nWhat is the *project name*?",
        parse_mode="Markdown")
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
    await update.message.reply_text(
        "🗺 Do you have *floor plans* to attach?\n\nSend photos of the plans, or type *skip*.",
        parse_mode="Markdown")
    return STATE_PLANS

async def got_plan_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    session    = load_session(chat_id)
    photo_file = await update.message.photo[-1].get_file()
    plan_idx   = len(session.get("plans", [])) + 1
    plan_path  = str(PHOTOS_DIR / f"{chat_id}_plan_{plan_idx}.jpg")
    await photo_file.download_to_drive(plan_path)
    session.setdefault("plans", []).append({"path": plan_path, "ai": {
        "caption_fr": f"Plan {plan_idx}", "caption_en": f"Plan {plan_idx}",
        "severity": "ok", "detail_fr": "", "detail_en": "",
    }})
    save_session(chat_id, session)
    count = len(session["plans"])
    await update.message.reply_text(
        f"✅ Plan {count} saved!\n\nSend another plan, or type *skip* to continue.",
        parse_mode="Markdown")
    return STATE_PLANS

async def got_plan_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().lower() == "skip":
        await update.message.reply_text(
            "🔩 Do you have a *davit detail drawing*?\n\nSend a photo of the davit detail, or type *skip*.",
            parse_mode="Markdown")
        return STATE_DAVIT_DETAIL
    await update.message.reply_text("Send a plan photo, or type *skip* to continue.", parse_mode="Markdown")
    return STATE_PLANS

async def got_davit_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    session    = load_session(chat_id)
    photo_file = await update.message.photo[-1].get_file()
    davit_path = str(PHOTOS_DIR / f"{chat_id}_davit_detail.jpg")
    await photo_file.download_to_drive(davit_path)
    session["davit_detail"] = davit_path
    save_session(chat_id, session)
    await update.message.reply_text(
        "✅ Davit detail saved!\n\n📸 Now send the *first inspection photo*.",
        parse_mode="Markdown")
    return STATE_PHOTO

async def got_davit_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().lower() == "skip":
        await update.message.reply_text(
            "✅ No davit detail attached.\n\n📸 Now send the *first inspection photo*.",
            parse_mode="Markdown")
        return STATE_PHOTO
    await update.message.reply_text("Send a davit detail photo, or type *skip* to continue.", parse_mode="Markdown")
    return STATE_DAVIT_DETAIL

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
        reply_markup=ReplyKeyboardMarkup(ELEMENT_TYPES, one_time_keyboard=True, resize_keyboard=True))
    return STATE_ELEMENT_TYPE

async def got_element_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["element_type"] = update.message.text.strip()
    await update.message.reply_text(
        "📌 Where exactly in the structure?\n\n_e.g. Roof NE corner · Anchor #5 · Level 12_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return STATE_LOCATION

async def got_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["location"] = update.message.text.strip()
    await update.message.reply_text(
        "🔍 Describe the problem observed.\n\n_Type *skip* if there is no visible issue._",
        parse_mode="Markdown")
    return STATE_PROBLEM

async def got_problem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    problem = update.message.text.strip()
    if problem.lower() == "skip": problem = ""
    await update.message.reply_text("🤖 Analysing photo with AI…")
    try:
        img_bytes = Path(ctx.user_data["current_photo_path"]).read_bytes()
        ai = analyse_photo(img_bytes, ctx.user_data.get("element_type","Unknown"),
                           ctx.user_data.get("location","Unknown"), problem)
    except Exception as e:
        log.error(f"Claude API error: {e}")
        ai = {"caption_fr":"Observation à compléter","caption_en":"Observation to be completed",
              "severity":"minor","detail_fr":"Détail à préciser.","detail_en":"Detail to be specified."}
    sev = SEVERITY_MAP.get(ai.get("severity","ok"),"")
    msg = (
        f"*Caption (FR):* {ai.get('caption_fr')}\n"
        f"*Caption (EN):* {ai.get('caption_en')}\n"
        f"*Severity:* {sev}\n"
        f"*Detail (FR):* {ai.get('detail_fr')}\n"
        f"*Detail (EN):* {ai.get('detail_en')}\n\n"
        "Do you accept this caption?"
    )
    await update.message.reply_text(msg, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["✅ Accept","✏️ Edit"]], one_time_keyboard=True, resize_keyboard=True))
    ctx.user_data["pending_ai"]      = ai
    ctx.user_data["pending_problem"] = problem
    return STATE_CONFIRM_CAPTION

async def got_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    choice  = update.message.text.strip()
    if "Edit" in choice:
        await update.message.reply_text("✏️ Type the corrected *French caption*:",
                                        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
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
        "path": ctx.user_data["current_photo_path"],
        "element_type": ctx.user_data.get("element_type"),
        "location": ctx.user_data.get("location"),
        "problem": ctx.user_data.get("pending_problem"),
        "ai": ctx.user_data.get("pending_ai"),
    })
    save_session(chat_id, session)
    count = len(session["photos"])
    await update.message.reply_text(
        f"✅ Photo {count} saved!\n\n📸 Send the next photo, or type */done* to generate reports.",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
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
        parse_mode="Markdown")
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
    await update.message.reply_text("❌ Cancelled. Type /start to begin again.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    if not session:
        await update.message.reply_text("No active inspection. Type /start.")
        return
    await update.message.reply_text(
        f"📊 *Status*\n"
        f"Project      : {session.get('project_name','—')}\n"
        f"Address      : {session.get('address','—')}\n"
        f"Plans        : {len(session.get('plans',[]))}\n"
        f"Davit detail : {'✅' if session.get('davit_detail') else '—'}\n"
        f"Photos       : {len(session.get('photos',[]))}\n\n"
        "Send more photos or type /done.",
        parse_mode="Markdown")

def main():
    app  = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            STATE_PROJECT_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_project_name)],
            STATE_ADDRESS:         [MessageHandler(filters.TEXT & ~filters.COMMAND, got_address)],
            STATE_PLANS:           [MessageHandler(filters.PHOTO, got_plan_photo),
                                    MessageHandler(filters.TEXT & ~filters.COMMAND, got_plan_skip)],
            STATE_DAVIT_DETAIL:    [MessageHandler(filters.PHOTO, got_davit_photo),
                                    MessageHandler(filters.TEXT & ~filters.COMMAND, got_davit_skip)],
            STATE_PHOTO:           [MessageHandler(filters.PHOTO, got_photo),
                                    CommandHandler("done", cmd_done)],
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
