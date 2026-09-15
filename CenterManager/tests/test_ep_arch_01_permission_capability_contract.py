from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "Deployment_Docs"
CONTRACT = DOCS / "590_PERMISSION_CAPABILITY_CONTRACT.md"
PLATFORM = DOCS / "575_PLATFORM_CONTRACT.md"


def test_permission_capability_contract_exists_and_declares_canonical_roles():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "# 590_PERMISSION_CAPABILITY_CONTRACT.md" in text
    for role in ("`ADMIN`", "`MANAGER`", "`EMPLOYEE`"):
        assert role in text


def test_canonical_capability_registry_contains_established_capabilities():
    text = CONTRACT.read_text(encoding="utf-8")
    capabilities = (
        "work_registration.view.all",
        "work_registration.manage",
        "work_registration.period.admin_override",
        "work_registration.delete",
        "employee.delete",
        "class.teacher_assignment.manage",
    )
    for capability in capabilities:
        assert f"`{capability}`" in text


def test_role_is_not_the_authorization_source_of_truth():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "Role -> Capability -> Authorization Decision" in text
    assert "role-name checks as a substitute for a capability check" in text
    assert "UI state never acts as the authorization source of truth" in text


def test_write_mode_and_edit_session_are_not_permissions():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "`WRITE` / `READ` is a workspace or interaction state." in text
    assert "It is not a permission" in text
    assert "Capability authorization does not bypass Edit Session rules." in text


def test_denial_has_no_mutation_and_admin_capabilities_are_explicit():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "A denied operation must not mutate business state." in text
    assert "work_registration.period.admin_override -> ADMIN only" in text
    assert "work_registration.delete                 -> ADMIN only" in text
    assert "employee.delete                          -> ADMIN only" in text


def test_platform_contract_registers_security_contract():
    text = PLATFORM.read_text(encoding="utf-8")
    assert "590_PERMISSION_CAPABILITY_CONTRACT.md" in text
    assert "Security Contracts" in text
    assert "Stable authorization vocabulary." in text
