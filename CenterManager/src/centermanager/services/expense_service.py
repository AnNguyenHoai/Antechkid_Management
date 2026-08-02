# -*- coding: utf-8 -*-
"""
ExpenseService - business logic for Expense entity (placeholder).
"""
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.expense import Expense
from centermanager.repositories.expense_repository import ExpenseRepository


class ExpenseService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def create_expense(self, **kwargs) -> Expense:
        raise NotImplementedError("Expense CRUD will be implemented in next sprint.")

    def get_expense(self, expense_id: int) -> Expense:
        raise NotImplementedError("Expense CRUD will be implemented in next sprint.")

    def list_expenses(self) -> List[Expense]:
        raise NotImplementedError("Expense CRUD will be implemented in next sprint.")

    def update_expense(self, expense_id: int, **kwargs) -> Expense:
        raise NotImplementedError("Expense CRUD will be implemented in next sprint.")

    def delete_expense(self, expense_id: int) -> None:
        raise NotImplementedError("Expense CRUD will be implemented in next sprint.")