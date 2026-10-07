---
name: ai-job-evaluator
version: 1.0.0
description: >
  Evaluates job postings against Eng. Mustafa Mahmoud Shawky's candidate profile using
  the 5-Dimension Scoring Matrix and Eligibility Gate (Citizenship, Work Rights, Visa Sponsorship).
  Trigger phrases: evaluate this job, score this job, job fit analysis, visa eligibility check,
  assess vacancy, analyze job posting.
context: fork
enabled: true
allowed-tools: RunCommand(python -c "from cv_servant.ai.job_analyzer import JobAnalyzer; import sys; print(JobAnalyzer().analyze_job(open(sys.argv[1]).read()))" *)
---

# 5-Dimension Job Evaluation & Eligibility Gate Skill

Evaluates job postings using the rigorous scoring framework from `ai-job-search` adapted for Eng. Mustafa Mahmoud Shawky (19+ years experience, Senior Architect, BIM Manager, PMP, Revit, Dynamo, Navisworks).

## 1. Eligibility Gate (Hard Filter)
Evaluated before scoring:
- **Citizenship / PR Requirement**: If posting explicitly demands "Australian Citizen only", "Canadian Citizen only", or "Must hold existing PR/Citizenship" with no sponsorship -> **FAIL (Hard Stop)**.
- **Security Clearance**: NV1 / NV2 / Baseline clearance requirement -> **FAIL** (requires citizenship).
- **Visa Sponsorship / International**: Explicitly states "Visa sponsorship available", "TSS 482", "LMIA", or "International applicants welcome" -> **PASS**.
- **Silent on Citizenship**: **UNVERIFIED / PROCEED** with caution.

## 2. 5-Dimension Scoring Matrix (0-100)

| Dimension | Weight | Description |
|---|---|---|
| **Technical Skills Match** | 30% | Revit, Navisworks, BIM 360/ACC, Dynamo, Python, ISO 19650, Clash Detection, dRofus |
| **Experience Match** | 25% | 19 years in architectural engineering, mega-projects, healthcare, commercial, residential |
| **Behavioral / Culture Fit** | 15% | Leadership, team mentoring, interdisciplinary coordination, BIM execution planning |
| **Location & Logistics** | Pass/Fail | Australia, Canada, New Zealand, Saudi Arabia, Kuwait, Remote/Hybrid |
| **Career Alignment** | 30% | Senior BIM Manager, Computational Design Lead, Digital Delivery Director |

### Overall Fit Score & Verdict
$$\text{Score} = (0.30 \times \text{Technical}) + (0.25 \times \text{Experience}) + (0.15 \times \text{Behavioral}) + (0.30 \times \text{Career})$$

- **75 - 100**: Strong Fit (Definite match; tailor CV and Cover Letter)
- **60 - 74**: Good Fit (Address minor gaps in cover letter)
- **45 - 59**: Moderate Fit (Carefully weigh options)
- **30 - 44**: Weak Fit (Skip unless strategic)
- **< 30**: Poor Fit (Do not apply)
