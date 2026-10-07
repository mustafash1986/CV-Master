"""
Job Analyzer Module:
Extracts structured job metadata, keywords, email, employer screening questions,
and performs 5-Dimension Job Evaluation & Eligibility Gating (ported from ai-job-search framework)
powered by local Qwen 3.5.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

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
    match = re.search(
        r"(?:Employer questions|Screening questions|Application questions)(.*?)(?:Report this job|Be careful|Apply Now|\Z)",
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        block = match.group(1)
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        for l in lines:
            if any(intro in l.lower() for intro in ["application will include", "following questions", "employer asks"]):
                continue
            if "?" in l or any(
                q_word in l.lower()
                for q_word in [
                    "which of", "how many", "do you have", "what is your", "are you",
                    "right to work", "visa", "notice period", "years of experience",
                ]
            ):
                if len(l) > 10 and l not in questions:
                    questions.append(l)
    return questions


class JobAnalyzer:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama = ollama_client or OllamaClient()

    def detect_country_and_sponsorship_heuristics(self, text: str) -> Dict[str, Any]:
        """
        Fast heuristic check for country, visa sponsorship, eligibility gate,
        contact information, employer questions, and 5-dimension scoring baseline.
        """
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
            "Canberra": "Australia", "Auckland": "New Zealand", "Wellington": "New Zealand",
            "Christchurch": "New Zealand", "Toronto": "Canada", "Vancouver": "Canada",
            "Calgary": "Canada", "Montreal": "Canada", "Ottawa": "Canada",
            "Riyadh": "Saudi Arabia", "Jeddah": "Saudi Arabia", "Kuwait City": "Kuwait",
            "Dubai": "UAE", "Abu Dhabi": "UAE", "Doha": "Qatar", "London": "United Kingdom",
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
                    ind_low = ind.lower()
                    if ind_low in lower_text:
                        is_negated = any(
                            neg in lower_text
                            for neg in [
                                f"no {ind_low}", f"not offer {ind_low}", f"not provide {ind_low}",
                                "no sponsorship", "cannot sponsor", "unable to sponsor", "not sponsoring",
                            ]
                        )
                        if not is_negated:
                            matched_indicators.append(ind)

        # ---------------- Eligibility Gate (Hard Filter) ----------------
        # 1. Check for citizenship / PR exclusion
        citizen_phrases = [
            "australian citizen only", "australian citizenship required", "must be an australian citizen",
            "australian citizens only", "canadian citizen only", "canadian citizenship required",
            "must be a canadian citizen", "citizenship required", "must have permanent residency",
            "pr or citizen only", "australian pr required", "unrestricted working rights required",
            "full working rights required", "سعوديين فقط", "كويتيين فقط",
        ]
        has_citizen_restriction = any(p in lower_text for p in citizen_phrases)

        # 2. Check for security clearance
        clearance_phrases = [
            "baseline clearance", "nv1", "nv2", "negative vetting", "defence clearance",
            "defense clearance", "security clearance required", "must be eligible for baseline",
        ]
        has_clearance = any(p in lower_text for p in clearance_phrases)

        # Hard Gate Priority: Explicit exclusion (Citizenship or Clearance) overrides general mentions
        if has_citizen_restriction:
            sponsorship_status = "Local Only / Restricted"
            eligibility_verdict = "FAIL"
            eligibility_notes = "Posting demands Citizenship or Permanent Residency with no sponsorship."
        elif has_clearance:
            sponsorship_status = "Restricted (Security Clearance)"
            eligibility_verdict = "FAIL"
            eligibility_notes = "Requires Defence/Security Clearance (typically gated on national citizenship)."
        elif matched_indicators:
            sponsorship_status = f"Available ({', '.join(matched_indicators)})"
            eligibility_verdict = "PASS"
            eligibility_notes = f"Visa sponsorship detected ({', '.join(matched_indicators)})"
        else:
            eligibility_verdict = "UNVERIFIED"
            eligibility_notes = "Posting does not state visa sponsorship explicitly. Verify employer international policy."

        # Regex email scan
        raw_emails = EMAIL_REGEX.findall(cleaned)
        emails = [e.strip().strip(".,;:<>\"'()[]{} \t\r\n") for e in raw_emails if "@" in e and len(e.strip().strip(".,;:<>\"'()[]{} \t\r\n")) > 3]
        primary_email = emails[0] if emails else ""

        # Regex URL scan
        urls = URL_REGEX.findall(cleaned)
        primary_url = urls[0] if urls else ""

        # Heuristic Company, Contact Person, and Phone extraction
        detected_company = ""
        detected_contact_person = ""
        detected_phone = ""
        detected_job_title = ""

        lines = [l.strip() for l in cleaned.split("\n") if l.strip()]

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
            excluded_domains = ["gmail", "yahoo", "hotmail", "outlook", "icloud", "mail", "apply", "recruit"]
            if domain not in excluded_domains and len(domain) > 2:
                detected_company = domain.capitalize()

        if not detected_company:
            for l in lines[:10]:
                match_at = re.search(r'\bat\s+([A-Z][A-Za-z0-9&\s]{2,30})', l)
                if match_at:
                    cand = match_at.group(1).strip()
                    if not any(w in cand.lower() for w in ["least", "present", "our", "the", "work", "home", "once"]):
                        detected_company = cand
                        break

        # Contact person near email
        for i, l in enumerate(lines):
            if primary_email and primary_email in l:
                if i > 0:
                    prev_line = lines[i - 1].strip()
                    prev_words = prev_line.split()
                    if 2 <= len(prev_words) <= 4 and all(w[0].isupper() for w in prev_words if w.isalpha()):
                        detected_contact_person = prev_line
                break

        # Phone extraction
        phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}", cleaned)
        if phone_match and len(phone_match.group(0).strip()) >= 8:
            detected_phone = phone_match.group(0).strip()

        detected_employer_questions = extract_employer_questions(text)

        # ---------------- 5-Dimension Heuristic Scoring Matrix ----------------
        # 1. Technical Match (Revit, Navisworks, Dynamo, Python, ISO 19650, BIM 360, dRofus)
        tech_score = 75
        if "revit" in lower_text:
            tech_score += 6
        if "dynamo" in lower_text or "python" in lower_text or "computational" in lower_text:
            tech_score += 6
        if "navisworks" in lower_text or "clash" in lower_text or "coordination" in lower_text:
            tech_score += 4
        if "iso 19650" in lower_text or "bim 360" in lower_text or "acc" in lower_text:
            tech_score += 4
        if "drofus" in lower_text:
            tech_score += 3
        tech_score = min(tech_score, 98)

        # 2. Experience Match (19+ years, Healthcare, Mega-projects, Architecture)
        exp_score = 80
        if any(w in lower_text for w in ["manager", "lead", "senior", "head", "director"]):
            exp_score += 6
        if any(w in lower_text for w in ["health", "hospital", "commercial", "large", "complex"]):
            exp_score += 6
        if any(w in lower_text for w in ["architectural", "architecture", "design"]):
            exp_score += 4
        exp_score = min(exp_score, 98)

        # 3. Behavioral / Culture Fit (Mentoring, Coordination, Team Leadership)
        beh_score = 80
        if any(w in lower_text for w in ["mentor", "lead", "guide", "training", "leadership"]):
            beh_score += 6
        if any(w in lower_text for w in ["collaborat", "stakeholder", "multidisciplinary", "interdisciplinary", "coordinat", "team"]):
            beh_score += 6
        beh_score = min(beh_score, 95)

        # 4. Location & Logistics
        loc_verdict = "PASS" if detected_country in ["Australia", "Canada", "New Zealand", "Saudi Arabia", "Kuwait"] or "remote" in lower_text else "FLAG"

        # 5. Career Alignment & Motivation
        career_score = 85
        if "bim manager" in lower_text or "bim lead" in lower_text or "digital delivery" in lower_text:
            career_score += 7
        if "pmp" in lower_text or "project management" in lower_text:
            career_score += 4
        career_score = min(career_score, 98)

        # Weighted score: 30% Tech, 25% Exp, 15% Beh, 30% Career
        weighted_fit = round(0.30 * tech_score + 0.25 * exp_score + 0.15 * beh_score + 0.30 * career_score)
        if eligibility_verdict == "FAIL":
            fit_verdict = "Excluded (Eligibility Gate Fail)"
        elif weighted_fit >= 75:
            fit_verdict = "Strong Fit"
        elif weighted_fit >= 60:
            fit_verdict = "Good Fit"
        elif weighted_fit >= 45:
            fit_verdict = "Moderate Fit"
        else:
            fit_verdict = "Weak Fit"

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
            "eligibility_gate": {
                "verdict": eligibility_verdict,
                "notes": eligibility_notes,
                "citizenship_restricted": has_citizen_restriction,
                "clearance_required": has_clearance,
            },
            "dimensions": {
                "technical_score": tech_score,
                "experience_score": exp_score,
                "behavioral_score": beh_score,
                "location_verdict": loc_verdict,
                "career_score": career_score,
            },
            "fit_score": weighted_fit,
            "fit_verdict": fit_verdict,
        }

    def analyze_job(self, raw_job_text: str) -> Dict[str, Any]:
        """
        Deep analysis using local Qwen 3.5 LLM to evaluate the job posting
        using the 5-Dimension Framework and Eligibility Gate from ai-job-search.
        """
        cleaned_text = clean_job_text(raw_job_text)
        heuristics = self.detect_country_and_sponsorship_heuristics(raw_job_text)

        system_prompt = (
            "You are an expert HR Director, Executive Recruiter, and Career Advisor for Eng. Mustafa Mahmoud Shawky.\n"
            "CANDIDATE BACKGROUND:\n"
            "- 19+ years experience as Senior Architect, Senior BIM Specialist, and BIM Manager.\n"
            "- Certified PMP (Project Management Professional), Autodesk Certified Professional in Revit.\n"
            "- Expert in Revit, Navisworks Manage (Clash Detection), BIM 360/Autodesk Construction Cloud, Dynamo & Python automation, ISO 19650 standards.\n"
            "- Resident in Kuwait, Egyptian citizen. Requires employer visa sponsorship (TSS 482 / ENS 186 / LMIA) for roles in Australia, Canada, etc.\n"
            "- Extensive experience on major healthcare, hospitals, and complex commercial projects.\n\n"
            "You MUST evaluate the job strictly using the 5-Dimension Evaluation Framework & Eligibility Gate.\n"
            "Output MUST be valid JSON only."
        )

        truncated_text = cleaned_text[:4200] if len(cleaned_text) > 4200 else cleaned_text

        prompt = f"""Evaluate this job posting text against Eng. Mustafa Shawky's candidate profile:

