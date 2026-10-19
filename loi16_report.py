"""Metra reserve-fund study, component sheets and living maintenance log.

DOCX and PDF are authored from the same content, preserving table/photo order
without the legacy paragraph-only DOCX-to-PDF converter.
"""
from pathlib import Path
from io import BytesIO
from html import escape

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, PolyLine, String, Line
from reportlab.graphics import renderSVG
import reserve_fund as rf
import re

NAVY = colors.HexColor("#102f50")
GOLD = colors.HexColor("#efa916")
LOGO = Path(__file__).parent / "assets" / "metra-logo.png"
RULE_URL = "https://www.legisquebec.gouv.qc.ca/fr/document/rc/CCQ,%20r.%208.01"


def clean(text):
    return re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27ff\ufe0f\u200d]", "", str(text))


def dollars(value):
    return f"{value:,.2f} $".replace(",", " ")


class Report:
    def __init__(self):
        self.doc = Document()
        self.doc.core_properties.author = "Metra Consultation Inc."
        self.doc.core_properties.title = "Étude du fonds de prévoyance et carnet d’entretien"
        self.doc.core_properties.subject = "metra-loi16-v1"
        section = self.doc.sections[0]
        section.page_width, section.page_height = Inches(8.5), Inches(11)
        section.top_margin = section.bottom_margin = Inches(.7)
        section.left_margin = section.right_margin = Inches(.65)
        self.doc.styles["Normal"].font.name = "Arial"
        self.doc.styles["Normal"].font.size = Pt(10)
        self.doc.styles["Normal"].paragraph_format.space_after = Pt(7)
        footer = section.footer.paragraphs[0]
        footer.add_run("Metra Consultation Inc. | Ébauche à valider | Page ").font.size = Pt(8)
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        footer._p.append(field)
        self.styles = getSampleStyleSheet()
        self.styles["BodyText"].fontName = "Helvetica"
        self.styles["BodyText"].fontSize = 9
        self.styles["BodyText"].leading = 13
        self.styles["BodyText"].spaceAfter = 8
        self.styles["Heading1"].textColor = NAVY
        self.story = []

    def text(self, text, heading=0):
        text = clean(text)
        self.doc.add_heading(text, heading) if heading else self.doc.add_paragraph(str(text))
        style = self.styles["Heading1" if heading == 1 else "Heading2" if heading else "BodyText"]
        self.story.append(Paragraph(escape(str(text)).replace("\n", "<br/>"), style))

    def page(self):
        self.doc.add_page_break()
        self.story.append(PageBreak())

    def photo(self, path, caption="", width=3):
        path = Path(path)
        if not path.is_file():
            self.text("Photo indisponible : " + caption)
            return
        self.doc.add_picture(str(path), width=Inches(width))
        iw, ih = ImageReader(str(path)).getSize()
        w = min(width * 72, 490)
        h = w * ih / iw
        if h > 280:
            w, h = w * 280 / h, 280
        self.story.append(Image(str(path), w, h))
        if caption:
            self.text(caption)

    def table(self, headers, rows):
        rows = rows or [["À compléter"] + ["-"] * (len(headers) - 1)]
        headers = [clean(c) for c in headers]
        rows = [[clean(c) for c in row] for row in rows]
        word_table = self.doc.add_table(rows=1, cols=len(headers))
        word_table.style = "Table Grid"
        word_table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
        for i, value in enumerate(headers):
            word_table.rows[0].cells[i].text = value
        for row in rows:
            cells = word_table.add_row().cells
            for i, value in enumerate(row):
                cells[i].text = value
        for index, row in enumerate(word_table.rows):
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for cell in row.cells:
                if index == 0:
                    shading = OxmlElement("w:shd")
                    shading.set(qn("w:fill"), "E6EDF3")
                    cell._tc.get_or_add_tcPr().append(shading)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after = Pt(4)
                    for run in p.runs:
                        run.font.size = Pt(8)
                        run.bold = index == 0
        style = self.styles["BodyText"].clone("cell")
        style.fontSize, style.leading, style.spaceAfter = 7, 9, 0
        values = [[Paragraph(escape(str(c)).replace("\n", "<br/>"), style) for c in r] for r in [headers] + rows]
        table = Table(values, colWidths=[518 / len(headers)] * len(headers), repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6edf3")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7f9")]),
            ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#c4cdd5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        self.story.extend([table, Spacer(1, 12)])

    def chart(self, scenarios):
        # ReportLab vector graphic in PDF; SVG retained for editable source.
        drawing = Drawing(510, 220)
        all_values = [float(r["closing"]) for _, rows in scenarios for r in rows]
        low, high = min(0, min(all_values)), max(1, max(all_values))
        def xy(index, value, count):
            return (65 + 420 * index / max(count - 1, 1), 42 + 140 * (float(value) - low) / (high - low))
        for amount in (low, (high + low) / 2, high):
            y = xy(0, amount, 2)[1]
            drawing.add(Line(65, y, 485, y, strokeColor=colors.lightgrey, strokeWidth=.5))
            drawing.add(String(0, y - 2, f"{amount:,.0f} $".replace(",", " "), fontSize=8))
        for index, (name, rows) in enumerate(scenarios):
            points = [coord for i, row in enumerate(rows) for coord in xy(i, row["closing"], len(rows))]
            color = NAVY if index == 0 else GOLD
            drawing.add(PolyLine(points, strokeColor=color, strokeWidth=2))
            drawing.add(String(65 + index * 225, 12, name, fontSize=8, fillColor=color))
        rows = scenarios[0][1]
        drawing.add(String(65, 28, str(rows[0]["year"]), fontSize=8))
        drawing.add(String(460, 28, str(rows[-1]["year"]), fontSize=8))
        self.story.append(drawing)
        # DOCX embeds a PNG generated with the bundled graphics renderer.
        try:
            import cairosvg
            png = cairosvg.svg2png(bytestring=renderSVG.drawToString(drawing).encode())
            self.doc.add_picture(BytesIO(png), width=Inches(7))
        except (ImportError, OSError):
            self.doc.add_paragraph("Graphique comparatif fourni dans le PDF; valeurs détaillées aux tableaux annuels.")

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(path)
        def footer(canvas, doc):
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(NAVY)
            canvas.drawString(47, 24, "Metra Consultation Inc. | Ébauche à valider")
            canvas.drawRightString(565, 24, f"Page {doc.page}")
        SimpleDocTemplate(str(path.with_suffix(".pdf")), pagesize=(612, 792),
                          leftMargin=47, rightMargin=47, topMargin=45, bottomMargin=45,
                          title=self.doc.core_properties.title, author="Metra Consultation Inc.").build(
                              self.story, onFirstPage=footer, onLaterPages=footer)
        return path


