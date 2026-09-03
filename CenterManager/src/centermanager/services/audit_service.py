import json
from typing import Optional, Any, Dict, List
from sqlalchemy.orm import sessionmaker, Session
from centermanager.repositories.audit_log_repository import AuditLogRepository
from centermanager.models.audit_log import AuditLog
from centermanager.core.current_user import get_current_user
from centermanager.core.clock import get_clock

class AuditService:
    def __init__(self, session_factory: sessionmaker): self._session_factory=session_factory

    @staticmethod
    def _build_summary(action: str, target_type: Optional[str], target_id: Optional[Any], target_name: Optional[str]) -> str:
        """Build a deterministic human-readable summary for audit rows.

        The summary is deliberately independent from localized UI text so audit
        records remain stable across machines and runs. Callers that need a more
        specific description can pass ``summary`` explicitly.
        """
        action_text = str(action or "AUDIT")
        if target_type and target_id is not None:
            return f"{action_text}: {target_type}#{target_id}"
        if target_type and target_name:
            return f"{action_text}: {target_type} ({target_name})"
        if target_type:
            return f"{action_text}: {target_type}"
        return action_text

    def record_in_session(self, session: Session, action: str, module: str, target_type: Optional[str]=None, target_id: Optional[Any]=None, target_name: Optional[str]=None, result: str='success', details: Optional[Any]=None, actor=None, entity_type: Optional[str]=None, entity_id: Optional[Any]=None, summary: Optional[str]=None) -> AuditLog:
        """Add an audit record to an existing transaction without committing it.

        ``entity_*`` is the canonical audit identity. For existing callers that
        only provide the legacy ``target_*`` metadata, mirror the target identity
        so required audit schemas never receive a null entity identity.
        """
        actor = actor if actor is not None else get_current_user()
        if isinstance(details, (dict,list)): details=json.dumps(details, ensure_ascii=False, sort_keys=True)
        resolved_entity_type = entity_type if entity_type is not None else target_type
        resolved_entity_id = entity_id if entity_id is not None else target_id
        resolved_summary = summary if summary is not None else self._build_summary(action, target_type, target_id, target_name)
        if not str(resolved_summary).strip():
            resolved_summary = self._build_summary(action, target_type, target_id, target_name)
        log=AuditLog(
            created_at=get_clock().now(),
            actor_id=getattr(actor,'id',None),
            actor_name=getattr(actor,'username',None),
            action=action,
            module=module,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            target_name=target_name,
            entity_type=resolved_entity_type,
            entity_id=str(resolved_entity_id) if resolved_entity_id is not None else None,
            summary=str(resolved_summary),
            result=result,
            details=details,
        )
        session.add(log)
        return log

    def record(self, action: str, module: str, target_type: Optional[str]=None, target_id: Optional[Any]=None, target_name: Optional[str]=None, result: str='success', details: Optional[Any]=None, actor=None, entity_type: Optional[str]=None, entity_id: Optional[Any]=None, summary: Optional[str]=None) -> AuditLog:
        with self._session_factory() as session:
            log=self.record_in_session(session, action, target_type=target_type, target_id=target_id, target_name=target_name, module=module, result=result, details=details, actor=actor, entity_type=entity_type, entity_id=entity_id, summary=summary)
            session.commit(); session.refresh(log); return log

    def list_logs(self, **filters) -> List[AuditLog]:
        with self._session_factory() as session: return AuditLogRepository(session).search(**filters)

    def log_user_action(self, action, user, details=None, **kwargs): return self.record(action, 'admin', 'user', getattr(user,'id',None), getattr(user,'username',None), details=details, **kwargs)
    def log_role_action(self, action, role, details=None, **kwargs): return self.record(action, 'admin', 'role', getattr(role,'id',None), getattr(role,'name',None), details=details, **kwargs)
