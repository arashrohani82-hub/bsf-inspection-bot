"""
BSF Inspections – Telegram Report Bot
Group-based photos: multiple photos share one caption
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
    STATE_GROUP_OR_ADD,
    STATE_GROUP_CAPTION_FR,
    STATE_GROUP_CAPTION_EN,
    STATE_ELEMENT_TYPE,
    STATE_LOCATION,
    STATE_PROBLEM,
) = range(11)

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


# ── Replace placeholders ───────────────────────────────────────────────────
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


# ── Insert single image (for davit detail) ────────────────────────────────
def insert_single_image(doc, anchor_para, img_path, width_inches=4.5, caption=""):
    insert_after = anchor_para._element
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
    insert_after = img_elem
    cap_elem = OxmlElement("w:p")
    insert_after.addnext(cap_elem)
    for p in doc.paragraphs:
        if p._element is cap_elem:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(caption)
            r.italic = True
            r.font.size = Pt(9)
            break


# ── Insert plans vertically ────────────────────────────────────────────────
def insert_photos_vertical(doc, anchor_elem, photos, lang, img_width=5.5):
    caption_k    = "caption_fr" if lang == "fr" else "caption_en"
    insert_after = anchor_elem
    fig_num      = 1
    for photo in photos:
        ai      = photo.get("ai", {})
        caption = ai.get(caption_k, f"Plan {fig_num}")
        img_path= photo.get("path")
        img_elem = OxmlElement("w:p")
        insert_after.addnext(img_elem)
        for p in doc.paragraphs:
            if p._element is img_elem:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if img_path and Path(img_path).exists():
                    try:
                        p.add_run().add_picture(img_path, width=Inches(img_width))
                    except:
                        p.add_run("[image error]")
                break
        insert_after = img_elem
        cap_elem = OxmlElement("w:p")
        insert_after.addnext(cap_elem)
        for p in doc.paragraphs:
            if p._element is cap_elem:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(f"Fig. {fig_num} – {caption}")
                r.italic = True
                r.font.size = Pt(9)
                break
        insert_after = cap_elem
        spacer = OxmlElement("w:p")
        insert_after.addnext(spacer)
        insert_after = spacer
        fig_num += 1



# ── Add label to image ─────────────────────────────────────────────────────
def add_label_to_image(img_path, label, output_path, display_width_px=800):
    """Resize image to standard width, add large label, save."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(img_path).convert("RGB")
    # Resize to standard display width (preserving aspect ratio)
    ratio = display_width_px / img.width
    new_h = int(img.height * ratio)
    img = img.resize((display_width_px, new_h), Image.LANCZOS)
    draw = ImageDraw.Draw(img)
    # Label = 1/5 of display width — always large and clear
    font_size = display_width_px // 5
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
    pad  = font_size // 4
    bbox = draw.textbbox((0, 0), label, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.rectangle([0, 0, w + pad*2, h + pad*2], fill="white")
    draw.text((pad, pad), label, fill="black", font=font)
    img.save(output_path, format="JPEG", quality=92)
    return output_path

# ── Insert photo groups ────────────────────────────────────────────────────
def insert_photo_groups(doc, anchor_elem, groups, lang):
    """
    groups = [
        {
            "caption_fr": "...",
            "caption_en": "...",
            "severity": "major",
            "photos": [{"path": "..."},  ...]
        },
        ...
    ]
    Each group gets a 2-column grid + one shared caption below.
    """
    caption_k    = "caption_fr" if lang == "fr" else "caption_en"
    insert_after = anchor_elem
    group_num    = 1

    for group in groups:
        photos   = group.get("photos", [])
        caption  = group.get(caption_k, "")
        severity = SEVERITY_MAP.get(group.get("severity", "ok"), "")
        n        = len(photos)

        # Letter labels: a, b, c...
        letters = [chr(ord('a') + i) for i in range(n)]
        if n == 1:
            fig_label = f"Fig. {group_num}"
        else:
            fig_label = f"Fig. {group_num}a à {group_num}{letters[-1]}"

        # Build 2-col grid of photos (no captions per photo)
        if len(photos) % 2 != 0:
            photos_padded = photos + [None]
        else:
            photos_padded = photos

        pairs = [(photos_padded[i], photos_padded[i+1]) for i in range(0, len(photos_padded), 2)]

        pair_idx = 0
        for left, right in pairs:
            left_idx   = pair_idx * 2
            right_idx  = pair_idx * 2 + 1
            left_label  = f"{group_num}{letters[left_idx]}"  if left_idx  < len(letters) else ""
            right_label = f"{group_num}{letters[right_idx]}" if right_idx < len(letters) else ""
            pair_idx += 1
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

            def fill_cell(cell, photo, label=""):
                if photo is None:
                    return
                img_path = photo.get("path")
                img_para = cell.paragraphs[0]
                img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if img_path and Path(img_path).exists():
                    try:
                        labeled_path = img_path.replace(".jpg", f"_{label}.jpg")
                        add_label_to_image(img_path, label, labeled_path)
                        img_para.add_run().add_picture(labeled_path, width=Inches(2.7))
                    except:
                        img_para.add_run("[image error]")

            fill_cell(tbl.rows[0].cells[0], left,  left_label  if left  else "")
            fill_cell(tbl.rows[0].cells[1], right, right_label if right else "")

            tbl_el = tbl._tbl
            doc._body._body.remove(tbl_el)
            insert_after.addnext(tbl_el)
            insert_after = tbl_el

        # Shared caption below the grid
        cap_elem = OxmlElement("w:p")
        insert_after.addnext(cap_elem)
        for p in doc.paragraphs:
            if p._element is cap_elem:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(f"{fig_label} – {caption}")
                r.italic = True
                r.font.size = Pt(9)
                break
        insert_after = cap_elem

        # Severity line
        sev_elem = OxmlElement("w:p")
        insert_after.addnext(sev_elem)
        for p in doc.paragraphs:
            if p._element is sev_elem:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(f"{severity}")
                r.font.size = Pt(8)
                break
        insert_after = sev_elem

        # Spacer between groups
        spacer = OxmlElement("w:p")
        insert_after.addnext(spacer)
        insert_after = spacer

        group_num += 1


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
2. Assign severity: critical | major | moderate | minor | ok
3. Write a SHORT professional caption in French (≤ 20 words).
4. Write the SAME caption in English (≤ 20 words).

Respond ONLY with valid JSON:
{{
  "caption_fr": "...",
  "caption_en": "...",
  "severity": "critical|major|moderate|minor|ok"
}}"""
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
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
    groups       = session.get("groups", [])
    plans        = session.get("plans", [])
    davit_detail = session.get("davit_detail")

    apply_replacements(doc, {
        "{{Project_Name}}":          project,
        "{{Address_of _project }}":  address,
        "{{Address_of_project}}":    address,
        "{{Date }}":                 date,
        "{{Date}}":                  date,
        "{{caption}}":               "",
    })

    for para in doc.paragraphs:
        if "{{Plans}}" in para.text:
            for run in para.runs: run.text = ""
            if plans:
                insert_photos_vertical(doc, para._element, plans, lang, img_width=5.5)
            break

    for para in doc.paragraphs:
        if "{{Detail_davit" in para.text:
            for run in para.runs: run.text = ""
            if davit_detail:
                cap = "Fig. 2 : Détail de configuration des bossoirs" if lang == "fr" else "Fig. 2 : Davit configuration detail"
                insert_single_image(doc, para, davit_detail, width_inches=4.5, caption=cap)
            break

    photos_para = None
    for para in doc.paragraphs:
        if "{{Photos" in para.text:
            photos_para = para
            break
    if photos_para is None:
        photos_para = doc.add_paragraph()
    for run in photos_para.runs: run.text = ""
    if groups:
        insert_photo_groups(doc, photos_para._element, groups, lang)

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
    save_session(chat_id, {"groups": [], "plans": [], "davit_detail": None,
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
        "🗺 Do you have *floor plans* to attach?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["📎 Send plans", "⏭ Skip plans"]], one_time_keyboard=True, resize_keyboard=True))
    return STATE_PLANS

async def got_plan_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    photo_file = await update.message.photo[-1].get_file()
    plan_idx   = len(session.get("plans", [])) + 1
    plan_path  = str(PHOTOS_DIR / f"{chat_id}_plan_{plan_idx}.jpg")
    await photo_file.download_to_drive(plan_path)
    session.setdefault("plans", []).append({"path": plan_path, "ai": {
        "caption_fr": f"Plan {plan_idx}", "caption_en": f"Plan {plan_idx}",
        "severity": "ok", "detail_fr": "", "detail_en": "",
    }})
    save_session(chat_id, session)
    await update.message.reply_text(
        f"✅ Plan {plan_idx} saved!",
        reply_markup=ReplyKeyboardMarkup([["📎 Send another plan", "⏭ Done with plans"]], one_time_keyboard=True, resize_keyboard=True))
    return STATE_PLANS

async def got_plan_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if "skip" in text or "plans" not in text:
        await update.message.reply_text(
            "🔩 Do you have a *davit detail drawing*?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["📎 Send davit detail", "⏭ Skip davit detail"]], one_time_keyboard=True, resize_keyboard=True))
        return STATE_DAVIT_DETAIL
    await update.message.reply_text(
        "✅ Send the plan photo now, or tap Skip.",
        reply_markup=ReplyKeyboardMarkup([["⏭ Skip plans"]], one_time_keyboard=True, resize_keyboard=True))
    return STATE_PLANS

async def got_davit_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    photo_file = await update.message.photo[-1].get_file()
    davit_path = str(PHOTOS_DIR / f"{chat_id}_davit_detail.jpg")
    await photo_file.download_to_drive(davit_path)
    session["davit_detail"] = davit_path
    save_session(chat_id, session)
    await update.message.reply_text(
        "✅ Davit detail saved!\n\n📸 Send the *first inspection photo*.", parse_mode="Markdown")
    return STATE_PHOTO

async def got_davit_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if "skip" in text or "davit" not in text:
        await update.message.reply_text(
            "📸 Send the *first inspection photo*.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove())
        return STATE_PHOTO
    await update.message.reply_text(
        "Send the davit detail photo, or tap Skip.",
        reply_markup=ReplyKeyboardMarkup([["⏭ Skip davit detail"]], one_time_keyboard=True, resize_keyboard=True))
    return STATE_DAVIT_DETAIL

async def got_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    session    = load_session(chat_id)
    photo_file = await update.message.photo[-1].get_file()
    total      = sum(len(g["photos"]) for g in session.get("groups", []))
    photo_path = str(PHOTOS_DIR / f"{chat_id}_photo_{total+1}.jpg")
    await photo_file.download_to_drive(photo_path)
    ctx.user_data["pending_photo_path"] = photo_path

    groups = session.get("groups", [])
    if groups:
        last = groups[-1]
        n    = len(last["photos"])
        await update.message.reply_text(
            f"📷 Photo received!\n\n"
            f"Current group: *{last.get('caption_en','Group')}* ({n} photo{'s' if n>1 else ''})\n\n"
            "Add to this group or start a new one?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [["➕ Add to current group", "🆕 New group"]],
                one_time_keyboard=True, resize_keyboard=True))
        return STATE_GROUP_OR_ADD
    else:
        await update.message.reply_text(
            "📷 First photo received!\n\n🔩 What *element type* is this?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(ELEMENT_TYPES, one_time_keyboard=True, resize_keyboard=True))
        return STATE_ELEMENT_TYPE

async def got_group_or_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if "Add" in choice:
        # Add to current group
        chat_id = update.effective_chat.id
        session = load_session(chat_id)
        session["groups"][-1]["photos"].append({"path": ctx.user_data["pending_photo_path"]})
        save_session(chat_id, session)
        n = len(session["groups"][-1]["photos"])
        await update.message.reply_text(
            f"✅ Photo added to current group ({n} photos total).\n\n"
            "📸 Send another photo or type */done* to generate reports.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return STATE_PHOTO
    else:
        # New group — ask element type
        await update.message.reply_text(
            "🆕 New group!\n\n🔩 What *element type* is this?",
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
        "🔍 Describe the observation for this group, or tap the button if no visible issue.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["⏭ No visible issue"]], one_time_keyboard=True, resize_keyboard=True))
    return STATE_PROBLEM

async def got_problem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    problem = update.message.text.strip()
    if problem.lower() in ("skip", "⏭ no visible issue", "no visible issue"): problem = ""

    await update.message.reply_text("🤖 Analysing photo with AI…")
    try:
        img_bytes = Path(ctx.user_data["pending_photo_path"]).read_bytes()
        ai = analyse_photo(img_bytes, ctx.user_data.get("element_type","Unknown"),
                           ctx.user_data.get("location","Unknown"), problem)
    except Exception as e:
        log.error(f"Claude API error: {e}")
        ai = {"caption_fr": "Observation à compléter",
              "caption_en": "Observation to be completed", "severity": "minor"}

    sev = SEVERITY_MAP.get(ai.get("severity","ok"),"")
    await update.message.reply_text(
        f"*Suggested caption (FR):* {ai.get('caption_fr')}\n"
        f"*Suggested caption (EN):* {ai.get('caption_en')}\n"
        f"*Severity:* {sev}\n\n"
        "✏️ Type your *French caption* for this group\n_(or press Enter to accept the suggestion)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    ctx.user_data["pending_ai"] = ai
    return STATE_GROUP_CAPTION_FR

async def got_group_caption_fr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ai   = ctx.user_data.get("pending_ai", {})
    ctx.user_data["final_caption_fr"] = text if text else ai.get("caption_fr", "")
    await update.message.reply_text("✏️ Now type the *English caption* for this group:")
    return STATE_GROUP_CAPTION_EN

async def got_group_caption_en(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    text    = update.message.text.strip()
    ai      = ctx.user_data.get("pending_ai", {})
    caption_en = text if text else ai.get("caption_en", "")
    caption_fr = ctx.user_data.get("final_caption_fr", "")
    severity   = ai.get("severity", "ok")

    new_group = {
        "caption_fr": caption_fr,
        "caption_en": caption_en,
        "severity":   severity,
        "photos":     [{"path": ctx.user_data["pending_photo_path"]}],
    }
    session.setdefault("groups", []).append(new_group)
    save_session(chat_id, session)

    g_num = len(session["groups"])
    await update.message.reply_text(
        f"✅ Group {g_num} created: *{caption_en}*\n\n"
        "📸 Send the next photo, or type */done* to generate reports.",
        parse_mode="Markdown")
    return STATE_PHOTO

async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = load_session(chat_id)
    groups  = session.get("groups", [])
    total   = sum(len(g["photos"]) for g in groups)
    if not groups:
        await update.message.reply_text("⚠️ No photos yet. Send at least one photo first.")
        return STATE_PHOTO
    await update.message.reply_text(
        f"📝 Building reports for *{session.get('project_name')}*…\n"
        f"{len(groups)} group(s), {total} photo(s) — please wait…",
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
    groups = session.get("groups", [])
    total  = sum(len(g["photos"]) for g in groups)
    msg    = (f"📊 *Status*\n"
              f"Project      : {session.get('project_name','—')}\n"
              f"Address      : {session.get('address','—')}\n"
              f"Plans        : {len(session.get('plans',[]))}\n"
              f"Davit detail : {'✅' if session.get('davit_detail') else '—'}\n"
              f"Groups       : {len(groups)}\n"
              f"Total photos : {total}\n\n")
    for i, g in enumerate(groups, 1):
        msg += f"  Group {i}: {g.get('caption_en','—')} ({len(g['photos'])} photos)\n"
    msg += "\nSend more photos or type /done."
    await update.message.reply_text(msg, parse_mode="Markdown")

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
            STATE_GROUP_OR_ADD:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_group_or_add)],
            STATE_ELEMENT_TYPE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_element_type)],
            STATE_LOCATION:        [MessageHandler(filters.TEXT & ~filters.COMMAND, got_location)],
            STATE_PROBLEM:         [MessageHandler(filters.TEXT & ~filters.COMMAND, got_problem)],
            STATE_GROUP_CAPTION_FR:[MessageHandler(filters.TEXT & ~filters.COMMAND, got_group_caption_fr)],
            STATE_GROUP_CAPTION_EN:[MessageHandler(filters.TEXT & ~filters.COMMAND, got_group_caption_en)],
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
