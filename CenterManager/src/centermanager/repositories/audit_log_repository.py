from typing import Optional, List
from sqlalchemy.orm import Session
from centermanager.models.audit_log import AuditLog
from centermanager.repositories.base import BaseRepository

class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: Session): super().__init__(session, AuditLog)
    def search(self, actor_id: Optional[int]=None, action: Optional[str]=None, module: Optional[str]=None, result: Optional[str]=None, limit: int=500) -> List[AuditLog]:
        q=self._session.query(AuditLog)
        if actor_id is not None: q=q.filter(AuditLog.actor_id==actor_id)
        if action: q=q.filter(AuditLog.action==action)
        if module: q=q.filter(AuditLog.module==module)
        if result: q=q.filter(AuditLog.result==result)
        return q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
