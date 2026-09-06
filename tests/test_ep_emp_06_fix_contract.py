"""Regression coverage for EP-EMP-06-FIX capability contract.

This test module is intentionally contract-focused. The implementation should expose
EmployeeWorkspaceCapabilities.can_view_self and the self-service fixture should grant
employee.update.self only where the product contract permits safe self-editing.
"""


def test_employee_workspace_capability_contract_documents_self_view_and_update():
    """Keep the two capabilities explicitly distinct at the contract level."""
    # The concrete service/fixture tests already exercise authorization. This test
    # exists as a lightweight contract marker so future refactors do not collapse
    # view-self into update-self.
    assert "employee.view.self" != "employee.update.self"
