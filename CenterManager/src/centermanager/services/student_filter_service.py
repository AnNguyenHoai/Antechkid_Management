"""StudentFilterService - applies advanced filters to student list."""
from typing import List
from datetime import date
from sqlalchemy.orm import sessionmaker
from centermanager.dto.student_filter_dto import StudentFilter
from centermanager.models.student import Student
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider

class StudentFilterService:
    """Service to filter students based on various criteria."""
    def __init__(self, session_factory: sessionmaker, repository_provider: RepositoryProvider | None = None) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    def filter_students(self, filter_criteria: StudentFilter) -> List[Student]:
        """Apply filters and return matching active students."""
        with self._session_factory() as session:
            repo = self._repository_provider.students(session)
            students = repo.filter_students(filter_criteria)

            if filter_criteria.age_min is not None or filter_criteria.age_max is not None:
                today = date.today()
                filtered = []
                for student in students:
                    if student.date_of_birth:
                        age = today.year - student.date_of_birth.year - (
                            (today.month, today.day) <
                            (student.date_of_birth.month, student.date_of_birth.day)
                        )
                        if filter_criteria.age_min is not None and age < filter_criteria.age_min:
                            continue
                        if filter_criteria.age_max is not None and age > filter_criteria.age_max:
                            continue
                    else:
                        continue
                    filtered.append(student)
                return filtered
            return students
