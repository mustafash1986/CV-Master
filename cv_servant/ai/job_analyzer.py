"""
Job Analyzer module:
Extracts structured job metadata, keywords, email, and determines Visa Sponsorship status.
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


class JobAnalyzer:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama = ollama_client or OllamaClient()

    def detect_country_and_sponsorship_heuristics(self, text: str) -> Dict[str, Any]:
        """Fast heuristic check for country, visa sponsorship, email, and job URLs."""
        lower_text = text.lower()
        detected_country = "Unknown"
        sponsorship_status = "Not Mentioned"
        matched_indicators = []

        for country, data in TARGET_COUNTRIES.items():
            if any(k.lower() in lower_text for k in data["keywords"]):
                detected_country = country
                for ind in data["sponsorship_indicators"]:
                    if ind.lower() in lower_text:
                        matched_indicators.append(ind)

        if matched_indicators:
            sponsorship_status = f"Available ({', '.join(matched_indicators)})"
        elif "citizens only" in lower_text or "must have permanent residency" in lower_text or "سعوديين فقط" in lower_text or "كويتيين فقط" in lower_text:
            sponsorship_status = "Local Only / Restricted"

        # Regex email and URL scan
        emails = EMAIL_REGEX.findall(text)
        primary_email = emails[0] if emails else ""

        urls = URL_REGEX.findall(text)
        primary_url = urls[0] if urls else ""

        return {
            "country": detected_country,
            "sponsorship_status": sponsorship_status,
            "detected_indicators": matched_indicators,
            "detected_email": primary_email,
            "detected_url": primary_url,
        }

    def analyze_job(self, raw_job_text: str) -> Dict[str, Any]:
        """
        Deep analysis using local LLM (Qwen3.5:9b) to extract structured JSON.
        """
        heuristics = self.detect_country_and_sponsorship_heuristics(raw_job_text)

        system_prompt = (
            "You are an expert HR and Technical Recruiter specializing in Architecture and BIM recruitment. "
            "Analyze the given job posting text and extract structured information in JSON format."
        )

        prompt = f"""
Analyze this job posting and return a JSON object with EXACTLY these keys:
- "job_title": string (e.g. "Senior BIM Specialist", "BIM Manager", "Architect")
- "company_name": string
- "country": string (e.g. "Australia", "Canada", "New Zealand", "Saudi Arabia", "Kuwait", or other)
- "city": string
- "application_email": string (extracted email if present, else empty string)
- "application_method": string ("EMAIL", "WEBSITE_FORM", or "LINKEDIN_INDEED")
- "visa_sponsorship": string ("AVAILABLE", "NOT_MENTIONED", or "LOCAL_ONLY")
- "sponsorship_notes": string (brief explanation of sponsorship status)
- "key_requirements": list of strings (must-have tools, skills, years of experience)
- "fit_score": integer between 0 and 100 representing alignment with a Senior Architect / BIM Manager with 19 years experience, Revit Expert, Dynamo, Python, PMP
- "fit_rationale": string explaining why this candidate is a strong fit

Job Posting Text:
\"\"\"
{raw_job_text}
\"\"\"
"""
        try:
            response_text = self.ollama.generate(
                prompt=prompt,
                system=system_prompt,
                format_json=True,
                temperature=0.2,
                timeout=90,
            )
            data = json.loads(response_text)

            # Fallback heuristics if LLM missed email or country
            if not data.get("application_email") and heuristics["detected_email"]:
                data["application_email"] = heuristics["detected_email"]
                data["application_method"] = "EMAIL"

            if data.get("country") == "Unknown" and heuristics["country"] != "Unknown":
                data["country"] = heuristics["country"]

            if heuristics["sponsorship_status"].startswith("Available") and data.get("visa_sponsorship") != "AVAILABLE":
                data["visa_sponsorship"] = "AVAILABLE"
                data["sponsorship_notes"] = f"Detected: {heuristics['sponsorship_status']}"

            if heuristics.get("detected_url"):
                data["job_url"] = heuristics["detected_url"]

            data["raw_text"] = raw_job_text
            return data

        except Exception as e:
            logger.warning(f"LLM analysis failed, falling back to heuristics: {e}")
            return {
                "job_title": "Architect / BIM Specialist",
                "company_name": "Target Employer",
                "country": heuristics["country"],
                "city": "",
                "application_email": heuristics["detected_email"],
                "job_url": heuristics.get("detected_url", ""),
                "application_method": "EMAIL" if heuristics["detected_email"] else "WEBSITE_FORM",
                "visa_sponsorship": "AVAILABLE" if heuristics["sponsorship_status"].startswith("Available") else "NOT_MENTIONED",
                "sponsorship_notes": heuristics["sponsorship_status"],
                "key_requirements": ["Revit", "BIM", "Architecture"],
                "fit_score": 85,
                "fit_rationale": "Matches core architectural and BIM competence.",
                "raw_text": raw_job_text,
            }
