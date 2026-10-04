"""
ATS Tailoring Engine:
Customizes resume summary, skills emphasis, cover letters, and email copy
to achieve a 95%+ ATS keyword score without fabricating facts.
"""
import json
import logging
from typing import Any, Dict, Optional

from cv_servant.ai.ollama_client import OllamaClient
from cv_servant.master_profile import MASTER_PROFILE

logger = logging.getLogger(__name__)


class ATSTailor:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama = ollama_client or OllamaClient()

    def generate_tailored_package(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates tailored resume summary, customized cover letter, and email draft.
        """
        job_title = job_data.get("job_title", "Senior Architect & BIM Specialist")
        company = job_data.get("company_name", "Prospective Employer")
        country = job_data.get("country", "")
        requirements = ", ".join(job_data.get("key_requirements", []))

        system_prompt = (
            "You are a top-tier executive career strategist and ATS optimization expert for senior architects and BIM leaders. "
            "Tailor the candidate's authentic credentials to match the target job description with maximum ATS alignment."
        )

        prompt = f"""
Candidate: Mustafa Mahmoud Shawky (19 years experience, Senior Architect & BIM Specialist / Manager, PMP certified, Revit Expert, Dynamo, Python, BEFA eligible).
Target Job Title: {job_title}
Target Company: {company}
Target Country/Location: {country}
Key Requirements: {requirements}

Generate a JSON object with EXACTLY these fields:
1. "tailored_title": An impactful professional title aligning with the job (e.g., "Senior Architect & BIM Specialist" or "BIM Manager / Computational Architect").
2. "tailored_summary": A high-impact 4-5 line professional summary emphasizing exact keywords, years of experience, relevant project types (KUHSC healthcare, Dubai Iconic Tower, KGOC), and BIM automation.
3. "top_keywords": A list of 8-10 high-value ATS keywords relevant to this specific role.
4. "cover_letter": A formal, compelling cover letter (3-4 concise paragraphs) addressed to the Hiring Team at {company}, demonstrating value, referencing major achievements, and noting work authorization readiness.
5. "email_subject": A crisp, professional subject line (e.g. "Application: {job_title} - Mustafa Mahmoud Shawky, PMP, Revit Expert").
6. "email_body": A succinct, professional outreach email body (150-200 words) referencing the attached CV and portfolio.
"""
        try:
            response = self.ollama.generate(
                prompt=prompt,
                system=system_prompt,
                format_json=True,
                temperature=0.3,
                timeout=120,
            )
            tailored = json.loads(response)
        except Exception as e:
            logger.warning(f"ATS tailoring generation fallback: {e}")
            tailored = {
                "tailored_title": f"{job_title} | PMP® | Autodesk Certified",
                "tailored_summary": MASTER_PROFILE["professional_summary"],
                "top_keywords": ["Revit", "BIM Management", "Dynamo", "Python", "Clash Detection", "PMP"],
                "cover_letter": (
                    f"Dear Hiring Team at {company},\n\n"
                    f"I am writing to express my enthusiastic interest in the {job_title} position. "
                    f"With over 19 years of architectural engineering and BIM management experience on landmark projects "
                    f"including the Kuwait University Health Sciences Center and the Dubai Iconic Tower, I bring proven leadership "
                    f"in Revit coordination, BIM automation with Dynamo/Python, and multidisciplinary delivery.\n\n"
                    f"I look forward to discussing how my experience aligns with your upcoming projects.\n\n"
                    f"Sincerely,\nMustafa Mahmoud Shawky\n{MASTER_PROFILE['personal_info']['phone']}"
                ),
                "email_subject": f"Application for {job_title} - Mustafa Mahmoud Shawky, PMP",
                "email_body": (
                    f"Dear Hiring Team at {company},\n\n"
                    f"Please accept my application for the {job_title} position. "
                    f"Attached you will find my detailed ATS-optimized Curriculum Vitae and portfolio highlights.\n\n"
                    f"With 19 years of experience spearheading BIM and architectural delivery for complex institutional and commercial developments, "
                    f"I welcome the opportunity to contribute to your team's success.\n\n"
                    f"Best regards,\nMustafa Mahmoud Shawky\nSenior Architect & BIM Specialist\n+965 9919 1358\n"
                    f"arch.mustafa.mahmoud.2007@gmail.com"
                )
            }

        # Merge base profile with tailored summary
        final_profile = dict(MASTER_PROFILE)
        final_profile["tailored_title"] = tailored.get("tailored_title", MASTER_PROFILE["personal_info"]["title"])
        final_profile["tailored_summary"] = tailored.get("tailored_summary", MASTER_PROFILE["professional_summary"])
        final_profile["top_keywords"] = tailored.get("top_keywords", [])
        final_profile["cover_letter"] = tailored.get("cover_letter", "")
        final_profile["email_subject"] = tailored.get("email_subject", "")
        final_profile["email_body"] = tailored.get("email_body", "")

        return final_profile