\"\"\"
{truncated_text}
\"\"\"

CRITICAL EVALUATION INSTRUCTIONS:
1. "job_title": Exact title from the ad (e.g. "BIM Manager", "Architectural BIM Coordinator").
2. "company_name": Name of hiring company or recruitment agency. If agency is known, use it. Do not invent names.
3. "contact_person": Recruiter or hiring manager's name if mentioned, otherwise "".
4. "contact_phone": Recruiter contact phone if mentioned, otherwise "".
5. "application_email": Direct application email if mentioned, otherwise "".
6. "city": City mentioned (e.g. "Melbourne", "Sydney", "Toronto").
7. "country": Country mentioned (e.g. "Australia", "Canada", "Kuwait").
8. "key_requirements": List of required software, skills, and certifications.
9. "employer_questions": List of questions from screening/employer questions section. If none, return empty list [].
10. "application_method": "EMAIL" if email exists, else "WEBSITE_FORM" or "LINKEDIN_INDEED".
11. "visa_sponsorship": "AVAILABLE", "LOCAL_ONLY", or "NOT_MENTIONED".
12. "sponsorship_notes": Note on visa eligibility or sponsorship support.
13. "salary_range": Stated salary or "Not Disclosed".

14. "eligibility_gate": An object with:
    - "verdict": "PASS" (sponsorship available/international welcome), "FAIL" (explicit citizenship or security clearance required), or "UNVERIFIED" (silent).
    - "notes": Reason for the eligibility gate verdict citing ad wording.

