"""
Local HTTP REST Bridge for CV Servant Chrome Extension.
Listens on localhost (127.0.0.1:5822) to serve candidate profile data
for automated form filling and to record external job submissions in the tracker.

Zero external dependencies - built entirely on Python standard library.
"""
import http.server
import json
import logging
import re
import socketserver
import threading
from datetime import datetime
from typing import Any, Callable, Dict, Optional
import urllib.parse

from cv_servant.master_profile import MASTER_PROFILE

logger = logging.getLogger(__name__)

DEFAULT_PORT = 5822


def get_candidate_autofill_data() -> Dict[str, Any]:
    """
    Returns structured, comprehensive candidate data mapped to common
    ATS and job board form fields.
    """
    p = MASTER_PROFILE.get("personal_info", {})
    full_name = p.get("full_name", "MUSTAFA MAHMOUD SHAWKY")
    name_parts = full_name.split()
    first_name = name_parts[0].capitalize() if name_parts else "Mustafa"
    last_name = name_parts[-1].capitalize() if len(name_parts) > 1 else "Shawky"
    middle_name = " ".join(part.capitalize() for part in name_parts[1:-1]) if len(name_parts) > 2 else "Mahmoud"

    summary = MASTER_PROFILE.get("professional_summary", "")

    return {
        "candidate": {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "full_name": full_name.title(),
            "headline": p.get("title", "Senior Architect & BIM Specialist / BIM Manager"),
            "email": p.get("email", "arch.mustafa.mahmoud.2007@gmail.com"),
            "phone": p.get("phone", "+965 9919 1358"),
            "phone_country_code": "+965",
            "phone_national": "99191358",
            "address": "Sabah Elsalem",
            "city": "Sabah Elsalem",
            "country": "Kuwait",
            "nationality": p.get("nationality", "Egyptian"),
            "residency": p.get("residency", "Kuwait (Transferable Visa)"),
            "postal_code": "44000",
            "linkedin": f"https://{p.get('linkedin', 'www.linkedin.com/in/mostafamahmoud-architect')}",
            "portfolio": p.get("portfolio_website", "https://mustafash1986.github.io/mustafa-portfolio1/"),
            "github": "https://github.com/mustafash1986",
            "current_company": "Pace",
            "current_title": "Senior Architect & BIM Specialist",
            "current_location": "Kuwait",
            "family_status": "Married",
            "family_in_saudi": "No",
            "date_of_birth": "15/07/1986",
            "birth_year": "1986",
            "saudi_residency": "No",
            "saudi_iqama": "No",
            "iqama_title": "N/A",
            "total_experience_years": 19,
            "gcc_experience_years": 17,
            "worked_with_company_before": "No",
            "relatives_in_company": "No",
            "salary_expectation_usd": "5000",
            "salary_expectation": "5000",
            "highest_degree": "Bachelor's Degree",
            "bachelor_degree": "Bachelor of Architecture (B.Arch.)",
            "graduation_year": 2007,
            "revit_experience_years": 16,
            "bim_experience_years": 15,
            "autocad_experience_years": 19,
            "navisworks_experience_years": 12,
            "pmp_certified": "Yes",
            "pmp_license": "PMP #3010938 (PMI - Valid through May 2027)",
            "revit_certified": "Yes",
            "revit_license": "Autodesk Certified Professional #00424122",
            "kse_registered": "Yes (Registered Professional Architect, Kuwait Society of Engineers)",
            "notice_period": "1 Month",
            "notice_period_days": 30,
            "willing_to_relocate": "Yes",
            "work_mode": "Hybrid / Onsite / Remote",
            "summary": summary,
            "education": {
                "degree": "Bachelor of Architecture (B.Arch.)",
                "institution": "Minia University, Faculty of Engineering",
                "country": "Egypt",
                "graduation_year": 2007,
                "grade": "Graduated with Excellency"
            },
            "languages": [
                {"name": "Arabic", "level": "Native / Mother Tongue"},
                {"name": "English", "level": "Professional Working Proficiency (BUSUU B2 Certified)"}
            ],
            "common_answers": {
                "sponsorship": "Will require work visa sponsorship for overseas positions (Transferable residency in Kuwait).",
                "work_authorization": "Authorized to work in Kuwait (Transferable Visa). Require sponsorship for international roles.",
                "relocate": "Yes, fully willing and prepared to relocate internationally.",
                "salary_expectation": "Negotiable based on market benchmark, package, and cost of living.",
                "commence_date": "Within 30 days of offer acceptance (Standard notice period).",
                "criminal_record": "No",
                "over_18": "Yes",
                "drivers_license": "Yes (Valid driving license)"
            }
        }
    }


class CVBridgeRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handles REST requests from the Chrome Extension with CORS and input validation."""

    server_instance: Any = None

    def _set_cors_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self._set_cors_headers(200)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status" or path == "/":
            self._set_cors_headers(200)
            resp = {
                "status": "online",
                "service": "CV Servant Local Bridge",
                "version": "1.0.0",
                "candidate": "Eng. Mustafa Mahmoud Shawky",
                "server_time": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/profile":
            self._set_cors_headers(200)
            data = get_candidate_autofill_data()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/check_job":
            target_url = query.get("url", [""])[0]
            title = query.get("title", [""])[0]
            comp = query.get("company", [""])[0]

            is_tracked = False
            job_record = None

            if self.server_instance and self.server_instance.coordinator:
                tracker = self.server_instance.coordinator.tracker
                existing = tracker.find_job_by_url_or_title(target_url, title, comp)
                if existing:
                    is_tracked = True
                    job_record = existing

            self._set_cors_headers(200)
            self.wfile.write(json.dumps({
                "is_tracked": is_tracked,
                "job": job_record
            }, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/tracked_jobs":
            jobs = []
            if self.server_instance and self.server_instance.coordinator:
                jobs = self.server_instance.coordinator.tracker.get_all_jobs()
            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"jobs": jobs}, ensure_ascii=False).encode("utf-8"))

        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/track_application":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                if content_len > 1_000_000:  # 1MB limit for security
                    self._set_cors_headers(413)
                    self.wfile.write(json.dumps({"error": "Payload too large"}).encode("utf-8"))
                    return

                raw_body = self.rfile.read(content_len).decode("utf-8")
                payload = json.loads(raw_body)
            except Exception as e:
                logger.error(f"Failed to parse JSON in bridge request: {e}")
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {str(e)}"}).encode("utf-8"))
                return

            # Sanitize and validate inputs
            company = str(payload.get("company_name", "")).strip()[:100] or "Direct Employer"
            title = str(payload.get("job_title", "")).strip()[:150] or "BIM Role"
            url = str(payload.get("job_url", "")).strip()[:500]
            country = str(payload.get("country", "Australia")).strip()[:60]
            city = str(payload.get("city", "")).strip()[:60]
            source = str(payload.get("source", "Chrome Extension")).strip()[:60]
            notes = str(payload.get("notes", "Submitted via CV Servant Chrome Auto-Fill Extension")).strip()[:500]

            job_dict = {
                "company_name": company,
                "job_title": title,
                "country": country,
                "city": city,
                "job_url": url,
                "contact": url,
                "source": source,
                "application_method": f"WEBSITE_FORM ({source})",
                "visa_sponsorship": payload.get("visa_sponsorship", "Not Mentioned"),
                "status": "Applied (External / تم التقديم)",
                "notes": notes
            }

            job_id = ""
            if self.server_instance and self.server_instance.coordinator:
                try:
                    tracker = self.server_instance.coordinator.tracker
                    job_id = tracker.track_external_application(job_dict, is_applied=True)
                    # Sync to GDrive
                    self.server_instance.coordinator.gdrive.sync_tracker_to_drive()

                    # Notify GUI callback if registered
                    if self.server_instance.on_application_tracked:
                        self.server_instance.on_application_tracked(job_dict, job_id)
                except Exception as e:
                    logger.error(f"Error tracking application in coordinator: {e}")

            self._set_cors_headers(200)
            resp = {
                "success": True,
                "job_id": job_id,
                "message": f"Successfully tracked application for '{title}' at '{company}'!",
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress noisy request logs, keep error logs."""
        pass


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class CVBridgeServer:
    """
    Manager for the background HTTP server that bridges CV Servant with Chrome.
    """
    def __init__(
        self,
        coordinator: Any,
        port: int = DEFAULT_PORT,
        on_application_tracked: Optional[Callable[[Dict[str, Any], str], None]] = None
    ):
        self.coordinator = coordinator
        self.port = port
        self.on_application_tracked = on_application_tracked
        self.httpd: Optional[ThreadedHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.is_running = False

    def start(self) -> bool:
        """Starts the bridge server in a background daemon thread."""
        try:
            handler = CVBridgeRequestHandler
            handler.server_instance = self
            self.httpd = ThreadedHTTPServer(("127.0.0.1", self.port), handler)
            self.is_running = True

            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()
            logger.info(f"CV Servant Chrome Bridge Server started on http://127.0.0.1:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start CV Servant Bridge Server on port {self.port}: {e}")
            self.is_running = False
            return False

    def _run_server(self):
        if self.httpd:
            try:
                self.httpd.serve_forever()
            except Exception as e:
                logger.debug(f"Bridge server stopped: {e}")

    def stop(self):
        """Stops the bridge server cleanly."""
        self.is_running = False
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
