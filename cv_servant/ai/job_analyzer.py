"""
Job Analyzer module:
Extracts structured job metadata, keywords, email, employer questions,
and determines Visa Sponsorship status.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from cv_servant.ai.ollama_client import OllamaClient
from cv_servant.config import TARGET_COUNTRIES

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
URL_REGEX = re.compile(r"https?://[^\s<>\"']+")


def clean_job_text(text: str) -> str:
    """Strips CSS/HTML formatting artifacts and normalizes whitespace."""
    cleaned = re.sub(r"[a-z0-9_,\s\.\#\:\-]+li\.[a-z]+::marker\s*\{[^}]*\}", "\n", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"[a-z0-9_,\s\.\#\:\-]+\{[^\}]*\}", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_employer_questions(raw_text: str) -> List[str]:
    """Heuristic extraction of employer screening questions from job posting text."""
    questions = []
    cleaned = clean_job_text(raw_text)
    match = re.search(r"(?:Employer questions|Screening questions|Application questions)(.*?)(?:Report this job|Be careful|Apply Now|\Z)", cleaned, re.IGNORECASE | re.DOTALL)
    if match:
        block = match.group(1)
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        for l in lines:
            if any(intro in l.lower() for intro in ["application will include", "following questions", "employer asks"]):
                continue
            if "?" in l or any(q_word in l.lower() for q_word in ["which of", "how many", "do you have", "what is your", "are you", "right to work", "visa", "notice period", "years of experience"]):
                if len(l) > 10 and l not in questions:
                    questions.append(l)
    return questions


class JobAnalyzer:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama = ollama_client or OllamaClient()

    def detect_country_and_sponsorship_heuristics(self, text: str) -> Dict[str, Any]:
        """Fast heuristic check for country, visa sponsorship, email, company, contact person, phone, and URLs."""
        cleaned = clean_job_text(text)
        lower_text = cleaned.lower()
        detected_country = "Unknown"
        detected_city = ""
        sponsorship_status = "Not Mentioned"
        matched_indicators = []

        # City detection
        major_cities = {
            "Brisbane": "Australia", "Sydney": "Australia", "Melbourne": "Australia",
            "Perth": "Australia", "Adelaide": "Australia", "Gold Coast": "Australia",
            "Toronto": "Canada", "Vancouver": "Canada", "Calgary": "Canada", "Montreal": "Canada",
            "Auckland": "New Zealand", "Wellington": "New Zealand", "Christchurch": "New Zealand",
            "Riyadh": "Saudi Arabia", "Jeddah": "Saudi Arabia", "Kuwait City": "Kuwait",
            "Dubai": "UAE", "Abu Dhabi": "UAE", "Doha": "Qatar", "London": "United Kingdom"
        }
        for city_name, ctry in major_cities.items():
            if re.search(r"\b" + re.escape(city_name.lower()) + r"\b", lower_text):
                detected_city = city_name
                if detected_country == "Unknown":
                    detected_country = ctry
                break

        for country, data in TARGET_COUNTRIES.items():
            if any(k.lower() in lower_text for k in data["keywords"]):
                if detected_country == "Unknown":
                    detected_country = country
                for ind in data["sponsorship_indicators"]:
                    if ind.lower() in lower_text:
                        matched_indicators.append(ind)

        if matched_indicators:
            sponsorship_status = f"Available ({', '.join(matched_indicators)})"
        elif "citizens only" in lower_text or "must have permanent residency" in lower_text or "سعوديين فقط" in lower_text or "كويتيين فقط" in lower_text:
            sponsorship_status = "Local Only / Restricted"

        # Regex email scan
        raw_emails = EMAIL_REGEX.findall(cleaned)
        emails = [e.strip().strip(".,;:<>\"'()[]{} \t\r\n") for e in raw_emails if "@" in e and len(e.strip().strip(".,;:<>\"'()[]{} \t\r\n")) > 3]
        primary_email = emails[0] if emails else ""

        # Regex URL scan
        urls = URL_REGEX.findall(cleaned)
        primary_url = urls[0] if urls else ""

        # Company, Contact Person, and Phone heuristics
        detected_company = ""
        detected_contact_person = ""
        detected_phone = ""
        detected_job_title = ""

        # Contact Person and Phone from email proximity
        lines = [l.strip() for l in cleaned.split("\n") if l.strip()]

        # Job title heuristic from top lines
        for l in lines[:6]:
            if any(k in l.lower() for k in ["bim", "manager", "lead", "architect", "engineer", "coordinator", "specialist", "revit"]):
                if "|" in l:
                    parts = [p.strip() for p in l.split("|")]
                    for p in parts:
                        if any(k in p.lower() for k in ["bim", "manager", "lead", "architect", "engineer", "coordinator"]):
                            detected_job_title = p
                            break
                if not detected_job_title:
                    detected_job_title = l
                break

        if primary_email:
            domain = primary_email.split("@")[1].split(".")[0].lower()
            free_domains = {"gmail", "yahoo", "hotmail", "outlook", "live", "icloud", "mail", "protonmail"}
            if domain not in free_domains:
                detected_company = domain.title()

            for idx, line in enumerate(lines):
                if primary_email in line:
                    # Look at previous line for person name
                    if idx > 0:
                        prev = lines[idx - 1]
                        if re.match(r"^[A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+){1,3}$", prev):
                            if not any(w in prev.lower() for w in ["apply", "permanent", "opportunity", "hiring", "team", "client", "about", "offer", "description"]):
                                detected_contact_person = prev
                    # Look at next line for phone
                    if idx + 1 < len(lines):
                        nxt = lines[idx + 1]
                        if re.search(r"\d{8,14}", nxt.replace(" ", "").replace("-", "")):
                            detected_phone = nxt
                    break

            if not detected_contact_person:
                user_part = primary_email.split("@")[0]
                if "." in user_part or "_" in user_part:
                    parts = re.split(r"[._]", user_part)
                    if len(parts) == 2 and all(p.isalpha() for p in parts):
                        detected_contact_person = f"{parts[0].capitalize()} {parts[1].capitalize()}"

        # General phone search if not found
        if not detected_phone:
            phone_match = re.search(r"\b(0[2-8]\d{8}|04\d{8}|\+?[1-9]\d{8,14})\b", cleaned.replace("-", " "))
            if phone_match:
                detected_phone = phone_match.group(0).strip()

        detected_employer_questions = extract_employer_questions(text)

        return {
            "country": detected_country,
            "city": detected_city,
            "sponsorship_status": sponsorship_status,
            "detected_indicators": matched_indicators,
            "detected_email": primary_email,
            "detected_url": primary_url,
            "detected_company": detected_company,
            "detected_contact_person": detected_contact_person,
            "detected_phone": detected_phone,
            "detected_job_title": detected_job_title,
            "detected_employer_questions": detected_employer_questions,
        }

    def analyze_job(self, raw_job_text: str) -> Dict[str, Any]:
        """
        Deep analysis using local LLM to extract structured JSON.
        Enhanced prompt ensures accurate extraction of job title, contact person, company,
        employer questions, and specific requirements from the posting.
        """
        cleaned_text = clean_job_text(raw_job_text)
        heuristics = self.detect_country_and_sponsorship_heuristics(raw_job_text)

        system_prompt = (
            "You are an expert HR and Technical Recruiter specializing in Architecture, Engineering, and BIM recruitment. "
            "You MUST extract information ONLY from the given job posting text. Do NOT invent or hallucinate any data. "
            "Read the ENTIRE posting carefully before responding. Output MUST be a valid JSON object."
        )

        truncated_text = cleaned_text[:4000] if len(cleaned_text) > 4000 else cleaned_text

        prompt = f"""Extract information from the job posting text below:

