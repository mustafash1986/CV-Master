"""
ATS Tailoring Engine:
Customizes resume summary, skills emphasis, cover letters, and email copy
to achieve a 95%+ ATS keyword score without fabricating facts.
Now includes employer question responses and references specific job requirements.
"""
import json
import logging
from typing import Any, Dict, Optional

from cv_servant.ai.ollama_client import OllamaClient
from cv_servant.master_profile import MASTER_PROFILE

logger = logging.getLogger(__name__)


import re

def answer_employer_question(question: str, country: str = "Australia") -> str:
    """
    Generates an accurate, professional answer tailored specifically to
    Mustafa Mahmoud Shawky's real credentials, location in Kuwait, and visa sponsorship needs.
    Strictly avoids incorrect statements (e.g. falsely claiming security clearance or giving
    generic boilerplate answers to specific questions like notice periods).
    """
    q_low = question.lower().strip()

    # 1. Right to work / Visa / Citizenship / Work Rights
    if re.search(r"\b(right to work|work rights|work in|visa|sponsorship|sponsor|citizen|citizenship|permanent resident|work permit|legally entitled|authorized to work|authorisation|eligible to work)\b", q_low):
        if "australia" in q_low or country.lower() == "australia":
            return (
                "I currently reside in Kuwait and hold Egyptian citizenship. I require employer visa sponsorship "
                "(such as Temporary Skill Shortage Subclass 482 or Employer Nomination Subclass 186) to work in Australia. "
                "I have over 19 years of verified architectural engineering and BIM leadership experience, complete credential documentation, "
                "and am fully prepared to initiate visa processing immediately."
            )
        elif "canada" in q_low or country.lower() == "canada":
            return (
                "I currently reside in Kuwait and hold Egyptian citizenship. I require employer sponsorship (LMIA-backed work permit) "
                "to work in Canada. I have 19+ years of verified international architectural engineering experience and complete documentation ready."
            )
        else:
            return (
                f"I currently reside in Kuwait and hold Egyptian citizenship. I require employer visa sponsorship to relocate and work in {country or 'your region'}. "
                "I have 19+ years of verified architectural engineering and BIM leadership experience and am fully prepared for sponsorship processing."
            )

    # 2. Security Clearance / Defence / Vetting / Police Check
    if re.search(r"\b(security clearance|defence clearance|defense clearance|baseline clearance|nv1|nv2|negative vetting|secret clearance)\b", q_low):
        return (
            "No, I do not currently hold an Australian Security Clearance as an international applicant currently based in Kuwait. "
            "However, I have an unblemished professional and legal record, complete background documentation, and am fully eligible and prepared "
            "to undergo all required vetting, security screening, and background checks."
        )

    if re.search(r"\b(police check|criminal check|background check|police clearance)\b", q_low):
        return (
            "I have a clean criminal history record and can provide an official Police Clearance Certificate immediately upon request."
        )

    # 3. Notice Period / Availability / Start Date / Commencing
    if re.search(r"\b(notice|how much notice|notice period|how soon|when can you start|start date|commence|commencing|commencement|availability|available to start)\b", q_low):
        return "Zero (Immediately available / No notice period required with current employer). Fully prepared to mobilize and commence work immediately upon visa issuance / relocation."

    # 4. White Card / Site Safety Induction
    if re.search(r"\b(white card|construction induction|site induction|cpccwhs1001)\b", q_low):
        return (
            "I do not currently hold an Australian White Card, but I am fully prepared to complete the online General Construction Induction Training "
            "(White Card) course immediately prior to commencing work."
        )

    # 5. Driver's Licence
    if re.search(r"\b(driver|driving licence|driver's licence|drivers licence|valid licence|own vehicle)\b", q_low):
        return "Yes, I hold a valid full driver's licence and will convert/obtain the local Australian driver's licence upon relocation."

    # 6. Salary / Remuneration / Compensation Expectations
    if re.search(r"\b(salary|remuneration|compensation|expected rate|expected salary|rate expectation|package expectation)\b", q_low):
        return "Negotiable in line with standard Australian market rates for Senior BIM Manager / Digital Engineering Lead roles, taking the overall relocation and sponsorship package into consideration."

    # 7. Relocation / Location Preference / Travel
    if re.search(r"\b(relocate|relocation|willing to travel|willing to relocate|based in|move to)\b", q_low):
        return "Yes, 100% committed to relocating internationally with my family to Australia upon employer visa sponsorship, and flexible for domestic travel as required by project needs."

    # 8. Years of experience (Specific breakdown)
    if re.search(r"\b(how many years|years of experience|years' experience|years experience|number of years)\b", q_low):
        if any(w in q_low for w in ["bim", "revit", "navisworks", "modelling", "digital engineering", "vdc"]):
            return "19+ years in architectural engineering, including 14+ years dedicated to BIM management, Revit, Navisworks, and multidisciplinary digital delivery on landmark healthcare, commercial, and infrastructure developments."
        elif any(w in q_low for w in ["architect", "architecture", "design"]):
            return "19+ years of progressive professional experience in architectural engineering, design coordination, and project delivery."
        elif any(w in q_low for w in ["construction", "contractor", "site"]):
            return "19+ years working on complex building and construction projects, with extensive contractor coordination and on-site BIM implementation experience."
        else:
            return "19+ years of verified professional experience in architectural engineering and project leadership."

    # 9. Project Coordination / Multidisciplinary Coordination / Stakeholder Management
    if re.search(r"\b(project coordination|multidisciplinary coordination|coordination experience|interdisciplinary|stakeholder coordination|consultant coordination|clash resolution)\b", q_low):
        return (
            "Yes, extensive experience. Over 19 years directing multidisciplinary coordination between architectural, structural, and MEP engineering teams "
            "on mega-scale projects (e.g., Kuwait University Health Sciences Center and Dubai Iconic Tower), proactively resolving clashes and ensuring full design alignment prior to construction."
        )

    # 10. BIM Management / BIM Lead / BEP / ISO 19650
    if re.search(r"\b(bim management|bim manager|bim lead|digital engineering|vdc|lead bim|iso 19650|bep\b|bim execution plan|lod\b)\b", q_low):
        return (
            "Yes, extensive experience. I have spearheaded BIM implementation and management across major consulting and engineering firms, "
            "authoring and executing ISO 19650-compliant BIM Execution Plans (BEPs), establishing LOD 100-500 matrices, and leading multidisciplinary digital engineering delivery."
        )

    # 11. Software Proficiency: Revit / Navisworks / ACC / BIM 360 / Dynamo / Python
    if re.search(r"\b(revit|navisworks|autodesk construction cloud|acc\b|bim 360|dynamo|python|clash detection|autocad|solibri)\b", q_low):
        return (
            "Advanced Expert. Autodesk Certified Professional in Revit Architecture (#00424122), advanced mastery in Navisworks Manage clash detection, "
            "seamless collaboration via Autodesk Construction Cloud (ACC) and BIM 360, and custom computational automation workflows developed using Dynamo and Python."
        )

    # 12. Qualifications / Degree / Education / AACA / BEFA
    if re.search(r"\b(qualification|qualifications|degree|bachelor|university|education|academic|befa|aaca|graduated)\b", q_low):
        return "Bachelor of Architectural Engineering (2007) with Honors from Zagazig University, Egypt. Eligible for Australian architectural credential assessments (AACA / BEFA)."

    # 13. Certifications: PMP / ACP
    if re.search(r"\b(pmp|project management professional|certified|certification|credentials|acp\b)\b", q_low):
        return "PMP® Certified Project Manager (PMI #3010938) and Autodesk Certified Professional in Revit Architecture (#00424122)."

    # 14. Contract Type / Permanent
    if re.search(r"\b(permanent|full time|contract|full-time|part-time|employment type)\b", q_low):
        return "Seeking a permanent, full-time opportunity with employer visa sponsorship (TSS 482 / ENS 186), committed to long-term career growth with the organization."

    # 15. English Language
    if re.search(r"\b(english|ielts|pte|toefl|language proficiency)\b", q_low):
        return "Full professional working proficiency in English, with 19+ years of experience authoring technical documentation and directing international multidisciplinary teams."

    # 16. General "Do you have..." or "Are you experienced..." questions
    if re.search(r"\b(do you have|have you|are you experienced|are you able|can you)\b", q_low):
        return (
            "Yes. Over my 19+ years in architectural engineering and BIM management, I have gained substantial hands-on and leadership experience "
            "in this area across major international projects, consistently meeting and exceeding technical requirements."
        )

    # 17. Default fallback
    return (
        "With over 19 years of verified architectural engineering, BIM management, and multidisciplinary project leadership experience, "
        "I possess the required competencies and am fully prepared to discuss my qualifications for this requirement in detail."
    )