15. "dimensions": An object with:
    - "technical_score": Integer (0-100) scoring technical skills (Revit, Navisworks, Dynamo, Python, ISO 19650).
    - "technical_notes": Brief explanation of technical alignment.
    - "experience_score": Integer (0-100) scoring domain experience (19 yrs, healthcare, architectural).
    - "experience_notes": Brief explanation of experience match.
    - "behavioral_score": Integer (0-100) scoring team leadership, coordination, and culture fit.
    - "behavioral_notes": Brief explanation of culture/leadership match.
    - "location_verdict": "PASS", "FAIL", or "REMOTE".
    - "location_notes": Commute/relocation assessment.
    - "career_score": Integer (0-100) scoring alignment with senior BIM leadership goals.
    - "career_notes": Brief explanation of career alignment.

16. "fit_score": Weighted integer (0-100) calculated as: (0.30*technical + 0.25*experience + 0.15*behavioral + 0.30*career).
17. "fit_verdict": "Strong Fit" (75+), "Good Fit" (60-74), "Moderate Fit" (45-59), "Weak Fit" (30-44), or "Poor Fit" (<30).
18. "fit_rationale": Summary paragraph explaining fit.
19. "key_strengths": List of 3-4 top selling points of Mustafa for this specific role.
20. "gaps_to_address": List of 1-2 minor gaps to proactively bridge in the application.
21. "recommendation": Actionable 1-2 sentence recommendation.

