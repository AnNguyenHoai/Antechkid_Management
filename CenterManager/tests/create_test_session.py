import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy.orm import sessionmaker
from centermanager.database.engine import create_production_engine
from centermanager.models.class_ import Class
from centermanager.models.session import Session, SessionStatus
from centermanager.models.enrollment import Enrollment
from centermanager.models.student import Student
from datetime import date

engine = create_production_engine()
SessionFactory = sessionmaker(bind=engine)
session = SessionFactory()

# 1. Tạo Class
class_obj = Class(
    name="Python Class 01",
    course="Python Basics",
    teacher="Mr. An",
    start_date=date(2026, 7, 1),
    end_date=date(2026, 9, 30)
)
session.add(class_obj)
session.commit()
print(f"Created Class: {class_obj.name} (id={class_obj.id})")

# 2. Gán Student vào Class (enrollment)
# Lấy student đầu tiên
student = session.query(Student).first()
if student:
    enrollment = Enrollment(
        student_id=student.id,
        class_id=class_obj.id,
        class_name=class_obj.name,
        course_name=class_obj.course,
    )
    session.add(enrollment)
    session.commit()
    print(f"Enrolled student {student.full_name} into class {class_obj.name}")

# 3. Tạo Session (Completed để thấy Teaching Note và Highlights)
session_obj = Session(
    class_id=class_obj.id,
    session_number=1,
    title="Introduction to Python",
    lesson_topic="Variables and Data Types",
    scheduled_date=date(2026, 7, 5),
    status=SessionStatus.COMPLETED.value
)
session.add(session_obj)
session.commit()
print(f"Created Session: {session_obj.title} (id={session_obj.id})")

# 4. In ra session_id để mở
print(f"\nSession ID: {session_obj.id}")
print("Mở ứng dụng và đi đến Session Detail với ID này.")