# -*- coding: utf-8 -*-
"""
Expense repository - data access for Expense entity.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from centermanager.models.expense import Expense
from centermanager.repositories.base import BaseRepository


class ExpenseRepository(BaseRepository[Expense]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Expense)

    def add(self, expense: Expense) -> Expense:
        self._session.add(expense)
        return expense

    def delete(self, expense: Expense) -> None:
        self._session.delete(expense)

    # Additional query methods can be added later