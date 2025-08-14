# tests/test_gradebook.py

import datetime
import json
import os
import tempfile

from core.response import ErrorCode
from models.student import AttendanceStatus
from models.submission import Submission


def test_create_new_gradebook(create_new_gradebook):
    assert create_new_gradebook.name == "THTR 274A"
    assert create_new_gradebook.term == "FALL 2025"


def test_load_gradebook_from_file(load_gradebook_from_file):
    assert load_gradebook_from_file.name == "THTR 274B"
    assert load_gradebook_from_file.term == "SPRING 2026"


# === data manipulators ===

# --- gradebook methods ---


def test_mark_dirty(sample_gradebook):
    gb = sample_gradebook
    assert not gb.has_unsaved_changes

    gb._mark_dirty()
    assert gb.has_unsaved_changes


def test_mark_dirty_if_tracked(sample_gradebook, sample_student):
    gb = sample_gradebook
    assert not gb.has_unsaved_changes

    gb._mark_dirty_if_tracked(sample_student)
    assert not gb.has_unsaved_changes

    gb.add_student(sample_student)
    gb._mark_dirty_if_tracked(sample_student)
    assert gb.has_unsaved_changes


# --- student methods ---


def test_add_student(sample_gradebook, sample_student):
    response = sample_gradebook.add_student(sample_student)
    assert response.success
    assert sample_student in sample_gradebook.students.values()


