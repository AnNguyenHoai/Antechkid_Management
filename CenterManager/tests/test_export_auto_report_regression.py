from datetime import date
from centermanager.services.auto_report_service import AutoReportService


class Student:
    def __init__(self, student_id):
        self.id = student_id


class Students:
    def list_students(self):
        return [Student(1), Student(2)]


class Reports:
    def __init__(self):
        self.generated = []
        self.fail_ids = set()

    def report_exists_on_date(self, student_id, trigger, target_date):
        return (student_id, target_date) in self.generated

    def generate_student_report(self, student_id, **kwargs):
        if student_id in self.fail_ids:
            raise RuntimeError("planned failure")
        self.generated.append((student_id, date.today()))


def test_daily_report_is_once_per_student_and_retries_failures(tmp_path):
    reports = Reports()
    service = AutoReportService(Students(), reports)
    service._state_file = tmp_path / "state.json"

    service.run_daily_check()
    assert len(reports.generated) == 2

    # Reset state to simulate a partial retry check on the same date.
    service._state_file.unlink()
    reports.fail_ids = {2}
    reports.generated = [(1, date.today())]
    service.run_daily_check()

    assert (1, date.today()) in reports.generated
    assert not service._state_file.exists()

    reports.fail_ids.clear()
    service.run_daily_check()
    assert (2, date.today()) in reports.generated
    assert service._state_file.exists()
