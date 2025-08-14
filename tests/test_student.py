# tests/test_student.py

from models.student import Student


def test_student_to_dict(sample_student):
    data = sample_student.to_dict()

    assert data["id"] == "s001"
    assert data["first_name"] == "Sean"
    assert data["last_name"] == "Cameron"
    assert data["email"] == "scameron@mmm.edu"
    assert data["active"]


def test_student_from_dict():
    student = Student.from_dict(
        {
            "id": "s001",
            "first_name": "Sean",
            "last_name": "Cameron",
            "email": "scameron@mmm.edu",
            "active": True,
        }
    )

    assert student.id == "s001"
    assert student.first_name == "Sean"
    assert student.last_name == "Cameron"
    assert student.full_name == "Sean Cameron"
    assert student.email == "scameron@mmm.edu"
    assert student.is_active
    assert student.status == "'ACTIVE'"


def test_student_to_str(sample_student):
    assert sample_student.__str__() == "STUDENT: Sean Cameron - (ID: s001)"
