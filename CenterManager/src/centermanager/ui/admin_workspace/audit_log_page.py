from typing import Optional, List
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QComboBox
from centermanager.ui.design_system import SearchBar, SecondaryButton
from centermanager.ui.shared import DataTable

class AuditLogPage(QWidget):
    def __init__(self, audit_service, notification_service=None, parent: Optional[QWidget]=None):
        super().__init__(parent); self._service=audit_service; self._logs=[]; self._setup_ui(); self.refresh()
    def _setup_ui(self):
        l=QVBoxLayout(self); l.setContentsMargins(0,0,0,0)
        bar=QHBoxLayout(); self.search_bar=SearchBar('Search audit trail...'); self.search_bar.text_changed.connect(lambda _: self._apply())
        self.module_filter=QComboBox(); self.module_filter.addItems(['All modules','admin','system']); self.module_filter.currentTextChanged.connect(lambda _: self._apply())
        self.result_filter=QComboBox(); self.result_filter.addItems(['All results','success','failed']); self.result_filter.currentTextChanged.connect(lambda _: self._apply())
        self.refresh_btn=SecondaryButton('🔄 Refresh'); self.refresh_btn.clicked.connect(self.refresh)
        for w in (self.search_bar,self.module_filter,self.result_filter,self.refresh_btn): bar.addWidget(w)
        l.addLayout(bar)
        self.data_table=DataTable([{'key':'time','label':'Time','sortable':True},{'key':'actor','label':'Actor','sortable':True},{'key':'action','label':'Action','sortable':True},{'key':'module','label':'Module','sortable':True},{'key':'target','label':'Target','sortable':True},{'key':'result','label':'Result','sortable':True},{'key':'details','label':'Details','sortable':False}],page_size=50); l.addWidget(self.data_table)
    def refresh(self): self._logs=self._service.list_logs(limit=500); self._apply()
    def _apply(self):
        q=self.search_bar.text().strip().lower(); mod=self.module_filter.currentText(); res=self.result_filter.currentText(); rows=[]
        for x in self._logs:
            if mod!='All modules' and x.module!=mod: continue
            if res!='All results' and x.result!=res: continue
            hay=' '.join(str(v or '') for v in [x.actor_name,x.action,x.module,x.target_name,x.details,x.target_id]).lower()
            if q and q not in hay: continue
            rows.append({'time':x.created_at.strftime('%Y-%m-%d %H:%M:%S'),'actor':x.actor_name or 'System','action':x.action,'module':x.module,'target':x.target_name or x.target_id or '-','result':x.result,'details':x.details or '-'})
        self.data_table.set_data(rows,len(rows))