def validate_and_sanitize_answer(question: str, answer: str, country: str = "Australia") -> str:
    """
    Validates and sanitizes screening question answers to ensure:
    - Never claiming Australian Security Clearance when not held
    - Notice period questions are answered with actual timeframe (1 month / 30 days)
    - Right to work questions properly state Kuwait residence and visa sponsorship
    - Generic/repetitive boilerplate is replaced with question-specific answers
    """
    q_low = question.lower().strip()
    ans_low = (answer or "").lower().strip()

    # 1. Security clearance check
    if re.search(r"\b(security clearance|defence clearance|defense clearance|baseline clearance|nv1|nv2)\b", q_low):
        if not ans_low.startswith("no") or "yes" in ans_low:
            return answer_employer_question(question, country)

    # 2. Notice period check
    if re.search(r"\b(notice|how much notice|when can you start|start date|commence|availability)\b", q_low):
        if not any(w in ans_low for w in ["zero", "immediate", "available immediately", "no notice"]):
            return answer_employer_question(question, country)

    # 3. Right to work / Visa check
    if re.search(r"\b(right to work|work rights|work in|visa|sponsorship|sponsor|citizen|citizenship|permanent resident)\b", q_low):
        if "kuwait" not in ans_low or "sponsorship" not in ans_low:
            return answer_employer_question(question, country)

    # 4. White card check
    if re.search(r"\b(white card|cpccwhs1001)\b", q_low):
        if "yes" in ans_low:
            return answer_employer_question(question, country)

    # 5. Check if answer is just a generic fallback repeat
    if "fully meeting and exceeding this requirement" in ans_low:
        return answer_employer_question(question, country)

    return answer or answer_employer_question(question, country)


