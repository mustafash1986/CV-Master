"""
Unit tests for CV Servant Core Components:
- Candidate Master Profile validation
- Heuristic and Sponsorship Detection (Australia, Canada, New Zealand, Saudi Arabia, Kuwait)
- ATS PDF & DOCX Generation
- Excel Tracker creation, job insertion, and status update
"""
import os
from pathlib import Path
import pytest
import openpyxl

from cv_servant.master_profile import MASTER_PROFILE
from cv_servant.ai.job_analyzer import JobAnalyzer
from cv_servant.documents.pdf_generator import PDFGenerator
from cv_servant.documents.word_generator import WordGenerator
from cv_servant.tracker.excel_tracker import ExcelTracker


def test_master_profile_completeness():
    assert MASTER_PROFILE["personal_info"]["full_name"] == "MUSTAFA MAHMOUD SHAWKY"
    assert "Revit" in str(MASTER_PROFILE["core_competencies"])
    assert "PMP" in str(MASTER_PROFILE["licenses_and_certifications"])
    assert len(MASTER_PROFILE["work_experience"]) >= 3
    assert len(MASTER_PROFILE["key_projects"]) >= 5


def test_sponsorship_heuristics_australia():
    analyzer = JobAnalyzer()
    sample_job = """
    Leading Architectural firm in Sydney, Australia is looking for a Senior BIM Specialist.
    Requirements: 10+ years experience, Revit expert, Dynamo scripting.
    Visa sponsorship available under Subclass 482 (TSS) for the right candidate.
    Send your CV to careers@sydneybim.com.au
    """
    heuristics = analyzer.detect_country_and_sponsorship_heuristics(sample_job)
    assert heuristics["country"] == "Australia"
    assert "subclass 482" in [x.lower() for x in heuristics["detected_indicators"]] or "Available" in heuristics["sponsorship_status"]
    assert heuristics["detected_email"] == "careers@sydneybim.com.au"


def test_sponsorship_heuristics_canada():
    analyzer = JobAnalyzer()
    sample_job = """
    BIM Manager needed in Toronto, Canada for large healthcare infrastructure.
    LMIA approved position open for international architectural professionals.
    Apply with portfolio to hr@torontobimconsultants.ca
    """
    heuristics = analyzer.detect_country_and_sponsorship_heuristics(sample_job)
    assert heuristics["country"] == "Canada"
    assert "Available" in heuristics["sponsorship_status"]
    assert heuristics["detected_email"] == "hr@torontobimconsultants.ca"


def test_sponsorship_heuristics_saudi_arabic():
    analyzer = JobAnalyzer()
    sample_job = """
    مطلوب مهندس معماري أول ومنسق BIM للعمل بمشاريع الرياض بالمملكة العربية السعودية.
    خبرة في الريفيت والكلاش ديتكشن.
    نوفر نقل كفالة وتأشيرة عمل فورية.
    إرسال السيرة الذاتية إلى jobs@riyadh-arch.sa
    """
    heuristics = analyzer.detect_country_and_sponsorship_heuristics(sample_job)
    assert heuristics["country"] == "Saudi Arabia"
    assert "Available" in heuristics["sponsorship_status"]
    assert heuristics["detected_email"] == "jobs@riyadh-arch.sa"


def test_pdf_and_word_generation(tmp_path):
    test_pdf = tmp_path / "test_cv.pdf"
    test_docx = tmp_path / "test_cv.docx"
    test_cl = tmp_path / "test_cover_letter.docx"

    PDFGenerator.generate_resume(MASTER_PROFILE, test_pdf)
    assert test_pdf.exists()
    assert test_pdf.stat().st_size > 1000

    WordGenerator.generate_resume(MASTER_PROFILE, test_docx)
    assert test_docx.exists()
    assert test_docx.stat().st_size > 1000

    WordGenerator.generate_cover_letter(MASTER_PROFILE, test_cl)
    assert test_cl.exists()
    assert test_cl.stat().st_size > 1000


def test_excel_tracker_operations(tmp_path):
    tracker_file = tmp_path / "test_tracker.xlsx"
    tracker = ExcelTracker(file_path=tracker_file)

    job_data = {
        "company_name": "Test Engineering",
        "job_title": "Senior BIM Specialist",
        "country": "Australia",
        "city": "Sydney",
        "application_method": "EMAIL",
        "application_email": "test@test.com",
        "visa_sponsorship": "Available (TSS 482)",
        "sponsorship_notes": "Full sponsorship provided",
        "status": "Pending Approval",
    }
    job_id = tracker.add_job(job_data)
    assert job_id.startswith("JOB-")

    all_jobs = tracker.get_all_jobs()
    assert len(all_jobs) == 1
    assert all_jobs[0]["company_name"] == "Test Engineering"
    assert all_jobs[0]["status"] == "Pending Approval"

    # Test Status Update
    updated = tracker.update_job_status(job_id, "Applied / Sent", notes="Emailed portfolio")
    assert updated is True

    all_jobs_updated = tracker.get_all_jobs()
    assert all_jobs_updated[0]["status"] == "Applied / Sent"
    assert "Emailed portfolio" in all_jobs_updated[0]["notes"]