def test_add_student_and_save(sample_gradebook, sample_student):
    response = sample_gradebook.add_student(sample_student)
    assert response.success

    with tempfile.TemporaryDirectory() as temp_dir:
        sample_gradebook.metadata = {
            "name": "Test Course",
            "term": "Fall 1987",
            "created_at": "Testing",
        }

        sample_gradebook.save(temp_dir)

        students_path = os.path.join(temp_dir, "students.json")
        assert os.path.exists(students_path)

        with open(students_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "s001"
        assert data[0]["last_name"] == "Cameron"


def test_add_and_remove_student(sample_gradebook, sample_student):
    gb = sample_gradebook
    assert sample_student not in gb.students.values()

    response = gb.add_student(sample_student)
    assert response.success
    assert sample_student in gb.students.values()

    response = gb.remove_student(sample_student)
    assert response.success
    assert sample_student not in gb.students.values()


def test_update_student_attributes(sample_gradebook, sample_student):
    gb = sample_gradebook

    assert sample_student.first_name == "Sean"
    assert sample_student.last_name == "Cameron"
    assert sample_student.email == "scameron@mmm.edu"
    assert sample_student.is_active

    response = gb.update_student_first_name(sample_student, "Paul")
    assert response.success
    assert sample_student.first_name == "Paul"

    response = gb.update_student_last_name(sample_student, "Atreides")
    assert response.success
    assert sample_student.last_name == "Atreides"

    response = gb.update_student_email(sample_student, "patreides@mmm.edu")
    assert response.success
    assert sample_student.email == "patreides@mmm.edu"

    response = gb.toggle_student_active_status(sample_student)
    assert response.success
    assert not sample_student.is_active


# --- assignment methods ---


def test_add_assignment(sample_gradebook, sample_assignment):
    response = sample_gradebook.add_assignment(sample_assignment)
    assert response.success
    assert sample_assignment in sample_gradebook.assignments.values()


def test_add_assignment_and_save(sample_gradebook, sample_assignment):
    response = sample_gradebook.add_assignment(sample_assignment)
    assert response.success

    with tempfile.TemporaryDirectory() as temp_dir:
        sample_gradebook.metadata = {
            "name": "Test Course",
            "term": "Fall 1987",
            "created_at": "Testing",
        }

        sample_gradebook.save(temp_dir)

        assignments_path = os.path.join(temp_dir, "assignments.json")
        assert os.path.exists(assignments_path)

        with open(assignments_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "a001"
        assert data[0]["name"] == "test_assignment"


def test_add_and_remove_assignment(sample_gradebook, sample_assignment):
    gb = sample_gradebook
    assert sample_assignment not in gb.assignments.values()

    response = gb.add_assignment(sample_assignment)
    assert response.success
    assert sample_assignment in gb.assignments.values()

    response = gb.remove_assignment(sample_assignment)
    assert response.success
    assert sample_assignment not in gb.assignments.values()


def test_update_assignment_attributes(
    sample_gradebook, sample_assignment, sample_weighted_category
):
    gb = sample_gradebook

    assert sample_assignment.name == "test_assignment"
    assert sample_assignment.category_id == "c001"
    assert sample_assignment.points_possible == 50.0
    assert sample_assignment.due_date_iso == "1987-06-21T23:59:00"
    assert sample_assignment.is_active

    response = gb.update_assignment_name(sample_assignment, "new_assignment")
    assert response.success
    assert sample_assignment.name == "new_assignment"

    gb.add_category(sample_weighted_category)
    response = gb.update_assignment_linked_category(
        sample_assignment, sample_weighted_category
    )
    assert response.success
    assert sample_assignment.category_id == "c002"

    new_due_date = datetime.datetime.strptime("1987-12-17 23:59", "%Y-%m-%d %H:%M")
    response = gb.update_assignment_due_date(sample_assignment, new_due_date)
    assert response.success
    assert sample_assignment.due_date_iso == "1987-12-17T23:59:00"

    response = gb.update_assignment_points_possible(sample_assignment, 100.0)
    assert response.success
    assert sample_assignment.points_possible == 100.0

    response = gb.toggle_assignment_active_status(sample_assignment)
    assert response.success
    assert not sample_assignment.is_active


# --- category methods ---


def test_add_category(sample_gradebook, sample_unweighted_category):
    response = sample_gradebook.add_category(sample_unweighted_category)
    assert response.success
    assert sample_unweighted_category in sample_gradebook.categories.values()


def test_add_category_and_save(sample_gradebook, sample_unweighted_category):
    response = sample_gradebook.add_category(sample_unweighted_category)
    assert response.success

    with tempfile.TemporaryDirectory() as temp_dir:
        sample_gradebook.metadata = {
            "name": "Test Course",
            "term": "Fall 1987",
            "created_at": "Testing",
        }

        sample_gradebook.save(temp_dir)

        categories_path = os.path.join(temp_dir, "categories.json")
        assert os.path.exists(categories_path)

        with open(categories_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "c001"
        assert data[0]["name"] == "test_category"


def test_add_and_remove_category(sample_gradebook, sample_category):
    gb = sample_gradebook
    assert sample_category not in gb.categories.values()

    response = gb.add_category(sample_category)
    assert response.success
    assert sample_category in gb.categories.values()

    response = gb.remove_category(sample_category)
    assert response.success
    assert sample_category not in gb.categories.values()


def test_update_category_attributes(sample_gradebook, sample_category):
    gb = sample_gradebook

    assert sample_category.name == "test_category"
    assert sample_category.weight is None
    assert sample_category.is_active

    response = gb.update_category_name(sample_category, "new_category")
    assert response.success
    assert sample_category.name == "new_category"

    response = gb.update_category_weight(sample_category, 50.0)
    assert response.success
    assert sample_category.weight == 50.0

    response = gb.toggle_category_active_status(sample_category)
    assert response.success
    assert not sample_category.is_active


# --- attendance methods ---


def test_add_class_date(sample_gradebook, sample_date):
    gb = sample_gradebook
    assert sample_date not in gb.class_dates

    response = gb.add_class_date(sample_date)
    assert response.success
    assert sample_date in gb.class_dates


def test_mark_student_present(sample_gradebook, sample_date, sample_student):
    gb = sample_gradebook

    response = gb.mark_student_attendance_for_date(
        sample_date, sample_student, AttendanceStatus.PRESENT
    )
    assert not response.success
    assert response.error == ErrorCode.NOT_FOUND

    gb.add_student(sample_student)
    gb.add_class_date(sample_date)

    response = gb.mark_student_attendance_for_date(
        sample_date, sample_student, AttendanceStatus.PRESENT
    )
    assert response.success


# --- submission tests ---


def test_add_submission(
    sample_gradebook, sample_submission, sample_student, sample_assignment
):
    gb = sample_gradebook
    assert sample_submission not in gb.submissions.values()

    response = gb.add_student(sample_student)
    assert response.success
    response = gb.add_assignment(sample_assignment)
    assert response.success

    response = gb.add_submission(sample_submission)
    assert response.success
    assert sample_submission in gb.submissions.values()


def test_add_submission_and_save(
    sample_gradebook, sample_submission, sample_student, sample_assignment
):
    gb = sample_gradebook
    assert sample_submission not in gb.submissions.values()

    response = gb.add_student(sample_student)
    assert response.success
    response = gb.add_assignment(sample_assignment)
    assert response.success

    response = gb.add_submission(sample_submission)
    assert response.success

    with tempfile.TemporaryDirectory() as temp_dir:
        gb.metadata = {
            "name": "Test Course",
            "term": "Fall 1987",
            "created_at": "Testing",
        }

        gb.save(temp_dir)

        submissions_path = os.path.join(temp_dir, "submissions.json")
        assert os.path.exists(submissions_path)

        with open(submissions_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "sub001"
        assert data[0]["points_earned"] == 40.0


def test_and_remove_submission(
    sample_gradebook, sample_submission, sample_student, sample_assignment
):
    gb = sample_gradebook
    assert sample_submission not in gb.submissions.values()

    response = gb.add_student(sample_student)
    assert response.success
    response = gb.add_assignment(sample_assignment)
    assert response.success

    response = gb.add_submission(sample_submission)
    assert response.success
    assert sample_submission in gb.submissions.values()

    response = gb.remove_submission(sample_submission)
    assert response.success
    assert sample_submission not in gb.submissions.values()


def test_batch_add_submissions(
    sample_gradebook, sample_assignment, sample_student_roster
):
    gb = sample_gradebook
    students = sample_student_roster
    gb.add_assignment(sample_assignment)
    for student in students:
        gb.add_student(student)

    submissions = []
    submissions.append(
        Submission(
            id="sub001",
            student_id=students[0].id,
            assignment_id=sample_assignment.id,
            points_earned=10.0,
        )
    )
    submissions.append(
        Submission(
            id="sub002",
            student_id=students[1].id,
            assignment_id=sample_assignment.id,
            points_earned=20.0,
        )
    )
    submissions.append(
        Submission(
            id="sub003",
            student_id=students[2].id,
            assignment_id=sample_assignment.id,
            points_earned=30.0,
        )
    )

    response = gb.batch_add_submissions(submissions)
    assert response.success
    for submission in submissions:
        assert submission in response.data["success"]
        assert submission in gb.submissions.values()


def test_update_submission_attributes(
    sample_gradebook, sample_submission, sample_student, sample_assignment
):
    gb = sample_gradebook
    gb.add_student(sample_student)
    gb.add_assignment(sample_assignment)
    gb.add_submission(sample_submission)

    assert sample_submission.points_earned == 40.0
    assert not sample_submission.is_late
    assert not sample_submission.is_exempt

    response = gb.update_submission_points_earned(sample_submission, 50.0)
    assert response.success
    assert sample_submission.points_earned == 50.0

    response = gb.toggle_submission_late_status(sample_submission)
    assert response.success
    assert sample_submission.is_late

    response = gb.toggle_submission_exempt_status(sample_submission)
    assert response.success
    assert sample_submission.is_exempt


# --- category weighting ---


# === data access methods ===

# --- submission methods ---


def test_find_submission_by_uuid(
    sample_gradebook, sample_submission, sample_student, sample_assignment
):
    gb = sample_gradebook
    gb.add_student(sample_student)
    gb.add_assignment(sample_assignment)

    response = gb.find_submission_by_uuid(sample_submission.id)
    assert not response.success
    assert response.error == ErrorCode.NOT_FOUND

    gb.add_submission(sample_submission)
    response = gb.find_submission_by_uuid(sample_submission.id)
    assert response.success
    assert response.data["record"] == sample_submission


def test_get_assignment_and_student(
    sample_gradebook, sample_submission, sample_student, sample_assignment
):
    gb = sample_gradebook

    response = gb.get_assignment_and_student(sample_submission)
    assert not response.success
    assert response.error == ErrorCode.NOT_FOUND

    gb.add_student(sample_student)
    gb.add_assignment(sample_assignment)
    gb.add_submission(sample_submission)

    response = gb.get_assignment_and_student(sample_submission)
    assert response.success
    assert response.data["assignment"] == sample_assignment
    assert response.data["student"] == sample_student


def test_submission_already_exists(
    sample_gradebook, sample_submission, sample_student, sample_assignment
):
    gb = sample_gradebook
    gb.add_student(sample_student)
    gb.add_assignment(sample_assignment)

    assert not gb.submission_already_exists(sample_assignment.id, sample_student.id)

    gb.add_submission(sample_submission)
    assert gb.submission_already_exists(sample_assignment.id, sample_student.id)


# --- attendance records ---


def test_get_attendance_for_date(sample_gradebook, sample_date, sample_student):
    gb = sample_gradebook
    gb.add_student(sample_student)
    gb.add_class_date(sample_date)
    gb.mark_student_attendance_for_date(
        sample_date, sample_student, AttendanceStatus.PRESENT
    )

    response = gb.get_attendance_for_date(sample_date)
    assert response.success
    attendance_report = response.data["attendance"]
    assert attendance_report.get(sample_student.id) == AttendanceStatus.PRESENT


def test_get_attendance_for_student(sample_gradebook, sample_date, sample_student):
    gb = sample_gradebook
    gb.add_student(sample_student)
    gb.add_class_date(sample_date)
    gb.mark_student_attendance_for_date(
        sample_date, sample_student, AttendanceStatus.PRESENT
    )

    response = gb.get_attendance_for_student(sample_student)
    assert response.success
    attendance_report = response.data["attendance"]
    assert attendance_report.get(sample_date) == AttendanceStatus.PRESENT


def test_get_total_absences_for_student(sample_gradebook, sample_date, sample_student):
    gb = sample_gradebook
    gb.add_student(sample_student)
    gb.add_class_date(sample_date)
    gb.mark_student_attendance_for_date(
        sample_date, sample_student, AttendanceStatus.ABSENT
    )

    response = gb.get_total_absences_for_student(sample_student)
    assert response.success
    absences = response.data["total_absences"]
    assert absences == 1


# --- student records ---


def test_find_student_by_uuid(sample_gradebook, sample_student):
    gb = sample_gradebook

    response = gb.find_student_by_uuid(sample_student.id)
    assert not response.success
    assert response.error == ErrorCode.NOT_FOUND

    gb.add_student(sample_student)
    response = gb.find_student_by_uuid(sample_student.id)
    assert response.success
    assert response.data["record"] == sample_student


def test_find_student_by_query(sample_gradebook, sample_student):
    gb = sample_gradebook
    gb.add_student(sample_student)

    # exact string of first_name attribute
    query = "Sean"
    response = gb.find_student_by_query(query)
    assert response.success
    search_results = response.data["records"]
    assert sample_student in search_results

    # partial string, mismatched case of last_name attribute
    query = "eRoN"
    response = gb.find_student_by_query(query)
    assert response.success
    search_results = response.data["records"]
    assert sample_student in search_results


# --- category records ---


def test_find_category_by_uuid(sample_gradebook, sample_category):
    gb = sample_gradebook

    response = gb.find_category_by_uuid(sample_category.id)
    assert not response.success
    assert response.error == ErrorCode.NOT_FOUND

    gb.add_category(sample_category)
    response = gb.find_category_by_uuid(sample_category.id)
    assert response.success
    assert response.data["record"] == sample_category


def test_find_category_by_query(sample_gradebook, sample_category):
    gb = sample_gradebook
    gb.add_category(sample_category)

    query = "test_cat"
    response = gb.find_category_by_query(query)
    assert response.success
    search_results = response.data["records"]
    assert sample_category in search_results


# --- assignment records ---


def test_find_assignment_by_uuid(sample_gradebook, sample_assignment):
    gb = sample_gradebook

    response = gb.find_assignment_by_uuid(sample_assignment.id)
    assert not response.success
    assert response.error == ErrorCode.NOT_FOUND

    gb.add_assignment(sample_assignment)
    response = gb.find_assignment_by_uuid(sample_assignment.id)
    assert response.success
    assert response.data["record"] == sample_assignment


def test_find_assignment_by_query(sample_gradebook, sample_assignment):
    gb = sample_gradebook
    gb.add_assignment(sample_assignment)

    query = "test_assig"
    response = gb.find_assignment_by_query(query)
    assert response.success
    search_results = response.data["records"]
    assert sample_assignment in search_results


# --- submission records ---
