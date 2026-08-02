# -*- coding: utf-8 -*-
"""
FinanceService - aggregate service for finance module (placeholder).
"""
from sqlalchemy.orm import sessionmaker


class FinanceService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        # Future: can hold references to IncomeService, ExpenseService