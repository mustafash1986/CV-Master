"""
ATS-Compliant PDF generator using ReportLab.
Produces machine-readable, pristine PDFs that pass automated ATS scanners with high fidelity.
"""
from pathlib import Path
from typing import Any, Dict
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem
from cv_servant.master_profile import MASTER_PROFILE


class PDFGenerator:
    @classmethod
    def generate_resume(cls, profile: Dict[str, Any], output_path: Path) -> Path:
        """Generates ATS-optimized PDF document."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            leftMargin=0.55 * inch,
            rightMargin=0.55 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        styles = getSampleStyleSheet()

        # Custom ATS Styles
        style_name = ParagraphStyle(
            "NameStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            alignment=1,  # Center
            textColor=colors.HexColor("#0f1e36"),
        )
        style_title = ParagraphStyle(
            "TitleStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            alignment=1,
            textColor=colors.HexColor("#1b4965"),
        )
        style_contact = ParagraphStyle(
            "ContactStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            alignment=1,
            textColor=colors.HexColor("#4a5568"),
        )
        style_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#0f1e36"),
            spaceBefore=6,
            spaceAfter=2,
        )
        style_body = ParagraphStyle(
            "BodyStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11.5,
            textColor=colors.HexColor("#2d3748"),
        )
        style_job_title = ParagraphStyle(
            "JobTitleStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#0f1e36"),
        )
        style_bullet = ParagraphStyle(
            "BulletStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#2d3748"),
        )

        story = []
        info = profile["personal_info"]

        # Header: Name, Title, Contact
        story.append(Paragraph(info["full_name"], style_name))
        story.append(Spacer(1, 2))
        story.append(Paragraph(profile.get("tailored_title", info["title"]), style_title))
        story.append(Spacer(1, 2))
        contact_line = f"{info['location']} | {info['phone']} | {info['email']} | {info['linkedin']}"
        story.append(Paragraph(contact_line, style_contact))
        story.append(Spacer(1, 6))

        def add_divider():
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#cbd5e0"), spaceBefore=2, spaceAfter=4))

        # Professional Summary
        story.append(Paragraph("PROFESSIONAL SUMMARY", style_heading))
        add_divider()
        summary_text = profile.get("tailored_summary", profile.get("professional_summary", ""))
        story.append(Paragraph(summary_text, style_body))
        story.append(Spacer(1, 4))

        # Core Competencies
        story.append(Paragraph("CORE COMPETENCIES & TECHNICAL SKILLS", style_heading))
        add_divider()
        for cat, items in profile.get("core_competencies", {}).items():
            cat_label = cat.replace("_", " ").title()
            comp_text = f"<b>• {cat_label}:</b> {', '.join(items)}"
            story.append(Paragraph(comp_text, style_bullet))
        story.append(Spacer(1, 4))

        # Professional Experience
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", style_heading))
        add_divider()
        for exp in profile.get("work_experience", []):
            role_header = f"<b>{exp['role']}</b> – {exp['company']}, {exp['location']} ({exp['period']})"
            story.append(Paragraph(role_header, style_job_title))
            for h in exp.get("highlights", []):
                bullet_text = f"• {h}"
                story.append(Paragraph(bullet_text, style_bullet))
            story.append(Spacer(1, 3))

        # Key Projects
        story.append(Paragraph("KEY PROJECT PORTFOLIO", style_heading))
        add_divider()
        for pcat in profile.get("key_projects", []):
            p_text = f"<b>• {pcat['category']}:</b> {'; '.join(pcat['projects'])}"
            story.append(Paragraph(p_text, style_bullet))
        story.append(Spacer(1, 4))

        # Education & Certifications
        story.append(Paragraph("EDUCATION & CERTIFICATIONS", style_heading))
        add_divider()
        for edu in profile.get("education", []):
            e_text = f"<b>• {edu['degree']}</b>, {edu['institution']} ({edu['period']}) - {edu.get('grade', '')}"
            story.append(Paragraph(e_text, style_bullet))
        for lic in profile.get("licenses_and_certifications", []):
            l_text = f"<b>• {lic['name']}</b> – {lic['issuer']} ({lic['details']})"
            story.append(Paragraph(l_text, style_bullet))

        doc.build(story)
        return output_path

    @classmethod
    def generate_cover_letter(cls, profile: Dict[str, Any], output_path: Path) -> Path:
        """Generates pristine, formal Cover Letter PDF."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()

        style_name = ParagraphStyle(
            "CLName",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#0f1e36"),
        )
        style_sub = ParagraphStyle(
            "CLSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#4a5568"),
        )
        style_body = ParagraphStyle(
            "CLBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14.5,
            textColor=colors.HexColor("#2d3748"),
            spaceAfter=10,
        )

        story = []
        info = profile.get("personal_info") or MASTER_PROFILE.get("personal_info", {})

        # Header Letterhead
        story.append(Paragraph(info["full_name"], style_name))
        contact_line = f"{info['title']} | {info['location']} | {info['phone']} | {info['email']}"
        story.append(Paragraph(contact_line, style_sub))
        links_line = f"LinkedIn: {info['linkedin']} | Portfolio: https://mustafash1986.github.io/mustafa-portfolio1/"
        story.append(Paragraph(links_line, style_sub))
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1b4965"), spaceBefore=4, spaceAfter=14))

        # Body paragraphs
        letter_content = profile.get("cover_letter", "")
        for para in letter_content.split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip().replace("\n", "<br/>"), style_body))

        doc.build(story)
        return output_path
