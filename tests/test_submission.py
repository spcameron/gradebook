# tests/test_submission.py

from models.submission import Submission


def test_submission_to_dict(sample_submission):
    assert sample_submission.to_dict() == {
        "id": "sub001",
        "student_id": "s001",
        "assignment_id": "a001",
        "score": 40.0,
        "is_late": False,
    }


def test_submission_from_dict():
    submission = Submission.from_dict(
        {
            "id": "sub001",
            "student_id": "s001",
            "assignment_id": "a001",
            "score": 40.0,
            "is_late": False,
        }
    )

    assert submission.id == "sub001"
    assert submission._student_id == "s001"
    assert submission._assignment_id == "a001"
    assert submission._points_earned == 40.0
    assert not submission._is_late


def test_late_submission(sample_late_submission):
    assert sample_late_submission.is_late
