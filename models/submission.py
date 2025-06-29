# models/submission.py


class Submission:

    def __init__(
        self,
        id: str,
        student_id: str,
        assignment_id: str,
        score: float,
        is_late: bool = False,
    ):
        self.id = id
        self.student_id = student_id
        self.assignment_id = assignment_id
        self.score = score
        self.is_late = is_late
        # self.resolved_refs = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "assignment_id": self.assignment_id,
            "score": self.score,
            "is_late": self.is_late,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Submission":
        return cls(
            id=data["id"],
            student_id=data["student_id"],
            assignment_id=data["assignment_id"],
            score=data["score"],
            is_late=data["is_late"],
        )

    def __repr__(self) -> str:
        return f"Submission({self.id}, {self.student_id}, {self.assignment_id}, {self.score}, {self.is_late})"

    def __str__(self) -> str:
        return f"SUBMISSION: id: {self.id}, student id: {self.student_id}, assignment id: {self.assignment_id}"
