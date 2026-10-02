import inspect

from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QWidget

from centermanager.ui.student_workspace.student_detail_page import StudentDetailPage


def test_scroll_tab_preserves_content_height_contract(qapplication_session):
    content = QWidget()

    scroll = StudentDetailPage._create_scroll_tab(content)

    assert isinstance(scroll, QScrollArea)
    assert scroll.widget() is content
    assert scroll.widgetResizable() is True
    assert scroll.frameShape() == QFrame.Shape.NoFrame
    assert content.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert content.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Minimum


def test_enrollment_and_finance_use_scroll_tabs():
    source = inspect.getsource(StudentDetailPage._setup_ui)

    assert "self._create_scroll_tab(self.enrollment_widget)" in source
    assert "self.tab_widget.add_page(self.enrollment_tab, \"Enrollment\")" in source
    assert "self._create_scroll_tab(self.financial_tab)" in source
    assert "self.tab_widget.add_page(self.finance_scroll_tab, \"Finance\")" in source
