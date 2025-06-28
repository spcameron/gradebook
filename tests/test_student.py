# test_student.py

from models.student import Student


def test_student_to_dict(sample_student):
    assert sample_student.to_dict() == {
        "id": "s001",
        "name": "Sean Cameron",
        "email": "scameron@mmm.edu",
        "status": "active",
    }


def test_student_from_dict(sample_student):
    student = Student.from_dict(
        {
            "id": "s001",
            "name": "Sean Cameron",
            "email": "scameron@mmm.edu",
            "status": "active",
        }
    )

    assert student.id == "s001"
    assert student.name == "Sean Cameron"
    assert student.email == "scameron@mmm.edu"
    assert student.status == "active"


def test_student_to_str(sample_student):
    assert (
        sample_student.__str__()
        == "STUDENT: name: Sean Cameron, id: s001, email: scameron@mmm.edu"
    )
