# -*- coding: utf-8 -*-
import csv
import logging
import os
import tempfile
from datetime import date
from typing import Any, Optional, List, Tuple

from centermanager.models.expense import Expense
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.expense_timeline_service import ExpenseTimelineService
from centermanager.services.permission_service import PermissionService
from centermanager.core.permission_guard import require_permission
from centermanager.core.current_user import get_current_user
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged

logger = logging.getLogger(__name__)


class ExpenseValidationError(Exception):
    pass


class ExpenseNotFoundError(Exception):
    pass


class ExpenseService:
    """Expense application service.

    Pending records are planned/non-realized outflows. Completed records are
    realized ledger postings and therefore require a unique canonical
    FinancePeriod and may not be future-dated.
    """

    def __init__(self, session_factory: Any, timeline_service: ExpenseTimelineService,
                 permission_service: PermissionService,
                 repository_provider: Optional[RepositoryProvider] = None,
                 event_bus: Optional[EventBus] = None):
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._permission_service = permission_service
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._event_bus = event_bus

    def set_event_bus(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _publish_finance_change(self, action: str, expense_id: int) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(FinanceDataChanged(entity="expense", action=action, entity_id=expense_id))
            except Exception:
                logger.exception("Expense %s committed but FinanceDataChanged publish failed", expense_id)

    def _log_timeline_best_effort(self, **kwargs) -> None:
        try:
            self._timeline_service.log_event(**kwargs)
        except Exception:
            logger.exception("Expense committed but timeline projection failed")

    def _normalize_text(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        stripped = text.strip()
        return stripped if stripped else None

    def _validate_amount(self, amount: float) -> float:
        if amount <= 0:
            raise ExpenseValidationError("Amount must be greater than 0")
        return amount

    def _validate_category(self, category: str) -> str:
        valid = ["Teacher Salary", "Office Rent", "Electricity", "Water", "Internet", "Equipment", "Marketing", "Office Supply", "Maintenance", "Transportation", "Other"]
        if category not in valid:
            raise ExpenseValidationError(f"Category must be one of: {', '.join(valid)}")
        return category

    def _validate_payment_date(self, payment_date):
        if payment_date is None:
            raise ExpenseValidationError("Payment date is required.")
        return payment_date

    def _validate_payment_method(self, method: str) -> str:
        mapping = {"TÀI KHOẢN CÁ NHÂN": "Cash", "TÀI KHOẢN CÔNG TY": "Bank", "Bank Transfer": "Bank", "Cash": "Cash", "Bank": "Bank", "Other": "Other"}
        value = mapping.get(method, method)
        if value not in {"Cash", "Bank", "Other"}:
            raise ExpenseValidationError("Invalid payment method.")
        return value

    def _validate_status(self, status: str) -> str:
        mapping = {"ĐÃ HOÀN TRẢ": "Completed", "CHƯA HOÀN TRẢ": "Pending", "Completed": "Completed", "Pending": "Pending"}
        value = mapping.get(status, status)
        if value not in {"Completed", "Pending"}:
            raise ExpenseValidationError("Invalid expense status.")
        return value

    def _resolve_posting_period_id(self, session, payment_date: date, status: str) -> Optional[int]:
        """Return deterministic period assignment for an Expense state.

        Pending may be future/planned and therefore may remain unassigned when no
        configuration covers its date. Completed is realized money: future dates,
        missing coverage and ambiguous coverage are hard validation failures.
        """
        if status == "Completed" and payment_date > date.today():
            raise ExpenseValidationError("Completed expense cannot have a future payment date.")
        repo = self._repository_provider.finance_periods(session)
        try:
            period = repo.get_unique_effective(payment_date)
        except ValueError as exc:
            raise ExpenseValidationError(str(exc)) from exc
        if status == "Completed" and period is None:
            raise ExpenseValidationError(
                f"No FinancePeriod configuration covers {payment_date.isoformat()}."
            )
        return period.id if period is not None else None

    @require_permission("finance.expense.create")
    def create_expense(self, category: str, description: str, amount: float, payment_method: str,
                       payment_date: date, paid_by: Optional[str] = None, status: str = "Completed",
                       note: Optional[str] = None) -> Expense:
        category = self._validate_category(category)
        description = self._normalize_text(description)
        if not description:
            raise ExpenseValidationError("Description is required")
        amount = self._validate_amount(amount)
        payment_method = self._validate_payment_method(payment_method)
        payment_date = self._validate_payment_date(payment_date)
        status = self._validate_status(status)
        paid_by = self._normalize_text(paid_by) or (get_current_user().full_name if get_current_user() else "System")
        note = self._normalize_text(note)
        with self._session_factory() as session:
            period_id = self._resolve_posting_period_id(session, payment_date, status)
            repo = self._repository_provider.expenses(session)
            expense = Expense(category=category, description=description, amount=amount, payment_method=payment_method,
                              payment_date=payment_date, finance_period_id=period_id,
                              paid_by=paid_by, status=status, note=note)
            repo.add(expense)
            session.commit()
            repo.refresh(expense)
            expense_id = expense.id
            self._log_timeline_best_effort(expense_id=expense_id, event_type="ExpenseCreated", title=f"Expense Created: {category}",
                                           description=f"Amount: {amount:,.0f} VND, Method: {payment_method}", metadata={"category": category, "amount": amount})
            self._publish_finance_change("created", expense_id)
            return expense

    @require_permission("finance.view")
    def get_expense(self, expense_id: int) -> Expense:
        with self._session_factory() as session:
            expense = self._repository_provider.expenses(session).get_by_id(expense_id)
            if not expense:
                raise ExpenseNotFoundError(f"Expense {expense_id} not found")
            return expense

    @require_permission("finance.view")
    def list_expenses(self, category: Optional[str] = None, payment_method: Optional[str] = None,
                      status: Optional[str] = None, date_from: Optional[date] = None,
                      date_to: Optional[date] = None, search_text: Optional[str] = None,
                      page: int = 1, per_page: int = 20,
                      finance_period_start: Optional[date] = None,
                      sort_by: str = "payment_date", ascending: bool = False,
                      realized_only: bool = False) -> Tuple[List[Expense], int]:
        page = max(1, int(page)); per_page = max(1, int(per_page)); offset = (page - 1) * per_page
        with self._session_factory() as session:
            repo = self._repository_provider.expenses(session)
            kwargs = dict(category=category, payment_method=payment_method, status=status,
                          date_from=date_from, date_to=date_to, search_text=search_text,
                          finance_period_start=finance_period_start, realized_only=realized_only)
            return (repo.list_active(offset=offset, limit=per_page, sort_by=sort_by, ascending=ascending, **kwargs),
                    repo.count_active(**kwargs))

    @require_permission("finance.view")
    def export_expenses_csv(self, destination: str, category: Optional[str] = None,
                            payment_method: Optional[str] = None, status: Optional[str] = None,
                            date_from: Optional[date] = None, date_to: Optional[date] = None,
                            search_text: Optional[str] = None, finance_period_start: Optional[date] = None,
                            sort_by: str = "payment_date", ascending: bool = False) -> int:
        if not destination.lower().endswith(".csv"):
            destination += ".csv"
        with self._session_factory() as session:
            repo = self._repository_provider.expenses(session)
            kwargs = dict(category=category, payment_method=payment_method, status=status,
                          date_from=date_from, date_to=date_to, search_text=search_text,
                          finance_period_start=finance_period_start, realized_only=False)
            total = repo.count_active(**kwargs)
            rows = repo.list_active(offset=0, limit=max(total, 1), sort_by=sort_by,
                                    ascending=ascending, **kwargs) if total else []
        directory = os.path.dirname(os.path.abspath(destination))
        fd, temp_path = tempfile.mkstemp(prefix=".expense_export_", suffix=".csv", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Date", "Category", "Description", "Amount", "Payment Method", "Paid By", "Status", "Note"])
                for expense in rows:
                    writer.writerow([expense.payment_date.isoformat(), expense.category, expense.description or "",
                                     f"{expense.amount:.2f}", expense.payment_method, expense.paid_by or "",
                                     expense.status, expense.note or ""])
            os.replace(temp_path, destination)
        except Exception:
            try: os.unlink(temp_path)
            except OSError: pass
            raise
        return total

    @require_permission("finance.expense.update")
    def update_expense(self, expense_id: int, category: Optional[str] = None, description: Optional[str] = None,
                       amount: Optional[float] = None, payment_method: Optional[str] = None,
                       payment_date: Optional[date] = None, paid_by: Optional[str] = None,
                       status: Optional[str] = None, note: Optional[str] = None) -> Expense:
        with self._session_factory() as session:
            repo = self._repository_provider.expenses(session)
            expense = repo.get_by_id_including_deleted(expense_id)
            if not expense or expense.deleted_at is not None:
                raise ExpenseNotFoundError(f"Expense {expense_id} not found or deleted")
            changes = []
            updates = [("category", category, self._validate_category), ("description", description, self._normalize_text),
                       ("amount", amount, self._validate_amount), ("payment_method", payment_method, self._validate_payment_method),
                       ("payment_date", payment_date, self._validate_payment_date), ("paid_by", paid_by, self._normalize_text),
                       ("status", status, self._validate_status), ("note", note, self._normalize_text)]
            for field, value, validator in updates:
                if value is None: continue
                new_value = validator(value)
                if field == "description" and not new_value:
                    raise ExpenseValidationError("Description cannot be empty")
                old_value = getattr(expense, field)
                if old_value != new_value:
                    changes.append(f"{field}: {old_value} -> {new_value}")
                    setattr(expense, field, new_value)
            if not changes:
                return expense
            # Re-evaluate assignment from the final transaction state even when
            # only status changes (Pending -> Completed) or date crosses a period.
            new_period_id = self._resolve_posting_period_id(session, expense.payment_date, expense.status)
            if expense.finance_period_id != new_period_id:
                changes.append(f"finance_period_id: {expense.finance_period_id} -> {new_period_id}")
                expense.finance_period_id = new_period_id
            session.commit()
            repo.refresh(expense)
            self._log_timeline_best_effort(expense_id=expense.id, event_type="ExpenseUpdated", title="Expense Updated",
                                           description="; ".join(changes), metadata={"changes": changes})
            self._publish_finance_change("updated", expense.id)
            return expense

    @require_permission("finance.expense.delete")
    def delete_expense(self, expense_id: int) -> None:
        with self._session_factory() as session:
            repo = self._repository_provider.expenses(session)
            expense = repo.get_by_id_including_deleted(expense_id)
            if not expense or expense.deleted_at is not None:
                raise ExpenseNotFoundError(f"Expense {expense_id} not found or already deleted")
            category, amount = expense.category, expense.amount
            repo.soft_delete(expense)
            session.commit()
            self._log_timeline_best_effort(expense_id=expense_id, event_type="ExpenseDeleted", title="Expense Deleted",
                                           description=f"Expense {category} amount {amount:,.0f} VND deleted")
            self._publish_finance_change("deleted", expense_id)
