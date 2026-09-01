import json
from typing import Optional, Any, Dict, List
from sqlalchemy.orm import sessionmaker, Session
from centermanager.repositories.audit_log_repository import AuditLogRepository
from centermanager.models.audit_log import AuditLog
from centermanager.core.current_user import get_current_user
from centermanager.core.clock import get_clock

class AuditService:
    def __init__(self, session_factory: sessionmaker): self._session_factory=session_factory

    def record_in_session(self, session: Session, action: str, module: str, target_type: Optional[str]=None, target_id: Optional[Any]=None, target_name: Optional[str]=None, result: str='success', details: Optional[Any]=None, actor=None) -> AuditLog:
        """Add an audit record to an existing transaction without committing it."""
        actor = actor if actor is not None else get_current_user()
        if isinstance(details, (dict,list)): details=json.dumps(details, ensure_ascii=False, sort_keys=True)
        log=AuditLog(
            created_at=get_clock().now(),
            actor_id=getattr(actor,'id',None),
            actor_name=getattr(actor,'username',None),
            action=action,
            module=module,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            target_name=target_name,
            result=result,
            details=details,
        )
        session.add(log)
        return log

    def record(self, action: str, module: str, target_type: Optional[str]=None, target_id: Optional[Any]=None, target_name: Optional[str]=None, result: str='success', details: Optional[Any]=None, actor=None) -> AuditLog:
        with self._session_factory() as session:
            log=self.record_in_session(session, action, module, target_type, target_id, target_name, result, details, actor)
            session.commit(); session.refresh(log); return log

    def list_logs(self, **filters) -> List[AuditLog]:
        with self._session_factory() as session: return AuditLogRepository(session).search(**filters)

    def log_user_action(self, action, user, details=None, **kwargs): return self.record(action, 'admin', 'user', getattr(user,'id',None), getattr(user,'username',None), details=details, **kwargs)
    def log_role_action(self, action, role, details=None, **kwargs): return self.record(action, 'admin', 'role', getattr(role,'id',None), getattr(role,'name',None), details=details, **kwargs)