def build_loi16_report(session, path):
    r = Report()
    groups = session.get("groups", [])
    data = session.get("reserve_fund", {})
    if LOGO.exists():
        r.photo(LOGO, width=1.8)
    r.text("Étude du fonds de prévoyance et carnet d’entretien", 1)
    r.text("METRA CONSULTATION INC.")
    if session.get("demonstration"):
        r.text("SPÉCIMEN - DONNÉES FICTIVES POUR DÉMONSTRATION. Aucun immeuble réel n’est évalué.")
    r.text(session.get("project_name", "Syndicat à préciser"), 2)
    r.text(session.get("address", "Adresse à préciser"))
    r.text("Préparé pour le conseil d’administration du syndicat")
    r.text("Préparé par Arash Rohani, ing., P.Eng.\nMetra Consultation Inc.\na.rohani@metraconsultation.ca | 438 867-4131\nmetraconsultation.ca")
    r.text(f"Visite : {session.get('date', 'À préciser')} | Dossier : {session.get('project_id', 'À préciser')}")
    r.text("ÉBAUCHE - Validation des données et signature de l’auteur requises avant émission.")
    r.page()
    r.text("Table des matières", 1)
    titles = ["1 Introduction et portée", "2 Cadre réglementaire", "3 Sommaire du bâtiment et documents",
              "4 Hypothèses et méthode financière", "5 Scénarios de financement", "6 Conclusion et validation",
              "Annexe A Inventaire des composantes", "Annexe B Réparations majeures et remplacements",
              "Annexe C Entretien préventif", "Annexe D Registre de suivi et documents"]
    for title in titles:
        r.text(title)
    r.text("Les sections et annexes sont générées selon les composantes effectivement inventoriées.")
    r.text("Lexique", 2)
    r.table(["Terme", "Définition"], [
        ["Vie résiduelle", "Durée estimée avant une intervention majeure, à confirmer selon l’état et l’historique."],
        ["Coût de référence", "Coût exprimé à l’année monétaire de départ; base des taxes et honoraires précisée séparément."],
        ["Fonds de prévoyance", "Ressources affectées aux réparations majeures et aux remplacements des parties communes."],
        ["Entretien courant", "Tâches récurrentes présentées au carnet; exclues des dépenses du fonds modélisées ici."],
    ])
    r.page()
    r.text(titles[0], 1)
    r.text("Cette étude organise les observations de l’immeuble, les interventions majeures et les besoins de financement du syndicat. Le carnet d’entretien regroupe les tâches préventives et permet de consigner les travaux réalisés et les pièces justificatives.")
    r.text("Le mandat comprend l’examen des documents reçus et des parties accessibles lors de la visite. L’inspection est visuelle et non destructive sauf essais expressément consignés. Les éléments cachés et les zones inaccessibles doivent être identifiés. Les quantités, durées résiduelles, coûts et responsabilités doivent être validés avant la recommandation finale.")
    r.text("Les limites des parties communes et les obligations du syndicat, y compris certains équipements en parties privatives, sont établies à partir de la déclaration de copropriété. Cette étude ne constitue pas une évaluation de la valeur de reconstruction aux fins d’assurance.")
    r.text(titles[1], 1)
    r.text("Référence : Règlement établissant diverses règles en matière de copropriété divise, CCQ, r. 8.01, articles 1 à 9. Texte consulté le 19 octobre 2026; version officielle affichée à jour au 1er juillet 2026. " + RULE_URL)
    r.text("Le carnet décrit les composantes dont le syndicat est responsable, leur état et les interventions prévues sur au moins 25 ans. Il comprend les renseignements et documents d’entretien disponibles. Sa mise à jour relève du conseil d’administration au moins une fois par année. L’étude financière est obtenue au moins tous les cinq ans. La périodicité de révision du carnet est à confirmer selon les caractéristiques de l’immeuble et l’article 5.")
    r.text("L’auteur doit vérifier son admissibilité et son indépendance. La déclaration d’examen sur place et de prise de connaissance des documents est datée et signée après vérification; aucune déclaration de conformité ni signature n’est apposée automatiquement.")
    r.text(titles[2], 1)
    r.table(["Information", "Donnée"], [["Projet", session.get("project_name", "À préciser")],
        ["Adresse", session.get("address", "À préciser")], ["Date de visite", session.get("date", "À préciser")]] +
        [[v.get("label", k), v.get("value", "À préciser")] for k, v in session.get("project_fields", {}).items() if isinstance(v, dict)])
    r.page()
    r.text(titles[3], 1)
    scenarios = []
    try:
        current = rf.project(data, groups)
        minimum = rf.recommended_contribution(data, groups)
        recommended = rf.project(data, groups, minimum)
        scenarios = [("Cotisation actuelle", current), ("Seuil mathématique calculé", recommended)]
        r.table(["Hypothèse", "Valeur"], [["Année monétaire", data["base_year"]], ["Horizon", f"{data['years']} années"],
            ["Solde initial", dollars(rf.money(data["opening_balance"]))], ["Date du solde", data["balance_date"]],
            ["Cotisation initiale actuelle", dollars(rf.money(data["annual_contribution"]))],
            ["Inflation / rendement / indexation", " / ".join(f"{rf.number(data[k])*100:g} %" for k in ("inflation", "interest", "growth"))],
            ["Base des coûts", data["cost_basis"]], ["Cotisations spéciales", "Aucune dans ces deux scénarios"]])
        r.text("Chaque coût futur = coût de référence × (1 + inflation) puissance (année des travaux - année de référence). Les coûts saisis sont des montants totaux incluant uniquement les éléments déclarés dans la base des coûts; aucune taxe n’est ajoutée une seconde fois.")
        r.text("Convention annuelle : cotisation versée en début d’année, travaux payés ensuite, rendement net crédité en fin d’année sur le solde positif restant. Solde final = solde initial + cotisation - dépenses + rendement. Les valeurs sont arrondies au cent; un solde négatif représente un déficit, sans rendement fictif ni cotisation spéciale automatique. Cette convention simplifiée ne remplace pas une analyse des dates réelles de paiement.")
        r.page()
        r.text(titles[4], 1)
        r.table(["Scénario", "Cotisation an 1", "Solde minimal", "Solde final"],
            [[name, dollars(rows[0]["contribution"]), dollars(min(x["closing"] for x in rows)), dollars(rows[-1]["closing"])] for name, rows in scenarios])
        r.text(f"Seuil initial calculé : {dollars(minimum)} par année, avec l’indexation indiquée. Il s’agit du minimum mathématique maintenant les soldes annuels non négatifs selon l’inventaire et les hypothèses saisis. La marge de sécurité, les besoins de liquidités en cours d’année et la recommandation professionnelle restent à déterminer.")
        r.chart(scenarios)
        for name, rows in scenarios:
            r.page()
            r.text(name, 1)
            r.table(["Année", "Ouverture", "Cotisation", "Travaux", "Rendement", "Fermeture"],
                [[row["year"]] + [dollars(row[k]) for k in ("opening", "contribution", "expense", "interest", "closing")] for row in rows])
            r.text("Montants nécessaires en début d’année", 2)
            targets = rf.required_openings(rows, data["interest"])
            total = sum(x["expense"] for x in rows)
            share = sum(x["restricted"] for x in rows) / total if total else 0
            r.table(["Année", "Réserve initiale nécessaire", "Cotisation totale", "Part usage restreint"],
                [[row["year"], dollars(target), dollars(row["contribution"]), dollars(rf.money(row["contribution"] * share))]
                 for row, target in zip(rows, targets)])
            r.text("Les réserves initiales nécessaires sont calculées à rebours pour couvrir les travaux restants, avec les cotisations et le rendement du scénario et un objectif final nul. La part proposée à usage restreint est proportionnelle au total des dépenses futures identifiées à usage restreint dans ce scénario. Cette ventilation de planification doit être validée selon la déclaration de copropriété; elle ne répartit pas les charges entre copropriétaires. La recommandation de l’auteur peut majorer ces seuils pour la liquidité et la marge de sécurité.")
    except (ValueError, KeyError, TypeError) as exc:
        r.text("Calcul financier non produit : " + str(exc))
        r.text("Compléter les données exactes du fonds et chaque fiche de composante depuis le bouton Données Loi 16. Les réponses approximatives au questionnaire ne servent pas de valeurs de calcul.")
    r.page()
    r.text(titles[5], 1)
    r.text("La recommandation finale doit tenir compte de l’ensemble des composantes communes, de la déclaration de copropriété, des budgets, de l’historique des travaux et des hypothèses retenues. Les besoins urgents identifiés lors de l’inspection font l’objet d’un suivi distinct. Les échéances prévisionnelles sont révisées à la lumière des travaux réellement exécutés.")
    r.table(["Validation avant émission", "État"], [[item, "À compléter / confirmer"] for item in [
        "Déclaration de copropriété et limites des responsabilités", "Inventaire exhaustif et accès non obtenus", "Sources des coûts, quantités et durées de vie",
        "Montants recommandés au début de chaque année", "Ventilation des sommes à verser pour les parties à usage restreint", "Indépendance et admissibilité de l’auteur",
        "Déclaration datée d’examen sur place et d’examen des documents", "Révision professionnelle, date et signature de l’étude"]])
    r.text("Auteur prévu : Arash Rohani, ing., P.Eng.\nSignature : ____________________    Date : ____________________")
    r.page()
    r.text(titles[6], 1)
    if not groups:
        r.text("Inventaire à compléter lors de la visite.")
    for index, group in enumerate(groups, 1):
        if index > 1:
            r.page()
        plan = group.get("reserve_plan", {})
        r.text(f"A{index:03d} {group.get('element_type', 'Composante')}", 2)
        r.text(group.get("caption_fr") or "Observation à compléter")
        r.table(["Fiche technique", "Donnée"], [["Localisation", group.get("location", "À préciser")],
            ["Quantité et unité", plan.get("quantity", "À préciser")], ["Année d’installation", plan.get("installed", "À préciser")],
            ["Durée de vie utile", plan.get("useful_life", "À préciser")], ["Vie résiduelle", plan.get("remaining_life", "À préciser")],
            ["État apparent", ", ".join(dict.fromkeys(p.get("status", "À préciser") for p in group.get("photos", []))) or "À préciser"],
            ["Intervention majeure", plan.get("action", "À préciser")], ["Année prévue", plan.get("year", "À préciser")],
            ["Coût de référence", dollars(rf.money(plan["cost"])) if plan.get("cost") is not None else "À préciser"],
            ["Source du coût", plan.get("cost_source", "À préciser")],
            ["Usage restreint", "Oui" if plan.get("restricted") is True else "Non" if plan.get("restricted") is False else "À confirmer"],
            ["Exclusion financière", plan.get("exclusion_reason", "Aucune exclusion consignée")]])
        for j, photo in enumerate(group.get("photos", []), 1):
            r.photo(photo.get("path", ""), f"Photo A{index:03d}-{j} - {group.get('element_type', 'Composante')}", width=3.6)
    r.page()
    r.text(titles[7], 1)
    if scenarios:
        schedule = rf.events(data, groups)
        r.table(["Année", "Composante", "Travaux", "Coût futur", "Usage restreint"],
            [[e["year"], f"A{e['id']:03d} {e['component']}", e["action"], dollars(e["cost"]), "Oui" if e["restricted"] else "Non"] for e in schedule])
    else:
        r.text("Calendrier et coûts futurs à compléter après validation des données de calcul.")
    r.page()
    r.text(titles[8], 1)
    r.text("L’entretien courant relève du budget d’exploitation. Ces tâches sont présentées séparément des réparations majeures financées par le fonds.")
    r.table(["Composante", "Tâche", "Fréquence", "Responsable", "Prochaine date"],
        [[f"A{i:03d} {g.get('element_type', '')}"] + [g.get("reserve_plan", {}).get(k, "À préciser") for k in ("maintenance", "frequency", "responsible", "due_date")] for i, g in enumerate(groups, 1)])
    r.text("Calendrier annuel des interventions", 2)
    r.table(["Mois", "Travaux prévus / références"], [[m, "À compléter selon les échéances des fiches"] for m in
        ("Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre")])
    r.page()
    r.text(titles[9], 1)
    r.text("Le conseil d’administration consigne les travaux exécutés, leur date, leur coût, les contrats et les pièces justificatives. Tout report de travaux requis ou prévus est documenté avec sa raison.")
    r.table(["Date", "ID / travaux", "Coût réel", "Entreprise / pièce", "Report et raison"], [["", "", "", "", ""] for _ in range(8)])
    r.text("Répertoire documentaire", 2)
    r.table(["Document", "Référence / date / emplacement"], [[name, "À consigner"] for name in [
        "Déclaration de copropriété et modifications", "Plans et devis", "États financiers et budget", "Historique des travaux et factures",
        "Contrats d’entretien", "Garanties en vigueur", "Manuels des fabricants", "Rapports d’inspection et expertises", "Études antérieures"]])
    return r.save(path)