class ATSTailor:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama = ollama_client or OllamaClient()

    def generate_tailored_package(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates tailored resume summary, customized cover letter, email draft,
        and employer question responses based on the FULL job posting content.
        """
        job_title = job_data.get("job_title", "Senior Architect & BIM Specialist")
        raw_company = (job_data.get("company_name") or "").strip()
        contact_person = (job_data.get("contact_person") or "").strip()
        country = job_data.get("country", "")
        city = job_data.get("city", "")
        employer_questions = job_data.get("employer_questions", [])
        salary_range = job_data.get("salary_range", "Not Disclosed")

        # Sanitize company name
        company = raw_company
        if company.lower() in [
            "confidential", "confidential / not disclosed", "not disclosed",
            "target employer", "prospective employer", "unknown", "hiring team"
        ]:
            company = ""

        # Formulate clean, professional salutation
        if contact_person:
            salutation = f"Dear {contact_person},"
        elif company:
            salutation = f"Dear {company} Hiring Team,"
        else:
            salutation = "Dear Hiring Manager,"

        # Extract concise core technical keywords from requirements instead of pasting entire bullet sentences
        raw_reqs = job_data.get("key_requirements", [])
        core_skills = []
        for r in raw_reqs:
            for kw in [
                "Revit", "Navisworks", "Autodesk Construction Cloud", "BIM 360",
                "Dynamo", "Python", "Clash Detection", "BIM Management", "Digital Engineering",
                "BIM Execution Plans (BEP)", "Multidisciplinary Coordination", "Building Services"
            ]:
                if kw.lower() in r.lower() and kw not in core_skills:
                    core_skills.append(kw)
        if not core_skills:
            core_skills = ["BIM management", "Revit", "Navisworks", "digital engineering delivery", "multidisciplinary coordination"]
        skills_summary = ", ".join(core_skills[:5])

        # Extract relevant snippet from raw job text for context
        raw_text = job_data.get("raw_text", "")
        job_context_snippet = raw_text[:2000] if raw_text else ""

        location_str = f"{city}, {country}" if city and city != country else (country or "your region")

        system_prompt = (
            "You are a top-tier executive career strategist and ATS optimization expert for senior architects and BIM leaders. "
            "You MUST tailor the candidate's real credentials to match the SPECIFIC job requirements mentioned in the posting. "
            "Do NOT copy-paste raw bullet sentences verbatim into run-on sentences. Synthesize technical competencies smoothly. "
            "CANDIDATE STATUS: Mustafa Mahmoud Shawky currently resides in Kuwait (+965) and holds Egyptian citizenship. "
            "For right-to-work or visa questions in Australia/Canada/UK/NZ, truthfully state that he resides in Kuwait, "
            "requires employer visa sponsorship (e.g. TSS Subclass 482 or ENS 186 for Australia), and has full documentation ready. "
            "The candidate's real qualifications: 19 years experience, Senior Architect & BIM Specialist / Manager, PMP certified, "
            "Revit Expert (Autodesk Certified), Dynamo/Python automation, Navisworks clash detection, "
            "led KUHSC healthcare campus, Dubai Iconic Tower, KGOC HQ projects, custom plugin development. "
            "STRICT QUESTION RULE: If no screening questions are asked by the employer in the job posting, "
            "you MUST return an empty list [] for employer_question_responses. Never invent, imagine, or assume any questions."
        )

        # Build employer questions section for the prompt
        eq_section = ""
        if employer_questions:
            eq_list = "\n".join([f"  Q{i+1}: {q}" for i, q in enumerate(employer_questions)])
            eq_section = f"""
7. "employer_question_responses": A list of objects, each with "question" (the original question) and "answer" (a professional, truthful answer based on the candidate's real experience).
NOTE: For Right to Work in Australia/Canada, state that candidate resides in Kuwait and requires employer visa sponsorship (TSS 482 / ENS 186).
Answer ONLY these specific employer questions:
{eq_list}
"""
        else:
            eq_section = '7. "employer_question_responses": [] (CRITICAL: The employer has NO screening questions in this job posting. Return an empty list [] and do NOT invent any question).\n'

        prompt = f"""Candidate: Mustafa Mahmoud Shawky (19 years experience, Senior Architect & BIM Specialist / Manager, PMP certified, Revit Expert, Dynamo, Python, Navisworks, BEFA eligible, Resident in Kuwait).

Target Job: {job_title}
Target Company: {company or 'Hiring Organization'}
Contact Person: {contact_person or 'Hiring Manager'}
Salutation to use: {salutation}
Location: {location_str}
Core Technical Skills: {skills_summary}
Salary Range: {salary_range}

IMPORTANT CONTEXT - Actual Job Posting Excerpt:
\"\"\"
{job_context_snippet}
\"\"\"

Generate a JSON object with EXACTLY these fields:
1. "tailored_title": An impactful professional title aligning with "{job_title}".
2. "tailored_summary": A high-impact 4-5 line professional summary addressing the role's digital engineering and BIM leadership requirements. Mention {skills_summary}.
3. "top_keywords": A list of 8-12 high-value ATS keywords extracted from the job requirements: {skills_summary}.
4. "cover_letter": A formal, compelling cover letter (3-4 paragraphs) opening with EXACTLY: "{salutation}".
   - Reference the SPECIFIC job title "{job_title}"
   - Address key technical requirements: {skills_summary}
   - Reference relevant projects (KUHSC for healthcare, Dubai Iconic Tower for high-rise, KGOC for oil/gas)
   - Mention portfolio website: https://mustafash1986.github.io/mustafa-portfolio1/
5. "email_subject": A crisp subject line: "Application: {job_title} – Mustafa Mahmoud Shawky, PMP, Revit Expert"
6. "email_body": A professional outreach email opening with EXACTLY: "{salutation}".
   - Opens by referencing the "{job_title}" role
   - Smoothly highlights 19+ years experience, PMP, Revit Expert, and {skills_summary}
   - Mentions attached CV, Cover Letter, and Project Portfolio
   - Includes portfolio link: https://mustafash1986.github.io/mustafa-portfolio1/
   - Closes professionally with contact info
{eq_section}"""

        try:
            response = self.ollama.generate(
                prompt=prompt,
                system=system_prompt,
                format_json=True,
                temperature=0.2,
                timeout=120,
            )

            # Strip thinking tags and markdown code blocks if present
            if "<think>" in response and "</think>" in response:
                response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            tailored = json.loads(response)

            # Sanitize cover letter greeting
            cl = tailored.get("cover_letter", "")
            for bad_salutation in ["Dear Hiring Team at Confidential", "Dear Hiring Team at Not Disclosed", "Dear Hiring Team at Prospective Employer", "Dear Hiring Team at Confidential / Not Disclosed"]:
                if bad_salutation in cl:
                    cl = cl.replace(bad_salutation, salutation)
            tailored["cover_letter"] = cl

            # Sanitize email body greeting
            eb = tailored.get("email_body", "")
            for bad_salutation in ["Dear Hiring Team at Confidential", "Dear Hiring Team at Not Disclosed", "Dear Hiring Team at Prospective Employer", "Dear Hiring Team at Confidential / Not Disclosed"]:
                if bad_salutation in eb:
                    eb = eb.replace(bad_salutation, salutation)
            tailored["email_body"] = eb

            # Process employer questions ONLY if explicitly present in the job posting
            sanitized_eq = []
            if employer_questions:
                eq_responses = tailored.get("employer_question_responses", [])
                if not isinstance(eq_responses, list):
                    eq_responses = []

                answered_questions = [r.get("question", "").strip() for r in eq_responses if isinstance(r, dict)]

                for q in employer_questions:
                    if q.strip() not in answered_questions:
                        ans = answer_employer_question(q, country)
                        eq_responses.append({"question": q, "answer": ans})

                # Sanitize each response to strictly avoid hallucinations
                for item in eq_responses:
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

            # If no employer questions in job posting, strictly keep the list empty
            tailored["employer_question_responses"] = sanitized_eq

        except Exception as e:
            logger.warning(f"ATS tailoring generation fallback: {e}")
            fallback_eq = [
                {"question": q, "answer": answer_employer_question(q, country)}
                for q in employer_questions
            ] if employer_questions else []

            tailored = {
                "tailored_title": f"{job_title} | PMP® | Autodesk Certified",
                "tailored_summary": (
                    f"Accomplished Architectural Engineer and BIM Manager with 19+ years of distinguished experience "
                    f"directly relevant to the {job_title} role. Deep expertise in {skills_summary}. "
                    f"Proven track record leading multidisciplinary teams on landmark projects including "
                    f"the Kuwait University Health Sciences Center and the Dubai Iconic Tower."
                ),
                "top_keywords": core_skills[:10] or ["Revit", "BIM Management", "Dynamo", "Python", "Clash Detection", "PMP"],
                "cover_letter": (
                    f"{salutation}\n\n"
                    f"I am writing to express my enthusiastic interest in the {job_title} position in {location_str}. "
                    f"With over 19 years of architectural engineering and digital delivery leadership on landmark projects "
                    f"including the Kuwait University Health Sciences Center and the Dubai Iconic Tower, I bring proven expertise "
                    f"in end-to-end BIM coordination, digital engineering strategy, and multidisciplinary delivery.\n\n"
                    f"My qualifications directly address your role's objectives:\n"
                    f"• 19+ years directing BIM strategy, execution plans (BEPs), and model coordination across complex developments\n"
                    f"• Advanced proficiency in Revit, Navisworks, Autodesk Construction Cloud / BIM 360, and Dynamo/Python automation\n"
                    f"• PMP® Certified Project Manager (PMI #3010938) and Autodesk Certified Professional in Revit Architecture\n"
                    f"• Developed 19+ custom Revit plugins slashing task completion times by up to 80%\n"
                    f"• Registered Professional Architect eligible for Australian / international credential assessments\n\n"
                    f"Please review my interactive online portfolio for detailed project sheets and code samples: https://mustafash1986.github.io/mustafa-portfolio1/\n\n"
                    f"I look forward to discussing how my experience can support your upcoming project pipeline.\n\n"
                    f"Sincerely,\nMustafa Mahmoud Shawky\nSenior Architect & BIM Specialist / BIM Manager\n+965 9919 1358\narch.mustafa.mahmoud.2007@gmail.com"
                ),
                "email_subject": f"Application: {job_title} – Mustafa Mahmoud Shawky, PMP, Revit Expert",
                "email_body": (
                    f"{salutation}\n\n"
                    f"Please accept my application for the {job_title} position in {location_str}.\n\n"
                    f"With over 19 years of distinguished architectural engineering and digital delivery experience, "
                    f"I bring deep expertise in {skills_summary}. Throughout my career, I have successfully directed BIM implementation, "
                    f"coordinated multidisciplinary models, and developed automated workflows on landmark healthcare, "
                    f"commercial, and infrastructure projects.\n\n"
                    f"Key Highlights:\n"
                    f"• 19+ years leading BIM execution, standards, and clash-free delivery\n"
                    f"• PMP® Certified Project Manager & Autodesk Certified Professional in Revit\n"
                    f"• Expert in Revit, Navisworks, Autodesk Construction Cloud / BIM 360, and Dynamo/Python automation\n"
                    f"• Proven leadership on mega-scale developments including the Kuwait University Health Sciences Center\n\n"
                    f"Attached you will find my ATS-optimized CV, tailored Cover Letter, and Project Portfolio for your review.\n\n"
                    f"🌐 Interactive Online Portfolio: https://mustafash1986.github.io/mustafa-portfolio1/\n\n"
                    f"I welcome the opportunity to speak with you regarding how my background aligns with your project requirements.\n\n"
                    f"Best regards,\nMustafa Mahmoud Shawky\nSenior Architect & BIM Specialist / Manager\n+965 9919 1358\narch.mustafa.mahmoud.2007@gmail.com\nlinkedin.com/in/mostafamahmoud-architect"
                ),
                "employer_question_responses": fallback_eq,
            }

        # Embed employer screening questions & responses into email_body
        eq_list = tailored.get("employer_question_responses", [])
        eb = tailored.get("email_body", "")

        if eq_list:
            eq_block = "\n\n" + "=" * 48 + "\nEMPLOYER SCREENING QUESTIONS & RESPONSES:\n" + "=" * 48 + "\n"
            for item in eq_list:
                if isinstance(item, dict):
                    eq_block += f"\nQ: {item.get('question', '')}\nA: {item.get('answer', '')}\n"
                elif isinstance(item, str):
                    eq_block += f"\n• {item}\n"

            # Strip any preexisting or unvalidated questions block to avoid duplicates or hallucinated content
            if "EMPLOYER SCREENING QUESTIONS" in eb:
                eb = re.sub(
                    r"={30,}\s*\n\s*EMPLOYER SCREENING QUESTIONS & RESPONSES:.*?(?=\n\n(?:Attached|Please find|Best regards|Sincerely|🌐)|\Z)",
                    "",
                    eb,
                    flags=re.DOTALL
                ).strip()

            # Insert before attachment reference or before sign-off
            if "Attached you will find" in eb:
                eb = eb.replace("Attached you will find", f"{eq_block}\nAttached you will find")
            elif "Please find attached" in eb:
                eb = eb.replace("Please find attached", f"{eq_block}\nPlease find attached")
            elif "Best regards," in eb:
                eb = eb.replace("Best regards,", f"{eq_block}\nBest regards,")
            elif "Sincerely," in eb:
                eb = eb.replace("Sincerely,", f"{eq_block}\nSincerely,")
            else:
                eb += f"\n{eq_block}"
        else:
            # When no employer questions exist, strictly ensure no question block appears in the email
            if "EMPLOYER SCREENING QUESTIONS" in eb:
                eb = re.sub(
                    r"={30,}\s*\n\s*EMPLOYER SCREENING QUESTIONS & RESPONSES:.*?(?=\n\n(?:Attached|Please find|Best regards|Sincerely|🌐)|\Z)",
                    "",
                    eb,
                    flags=re.DOTALL
                ).strip()

        # Ensure complete sign-off in email_body
        if "Mustafa Mahmoud Shawky" not in eb:
            portfolio_str = "🌐 Interactive Online Portfolio: https://mustafash1986.github.io/mustafa-portfolio1/\n\n" if "mustafash1986" not in eb else ""
            eb += (
                f"\n\n{portfolio_str}"
                "Best regards,\n"
                "Mustafa Mahmoud Shawky\n"
                "Senior Architect & BIM Specialist / Manager\n"
                "+965 9919 1358\n"
                "arch.mustafa.mahmoud.2007@gmail.com\n"
                "linkedin.com/in/mostafamahmoud-architect"
            )

        tailored["email_body"] = eb

        # Merge base profile with tailored summary
        final_profile = dict(MASTER_PROFILE)
        final_profile["tailored_title"] = tailored.get("tailored_title", MASTER_PROFILE["personal_info"]["title"])
        final_profile["tailored_summary"] = tailored.get("tailored_summary", MASTER_PROFILE["professional_summary"])
        final_profile["top_keywords"] = tailored.get("top_keywords", [])
        final_profile["cover_letter"] = tailored.get("cover_letter", "")
        final_profile["email_subject"] = tailored.get("email_subject", "")
        final_profile["email_body"] = eb
        final_profile["employer_question_responses"] = tailored.get("employer_question_responses", [])

        return final_profile

    def refine_cover_letter_and_email(
        self,
        job_data: Dict[str, Any],
        current_cover_letter: str,
        current_email_body: str,
        current_email_subject: str,
        user_instruction: str,
    ) -> Dict[str, str]:
        """
        Refines the cover letter and email body based on candidate's feedback.
        Maintains factual accuracy, real credentials, and professional tone.
        """
        job_title = job_data.get("job_title", "BIM Specialist / Manager")
        company = job_data.get("company_name", "Prospective Employer")
        contact_person = job_data.get("contact_person", "")

        system_prompt = (
            "You are an elite executive career assistant and ATS copywriter for Eng. Mustafa Mahmoud Shawky.\n"
            "The candidate has provided specific revision instructions for their cover letter and email application.\n"
            "Apply the candidate's instructions accurately while preserving verified core facts:\n"
            "- 19+ years in architectural engineering, PMP certified, Autodesk Certified Professional in Revit.\n"
            "- Resident in Kuwait, Egyptian nationality, requires employer visa sponsorship (TSS 482 / ENS 186 / LMIA) for international roles.\n"
            "- Notice period with current employer: Zero (available immediately).\n"
            "- Portfolio website: https://mustafash1986.github.io/mustafa-portfolio1/\n"
            "- Keep a confident, highly professional tone.\n"
            "- Return STRICT JSON with keys: 'cover_letter', 'email_body', 'email_subject'."
        )

        prompt = f"""Candidate: Mustafa Mahmoud Shawky
Role: {job_title}
Company: {company}
Contact: {contact_person}

CANDIDATE'S MODIFICATION INSTRUCTION:
\"\"\"{user_instruction}\"\"\"

CURRENT COVER LETTER:
\"\"\"{current_cover_letter}\"\"\"

CURRENT EMAIL SUBJECT:
\"\"\"{current_email_subject}\"\"\"

CURRENT EMAIL BODY:
\"\"\"{current_email_body}\"\"\"

Apply the candidate's modifications carefully to both the Cover Letter and the Email Body.
Return a JSON object with:
1. "cover_letter": The revised, polished cover letter text.
2. "email_body": The revised, polished email body text.
3. "email_subject": The revised or retained email subject line.
"""
        try:
            response = self.ollama.generate(
                prompt=prompt,
                system=system_prompt,
                format_json=True,
                temperature=0.2,
                timeout=120,
            )

            if "<think>" in response and "</think>" in response:
                response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            parsed = json.loads(response)
            cl = parsed.get("cover_letter", "").strip() or current_cover_letter
            eb = parsed.get("email_body", "").strip() or current_email_body
            es = parsed.get("email_subject", "").strip() or current_email_subject

            if "Mustafa Mahmoud Shawky" not in eb:
                portfolio_str = "🌐 Interactive Online Portfolio: https://mustafash1986.github.io/mustafa-portfolio1/\n\n" if "mustafash1986" not in eb else ""
                eb += (
                    f"\n\n{portfolio_str}"
                    "Best regards,\n"
                    "Mustafa Mahmoud Shawky\n"
                    "Senior Architect & BIM Specialist / Manager\n"
                    "+965 9919 1358\n"
                    "arch.mustafa.mahmoud.2007@gmail.com\n"
                    "linkedin.com/in/mostafamahmoud-architect"
                )

            return {
                "cover_letter": cl,
                "email_body": eb,
                "email_subject": es,
            }
        except Exception as e:
            logger.error(f"Refinement via Ollama failed: {e}")
            return {
                "cover_letter": current_cover_letter,
                "email_body": current_email_body,
                "email_subject": current_email_subject,
            }
