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
import re
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
        """Sends application email with CV and documents attached."""
        recipient_email = (recipient_email or "").strip().strip(".,;:<>\"'()[]{} \t\r\n")
        if not self.app_password:
            logger.warning("GMAIL_APP_PASSWORD is not set. Email cannot be sent automatically.")
            return False

        if not recipient_email or "@" not in recipient_email:
            logger.error(f"Invalid recipient email: {recipient_email}")
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
        Checks both unread and recent emails (to catch replies even if already opened in browser/mobile).
        Classifies responses into: 'Interview', 'Rejected', or 'Under Review'.
        """
        if not self.app_password:
            return []

        GENERIC_NAMES = {
            "hiring team", "multiple canadian employers", "confidential", 
            "employer", "recruitment team", "talent team", "hr team", "career team"
        }

        CONDITIONAL_PATTERNS = [
            r"if\s+(?:you\s+are\s+)?(?:selected|shortlisted|successful|appropriate)",
            r"if\s+appropriate[,\s]+(?:we\s+will\s+)?schedule",
            r"what\s+happens\s+next",
            r"next\s+steps?\s*:",
            r"our\s+(?:hiring\s+)?process\s*:",
            r"(?:may|might)\s+(?:be\s+invited|contact\s+you|schedule)",
            r"will\s+contact\s+you\s+if",
            r"while\s+you(?:’|')?re\s+waiting",
            r"waiting\s+to\s+hear\s+back",
        ]

        DEFINITIVE_INTERVIEW_PHRASES = [
            "would like to invite you to an interview",
            "would like to invite you for an interview",
            "pleased to invite you to an interview",
            "pleased to invite you for an interview",
            "delighted to invite you to an interview",
            "delighted to invite you for an interview",
            "happy to invite you to an interview",
            "happy to invite you for an interview",
            "invite you to an interview",
            "invite you for an interview",
            "inviting you to an interview",
            "inviting you for an interview",
            "you have been shortlisted for an interview",
            "you are shortlisted for an interview",
            "you have been invited to interview",
            "you are invited to an interview",
            "you're invited to an interview",
            "book your interview",
            "select a time for your interview",
            "select an interview slot",
            "choose an interview slot",
            "schedule your interview via",
            "use this link to schedule your interview",
            "schedule a phone screen",
            "your interview has been scheduled",
            "your interview is scheduled for",
            "let us know your availability for an interview",
            "let me know your availability for an interview",
            "available for an interview",
            "available for a phone interview",
            "calendly.com",
            "دعوة لمقابلة",
            "يسرنا دعوتكم لمقابلة",
            "تم تحديد موعد مقابلة"
        ]

        REJECTION_PHRASES = [
            "regret to inform", "unfortunately", "not moving forward", "other candidates",
            "unsuccessful", "decided not to proceed", "pursuing other candidates",
            "not be proceeding", "won't be moving forward", "will not be proceeding",
            "decided to move forward with other",
            "نعتذر عن عدم", "للأسف نعتذر", "اختيار مرشح آخر", "لم يتم اختيارك"
        ]

        RECEIVED_PHRASES = [
            "application has been received", "application received", "job application received",
            "thank you for submitting your application", "thank you for submitting an application",
            "thank you for your application", "thank you for applying", "we have received your application",
            "application submitted successfully", "successfully submitted", "application under review",
            "has been submitted", "look forward to reviewing", "we look forward to reviewing",
            "تم استلام طلبك", "شكراً لتقديمك", "تم استلام التقديم بنجاح"
        ]

        def _decode_header_text(header_val: Optional[str]) -> str:
            if not header_val:
                return ""
            try:
                parts = decode_header(header_val)
                decoded_str = ""
                for part, enc in parts:
                    if isinstance(part, bytes):
                        decoded_str += part.decode(enc or "utf-8", errors="ignore")
                    else:
                        decoded_str += str(part)
                return decoded_str.strip()
            except Exception:
                return str(header_val)

        def _classify(subject_text: str, body_text: str):
            full_text = f"{subject_text} {body_text}".lower()
            lower_subj = subject_text.lower()

            # 1. Check for Rejection (excluding conditional 'if you are not selected')
            cleaned_for_rej = re.sub(r"if\s+(?:you\s+are\s+)?not\s+selected[^\n.]*", "", full_text)
            if any(p in cleaned_for_rej for p in REJECTION_PHRASES):
                return "Rejected", 3

            # 2. Check for Interview
            is_conditional = any(re.search(pat, full_text) for pat in CONDITIONAL_PATTERNS)
            has_definitive_invite = any(p in full_text for p in DEFINITIVE_INTERVIEW_PHRASES)

            # Only classify as Interview if it's an active, definitive invitation, not a conditional description
            if has_definitive_invite and not (is_conditional and not any(p in full_text for p in ["calendly.com", "book your interview", "select a time for your interview"])):
                return "Interview", 4

            # 3. Direct confirmation in subject (e.g. 'Job Application received')
            if any(p in lower_subj for p in ["application has been received", "application received", "job application received", "application submitted", "received your application"]):
                return "Under Review", 2.5

            # 4. Survey / Candidate Experience (Lower priority than direct confirmation)
            if any(w in lower_subj or w in full_text for w in ["survey", "application experience", "how was your experience"]):
                return "Under Review", 1.0

            # 5. Received / Under Review in body
            if any(p in full_text for p in RECEIVED_PHRASES):
                return "Under Review", 2.0

            return "Under Review", 0

        results_by_job = {}
        try:
            mail = imaplib.IMAP4_SSL(GMAIL_IMAP_SERVER)
            mail.login(self.user, self.app_password)
            mail.select("inbox")

            # 1. Search unread emails
            status_unseen, unseen_msgs = mail.search(None, "UNSEEN")
            unseen_ids = unseen_msgs[0].split() if status_unseen == "OK" and unseen_msgs[0] else []

            # 2. Search all emails to get recent messages (even if already viewed)
            status_all, all_msgs = mail.search(None, "ALL")
            all_ids = all_msgs[0].split() if status_all == "OK" and all_msgs[0] else []

            recent_ids = all_ids[-60:]  # latest 60 messages
            candidate_ids = []
            for eid in reversed(all_ids):
                if eid in unseen_ids or eid in recent_ids:
                    if eid not in candidate_ids:
                        candidate_ids.append(eid)
                if len(candidate_ids) >= 60:
                    break

            if not candidate_ids:
                mail.close()
                mail.logout()
                return []

            for e_id in candidate_ids:
                _, msg_data = mail.fetch(e_id, "(RFC822)")
                for response_part in msg_data:
                    if not isinstance(response_part, tuple):
                        continue
                    msg = email.message_from_bytes(response_part[1])
                    sender = _decode_header_text(msg.get("From", ""))
                    subject = _decode_header_text(msg.get("Subject", ""))
                    email_date = msg.get("Date", "")

                    lower_subj = subject.lower()
                    # Skip OTP and account verification emails
                    if any(otp in lower_subj for otp in ["one-time password", "otp", "passcode", "account verification", "verify your account", "رمز التحقق"]):
                        continue

                    # Extract body text (handles plain text and HTML fallback)
                    body_plain = ""
                    body_html = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            if ctype == "text/plain" and not body_plain:
                                p = part.get_payload(decode=True)
                                if p:
                                    body_plain = p.decode(part.get_content_charset() or "utf-8", errors="ignore")
                            elif ctype == "text/html" and not body_html:
                                p = part.get_payload(decode=True)
                                if p:
                                    body_html = p.decode(part.get_content_charset() or "utf-8", errors="ignore")
                    else:
                        p = msg.get_payload(decode=True)
                        if p:
                            dec = p.decode(msg.get_content_charset() or "utf-8", errors="ignore")
                            if msg.get_content_type() == "text/html":
                                body_html = dec
                            else:
                                body_plain = dec

                    raw_text = body_plain or re.sub(r"<[^>]+>", " ", body_html)
                    clean_body = re.sub(r"\s+", " ", raw_text).strip()
                    searchable = f"{sender} {subject} {clean_body}".lower()

                    # Match against tracked jobs
                    for comp in tracked_companies:
                        comp_name = (comp.get("company_name") or "").strip().lower()
                        job_title = (comp.get("job_title") or "").strip().lower()

                        # Prevent false positives on generic names
                        if comp_name in GENERIC_NAMES:
                            if not job_title or job_title not in searchable:
                                continue

                        matched = False
                        if comp_name and comp_name in searchable:
                            matched = True
                        elif comp_name and len(comp_name.split()) > 1 and all(w in searchable for w in comp_name.split() if len(w) > 2):
                            matched = True
                        elif comp_name and comp_name.replace(" ", "") in searchable.replace(" ", ""):
                            matched = True

                        if matched:
                            status_det, prio = _classify(subject, clean_body)
                            jid = comp.get("job_id")
                            candidate_res = {
                                "job_id": jid,
                                "company_name": comp.get("company_name"),
                                "subject": subject,
                                "sender": sender,
                                "detected_status": status_det,
                                "priority": prio,
                                "date": email_date,
                                "snippet": clean_body[:200]
                            }

                            if jid not in results_by_job or prio > results_by_job[jid]["priority"]:
                                results_by_job[jid] = candidate_res

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Error checking inbox: {e}")

        return list(results_by_job.values())
