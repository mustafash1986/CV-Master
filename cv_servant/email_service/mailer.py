"""
Gmail Mailer and Response Checker.
Sends tailored application emails with attachments and monitors inbox for replies.
"""
import email
from email.header import decode_header
import imaplib
import logging
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Any, Dict, List, Optional

from cv_servant.config import (
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
    GMAIL_SMTP_SERVER,
    GMAIL_SMTP_PORT,
    GMAIL_IMAP_SERVER,
)

logger = logging.getLogger(__name__)


class GmailService:
    def __init__(self, user: str = GMAIL_USER, app_password: str = GMAIL_APP_PASSWORD):
        self.user = user.strip()
        self.app_password = app_password.replace(" ", "").strip()

    def send_application_email(
        self,
        recipient_email: str,
        subject: str,
        body_text: str,
        attachment_paths: List[Path],
    ) -> bool:
        """
        Sends application email with CV and documents attached.
        """
        if not self.app_password:
            logger.warning("GMAIL_APP_PASSWORD is not set. Email cannot be sent automatically.")
            return False

        msg = MIMEMultipart()
        msg["From"] = f"Mustafa Mahmoud Shawky <{self.user}>"
        msg["To"] = recipient_email
        msg["Subject"] = subject

        # Attach body
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        # Attach files
        for path in attachment_paths:
            path = Path(path)
            if not path.exists():
                continue
            part = MIMEBase("application", "octet-stream")
            with open(path, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{path.name}"',
            )
            msg.attach(part)

        try:
            with smtplib.SMTP_SSL(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT) as server:
                server.login(self.user, self.app_password)
                server.send_message(msg)
            logger.info(f"Application successfully sent to {recipient_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            raise

    def check_inbox_responses(self, tracked_companies: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Checks Gmail inbox for replies from companies applied to.
        Classifies responses into: 'Interview', 'Rejected', or 'Acknowledgement'.
        """
        if not self.app_password:
            return []

        results = []
        try:
            mail = imaplib.IMAP4_SSL(GMAIL_IMAP_SERVER)
            mail.login(self.user, self.app_password)
            mail.select("inbox")

            # Search unseen emails in past 30 days
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK" or not messages[0]:
                mail.close()
                mail.logout()
                return []

            email_ids = messages[0].split()

            for e_id in email_ids[-20:]:  # Check the latest 20 unread emails
                _, msg_data = mail.fetch(e_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        sender = msg.get("From", "")
                        subject, encoding = decode_header(msg.get("Subject", ""))[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors="ignore")

                        # Extract body text
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body = payload.decode("utf-8", errors="ignore")
                                        break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode("utf-8", errors="ignore")

                        lower_content = f"{subject} {body}".lower()

                        # Match against companies
                        for comp in tracked_companies:
                            comp_name = comp.get("company_name", "").lower()
                            if comp_name and comp_name in lower_content:
                                # Determine sentiment
                                status_determined = "Under Review"
                                if any(w in lower_content for w in ["interview", "invitation", "shortlisted", "schedule a time", "مقابلة"]):
                                    status_determined = "Interview"
                                elif any(w in lower_content for w in ["regret", "unfortunately", "not moving forward", "other candidates", "نعتذر"]):
                                    status_determined = "Rejected"

                                results.append({
                                    "job_id": comp.get("job_id"),
                                    "company_name": comp.get("company_name"),
                                    "subject": subject,
                                    "sender": sender,
                                    "detected_status": status_determined,
                                    "snippet": body[:200]
                                })

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Error checking inbox: {e}")

        return results
