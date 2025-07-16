# tests/test_submission.py

from models.submission import Submission


def test_submission_to_dict(sample_submission):
    assert sample_submission.to_dict() == {
        "id": "sub001",
        "student_id": "s001",
        "assignment_id": "a001",
        "points_earned": 40.0,
        "is_late": False,
        "is_exempt": False,
    }


def test_submission_from_dict():
    submission = Submission.from_dict(
        {
            "id": "sub001",
            "student_id": "s001",
            "assignment_id": "a001",
            "points_earned": 40.0,
            "is_late": False,
            "is_exempt": False,
        }
    )

    assert submission.id == "sub001"
    assert submission.student_id == "s001"
    assert submission.assignment_id == "a001"
    assert submission.points_earned == 40.0
    assert not submission.is_late
    assert not submission.is_exempt


def test_late_submission(sample_late_submission):
    assert sample_late_submission.is_late


def test_toggle_late(sample_submission):
    assert not sample_submission.is_late
    sample_submission.toggle_late_status()
    assert sample_submission.is_late


def test_toggle_exempt(sample_submission):
    assert not sample_submission.is_exempt
    sample_submission.toggle_exempt_status()
    assert sample_submission.is_exempt