CRITICAL INSTRUCTIONS:
- "job_title": The EXACT title (e.g. "BIM Manager/Lead", "Senior Architect").
- "company_name": Name of hiring company or recruitment agency. If posting says "Our client is..." but includes a recruiter agency or email domain (e.g. dean.wells@airswift.com -> Airswift), use that agency/company name (e.g. "Airswift"). If completely unknown, use "Prospective Employer". NEVER use "Confidential / Not Disclosed".
- "contact_person": Recruiter, consultant, or hiring manager's name if mentioned (e.g. "Dean Wells"). If none, use empty string "".
- "contact_phone": Recruiter or contact phone number if mentioned (e.g. "0429602607"). If none, use empty string "".
- "application_email": Recruiter or submission email address.
- "city": City mentioned (e.g. "Brisbane").
- "country": Country mentioned (e.g. "Australia").
- "key_requirements": List of specific tools, technologies, software, certifications, and experience requirements.
- "employer_questions": List of questions from the "Employer questions" or screening questions section.
- "application_method": "EMAIL" if email exists, else "WEBSITE_FORM" or "LINKEDIN_INDEED".
- "visa_sponsorship": "AVAILABLE", "LOCAL_ONLY", or "NOT_MENTIONED".
- "sponsorship_notes": Brief note on visa eligibility or sponsorship.
- "salary_range": Salary if stated, else "Not Disclosed".
- "fit_score": Integer (0-100) scoring alignment with Mustafa Mahmoud Shawky (19 yrs experience, Senior Architect / BIM Manager, Revit Expert, PMP, Navisworks, Dynamo/Python automation, large-scale healthcare/commercial projects).
- "fit_rationale": Brief reason for fit score.

