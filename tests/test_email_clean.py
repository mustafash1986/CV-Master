"""
Test verifying that Cover Letter is NEVER leaked into the email body text.
"""
from cv_servant.coordinator import ApplicationCoordinator


def test_no_cover_letter_in_email_body():
    coordinator = ApplicationCoordinator()
    
    # Simulate a job with separate email_body and cover_letter
    job_data = {
        "job_id": "TEST_001",
        "job_title": "BIM Manager",
        "company_name": "Test Firm",
        "email_subject": "Application: BIM Manager - Mustafa Shawky",
        "email_body": "Dear Hiring Manager,\n\nPlease find attached my CV and Cover Letter.\n\nBest regards,\nMustafa Shawky",
        "cover_letter": "Dear Hiring Manager,\n\nI am writing to express my enthusiastic interest in the BIM Manager position...",
    }

    # Simulate dirty manual update where someone passed combined preview text into new_email_body
    dirty_body = (
        "Dear Hiring Manager,\n\nPlease find attached my CV.\n\nBest regards,\nMustafa Shawky\n\n"
        "--------------------------------------------------\n"
        "COVER LETTER:\n"
        "Dear Hiring Manager,\n\nI am writing to express my enthusiastic interest..."
    )

    clean_res = coordinator.update_job_texts_manually(
        job_data=job_data,
        new_subject=job_data["email_subject"],
        new_email_body=dirty_body,
        new_cover_letter=job_data["cover_letter"],
    )

    assert "COVER LETTER:" not in clean_res["email_body"]
    assert "--------------------------------------------------" not in clean_res["email_body"]
    assert "enthusiastic interest" not in clean_res["email_body"]
    assert "Best regards" in clean_res["email_body"]
