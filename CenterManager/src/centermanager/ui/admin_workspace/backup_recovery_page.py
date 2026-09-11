from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QMessageBox,QLineEdit
from PySide6.QtCore import Qt
from centermanager.ui.admin_workspace.access import can_write, notify

class BackupRecoveryPage(QWidget):
    def __init__(self, service, permission_service, collaboration_manager, notification_service, parent=None):
        super().__init__(parent); self._service=service; self._ps=permission_service; self._cm=collaboration_manager; self._ns=notification_service; self._rows=[]; self._setup(); self.refresh()
    def _setup(self):
        l=QVBoxLayout(self); head=QHBoxLayout(); head.addWidget(QLabel('<h2>🗄️ Backup & Recovery</h2>')); head.addStretch(); self.create_btn=QPushButton('➕ Create Backup'); self.create_btn.clicked.connect(self.create_backup); head.addWidget(self.create_btn); self.refresh_btn=QPushButton('🔄 Refresh'); self.refresh_btn.clicked.connect(self.refresh); head.addWidget(self.refresh_btn); l.addLayout(head)
        self.info=QLabel('Restoring replaces the runtime database. A safety backup is created automatically before restore.'); self.info.setWordWrap(True); l.addWidget(self.info)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['Created','Label','Location','Status']); self.table.horizontalHeader().setStretchLastSection(True); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); l.addWidget(self.table,1)
        foot=QHBoxLayout(); self.restore_btn=QPushButton('↩ Restore Selected Backup'); self.restore_btn.clicked.connect(self.restore_selected); foot.addWidget(self.restore_btn); foot.addStretch(); l.addLayout(foot)
    def set_write_enabled(self, enabled): self._update_actions()
    def _update_actions(self):
        write=can_write(self._cm)
        self.create_btn.setEnabled(write and self._ps.has_permission('backup.create'))
        self.restore_btn.setEnabled(write and self._ps.has_permission('backup.restore') and bool(self.table.selectionModel().selectedRows()))
    def refresh(self):
        self._rows=self._service.list_backups(); self.table.setRowCount(len(self._rows))
        for r,b in enumerate(self._rows):
            self.table.setItem(r,0,QTableWidgetItem(str(b.get('created_at') or b.get('timestamp','')))); self.table.setItem(r,1,QTableWidgetItem(str(b.get('label','')))); self.table.setItem(r,2,QTableWidgetItem(str(b.get('path','')))); self.table.setItem(r,3,QTableWidgetItem('Available'))
        self._update_actions()
    def create_backup(self):
        if not can_write(self._cm): return notify(self._ns,'WRITE mode is required.','warning')
        result=self._service.create_backup('manual')
        if result.success: notify(self._ns,f'Backup created: {result.backup_path}','success'); self.refresh()
        else: notify(self._ns,f'Backup failed: {result.error}','error')
    def restore_selected(self):
        rows=self.table.selectionModel().selectedRows()
        if not rows: return
        if not can_write(self._cm): return notify(self._ns,'WRITE mode is required.','warning')
        b=self._rows[rows[0].row()]
        msg=QMessageBox(self); msg.setIcon(QMessageBox.Icon.Warning); msg.setWindowTitle('Restore Backup'); msg.setText('Restore this backup? Current runtime data will be replaced. A safety backup will be created first.'); msg.setInformativeText('Restart the application after a successful restore to ensure all database sessions are refreshed.'); msg.setStandardButtons(QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)
        if msg.exec()!=QMessageBox.StandardButton.Yes: return
        result=self._service.restore_backup(b['path'])
        if result.success: notify(self._ns,'Backup restored successfully. Please restart the application.','success'); self.refresh()
        else: notify(self._ns,f'Restore failed: {result.error}','error')