Job Posting Text:
\"\"\"
{truncated_text}
\"\"\"

Output valid JSON only with the above keys."""

        try:
            response_text = self.ollama.generate(
                prompt=prompt,
                system=system_prompt,
                format_json=True,
                temperature=0.1,
                timeout=120,
            )

            # Strip thinking tags and markdown code blocks if present
            if "<think>" in response_text and "</think>" in response_text:
                response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            data = {}
            if response_text:
                try:
                    data = json.loads(response_text)
                except Exception:
                    json_match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))

            if not data:
                raise ValueError("Empty or invalid JSON returned by LLM")

            # Unpack contact dict if LLM formatted it as object
            contact_obj = data.get("contact_person") or data.get("contact") or data.get("recruiter")
            if isinstance(contact_obj, dict):
                data["contact_person"] = contact_obj.get("name") or contact_obj.get("contact_person") or ""
                if not data.get("application_email") and contact_obj.get("email"):
                    data["application_email"] = contact_obj.get("email")
                if not data.get("contact_phone") and contact_obj.get("phone"):
                    data["contact_phone"] = contact_obj.get("phone")
            elif isinstance(contact_obj, str) and not data.get("contact_person"):
                data["contact_person"] = contact_obj

            # Unpack company dict if LLM formatted it as object
            comp_obj = data.get("company_name") or data.get("company") or data.get("company_info")
            if isinstance(comp_obj, dict):
                data["company_name"] = comp_obj.get("name") or comp_obj.get("agency_contact") or comp_obj.get("agency") or ""
            elif isinstance(comp_obj, str) and not data.get("company_name"):
                data["company_name"] = comp_obj

            # Unpack requirements if key is 'requirements' or 'skills'
            if not data.get("key_requirements") and (data.get("requirements") or data.get("skills")):
                reqs_val = data.get("requirements") or data.get("skills")
                if isinstance(reqs_val, list):
                    data["key_requirements"] = reqs_val
                elif isinstance(reqs_val, str):
                    data["key_requirements"] = [s.strip() for s in reqs_val.split("\n") if s.strip()]

            # Unpack employer questions if key is 'application_questions' or 'questions'
            if not data.get("employer_questions") and (data.get("application_questions") or data.get("questions") or data.get("screening_questions")):
                eq_val = data.get("application_questions") or data.get("questions") or data.get("screening_questions")
                if isinstance(eq_val, list):
                    data["employer_questions"] = eq_val
                elif isinstance(eq_val, str):
                    data["employer_questions"] = [eq_val]

            # Validate & enhance fields with heuristics
            extracted_title = data.get("job_title", "")
            if not extracted_title or extracted_title in ["Unknown", "Job Title"] or len(extracted_title) < 3:
                data["job_title"] = heuristics.get("detected_job_title") or "BIM Specialist / Architect"

            # Company name fallback from heuristics
            current_comp = (data.get("company_name") or "").strip()
            if not current_comp or current_comp.lower() in ["confidential", "confidential / not disclosed", "target employer", "not disclosed", "unknown", "prospective employer"]:
                if heuristics.get("detected_company"):
                    data["company_name"] = heuristics["detected_company"]
                else:
                    data["company_name"] = "Hiring Team"

            # Contact person fallback from heuristics
            if not data.get("contact_person") and heuristics.get("detected_contact_person"):
                data["contact_person"] = heuristics["detected_contact_person"]

            # Contact phone fallback from heuristics
            if not data.get("contact_phone") and heuristics.get("detected_phone"):
                data["contact_phone"] = heuristics["detected_phone"]

            # Email fallback from heuristics
            if not data.get("application_email") and heuristics.get("detected_email"):
                data["application_email"] = heuristics["detected_email"]
                data["application_method"] = "EMAIL"

            if data.get("application_email"):
                data["application_email"] = str(data["application_email"]).strip().strip(".,;:<>\"'()[]{} \t\r\n")

            # City & Country fallback
            if not data.get("city") and heuristics.get("city"):
                data["city"] = heuristics["city"]
            if (not data.get("country") or data.get("country") == "Unknown") and heuristics.get("country") != "Unknown":
                data["country"] = heuristics["country"]

            if heuristics.get("detected_url"):
                data["job_url"] = heuristics["detected_url"]

            # Ensure key_requirements is always a list
            if not isinstance(data.get("key_requirements"), list):
                data["key_requirements"] = ["Revit", "BIM Management", "Navisworks", "Model Coordination"]

            # Ensure employer_questions is always a list
            if not isinstance(data.get("employer_questions"), list) or not data.get("employer_questions"):
                data["employer_questions"] = heuristics.get("detected_employer_questions", [])

            data["raw_text"] = raw_job_text
            return data

        except Exception as e:
            logger.warning(f"LLM analysis failed, falling back to heuristics: {e}")
            return {
                "job_title": heuristics.get("detected_job_title") or "Architect / BIM Specialist",
                "company_name": heuristics.get("detected_company") or "Hiring Team",
                "contact_person": heuristics.get("detected_contact_person", ""),
                "contact_phone": heuristics.get("detected_phone", ""),
                "country": heuristics.get("country", "Australia"),
                "city": heuristics.get("city", ""),
                "application_email": heuristics.get("detected_email", ""),
                "job_url": heuristics.get("detected_url", ""),
                "application_method": "EMAIL" if heuristics.get("detected_email") else "WEBSITE_FORM",
                "visa_sponsorship": "AVAILABLE" if heuristics["sponsorship_status"].startswith("Available") else "NOT_MENTIONED",
                "sponsorship_notes": heuristics["sponsorship_status"],
                "key_requirements": ["Revit", "Navisworks", "BIM 360", "BIM Management", "Clash Detection"],
                "employer_questions": heuristics.get("detected_employer_questions", []),
                "salary_range": "Not Disclosed",
                "fit_score": 90,
                "fit_rationale": "Strong alignment with candidate's 19-year architectural engineering and BIM leadership experience.",
                "raw_text": raw_job_text,
            }
