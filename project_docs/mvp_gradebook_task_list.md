## MVP Gradebook Project — Task Outline

### PHASE 1: Core Models and CLI Scaffolding

1. Set up project structure (e.g., `main.py`, `models/`, `data/`)
2. Define in-memory models:
   - Course
   - Student
   - AssignmentCategory
   - Assignment
   - Submission
3. Create initial CLI loop with basic menu shell
4. Implement course creation via prompts
5. Implement category and student entry

### PHASE 2: Assignment + Submission Workflows

6. Add new assignment (select category, enter name, max points)
7. Log submissions for a given assignment:
   - Loop through active students
   - Prompt for score, late flag, exempt flag
8. Edit existing submission (revisit assignment, select student)
9. Mark student as withdrawn
   - Prompt for date
   - Set `status: withdrawn`
10. Increment absences per student

### PHASE 3: Progress + Final Reports

11. Generate current progress report:
   - Filter out ungraded assignments
   - Apply weights only to completed categories
12. Generate final report:
   - Show category breakdown
   - Apply late penalties
   - Factor in all assignments (missing = 0)
13. Display absences and withdrawal status in reports

### PHASE 4: Data Persistence and JSON I/O

14. Save course data:
   - Write all files in `courses/COURSE_NAME/`
15. Load existing course from disk
16. Confirm before overwriting on save
17. Allow "Save As" functionality
18. Handle schema validation on load (basic consistency check)

### Optional / Stretch Goals

- Add helper views: "List all assignments", "List student roster"
- Add sorting by grade or name
- Add default grading schemes (e.g., auto-set 50% penalty on late)