Output valid JSON only with all keys above."""

        try:
            response_text = self.ollama.generate(
                prompt=prompt,
                system=system_prompt,
                format_json=True,
                temperature=0.1,
                timeout=120,
            )

            # Strip thinking tags and markdown code blocks
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

            # Unpack requirements
            if not data.get("key_requirements") and (data.get("requirements") or data.get("skills")):
                reqs_val = data.get("requirements") or data.get("skills")
                if isinstance(reqs_val, list):
                    data["key_requirements"] = reqs_val
                elif isinstance(reqs_val, str):
                    data["key_requirements"] = [s.strip() for s in reqs_val.split("\n") if s.strip()]

            # Unpack employer questions
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

            current_comp = (data.get("company_name") or "").strip()
            if not current_comp or current_comp.lower() in [
                "confidential", "confidential / not disclosed", "target employer", "not disclosed",
                "unknown", "prospective employer",
            ]:
                if heuristics.get("detected_company"):
                    data["company_name"] = heuristics["detected_company"]
                else:
                    data["company_name"] = "Hiring Team"

            if not data.get("contact_person") and heuristics.get("detected_contact_person"):
                data["contact_person"] = heuristics["detected_contact_person"]

            if not data.get("contact_phone") and heuristics.get("detected_phone"):
                data["contact_phone"] = heuristics["detected_phone"]

            if not data.get("application_email") and heuristics.get("detected_email"):
                data["application_email"] = heuristics["detected_email"]
                data["application_method"] = "EMAIL"

            if data.get("application_email"):
                data["application_email"] = str(data["application_email"]).strip().strip(".,;:<>\"'()[]{} \t\r\n")

            if not data.get("city") and heuristics.get("city"):
                data["city"] = heuristics["city"]
            if (not data.get("country") or data.get("country") == "Unknown") and heuristics.get("country") != "Unknown":
                data["country"] = heuristics["country"]

            if heuristics.get("detected_url"):
                data["job_url"] = heuristics["detected_url"]

            if not isinstance(data.get("key_requirements"), list):
                data["key_requirements"] = ["Revit", "BIM Management", "Navisworks", "Model Coordination"]

            if not isinstance(data.get("employer_questions"), list) or not data.get("employer_questions"):
                data["employer_questions"] = heuristics.get("detected_employer_questions", [])

            # Merge eligibility gate and dimensions with fallbacks
            if not data.get("eligibility_gate") or not isinstance(data.get("eligibility_gate"), dict):
                data["eligibility_gate"] = heuristics["eligibility_gate"]

            if not data.get("dimensions") or not isinstance(data.get("dimensions"), dict):
                data["dimensions"] = heuristics["dimensions"]

            # Recalculate weighted fit score if missing or invalid
            dims = data.get("dimensions", {})
            try:
                t = int(dims.get("technical_score", 85))
                e = int(dims.get("experience_score", 85))
                b = int(dims.get("behavioral_score", 80))
                c = int(dims.get("career_score", 85))
                data["fit_score"] = round(0.30 * t + 0.25 * e + 0.15 * b + 0.30 * c)
            except Exception:
                if not data.get("fit_score"):
                    data["fit_score"] = heuristics.get("fit_score", 88)

            if not data.get("fit_verdict"):
                score = data.get("fit_score", 88)
                if data.get("eligibility_gate", {}).get("verdict") == "FAIL":
                    data["fit_verdict"] = "Excluded (Eligibility Gate Fail)"
                elif score >= 75:
                    data["fit_verdict"] = "Strong Fit"
                elif score >= 60:
                    data["fit_verdict"] = "Good Fit"
                elif score >= 45:
                    data["fit_verdict"] = "Moderate Fit"
                else:
                    data["fit_verdict"] = "Weak Fit"

            if not data.get("key_strengths"):
                data["key_strengths"] = [
                    "19+ years of extensive architectural engineering and BIM management experience.",
                    "Expert Autodesk Certified Professional proficiency in Revit and Navisworks Manage.",
                    "Proven computational automation track record using Dynamo and Python.",
                    "Track record of leadership on major complex healthcare and commercial facilities.",
                ]

            if not data.get("gaps_to_address"):
                data["gaps_to_address"] = [
                    "Highlight international relocation readiness and complete credential portfolio.",
                ]

            if not data.get("recommendation"):
                data["recommendation"] = "Apply with tailored ATS CV and personalized cover letter emphasizing complex project leadership."

            data["raw_text"] = raw_job_text
            return data

        except Exception as e:
            logger.warning(f"LLM analysis failed, falling back to heuristics: {e}")
            h = heuristics
            return {
                "job_title": h.get("detected_job_title") or "Architect / BIM Specialist",
                "company_name": h.get("detected_company") or "Hiring Team",
                "contact_person": h.get("detected_contact_person", ""),
                "contact_phone": h.get("detected_phone", ""),
                "country": h.get("country", "Australia"),
                "city": h.get("city", ""),
                "application_email": h.get("detected_email", ""),
                "job_url": h.get("detected_url", ""),
                "application_method": "EMAIL" if h.get("detected_email") else "WEBSITE_FORM",
                "visa_sponsorship": "AVAILABLE" if h["sponsorship_status"].startswith("Available") else "NOT_MENTIONED",
                "sponsorship_notes": h["sponsorship_status"],
                "key_requirements": ["Revit", "Navisworks", "BIM 360", "BIM Management", "Clash Detection"],
                "employer_questions": h.get("detected_employer_questions", []),
                "salary_range": "Not Disclosed",
                "eligibility_gate": h["eligibility_gate"],
                "dimensions": h["dimensions"],
                "fit_score": h["fit_score"],
                "fit_verdict": h["fit_verdict"],
                "fit_rationale": "Strong alignment with candidate's 19-year architectural engineering and BIM leadership experience.",
                "key_strengths": [
                    "19+ years in architectural engineering & BIM management",
                    "Expert Autodesk Revit & Navisworks proficiency",
                    "PMP certified with strong team leadership track record",
                ],
                "gaps_to_address": [
                    "Confirm international visa sponsorship and onboarding timeframe.",
                ],
                "recommendation": "Strong candidate alignment. Proceed with application.",
                "raw_text": raw_job_text,
            }
