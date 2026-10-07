"""
Central Application Coordinator for CV Servant.
Orchestrates OCR, LLM analysis, ATS tailoring, document generation, Excel logging,
Google Drive synchronization, and Mobile/Email dispatch.
"""
from datetime import datetime
import logging
from pathlib import Path
import re
from typing import Any, Dict, Optional

from cv_servant.ai.ats_tailor import ATSTailor, validate_and_sanitize_answer, answer_employer_question
from cv_servant.ai.job_analyzer import JobAnalyzer
from cv_servant.ai.ocr_engine import OCREngine
from cv_servant.ai.ollama_client import OllamaClient
from cv_servant.config import APPLICATIONS_DIR, INBOX_IMAGES_DIR
from cv_servant.documents.pdf_generator import PDFGenerator
from cv_servant.documents.word_generator import WordGenerator
from cv_servant.email_service.mailer import GmailService
from cv_servant.mobile.telegram_agent import TelegramMobileAgent
from cv_servant.tracker.excel_tracker import ExcelTracker
from cv_servant.tracker.gdrive_sync import GDriveSync
from cv_servant.master_profile import MASTER_PROFILE

logger = logging.getLogger(__name__)


class ApplicationCoordinator:
    def __init__(self):
        self.ollama = OllamaClient()
        self.ocr = OCREngine(self.ollama)
        self.analyzer = JobAnalyzer(self.ollama)
        self.tailor = ATSTailor(self.ollama)
        self.tracker = ExcelTracker()
        self.gdrive = GDriveSync()
        self.mailer = GmailService()
        self.telegram = TelegramMobileAgent(
            on_job_received=self.handle_mobile_incoming_job,
            on_approval=self.handle_mobile_approval,
        )
        self.cached_jobs: Dict[str, Dict[str, Any]] = {}

    def sanitize_filename(self, text: str) -> str:
        """Sanitizes strings for safe cross-platform folder and file naming."""
        clean = re.sub(r'[\\/*?:"<>|]', "", text)
        return clean.strip().replace(" ", "_")[:50]

    def process_job_text(self, raw_text: str, source_info: str = "Direct Input") -> Dict[str, Any]:
        """
        Full workflow from raw job description to ready-to-dispatch package.
        """
        logger.info(f"Analyzing job from {source_info}...")

        # 1. Analyze Job Posting
        analysis = self.analyzer.analyze_job(raw_text)

        # 2. Tailor CV, Cover Letter & Email Pitch
        tailored_profile = self.tailor.generate_tailored_package(analysis)

        # 3. Create Dedicated Application Folder
        date_str = datetime.now().strftime("%Y-%m-%d")
        clean_company = self.sanitize_filename(analysis.get("company_name", "Employer"))
        clean_title = self.sanitize_filename(analysis.get("job_title", "BIM_Role"))
        folder_name = f"{date_str}_{clean_company}_{clean_title}"
        folder_path = APPLICATIONS_DIR / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        # 4. Generate ATS Documents
        pdf_cv_path = folder_path / f"Mustafa_Shawky_{clean_title}_ATS.pdf"
        docx_cv_path = folder_path / f"Mustafa_Shawky_{clean_title}_ATS.docx"
        docx_cl_path = folder_path / f"Cover_Letter_{clean_company}.docx"
        pdf_cl_path = folder_path / f"Cover_Letter_{clean_company}.pdf"

        PDFGenerator.generate_resume(tailored_profile, pdf_cv_path)
        PDFGenerator.generate_cover_letter(tailored_profile, pdf_cl_path)
        WordGenerator.generate_resume(tailored_profile, docx_cv_path)
        WordGenerator.generate_cover_letter(tailored_profile, docx_cl_path)

        # 5. Write Quick-Reference Application Info file for manual form filling
        info_file = folder_path / "application_dossier.txt"
        with open(info_file, "w", encoding="utf-8") as f:
            f.write(f"JOB APPLICATION DOSSIER\n")
            f.write(f"=======================\n")
            f.write(f"Company: {analysis.get('company_name')}\n")
            f.write(f"Contact Person: {analysis.get('contact_person', '')}\n")
            f.write(f"Contact Phone: {analysis.get('contact_phone', '')}\n")
            f.write(f"Title: {analysis.get('job_title')}\n")
            f.write(f"Country: {analysis.get('country')}\n")
            f.write(f"City: {analysis.get('city', '')}\n")
            f.write(f"Salary Range: {analysis.get('salary_range', 'Not Disclosed')}\n")
            f.write(f"Visa Sponsorship: {analysis.get('visa_sponsorship')} - {analysis.get('sponsorship_notes')}\n")
            f.write(f"Application Email: {analysis.get('application_email')}\n")
            f.write(f"Job URL: {analysis.get('job_url', '')}\n")
            f.write(f"Portfolio Website: https://mustafash1986.github.io/mustafa-portfolio1/\n")
            fwrite_score = analysis.get('fit_score', 90)
            fwrite_verdict = analysis.get('fit_verdict', 'Strong Fit')
            f.write(f"Fit Score: {fwrite_score}% ({fwrite_verdict})\n")
            f.write(f"Fit Rationale: {analysis.get('fit_rationale', '')}\n\n")

            # 5-Dimension Evaluation Matrix (ai-job-search framework)
            gate = analysis.get('eligibility_gate', {})
            dims = analysis.get('dimensions', {})
            f.write(f"5-DIMENSION EVALUATION MATRIX:\n")
            f.write(f"=============================\n")
            f.write(f"Eligibility Gate: [{gate.get('verdict', 'UNVERIFIED')}] - {gate.get('notes', '')}\n")
            f.write(f"• Technical Match (30%):   {dims.get('technical_score', 85)}/100 - {dims.get('technical_notes', '')}\n")
            f.write(f"• Experience Match (25%):  {dims.get('experience_score', 85)}/100 - {dims.get('experience_notes', '')}\n")
            f.write(f"• Behavioral Match (15%):  {dims.get('behavioral_score', 80)}/100 - {dims.get('behavioral_notes', '')}\n")
            f.write(f"• Location & Logistics:    {dims.get('location_verdict', 'PASS')} - {dims.get('location_notes', '')}\n")
            f.write(f"• Career Alignment (30%):  {dims.get('career_score', 85)}/100 - {dims.get('career_notes', '')}\n\n")

            recom = analysis.get('recommendation', '')
            if recom:
                f.write(f"Recommendation: {recom}\n\n")

            strengths = analysis.get('key_strengths', [])
            if strengths:
                f.write(f"Key Candidate Strengths:\n")
                for s in strengths:
                    f.write(f"  + {s}\n")
                f.write(f"\n")

            gaps = analysis.get('gaps_to_address', [])
            if gaps:
                f.write(f"Gaps to Address / Strategy:\n")
                for g in gaps:
                    f.write(f"  - {g}\n")
                f.write(f"\n")

            # Key Requirements extracted from the job posting
            key_reqs = analysis.get('key_requirements', [])
            if key_reqs:
                f.write(f"KEY REQUIREMENTS (from Job Posting):\n")
                for req in key_reqs:
                    f.write(f"  • {req}\n")
                f.write(f"\n")

            # Employer Questions & Answers
            eq_responses = tailored_profile.get('employer_question_responses', [])
            if eq_responses:
                f.write(f"EMPLOYER QUESTIONS & ANSWERS:\n")
                f.write(f"=============================\n")
                for eq in eq_responses:
                    if isinstance(eq, dict):
                        f.write(f"Q: {eq.get('question', '')}\n")
                        f.write(f"A: {eq.get('answer', '')}\n\n")
                    elif isinstance(eq, str):
                        f.write(f"• {eq}\n")
                f.write(f"\n")

            f.write(f"EMAIL SUBJECT:\n{tailored_profile.get('email_subject')}\n\n")
            f.write(f"EMAIL BODY:\n{tailored_profile.get('email_body')}\n\n")
            f.write(f"COVER LETTER:\n{tailored_profile.get('cover_letter')}\n\n")

        # 6. Prepare Job Record and Log to Excel
        job_url_val = analysis.get("job_url", "")
        job_record = {
            "company_name": analysis.get("company_name"),
            "contact_person": analysis.get("contact_person", ""),
            "contact_phone": analysis.get("contact_phone", ""),
            "job_title": analysis.get("job_title"),
            "country": analysis.get("country"),
            "city": analysis.get("city"),
            "application_method": analysis.get("application_method"),
            "application_email": analysis.get("application_email") or job_url_val,
            "job_url": job_url_val,
            "visa_sponsorship": analysis.get("visa_sponsorship"),
            "sponsorship_notes": analysis.get("sponsorship_notes"),
            "eligibility_gate": analysis.get("eligibility_gate", {}),
            "dimensions": analysis.get("dimensions", {}),
            "fit_score": analysis.get("fit_score", 90),
            "fit_verdict": analysis.get("fit_verdict", "Strong Fit"),
            "key_strengths": analysis.get("key_strengths", []),
            "gaps_to_address": analysis.get("gaps_to_address", []),
            "recommendation": analysis.get("recommendation", ""),
            "status": "Pending Approval",
            "folder_path": str(folder_path),
            "pdf_cv_path": str(pdf_cv_path),
            "pdf_cl_path": str(pdf_cl_path),
            "docx_cv_path": str(docx_cv_path),
            "docx_cl_path": str(docx_cl_path),
            "cover_letter": tailored_profile.get("cover_letter"),
            "email_subject": tailored_profile.get("email_subject"),
            "email_body": tailored_profile.get("email_body"),
            "employer_question_responses": tailored_profile.get("employer_question_responses", []),
        }

        job_id = self.tracker.add_job(job_record)
        job_record["job_id"] = job_id
        self.cached_jobs[job_id] = job_record

        # 7. Backup to Google Drive
        self.gdrive.sync_tracker_to_drive()
        self.gdrive.backup_application_package(folder_path)

        # 8. Notify Mobile via Telegram if enabled
        if self.telegram.is_configured():
            self.telegram.send_approval_request(job_record, pdf_cv_path)

        return job_record

    def process_image_ad(self, image_path: Path) -> Dict[str, Any]:
        """Process a job advertisement image (flyer / screenshot)."""
        logger.info(f"Extracting text from flyer: {image_path.name}")
        ocr_res = self.ocr.process_image(image_path)
        combined_text = ocr_res["combined_raw"]

        if not combined_text.strip():
            logger.warning(f"No text extracted from {image_path.name}")
            return {}

        result = self.process_job_text(combined_text, source_info=f"Image Ad: {image_path.name}")
        self.gdrive.archive_processed_image(image_path)
        return result

    def handle_mobile_incoming_job(self, data: Dict[str, Any]):
        """Handler for jobs received from smartphone via Telegram."""
        if data["type"] == "text":
            self.process_job_text(data["content"], source_info="Mobile Telegram Text")
        elif data["type"] == "image_bytes":
            temp_path = INBOX_IMAGES_DIR / data.get("filename", "mobile_ad.jpg")
            with open(temp_path, "wb") as f:
                f.write(data["content"])
            self.process_image_ad(temp_path)

    def handle_mobile_approval(self, job_id: str, action: str):
        """Handler for 1-click approval button clicks from smartphone."""
        self.execute_action(job_id, action)

    def execute_action(self, job_id: str, action: str) -> bool:
        """Executes the approved action for a job (Send Email, Manual, Decline)."""
        job = self.cached_jobs.get(job_id)
        if not job:
            # Try to lookup from all jobs
            for j in self.tracker.get_all_jobs():
                if j.get("job_id") == job_id:
                    job = j
                    break

        if not job:
            logger.error(f"Job ID {job_id} not found.")
            return False

        if action == "SEND_EMAIL":
            raw_email = str(job.get("application_email") or job.get("contact") or "")
            email_addr = raw_email.strip().strip(".,;:<>\"'()[]{} \t\r\n")
            if not email_addr or "@" not in email_addr:
                logger.error("No valid recipient email specified for this job.")
                self.last_error = f"عنوان البريد الإلكتروني غير صالح: '{raw_email}'"
                return False

            folder_path = Path(job.get("folder_path", "")) if job.get("folder_path") else None

            # 1. Resolve attachments: PDF CV + PDF Cover Letter + Portfolio PDF
            attachments = []
            if job.get("pdf_cv_path") and Path(job["pdf_cv_path"]).exists():
                attachments.append(Path(job["pdf_cv_path"]))
            if job.get("pdf_cl_path") and Path(job["pdf_cl_path"]).exists():
                attachments.append(Path(job["pdf_cl_path"]))
            elif job.get("docx_cl_path") and Path(job["docx_cl_path"]).exists():
                attachments.append(Path(job["docx_cl_path"]))

            if not attachments and folder_path and folder_path.exists():
                for p in folder_path.glob("*.pdf"):
                    attachments.append(p)
                for c in folder_path.glob("Cover_Letter*.docx"):
                    if not any("Cover_Letter" in str(x) for x in attachments):
                        attachments.append(c)

            # Attach Email-Ready Portfolio PDF (5.3 MB)
            from cv_servant.config import DATA_DIR
            portfolio_pdf = DATA_DIR / "portfolio" / "Mustafa_Mahmoud_Portfolio_Email_Ready.pdf"
            if portfolio_pdf.exists() and portfolio_pdf not in attachments:
                attachments.append(portfolio_pdf)

            # 2. Resolve rich Email Body: check memory, then dossier file, then rich template
            body_text = job.get("email_body", "")
            if (not body_text or len(body_text.strip()) < 50) and folder_path and folder_path.exists():
                dossier_path = folder_path / "application_dossier.txt"
                if dossier_path.exists():
                    try:
                        with open(dossier_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            if "EMAIL BODY:" in content and "COVER LETTER:" in content:
                                extracted = content.split("EMAIL BODY:")[1].split("COVER LETTER:")[0].strip()
                                if extracted:
                                    body_text = extracted
                    except Exception as e:
                        logger.warning(f"Could not read dossier: {e}")

            # 3. If still empty, build high-impact executive summary from Master Profile
            if not body_text or len(body_text.strip()) < 50:
                title = job.get("job_title", "Senior Architect & BIM Specialist")
                raw_company = (job.get("company_name") or "").strip()
                contact = (job.get("contact_person") or "").strip()
                country = job.get("country", "")
                loc_str = f" in {country}" if country and country != "N/A" else ""

                company = raw_company
                if company.lower() in [
                    "confidential", "confidential / not disclosed", "not disclosed",
                    "target employer", "prospective employer", "unknown", "hiring team"
                ]:
                    company = ""

                if contact:
                    salutation = f"Dear {contact},"
                elif company:
                    salutation = f"Dear {company} Hiring Team,"
                else:
                    salutation = "Dear Hiring Manager,"

                body_text = (
                    f"{salutation}\n\n"
                    f"I am writing to formally submit my application for the {title} position{loc_str}.\n\n"
                    f"With over 19 years of distinguished architectural engineering and BIM management experience, "
                    f"I specialize in Revit modeling, inter-discipline clash detection (Navisworks), and custom workflow automation "
                    f"using Dynamo and Python. My portfolio spans major institutional, healthcare, and commercial landmark projects, "
                    f"including the Kuwait University Health Sciences Center (KUHSC) and the Dubai Iconic Tower.\n\n"
                    f"Key Highlights of my qualifications:\n"
                    f"• 19+ Years of multidisciplinary architectural leadership across Kuwait and the Gulf region\n"
                    f"• PMP® Certified Project Manager (PMI #3010938)\n"
                    f"• Autodesk Certified Professional in Revit Architecture (#00424122)\n"
                    f"• Registered Professional Architect (KSE & Egyptian Syndicate) and BEFA eligible\n"
                    f"• Developed 19+ custom Revit plugins slashing task completion times by up to 80%\n\n"
                    f"Please find attached my detailed ATS-optimized Curriculum Vitae, formal Cover Letter, and Project Portfolio for your review. "
                    f"I welcome the opportunity to discuss how my expertise can support your upcoming projects.\n\n"
                    f"🌐 Interactive Online Portfolio: https://mustafash1986.github.io/mustafa-portfolio1/\n\n"
                    f"Sincerely,\n\n"
                    f"Mustafa Mahmoud Shawky\n"
                    f"Senior Architect & BIM Specialist / BIM Manager\n"
                    f"Mobile: +965 9919 1358\n"
                    f"Email: arch.mustafa.mahmoud.2007@gmail.com\n"
                    f"LinkedIn: linkedin.com/in/mostafamahmoud-architect"
                )

            # Absolute safety: ensure Cover Letter is never leaked into email text (it is already an attached PDF)
            if "COVER LETTER:" in body_text:
                body_text = body_text.split("COVER LETTER:")[0].strip()
            if "--------------------------------------------------" in body_text:
                body_text = body_text.split("--------------------------------------------------")[0].strip()

            # Sanitize any legacy bad greetings in body_text
            for bad_sal in [
                "Dear Hiring Team at Confidential", "Dear Hiring Team at Not Disclosed",
                "Dear Hiring Team at Prospective Employer", "Dear Hiring Team at Confidential / Not Disclosed"
            ]:
                if bad_sal in body_text:
                    contact = (job.get("contact_person") or "").strip()
                    comp = (job.get("company_name") or "").strip()
                    if comp.lower() in ["confidential", "confidential / not disclosed", "not disclosed", "target employer", "prospective employer", "unknown"]:
                        comp = ""
                    clean_greeting = f"Dear {contact}," if contact else (f"Dear {comp} Hiring Team," if comp else "Dear Hiring Manager,")
                    body_text = body_text.replace(bad_sal, clean_greeting)

            # Ensure portfolio link is included if body was generated by LLM
            portfolio_link = "🌐 Interactive Online Portfolio: https://mustafash1986.github.io/mustafa-portfolio1/"
            if "mustafa-portfolio1" not in body_text:
                if "Sincerely," in body_text:
                    body_text = body_text.replace("Sincerely,", f"{portfolio_link}\n\nSincerely,")
                elif "Best regards," in body_text:
                    body_text = body_text.replace("Best regards,", f"{portfolio_link}\n\nBest regards,")
                else:
                    body_text += f"\n\n{portfolio_link}"

            # Ensure employer questions & answers are sanitized and included in body_text
            country = job.get("country", "Australia")
            raw_eq_list = job.get("employer_question_responses", [])
            sanitized_eq = []
            for item in raw_eq_list:
                if isinstance(item, dict):
                    q = item.get("question", "")
                    a = item.get("answer", "")
                    sanitized_eq.append({
                        "question": q,
                        "answer": validate_and_sanitize_answer(q, a, country)
                    })
                elif isinstance(item, str):
                    sanitized_eq.append({
                        "question": item,
                        "answer": answer_employer_question(item, country)
                    })
            eq_list = sanitized_eq
            job["employer_question_responses"] = eq_list

            if eq_list:
                eq_block = "\n\n" + "=" * 48 + "\nEMPLOYER SCREENING QUESTIONS & RESPONSES:\n" + "=" * 48 + "\n"
                for item in eq_list:
                    eq_block += f"\nQ: {item.get('question', '')}\nA: {item.get('answer', '')}\n"

                # Check if body_text has old/bad screening question block or if missing
                has_bad_eq = False
                if "EMPLOYER SCREENING QUESTIONS" in body_text:
                    if re.search(r"Security Clearance\??\s*\n\s*A:\s*Yes", body_text, re.IGNORECASE) or \
                       re.search(r"notice.*?\??\s*\n\s*A:\s*Yes,\s*with over 19 years", body_text, re.IGNORECASE) or \
                       "fully meeting and exceeding this requirement" in body_text:
                        has_bad_eq = True
                        body_text = re.sub(
                            r"={30,}\s*\n\s*EMPLOYER SCREENING QUESTIONS & RESPONSES:.*?(?=\n\n(?:Attached|Please find|Best regards|Sincerely|🌐)|\Z)",
                            "",
                            body_text,
                            flags=re.DOTALL
                        ).strip()

                if "EMPLOYER SCREENING QUESTIONS" not in body_text or has_bad_eq:
                    if "Attached you will find" in body_text:
                        body_text = body_text.replace("Attached you will find", f"{eq_block}\nAttached you will find")
                    elif "Please find attached" in body_text:
                        body_text = body_text.replace("Please find attached", f"{eq_block}\nPlease find attached")
                    elif "Best regards," in body_text:
                        body_text = body_text.replace("Best regards,", f"{eq_block}\nBest regards,")
                    elif "Sincerely," in body_text:
                        body_text = body_text.replace("Sincerely,", f"{eq_block}\nSincerely,")
                    else:
                        body_text += f"\n{eq_block}"
            else:
                # When no employer questions exist, strictly ensure no screening question block appears
                if "EMPLOYER SCREENING QUESTIONS" in body_text:
                    body_text = re.sub(
                        r"={30,}\s*\n\s*EMPLOYER SCREENING QUESTIONS & RESPONSES:.*?(?=\n\n(?:Attached|Please find|Best regards|Sincerely|🌐)|\Z)",
                        "",
                        body_text,
                        flags=re.DOTALL
                    ).strip()

            # Ensure complete sign-off in body_text
            if "Mustafa Mahmoud Shawky" not in body_text:
                portfolio_str = "🌐 Interactive Online Portfolio: https://mustafash1986.github.io/mustafa-portfolio1/\n\n" if "mustafash1986" not in body_text else ""
                body_text += (
                    f"\n\n{portfolio_str}"
                    "Best regards,\n"
                    "Mustafa Mahmoud Shawky\n"
                    "Senior Architect & BIM Specialist / Manager\n"
                    "+965 9919 1358\n"
                    "arch.mustafa.mahmoud.2007@gmail.com\n"
                    "linkedin.com/in/mostafamahmoud-architect"
                )

            # Send Email via Gmail
            try:
                subject = job.get("email_subject") or f"Application: {job.get('job_title', 'Senior Architect / BIM Specialist')} - Mustafa Mahmoud Shawky, PMP"
                success = self.mailer.send_application_email(
                    recipient_email=email_addr,
                    subject=subject,
                    body_text=body_text,
                    attachment_paths=attachments,
                )
                if success:
                    self.tracker.update_job_status(job_id, "Applied / Sent")
                    self.gdrive.sync_tracker_to_drive()
                    if self.telegram.is_configured():
                        self.telegram.send_message(
                            f"🎉 <b>تم إرسال التقديم بنجاح!</b>\n"
                            f"🏢 {job.get('company_name')}\n"
                            f"✉️ إلى: {email_addr}\n"
                            f"📎 المرفقات: {len(attachments)} ملفات (CV + Cover Letter + Portfolio)\n"
                            f"🌐 البورتفوليو أونلاين: https://mustafash1986.github.io/mustafa-portfolio1/"
                        )
                    return True
            except Exception as e:
                logger.error(f"Email dispatch error: {e}")
                self.last_error = str(e)
                return False

        elif action in ["MANUAL_FOLDER", "OPEN_PORTAL"]:
            import webbrowser
            import urllib.parse
            url = job.get("job_url") or job.get("contact", "")
            if not url or not ("http://" in str(url) or "https://" in str(url)):
                comp = job.get("company_name", "")
                tit = job.get("job_title", "")
                cntry = job.get("country", "")
                query = urllib.parse.quote(f"{comp} {tit} {cntry} careers apply")
                url = f"https://www.google.com/search?q={query}"

            try:
                webbrowser.open(url)
            except Exception as e:
                logger.warning(f"Could not open browser URL: {e}")

            folder_path = job.get("folder_path")
            if folder_path and Path(folder_path).exists():
                import os
                os.startfile(str(folder_path))

            self.tracker.update_job_status(job_id, "Opened Form / In Progress")
            self.gdrive.sync_tracker_to_drive()
            return True

        elif action == "REJECT":
            self.tracker.update_job_status(job_id, "Declined / Ignored")
            self.gdrive.sync_tracker_to_drive()
            return True

        return False

    def refine_job_package(self, job_data: Dict[str, Any], user_instruction: str) -> Dict[str, Any]:
        """Refines cover letter, email body, updates files and regenerates PDF."""
        current_cl = job_data.get("cover_letter", "")
        current_eb = job_data.get("email_body", "")
        current_sub = job_data.get("email_subject", "")

        refined = self.tailor.refine_cover_letter_and_email(
            job_data=job_data,
            current_cover_letter=current_cl,
            current_email_body=current_eb,
            current_email_subject=current_sub,
            user_instruction=user_instruction,
        )

        job_data["cover_letter"] = refined.get("cover_letter", current_cl)
        job_data["email_body"] = refined.get("email_body", current_eb)
        job_data["email_subject"] = refined.get("email_subject", current_sub)

        job_id = job_data.get("job_id")
        if job_id and job_id in self.cached_jobs:
            self.cached_jobs[job_id]["cover_letter"] = job_data["cover_letter"]
            self.cached_jobs[job_id]["email_body"] = job_data["email_body"]
            self.cached_jobs[job_id]["email_subject"] = job_data["email_subject"]

        # Update saved files in job folder if folder exists
        folder_path_str = job_data.get("folder_path")
        if folder_path_str:
            folder_path = Path(folder_path_str)
            if folder_path.exists():
                clean_company = self.sanitize_filename(job_data.get("company_name", "Employer"))
                pdf_cl_path = Path(job_data.get("pdf_cl_path") or (folder_path / f"Cover_Letter_{clean_company}.pdf"))
                docx_cl_path = Path(job_data.get("docx_cl_path") or (folder_path / f"Cover_Letter_{clean_company}.docx"))
                job_data["pdf_cl_path"] = str(pdf_cl_path)
                job_data["docx_cl_path"] = str(docx_cl_path)

                render_profile = dict(MASTER_PROFILE)
                render_profile.update(job_data)
                render_profile["cover_letter"] = job_data.get("cover_letter", "")

                try:
                    PDFGenerator.generate_cover_letter(render_profile, pdf_cl_path)
                    WordGenerator.generate_cover_letter(render_profile, docx_cl_path)
                    logger.info(f"Successfully regenerated Cover Letter PDF: {pdf_cl_path}")
                except PermissionError:
                    raise PermissionError(f"الملف {pdf_cl_path.name} مفتوح حالياً في برنامج آخر (مثل Adobe Acrobat أو Word). يرجى إغلاقه أولاً حتى يتمكن البرنامج من تحديثه.")
                except Exception as e:
                    logger.error(f"Failed to regenerate cover letter documents: {e}")
                    raise

                # Update dossier file
                info_file = folder_path / "application_dossier.txt"
                if info_file.exists():
                    try:
                        content = info_file.read_text(encoding="utf-8")
                        if "EMAIL SUBJECT:" in content:
                            prefix = content.split("EMAIL SUBJECT:")[0]
                            new_content = (
                                f"{prefix}"
                                f"EMAIL SUBJECT:\n{job_data.get('email_subject')}\n\n"
                                f"EMAIL BODY:\n{job_data.get('email_body')}\n\n"
                                f"COVER LETTER:\n{job_data.get('cover_letter')}\n\n"
                            )
                            info_file.write_text(new_content, encoding="utf-8")
                    except Exception as e:
                        logger.warning(f"Failed to update dossier file: {e}")

        return job_data

    def update_job_texts_manually(self, job_data: Dict[str, Any], new_subject: str, new_email_body: str, new_cover_letter: Optional[str] = None) -> Dict[str, Any]:
        """Saves user manual edits to email and cover letter, regenerating documents."""
        # Ensure Cover Letter is never accidentally stored inside email_body
        if "COVER LETTER:" in new_email_body:
            new_email_body = new_email_body.split("COVER LETTER:")[0].replace("--------------------------------------------------", "").strip()
        elif "--------------------------------------------------" in new_email_body:
            new_email_body = new_email_body.split("--------------------------------------------------")[0].strip()

        job_data["email_subject"] = new_subject
        job_data["email_body"] = new_email_body
        if new_cover_letter:
            job_data["cover_letter"] = new_cover_letter

        job_id = job_data.get("job_id")
        if job_id and job_id in self.cached_jobs:
            self.cached_jobs[job_id]["email_subject"] = new_subject
            self.cached_jobs[job_id]["email_body"] = new_email_body
            if new_cover_letter:
                self.cached_jobs[job_id]["cover_letter"] = new_cover_letter

        folder_path_str = job_data.get("folder_path")
        if folder_path_str:
            folder_path = Path(folder_path_str)
            if folder_path.exists():
                clean_company = self.sanitize_filename(job_data.get("company_name", "Employer"))
                pdf_cl_path = Path(job_data.get("pdf_cl_path") or (folder_path / f"Cover_Letter_{clean_company}.pdf"))
                docx_cl_path = Path(job_data.get("docx_cl_path") or (folder_path / f"Cover_Letter_{clean_company}.docx"))
                job_data["pdf_cl_path"] = str(pdf_cl_path)
                job_data["docx_cl_path"] = str(docx_cl_path)

                render_profile = dict(MASTER_PROFILE)
                render_profile.update(job_data)
                render_profile["cover_letter"] = job_data.get("cover_letter", "")

                try:
                    PDFGenerator.generate_cover_letter(render_profile, pdf_cl_path)
                    WordGenerator.generate_cover_letter(render_profile, docx_cl_path)
                    logger.info(f"Successfully updated Cover Letter PDF: {pdf_cl_path}")
                except PermissionError:
                    raise PermissionError(f"الملف {pdf_cl_path.name} مفتوح حالياً في برنامج آخر (مثل Adobe Acrobat أو Word). يرجى إغلاقه أولاً حتى يتمكن البرنامج من تحديثه.")
                except Exception as e:
                    logger.error(f"Failed to regenerate cover letter documents: {e}")
                    raise

                info_file = folder_path / "application_dossier.txt"
                if info_file.exists():
                    try:
                        content = info_file.read_text(encoding="utf-8")
                        if "EMAIL SUBJECT:" in content:
                            prefix = content.split("EMAIL SUBJECT:")[0]
                            new_content = (
                                f"{prefix}"
                                f"EMAIL SUBJECT:\n{job_data.get('email_subject')}\n\n"
                                f"EMAIL BODY:\n{job_data.get('email_body')}\n\n"
                                f"COVER LETTER:\n{job_data.get('cover_letter', '')}\n\n"
                            )
                            info_file.write_text(new_content, encoding="utf-8")
                    except Exception as e:
                        logger.warning(f"Failed to update dossier file: {e}")

        return job_data
