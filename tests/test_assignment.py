# tests/test_assignment.py

from models.assignment import Assignment


def test_assignment_to_dict(sample_assignment):
    assert sample_assignment.to_dict() == {
        "id": "a001",
        "name": "test_assignment",
        "category_id": "c001",
        "points_possible": 50.0,
        "extra_credit": False,
    }


def test_assignment_from_dict(sample_assignment):
    assignment = Assignment.from_dict(
        {
            "id": "a001",
            "name": "test_assignment",
            "category_id": "c001",
            "points_possible": 50.0,
            "extra_credit": False,
        }
    )

    assert assignment.id == "a001"
    assert assignment.name == "test_assignment"
    assert assignment.category_id == "c001"
    assert assignment.points_possible == 50.0
    assert assignment.is_extra_credit == False


def test_assignment_to_str(sample_assignment):
    assert sample_assignment.__str__() == "ASSIGNMENT: name: test_assignment, id: a001"
