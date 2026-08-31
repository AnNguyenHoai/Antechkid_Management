from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QStackedWidget,QFrame
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from .employee_list_page import EmployeeListPage

class EmployeeWorkspaceShell(QWidget):
    go_home=Signal()
    def __init__(self, employee_service, document_service, parent=None):
        super().__init__(parent); self._es=employee_service; self._ds=document_service; self._setup()
    def _setup(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.header=WorkspaceHeader('Employee Workspace','Employees'); self.header.back_home_clicked.connect(self.go_home.emit); root.addWidget(self.header)
        body=QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        self.nav=WorkspaceNavigation('Employee Workspace',[{'id':'employees','icon':'👥','label':'Employees'}]); self.nav.page_selected.connect(self.navigate_to); body.addWidget(self.nav)
        self.stack=QStackedWidget(); self.list_page=EmployeeListPage(self._es,self._ds); self.stack.addWidget(self.list_page); body.addWidget(self.stack,1); root.addLayout(body)
    def navigate_to(self,page_id):
        self.stack.setCurrentWidget(self.list_page); self.nav.set_active_page('employees'); self.header.set_context('Employee Workspace','Employees'); self.list_page.refresh()
    def set_write_enabled(self,enabled): self.list_page.set_write_enabled(enabled)
