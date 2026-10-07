"""
Tests for ai-job-search skills and Qwen 3.5 5-Dimension Evaluation integration.
"""
from cv_servant.ai.job_analyzer import JobAnalyzer
from cv_servant.hunter.job_hunter import LiveJobHunter


def test_eligibility_gate_pass_on_sponsorship():
    analyzer = JobAnalyzer()
    text = (
        "BIM Manager wanted in Melbourne, Australia. "
        "We welcome international applicants and visa sponsorship (TSS 482 / Subclass 186) is available."
    )
    res = analyzer.detect_country_and_sponsorship_heuristics(text)
    assert res["eligibility_gate"]["verdict"] == "PASS"
    assert "Available" in res["sponsorship_status"]
    assert res["dimensions"]["technical_score"] >= 75
    assert res["dimensions"]["experience_score"] >= 80


def test_eligibility_gate_fail_on_citizenship_restriction():
    analyzer = JobAnalyzer()
    text = (
        "Project BIM Coordinator in Canberra. "
        "Candidate MUST BE AN AUSTRALIAN CITIZEN with Baseline Clearance. No visa sponsorship provided."
    )
    res = analyzer.detect_country_and_sponsorship_heuristics(text)
    assert res["eligibility_gate"]["verdict"] == "FAIL"
    assert res["fit_verdict"] == "Excluded (Eligibility Gate Fail)"


def test_5_dimension_scoring_matrix():
    analyzer = JobAnalyzer()
    text = (
        "Senior Architectural BIM Manager at Hassell Melbourne. "
        "Leading BIM execution plans across major healthcare projects. "
        "Requires 10+ years experience, expert Revit, Navisworks clash coordination, "
        "Dynamo / Python automation, ISO 19650 standards, and mentoring junior modellers."
    )
    res = analyzer.detect_country_and_sponsorship_heuristics(text)
    dims = res["dimensions"]
    assert dims["technical_score"] >= 90  # Revit + Navisworks + Dynamo/Python + ISO 19650
    assert dims["experience_score"] >= 90  # Senior/Manager + Healthcare + Architecture
    assert dims["behavioral_score"] >= 90  # Mentoring + Coordination
    assert dims["career_score"] >= 90      # Senior BIM Manager
    assert res["fit_score"] >= 88
    assert res["fit_verdict"] == "Strong Fit"


def test_linkedin_hunter_live_integration():
    hunter = LiveJobHunter()
    # Test searching with limit 3 to verify live connectivity
    results = hunter.search_online_jobs(keywords="BIM Manager", country="Australia", limit=3)
    assert len(results) > 0
    first_job = results[0]
    assert "job_title" in first_job
    assert "company_name" in first_job
    assert "eligibility_gate" in first_job
    assert "dimensions" in first_job
    assert "fit_score" in first_job
    assert "fit_verdict" in first_job
