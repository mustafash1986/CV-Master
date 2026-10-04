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

from cv_servant.ai.ats_tailor import ATSTailor
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

        PDFGenerator.generate_resume(tailored_profile, pdf_cv_path)
        WordGenerator.generate_resume(tailored_profile, docx_cv_path)
        WordGenerator.generate_cover_letter(tailored_profile, docx_cl_path)

        # 5. Write Quick-Reference Application Info file for manual form filling
        info_file = folder_path / "application_dossier.txt"
        with open(info_file, "w", encoding="utf-8") as f:
            f.write(f"JOB APPLICATION DOSSIER\n")
            f.write(f"=======================\n")
            f.write(f"Company: {analysis.get('company_name')}\n")
            f.write(f"Title: {analysis.get('job_title')}\n")
            f.write(f"Country: {analysis.get('country')}\n")
            f.write(f"Visa Sponsorship: {analysis.get('visa_sponsorship')} - {analysis.get('sponsorship_notes')}\n")
            f.write(f"Application Email: {analysis.get('application_email')}\n")
            f.write(f"Fit Score: {analysis.get('fit_score')}%\n\n")
            f.write(f"EMAIL SUBJECT:\n{tailored_profile.get('email_subject')}\n\n")
            f.write(f"EMAIL BODY:\n{tailored_profile.get('email_body')}\n\n")
            f.write(f"COVER LETTER:\n{tailored_profile.get('cover_letter')}\n\n")

        # 6. Prepare Job Record and Log to Excel
        job_record = {
            "company_name": analysis.get("company_name"),
            "job_title": analysis.get("job_title"),
            "country": analysis.get("country"),
            "city": analysis.get("city"),
            "application_method": analysis.get("application_method"),
            "application_email": analysis.get("application_email"),
            "visa_sponsorship": analysis.get("visa_sponsorship"),
            "sponsorship_notes": analysis.get("sponsorship_notes"),
            "status": "Pending Approval",
            "folder_path": str(folder_path),
            "pdf_cv_path": str(pdf_cv_path),
            "docx_cl_path": str(docx_cl_path),
            "email_subject": tailored_profile.get("email_subject"),
            "email_body": tailored_profile.get("email_body"),
            "fit_score": analysis.get("fit_score", 90),
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
            email_addr = job.get("application_email") or job.get("contact")
            if not email_addr or "@" not in str(email_addr):
                logger.error("No valid recipient email specified for this job.")
                return False

            folder_path = Path(job.get("folder_path", "")) if job.get("folder_path") else None

            # 1. Resolve attachments: check explicit paths first, then scan job folder
            attachments = []
            if job.get("pdf_cv_path") and Path(job["pdf_cv_path"]).exists():
                attachments.append(Path(job["pdf_cv_path"]))
            if job.get("docx_cl_path") and Path(job["docx_cl_path"]).exists():
                attachments.append(Path(job["docx_cl_path"]))

            if not attachments and folder_path and folder_path.exists():
                for p in folder_path.glob("*.pdf"):
                    attachments.append(p)
                for c in folder_path.glob("Cover_Letter*.docx"):
                    attachments.append(c)

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
                company = job.get("company_name", "Hiring Team")
                country = job.get("country", "")
                loc_str = f" in {country}" if country and country != "N/A" else ""
                body_text = (
                    f"Dear Hiring Team at {company},\n\n"
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
                    f"Please find attached my detailed ATS-optimized Curriculum Vitae and formal Cover Letter for your review. "
                    f"I welcome the opportunity to discuss how my expertise can support your upcoming projects.\n\n"
                    f"Sincerely,\n\n"
                    f"Mustafa Mahmoud Shawky\n"
                    f"Senior Architect & BIM Specialist / BIM Manager\n"
                    f"Mobile: +965 9919 1358\n"
                    f"Email: arch.mustafa.mahmoud.2007@gmail.com\n"
                    f"LinkedIn: linkedin.com/in/mostafamahmoud-architect"
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
                            f"📎 المرفقات: {len(attachments)} ملفات (CV + Cover Letter)"
                        )
                    return True
            except Exception as e:
                logger.error(f"Email dispatch error: {e}")
                return False

        elif action in ["MANUAL_FOLDER", "OPEN_PORTAL"]:
            import webbrowser
            url = job.get("job_url") or job.get("contact", "")
            if url and ("http://" in str(url) or "https://" in str(url)):
                webbrowser.open(url)

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
