"""
ATS-Compliant Microsoft Word (.docx) document generator.
Creates clean, parser-friendly resumes and cover letters.
"""
from pathlib import Path
from typing import Any, Dict
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


class WordGenerator:
    @staticmethod
    def _set_paragraph_format(p, space_after=4, space_before=0, line_spacing=1.15):
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.line_spacing = line_spacing

    @classmethod
    def generate_resume(cls, profile: Dict[str, Any], output_path: Path) -> Path:
        """Generates ATS-optimized Word document for the tailored CV."""
        doc = Document()

        # Margins: 0.6 inch
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(0.6)
            section.bottom_margin = Inches(0.6)
            section.left_margin = Inches(0.65)
            section.right_margin = Inches(0.65)

        info = profile["personal_info"]

        # Candidate Name
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cls._set_paragraph_format(p_name, space_after=2)
        run_name = p_name.add_run(info["full_name"])
        run_name.bold = True
        run_name.font.size = Pt(18)
        run_name.font.name = "Calibri"
        run_name.font.color.rgb = RGBColor(15, 30, 54)

        # Title
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cls._set_paragraph_format(p_title, space_after=3)
        run_title = p_title.add_run(profile.get("tailored_title", info["title"]))
        run_title.bold = True
        run_title.font.size = Pt(12)
        run_title.font.name = "Calibri"
        run_title.font.color.rgb = RGBColor(41, 128, 185)

        # Contact Info
        p_contact = doc.add_paragraph()
        p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cls._set_paragraph_format(p_contact, space_after=12)
        contact_text = f"{info['location']} | {info['phone']} | {info['email']} | {info['linkedin']}"
        run_contact = p_contact.add_run(contact_text)
        run_contact.font.size = Pt(9.5)
        run_contact.font.name = "Calibri"
        run_contact.font.color.rgb = RGBColor(80, 80, 80)

        # Helper for Section Headers
        def add_section_heading(title: str):
            p_head = doc.add_paragraph()
            cls._set_paragraph_format(p_head, space_before=8, space_after=4)
            run = p_head.add_run(title.upper())
            run.bold = True
            run.font.size = Pt(11)
            run.font.name = "Calibri"
            run.font.color.rgb = RGBColor(15, 30, 54)

        # Professional Summary
        add_section_heading("Professional Summary")
        p_sum = doc.add_paragraph()
        cls._set_paragraph_format(p_sum, space_after=8)
        run_sum = p_sum.add_run(profile.get("tailored_summary", profile.get("professional_summary", "")))
        run_sum.font.size = Pt(10)
        run_sum.font.name = "Calibri"

        # Core Competencies & Skills
        add_section_heading("Core Competencies & Technical Skills")
        for category, items in profile.get("core_competencies", {}).items():
            cat_name = category.replace("_", " ").title()
            p_skill = doc.add_paragraph(style='List Bullet')
            cls._set_paragraph_format(p_skill, space_after=2)
            r_cat = p_skill.add_run(f"{cat_name}: ")
            r_cat.bold = True
            r_cat.font.size = Pt(9.5)
            r_cat.font.name = "Calibri"
            r_items = p_skill.add_run(", ".join(items))
            r_items.font.size = Pt(9.5)
            r_items.font.name = "Calibri"

        # Professional Experience
        add_section_heading("Professional Experience")
        for exp in profile.get("work_experience", []):
            p_exp_header = doc.add_paragraph()
            cls._set_paragraph_format(p_exp_header, space_before=4, space_after=2)
            r_role = p_exp_header.add_run(exp["role"])
            r_role.bold = True
            r_role.font.size = Pt(10.5)
            r_role.font.name = "Calibri"

            r_comp = p_exp_header.add_run(f" | {exp['company']}, {exp['location']} ({exp['period']})")
            r_comp.font.size = Pt(10)
            r_comp.font.name = "Calibri"
            r_comp.font.color.rgb = RGBColor(60, 60, 60)

            for bullet in exp.get("highlights", []):
                p_bullet = doc.add_paragraph(style='List Bullet')
                cls._set_paragraph_format(p_bullet, space_after=2)
                r_b = p_bullet.add_run(bullet)
                r_b.font.size = Pt(9.5)
                r_b.font.name = "Calibri"

        # Key Projects Portfolio
        add_section_heading("Key Project Portfolio")
        for proj_cat in profile.get("key_projects", []):
            p_cat = doc.add_paragraph(style='List Bullet')
            cls._set_paragraph_format(p_cat, space_after=2)
            r_c = p_cat.add_run(f"{proj_cat['category']}: ")
            r_c.bold = True
            r_c.font.size = Pt(9.5)
            r_c.font.name = "Calibri"
            r_projs = p_cat.add_run("; ".join(proj_cat["projects"]))
            r_projs.font.size = Pt(9.5)
            r_projs.font.name = "Calibri"

        # Education
        add_section_heading("Education")
        for edu in profile.get("education", []):
            p_edu = doc.add_paragraph()
            cls._set_paragraph_format(p_edu, space_after=2)
            r_deg = p_edu.add_run(f"{edu['degree']} | {edu['institution']} ({edu['period']})")
            r_deg.bold = True
            r_deg.font.size = Pt(10)
            r_deg.font.name = "Calibri"
            if "grade" in edu:
                p_g = doc.add_paragraph(style='List Bullet')
                cls._set_paragraph_format(p_g, space_after=2)
                rg = p_g.add_run(edu["grade"])
                rg.font.size = Pt(9.5)
                rg.font.name = "Calibri"

        # Licenses & Certifications
        add_section_heading("Licenses & Certifications")
        for lic in profile.get("licenses_and_certifications", []):
            p_lic = doc.add_paragraph(style='List Bullet')
            cls._set_paragraph_format(p_lic, space_after=2)
            rl_n = p_lic.add_run(f"{lic['name']} – ")
            rl_n.bold = True
            rl_n.font.size = Pt(9.5)
            rl_n.font.name = "Calibri"
            rl_d = p_lic.add_run(f"{lic['issuer']} ({lic['details']})")
            rl_d.font.size = Pt(9.5)
            rl_d.font.name = "Calibri"

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path

    @classmethod
    def generate_cover_letter(cls, profile: Dict[str, Any], output_path: Path) -> Path:
        """Generates Word document for the tailored cover letter."""
        doc = Document()
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)

        info = profile["personal_info"]

        # Sender Info
        p_head = doc.add_paragraph()
        cls._set_paragraph_format(p_head, space_after=2)
        r_name = p_head.add_run(info["full_name"])
        r_name.bold = True
        r_name.font.size = Pt(14)
        r_name.font.name = "Calibri"

        p_con = doc.add_paragraph()
        cls._set_paragraph_format(p_con, space_after=20)
        r_c = p_con.add_run(f"{info['title']} | {info['email']} | {info['phone']}")
        r_c.font.size = Pt(10)
        r_c.font.color.rgb = RGBColor(90, 90, 90)

        # Body
        letter_content = profile.get("cover_letter", "")
        for para in letter_content.split("\n\n"):
            if para.strip():
                p = doc.add_paragraph()
                cls._set_paragraph_format(p, space_after=10, line_spacing=1.2)
                r = p.add_run(para.strip())
                r.font.size = Pt(11)
                r.font.name = "Calibri"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path
